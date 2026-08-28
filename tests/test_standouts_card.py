# -*- coding: utf-8 -*-
"""STANDOUTS-CARD (27.8): valinnat ovat puhtaita funktioita artefaktin
xp_dist-kentista. Portti: (1) penkkilaista ei nosteta, (2) epavarma pelaaja ei
ole "safest", (3) gamble vaatii aidon blank-riskin, (4) kortti ei tarvitse
per-pelaaja-xP:ta muuhun kuin kapteenin jarjestykseen."""
from __future__ import annotations

from scripts.render_standouts_card import pick_standouts, build_html


def _p(name, xp, p_start, haul, blank, p90, status="a", pos="MID"):
    return {"web_name": name, "pos": pos, "team_short": "TST", "price": 7.5,
            "status": status, "p_start": p_start, "xp_per_gw": xp * 0.5,
            "gameweeks": [{"gw": 2, "xp": xp}],
            "xp_dist": {"gw": 2, "n": 2000, "mean": xp, "p_haul": haul,
                        "p_blank": blank, "p10": 1, "median": 4, "p90": p90,
                        "haul_pts": 10, "blank_pts": 2}}


def test_picks_follow_definitions():
    ps = [
        _p("Cap", 6.0, 0.95, 0.30, 0.30, 13),
        _p("Ceil", 5.0, 0.90, 0.28, 0.40, 15),
        _p("Safe", 4.5, 0.92, 0.10, 0.12, 9),
        _p("Gamb", 3.9, 0.80, 0.29, 0.45, 12),
        _p("Bench", 7.0, 0.20, 0.50, 0.10, 20),      # p_start < 0.6 -> ei kortille
        _p("Inj", 6.5, 0.95, 0.40, 0.20, 14, status="i"),
    ]
    s = pick_standouts(ps)
    assert s["captain"]["web_name"] == "Cap"
    assert s["ceiling"]["web_name"] == "Ceil"
    assert s["safest"]["web_name"] == "Safe"
    assert s["gamble"]["web_name"] == "Gamb"


def test_negative_control_bench_player_never_captain():
    ps = [_p("Bench", 9.0, 0.5, 0.6, 0.1, 20), _p("Starter", 4.0, 0.9, 0.2, 0.3, 10)]
    assert pick_standouts(ps)["captain"]["web_name"] == "Starter"


def test_safest_requires_real_projection_and_gamble_requires_blank_risk():
    ps = [_p("Star", 6.0, 0.95, 0.3, 0.3, 11), _p("Mid", 4.5, 0.9, 0.25, 0.3, 12),
          _p("Low", 2.0, 0.9, 0.02, 0.05, 5), _p("Solid", 5.0, 0.9, 0.2, 0.2, 10)]
    s = pick_standouts(ps)
    assert s["captain"]["web_name"] == "Star" and s["ceiling"]["web_name"] == "Mid"
    assert s["safest"]["web_name"] == "Solid"   # Low: xp < 4 -> ei "safest"
    assert s["gamble"] is None                   # jaljella vain Low, ei blankkaa >= 35 %


def test_four_distinct_names():
    ps = [_p("Star", 7.0, 0.95, 0.40, 0.40, 16), _p("B", 5.0, 0.9, 0.2, 0.2, 11),
          _p("C", 4.5, 0.9, 0.15, 0.36, 10), _p("D", 4.2, 0.9, 0.1, 0.5, 9)]
    s = pick_standouts(ps)
    names = [s[k]["web_name"] for k in ("captain", "ceiling", "safest", "gamble") if s[k]]
    assert len(names) == len(set(names)) == 4


def test_thiaw_never_on_card():
    ps = [_p("Thiaw", 6.0, 0.95, 0.4, 0.1, 14), _p("M.Thiaw", 6.0, 0.95, 0.4, 0.1, 14),
          _p("Other", 4.0, 0.9, 0.2, 0.3, 10)]
    s = pick_standouts(ps)
    assert all((s[k] is None or "Thiaw" not in s[k]["web_name"]) for k in s)


def test_promoted_side_gets_star_and_footnote():
    a = _p("Keeper", 4.6, 0.95, 0.01, 0.2, 8, pos="GKP"); a["team_flag"] = "promoted"
    html, _ = build_html({"meta": {"next_gameweek": 2},
                          "players": [a, _p("B", 4.0, 0.9, 0.2, 0.3, 10)]})
    assert "TST*" in html and "promoted side" in html
    html2, _ = build_html({"meta": {"next_gameweek": 2},
                           "players": [_p("B", 4.0, 0.9, 0.2, 0.3, 10)]})
    assert "promoted side" not in html2


