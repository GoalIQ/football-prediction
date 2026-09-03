# -*- coding: utf-8 -*-
"""CHIP-EV-CHIPS-USED (3.9): chippien saatavuus bootstrapin ikkunoista +
entryn pelatuista chipeista. Negatiiviset kontrollit: ilman pelattuja chippeja
kaikki ikkunat tarjolla; ilman bootstrap-listaa yksi koko kauden ikkuna."""
from src.models.fpl_chips import (chip_state, chip_windows, gw_allowed,
                                  next_available_window, played_chips)

BOOT = {"chips": [
    {"name": "wildcard", "start_event": 2, "stop_event": 19},
    {"name": "wildcard", "start_event": 20, "stop_event": 38},
    {"name": "freehit", "start_event": 2, "stop_event": 19},
    {"name": "bboost", "start_event": 1, "stop_event": 19},
    {"name": "3xc", "start_event": 1, "stop_event": 19},
    {"name": "freehit", "start_event": 20, "stop_event": 38},
    {"name": "bboost", "start_event": 20, "stop_event": 38},
    {"name": "3xc", "start_event": 20, "stop_event": 38},
    {"name": "manager", "start_event": 1, "stop_event": 38},  # tuntematon -> ohi
]}
HIST = {"chips": [{"name": "wildcard", "event": 2, "time": "2026-08-28T17:17:50Z"}]}


def test_windows_come_from_bootstrap_two_per_chip_sorted():
    w = chip_windows(BOOT)
    assert w["wc"] == [(2, 19), (20, 38)]
    assert w["bb"] == [(1, 19), (20, 38)]
    assert set(w) == {"wc", "fh", "bb", "tc"}


def test_no_bootstrap_chips_falls_back_to_one_season_window():
    assert chip_windows({})["wc"] == [(1, 38)]


def test_played_wildcard_blocks_first_half_only():
    st = chip_state(BOOT, HIST, current_gw=3)
    assert st["wc"]["played_gws"] == [2]
    assert st["wc"]["windows"][0]["played_gw"] == 2
    assert st["wc"]["windows"][0]["available"] is False
    assert st["wc"]["windows"][1]["available"] is True
    assert st["wc"]["available_now"] is False
    assert not gw_allowed(st, "wc", 5) and gw_allowed(st, "wc", 25)
    assert next_available_window(st, "wc", 3)["start_gw"] == 20


def test_negative_control_no_played_chips_everything_available():
    st = chip_state(BOOT, {"chips": []}, current_gw=3)
    for key in ("wc", "fh", "bb", "tc"):
        assert all(r["available"] for r in st[key]["windows"]), key
        assert st[key]["available_now"] is True
        assert gw_allowed(st, key, 3) and gw_allowed(st, key, 30)


def test_past_window_is_not_available_even_if_unplayed():
    st = chip_state(BOOT, None, current_gw=25)
    assert st["bb"]["windows"][0]["available"] is False   # 1-19 takana
    assert st["bb"]["windows"][1]["available"] is True
    assert gw_allowed(st, "bb", 10) is False


def test_played_chips_parser_ignores_garbage():
    assert played_chips({"chips": [{"name": "bboost", "event": "x"},
                                   {"name": "3xc", "event": 7}]}) == {"tc": [7]}
    assert played_chips(None) == {}
