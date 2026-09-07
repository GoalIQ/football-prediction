# -*- coding: utf-8 -*-
"""UCL Fantasyn julkinen syote -> normalisoidut artefaktit.

Villen paatos 7.9.2026: "laajin mahdollinen, anna mennä vaan". Tama on
perusta - ilman sita ei ole mitaan mille rakentaa.

🔴 KAKSI ASIAA JOTKA MITTAUS PALJASTI, JA JOTKA MAARITTAVAT TAMAN RAKENTEEN

**(1) KAUSI-ID ON LOYDETTAVA, EI KOVAKOODATTAVA.**
Jonorivi (6.9) sanoi `players_70_en_1.json`, "70 = kausi 2026/27". Mitattu
7.9: se on **2024/25**. Kaikki 1 126 pelaajaa, ottelupaivat 17.-19.9.2024,
`mdId` vain 1, ja syotteen oma aikaleima kesakuulta 2025 - jaatynyt
tilannekuva kahden kauden takaa. Naapuri-id:t 68-79 palauttavat 403, joten
"se ainoa joka vastaa" nayttaa oikealta. Se ei ole.

Kuluva kausi on **90**: 1 162 pelaajaa, ottelupaivat 8.-10.9.2026, syotteen
aikaleima taman paivan iltapaivalta. Ero on kaksi kautta, ja vaara valinta
olisi nakynyt tuotteessa 2024/25:n hintoina ja omistusprosentteina.

Kovakoodattu id vanhenee joka kausi ja tekee sen HILJAA: vanha id vastaa
edelleen 200:lla. Siksi id etsitaan joka ajossa, ja valinta perustellaan
DEADLINEILLA - kausi jonka kierroksia on viela pelaamatta.

**(2) `totPts` JA `minsPlyd` OVAT VIIME KAUDELTA.**
Mitattu: `teamPlayed == 0` kaikilla 1 162 pelaajalla (tata kautta ei ole
pelattu), mutta `totPts` yltaa 121:een ja `minsPlyd` 1 560:een. Luvut ovat
siis 2025/26:n UCL-kaudelta. Jos pinta nayttaa ne MD1:n vieressa,
lukija lukee ne taman kauden luvuiksi.

Ne kannetaan siksi nimella `prev_season_points` / `prev_season_minutes`,
eika `points`-nimista kenttaa ole olemassa ennen kuin kierroksia on
pelattu. Vaara nimi on vaikeampi korjata kuin puuttuva kentta.

0 EUROA: julkinen syote, ei avaimia, ei krediitteja. Ajetaan eraajona
CI:sta, ei serve-ajan fan-outia (muisti:
fan-out-ryoppy-lyo-upstreamin-rajan-lapi).
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data"

BASE = "https://gaming.uefa.com/en/uclfantasy/services/feeds"
# Selain-UA blokataan, curlin oma UA lapaisee. Mitattu 6.9 CI-runnerilta ja
# 7.9 uudelleen seka runnerilta etta kehityskoneelta.
HEADERS = {
    "User-Agent": "curl/8.0",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://gaming.uefa.com/en/uclfantasy/create-team",
}

# Mista id:sta alaspain etsitaan. Uusi kausi saa suuremman numeron (70 =
# 2024/25, 80 = 2025/26, 90 = 2026/27), joten haku alkaa ylhaalta.
ID_MAX = 140
ID_MIN = 60
TIMEOUT = 40

# Positiokoodit syotteen `skill`-kentasta. Mitattu jakauma 7.9:
# 1=138, 2=385, 3=481, 4=158 -> GK/DEF/MID/FWD.
SKILL = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}

# `pStatus`-koodit. Tyhja = kaytettavissa. Mitattu 7.9: '' 991, NIS 122,
# I 31, D 10, S 8.
STATUS = {
    "": "available",
    "NIS": "not_in_squad",
    "I": "injured",
    "D": "doubtful",
    "S": "suspended",
}


def _hae(polku: str) -> dict | None:
    """JSON syotteesta, tai None jos se ei vastaa. Ei nosta poikkeusta:
    id-haku kokeilee tarkoituksella olemattomia id:ita."""
    req = urllib.request.Request(f"{BASE}/{polku}", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            if r.status != 200:
                return None
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            json.JSONDecodeError, OSError):
        return None


def _feed_aika(pelaajat_doc: dict) -> str | None:
    """Syotteen oma aikaleima UTC-ISOna, tai None.

    🔴 TAMA KORVAA RAKENNUSAJAN ARTEFAKTIN TUOREUSKENTTANA. `generated_at`
    oli `now()`, joten artefakti muuttui JOKA ajossa vaikka UEFA ei olisi
    paivittanyt mitaan: workflow'n "ei muutoksia" -pikapoistuma ei
    lauennut kertaakaan, ja jokainen 6 h ajo olisi tuottanut commitin,
    hub-deployn ja testiajon ilman yhtaan uutta lukua.

    Rakennusaika ei myoskaan ole tieto DATASTA. Lukijaa kiinnostaa milloin
    luvut ovat UEFAlta, ei milloin me ajoimme skriptin.

    Muoto syotteessa: `9/7/2026 3:02:01 PM`, jossa valilyonti ennen
    AM/PM:aa on U+202F (narrow no-break space). Normalisoidaan kaikki
    unicode-valilyonnit ennen jasennysta, jottei portti kaadu siihen etta
    UEFA vaihtaa merkin takaisin tavalliseen.
    """
    raw = ((pelaajat_doc.get("meta") or {}).get("timestamp", {})
           .get("utcTime"))
    if not raw:
        return None
    siisti = "".join(" " if unicodedata.category(c) == "Zs" else c
                     for c in str(raw)).strip()
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%y %I:%M:%S %p"):
        try:
            return (dt.datetime.strptime(siisti, fmt)
                    .replace(tzinfo=dt.timezone.utc).isoformat())
        except ValueError:
            continue
    return None


def _deadlinet(fixtures_doc: dict) -> list[dt.datetime]:
    """Kierrosten deadlinet UTC:na. Syotteen muoto: `09/08/26 06:45:00 PM`."""
    ulos = []
    for gd in (fixtures_doc.get("data") or {}).get("value") or []:
        raw = gd.get("deadline")
        if not raw:
            continue
        try:
            ulos.append(dt.datetime.strptime(raw, "%m/%d/%y %I:%M:%S %p")
                        .replace(tzinfo=dt.timezone.utc))
        except ValueError:
            continue
    return sorted(ulos)


def loyda_kausi(nyt: dt.datetime | None = None) -> tuple[int, dict] | None:
    """(kausi_id, fixtures_doc) sille kaudelle jolla on pelaamattomia
    kierroksia.

    Perustelu on DEADLINE, ei id:n suuruus: kausi jonka kaikki kierrokset
    ovat menneisyydessa on ohi, ja sen syote vastaa silti 200:lla. Juuri
    se teki jonorivin URL:sta kaksi kautta vanhan ilman etta mikaan huusi.
    """
    nyt = nyt or dt.datetime.now(dt.timezone.utc)
    for kausi in range(ID_MAX, ID_MIN - 1, -10):
        fx = _hae(f"fixtures/fixtures_{kausi}_en.json")
        if not fx:
            continue
        dls = _deadlinet(fx)
        if not dls:
            continue
        if dls[-1] > nyt:
            return kausi, fx
    return None


def normalisoi_pelaajat(doc: dict, kausi: int) -> list[dict]:
    ulos = []
    for p in (doc.get("data") or {}).get("value", {}).get("playerList") or []:
        pelattu = int(p.get("teamPlayed") or 0)
        rivi = {
            "id": str(p.get("id")),
            "name": p.get("pDName") or p.get("latinName"),
            "team": p.get("tName"),
            "team_code": p.get("cCode"),
            "team_id": str(p.get("tId")),
            "pos": SKILL.get(int(p.get("skill") or 0), "?"),
            "price": float(p.get("value") or 0),
            "owned_pct": float(p.get("selPer") or 0),
            "status": STATUS.get(str(p.get("pStatus") or ""), "unknown"),
            "matchdays_played": pelattu,
            # 🔴 NIMI KERTOO MISTA KAUDESTA. Ks. moduulin docstring: nama
            # ovat VIIME kauden lukuja niin kauan kuin `matchdays_played`
            # on 0, ja niiden nimeaminen `points`iksi olisi vaite tasta
            # kaudesta.
            "prev_season_points": int(p.get("totPts") or 0) if not pelattu else 0,
            "prev_season_minutes": int(p.get("minsPlyd") or 0) if not pelattu else 0,
        }
        if pelattu:
            rivi["points"] = int(p.get("totPts") or 0)
            rivi["minutes"] = int(p.get("minsPlyd") or 0)
        ulos.append(rivi)
    return ulos


def normalisoi_kierrokset(fx: dict) -> list[dict]:
    ulos = []
    for gd in (fx.get("data") or {}).get("value") or []:
        raw = gd.get("deadline")
        dl = None
        if raw:
            try:
                dl = (dt.datetime.strptime(raw, "%m/%d/%y %I:%M:%S %p")
                      .replace(tzinfo=dt.timezone.utc).isoformat())
            except ValueError:
                dl = None
        ulos.append({
            "md": int(gd.get("mdId") or 0),
            "deadline_utc": dl,
            "is_current": bool(gd.get("gdIsCurrent")),
            "is_locked": bool(gd.get("gdIsLocked")),
            "subs_allowed": gd.get("subsAllowed"),
        })
    return sorted(ulos, key=lambda x: x["md"])


def normalisoi_joukkueet(doc: dict) -> list[dict]:
    ulos = []
    for t in (doc.get("data") or {}).get("value") or []:
        ulos.append({
            "id": str(t.get("id")),
            "name": t.get("webName") or t.get("offName"),
            "short": t.get("shortName"),
            "pot": t.get("htPtName"),
            "eliminated": bool(t.get("isEliminated")),
        })
    return sorted(ulos, key=lambda x: x["name"] or "")


def build(nyt: dt.datetime | None = None) -> dict:
    nyt = nyt or dt.datetime.now(dt.timezone.utc)
    loytyi = loyda_kausi(nyt)
    if not loytyi:
        raise SystemExit(
            "ucl: yhtaan kautta ei loytynyt jolla olisi pelaamattomia "
            "kierroksia. Syote on voinut muuttaa muotoaan - ALA kovakoodaa "
            "id:ta, vaan korjaa haku.")
    kausi, fx = loytyi

    kierrokset = normalisoi_kierrokset(fx)
    seuraava = next((k for k in kierrokset
                     if k["deadline_utc"]
                     and dt.datetime.fromisoformat(k["deadline_utc"]) > nyt),
                    None)
    md = (seuraava or kierrokset[0])["md"] if kierrokset else 1

    pelaajat_doc = _hae(f"players/players_{kausi}_en_{md}.json")
    if not pelaajat_doc:
        raise SystemExit(f"ucl: pelaajasyote {kausi}/{md} ei vastannut")
    joukkueet_doc = _hae(f"teams/teams_{kausi}_en.json") or {}

    pelaajat = normalisoi_pelaajat(pelaajat_doc, kausi)
    if len(pelaajat) < 500:
        raise SystemExit(
            f"ucl: vain {len(pelaajat)} pelaajaa - syote on vajaa, ei "
            "kirjoiteta artefaktia vajaan datan paalle")

    return {
        "meta": {
            "source": "UEFA UCL Fantasy public feed (no key, no login)",
            "season_id": kausi,
            "matchday": md,
            # 🔴 EI RAKENNUSAIKAA. Ks. `_feed_aika`: `now()` teki
            # artefaktista erilaisen joka ajossa, jolloin workflow olisi
            # committanut ja deployannut 4 kertaa vuorokaudessa ilman
            # yhtaan muuttunutta lukua.
            "feed_updated_utc": _feed_aika(pelaajat_doc),
            "feed_timestamp_raw": ((pelaajat_doc.get("meta") or {})
                                   .get("timestamp", {}).get("utcTime")),
            # Sanotaan aaneen mita luvut EIVAT ole. Pinta lukee taman.
            "points_basis": (
                "prev_season_points and prev_season_minutes are last "
                "season's UCL totals, carried in the feed before any "
                "matchday of this season is played (teamPlayed = 0)"),
            "players": len(pelaajat),
            "teams": len(normalisoi_joukkueet(joukkueet_doc)),
        },
        "matchdays": kierrokset,
        "teams": normalisoi_joukkueet(joukkueet_doc),
        "players": pelaajat,
    }


def main() -> int:
    doc = build()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "ucl_fantasy.json"
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    m = doc["meta"]
    nxt = next((k for k in doc["matchdays"] if not k["is_locked"]), None)
    print(f"ucl_fantasy.json: kausi {m['season_id']}, MD{m['matchday']}, "
          f"{m['players']} pelaajaa, {m['teams']} joukkuetta")
    if nxt:
        print(f"  seuraava deadline: MD{nxt['md']} {nxt['deadline_utc']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
