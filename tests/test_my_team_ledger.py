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


# ---------------------------------------------------------------------------
# 26.9 (MP-14, julkaisutarkistaja B3/B4): kesken oleva kierros ja vertailukohta
# ---------------------------------------------------------------------------


def test_kesken_oleva_kierros_ei_ole_riveissa_eika_summissa(freeze):
    """B3: GW:n deadlinen jalkeen koko kierroksen projektio (~55) verrattiin
    osittaisiin pisteisiin -> ~-55 pylvas. Kesken oleva jaa pois ja kerrotaan."""
    freeze({1: {10: 5.0}, 2: {10: 55.0}})
    out = L.build_ledger(_hist([(1, 8, 0, 0), (2, 3, 0, 0)]),
                         {1: _picks([(10, 1)]), 2: _picks([(10, 1)])},
                         provisional_gws=[2], states={2: "in_progress"})
    assert [r["gw"] for r in out["gameweeks"]] == [1]
    assert out["meta"]["in_progress_gws"] == [2]
    assert out["totals"]["actual"] == 8 and out["totals"]["projected"] == 5.0
    assert out["meta"]["provisional_gws"] == []


def test_tila_kulkee_riville_ja_tuntematon_on_oletus(freeze):
    freeze({1: {10: 5.0}, 2: {10: 5.0}, 3: {10: 5.0}})
    out = L.build_ledger(_hist([(1, 8, 0, 0), (2, 8, 0, 0), (3, 8, 0, 0)]),
                         {g: _picks([(10, 1)]) for g in (1, 2, 3)},
                         provisional_gws=[2, 3], states={2: "awaiting_check"})
    assert [r["state"] for r in out["gameweeks"]] == ["final", "awaiting_check", "unknown"]
    # Kesken-tila ilman provisionaalisuutta ei poista lopullista kierrosta.
    out2 = L.build_ledger(_hist([(1, 8, 0, 0)]), {1: _picks([(10, 1)])},
                          provisional_gws=[], states={1: "in_progress"})
    assert [r["gw"] for r in out2["gameweeks"]] == [1]


def test_fpl_keskiarvo_rivilla_ja_summassa_vain_kun_kaikille_on(freeze):
    """B4: vertailukohta FPL:n omasta keskiarvosta; osittainen summa ei kelpaa."""
    freeze({1: {10: 5.0}, 2: {10: 5.0}})
    kaksi = (_hist([(1, 8, 0, 0), (2, 3, 0, 0)]), {1: _picks([(10, 1)]), 2: _picks([(10, 1)])})
    out = L.build_ledger(*kaksi, averages={1: 50, 2: 81})
    assert [r["fpl_average"] for r in out["gameweeks"]] == [50, 81]
    assert out["totals"]["fpl_average"] == 131
    for puuttuva in ({1: 50}, {1: 50, 2: 0}, {1: 50, 2: None}, None):
        assert L.build_ledger(*kaksi, averages=puuttuva)["totals"]["fpl_average"] is None


def test_endpoint_kytkee_tilan_ja_keskiarvon(monkeypatch, client):
    """Kutsupaikka: endpoint lukee kierroksen tilan jaetusta lukijasta ja
    keskiarvon bootstrapista (testi kaatuu jos kytkenta puuttuu)."""
    from src.data import fpl_api
    monkeypatch.setattr(L.fpl_actuals, "frozen_xp_for", lambda gw: {10: 5.0})
    monkeypatch.setattr(fpl_api, "fetch_entry_history",
                        lambda *a, **k: _hist([(1, 8, 0, 0), (2, 3, 0, 0)]))
    monkeypatch.setattr(fpl_api, "fetch_entry_picks", lambda *a, **k: _picks([(10, 1)]))
    monkeypatch.setattr(fpl_api, "fetch_bootstrap", lambda *a, **k: {"events": [
        {"id": 1, "finished": True, "data_checked": True, "average_entry_score": 50},
        {"id": 2, "finished": False, "data_checked": False, "average_entry_score": 0},
    ]})
    import datetime as dt
    pian = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)).isoformat()
    monkeypatch.setattr(fpl_api, "fetch_fixtures", lambda *a, **k: [
        {"event": 1, "finished_provisional": True, "kickoff_time": "2026-08-22T14:00:00Z"},
        {"event": 2, "finished_provisional": False, "kickoff_time": pian},
    ])
    import src.models.model_squad_scores as mss
    monkeypatch.setattr(mss, "provisional_hint_gws", lambda: [])
    r = client.get("/api/fantasy/my-team-ledger?entry=424242")
    assert r.status_code == 200, r.text
    b = r.json()
    assert [g["gw"] for g in b["gameweeks"]] == [1]
    assert b["meta"]["in_progress_gws"] == [2]
    assert b["gameweeks"][0]["fpl_average"] == 50
    assert b["totals"]["fpl_average"] == 50
