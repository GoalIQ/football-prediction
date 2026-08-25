"""POST-GW-KATSAUS: mallin hutit ovat osa tuotetta (25.8.2026).

Team Manager / FM-silmukka, vaihe 1. Villen paatos 26.7.
"""
from __future__ import annotations

from src.models import fpl_gw_review as R


def _picks(rivit):
    """rivit = [(element, multiplier, is_captain), ...]"""
    return {"picks": [{"element": e, "multiplier": m, "is_captain": c}
                      for e, m, c in rivit]}


INFO = {
    1: {"web_name": "Alpha", "team_short": "AAA", "pos": "MID"},
    2: {"web_name": "Beta", "team_short": "BBB", "pos": "FWD"},
    3: {"web_name": "Gamma", "team_short": "CCC", "pos": "DEF"},
}


# ---------------------------------------------------------------------------
# Kerroin molemmilla puolilla
# ---------------------------------------------------------------------------
def test_kapteeni_kerrotaan_molemmilla_puolilla():
    """🔴 Ilman kerrointa projektiossa kapteenin huti nayttaisi puolet
    todellisesta. B.Fernandes GW1: freeze 5,70 x2 = 11,40 ennustetta vastaan
    2 x2 = 4 pistetta."""
    out = R.build_review(1, _picks([(1, 2, True)]), {1: 5.70}, {1: 2}, INFO)
    r = out["review"]["captain"]
    assert r["projected"] == 11.40
    assert r["actual"] == 4
    assert r["diff"] == -7.40


def test_penkkilainen_ei_vaikuta_xi_summaan():
    """Kerroin 0 -> ei projektioon eika toteumaan, kuten FPL:n omissa
    kierrospisteissa."""
    out = R.build_review(1, _picks([(1, 1, False), (2, 0, False)]),
                         {1: 4.0, 2: 9.0}, {1: 6, 2: 12}, INFO)
    rv = out["review"]
    assert rv["projected"] == 4.0 and rv["actual"] == 6
    assert out["meta"]["players_compared"] == 2, "penkkilainen on yha rivi"


# ---------------------------------------------------------------------------
# Huti on yhta nakyva kuin osuma
# ---------------------------------------------------------------------------
def test_worst_call_on_payloadissa_yhta_nakyvasti():
    """🔴 Rehellisyys on kayttoliittyma, ei alaviite. Jos mallin huti ei nay
    tuotteessa, tuote valehtelee."""
    out = R.build_review(
        1, _picks([(1, 1, False), (2, 1, False), (3, 1, False)]),
        {1: 2.0, 2: 8.0, 3: 5.0}, {1: 9, 2: 1, 3: 5}, INFO)
    rv = out["review"]
    assert rv["best_call"]["web_name"] == "Alpha", "+7,0"
    assert rv["worst_call"]["web_name"] == "Beta", "-7,0"
    assert rv["best_call"]["diff"] == 7.0
    assert rv["worst_call"]["diff"] == -7.0


def test_paras_ja_huonoin_valitaan_XI_STA_kun_XI_on_olemassa():
    """Penkkilaisen huti ei ole kierroksen tarina: han ei kerannyt pisteita.
    Jos XI on olemassa, valinta tehdaan siita."""
    out = R.build_review(1, _picks([(1, 1, False), (2, 0, False)]),
                         {1: 4.0, 2: 20.0}, {1: 5, 2: 0}, INFO)
    # penkkilaisen "diff" olisi 0-0=0, XI:n +1 -> XI voittaa molemmat
    assert out["review"]["best_call"]["web_name"] == "Alpha"
    assert out["review"]["worst_call"]["web_name"] == "Alpha"


# ---------------------------------------------------------------------------
# Puuttuva data ei nollaudu
# ---------------------------------------------------------------------------
def test_pelaaja_ilman_freezea_tai_toteumaa_jatetaan_pois():
    """🔴 Toinen puoli yksin ei ole vertailu. Nollaksi tulkittuna pelaaja
    vaaristaisi seka summaa etta paras/huonoin-valintaa."""
    out = R.build_review(1, _picks([(1, 1, False), (2, 1, False)]),
                         {1: 4.0}, {1: 6, 2: 3}, INFO)   # 2 puuttuu freezesta
    assert out["meta"]["players_compared"] == 1
    assert out["review"]["projected"] == 4.0


def test_ei_vertailtavaa_ei_ole_saatavilla():
    out = R.build_review(1, _picks([(1, 1, False)]), {}, {}, INFO)
    assert out["meta"]["available"] is False
    assert out["meta"]["note_code"] == R.CODE_NOT_PLAYED
    assert out["review"] is None


def test_puuttuvat_argumentit_eivat_kaada():
    for args in ((None, None, None, None),
                 (1, None, {1: 1.0}, {1: 1}),
                 (1, _picks([(1, 1, False)]), None, {1: 1})):
        out = R.build_review(*args)
        assert out["meta"]["available"] is False
        assert out["flags"] == {"availability": [], "price": []}


# ---------------------------------------------------------------------------
# Liput seuraavaan kierrokseen
# ---------------------------------------------------------------------------
def test_saatavuuslippu_nostaa_vain_omat_pelaajat():
    info = dict(INFO)
    info[1] = {**INFO[1], "chance_next": 25, "news": "Knock - 25% chance"}
    info[3] = {**INFO[3], "chance_next": 50}
    out = R.build_review(1, _picks([(1, 1, False)]), {1: 4.0}, {1: 4}, info)
    liput = out["flags"]["availability"]
    assert [f["id"] for f in liput] == [1], "vain omistettu pelaaja"
    assert liput[0]["news"] == "Knock - 25% chance"


def test_taysi_saatavuus_ilman_uutista_ei_ole_lippu():
    info = {1: {**INFO[1], "chance_next": 100, "news": ""}}
    out = R.build_review(1, _picks([(1, 1, False)]), {1: 4.0}, {1: 4}, info)
    assert out["flags"]["availability"] == []


def test_uutinen_ilman_prosenttia_on_yha_lippu():
    """FPL kertoo osan huolista pelkkana uutistekstina ilman
    `chance_of_playing`ia. Se on silti lippu."""
    info = {1: {**INFO[1], "chance_next": None, "news": "Suspended"}}
    out = R.build_review(1, _picks([(1, 1, False)]), {1: 4.0}, {1: 4}, info)
    assert len(out["flags"]["availability"]) == 1


def test_hintalippu_vain_omista_pelaajista():
    pw = {"risers": [{"id": 1, "web_name": "Alpha", "progress_pct": 90.0},
                     {"id": 99, "web_name": "Muu", "progress_pct": 99.0}],
          "fallers": [{"id": 2, "web_name": "Beta", "progress_pct": 80.0}]}
    out = R.build_review(1, _picks([(1, 1, False), (2, 1, False)]),
                         {1: 4.0, 2: 4.0}, {1: 4, 2: 4}, INFO, pw)
    hinta = out["flags"]["price"]
    assert [h["id"] for h in hinta] == [1, 2], "99 ei ole omistettu"
    assert hinta[0]["direction"] == "rise"
    assert hinta[1]["direction"] == "fall"


def test_provisionaalinen_kierros_merkitaan():
    out = R.build_review(1, _picks([(1, 1, False)]), {1: 4.0}, {1: 4}, INFO,
                         None, [1])
    assert out["meta"]["provisional"] is True
    out2 = R.build_review(1, _picks([(1, 1, False)]), {1: 4.0}, {1: 4}, INFO,
                          None, [2])
    assert out2["meta"]["provisional"] is False
