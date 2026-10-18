"""Mittausdata aallonharjalle: konversio, Search Console ja PostHog (18.10.2026, Villen GO).

Ajetaan aallonharjan omassa työssä, jolla on lukuavaimet (ADMIN_TOKEN, GSC_SERVICE_ACCOUNT_JSON,
POSTHOG_PERSONAL_API_KEY). Agenttityö EI saa näitä avaimia (tests/test_auto_kehitys_workflow.py), vaan
lukee tämän tiedoston tuotoksen artefaktista.

JULKISUUSSÄÄNTÖ TEHDÄÄN TÄSSÄ, EI PROMPTISSA (CLAUDE.md 6a kohta 1). Agentti kirjoittaa julkiseen
repoon (BENCHMARK.md, AUTO-BACKLOG.md), joten se saa vain lukuja, jotka saavat näkyä julkisesti:
suhdeluvut (konversio-%, CTR, sijainti), muutosprosentit ja kokoluokat (0, 1-9, 10-99, 100-999, 1000+).
Tilien, Premiumien, käyntien ja tapahtumien absoluuttisia määriä ei koskaan kirjoiteta tuotokseen,
joten agentti ei voi vuotaa niitä.

Puuttuva lähde on "puuttuu" syineen, ei nolla: tyhjä ei ole sama kuin "ei käyttöä".
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path

import requests

API = "https://goaliq-api.onrender.com"
GSC_SITE = "sc-domain:goaliq.app"
POSTHOG_HOST = "https://us.posthog.com"  # web/pro-spa/src/lib/analytics.ts: us.i.posthog.com
POSTHOG_PROJEKTI = 427890
TIMEOUT = 60


def kokoluokka(n: int | float | None) -> str | None:
    if n is None:
        return None
    n = int(n)
    if n <= 0:
        return "0"
    if n < 10:
        return "1-9"
    if n < 100:
        return "10-99"
    if n < 1000:
        return "100-999"
    return "1000+"


def muutos_pct(nyt: float | None, ennen: float | None) -> float | None:
    if nyt is None or ennen is None or ennen == 0:
        return None
    return round((nyt - ennen) / ennen * 100, 1)


def _puuttuu(syy: str) -> dict:
    return {"tila": "puuttuu", "syy": syy}


def _virhe(e: Exception) -> dict:
    return {"tila": "virhe", "syy": f"{type(e).__name__}: {str(e)[:200]}"}


# ------------------------------------------------------------------ konversio

def siivoa_konversio(doc: dict) -> dict:
    """Vain suhdeluku ja liput. total_accounts ja premium_accounts jäävät pois tarkoituksella."""
    return {
        "tila": "ok",
        "konversio_pct_min": doc.get("conversion_pct_min"),
        "konversio_pct_max": doc.get("conversion_pct_max"),
        "tarkka": bool(doc.get("conversion_exact")),
        "vertailukelpoinen": doc.get("comparable"),
        "ilmaisikkuna_paalla": doc.get("window_active"),
    }


def hae_konversio(token: str | None) -> dict:
    if not token:
        return _puuttuu("ADMIN_TOKEN ei asetettu")
    try:
        r = requests.get(f"{API}/api/admin/conversion", headers={"X-Admin-Token": token}, timeout=TIMEOUT)
        if r.status_code != 200:
            return {"tila": "virhe", "syy": f"HTTP {r.status_code}"}
        return siivoa_konversio(r.json())
    except Exception as e:  # noqa: BLE001 - yksi lähde ei saa kaataa muita
        return _virhe(e)


# ------------------------------------------------------------------ Search Console

def siivoa_gsc(nyt: list[dict], ennen: list[dict], avain: str, n: int = 40) -> list[dict]:
    """GSC-rivit -> julkisesti turvallinen lista: sija näyttöjen mukaan, CTR, sijainti, muutos-%."""
    ennen_map = {r["keys"][0]: r for r in ennen if r.get("keys")}
    jarj = sorted((r for r in nyt if r.get("keys")), key=lambda r: -r.get("impressions", 0))[:n]
    out = []
    for i, r in enumerate(jarj, start=1):
        e = ennen_map.get(r["keys"][0], {})
        out.append({
            avain: r["keys"][0],
            "nayttosija": i,
            "nayttoja": kokoluokka(r.get("impressions")),
            "ctr_pct": round(100 * r.get("ctr", 0), 2),
            "sijainti": round(r.get("position", 0), 1),
            "naytot_muutos_pct": muutos_pct(r.get("impressions"), e.get("impressions")),
            "klikit_muutos_pct": muutos_pct(r.get("clicks"), e.get("clicks")),
        })
    return out


def hae_gsc(avain_json: str | None, paiva: _dt.date) -> dict:
    if not avain_json:
        return _puuttuu("GSC_SERVICE_ACCOUNT_JSON ei asetettu")
    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account
    except ImportError:
        return _puuttuu("google-auth ei asennettu tähän työhön")
    try:
        cr = service_account.Credentials.from_service_account_info(
            json.loads(avain_json), scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
        s = AuthorizedSession(cr)
        url = (f"https://www.googleapis.com/webmasters/v3/sites/{requests.utils.quote(GSC_SITE, safe='')}"
               "/searchAnalytics/query")
        # GSC:n data laahaa noin 2-3 vrk, joten jakso päättyy 3 päivää sitten.
        loppu = paiva - _dt.timedelta(days=3)
        nyt_alku = loppu - _dt.timedelta(days=27)
        ennen_loppu = nyt_alku - _dt.timedelta(days=1)
        ennen_alku = ennen_loppu - _dt.timedelta(days=27)

        def kysy(alku, loppu_, dim):
            r = s.post(url, json={"startDate": alku.isoformat(), "endDate": loppu_.isoformat(),
                                  "dimensions": [dim], "rowLimit": 250}, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json().get("rows", [])

        def yhteensa(alku, loppu_):
            r = s.post(url, json={"startDate": alku.isoformat(), "endDate": loppu_.isoformat()}, timeout=TIMEOUT)
            r.raise_for_status()
            rivit = r.json().get("rows", [])
            return rivit[0] if rivit else {}

        y_nyt, y_ennen = yhteensa(nyt_alku, loppu), yhteensa(ennen_alku, ennen_loppu)
        return {
            "tila": "ok",
            "jakso": f"{nyt_alku} - {loppu} vs {ennen_alku} - {ennen_loppu}",
            "yhteensa": {
                "ctr_pct": round(100 * y_nyt.get("ctr", 0), 2),
                "sijainti": round(y_nyt.get("position", 0), 1),
                "naytot_muutos_pct": muutos_pct(y_nyt.get("impressions"), y_ennen.get("impressions")),
                "klikit_muutos_pct": muutos_pct(y_nyt.get("clicks"), y_ennen.get("clicks")),
            },
            "sivut": siivoa_gsc(kysy(nyt_alku, loppu, "page"), kysy(ennen_alku, ennen_loppu, "page"), "sivu"),
            "haut": siivoa_gsc(kysy(nyt_alku, loppu, "query"), kysy(ennen_alku, ennen_loppu, "query"), "haku"),
        }
    except Exception as e:  # noqa: BLE001
        return _virhe(e)


# ------------------------------------------------------------------ PostHog

HOGQL_TAPAHTUMAT = """
SELECT event,
       countIf(timestamp > now() - INTERVAL 28 DAY) AS nyt,
       countIf(timestamp <= now() - INTERVAL 28 DAY) AS ennen
