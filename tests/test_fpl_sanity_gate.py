# -*- coding: utf-8 -*-
"""Rakenteellinen CS%/FDR-sanity-gate (27.8): joka tarkistukselle oma
mutaatio, ja tyhjä data ei läpäise ([[kontrolli-lapaisi-tyhjana]],
[[kaksi-vahtia-yhdessa-testissa]])."""
from __future__ import annotations

import math

from src.models.fpl_sanity import spearman, structural_checks

FDR, CS = "avg_fdr", "avg_cs"


def _league(n: int = 20) -> tuple[dict, dict]:
    """Synteettinen liiga: vahvuus laskee tasaisesti, FDR nousee, CS% laskee.
    Pieni jitter estää täydellisen monotonian (aito data ei ole sellaista)."""
    teams, strength = {}, {}
    for i in range(n):
        name = f"T{i:02d}"
        strength[name] = 1.5 - i * 0.15
        jitter = 0.05 * ((i * 7) % 3 - 1)
        teams[name] = {FDR: round(1.4 + i * 0.16 + jitter, 2),
                       CS: round(44.0 - i * 1.4 - jitter * 10, 1)}
    return teams, strength


def _ok(checks):
    return all(p for _, p, _ in checks)


def _failed(checks):
    return [label for label, p, _ in checks if not p]


def test_healthy_league_passes():
    teams, strength = _league()
    checks = structural_checks(teams, strength, FDR, CS)
    assert _ok(checks), _failed(checks)
    assert len(checks) == 7


def test_spearman_basic():
    assert abs(spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-9
    assert abs(spearman([1, 2, 3, 4], [1, 2, 3, 4]) - 1.0) < 1e-9
    assert math.isnan(spearman([1, 1, 1], [1, 2, 3]))


def test_mutation_reversed_cs_fails_direction_and_tiers():
    """Ylöspäin kääntynyt CS% (heikot pitävät nollan useammin) = data on
    väärin päin. Suunta JA mallitasot kaatuvat, muut eivät."""
    teams, strength = _league()
    css = [teams[t][CS] for t in sorted(teams)]
    for t, v in zip(sorted(teams), reversed(css)):
        teams[t][CS] = v
    failed = _failed(structural_checks(teams, strength, FDR, CS))
    assert any("vastakkaissuuntaiset" in f for f in failed)
    assert any("vahvin" in f for f in failed)
    assert not any("joukkueita" in f or "arvoalue" in f for f in failed)


def test_mutation_flat_fdr_fails_spread():
    teams, strength = _league()
    for t in teams:
        teams[t][FDR] = 3.0
    failed = _failed(structural_checks(teams, strength, FDR, CS))
    assert any("hajonta" in f for f in failed)


def test_mutation_missing_team_fails_count_only():
    teams, strength = _league()
    teams.pop("T19")
    failed = _failed(structural_checks(teams, strength, FDR, CS))
    assert failed == ["joukkueita == 20"]


def test_mutation_nan_does_not_pass_silently():
    teams, strength = _league()
    teams["T05"][CS] = float("nan")
    checks = structural_checks(teams, strength, FDR, CS)
    assert not _ok(checks)
    assert any("lukuja" in label for label, p, _ in checks if not p)


def test_empty_league_fails_every_check():
    checks = structural_checks({}, {}, FDR, CS)
    assert not _ok(checks)
    assert sum(1 for _, p, _ in checks if not p) >= 6


def test_mutation_strength_missing_fails_tier_check_not_others():
    """Vahvuudet puuttuvat (esim. fit ei kata joukkueita) -> tasotarkistus
    kaatuu nimetysti, ei hiljaa läpi."""
    teams, _ = _league()
    failed = _failed(structural_checks(teams, {}, FDR, CS))
    assert failed == ["mallin tasot erottuvat"]


def test_promoted_team_that_is_strong_does_not_fail():
    """Vanhan portin vikaluokka: nousija joka on mallissa vahva (Ipswich GW1:n
    jälkeen) EI saa kaataa porttia, koska tasot tulevat fitistä eikä
    nousijalistasta."""
    teams, strength = _league()
    # "Nousija" T03 on vahva: sillä on jo vahvan joukkueen FDR/CS%.
    checks = structural_checks(teams, strength, FDR, CS)
    assert _ok(checks)


def test_cs_out_of_range_fails_range_only():
    teams, strength = _league()
    teams["T00"][CS] = 91.0
    failed = _failed(structural_checks(teams, strength, FDR, CS))
    assert any("CS% jokaisella" in f for f in failed)
