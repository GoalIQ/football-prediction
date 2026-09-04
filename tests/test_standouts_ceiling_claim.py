"""Portti: kortin ceiling-vaite ei saa kumota viereista tiiltaan.

🔴 MITATTU VIKA (4.9.2026, julkaisuportti). Kortin Ceiling-tiili sanoi
"top ceiling in the pool", mutta `pick_standouts()` valitsee ceilingin
`rest()`-joukosta josta kapteenivalinta on jo pudotettu. GW3:ssa kapteeni
Haalandin katto oli **14** ja "ceiling"-valinnan Isakin **11** — ja Haalandin
luku on VIEREISESSA tiilessa samalla kortilla. Kortti olisi julkaissut
lauseen jonka oma naapuri kumoaa.

Samassa lauseessa oli toinen vaite: "and he reaches it most often". Mikaan
kentta ei mittaa sita. p90 saavutetaan rakenteellisesti noin kerran
kymmenesta kaikilla, ja `/fpl/expected-points`-sivun oma tooltip sanoo sen
sanatarkasti. Tasapelisaanto on `p_haul`, ja silla kapteeni (31 %) voittaa
ceiling-valinnan (21 %).

Molemmat olivat kovakoodattua proosaa. Vaite johdetaan nyt datasta, ja tama
portti ajaa sen molemmilla mahdollisilla suhteilla (saanto 6a kohta 3):
kapteenin katto korkeampi, ja ceiling-valinnan katto korkeampi.
"""
from __future__ import annotations

import re

from scripts.render_standouts_card import build_html


def _player(pid: int, name: str, p90: int, p_haul: float, p_blank: float,
            price: int = 60, et: int = 4) -> dict:
    return {
        "id": pid, "web_name": name, "team_short": "TST", "pos": "FWD",
        "element_type": et, "price": price, "now_cost": price,
        "status": "a", "chance_next": 100, "p_start": 0.9, "xmins": 85,
        "data_basis": "pl_history", "owned_pct": 5.0,
        "xp_horizon_total": 30.0, "xp_per_gw": 5.0,
        "gameweeks": [{"gw": 3, "xp": 5.0}],
        "xp_dist": {"gw": 3, "n": 2000, "mean": 5.0, "p_haul": p_haul,
                    "p_blank": p_blank, "p10": 2, "median": 5, "p90": p90,
                    "haul_pts": 10, "blank_pts": 2},
    }


def _data(players: list[dict]) -> dict:
    return {"meta": {"next_gameweek": 3, "deadline_gameweek": 3,
                     "horizon_gw": 6, "generated_at": "2026-09-04T00:00:00Z"},
            "players": players}


def _why(html: str, tile: str) -> str:
    """Tiilen why-teksti."""
    i = html.find(tile)
    assert i != -1, f"tiilta {tile!r} ei loydy kortilta"
    return re.sub(r"<[^>]+>", " ", html[i:i + 900])


def test_kapteenin_katto_korkeampi_sanotaan_rajaus() -> None:
    """GW3:n oikea tilanne: kapteenilla on korkeampi katto."""
    players = [
        _player(1, "Cap", p90=14, p_haul=0.31, p_blank=0.05),
        _player(2, "Ceil", p90=11, p_haul=0.21, p_blank=0.15),
        _player(3, "Safe", p90=8, p_haul=0.05, p_blank=0.17, price=64, et=3),
        _player(4, "Risk", p90=10, p_haul=0.11, p_blank=0.35, price=61),
    ]
    html, s = build_html(_data(players), log=None)
    why = _why(html, "Ceiling")
    assert "outside our captain pick" in why, why[:200]
    assert "top ceiling in the pool" not in why, why[:200]


def test_ceilingin_katto_korkeampi_saa_sanoa_poolin() -> None:
    """Negatiivinen kontrolli: rajaus ei saa jaada paalle aina."""
    players = [
        _player(1, "Cap", p90=9, p_haul=0.31, p_blank=0.05),
        _player(2, "Ceil", p90=15, p_haul=0.21, p_blank=0.15),
        _player(3, "Safe", p90=8, p_haul=0.05, p_blank=0.17, price=64, et=3),
        _player(4, "Risk", p90=10, p_haul=0.11, p_blank=0.35, price=61),
    ]
    html, s = build_html(_data(players), log=None)
    why = _why(html, "Ceiling")
    assert "top ceiling in the pool" in why, why[:200]
    assert "outside our captain pick" not in why, why[:200]


def test_ei_vaiteta_kuinka_usein_katto_saavutetaan() -> None:
    """"reaches it most often" ei perustu mihinkaan kenttaan, eika saa palata."""
    players = [
        _player(1, "Cap", p90=14, p_haul=0.31, p_blank=0.05),
        _player(2, "Ceil", p90=11, p_haul=0.21, p_blank=0.15),
        _player(3, "Safe", p90=8, p_haul=0.05, p_blank=0.17, price=64, et=3),
        _player(4, "Risk", p90=10, p_haul=0.11, p_blank=0.35, price=61),
    ]
    html, _ = build_html(_data(players), log=None)
    for kielletty in ("reaches it most often", "most often"):
        assert kielletty not in html, kielletty


def test_ceiling_luku_on_sama_kuin_tiilen_oma_jakauma() -> None:
    """Lause ja luku samasta lahteesta: tiilen iso luku on sen oma p90."""
    players = [
        _player(1, "Cap", p90=14, p_haul=0.31, p_blank=0.05),
        _player(2, "Ceil", p90=11, p_haul=0.21, p_blank=0.15),
        _player(3, "Safe", p90=8, p_haul=0.05, p_blank=0.17, price=64, et=3),
        _player(4, "Risk", p90=10, p_haul=0.11, p_blank=0.35, price=61),
    ]
    html, s = build_html(_data(players), log=None)
    assert str(s["ceiling"]["xp_dist"]["p90"]) in _why(html, "Ceiling")
