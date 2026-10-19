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

TASON MUUTOS LASKETAAN MEDIAANISTA, EI 28 VRK:N SUMMASTA (19.10.2026). Ensimmäinen mittaus 18.10 antoi
Search Consolen näytöille -83,5 %, ja se kirjattiin pudotukseksi. Päiväsarja näytti muuta: vertailujakson
näytöistä yli puolet tuli kolmena päivänä (kauden alun piikki 21.8 ja sitä seuranneet päivät), ja taso oli
sama kuin heinäkuussa. Klikit muuttuivat -22 %. Siksi GSC-tuotos kertoo päivämediaanin muutoksen,
piikkipäivien osuuden ja valmiin tulkinnan, ja PostHog uniikit viikkokäyttäjät pinnoittain (tapahtumamäärää
nostaa muutama raskas käyttäjä). Lukija ei voi saada kokonaismuutosta ilman tulkintaa vieressä.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import statistics
import sys
from pathlib import Path

import requests

API = "https://goaliq-api.onrender.com"
GSC_SITE = "sc-domain:goaliq.app"
POSTHOG_HOST = "https://us.posthog.com"  # web/pro-spa/src/lib/analytics.ts: us.i.posthog.com
POSTHOG_PROJEKTI = 427890
TIMEOUT = 60
# Tasaisessa 28 päivän jaksossa kolmen suurimman päivän osuus on noin 11 %. Yli 35 %:n osuus tarkoittaa,
# että jakson summa kertoo lähinnä yksittäisistä päivistä (18.10 mitattuna vertailujaksossa 54 %).
PIIKKI_RAJA_PCT = 35.0
BRANDI = re.compile(r"goal\s*-?\s*iq", re.IGNORECASE)


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
        # 19.10.2026 (backlog-rivi "Entry ID -osuus konversioaggregaattiin"): None, kunnes API palauttaa kentät.
        "entry_id_osuus_pct_ilmainen": doc.get("entry_id_share_pct_free"),
        "entry_id_osuus_pct_premium": doc.get("entry_id_share_pct_premium"),
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


def siivoa_gsc_ennen(nyt: list[dict], ennen: list[dict], avain: str, n: int = 20) -> list[dict]:
    """Vertailujakson suurimmat. siivoa_gsc listaa vain nykyjakson rivit, joten kokonaan kadonnut sivu
    ei näkyisi siinä lainkaan; täällä sen muutos on -100 %."""
    nyt_map = {r["keys"][0]: r for r in nyt if r.get("keys")}
    jarj = sorted((r for r in ennen if r.get("keys")), key=lambda r: -r.get("impressions", 0))[:n]
    return [{
        avain: r["keys"][0],
        "nayttosija_ennen": i,
        "nayttoja_ennen": kokoluokka(r.get("impressions")),
        "naytot_muutos_pct": muutos_pct(nyt_map.get(r["keys"][0], {}).get("impressions", 0), r.get("impressions")),
    } for i, r in enumerate(jarj, start=1)]


def _paivasarja(rivit: list[dict], alku: _dt.date, loppu: _dt.date, kentta: str) -> list[float]:
    """GSC jättää nollapäivät pois, joten sarja täytetään koko jaksolle (muuten mediaani nousee)."""
    arvot = {r["keys"][0]: r.get(kentta, 0) or 0 for r in rivit if r.get("keys")}
    return [arvot.get((alku + _dt.timedelta(days=i)).isoformat(), 0) for i in range((loppu - alku).days + 1)]


def _huippu3_osuus(sarja: list[float]) -> float | None:
    summa = sum(sarja)
    return round(100 * sum(sorted(sarja, reverse=True)[:3]) / summa, 1) if summa else None


def gsc_paivatunnusluvut(nyt: list[dict], ennen: list[dict], nyt_alku: _dt.date, nyt_loppu: _dt.date,
                         ennen_alku: _dt.date, ennen_loppu: _dt.date) -> dict:
    """Päivärivit (dimensio date) -> mediaanimuutos, piikkipäivien osuus ja tulkinta."""
    nn, en = (_paivasarja(nyt, nyt_alku, nyt_loppu, "impressions"),
              _paivasarja(ennen, ennen_alku, ennen_loppu, "impressions"))
    nk, ek = _paivasarja(nyt, nyt_alku, nyt_loppu, "clicks"), _paivasarja(ennen, ennen_alku, ennen_loppu, "clicks")
    h_nyt, h_ennen = _huippu3_osuus(nn), _huippu3_osuus(en)
    huiput = sorted((r for r in ennen if r.get("keys")), key=lambda r: -r.get("impressions", 0))[:3]
    piikki_ennen = h_ennen is not None and h_ennen >= PIIKKI_RAJA_PCT
    piikki_nyt = h_nyt is not None and h_nyt >= PIIKKI_RAJA_PCT
    if piikki_ennen:
        tulkinta = (f"Vertailujakson näytöistä {h_ennen} % tuli kolmena päivänä "
                    f"({', '.join(r['keys'][0] for r in huiput)}). Kokonaismuutos mittaa piikin loppumista, "
                    "ei tason muutosta: käytä mediaanimuutosta.")
    elif piikki_nyt:
        tulkinta = (f"Tämän jakson näytöistä {h_nyt} % tuli kolmena päivänä. Kokonaismuutos mittaa piikkiä, "
                    "ei tason muutosta: käytä mediaanimuutosta.")
    else:
        tulkinta = "Kummassakaan jaksossa ei ole piikkiä: kokonaismuutos ja mediaanimuutos ovat vertailukelpoisia."
    return {
        "naytot_mediaani_muutos_pct": muutos_pct(statistics.median(nn), statistics.median(en)),
        "klikit_mediaani_muutos_pct": muutos_pct(statistics.median(nk), statistics.median(ek)),
        "naytot_paivamediaani": kokoluokka(statistics.median(nn)),
        "klikit_paivamediaani": kokoluokka(statistics.median(nk)),
        "huippu3_osuus_pct": {"nyt": h_nyt, "ennen": h_ennen},
        "piikki_vertailujaksossa": piikki_ennen,
        "piikki_tassa_jaksossa": piikki_nyt,
        "tulkinta": tulkinta,
    }


