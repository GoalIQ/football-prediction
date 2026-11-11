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


# ---------------------------------------------------------------------------
# KOKO OTTELURIVI FPL:n datasta (11.11.2026, Understat-katko 1.11-)
# ---------------------------------------------------------------------------
# 🔴 MIKSI: understat.com palauttaa huoltosivun 1.11 ~22 UTC alkaen kaikkiin
# osoitteisiin, myos getLeagueData-API:in, eika paluupaivaa ole. Julkinen
# PL-malli kieltaytyi oikein football-data.co.uk:n riveista (22.10:n
# nousijavika), joten xP ja Phase 0 jaivat 1.11:n versioon ja GW11:n
# projektiota ei syntynyt lainkaan.
#
# Tama rakentaa KOKO ottelurivin (pvm, joukkueet, maalit, xG) FPL:n
# element-summaryista, joten fitin ikkuna voidaan lukea YHDESTA xG-lahteesta:
# kokonaan Understat tai kokonaan FPL (Opta). Ei sekoitusta (src/data/loader.
# lataa_pl_fit_data).
#
# 🔴 KOTIPUOLI LUETAAN RIVIN `was_home`-KENTASTA, ei pelaajan nykyisesta
# joukkueesta. `team_xg_by_fixture` yllä summaa nykyisen bootstrapin
# joukkueen mukaan: kesken kauden siirtynyt pelaaja kirjautuu silloin uuden
# seuransa otteluun, ja edellisen kauden arkistoon se on kokonaan vaara
# (kauden 26/27 joukkuejako, 26/27:n fixture-id:t). `opponent_team` +
# `was_home` kertovat ottelun joukkueet kummankin puolen riveista.
LAHDE = "FPL-Opta"
# Puolen pelaajaminuutit: 11 x 90 = 990. Alle 900 = rivi puuttuu (esim.
# hakematon element-summary) tai kaksi varhaista punaista; ottelu jatetaan
# pois mieluummin kuin vaarin pienella xG:lla.
MIN_SIDE_MINUTES = 900
# Odotetuista pelatuista otteluista saa puuttua tama osuus (vahintaan 1).
MAX_PUUTTUVA_OSUUS = 0.02


def aggregate_matches(docs, team_names: dict[int, str]) -> tuple[list[dict], list[dict]]:
    """Element-summaryt -> (ottelurivit, hylatyt). Puhdas funktio (testit).

    docs: iteroitava element-summary-dokumenteista ({"history": [...]}).
    team_names: {kauden fpl_team_id: mallinimi}.
    """
    fx: dict = collections.defaultdict(lambda: {
        "xg": [0.0, 0.0], "min": [0, 0], "opp": [set(), set()],
        "sc": collections.Counter(), "ko": None})
    for doc in docs:
        for h in (doc or {}).get("history") or []:
            if h.get("team_h_score") is None or h.get("team_a_score") is None:
                continue  # ottelu ei ole pelattu
            fid = h.get("fixture")
            if fid is None or h.get("opponent_team") is None:
                continue
            side = 0 if h.get("was_home") else 1
            f = fx[int(fid)]
            try:
                f["xg"][side] += float(h.get("expected_goals") or 0.0)
            except (TypeError, ValueError):
                pass
            f["min"][side] += int(h.get("minutes") or 0)
            f["opp"][side].add(int(h["opponent_team"]))
            f["sc"][(int(h["team_h_score"]), int(h["team_a_score"]))] += 1
            f["ko"] = f["ko"] or h.get("kickoff_time")
    rows, dropped = [], []
    for fid, f in sorted(fx.items()):
        syy = None
        if len(f["opp"][0]) != 1 or len(f["opp"][1]) != 1:
            syy = "puolen vastustaja ei yksiselitteinen"
        elif min(f["min"]) < MIN_SIDE_MINUTES:
            syy = f"pelaajaminuutteja {f['min']} < {MIN_SIDE_MINUTES}"
        elif len(f["sc"]) != 1:
            syy = f"tulos ristiriitainen {dict(f['sc'])}"
        if syy is None:
            (away_id,), (home_id,) = f["opp"][0], f["opp"][1]
            home, away = team_names.get(home_id), team_names.get(away_id)
            if home is None or away is None or home == away:
                syy = f"joukkue-id ei kauden bootstrapissa ({home_id}, {away_id})"
        if syy is not None:
            dropped.append({"fixture": fid, "syy": syy})
            continue
        (hs, as_), = f["sc"].keys()
        rows.append({"date": (f["ko"] or "")[:10], "home_team": home, "away_team": away,
                     "home_score": hs, "away_score": as_,
                     "home_xg": round(f["xg"][0], 3), "away_xg": round(f["xg"][1], 3)})
    return rows, dropped


