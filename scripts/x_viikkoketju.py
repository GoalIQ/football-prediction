"""X-viikkoketju: mallin oman FPL-joukkueen kierroskatsaus X-jonoon (19.10.2026, ylläpitäjän päätös).

X:ään ei postata automaattisesti (maksullinen API ja X:n automaatiosäännöt). Kun kierros on FPL:ssä lopullinen
(`finished` ja `data_checked`), tämä tekee ylläpitäjälle issuen (label x-jono, sama kanava kuin Bluesky-botin
X-jono), jossa on valmis 2-3 viestin ketju. Ylläpitäjä postaa sen itse.

Miksi juuri tämä luku: entry 116920 on FPL:n oma, kenen tahansa tarkistettava luku (FPL:n sivulla), eikä sitä
voi muokata jälkikäteen. Se on ainoa todiste, jonka lukija voi tarkistaa ilman meidän sivujamme.

Säännöt (CLAUDE.md 6a: väärä vaihtoehto mahdottomaksi):
  * Luvut vain FPL:n rajapinnasta tällä ajolla (lähde ensin), ei johdetuista tiedostoista.
  * Vain uusin lopullinen kierros, ja vain ennen seuraavan kierroksen deadlinea: vanha katsaus ei kuulu X:ään.
  * Kauden ero lasketaan FPL:n kokonaispisteistä (hitit vähennetty) FPL:n julkaisemien kierroskeskiarvojen
    summaa vastaan. Jos keskiarvo on ennen hittejä, ero on meille epäedullinen, ei edullinen.
  * Idempotentti: sama kierros ei saa toista issueta (otsikko haetaan olemassa olevista, myös suljetuista).
  * Kolme pohjaa vuorotellen (sama runko joka viikko on AI-tunnusmerkki). Julkaisutarkistaja blokkasi
    ensimmäiset pohjat 19.10; nämä ovat sen korjaamat versiot sellaisenaan. Muutos pohjaan = uusi tarkistus
    ennen mergeä.
  * Kapteenia ei mainita, jos hän ei pelannut tai on julkaisuportin estolistalla (scripts/publish_blocklist.json).

Ajo: python scripts/x_viikkoketju.py [--kuiva]   (GH_TOKEN ympäristössä; ilman sitä kuiva)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from scripts import publish_gate
from src.marketing.x_share import x_intent_url

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
    kapt_live = next((e["stats"] for e in live["elements"] if e["id"] == kapteeni["element"]), None)
    managereita = int(bootstrap["total_players"])
    return {
        "gw": gw, "pisteet": int(r["points"]), "hitti": int(r.get("event_transfers_cost") or 0),
        "keskiarvo": int(events[gw]["average_entry_score"]),
        "kokonais": int(r["total_points"]), "keskiarvo_summa": int(sum(keskiarvot)),
        "sijoitus": int(r["overall_rank"]), "managereita": managereita,
        # FPL:n oma % Rank -luku (sama kuin entry history -sivulla), ei omaa kaavaa (julkaisutarkistaja 19.10).
        "top_pct": int(r["overall_rank_percentage"]) if str(r.get("overall_rank_percentage") or "").isdigit() else None,
        "kapteeni": pelaajat.get(kapteeni["element"], "?"),
        "kapteeni_pisteet": kapt_live.get("total_points") if kapt_live else None,
        "kapteeni_minuutit": kapt_live.get("minutes", 0) if kapt_live else 0,
        "kerroin": int(kapteeni.get("multiplier") or 2), "chip": CHIPIT.get(picks.get("active_chip") or ""),
        "seuraava": gw + 1 if (gw + 1) in events else None,
    }


def _p(n: int) -> str:
    return f"{n} point" if abs(n) == 1 else f"{n} points"


def _linkki(gw: int) -> str:
    q = urllib.parse.urlencode({"utm_source": "x", "utm_medium": "partner", "utm_campaign": "model_entry",
                                "utm_content": f"gw{gw}"})
    return f"{SITE}/fpl/best-captain?{q}"


def _estetty(nimi: str) -> bool:
    """Sama estolista kuin julkaisuportilla ja korteilla (scripts/publish_blocklist.json), ei omaa listaa."""
    return bool(publish_gate.blocked_names(nimi, publish_gate.load_blocklist()))


def ketju(d: dict) -> list[str]:
    # Julkaisutarkistajan 19.10 korjaama versio sellaisenaan. Ei "model's own FPL team" (hylätty 29.9: chipit
    # ovat meidän), ei "every player" (xP kaikille on Premium), ei "locked" (rivi on muuttunut käsin).
    gw, ero = d["gw"], d["kokonais"] - d["keskiarvo_summa"]
    vko = d["pisteet"] - d["hitti"] - d["keskiarvo"]
    pist = _p(d["pisteet"]) + (f" (minus {d['hitti']} for transfers)" if d["hitti"] else "")
    ero_txt = f"{ero:,} more than" if ero > 0 else f"{-ero:,} fewer than" if ero < 0 else "the same as"
    top = d["top_pct"]
    taso = f"Top {top}% overall." if top is not None and top <= 50 else f"Overall rank {d['sijoitus']:,}."
    k, kp = d["kapteeni"], d["kapteeni_pisteet"]
    if kp is None or not d["kapteeni_minuutit"] or _estetty(k):
        kapt = ""
    elif d["kerroin"] == 3:
        kapt = f"Triple Captain on {k}, and he blanked." if kp <= 2 else f"Triple Captain on {k}: {kp * 3}."
    else:
        kapt = f"{k} blanked with the armband." if kp <= 2 else f"{k} with the armband: {kp * 2}."
    chip = {"Bench Boost": "We played the Bench Boost.", "Wildcard": "We played the Wildcard.",
            "Free Hit": "We played the Free Hit."}.get(d["chip"] or "", "")
    alku = " ".join(x for x in (kapt, chip) if x)
    tuomio = "Good week." if vko >= 4 else "Not our week." if vko <= -4 else "Average week, near enough."
    seur, linkki = d["seuraava"], _linkki(gw)
    pohja = gw % 3
    if pohja == 0:
        cta = f"\n\nThe model's GW{seur} captain pick is free on our site: {linkki}" if seur else ""
        viestit = [f"{tuomio} The model's squad got {pist} in GW{gw}, and FPL's average was {d['keskiarvo']}.",
                   f"{alku} The season's on {d['kokonais']:,}, {ero_txt} scoring the average every week. {taso}".strip(),
                   f"We play the model's squad in FPL as entry {ENTRY}, so the points and rank are public: {FPL_SIVU}{cta}"]
    elif pohja == 1:
        cta = f"\n\nWho the model would captain in GW{seur}, free: {linkki}" if seur else ""
        tulos = f"The model's squad finished GW{gw} on {pist}, with FPL's average at {d['keskiarvo']}."
        viestit = [f"{alku or tuomio} {tulos}",
                   f"{d['kokonais']:,} for the season. {taso} Scoring the FPL average every week would've got you "
                   f"{d['keskiarvo_summa']:,}. We play the squad in FPL, entry {ENTRY}: {FPL_SIVU}{cta}"]
    else:
        cta = f"\n\nGW{seur} captain pick from the same model, free: {linkki}" if seur else ""
        viikko = "Above the average" if vko >= 4 else "Below the average" if vko <= -4 else "Close to the average"
        kausi = "ahead of it" if ero > 0 else "behind it" if ero < 0 else "level with it"
        viestit = [f"{viikko} in GW{gw}, {kausi} over the season.",
                   f"The model's squad got {pist}, FPL's average was {d['keskiarvo']}. {alku}".strip(),
                   f"{d['kokonais']:,} after {gw} gameweeks, {ero_txt} scoring the average every week. "
                   f"The squad is FPL entry {ENTRY}, open to anyone: {FPL_SIVU}{cta}"]
    for v in viestit:
        if x_pituus(v) > X_MAX or "\u2014" in v or "\u2013" in v or "\u2019" in v:
            raise ValueError(f"viesti ei kelpaa X:ään ({x_pituus(v)} merkkiä): {v[:60]}")
        if publish_gate.blocked_names(v, publish_gate.load_blocklist()):
            raise ValueError(f"estolistan nimi viestissä: {v[:60]}")
    return viestit


def issue(d: dict, viestit: list[str]) -> dict:
    osat = [f"Kopioi X:ään ketjuna (@goaliqapp): ensimmäinen viesti ensin, loput vastauksina edelliseen. "
            f"Luvut FPL:n rajapinnasta {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC (GW{d['gw']} finished ja "
            f"data_checked). Postaa ennen GW{d['seuraava'] or '?'}-deadlinea tai sulje ohitettuna."]
    osat.append(f"[Avaa X valmiilla ensimmaisella viestilla]({x_intent_url(viestit[0])}) ja paina itse Post, "
                f"loput viestit lisaat vastauksina.")
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
