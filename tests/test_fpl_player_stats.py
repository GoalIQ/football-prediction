# -*- coding: utf-8 -*-
"""/api/fantasy/player-stats: FPL:n pisteet ja freeze-xP samalla rivilla (6.9).

Saanto 6a(3): invariantti mitataan JOKA VAIHEESSA synteettisilla fikstuureilla
(esikausi, kesken kauden, tuplakierros), ei vain nykyhetkessa levylla.
"""
from __future__ import annotations

import pytest

from src.models.fpl_player_stats import MASK_TEXT, aggregate, window_bounds

GW_COLS = ["gw", "pts", "g", "a", "tkl", "cbi", "rec", "dc", "cs", "gc",
           "saves", "bps", "bonus", "yc", "rc", "starts", "mins", "xg", "xa",
           "xgi", "xgc", "ict"]
STATS_COLS = ["id", "name", "team", "pos", "price", "own", "status", "mins",
              "starts", "g", "xg", "threat", "a", "xa", "xgi", "creativity",
              "tkl", "cbi", "rec", "dc", "cs", "gc", "xgc", "saves", "pts",
              "ppg", "bps", "bonus", "ict", "yc", "rc", "pen", "cor", "fk"]


def _gw_row(gw, pts, *, mins=90, xg=0.1, g=0, a=0, bonus=0):
    d = {c: 0 for c in GW_COLS}
    d.update(gw=gw, pts=pts, mins=mins, xg=xg, xa=0.2, xgi=round(xg + 0.2, 3),
             xgc=0.5, ict=3.3, g=g, a=a, bonus=bonus, starts=1 if mins else 0)
    return [d[c] for c in GW_COLS]


def _gw_doc(players: dict, max_gw: int, season="2026/27"):
    return {"meta": {"basis_season": season, "generated_at": "2026-09-05T17:09:21",
                     "cols": GW_COLS, "max_gw": max_gw},
            "players": {str(k): v for k, v in players.items()}}


def _stats_row(pid, name, pos, price=7.0, own=10.0):
    d = {c: 0 for c in STATS_COLS}
    d.update(id=pid, name=name, team="TST", pos=pos, price=price, own=own,
             status="a", ppg=1.0)
    return [d[c] for c in STATS_COLS]


def _stats_doc(rows, *, finished, season="2026/27"):
    return {"meta": {"basis_season": season, "generated_at": "2026-09-05T18:17:36",
                     "finished_events": finished, "cols": STATS_COLS},
            "players": rows}


def _live(players: dict[int, list[tuple[int, float]]], deadline_gw: int,
          season="2026/27"):
    """Elava projektio jo actionable-rajattuna (kuten load_xp_actionable)."""
    return {"meta": {"season": season, "deadline_gameweek": deadline_gw,
                     "trimmed_from": deadline_gw,
                     "generated_at": "2026-09-05T18:12:35+00:00"},
            "players": [
                {"id": pid, "web_name": f"L{pid}", "team_short": "TST",
                 "pos": "MID", "price": 5.5, "owned_pct": 1.0, "status": "a",
                 "news": "", "gameweeks": [{"gw": g, "xp": xp} for g, xp in gws]}
                for pid, gws in players.items()]}


# --- (a) esikausi -----------------------------------------------------------

def test_preseason_max_gw_zero_gives_empty_window_without_crash():
    stats = _stats_doc([_stats_row(1, "A", "MID")], finished=0)
    gw = _gw_doc({}, max_gw=0)
    for w in ("season", "last3", "last5", "last10"):
        out = aggregate(stats, gw, {}, None, window=w)
        assert out["meta"]["available"] is True
        assert out["meta"]["window"]["from"] == 1
        assert out["meta"]["window"]["to"] == 0
        assert out["meta"]["compared_gws"] == []
        assert out["players"] == []


def test_preseason_freeze_without_actuals_is_not_compared():
    """Freeze GW1 on kirjoitettu mutta yhtaan kierrosta ei ole pelattu."""
    stats = _stats_doc([], finished=0)
    gw = _gw_doc({}, max_gw=0)
    out = aggregate(stats, gw, {1: {1: 4.0}}, None)
    assert out["meta"]["frozen_gws"] == [1]
    assert out["meta"]["compared_gws"] == []


# --- (b) kesken kauden: freeze vain osalle kierroksista ---------------------

