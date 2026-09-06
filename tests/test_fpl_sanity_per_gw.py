# -*- coding: utf-8 -*-
"""PHASE0-SANITY-GATE-RHO (6.9.2026): suunta mitataan joka kierroksella.

Mitattu git-historiasta 23.8-5.9: kierroskohtainen Spearman(FDR, CS%) oli
-0.84...-0.96 jokaisessa artefaktissa, horisontin keskiarvojen rho liukui
-0.88 -> -0.65 ja kaatuneessa ajossa -0.51. Synteettinen liiga alla toistaa
juuri sen: joka kierros vahvasti vastakkaissuuntainen, keskiarvot heikosti.
Saanto 6a(3): invariantti mitataan joka vaiheessa, ei nykyhetkessa.
"""
from __future__ import annotations
import math
from src.models.fpl_sanity import (SPEARMAN_MAX, per_gw_direction, spearman,
                                   structural_checks)

FDR, CS = "next_avg_fdr", "next_avg_cs_pct"


def _league(n: int = 20, gws: int = 6, reverse_gw: int | None = None,
            own_defence_spread: float = 8.0) -> tuple[dict, dict]:
    """Joka kierros: CS% laskee FDR:n kasvaessa (rho ~ -1). Joukkueen oma
    puolustus lisaa vakio-offsetin joka EI riipu FDR:sta; kun offsetin
    hajonta on suuri ja otteluohjelmat eroavat, horisontin keskiarvojen
    korrelaatio heikkenee vaikka kierroskohtainen pitaa."""
    teams, strength = {}, {}
    for i in range(n):
        name = f"T{i:02d}"
        strength[name] = 1.5 - i * 0.15
        own = own_defence_spread * ((i * 7) % 5) / 4.0    # 0..spread, sekoitettu
        fixtures = []
        for g in range(1, gws + 1):
            # Syklinen ohjelma (mod 7): kuuden kierroksen keskiarvo-FDR on
            # lahes sama kaikilla, joten keskiarvojen rho on heikko (~ -0.55,
            # sama luokka kuin kaatunut ajo -0.51) vaikka jokainen kierros on
            # jyrkasti vastakkaissuuntainen (~ -0.97). Mitattu 6.9.
            fdr = 1.0 + ((i * 2 + g * 3) % 7) / 2.0           # 1.0..4.0
            cs = 60.0 - 12.0 * fdr + own
            if reverse_gw == g:
                cs = 10.0 + 12.0 * fdr + own
            fixtures.append({"gw": g, "fdr": round(fdr, 2), "cs_pct": round(cs, 1)})
        teams[name] = {
            "fixtures": fixtures,
            FDR: round(sum(f["fdr"] for f in fixtures) / gws, 2),
            CS: round(min(75.0, max(3.0, sum(f["cs_pct"] for f in fixtures) / gws)), 1),
        }
    return teams, strength


def _direction(checks):
    return next(c for c in checks if c[0].startswith("FDR ja CS% vastakkaissuuntaiset"))


def test_per_gw_holds_where_average_based_check_would_fail():
    teams, strength = _league()
    per = per_gw_direction(teams, "fixtures")
    assert len(per) == 6
    assert all(r <= -0.9 for _, r in per), per
    # Keskiarvoista laskettu rho on heikompi kuin kynnys: sama vikaluokka
    # kuin 5.9-6.9 kaatuneet ajot (-0.51). Ilman tata kontrollia testi ei
    # todistaisi etta uusi mittari eroaa vanhasta.
    names = sorted(teams)
    avg_rho = spearman([teams[t][FDR] for t in names], [teams[t][CS] for t in names])
    assert avg_rho > SPEARMAN_MAX, avg_rho
    label, passed, detail = _direction(structural_checks(teams, strength, FDR, CS,
                                                         fixtures_key="fixtures"))
    assert passed, detail
    assert "joka kierroksella" in label
    assert "vain tiedoksi" in detail


def test_check_count_unchanged_with_fixtures_key():
    teams, strength = _league()
    assert len(structural_checks(teams, strength, FDR, CS, fixtures_key="fixtures")) == 7


def test_mutation_one_reversed_gameweek_fails():
    teams, strength = _league(reverse_gw=4)
    per = dict(per_gw_direction(teams, "fixtures"))
    assert per[4] > 0.5, per
    label, passed, detail = _direction(structural_checks(teams, strength, FDR, CS,
                                                         fixtures_key="fixtures"))
    assert not passed
    assert "GW4" in detail


def test_no_fixture_data_fails_loudly_not_silently():
    teams, strength = _league()
    for t in teams.values():
        t["fixtures"] = []
    label, passed, detail = _direction(structural_checks(teams, strength, FDR, CS,
                                                         fixtures_key="fixtures"))
    assert not passed
    assert "ei kierrosdataa" in detail


def test_gameweek_with_too_few_fixtures_is_skipped_not_counted():
    teams, strength = _league()
    # GW7 vain kolmella joukkueella (blank): ei mittaan, ei kaada.
    for i, t in enumerate(teams.values()):
        if i < 3:
            t["fixtures"].append({"gw": 7, "fdr": 2.0, "cs_pct": 30.0})
    per = dict(per_gw_direction(teams, "fixtures"))
    assert 7 not in per and len(per) == 6


def test_nan_gameweek_fails():
    teams, strength = _league()
    # GW2: kaikilla sama FDR -> Spearman NaN -> portti kaatuu nimetysti.
    for t in teams.values():
        for f in t["fixtures"]:
            if f["gw"] == 2:
                f["fdr"] = 3.0
    per = dict(per_gw_direction(teams, "fixtures"))
    assert math.isnan(per[2])
    _, passed, detail = _direction(structural_checks(teams, strength, FDR, CS,
                                                     fixtures_key="fixtures"))
    assert not passed and "GW2 NaN" in detail


def test_without_fixtures_key_old_average_check_still_applies():
    teams, strength = _league()
    label, passed, _ = _direction(structural_checks(teams, strength, FDR, CS))
    assert "joka kierroksella" not in label
