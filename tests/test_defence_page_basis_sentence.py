"""DEFENCE-SIVU-25-26-LAUSE (10.9.2026): /fpl/defence on viime kauden data.

Vanha lause "there is no Premier League shot data for them yet" nousijoista
oli epatosi heti kun uusi kausi alkoi (3 PL-ottelua pelattu 9.9). Sivu sanoo
nyt etta taulukko on viime kauden dataa eika taman kauden otteluita ole siina
kenellakaan. Testi ajaa oikean renderoijan synteettisella metalla molemmissa
vaiheissa (nousijat listalla / ei listalla).
"""
from __future__ import annotations

from datetime import datetime, timezone

from scripts.build_fpl_longtail import render_defence


def _defence(promoted):
    row = {"team": "Arsenal", "xg_pm": 0.8, "head_pm": 2.1, "central_pm": 3.0,
           "six_pm": 0.9, "wide_pm": 2.0, "edge_pm": 1.5, "long_pm": 1.0,
           "sp_xg_pm": 0.2, "shots_pm": 8.0, "matches": 38, "far_pm": 0.7,
           "hvc_pm": 0.4, "pens": 1, "box_share": 0.6}
    return {"meta": {"available": True, "season": "2025/26",
                     "promoted_no_data": promoted, "relegated_excluded": [],
                     "generated_at": "2026-08-08T21:21:32"},
            "teams": [row]}


def test_promoted_sentence_says_last_season_not_no_data_yet():
    html = render_defence(_defence(["Coventry", "Hull", "Ipswich"]),
                          datetime(2026, 9, 10, tzinfo=timezone.utc))
    assert html
    assert "no Premier League shot data for them yet" not in html
    assert "last season's Premier League shot data does not cover them" in html
    assert "This season's matches are not in this table for anyone yet" in html
    assert "2025/26 season, per match" in html


def test_no_promoted_no_sentence():
    html = render_defence(_defence([]), datetime(2026, 9, 10, tzinfo=timezone.utc))
    assert html and "came up from the Championship" not in html


def test_live_artefact_is_last_season_not_current():
    """"last season" on kovakoodattu lauseeseen ja kausi luetaan metasta. Jos
    DEFENCE_PATH joskus osoittaa kuluvan kauden tiedostoon, lause olisi
    epatosi. Portti: artefaktin kausi ei saa olla kuluva kausi."""
    import json
    import config
    from scripts.build_fpl_longtail import DEFENCE_PATH
    if not DEFENCE_PATH.exists():
        return
    meta = json.loads(DEFENCE_PATH.read_text(encoding="utf-8"))["meta"]
    cur = config.current_season()                      # esim. "2627"
    cur_label = f"20{cur[:2]}/{cur[2:]}"                # "2026/27"
    assert meta["season"] != cur_label, (
        f"defence-sivun data on kuluvaa kautta ({meta['season']}), mutta copy sanoo 'last season'")
    html = render_defence(json.loads(DEFENCE_PATH.read_text(encoding="utf-8")),
                          datetime(2026, 9, 10, tzinfo=timezone.utc))
    assert "17 clubs" in html or f"{meta.get('n_teams')} clubs" in html