def brandin_osuus_klikeista(haut: list[dict]) -> float | None:
    """Osuus hakuriveihin kirjatuista klikeistä. Google anonymisoi harvinaiset haut, eivätkä ne ole mukana."""
    kaikki = sum(r.get("clicks", 0) for r in haut if r.get("keys"))
    brandi = sum(r.get("clicks", 0) for r in haut if r.get("keys") and BRANDI.search(r["keys"][0]))
    return round(100 * brandi / kaikki, 1) if kaikki else None


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
        sivut_nyt, sivut_ennen = kysy(nyt_alku, loppu, "page"), kysy(ennen_alku, ennen_loppu, "page")
        haut_nyt, haut_ennen = kysy(nyt_alku, loppu, "query"), kysy(ennen_alku, ennen_loppu, "query")
        return {
            "tila": "ok",
            "jakso": f"{nyt_alku} - {loppu} vs {ennen_alku} - {ennen_loppu}",
            "yhteensa": {
                "ctr_pct": round(100 * y_nyt.get("ctr", 0), 2),
                "sijainti": round(y_nyt.get("position", 0), 1),
                "naytot_muutos_pct": muutos_pct(y_nyt.get("impressions"), y_ennen.get("impressions")),
                "klikit_muutos_pct": muutos_pct(y_nyt.get("clicks"), y_ennen.get("clicks")),
                "brandihaut_klikeista_pct": brandin_osuus_klikeista(haut_nyt),
                **gsc_paivatunnusluvut(kysy(nyt_alku, loppu, "date"), kysy(ennen_alku, ennen_loppu, "date"),
                                       nyt_alku, loppu, ennen_alku, ennen_loppu),
            },
            "sivut": siivoa_gsc(sivut_nyt, sivut_ennen, "sivu"),
            "sivut_vertailujaksossa": siivoa_gsc_ennen(sivut_nyt, sivut_ennen, "sivu"),
            "haut": siivoa_gsc(haut_nyt, haut_ennen, "haku"),
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


# Uniikit käyttäjät täysiltä viikoilta (kesken oleva viikko jää pois, ettei se näytä pudotukselta).
# Tapahtumamäärä ei käy tasoksi: 18.10 mitattuna fantasy_tools_used -79 %, mutta viikon tapahtumista
# suurimman osan teki muutama käyttäjä.
VIIKKOPINNAT = ("sovellus", "spa", "hub", "tyokalut")
HOGQL_VIIKOT = """
SELECT toStartOfWeek(timestamp, 1) AS viikko,
       uniqIf(distinct_id, event = 'app_opened') AS sovellus,
       uniqIf(distinct_id, event = '$pageview' AND properties.$host = 'pro.goaliq.app') AS spa,
       uniqIf(distinct_id, event = '$pageview' AND properties.$host = 'goaliq.app') AS hub,
       uniqIf(distinct_id, event = 'fantasy_tools_used') AS tyokalut
FROM events
WHERE timestamp >= toStartOfWeek(now() - INTERVAL 10 WEEK, 1) AND timestamp < toStartOfWeek(now(), 1)
GROUP BY viikko
ORDER BY viikko
"""


# 19.10.2026 (ylläpitäjän päätös, automaatio myynnin palvelukseen): ostopolku lukosta ostoon lähteittäin ja
# alustoittain. Web ja mobiili lähettävät samat tapahtumat (paywall_shown, upgrade_tapped, purchase_completed),
# ja source kertoo lukon. Uniikit käyttäjät, ei tapahtumia: sama käyttäjä voi nähdä saman lukon kymmeniä kertoja.
# Webin purchase_completed kantaa lähteen "web", joten osto per lukko luetaan alustoittaisesta rivistä.
OSTOPOLKU_VAIHEET = ("lukko", "napautus", "osto")
PIENI_OTOS = 10
_OSTOPOLKU_SARAKKEET = """
       uniqIf(distinct_id, event = 'paywall_shown' AND timestamp > now() - INTERVAL 28 DAY) AS lukko_nyt,
       uniqIf(distinct_id, event = 'upgrade_tapped' AND timestamp > now() - INTERVAL 28 DAY) AS napautus_nyt,
       uniqIf(distinct_id, event = 'purchase_completed' AND timestamp > now() - INTERVAL 28 DAY) AS osto_nyt,
       uniqIf(distinct_id, event = 'paywall_shown' AND timestamp <= now() - INTERVAL 28 DAY) AS lukko_ennen,
       uniqIf(distinct_id, event = 'upgrade_tapped' AND timestamp <= now() - INTERVAL 28 DAY) AS napautus_ennen,
       uniqIf(distinct_id, event = 'purchase_completed' AND timestamp <= now() - INTERVAL 28 DAY) AS osto_ennen
FROM events
WHERE event IN ('paywall_shown', 'upgrade_tapped', 'purchase_completed') AND timestamp > now() - INTERVAL 56 DAY"""
_ALUSTA = "if(properties.$lib = 'posthog-react-native', 'mobiili', 'web')"
HOGQL_OSTOPOLKU_LAHTEET = (f"SELECT coalesce(toString(properties.source), '?') AS lahde, {_ALUSTA} AS alusta,"
                           f"{_OSTOPOLKU_SARAKKEET}\nGROUP BY lahde, alusta\nORDER BY lukko_nyt DESC\nLIMIT 60")
HOGQL_OSTOPOLKU_ALUSTAT = f"SELECT {_ALUSTA} AS alusta,{_OSTOPOLKU_SARAKKEET}\nGROUP BY alusta"


def _suhde_pct(osoittaja: float, nimittaja: float) -> float | None:
    return round(osoittaja / nimittaja * 100, 1) if nimittaja else None


def siivoa_ostopolku(rivit: list[list], avaimet: tuple[str, ...]) -> list[dict]:
    """Rivi -> vaiheiden kokoluokat ja suhdeluvut (napautus/lukko, osto/napautus) kummallekin jaksolle."""
    sarakkeet = avaimet + tuple(f"{v}_{j}" for j in ("nyt", "ennen") for v in OSTOPOLKU_VAIHEET)
    out = []
    for r in rivit:
        d = dict(zip(sarakkeet, r))
        rivi = {k: re.sub(r"[^A-Za-z0-9_:.-]", "", str(d[k]))[:40] for k in avaimet}
        for j in ("nyt", "ennen"):
            lukko, napautus, osto = (int(d.get(f"{v}_{j}") or 0) for v in OSTOPOLKU_VAIHEET)
            rivi[j] = {"lukko": kokoluokka(lukko), "napautus": kokoluokka(napautus), "osto": kokoluokka(osto),
                       "napautus_lukosta_pct": _suhde_pct(napautus, lukko),
                       "osto_napautuksesta_pct": _suhde_pct(osto, napautus),
                       "pieni_otos": lukko < PIENI_OTOS}
        out.append(rivi)
    return out


def siivoa_viikot(rivit: list[list]) -> list[dict]:
    """Viikkorivit -> kokoluokka ja muutos edelliseen viikkoon pinnoittain, ei määriä."""
    out, edellinen = [], None
    for r in rivit:
        d = dict(zip(("viikko",) + VIIKKOPINNAT, r))
        rivi = {"viikko": str(d["viikko"])[:10]}
        for p in VIIKKOPINNAT:
            rivi[p] = {"kayttajia": kokoluokka(d[p]),
                       "muutos_edellisesta_pct": muutos_pct(d[p], edellinen[p]) if edellinen else None}
        out.append(rivi)
        edellinen = d
    return out


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
        def kysy(hogql: str) -> list[list]:
            r = requests.post(f"{POSTHOG_HOST}/api/projects/{POSTHOG_PROJEKTI}/query/",
                              headers={"Authorization": f"Bearer {avain}"},
                              json={"query": {"kind": "HogQLQuery", "query": hogql}}, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json().get("results", [])

        return {
            "tila": "ok",
            "jakso": "viimeiset 28 vrk vs sitä edeltävät 28 vrk",
            "viikkokayttajat": siivoa_viikot(kysy(HOGQL_VIIKOT)),
            "tapahtumat": siivoa_posthog(kysy(HOGQL_TAPAHTUMAT), ["tapahtuma", "nyt", "ennen"]),
            "sivut": siivoa_posthog(kysy(HOGQL_SIVUT), ["isanta", "polku", "nyt", "ennen"]),
            "ostopolku": {
                "selite": ("uniikit käyttäjät: lukko = paywall_shown, napautus = upgrade_tapped, osto = "
                           "purchase_completed; webin osto kantaa lähteen 'web', joten osto lukkoa kohden "
                           f"luetaan alustoittain; pieni_otos = alle {PIENI_OTOS} lukon näkijää, suhde ei kanna"),
                "lahteittain": siivoa_ostopolku(kysy(HOGQL_OSTOPOLKU_LAHTEET), ("lahde", "alusta")),
                "alustoittain": siivoa_ostopolku(kysy(HOGQL_OSTOPOLKU_ALUSTAT), ("alusta",)),
            },
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
