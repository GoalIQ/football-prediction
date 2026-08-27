# -*- coding: utf-8 -*-
"""STANDOUTS-CARD (27.8): valinnat ovat puhtaita funktioita artefaktin
xp_dist-kentista. Portti: (1) penkkilaista ei nosteta, (2) epavarma pelaaja ei
ole "safest", (3) gamble vaatii aidon blank-riskin, (4) kortti ei tarvitse
per-pelaaja-xP:ta muuhun kuin kapteenin jarjestykseen."""
from __future__ import annotations

from scripts.render_standouts_card import pick_standouts, build_html


def _p(name, xp, p_start, haul, blank, p90, status="a", pos="MID"):
    return {"web_name": name, "pos": pos, "team_short": "TST", "price": 7.5,
            "status": status, "p_start": p_start, "xp_per_gw": xp,
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


def test_html_carries_no_per_player_xp():
    ps = [_p("Cap", 6.37, 0.95, 0.30, 0.30, 13)]
    html, _ = build_html({"meta": {"next_gameweek": 2}, "players": ps})
    assert "6.37" not in html and "6.4" not in html
    assert "GW2 standouts" in html and "entry 116920" in html
    assert "—" not in html  # em dash
