# -*- coding: utf-8 -*-
"""fpl_cs_fdr:n next6-ikkuna seuraa aikaa (30.8.2026, NEXT6-PINTA).

Vika: `team_aggregates` laski min_gw:n KOKO kauden 380 fixturesta, joten se
oli aina 1 ja `teams_next6` oli aina GW1-GW6. Kentan nimi lupasi "next 6",
sisalto oli kauden alku, ikuisesti. Mitattu 30.8.2026: GW1 pelattu, GW2
kesken, kentta yha GW1-GW6.

Sama vikaluokka on src/models/fpl_gameweek.py:n docstringissa NELJASTI; tama
oli viides. Portti tassa on aikasidonnainen, joten se kaatuu jos horisontti
palaa kiinnittymaan kauden alkuun.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GW_MS = 7 * 24 * 3600 * 1000
SEASON_START = 1_755_000_000_000  # mielivaltainen mutta kiintea alku


def _rows(n_gw=38):
    """Yksi ottelu per kierros, kickoff viikon valein."""
    return [{"gameweek": g, "kickoff_ms": SEASON_START + (g - 1) * GW_MS,
             "home": "A", "away": "B"} for g in range(1, n_gw + 1)]


def test_window_moves_forward_once_early_gameweeks_are_played():
    from scripts.build_fpl_cs_fdr import aggregate_window
    rows = _rows()
    # "nyt" = GW2:n kickoffin jalkeen, GW3 viela pelaamatta
    now = SEASON_START + 1 * GW_MS + 3600_000
    assert aggregate_window(rows, 6, now) == (3, 8)


def test_negative_control_before_the_season_window_starts_at_gw1():
    """Kontrolli: ennen kauden alkua GW1-GW6 on OIKEA vastaus.

    Ilman tata testi yllä lapaisisi myos toteutuksella joka vain lisaa
    vakion kierrosnumeroon.
    """
    from scripts.build_fpl_cs_fdr import aggregate_window
    rows = _rows()
    now = SEASON_START - 24 * 3600 * 1000
    assert aggregate_window(rows, 6, now) == (1, 6)


def test_regression_window_is_not_pinned_to_the_first_fixture():
    """Se konkreettinen vika: koko kauden fixturelista ei saa naulata GW1:een."""
    from scripts.build_fpl_cs_fdr import aggregate_window
    rows = _rows()
    now = SEASON_START + 20 * GW_MS
    win = aggregate_window(rows, 6, now)
    assert win is not None and win[0] > 1, win


def test_end_of_season_falls_back_instead_of_returning_nothing():
    from scripts.build_fpl_cs_fdr import aggregate_window
    rows = _rows()
    now = SEASON_START + 100 * GW_MS  # kaikki pelattu
    assert aggregate_window(rows, 6, now) == (1, 6)


def test_aggregate_uses_the_same_window_as_the_label():
    """Aggregaatti ja meta-leima on laskettava samasta ikkunasta.

    Muuten leima kertoo eri asian kuin luvut (muisti: varoitus-kaukana-luvusta).
    """
    from scripts.build_fpl_cs_fdr import aggregate_window, team_aggregates
    rows = []
    for g in range(1, 13):
        rows.append({"gameweek": g, "kickoff_ms": SEASON_START + (g - 1) * GW_MS,
                     "home": "A", "away": "B",
                     "cs_home_pct": 30.0, "cs_away_pct": 20.0,
                     "fdr_home": 2, "fdr_away": 4})
    now = SEASON_START + 1 * GW_MS + 3600_000
    win = aggregate_window(rows, 6, now)
    agg = team_aggregates(rows, 6, now)
    assert win == (3, 8)
    # GW3-GW8 = 6 ottelua joukkuetta kohti
    assert agg["A"]["next6_fixtures"] == 6, agg["A"]
    assert agg["B"]["next6_fixtures"] == 6, agg["B"]


def test_no_rows_returns_empty():
    from scripts.build_fpl_cs_fdr import aggregate_window, team_aggregates
    assert aggregate_window([], 6, SEASON_START) is None
    assert team_aggregates([], 6, SEASON_START) == {}
