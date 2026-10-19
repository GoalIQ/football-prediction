"""X-viikkoketju: mallin oman FPL-joukkueen kierroskatsaus X-jonoon (19.10.2026, ylläpitäjän päätös).

X:ään ei postata automaattisesti (maksullinen API ja X:n automaatiosäännöt). Kun kierros on FPL:ssä lopullinen
(`finished` ja `data_checked`), tämä tekee ylläpitäjälle issuen (label x-jono, sama kanava kuin Bluesky-botin
X-jono), jossa on valmis 4 viestin ketju. Ylläpitäjä postaa sen itse.

Miksi juuri tämä luku: entry 116920 on FPL:n oma, kenen tahansa tarkistettava luku (FPL:n sivulla), eikä sitä
voi muokata jälkikäteen. Se on ainoa todiste, jonka lukija voi tarkistaa ilman meidän sivujamme.

Säännöt (CLAUDE.md 6a: väärä vaihtoehto mahdottomaksi):
  * Luvut vain FPL:n rajapinnasta tällä ajolla (lähde ensin), ei johdetuista tiedostoista.
  * Vain uusin lopullinen kierros, ja vain ennen seuraavan kierroksen deadlinea: vanha katsaus ei kuulu X:ään.
  * Kauden ero lasketaan FPL:n kokonaispisteistä (hitit vähennetty) FPL:n julkaisemien kierroskeskiarvojen
    summaa vastaan. Jos keskiarvo on ennen hittejä, ero on meille epäedullinen, ei edullinen.
  * Idempotentti: sama kierros ei saa toista issueta (otsikko haetaan olemassa olevista, myös suljetuista).
  * Kolme pohjaa vuorotellen (sama runko joka viikko on AI-tunnusmerkki). Pohjat ovat julkaisutarkistajan
    hyväksymät 19.10; muutos pohjaan = uusi tarkistus ennen mergeä.

Ajo: python scripts/x_viikkoketju.py [--kuiva]   (GH_TOKEN ympäristössä; ilman sitä kuiva)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ENTRY = 116920
FPL = "https://fantasy.premierleague.com/api"
FPL_SIVU = f"https://fantasy.premierleague.com/entry/{ENTRY}/history"
SITE = "https://goaliq.app"
REPO = "GoalIQ/football-prediction"
LABEL = "x-jono"
ASSIGNEE = "Veikkoville"
OTSIKKO = "X-ketju: mallin joukkue GW{gw}"
X_MAX = 280
X_URL_LEN = 23
CHIPIT = {"bboost": "Bench Boost", "3xc": "Triple Captain", "wildcard": "Wildcard", "freehit": "Free Hit"}
_URL = re.compile(r"https?://\S+")
UA = {"User-Agent": "GoalIQ x-viikkoketju (+https://goaliq.app)"}


def x_pituus(teksti: str) -> int:
    return len(_URL.sub("", teksti)) + X_URL_LEN * len(_URL.findall(teksti))


def _hae(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def lopullinen_kierros(bootstrap: dict, nyt: datetime) -> int | None:
    """Uusin kierros, joka on finished ja data_checked, jos seuraavan kierroksen deadline ei ole mennyt."""
    events = sorted(bootstrap.get("events") or [], key=lambda e: e["id"])
    valmiit = [e for e in events if e.get("finished") and e.get("data_checked")]
    if not valmiit:
        return None
    gw = valmiit[-1]["id"]
    seuraava = next((e for e in events if e["id"] == gw + 1), None)
    if seuraava and seuraava.get("deadline_time"):
        deadline = datetime.fromisoformat(seuraava["deadline_time"].replace("Z", "+00:00"))
        if deadline <= nyt:
            return None
    return gw


def kokoa(gw: int, bootstrap: dict, historia: dict, picks: dict, live: dict) -> dict:
    events = {e["id"]: e for e in bootstrap["events"]}
    rivit = {r["event"]: r for r in historia["current"]}
    r = rivit[gw]
    keskiarvot = [events[g]["average_entry_score"] for g in sorted(rivit) if g <= gw]
    kapteeni = next(p for p in picks["picks"] if p.get("is_captain"))
    pelaajat = {e["id"]: e["web_name"] for e in bootstrap["elements"]}
    kapt_pisteet = next((e["stats"]["total_points"] for e in live["elements"] if e["id"] == kapteeni["element"]), None)
    managereita = int(bootstrap["total_players"])
    return {
        "gw": gw, "pisteet": int(r["points"]), "hitti": int(r.get("event_transfers_cost") or 0),
        "keskiarvo": int(events[gw]["average_entry_score"]),
        "kokonais": int(r["total_points"]), "keskiarvo_summa": int(sum(keskiarvot)),
        "sijoitus": int(r["overall_rank"]), "managereita": managereita,
        "top_pct": math.ceil(int(r["overall_rank"]) / managereita * 100),
        "kapteeni": pelaajat.get(kapteeni["element"], "?"), "kapteeni_pisteet": kapt_pisteet,
        "kerroin": int(kapteeni.get("multiplier") or 2), "chip": CHIPIT.get(picks.get("active_chip") or ""),
        "seuraava": gw + 1 if (gw + 1) in events else None,
    }


def _p(n: int) -> str:
    return f"{n} point" if abs(n) == 1 else f"{n} points"


def _ero(n: int) -> str:
    return f"{_p(n)} above" if n > 0 else f"{_p(-n)} below" if n < 0 else "level with"


def _milj(n: int) -> str:
    return f"{n / 1_000_000:.1f} million"


def _linkki(gw: int) -> str:
    q = urllib.parse.urlencode({"utm_source": "x", "utm_medium": "partner", "utm_campaign": "model_entry",
                                "utm_content": f"gw{gw}"})
    return f"{SITE}/fpl?{q}"


def ketju(d: dict) -> list[str]:
    gw, ero = d["gw"], d["kokonais"] - d["keskiarvo_summa"]
    kierros = _p(d["pisteet"]) + (f" before a {d['hitti']}-point hit" if d["hitti"] else "")
    if d["kapteeni_pisteet"] is None:
        kapt = f"Captain: {d['kapteeni']}."
    else:
        sana = "tripled" if d["kerroin"] == 3 else "doubled"
        kapt = f"Captain: {d['kapteeni']}, {_p(d['kapteeni_pisteet'])} {sana} to {d['kapteeni_pisteet'] * d['kerroin']}."
    # Chipit ovat meidän päätöksiämme, eivät mallin: "model's own FPL team" on hylätty 29.9
    # (data/rejected_phrases.json). Sanamuodot alla ovat hylkäyslistan hyväksyttyjä korvaajia.
    chip = f" We played {d['chip']}." if d["chip"] else ""
    kausi = (f"Season: {d['kokonais']} points, {_ero(ero)} the sum of FPL's gameweek averages. "
             f"Overall rank {d['sijoitus']:,} of {_milj(d['managereita'])}, top {d['top_pct']}%.")
    tarkistus = (f"The model's squad is frozen before each deadline, and entry {ENTRY} plays it with our own calls. "
                 f"Every number here is on FPL's site: {FPL_SIVU}")
    seuraava = f"GW{d['seuraava']}" if d["seuraava"] else "the next gameweek"
    cta = f"The model's {seuraava} picks and xP for every player: {_linkki(gw)}"
    pohja = gw % 3
    if pohja == 0:
        viestit = [f"We play our model's squad in FPL (entry {ENTRY}). GW{gw}: {kierros}, against an average of "
                   f"{d['keskiarvo']}.", f"{kapt}{chip}", kausi, f"{tarkistus}\n\n{cta}"]
    elif pohja == 1:
        viestit = [f"GW{gw} for our model's squad in FPL: {kierros}. The average manager scored {d['keskiarvo']}.{chip}",
                   kausi, f"{kapt} {tarkistus}", cta]
    else:
        viestit = [f"How our model's squad did in FPL in GW{gw}: {kierros}, average {d['keskiarvo']}.",
                   f"{kapt}{chip}", kausi, f"{tarkistus}\n\n{cta}"]
    for v in viestit:
        if x_pituus(v) > X_MAX or "—" in v or "–" in v:
            raise ValueError(f"viesti ei kelpaa X:ään ({x_pituus(v)} merkkiä): {v[:60]}")
    return viestit


def issue(d: dict, viestit: list[str]) -> dict:
    osat = [f"Kopioi X:ään ketjuna (@goaliqapp): ensimmäinen viesti ensin, loput vastauksina edelliseen. "
            f"Luvut FPL:n rajapinnasta {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC (GW{d['gw']} finished ja "
            f"data_checked). Postaa ennen GW{d['seuraava'] or '?'}-deadlinea tai sulje ohitettuna."]
    for i, v in enumerate(viestit, 1):
        osat.append(f"**{i}/{len(viestit)}** ({x_pituus(v)}/{X_MAX})\n\n```\n{v}\n```")
    osat.append(f"Tarkistus: {FPL_SIVU} · Sulje issue, kun postattu tai ohitettu.")
    return {"title": OTSIKKO.format(gw=d["gw"]), "body": "\n\n".join(osat),
            "assignees": [ASSIGNEE], "labels": [LABEL]}


def _gh(metodi: str, polku: str, token: str, data: dict | None = None):
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}{polku}", method=metodi,
                                 data=json.dumps(data).encode("utf-8") if data is not None else None,
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def on_jo(otsikko: str, token: str) -> bool:
    for sivu in range(1, 6):
        rivit = _gh("GET", f"/issues?labels={LABEL}&state=all&per_page=100&page={sivu}", token)
        if any(r.get("title") == otsikko for r in rivit):
            return True
        if len(rivit) < 100:
            return False
    return True  # yli 500 issueta: varmuuden vuoksi ei tuplaa


def main(argv=None, nyt: datetime | None = None, hae=_hae) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kuiva", action="store_true")
    a = ap.parse_args(argv)
    nyt = nyt or datetime.now(timezone.utc)
    bootstrap = hae(f"{FPL}/bootstrap-static/")
    gw = lopullinen_kierros(bootstrap, nyt)
    if gw is None:
        print("X-ketju: ei lopullista kierrosta ennen seuraavaa deadlinea, ei tehtävää.")
        return 0
    token = os.environ.get("GH_TOKEN", "").strip()
    otsikko = OTSIKKO.format(gw=gw)
    if token and not a.kuiva and on_jo(otsikko, token):
        print(f"X-ketju: {otsikko} on jo tehty.")
        return 0
    d = kokoa(gw, bootstrap, hae(f"{FPL}/entry/{ENTRY}/history/"), hae(f"{FPL}/entry/{ENTRY}/event/{gw}/picks/"),
              hae(f"{FPL}/event/{gw}/live/"))
    payload = issue(d, ketju(d))
    if a.kuiva or not token:
        print(f"[KUIVA] {payload['title']}\n\n{payload['body']}")
        return 0
    tulos = _gh("POST", "/issues", token, payload)
    print(f"X-ketju: {tulos.get('html_url')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