def _season_bootstrap(season_key: str) -> tuple[dict | None, bool]:
    """(bootstrap, onko_kuluva_kausi). Paattynyt kausi luetaan arkistosta."""
    import sys
    if str(config.PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(config.PROJECT_ROOT))
    from src.data import fpl_api

    live = fpl_api.fetch_bootstrap()
    if fpl_api.season_key_from_bootstrap(live) == season_key:
        return live, True
    p = SUMMARY_DIR / f"bootstrap_static_{season_key}.archive.json"
    if not p.exists():
        return None, False
    return json.loads(p.read_text(encoding="utf-8")), False


def season_match_frame(season_key: str):
    """Kauden pelatut PL-ottelut FPL:n datasta mallinimin, lahde = "FPL-Opta".

    Kuluva kausi: element-summaryt haetaan tuoreina (kerran prosessissa,
    fpl_api.fetch_all_summaries). Paattynyt kausi: levyn arkisto
    (data/fpl_2526_archive.tar.gz puretaan CI:ssa). Tyhja DataFrame =
    lahdetta ei ole; syy on `attrs["virhe"]`:ssa. Kutsuja kieltaytyy.
    """
    import pandas as pd
    import sys
    if str(config.PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(config.PROJECT_ROOT))
    from src.data import fpl_api
    from src.models.fpl_team_names import map_name

    cols = ["date", "home_team", "away_team", "home_score", "away_score",
            "league", "season", "home_xg", "away_xg", "lahde"]
    tyhja = pd.DataFrame(columns=cols)
    boot, live = _season_bootstrap(season_key)
    if boot is None:
        tyhja.attrs["virhe"] = f"kauden {season_key} bootstrap-arkistoa ei ole levylla"
        return tyhja
    if live:
        fpl_api.fetch_all_summaries(boot, force=not fpl_api.haettu_tuoreena(season_key))
    hakemisto = _summary_dir(season_key)
    docs = []
    for p in sorted(hakemisto.glob("element_*.json")) if hakemisto.exists() else []:
        try:
            docs.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    names = {int(t["id"]): map_name(t["name"]) for t in boot.get("teams") or []}
    rows, dropped = aggregate_matches(docs, names)
    if live:
        odotettu = sum(1 for f in fpl_api.fetch_fixtures(force=True)
                       if f.get("finished") or f.get("finished_provisional"))
    else:
        n = len(names)
        odotettu = n * (n - 1)
    puuttuu = max(0, odotettu - len(rows))
    sallittu = max(1, int(odotettu * MAX_PUUTTUVA_OSUUS))
    if not rows or puuttuu > sallittu:
        tyhja.attrs["virhe"] = (f"kausi {season_key}: {len(rows)}/{odotettu} pelattua ottelua "
                                f"FPL:n datasta (sallittu vaje {sallittu}); hylatty {dropped[:3]}")
        return tyhja
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["league"] = "ENG-Premier League"
    df["season"] = season_key
    df["lahde"] = LAHDE
    df = df[cols].sort_values("date").reset_index(drop=True)
    df.attrs["puuttuu"] = puuttuu
    df.attrs["hylatty"] = dropped
    return df