def _mid_season():
    stats = _stats_doc([_stats_row(1, "A", "MID"), _stats_row(2, "B", "DEF")],
                       finished=3)
    gw = _gw_doc({1: [_gw_row(1, 6), _gw_row(2, 5), _gw_row(3, 11)],
                  2: [_gw_row(1, 2), _gw_row(3, 1)]}, max_gw=3)
    frozen = {2: {1: 4.1, 2: 3.0}, 3: {1: 6.5, 2: 2.2}}
    return stats, gw, frozen


def test_compared_gws_require_both_freeze_and_actuals():
    stats, gw, frozen = _mid_season()
    out = aggregate(stats, gw, frozen, None)
    assert out["meta"]["frozen_gws"] == [2, 3]
    assert out["meta"]["compared_gws"] == [2, 3]
    a = next(p for p in out["players"] if p["id"] == 1)
    assert a["fpl"]["pts"] == 22 and a["fpl"]["games"] == 3
    assert a["goaliq"]["n_compared"] == 2
    assert a["goaliq"]["xp_frozen"] == pytest.approx(10.6)
    assert a["goaliq"]["pts_compared"] == 16
    assert a["goaliq"]["diff"] == pytest.approx(5.4)
    assert [g["gw"] for g in a["goaliq"]["gws"]] == [1, 2, 3]
    assert a["goaliq"]["gws"][0] == {"gw": 1, "pts": 6, "xp_frozen": None}


def test_pts_compared_uses_only_gws_where_player_has_row_and_freeze():
    """B oli freezessa GW2:ssa mutta ei pelannut: GW2 ei ole vertailussa
    kummassakaan summassa. Muuten erotus valehtelisi."""
    stats, gw, frozen = _mid_season()
    out = aggregate(stats, gw, frozen, None)
    b = next(p for p in out["players"] if p["id"] == 2)
    assert b["fpl"]["pts"] == 3
    assert b["goaliq"]["n_compared"] == 1
    assert b["goaliq"]["xp_frozen"] == pytest.approx(2.2)
    assert b["goaliq"]["pts_compared"] == 1
    assert b["goaliq"]["gws"][1] == {"gw": 2, "pts": None, "xp_frozen": 3.0}


def test_unfinished_round_is_not_compared_even_with_freeze_and_rows():
    """Kesken oleva kierros: max_gw=3 mutta finished_events=2 -> GW3 ei
    vertailuun, vaikka freeze ja osa toteumasta on olemassa."""
    stats, gw, frozen = _mid_season()
    stats["meta"]["finished_events"] = 2
    out = aggregate(stats, gw, frozen, None)
    assert out["meta"]["compared_gws"] == [2]
    a = next(p for p in out["players"] if p["id"] == 1)
    assert a["goaliq"]["n_compared"] == 1
    assert a["goaliq"]["pts_compared"] == 5
    # gws[] nayttaa silti freeze-luvun GW3:lle: lukija nakee sen, summa ei.
    assert a["goaliq"]["gws"][2]["xp_frozen"] == 6.5


# --- (c) tuplakierros -------------------------------------------------------

def test_double_gameweek_rows_sum_into_one_gw():
    stats = _stats_doc([_stats_row(1, "A", "MID")], finished=2)
    gw = _gw_doc({1: [_gw_row(1, 3), _gw_row(2, 4, xg=0.3), _gw_row(2, 9, xg=0.7)]},
                 max_gw=2)
    out = aggregate(stats, gw, {2: {1: 8.0}}, None)
    a = out["players"][0]
    assert a["fpl"]["pts"] == 16
    assert a["fpl"]["games"] == 2          # kaksi kierrosta, ei kolme
    assert a["fpl"]["mins"] == 270
    assert a["fpl"]["xg"] == pytest.approx(1.1)
    assert a["goaliq"]["gws"][1] == {"gw": 2, "pts": 13, "xp_frozen": 8.0}
    assert a["goaliq"]["pts_compared"] == 13


# --- (d) lastN rajautuu -----------------------------------------------------

