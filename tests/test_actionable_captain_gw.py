# -*- coding: utf-8 -*-
"""THIS-WEEK-KAPTEENI-KESKEN-KIERROKSEN (5.9.2026, selainaudit).

Kesken GW3:n This week sanoi "1 thing to do: Captain Haaland 6.07 xP in GW3"
ja My team "Captain suggestion ... in GW3", vaikka GW3 oli lukittu ja
deadline-nauha sanoi GW4. Kapteenikutsu on toimenpide, joten sen kierros on
se johon voi viela vaikuttaa. Sama funktio ajetaan synteettisilla vaiheilla
(saanto 6a): ennen deadlinea, kesken kierroksen, projektio ei kata seuraavaa.
"""
from __future__ import annotations

from src.models import fpl_rate_team as rt


def _pool(gws):
    return [{"id": 1, "web_name": "A", "team_short": "ARS",
             "gameweeks": [{"gw": g, "xp": 5.0} for g in gws]}]


def _xp(next_gw, deadline_gw):
    return {"meta": {"next_gameweek": next_gw, "deadline_gameweek": deadline_gw}}


def test_before_deadline_same_gameweek():
    assert rt.actionable_captain_gw(3, _pool([3, 4, 5]), _xp(3, 3)) == 3


def test_in_progress_moves_to_deadline_gameweek():
    """GW3 kaynnissa (next 3, deadline 4) -> kapteeni GW4:lle."""
    assert rt.actionable_captain_gw(3, _pool([3, 4, 5]), _xp(3, 4)) == 4


def test_in_progress_without_coverage_stays():
    """Projektio ei kata deadline-kierrosta (kauden loppu, vanha payload)."""
    assert rt.actionable_captain_gw(3, _pool([3]), _xp(3, 4)) == 3


def test_missing_deadline_field_stays():
    assert rt.actionable_captain_gw(3, _pool([3, 4]), {"meta": {"next_gameweek": 3}}) == 3


def test_meta_carries_captain_gw_and_pick_follows_it():
    """captain_suggestion saa saman kierroksen kuin meta.captain_gw: pelaaja
    jolla on paras GW4-xP voittaa GW3-parhaan kun GW3 on kaynnissa."""
    xi = [
        {"id": 1, "web_name": "GW3king", "team_short": "A",
         "gameweeks": [{"gw": 3, "xp": 9.0}, {"gw": 4, "xp": 2.0}]},
        {"id": 2, "web_name": "GW4king", "team_short": "B",
         "gameweeks": [{"gw": 3, "xp": 4.0}, {"gw": 4, "xp": 8.0}]},
    ]
    gw = rt.actionable_captain_gw(3, xi, _xp(3, 4))
    assert gw == 4
    assert rt.captain_suggestion(xi, gw)["pick"]["web_name"] == "GW4king"
    assert rt.captain_suggestion(xi, 3)["pick"]["web_name"] == "GW3king"


def test_wired_into_rate_team_response():
    import inspect
    src = inspect.getsource(rt)
    assert "cap_sugg = captain_suggestion(xi, cap_gw)" in src
    assert '"captain_gw": cap_gw' in src
