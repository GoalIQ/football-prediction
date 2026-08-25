"""MY TEAM LEDGER: ennuste vs toteuma kauden yli (25.8.2026).

Villen kysymys: "pitaisko fantasyyn laittaa joku erillinen my team missa oikeet
pisteet vrt mita ennustettu".
"""
from __future__ import annotations

import pytest

from src.models import fpl_my_team_ledger as L


def _hist(rows):
    return {"current": [{"event": gw, "points": pts, "points_on_bench": bench,
                         "event_transfers_cost": cost}
                        for gw, pts, bench, cost in rows]}


def _picks(pairs):
    """pairs = [(element_id, multiplier), ...]"""
    return {"picks": [{"element": e, "multiplier": m} for e, m in pairs]}


@pytest.fixture
def freeze(monkeypatch):
    def _aseta(kartta):
        monkeypatch.setattr(L.fpl_actuals, "frozen_xp_for",
                            lambda gw: kartta.get(gw, {}))
    return _aseta


# ---------------------------------------------------------------------------
# Kertoimet molemmilla puolilla
# ---------------------------------------------------------------------------
def test_kapteeni_tuplataan_ja_penkki_nollataan(freeze):
    """🔴 Toteutuneet kierrospisteet sisaltavat kapteenin tuplauksen ja
    jattavat penkin nollaan. Ilman kerrointa projektiossa vertailu olisi
    15 pelaajan summa vastaan 11 pelaajan tulos - malli nayttaisi
    systemaattisesti liian optimistiselta joka ainoalla kierroksella."""
    freeze({1: {10: 5.0, 11: 3.0, 12: 9.0}})
    picks = _picks([(10, 1), (11, 0), (12, 2)])   # pelaava, penkki, kapteeni
    out = L.build_ledger(_hist([(1, 20, 3, 0)]), {1: picks})
    # 5*1 + 3*0 + 9*2 = 23.0
    assert out["gameweeks"][0]["projected"] == 23.0
    assert out["gameweeks"][0]["players_matched"] == 3


def test_triple_captain_kolminkertaistuu(freeze):
    freeze({1: {10: 4.0}})
    out = L.build_ledger(_hist([(1, 12, 0, 0)]), {1: _picks([(10, 3)])})
    assert out["gameweeks"][0]["projected"] == 12.0


# ---------------------------------------------------------------------------
# Puuttuva freeze / puuttuva pelaaja: nolla ei ole "ei tietoa"
# ---------------------------------------------------------------------------
def test_kierros_ilman_freezea_jatetaan_pois_ja_kerrotaan(freeze):
    """🔴 Ilman freezea emme tieda mita ennustimme. 0,0 projektiona nayttaisi
    silta etta malli odotti nollaa - se on eri vaite kuin 'emme tieda'."""
    freeze({2: {10: 5.0}})           # GW1:lle EI freezea
    out = L.build_ledger(_hist([(1, 60, 0, 0), (2, 40, 0, 0)]),
                         {1: _picks([(10, 1)]), 2: _picks([(10, 1)])})
    assert [r["gw"] for r in out["gameweeks"]] == [2]
    assert out["meta"]["missing_freeze_gws"] == [1]
    assert out["totals"]["actual"] == 40, "GW1:n toteumaa ei saa laskea mukaan"


def test_freezesta_puuttuva_pelaaja_ei_ole_nolla(freeze):
    """Pelaaja jota ei ole freezessa jatetaan summasta pois JA kattavuus
    kerrotaan. Nollana han vetaisi projektiota alas ja saisi mallin
    nayttamaan tarkemmalta kuin se oli."""
    freeze({1: {10: 5.0}})           # pelaaja 11 puuttuu
    out = L.build_ledger(_hist([(1, 8, 0, 0)]),
                         {1: _picks([(10, 1), (11, 1)])})
    r = out["gameweeks"][0]
    assert r["projected"] == 5.0
    assert r["players_matched"] == 1, "vajaa kattavuus on kerrottava"


def test_kaikki_kierrokset_ilman_freezea_ei_ole_saatavilla(freeze):
    freeze({})
    out = L.build_ledger(_hist([(1, 50, 0, 0)]), {1: _picks([(10, 1)])})
    assert out["meta"]["available"] is False
    assert out["meta"]["missing_freeze_gws"] == [1]
    assert out["totals"]["projected"] is None, "ei nollaa vaan None"


# ---------------------------------------------------------------------------
# Kumulatiivisuus ja etumerkki
# ---------------------------------------------------------------------------
def test_kumulatiivinen_ero_kertyy_ja_etumerkki_on_pelaajan_hyvaksi(freeze):
    """diff = toteuma - ennuste. Positiivinen = ylitit ennusteen."""
    freeze({1: {10: 5.0}, 2: {10: 5.0}})
    out = L.build_ledger(_hist([(1, 8, 0, 0), (2, 3, 0, 0)]),
                         {1: _picks([(10, 1)]), 2: _picks([(10, 1)])})
    g = out["gameweeks"]
    assert g[0]["diff"] == 3.0 and g[0]["cumulative_diff"] == 3.0
    assert g[1]["diff"] == -2.0 and g[1]["cumulative_diff"] == 1.0
    assert out["totals"]["diff"] == 1.0


def test_provisionaalinen_kierros_merkitaan(freeze):
    freeze({1: {10: 5.0}})
    out = L.build_ledger(_hist([(1, 8, 0, 0)]), {1: _picks([(10, 1)])},
                         provisional_gws=[1])
    assert out["gameweeks"][0]["provisional"] is True
    assert out["meta"]["provisional_gws"] == [1]


def test_provisional_lista_ei_vuoda_pois_jatetyista(freeze):
    """Kierros joka jai pois freezen puutteen takia ei saa esiintya
    provisional_gws:ssa - se lupaisi rivin jota payloadissa ei ole."""
    freeze({2: {10: 5.0}})
    out = L.build_ledger(_hist([(1, 60, 0, 0), (2, 40, 0, 0)]),
                         {1: _picks([(10, 1)]), 2: _picks([(10, 1)])},
                         provisional_gws=[1, 2])
    assert out["meta"]["provisional_gws"] == [2]


# ---------------------------------------------------------------------------
# Ilman entrya
# ---------------------------------------------------------------------------
def test_ilman_entrya_selite_eika_nollat():
    out = L.build_ledger(None, None)
    assert out["meta"]["available"] is False
    assert out["meta"]["note_code"] == L.CODE_NO_ENTRY
    assert out["totals"] == {"projected": None, "actual": None, "diff": None}