def test_last_n_window_clamps_to_played_gameweeks():
    assert window_bounds("last5", 3) == {"kind": "last_n", "n": 5, "from": 1, "to": 3}
    assert window_bounds("last3", 10) == {"kind": "last_n", "n": 3, "from": 8, "to": 10}
    assert window_bounds("season", 10) == {"kind": "season", "n": None, "from": 1, "to": 10}
    stats = _stats_doc([_stats_row(1, "A", "MID")], finished=5)
    gw = _gw_doc({1: [_gw_row(g, g) for g in range(1, 6)]}, max_gw=5)
    out = aggregate(stats, gw, {}, None, window="last3")
    a = out["players"][0]
    assert out["meta"]["window"] == {"kind": "last_n", "n": 3, "from": 3, "to": 5}
    assert a["fpl"]["pts"] == 12
    assert [g["gw"] for g in a["goaliq"]["gws"]] == [3, 4, 5]
    out10 = aggregate(stats, gw, {}, None, window="last10")
    assert out10["meta"]["window"]["from"] == 1
    assert out10["players"][0]["fpl"]["pts"] == 15


# --- (e) premium-maski ------------------------------------------------------

def test_premium_mask_hides_only_forward_xp():
    stats, gw, frozen = _mid_season()
    live = _live({1: [(4, 4.62), (5, 5.0)], 2: [(4, 2.0)]}, deadline_gw=4)
    free = aggregate(stats, gw, frozen, live, premium=False)
    prem = aggregate(stats, gw, frozen, live, premium=True)
    assert free["meta"]["masked"] is True and free["meta"]["mask"] == MASK_TEXT
    assert prem["meta"]["masked"] is False and prem["meta"]["mask"] is None
    fa = next(p for p in free["players"] if p["id"] == 1)
    pa = next(p for p in prem["players"] if p["id"] == 1)
    assert fa["goaliq"]["next_gw_xp"] is None
    assert fa["goaliq"]["xp_horizon_total"] is None
    assert pa["goaliq"]["next_gw"] == 4
    assert pa["goaliq"]["next_gw_xp"] == pytest.approx(4.62)
    assert pa["goaliq"]["xp_horizon_total"] == pytest.approx(9.62)
    # Kaikki ilmainen sisalto identtista molemmille.
    assert fa["fpl"] == pa["fpl"]
    for k in ("xp_frozen", "pts_compared", "n_compared", "diff", "gws"):
        assert fa["goaliq"][k] == pa["goaliq"][k]


# --- (f) kausisekoitus ------------------------------------------------------

def test_season_mismatch_returns_available_false():
    stats = _stats_doc([_stats_row(1, "A", "MID")], finished=3, season="2025/26")
    gw = _gw_doc({1: [_gw_row(1, 6)]}, max_gw=1, season="2026/27")
    out = aggregate(stats, gw, {1: {1: 4.0}}, None)
    assert out["meta"]["available"] is False
    assert "2025/26" in out["meta"]["reason"] and "2026/27" in out["meta"]["reason"]
    assert out["players"] == []


def test_live_projection_from_other_season_is_dropped_not_mixed():
    stats, gw, frozen = _mid_season()
    live = _live({1: [(4, 4.62)]}, deadline_gw=4, season="2025/26")
    out = aggregate(stats, gw, frozen, live, premium=True)
    a = next(p for p in out["players"] if p["id"] == 1)
    assert a["goaliq"]["next_gw_xp"] is None
    assert a["goaliq"]["next_gw"] is None
    assert out["meta"]["available"] is True


# --- (g) negatiivinen kontrolli ---------------------------------------------

def test_player_without_freeze_has_null_diff_not_zero():
    stats = _stats_doc([_stats_row(1, "A", "MID"), _stats_row(2, "B", "FWD")],
                       finished=2)
    gw = _gw_doc({1: [_gw_row(1, 6), _gw_row(2, 6)],
                  2: [_gw_row(1, 6), _gw_row(2, 6)]}, max_gw=2)
    out = aggregate(stats, gw, {2: {1: 5.0}}, None)
    b = next(p for p in out["players"] if p["id"] == 2)
    assert b["goaliq"]["n_compared"] == 0
    assert b["goaliq"]["diff"] is None
    assert b["goaliq"]["xp_frozen"] is None
    assert b["goaliq"]["pts_compared"] is None
    assert all(g["xp_frozen"] is None for g in b["goaliq"]["gws"])


# --- jarjestys, suodatus, puuttuvat metakentat --------------------------------

