# -*- coding: utf-8 -*-
"""XP-DISTRIBUTION (27.8.2026): jakauma ei saa olla toinen totuus xP:n rinnalla.

Portti 1: simulaation keskiarvo ~ xp_components.total samoilla syotteilla.
Portti 2: tunnusluvut ovat todennakoisyyksia ja jarjestyksessa (p10 <= med <= p90).
Portti 3 (negatiivinen kontrolli): maaliuhan nollaus pudottaa P(10+):n;
          p_haul ja p_blank liikkuvat oikeaan suuntaan.
Portti 4: sama siemen -> sama tulos (determinismi).
"""
from __future__ import annotations

import numpy as np
import pytest

from src.models import fpl_xp as xp

RATES_MID = {"xg90": 0.45, "xa90": 0.30, "yc90": 0.15, "bonus90": 0.6,
             "saves90": 0.0, "dc_freq": 0.2}
RATES_DEF = {"xg90": 0.08, "xa90": 0.10, "yc90": 0.20, "bonus90": 0.4,
             "saves90": 0.0, "dc_freq": 0.45}
RATES_GKP = {"xg90": 0.0, "xa90": 0.0, "yc90": 0.02, "bonus90": 0.3,
             "saves90": 3.1, "dc_freq": 0.0}
CTX = {"goal_mult": 1.1, "cs_prob": 0.35,
       "conceded_dist": [0.35, 0.35, 0.18, 0.08, 0.03, 0.01],
       "opp_goal_mult": 0.9}


def _sim(pos, rates, xmins=85.0, p60=0.9, p1=0.05, ctx=CTX, seed=7, n=40000):
    rng = np.random.default_rng(seed)
    return xp.simulate_fixture_points(pos, rates, xmins, p60, p1, ctx, rng, n=n)


@pytest.mark.parametrize("pos,rates,tol", [
    (3, RATES_MID, 0.15),
    (2, RATES_DEF, 0.15),
    # GKP: FPL floor(saves/3) -> simulaation keskiarvo alle lineaarisen
    # odotusarvon; sallittu ero dokumentoitu moduulissa.
    (1, RATES_GKP, 0.45),
])
def test_simulation_mean_matches_xp_components(pos, rates, tol):
    expected = xp.xp_components(pos, rates, 85.0, 0.9, 0.05, CTX)["total"]
    got = _sim(pos, rates).mean()
    assert abs(got - expected) <= tol, (pos, got, expected)


def test_summary_is_probabilities_and_ordered():
    s = xp.summarize_distribution(_sim(3, RATES_MID), gw=2)
    assert 0.0 <= s["p_haul"] <= 1.0 and 0.0 <= s["p_blank"] <= 1.0
    assert s["p10"] <= s["median"] <= s["p90"]
    assert s["gw"] == 2 and s["n"] == 40000
    assert s["haul_pts"] == 10 and s["blank_pts"] == 2


def test_negative_control_zero_goal_threat_drops_haul_probability():
    base = xp.summarize_distribution(_sim(3, RATES_MID), gw=2)
    flat = xp.summarize_distribution(
        _sim(3, dict(RATES_MID, xg90=0.0, xa90=0.0)), gw=2)
    assert flat["p_haul"] < base["p_haul"] * 0.5
    assert flat["p_blank"] > base["p_blank"]


def test_bench_player_is_mostly_blank():
    s = xp.summarize_distribution(_sim(3, RATES_MID, xmins=15.0, p60=0.05, p1=0.4), gw=2)
    assert s["p_blank"] > 0.8 and s["p_haul"] < 0.05


def test_blank_gameweek_gives_none():
    assert xp.summarize_distribution(np.array([]), gw=3) is None


def test_deterministic_with_same_seed():
    a = _sim(2, RATES_DEF, seed=11, n=500)
    b = _sim(2, RATES_DEF, seed=11, n=500)
    assert np.array_equal(a, b)
