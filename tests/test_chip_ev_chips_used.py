# -*- coding: utf-8 -*-
"""CHIP-EV-CHIPS-USED (3.9): `best` ei saa osoittaa ikkunaan jolla chippia
ei voi pelata (pelattu talla puolikkaalla tai puolikas takana).
Negatiivinen kontrolli: ilman pelattuja chippeja valinta on entinen."""
from api import fantasy_edge as fe
from src.models.fpl_chips import chip_state

BOOT = {"chips": [
    {"name": "wildcard", "start_event": 2, "stop_event": 19},
    {"name": "wildcard", "start_event": 20, "stop_event": 38},
    {"name": "freehit", "start_event": 2, "stop_event": 19},
    {"name": "freehit", "start_event": 20, "stop_event": 38},
    {"name": "bboost", "start_event": 1, "stop_event": 19},
    {"name": "bboost", "start_event": 20, "stop_event": 38},
    {"name": "3xc", "start_event": 1, "stop_event": 19},
    {"name": "3xc", "start_event": 20, "stop_event": 38},
]}


def _win(gw, wc, bb, basis="player_xp"):
    return {"gw": gw, "wc_ev": wc, "wc_window_gws": 3 if wc is not None else None,
            "bb_ev": bb, "tc_ev": 1.0, "fh_ev": 1.0, "basis": basis}


WINDOWS = [_win(3, 9.0, 4.0), _win(4, 7.0, 6.0), _win(5, 5.0, 2.0),
           _win(22, None, 8.0, basis="team_approx_cs_fdr"),
           _win(30, None, 9.5, basis="team_approx_cs_fdr")]


def test_played_wildcard_removes_it_from_best_this_half():
    st = chip_state(BOOT, {"chips": [{"name": "wildcard", "event": 2}]}, 3)
    best, est = fe._pick_best(WINDOWS, st)
    assert "wc" not in best, best          # ei mitattua wc-ikkunaa 2. puolikkaalla
    assert best["bb"]["gw"] == 4           # muut ennallaan
    assert est["bb"]["gw"] == 30


def test_negative_control_without_played_chips_best_is_unchanged():
    st = chip_state(BOOT, {"chips": []}, 3)
    best, est = fe._pick_best(WINDOWS, st)
    assert best["wc"] == {"gw": 3, "ev": 9.0, "basis": "player_xp", "window_gws": 3}
    assert best["bb"]["gw"] == 4 and est["bb"]["gw"] == 30


def test_bench_boost_played_first_half_moves_best_estimate_to_second_half_only():
    st = chip_state(BOOT, {"chips": [{"name": "bboost", "event": 2}]}, 3)
    best, est = fe._pick_best(WINDOWS, st)
    assert "bb" not in best
    assert est["bb"]["gw"] == 30


def test_entry_history_fail_open(monkeypatch):
    def boom(path):
        raise RuntimeError("upstream")
    monkeypatch.setattr(fe, "_fetch_fpl", boom)
    assert fe._entry_history(116920) is None
    assert fe._entry_history(None) is None


def test_chip_notes_name_played_chips_and_halves():
    st = chip_state(BOOT, {"chips": [{"name": "wildcard", "event": 2}]}, 3)
    notes = fe._chip_notes(st, True, 116920)
    assert any("twice this season" in n and "GW19" in n and "GW20" in n for n in notes)
    assert any("Wildcard in GW2" in n for n in notes)
    assert not any("\u2014" in n for n in notes)
    # ilman historiaa: rehellinen varaus, ei pelattu-listaa
    n2 = fe._chip_notes(chip_state(BOOT, None, 3), False, 116920)
    assert any("could not be read" in n for n in n2)