def test_order_pts_desc_then_frozen_desc_then_id():
    stats = _stats_doc([_stats_row(i, f"P{i}", "MID") for i in (1, 2, 3)],
                       finished=1)
    gw = _gw_doc({1: [_gw_row(1, 5)], 2: [_gw_row(1, 5)], 3: [_gw_row(1, 9)]},
                 max_gw=1)
    out = aggregate(stats, gw, {1: {2: 6.0, 1: 3.0}}, None)
    assert [p["id"] for p in out["players"]] == [3, 2, 1]
    out2 = aggregate(stats, gw, {}, None)
    assert [p["id"] for p in out2["players"]] == [3, 1, 2]


def test_pos_filter_and_top_n():
    stats = _stats_doc([_stats_row(1, "A", "MID"), _stats_row(2, "B", "DEF"),
                        _stats_row(3, "C", "DEF")], finished=1)
    gw = _gw_doc({1: [_gw_row(1, 5)], 2: [_gw_row(1, 7)], 3: [_gw_row(1, 1)]},
                 max_gw=1)
    out = aggregate(stats, gw, {}, None, pos="DEF")
    assert [p["id"] for p in out["players"]] == [2, 3]
    assert out["meta"]["n_players"] == 2
    out = aggregate(stats, gw, {}, None, top_n=1)
    assert [p["id"] for p in out["players"]] == [2]


def test_player_missing_from_stats_keeps_rows_with_null_meta():
    stats = _stats_doc([_stats_row(1, "A", "MID")], finished=1)
    gw = _gw_doc({1: [_gw_row(1, 5)], 9: [_gw_row(1, 8)]}, max_gw=1)
    out = aggregate(stats, gw, {}, None)
    p9 = next(p for p in out["players"] if p["id"] == 9)
    assert p9["fpl"]["pts"] == 8
    assert p9["web_name"] is None and p9["price"] is None and p9["pos"] is None
    assert p9["code"] is None
    # Sijaintisuodatin pudottaa tuntemattoman sijainnin: ei arvausta.
    assert 9 not in [p["id"] for p in aggregate(stats, gw, {}, None, pos="MID")["players"]]


def test_player_in_stats_without_any_gw_rows_is_excluded():
    stats = _stats_doc([_stats_row(1, "A", "MID"), _stats_row(2, "B", "MID")],
                       finished=1)
    gw = _gw_doc({1: [_gw_row(1, 5)]}, max_gw=1)
    out = aggregate(stats, gw, {}, None)
    assert [p["id"] for p in out["players"]] == [1]


def test_generated_at_is_latest_of_sources():
    stats, gw, frozen = _mid_season()
    out = aggregate(stats, gw, frozen, None)
    assert out["meta"]["generated_at"] == "2026-09-05T18:17:36"
    live = _live({}, deadline_gw=4)
    live["meta"]["generated_at"] = "2026-09-05T19:00:00+00:00"
    out = aggregate(stats, gw, frozen, live)
    assert out["meta"]["generated_at"] == "2026-09-05T19:00:00+00:00"


# --- API ---------------------------------------------------------------------

def test_api_player_stats_responds_with_disk_files(client):
    from src.models.fpl_player_stats import STATS_PATH
    from src.models.fpl_actuals import PLAYER_GW_PATH
    if not (STATS_PATH.exists() and PLAYER_GW_PATH.exists()):
        pytest.skip("levyn lahdetiedostot puuttuvat")
    r = client.get("/api/fantasy/player-stats?window=season&top_n=3")
    assert r.status_code == 200, r.text
    body = r.json()
    assert r.headers.get("cache-control") == "no-store"
    assert body["meta"]["source"].startswith("FPL official API")
    assert "masked" in body["meta"] and "compared_gws" in body["meta"]
    if body["meta"]["available"]:
        assert len(body["players"]) <= 3
        for p in body["players"]:
            assert set(p) >= {"id", "web_name", "pos", "fpl", "goaliq"}
            assert set(p["goaliq"]) >= {"xp_frozen", "pts_compared", "n_compared",
                                       "diff", "gws", "next_gw", "next_gw_xp",
                                       "xp_horizon_total"}


def test_api_player_stats_rejects_unknown_window(client):
    assert client.get("/api/fantasy/player-stats?window=bogus").status_code == 422
    assert client.get("/api/fantasy/player-stats?pos=XX").status_code == 422
