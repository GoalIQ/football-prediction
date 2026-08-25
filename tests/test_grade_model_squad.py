"""Mallin rivin gradaus + provisionaalisuuden kanto pintaan (25.8.2026).

🔴 TAUSTA: `/api/fantasy/model-race` luki `data/model_squad_gw_scores.json`:aa
jota EI OLLUT OLEMASSA eika mikaan kirjoittanut. Jonossa oli useita riveja
joiden heratysehto oli "GW1 gradattu", ja endpoint vastasi "First scores land
once GW1 finishes" viela senkin jalkeen kun GW1 oli pelattu. Este ei ollut
FPL:n lippu vaan puuttuva gradaaja - selite nimesi vaaran mekanismin.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from src.models.fpl_model_race import build_race

ROOT = Path(__file__).resolve().parents[1]


def _load_grader():
    spec = importlib.util.spec_from_file_location(
        "grade_model_squad", ROOT / "scripts" / "grade_model_squad.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Gradattavuus: finished_provisional per ottelu, EI event.finished
# ---------------------------------------------------------------------------
def _boot(events):
    return {"events": events}


def test_kierros_on_gradattavissa_kun_kaikki_ottelut_pelattu():
    """🔴 Tama on koko skriptin olemassaolon syy.

    Mitattu 25.8 klo 07 UTC: GW1 pelattiin 21.-24.8, kaikki 10 ottelua olivat
    `finished_provisional: true`, mutta `event.finished` ja `data_checked`
    olivat molemmat yha False. `event.finished`:in odottaminen olisi pitanyt
    kierroksen poissa tuotteesta yli vuorokauden sen paattymisen jalkeen.
    """
    g = _load_grader()
    boot = _boot([{"id": 1, "finished": False, "data_checked": False,
                   "average_entry_score": 48}])
    fixtures = [{"event": 1, "finished_provisional": True} for _ in range(10)]
    st = g._gw_status(boot, fixtures)
    assert st[1]["gradable"] is True, (
        "kierros jonka kaikki ottelut on pelattu on gradattavissa, vaikka "
        "FPL ei olisi viela kaantanyt event.finished-lippua")
    assert st[1]["provisional"] is True, "data_checked False -> provisionaalinen"
    assert st[1]["fpl_average"] == 48


def test_kesken_oleva_kierros_ei_ole_gradattavissa():
    """Yksikin pelaamaton ottelu estaa gradauksen. Ilman tata kierros
    gradattaisiin kesken, ja `points` kasvaisi jalkikateen."""
    g = _load_grader()
    boot = _boot([{"id": 2, "finished": False, "data_checked": False,
                   "average_entry_score": 0}])
    fixtures = ([{"event": 2, "finished_provisional": True} for _ in range(9)]
                + [{"event": 2, "finished_provisional": False}])
    assert g._gw_status(boot, fixtures)[2]["gradable"] is False


def test_data_checked_poistaa_provisionaalisuuden():
    g = _load_grader()
    boot = _boot([{"id": 1, "finished": True, "data_checked": True,
                   "average_entry_score": 48}])
    fixtures = [{"event": 1, "finished_provisional": True}]
    st = g._gw_status(boot, fixtures)
    assert st[1]["gradable"] is True
    assert st[1]["provisional"] is False


def test_kierros_ilman_otteluita_jaa_pois():
    """Tyhja fixture-lista ei ole 'kaikki pelattu'. `all([])` on True, joten
    ilman tata vartiointia tuleva kierros olisi 'gradattavissa'."""
    g = _load_grader()
    boot = _boot([{"id": 38, "finished": False, "data_checked": False,
                   "average_entry_score": 0}])
    assert 38 not in g._gw_status(boot, [])


# ---------------------------------------------------------------------------
# Provisionaalisuus kannetaan pintaan asti
# ---------------------------------------------------------------------------
def test_provisionaalinen_kierros_merkitaan_payloadissa():
    """Luku saa nakya heti, mutta se EI saa esiintya lopullisena."""
    race = build_race({"gameweeks": [
        {"gw": 1, "points": 41, "fpl_average": 48, "provisional": True},
    ]}, None)
    assert race["meta"]["graded_gws"] == 1
    assert race["meta"]["provisional_gws"] == [1]
    assert race["gameweeks"][0]["provisional"] is True


def test_lopullinen_kierros_ei_kanna_lippua():
    race = build_race({"gameweeks": [
        {"gw": 1, "points": 41, "fpl_average": 48, "provisional": False},
    ]}, None)
    assert race["meta"]["provisional_gws"] == []
    assert race["gameweeks"][0]["provisional"] is False


def test_puuttuva_lippu_luetaan_lopulliseksi_ei_kaadu():
    """Vanha lokirivi ilman kenttaa: kaytos entinen, ei poikkeusta."""
    race = build_race({"gameweeks": [
        {"gw": 1, "points": 41, "fpl_average": 48},
    ]}, None)
    assert race["meta"]["provisional_gws"] == []
    assert race["gameweeks"][0]["provisional"] is False


def test_sekaotos_merkitsee_vain_provisionaaliset():
    race = build_race({"gameweeks": [
        {"gw": 1, "points": 41, "fpl_average": 48, "provisional": False},
        {"gw": 2, "points": 55, "fpl_average": 50, "provisional": True},
    ]}, None)
    assert race["meta"]["provisional_gws"] == [2]
    assert race["meta"]["graded_gws"] == 2
    assert [r["provisional"] for r in race["gameweeks"]] == [False, True]


def test_tyhja_loki_sanoo_yha_ettei_ole_alkanut():
    """Regressiovahti: provisionaalisuuden lisays ei saa rikkoa esikauden
    polkua, joka vastaa available=False + selite."""
    race = build_race({"gameweeks": []}, None)
    assert race["meta"]["available"] is False
    assert race["meta"]["graded_gws"] == 0
    assert race["gameweeks"] == []