FROM events
WHERE timestamp > now() - INTERVAL 56 DAY
GROUP BY event
ORDER BY nyt DESC
LIMIT 80
"""

HOGQL_SIVUT = """
SELECT properties.$host AS isanta, properties.$pathname AS polku,
       countIf(timestamp > now() - INTERVAL 28 DAY) AS nyt,
       countIf(timestamp <= now() - INTERVAL 28 DAY) AS ennen
FROM events
WHERE event = '$pageview' AND timestamp > now() - INTERVAL 56 DAY
GROUP BY isanta, polku
ORDER BY nyt DESC
LIMIT 60
"""


def siivoa_posthog(rivit: list[list], nimet: list[str]) -> list[dict]:
    out = []
    for r in rivit:
        d = dict(zip(nimet, r))
        nyt, ennen = d.pop("nyt", 0) or 0, d.pop("ennen", 0) or 0
        d["kokoluokka_28vrk"] = kokoluokka(nyt)
        d["muutos_pct"] = muutos_pct(nyt, ennen)
        out.append(d)
    return out


def hae_posthog(avain: str | None) -> dict:
    if not avain:
        return _puuttuu("POSTHOG_PERSONAL_API_KEY ei asetettu")
    try:
        def kysy(hogql: str, nimet: list[str]) -> list[dict]:
            r = requests.post(f"{POSTHOG_HOST}/api/projects/{POSTHOG_PROJEKTI}/query/",
                              headers={"Authorization": f"Bearer {avain}"},
                              json={"query": {"kind": "HogQLQuery", "query": hogql}}, timeout=TIMEOUT)
            r.raise_for_status()
            return siivoa_posthog(r.json().get("results", []), nimet)

        return {
            "tila": "ok",
            "jakso": "viimeiset 28 vrk vs sitä edeltävät 28 vrk",
            "tapahtumat": kysy(HOGQL_TAPAHTUMAT, ["tapahtuma", "nyt", "ennen"]),
            "sivut": kysy(HOGQL_SIVUT, ["isanta", "polku", "nyt", "ennen"]),
        }
    except Exception as e:  # noqa: BLE001
        return _virhe(e)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--pvm", default=_dt.date.today().isoformat())
    a = ap.parse_args(argv)
    paiva = _dt.date.fromisoformat(a.pvm)
    kansio = Path(a.out)
    kansio.mkdir(parents=True, exist_ok=True)
    tulokset = {
        "konversio": hae_konversio(os.environ.get("ADMIN_TOKEN")),
        "gsc": hae_gsc(os.environ.get("GSC_SERVICE_ACCOUNT_JSON"), paiva),
        "posthog": hae_posthog(os.environ.get("POSTHOG_PERSONAL_API_KEY")),
    }
    for nimi, doc in tulokset.items():
        (kansio / f"{nimi}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{nimi}: {doc['tila']}" + (f" ({doc.get('syy')})" if doc["tila"] != "ok" else ""))
    # Lähde saa puuttua (näkyy agentille ja raportissa), mutta jos KAIKKI puuttuvat, mittaus ei toimi.
    if all(d["tila"] != "ok" for d in tulokset.values()):
        print("::error::yksikään mittauslähde ei vastannut")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
