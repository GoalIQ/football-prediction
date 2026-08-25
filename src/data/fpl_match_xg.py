"""Ottelutason joukkue-xG FPL:n omasta API:sta (25.8.2026).

🔴 MIKSI TAMA ON OLEMASSA
Mallin xG-syote tuli Understatista, ja Understat lakkasi palvelemasta
palvelinhakuja. Mitattu 25.8 KONTROLLIN kanssa:

    understat.com/league/EPL/2026 -> HTTP 200, 18 689 B, ei datalohkoa
    understat.com/league/EPL/2025 -> HTTP 200, 18 689 B, ei datalohkoa

Identtiset. Kyse EI ole siita ettei uutta kautta olisi julkaistu, vaan siita
etta sivusto tarjoilee JS-kuoren kaikille kausille. Vanhat kaudet toimivat
vain koska ne ovat levylla valimuistissa (league_1_season_2022..2025).
Uusi kausi ei paase cacheen, joten 26/27:n otteluilla ei ole xG:ta lainkaan ja
DC-fitti sovittaa pelkkiin maaleihin. Se tapahtuu HILJAA: `home_xg` on vain
`NA`, eika mikaan kaadu.

🔴 TAMA EI OLE SAMA ASIA KUIN FBREF. FBrefin edistynyt data tyhjeni 8.8
(sarakeotsikot paikallaan, solut tyhjia). Molemmat ovat sama vikaluokka mutta
eri sivusto, ja meidan xG tuli Understatista - ei FBrefista.

RATKAISU: FPL:n oma element-summary kantaa `expected_goals`:n PER PELAAJA PER
OTTELU, ja se on Opta-lahtoista. Joukkueen ottelu-xG saadaan summaamalla sen
pelaajien luvut. Data on jo levylla: xP-builderi hakee samat summaryt joka
ajossa, joten tama ei lisaa yhtaan verkkokutsua.

Verifioitu GW1:lla (10/10 ottelua, 610 rivia):
    BRE 3-0 TOT  xG 3.91 - 0.57      BHA 4-0 AVL  xG 3.77 - 0.30
    NEW 2-2 LIV  xG 1.58 - 3.01      NFO 0-1 LEE  xG 0.65 - 0.47
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path

import config

SUMMARY_DIR = config.RAW_DATA_DIR / "fpl"

# 🔴 FPL:n ja football-data.co.uk:n joukkuenimet eroavat viidessa kohdassa.
# Kartta on EKSPLISIITTINEN ja `nimikartta_aukot()` kaataa ajon jos jokin nimi
# jaa kartoittamatta - muuten uuden kauden uudelleennimeaminen pudottaisi
# otteluita hiljaa, ja hiljainen pudotus nayttaa "ei xG:ta talle ottelulle".
FPL_TO_FD = {
    "Coventry City": "Coventry",
    "Hull City": "Hull",
    "Ipswich Town": "Ipswich",
    "Man Utd": "Man United",
    "Spurs": "Tottenham",
}


def _summary_dir(season_key: str) -> Path:
    return SUMMARY_DIR / f"summary_{season_key}"


def nimikartta_aukot(fpl_teams: list[dict], fd_names: set[str]) -> list[str]:
    """FPL-nimet jotka eivat osu football-datan nimiin edes kartan jalkeen."""
    aukot = []
    for t in fpl_teams:
        nimi = FPL_TO_FD.get(t["name"], t["name"])
        if nimi not in fd_names:
            aukot.append(f'{t["name"]!r} -> {nimi!r}')
    return sorted(aukot)


def team_xg_by_fixture(season_key: str) -> dict[int, dict[int, float]]:
    """{fixture_id: {fpl_team_id: xG}} levylla olevista element-summaryista.

    Puuttuva `expected_goals` ohitetaan rivikohtaisesti: se on eri asia kuin
    nolla. Pelaaja jolla ei ole lukua ei kasvata joukkueen summaa, muttei
    myoskaan vaaranna sita.
    """
    hakemisto = _summary_dir(season_key)
    if not hakemisto.exists():
        return {}
    import sys
    if str(config.PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(config.PROJECT_ROOT))
    from src.data import fpl_api

    boot = fpl_api.fetch_bootstrap()
    team_of = {e["id"]: e["team"] for e in boot["elements"]}

    agg: dict[int, dict[int, float]] = collections.defaultdict(
        lambda: collections.defaultdict(float))
    for p in hakemisto.glob("*.json"):
        m = re.search(r"element_(\d+)", p.name)
        if not m:
            continue
        pid = int(m.group(1))
        tid = team_of.get(pid)
        if tid is None:
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for h in (doc.get("history") or []):
            xg = h.get("expected_goals")
            fid = h.get("fixture")
            if xg is None or fid is None:
                continue
            try:
                agg[int(fid)][tid] += float(xg)
            except (TypeError, ValueError):
                continue
    return {k: dict(v) for k, v in agg.items()}


def match_xg_rows(season_key: str) -> list[dict]:
    """[{home_team, away_team, home_xg, away_xg}] football-datan nimilla.

    Palauttaa vain ottelut joilla on MOLEMPIEN joukkueiden xG. Toinen puoli
    yksin ei ole ottelun xG, ja puolikas rivi vaarantaisi fitin.
    """
    agg = team_xg_by_fixture(season_key)
    if not agg:
        return []
    import sys
    if str(config.PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(config.PROJECT_ROOT))
    from src.data import fpl_api

    boot = fpl_api.fetch_bootstrap()
    nimi = {t["id"]: FPL_TO_FD.get(t["name"], t["name"]) for t in boot["teams"]}
    out = []
    for f in fpl_api.fetch_fixtures():
        fid = f.get("id")
        per_team = agg.get(fid)
        if not per_team:
            continue
        h, a = f.get("team_h"), f.get("team_a")
        if h not in per_team or a not in per_team:
            continue
        out.append({
            "home_team": nimi.get(h), "away_team": nimi.get(a),
            "home_xg": round(per_team[h], 3),
            "away_xg": round(per_team[a], 3),
        })
    return out
