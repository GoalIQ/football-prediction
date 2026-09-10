"""openfootball/champions-league txt-parseri (UCL-KATTAVUUS-ILMAISELLA-DATALLA).

Synteettinen syote kattaa: vuosi paivamaararivilla ja ilman, kellonajalla ja
ilman, jatkoaika+rangaistuspotkut (90 min sulkujen ensimmainen luku),
maakoodit pois nimista, otsikko- ja kommenttirivit ohi.
"""
from __future__ import annotations

from src.data import openfootball_txt as t

SAMPLE = """= UEFA Europa League 2024/25

# Date       Wed Sep 25 2024 - Wed May 21 2025 (238d)
# Teams      36

▪ League phase
  Wed Sep 25 2024
    18:45  AZ Alkmaar (NED)        v IF Elfsborg (SWE)        3-2 (1-1)
           FK Bodø/Glimt (NOR)     v FC Porto (POR)           3-2 (2-1)
  Thu Jan 23
    21:00  AS Roma (ITA)           v Eintracht Frankfurt (GER)  2-0 (1-0)

▪ Round of 16
  Thu Mar 13
           Rangers FC (SCO)        v Fenerbahçe (TUR)         3-2 pen. 0-2 a.e.t. (0-2, 0-1)
           Lazio Roma (ITA)        v Viktoria Plzeň (CZE)     1-1 (0-0)
"""


def test_parse_rows_dates_and_names():
    d = t.parse_txt(SAMPLE, "INT-Europa League", "2425")
    assert len(d) == 5
    assert list(d.columns) == t.COLUMNS
    assert d.iloc[0].home_team == "AZ Alkmaar" and d.iloc[0].away_team == "IF Elfsborg"
    assert str(d.iloc[0].date.date()) == "2024-09-25"
    assert str(d.iloc[1].date.date()) == "2024-09-25"          # sama paiva, ei kellonaikaa
    assert str(d.iloc[2].date.date()) == "2025-01-23"          # vuosi kaudesta: tammikuu -> 2025
    assert (d.iloc[0].home_score, d.iloc[0].away_score) == (3, 2)
    assert "(NOR)" not in d.iloc[1].home_team and d.iloc[1].home_team == "FK Bodø/Glimt"
    assert set(d.league) == {"INT-Europa League"} and set(d.season) == {"2425"}


def test_extra_time_uses_the_90_minute_score():
    d = t.parse_txt(SAMPLE, "INT-Europa League", "2425")
    r = d[d.home_team == "Rangers FC"].iloc[0]
    assert (r.home_score, r.away_score) == (0, 2), "90 min, ei 3-2 pen."
    l = d[d.home_team == "Lazio Roma"].iloc[0]
    assert (l.home_score, l.away_score) == (1, 1)


def test_year_boundary_rule():
    assert t._year_for(7, "2425") == 2024 and t._year_for(12, "2425") == 2024
    assert t._year_for(1, "2425") == 2025 and t._year_for(6, "2425") == 2025


def test_empty_and_unknown_league():
    assert t.parse_txt("= nothing\n# only header\n", "INT-Europa League", "2425").empty
    assert t.lataa("XX-Unknown", ["2425"]).empty


def test_negative_control_unscored_fixture_is_skipped():
    txt = "  Thu Oct 3 2024\n    18:45  A (ENG)  v B (ESP)   -\n           C (ENG)  v D (ESP)   2-1 (1-0)\n"
    d = t.parse_txt(txt, "INT-Europa League", "2425")
    assert len(d) == 1 and d.iloc[0].home_team == "C"
