"""SIIRTOSUUNNITTELUN aloitus-GW (22.8.2026).

Vikaluokka jota nama testit vartioivat: kesken kierroksen `picks_gw` ja
`meta.next_gameweek` ovat molemmat yha KULUVA GW (pelaamattomia fixtureita on
jaljella), joten suunnitelma alkoi kierroksesta jonka deadline oli jo mennyt.
Mitattu tuotannosta 22.8: /api/fantasy/plan?entry= palautti start_gw 1 kun
GW1:n deadline oli mennyt edellisena paivana — jokainen sille kierrokselle
ehdotettu siirto on hyodyton.

Negatiivinen kontrolli on yhta tarkea kuin positiivinen: ilman
`deadline_gameweek`-kenttaa (vanha payload) kaytoksen on oltava bittitarkasti
entinen, muuten korjaus rikkoisi esikausipolun.
"""
from __future__ import annotations

import pytest

from src.models.fpl_rate_team import clamp_gw_to_projections, planning_start_gw


def _pool(gws: list[int]) -> list[dict]:
    return [{"id": 1, "gameweeks": [{"gw": g} for g in gws]}]


def _xp(next_gw: int, deadline_gw=None) -> dict:
    meta = {"next_gameweek": next_gw}
    if deadline_gw is not None:
        meta["deadline_gameweek"] = deadline_gw
    return {"meta": meta}


def test_deadline_passed_starts_from_next_open_gameweek():
    """GW1 kesken (kate 1-6), deadline_gameweek 2 -> suunnittelu alkaa 2:sta."""
    assert planning_start_gw(1, _pool([1, 2, 3, 4, 5, 6]), _xp(1, 2)) == 2


def test_without_deadline_field_behaviour_is_unchanged():
    """Vanha payload ilman kenttaa -> tasan clamp_gw_to_projectionsin tulos."""
    pool, xp = _pool([1, 2, 3]), _xp(1)
    assert planning_start_gw(1, pool, xp) == clamp_gw_to_projections(1, pool, xp)
    assert planning_start_gw(1, pool, xp) == 1


def test_deadline_gw_not_covered_falls_back():
    """Deadline osoittaa GW:hen jolle ei ole projektioita -> ei hypata sinne."""
    assert planning_start_gw(6, _pool([5, 6]), _xp(6, 7)) == 6


def test_deadline_gw_equal_or_behind_is_ignored():
    """Ennen deadlinea deadline_gameweek == next_gameweek -> ei muutosta."""
    assert planning_start_gw(2, _pool([2, 3, 4]), _xp(2, 2)) == 2
    # Ei myoskaan koskaan taaksepain.
    assert planning_start_gw(3, _pool([2, 3, 4]), _xp(3, 2)) == 3


@pytest.mark.parametrize("bad", [None, "2", 2.0, True])
def test_non_int_deadline_field_is_ignored(bad):
    """Rikkinainen kentta ei saa muuttaa suunnittelun aloitusta.

    `True` on mukana tarkoituksella: Pythonissa bool on int:n alaluokka, ja
    `True > 1` on False, joten se ei saa nostaa aloitusta vahingossa."""
    assert planning_start_gw(1, _pool([1, 2, 3]), _xp(1, bad)) == 1
