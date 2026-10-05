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


def test_live_artefact_copy_matches_its_season():
    """5.10: lukija (src/models/fpl_defence.load_defence) valitsee kuluvan
    kauden kun jokaisella seuralla on MIN_CURRENT_GAMES ottelua. Copy seuraa
    artefaktia: kuluva kausi -> "season so far" eika "last season";
    edellinen kausi -> "last season". Aiempi portti vaati etta data ON viime
    kauden, koska lause oli kovakoodattu."""
    import config
    from src.models.fpl_defence import is_season_so_far, load_defence
    doc = load_defence()
    if not doc:
        return
    meta = doc["meta"]
    cur = config.current_season()
    cur_label = f"20{cur[:2]}/{cur[2:]}"
    html = render_defence(doc, datetime(2026, 10, 5, tzinfo=timezone.utc))
    if meta["season"] == cur_label:
        assert is_season_so_far(doc) or meta.get("complete") is True
        assert f"{cur_label} season so far, per match" in html
        assert "played in the Premier League last season" not in html
    else:
        assert "played in the Premier League last season" in html


def _cur_doc(matches, promoted=()):
    row = {"team": "Arsenal", "xg_pm": 1.1, "head_pm": 0.6, "central_pm": 1.2,
           "six_pm": 0.4, "wide_pm": 1.0, "edge_pm": 1.5, "sp_xg_pm": 0.2,
           "shots_pm": 8.0, "matches": matches, "far_pm": 1.1, "hvc_pm": 0.4,
           "pens": 0, "box_share": 46.0}
    return {"meta": {"available": True, "season": "2026/27", "complete": False,
                     "promoted_no_data": list(promoted), "relegated_excluded": [],
                     "generated_at": "2026-10-05T16:00:00+00:00"},
            "teams": [row]}


def test_reader_phases(tmp_path):
    """Saanto 6a(3): sama lukija kauden eri vaiheissa."""
    import json
    from src.models.fpl_defence import load_defence
    prev = _defence([])
    (tmp_path / "understat_team_defence_2526.json").write_text(json.dumps(prev))
    # esikausi: kuluvan kauden tiedostoa ei ole -> edellinen kausi
    assert load_defence("2627", tmp_path)["meta"]["season"] == "2025/26"
    cur = tmp_path / "understat_team_defence_2627.json"
    # kaksi ottelua: alle MIN_CURRENT_GAMES -> edellinen kausi
    cur.write_text(json.dumps(_cur_doc(2)))
    assert load_defence("2627", tmp_path)["meta"]["season"] == "2025/26"
    # nousija ilman dataa -> edellinen kausi (taulukosta puuttuisi seura)
    cur.write_text(json.dumps(_cur_doc(5, ["Hull"])))
    assert load_defence("2627", tmp_path)["meta"]["season"] == "2025/26"
    # kesken kauden, viisi ottelua -> kuluva kausi, copy "so far"
    cur.write_text(json.dumps(_cur_doc(5)))
    doc = load_defence("2627", tmp_path)
    assert doc["meta"]["season"] == "2026/27"
    html = render_defence(doc, datetime(2026, 10, 5, tzinfo=timezone.utc))
    assert "2026/27 season so far, per match" in html
    assert "Every Premier League club, 5 matches each." in html
    assert "last season" not in html
    # rikkinainen kuluvan kauden tiedosto ei tyhjenna sivua
    cur.write_text("{")
    assert load_defence("2627", tmp_path)["meta"]["season"] == "2025/26"
