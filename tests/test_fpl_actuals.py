"""TOTEUTUNEET PISTEET (22.8.2026) — kausivartija ja puuttuvan tiedon rajat.

Vartioitava vikaluokka: edellisen kauden luvut renderoityvat kuluvan kauden
rivin viereen ilman etta mikaan kaatuu. Sama luokka on osunut ennenkin
(korttien vaara lahde 17.8: kentannimet olivat samat molemmissa tiedostoissa,
joten vaara lahde ei kaatanut mitaan).

Toinen vartioitava: pelaamaton kierros EI saa palauttaa nollia. Nolla on
vaite ("pelasi eika saanut pisteita"), puuttuva rivi on totuus.
"""
from __future__ import annotations

import json

import pytest

from src.models import fpl_actuals


@pytest.fixture
def doc(tmp_path, monkeypatch):
    """Tuotannon muotoinen artefakti omaan hakemistoon."""
    p = tmp_path / "player-gw.json"

    def write(basis: str = "2026/27"):
        p.write_text(json.dumps({
            "meta": {"basis_season": basis, "max_gw": 1,
                     "cols": ["gw", "pts", "mins"]},
            "players": {"10": [[1, 11, 90]], "15": [[1, 6, 75]],
                        "20": [[1, 0, 12]]},
        }), encoding="utf-8")
        monkeypatch.setattr(fpl_actuals, "PLAYER_GW_PATH", p)
        # mtime-cache: nollaa jotta fixture ei nae edellisen testin doccia
        fpl_actuals._CACHE["mtime"] = None
        fpl_actuals._CACHE["doc"] = None
    return write


def test_points_for_returns_played_gameweek(doc):
    doc()
    pts = fpl_actuals.points_for(1, "2026/27")
    assert pts == {10: 11, 15: 6, 20: 0}


def test_zero_points_row_is_kept(doc):
    """Pelaaja joka PELASI ja sai 0 pistetta on eri asia kuin puuttuva."""
    doc()
    assert fpl_actuals.points_for(1, "2026/27")[20] == 0


def test_wrong_season_returns_nothing(doc):
    """Kausivartija: 25/26-artefaktin lukuja ei anneta 26/27-pyyntoon."""
    doc(basis="2025/26")
    assert fpl_actuals.points_for(1, "2026/27") == {}
    # ...mutta oikealla kaudella samat luvut tulevat lapi.
    assert fpl_actuals.points_for(1, "2025/26") == {10: 11, 15: 6, 20: 0}


def test_unplayed_gameweek_is_empty_not_zeros(doc):
    doc()
    assert fpl_actuals.points_for(5, "2026/27") == {}


def test_no_season_arg_skips_the_guard(doc):
    """Ilman kausiargumenttia vartija ei aktivoidu (taaksepain-yhteensopiva)."""
    doc(basis="2025/26")
    assert fpl_actuals.points_for(1) == {10: 11, 15: 6, 20: 0}


def test_missing_file_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(fpl_actuals, "PLAYER_GW_PATH", tmp_path / "ei-ole.json")
    fpl_actuals._CACHE["mtime"] = None
    assert fpl_actuals.points_for(1, "2026/27") == {}
    assert fpl_actuals.basis_season() is None
    assert fpl_actuals.max_gw() is None


def test_broken_json_is_not_an_error(tmp_path, monkeypatch):
    p = tmp_path / "player-gw.json"
    p.write_text("{ ei ole jsonia", encoding="utf-8")
    monkeypatch.setattr(fpl_actuals, "PLAYER_GW_PATH", p)
    fpl_actuals._CACHE["mtime"] = None
    assert fpl_actuals.points_for(1, "2026/27") == {}