def test_captain_uses_gameweek_xp_not_horizon_average():
    a = _p("HorizonKing", 4.0, 0.95, 0.2, 0.3, 10); a["xp_per_gw"] = 9.0
    b = _p("ThisWeek", 5.5, 0.95, 0.2, 0.3, 10); b["xp_per_gw"] = 3.0
    assert pick_standouts([a, b])["captain"]["web_name"] == "ThisWeek"


def test_html_carries_no_per_player_xp():
    ps = [_p("Cap", 6.37, 0.95, 0.30, 0.30, 13)]
    html, _ = build_html({"meta": {"next_gameweek": 2}, "players": ps})
    assert "6.37" not in html and "6.4" not in html and "floor" not in html
    assert "typical range" not in html and ">range" not in html
    assert "GW2 standouts" in html and "entry 116920" in html
    assert "—" not in html  # em dash


# ---------------------------------------------------------------------------
# GW-CALLS-LOKI (28.8): kortti ei saa erota data/gw_calls.json:sta
# ---------------------------------------------------------------------------
import datetime as _dt

import pytest

from scripts.render_standouts_card import reconcile_with_log

_DL = "2026-08-28T17:30:00Z"
_BEFORE = _dt.datetime(2026, 8, 28, 14, 0, tzinfo=_dt.timezone.utc)
_AFTER = _dt.datetime(2026, 8, 28, 18, 0, tzinfo=_dt.timezone.utc)


def _card_players():
    return [_p("Cap", 6.0, 0.95, 0.30, 0.30, 13),
            _p("Ceil", 5.0, 0.90, 0.28, 0.40, 15),
            _p("Safe", 4.5, 0.92, 0.10, 0.12, 9),
            _p("Gamb", 3.9, 0.80, 0.29, 0.45, 12),
            _p("Old", 4.0, 0.85, 0.20, 0.40, 11)]


def _log(cap="Cap", ceil="Ceil", safe="Safe", gamb="Gamb"):
    def c(call, name, haul=0.2, blank=0.3, p90=11):
        return {"call": call, "web_name": name, "team_short": "LOG",
                "pos": "MID", "metric": "p_haul", "value": haul, "gw_xp": 4.0,
                "xp_dist": {"p_haul": haul, "p_blank": blank, "p10": 1,
                            "median": 4, "p90": p90, "haul_pts": 10,
                            "blank_pts": 2, "n": 2000}}
    return {"gameweeks": [{"gw": 2, "deadline_utc": _DL,
                           "logged_at": "2026-08-28T13:55:00Z",
                           "calls": [c("captain_pick", cap), c("ceiling", ceil),
                                     c("safest", safe), c("gamble", gamb)]}]}


def test_kortti_sama_kuin_loki_menee_lapi_sellaisenaan():
    """Negatiivinen kontrolli: kun nimet tasmaavat, ei kaatumista eika
    lokin lukuja. Kortti pitaa tuoreen projektion luvut."""
    ps = _card_players()
    s = reconcile_with_log(pick_standouts(ps), 2, _log(), _BEFORE, ps)
    assert s["captain"]["web_name"] == "Cap"
    assert s["captain"]["xp_dist"]["p_haul"] == 0.30  # projektion luku, ei lokin 0.2
    # ei lokirivia talle GW:lle -> sellaisenaan
    s2 = reconcile_with_log(pick_standouts(ps), 3, _log(), _BEFORE, ps)
    assert s2["captain"]["web_name"] == "Cap"


def test_ennen_deadlinea_eroava_kortti_kaatuu():
    ps = _card_players()
    with pytest.raises(RuntimeError, match="log_gw_calls"):
        reconcile_with_log(pick_standouts(ps), 2, _log(gamb="Old"), _BEFORE, ps)
    data = {"meta": {"next_gameweek": 2}, "players": ps}
    with pytest.raises(RuntimeError):
        build_html(data, log=_log(cap="Old"), now=_BEFORE)


def test_deadlinen_jalkeen_kortti_renderoi_lokin_nimet_ja_luvut():
    ps = _card_players()
    log = _log(gamb="Old")
    s = reconcile_with_log(pick_standouts(ps), 2, log, _AFTER, ps)
    assert s["gamble"]["web_name"] == "Old"
    assert s["gamble"]["xp_dist"]["p_haul"] == 0.2   # lokin luku, ei projektion
    assert s["captain"]["xp_dist"]["p_haul"] == 0.2   # kaikki nelja lokista
    data = {"meta": {"next_gameweek": 2}, "players": ps}
    html, s2 = build_html(data, log=log, now=_AFTER)
    assert "Old" in html and s2["gamble"]["web_name"] == "Old"

