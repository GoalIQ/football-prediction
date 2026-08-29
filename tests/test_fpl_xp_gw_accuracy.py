# -*- coding: utf-8 -*-
"""IDEA-2026-08-29-xp-graded-public: per-GW xP-gradaus luokittain + vertailu
FPL:n ep_next:iin ja form-baselineen, ja sen julkinen osio fpl-sivulla.

Kaikki testit ovat puhdasta logiikkaa (ei verkkoa, ei levya): freeze-rivit
ja toteuma syotetaan kasin. Mutaatiokontrollit varmistavat etta testi
mittaa sita mita sen kuuluu: vaara luokkaraja tai ep_next-puute-nolla
kaataa testin, ei mene lapi hiljaa.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import fpl_xp_accuracy as xacc  # noqa: E402
from src.models.fpl_xp_accuracy import (  # noqa: E402
    CLASS_BLANK, CLASS_DNP, CLASS_HAUL, CLASS_TICKER, PRED_EP_NEXT, PRED_FORM,
    PRED_GOALIQ, classify_outcome, grade_players, mae, pool_groups)


# ---------------------------------------------------------------------------
# MAE tunnetulla syotteella
# ---------------------------------------------------------------------------
def test_mae_tunnettu_syote():
    assert mae([2.0, 4.0, 6.0], [3.0, 2.0, 6.0]) == pytest.approx(1.0)
    assert mae([], []) is None
    assert mae([1.0], [1.0, 2.0]) is None   # eripituiset eivat ole "0 virhetta"


# ---------------------------------------------------------------------------
# Luokittelun rajat 2/3/9/10 ja DNP minuuteista
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("pts,mins,cls", [
    (0, 0, CLASS_DNP),
    (6, 0, CLASS_DNP),      # 0 min on DNP vaikka pisteita olisi (data-anomalia)
    (0, 1, CLASS_BLANK),
    (2, 90, CLASS_BLANK),   # ylaraja 2
    (3, 90, CLASS_TICKER),  # alaraja 3
    (9, 90, CLASS_TICKER),  # ylaraja 9
    (10, 90, CLASS_HAUL),   # alaraja 10
    (-1, 60, CLASS_BLANK),  # negatiivinen (punainen kortti) on blank
    (5, None, CLASS_DNP),   # ei minuuttitietoa -> ei voi vaittaa pelanneeksi
])
def test_luokittelun_rajat(pts, mins, cls):
    assert classify_outcome(pts, mins) == cls


def test_mutaatiokontrolli_vaara_luokkaraja_kaataa(monkeypatch):
    """Jos joku siirtaa blank-rajan 3:een, rajatesti 3 -> ticker kaatuu."""
    monkeypatch.setattr(xacc, "BLANK_MAX_PTS", 3)
    assert classify_outcome(3, 90) != CLASS_TICKER
    monkeypatch.setattr(xacc, "BLANK_MAX_PTS", 2)
    monkeypatch.setattr(xacc, "TICKER_MAX_PTS", 10)
    assert classify_outcome(10, 90) != CLASS_HAUL


# ---------------------------------------------------------------------------
# grade_players: GoalIQ kaikilla riveilla, vertailu vain taysilla riveilla
# ---------------------------------------------------------------------------
def _p(pid, xp, ep=None, form=None, pos="MID"):
    d = {"id": pid, "web_name": f"P{pid}", "pos": pos, "xp": xp}
    if ep is not None:
        d["ep_next"] = ep
    if form is not None:
        d["form"] = form
    return d


def test_grade_players_luvut_ja_luokat():
    players = [
        _p(1, 4.0, ep=3.0, form=2.0),          # 10 p, 90 min  -> haul
        _p(2, 3.0, ep=3.5, form=4.0),          # 2 p, 60 min   -> blank
        _p(3, 2.0, ep=1.0, form=1.0, pos="DEF"),   # 0 p, 0 min -> dnp
        _p(4, 5.0, ep=6.0, form=5.0, pos="DEF"),   # 6 p, 90 min -> ticker
    ]
    actual = {1: (10, 90), 2: (2, 60), 3: (0, 0), 4: (6, 90)}
    g = grade_players(players, actual)
    assert g["n"] == 4
    # |10-4| + |2-3| + |0-2| + |6-5| = 6+1+2+1 = 10 -> 2.5
    assert g["mae"] == pytest.approx(2.5)
    assert g["by_class"][CLASS_HAUL]["n"] == 1
    assert g["by_class"][CLASS_HAUL]["mae"] == pytest.approx(6.0)
    assert g["by_class"][CLASS_BLANK]["n"] == 1
    assert g["by_class"][CLASS_DNP]["n"] == 1
    assert g["by_class"][CLASS_DNP]["mae"] == pytest.approx(2.0)
    assert g["by_class"][CLASS_TICKER]["n"] == 1
    assert g["mae_by_pos"] == {"DEF": pytest.approx(1.5), "MID": pytest.approx(3.5)}
    assert g["by_pos_stats"]["DEF"] == {"n": 2, "mae": pytest.approx(1.5), "bias": pytest.approx(-0.5)}
    cmp_ = g["comparison"]
    assert cmp_["n"] == 4
    assert cmp_["mae"][PRED_GOALIQ] == pytest.approx(2.5)
    # ep: |10-3| + |2-3.5| + |0-1| + |6-6| = 7+1.5+1+0 = 9.5 -> 2.375
    assert cmp_["mae"][PRED_EP_NEXT] == pytest.approx(2.375)
    # form: |10-2| + |2-4| + |0-1| + |6-5| = 8+2+1+1 = 12 -> 3.0
    assert cmp_["mae"][PRED_FORM] == pytest.approx(3.0)
    assert cmp_["by_pos"]["DEF"]["n"] == 2
    assert cmp_["by_class"][CLASS_HAUL]["mae"][PRED_EP_NEXT] == pytest.approx(7.0)


def test_ep_next_puuttuu_rivi_ohitetaan_ei_nolla():
    """Rivi ilman ep_next:ia ei ole 'FPL ennusti 0' vaan poissa vertailusta.
    GoalIQ:n oma MAE lasketaan silti kaikilla riveilla."""
    players = [
        _p(1, 4.0, ep=3.0, form=2.0),   # taysi rivi
        _p(2, 3.0, form=4.0),           # ep_next puuttuu
        _p(3, 2.0, ep=1.0),             # form puuttuu
    ]
    actual = {1: (10, 90), 2: (2, 60), 3: (0, 0)}
    g = grade_players(players, actual)
    assert g["n"] == 3
    cmp_ = g["comparison"]
    assert cmp_["n"] == 1
    assert cmp_["mae"][PRED_EP_NEXT] == pytest.approx(7.0)
    # Mutaatiokontrolli: jos puuttuva ep_next olisi 0, n olisi 3 ja MAE
    # ep_next:lle (7 + 2 + 0)/3 = 3.0 -> eri luku kuin 7.0.
    assert cmp_["mae"][PRED_EP_NEXT] != pytest.approx(3.0)


def test_ilman_ep_nextia_vertailu_on_none_eika_nollarivi():
    """GW1/GW2-tyyppinen freeze: ei ep_next-kenttaa lainkaan."""
    g = grade_players([_p(1, 4.0), _p(2, 1.0)], {1: (5, 90), 2: (0, 0)})
    assert g["n"] == 2
    assert g["comparison"] is None
    assert g["by_class"][CLASS_DNP]["n"] == 1


def test_puuttuva_toteuma_on_dnp_nolla_pistetta():
    """Pelaaja jota ei ole live-datassa (siirtynyt) on aito DNP-miss."""
    g = grade_players([_p(9, 3.0, ep=2.0, form=1.0)], {})
    assert g["by_class"][CLASS_DNP]["n"] == 1
    assert g["mae"] == pytest.approx(3.0)


def test_ep_next_merkkijonona_kelpaa():
    """FPL antaa ep_next/form merkkijonoina; freeze normalisoi mutta gradaus
    ei saa kaatua jos vanha freeze sisaltaa merkkijonon."""
    g = grade_players([_p(1, 4.0, ep="3.5", form="2.0")], {1: (4, 90)})
    assert g["comparison"]["n"] == 1
    assert g["comparison"]["mae"][PRED_EP_NEXT] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Poolaus: n-painotettu MAE on tarkalleen yhdistetyn joukon MAE
# ---------------------------------------------------------------------------
def test_pool_groups_n_painotettu():
    a = {"n": 2, "mae": {"goaliq": 1.0, "fpl_ep_next": 2.0}}
    b = {"n": 6, "mae": {"goaliq": 3.0, "fpl_ep_next": 2.0}}
    out = pool_groups([a, b, None, {"n": 0, "mae": None}])
    assert out["n"] == 8
    assert out["mae"]["goaliq"] == pytest.approx(2.5)   # (2*1 + 6*3)/8, EI 2.0
    assert out["mae"]["fpl_ep_next"] == pytest.approx(2.0)
    assert pool_groups([]) is None
    assert pool_groups([{"n": 3, "mae": 1.5}])["mae"] == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# Freeze: ep_next + form samasta bootstrapista, puuttuva -> None
# ---------------------------------------------------------------------------
def test_freeze_slim_rows_kantaa_ep_next_ja_formin():
    from scripts.freeze_fpl_xp_gw import fpl_reference_by_id, slim_rows
    boot = {"elements": [
        {"id": 1, "ep_next": "4.5", "form": "3.2"},
        {"id": 2, "ep_next": "", "form": None},
    ]}
    xp = {"players": [
        {"id": 1, "web_name": "A", "pos": "MID", "gameweeks": [{"gw": 3, "xp": 5.0}]},
        {"id": 2, "web_name": "B", "pos": "DEF", "gameweeks": [{"gw": 3, "xp": 2.0}]},
        {"id": 3, "web_name": "C", "pos": "FWD", "gameweeks": [{"gw": 3, "xp": 1.0}]},
    ]}
    ref = fpl_reference_by_id(boot)
    rows = slim_rows(xp, 3, ref)
    by_id = {r["id"]: r for r in rows}
    assert by_id[1]["ep_next"] == pytest.approx(4.5)
    assert by_id[1]["form"] == pytest.approx(3.2)
    assert by_id[2]["ep_next"] is None and by_id[2]["form"] is None
    assert by_id[3]["ep_next"] is None      # ei bootstrapissa -> None, ei 0
    # Vanha kutsu ilman refia: kenttia ei ole (ei None-arvoa joka nayttaisi
    # silta kuin ep_next olisi yritetty tallentaa).
    assert "ep_next" not in slim_rows(xp, 3)[0]


def test_grade_script_actual_from_live_ja_enrich():
    from scripts.grade_fpl_xp_gw import actual_from_live, enrich_row, needs_enrich
    live = {"elements": [{"id": 1, "stats": {"total_points": 7, "minutes": 80}},
                         {"id": 2, "stats": {"total_points": 0, "minutes": 0}}]}
    actual = actual_from_live(live)
    assert actual == {1: (7.0, 80.0), 2: (0.0, 0.0)}
    old_row = {"gw": 1, "n": 2, "mae": 1.5, "bias": 0.5, "mae_by_pos": {"MID": 1.5}}
    assert needs_enrich(old_row)
    frozen = {"players": [_p(1, 5.0), _p(2, 3.0)]}
    enrich_row(old_row, frozen, actual)
    assert not needs_enrich(old_row)
    # Vanhat luvut eivat muutu vaikka ne olisivat eri kuin uudelleenlaskettu
    # (append-only): vain uudet avaimet lisataan.
    assert old_row["mae"] == 1.5 and old_row["n"] == 2
    assert old_row["by_class"][CLASS_DNP]["n"] == 1
    assert old_row["comparison"] is None
    assert "enriched_at" in old_row


# ---------------------------------------------------------------------------
# Sivun osio
# ---------------------------------------------------------------------------
def _gw_row(gw, n, m, cmp_=None):
    return {"gw": gw, "n": n, "mae": m, "bias": 0.1,
            "mae_by_pos": {"MID": m},
            "by_pos_stats": {"MID": {"n": n, "mae": m, "bias": 0.0}},
            "by_class": {c: {"n": 1, "mae": m, "bias": 0.0} for c in xacc.CLASSES},
            "comparison": cmp_}


def _cmp(n, g, e, f):
    trip = {PRED_GOALIQ: g, PRED_EP_NEXT: e, PRED_FORM: f}
    return {"n": n, "predictors": list(xacc.PREDICTORS), "mae": dict(trip),
            "by_class": {c: {"n": 1, "mae": dict(trip)} for c in xacc.CLASSES},
            "by_pos": {"MID": {"n": n, "mae": dict(trip)}}}


def test_osio_ei_renderoidy_tyhjalla_datalla():
    from scripts.build_fpl_page import xp_accuracy_html
    assert xp_accuracy_html(None) == ""
    assert xp_accuracy_html({}) == ""
    assert xp_accuracy_html({"gameweeks": []}) == ""
    # Rivi ilman MAE:ta (gradaus epaonnistui) ei ole julkaistava rivi.
    assert xp_accuracy_html({"gameweeks": [{"gw": 1, "n": 0, "mae": None}]}) == ""


def test_osio_ilman_vertailua_ei_lupaa_fpl_vertailua_ollenkaan():
    """Julkaisuportti 29.8 k2: ilman yhtaan vertailukierrosta osio EI saa
    nayttaa FPL-sarakkeita, kuvailla niita kappaleessa 1 eika selittaa
    'not frozen' -solua alaviitteessa. Vanha versio naytti 24 solua joissa
    luki 'not frozen' ja 34 sanaa vertailusta jota lukija ei paassyt
    tarkistamaan mistaan (GW1/GW2 jaadytettiin ilman ep_next-kenttaa)."""
    from scripts.build_fpl_page import xp_accuracy_html
    html = xp_accuracy_html({"gameweeks": [_gw_row(1, 490, 1.757)]})
    assert 'id="xp-accuracy"' in html
    assert "GW1" in html and "1.76" in html
    assert "0.00" not in html
    # Kolme osaa liikkuvat YHDESSA: sarake, P1-lause, alaviite.
    assert "not frozen" not in html
    assert "ep_next" not in html
    assert "FPL form" not in html
    # Positio nakyy myos ilman vertailua (GoalIQ-sarake, n mukana).
    assert "<td>MID</td>" in html
    assert 'Did not play (0 minutes)</td><td class="num">1</td>' in html
    # Sarakkeita on tasan kolme: rivilla ei saa jaada tyhjia soluja.
    assert html.count('<th scope="col"') == 6   # 3 + 3, kaksi taulukkoa


def test_fpl_sarake_prosa_ja_alaviite_liikkuvat_yhdessa():
    """Negatiivinen kontrolli portille: jos joku myohemmin nayttaa sarakkeet
    mutta unohtaa lauseen (tai painvastoin), tama kaatuu. Ilman tata testi
    lapaisisi myos version jossa alaviite selittaa 'not frozen' -solua jota
    ei ole yhtaan."""
    from scripts.build_fpl_page import xp_accuracy_html
    for log, want in (
            ({"gameweeks": [_gw_row(1, 490, 1.757)]}, False),
            ({"gameweeks": [_gw_row(3, 500, 1.9, _cmp(480, 1.85, 1.95, 2.3))]},
             True)):
        html = xp_accuracy_html(log)
        col = "FPL ep_next</th>" in html
        prose = "the ep_next field" in html
        note = "A cell reads not frozen" in html
        assert col == prose == note == want, (col, prose, note, want)


def test_blank_label_ei_ala_sanalla_blank():
    """Sama sivu kayttaa sanaa Blank ilmaisen xP-sivun merkityksessa
    (DIST_BLANK_PTS = 2, esiintyminen TAI ei mitaan -> sisaltaa DNP:t).
    Tama luokka on eri nimittaja (vain pelanneet), joten se ei saa alkaa
    samalla sanalla."""
    from src.models.fpl_xp_accuracy import CLASS_BLANK, CLASS_LABELS
    label = CLASS_LABELS[CLASS_BLANK]
    assert not label.lower().startswith("blank"), label
    assert "played" in label.lower()


def test_dnp_vaitetta_ei_renderoida_ollenkaan():
    """Portti k4: osio EI saa vaittaa etta pelaamaton sai 0 pistetta eika
    nimeta DNP-rivin lukua "naiden pelaajien keskimaaraiseksi projektioksi".

    Vaite oli aiemmin ehdollistettu vahdilla mae == -bias. Vahti oli
    TAUTOLOGIA: jaadytetty xp on aina >= 0 ja 0 minuuttia pelanneen pisteet
    aina <= 0, joten kaikki virheet ovat samansuuntaisia joka datajoukolla ja
    vahti palautti aina True. Alla toistettu vastaesimerkki mallin omalla
    gradaajalla: kortin saanut pelaamaton lapaisi vahdin, mutta rivin MAE
    (2.333) ei ollut keskiprojektio (2.0). Lause oli lisaksi osion ainoa
    kohta jota lukija ei voi tarkistaa kummastakaan linkatusta tiedostosta."""
    from scripts.build_fpl_page import xp_accuracy_html
    from src.models import fpl_xp_accuracy as x
    g = x.grade_players(
        [{"id": 1, "pos": "MID", "xp": 2.0}, {"id": 2, "pos": "MID", "xp": 2.0},
         {"id": 3, "pos": "MID", "xp": 2.0}],
        {1: (0.0, 0.0), 2: (0.0, 0.0), 3: (-1.0, 0.0)})
    dnp = g["by_class"][x.CLASS_DNP]
    assert dnp["mae"] == -dnp["bias"]      # vanha vahti olisi paastanyt lapi
    assert dnp["mae"] != 2.0               # mutta vaite olisi ollut epatosi
    for log in ({"gameweeks": [_gw_row(1, 490, 1.757)]},
                {"gameweeks": [_gw_row(1, 490, 1.757),
                               _gw_row(3, 500, 1.9, _cmp(480, 1.85, 1.95, 2.3))]}):
        html = xp_accuracy_html(log)
        assert "scored 0" not in html
        assert "average projection" not in html
        assert "carried into the deadline" not in html
        # Luokkanimi kantaa asian ilman vaitetta.
        assert "Did not play (0 minutes)" in html


def test_p1_ei_ole_ristiriidassa_poissulkulauseen_kanssa():
    """P1 sanoi "Every player the model projects sits in that file", kun
    alaviite sanoo etta malli projisoi luvun myos niille jotka EIVAT ole
    tiedostossa (alle 1.0 p kuudella GW:lla). Kaksi vastakkaista vaitetta
    samassa osiossa. Nyt P1 puhuu projektiosta artefaktina."""
    from scripts.build_fpl_page import xp_accuracy_html
    html = xp_accuracy_html({"gameweeks": [_gw_row(1, 490, 1.757)]})
    assert "Every player the model projects" not in html
    assert "Every player in the projection is in there" in html
    # "that file" ei saa esiintya ennen kuin tiedosto on nimetty.
    assert "locked into a file" in html


def test_vertailun_alkukierros_luetaan_datasta_ei_kovakoodata():
    """"the gameweek 3 freeze" oli kovakoodattu. Jos ensimmainen vertailurivi
    onkin GW4 (GW3:n freeze ei saanut ep_next:ia), kovakoodattu luku olisi
    epatosi juuri silla hetkella kun se ilmestyy."""
    from scripts.build_fpl_page import xp_accuracy_html
    html = xp_accuracy_html({"gameweeks": [
        _gw_row(1, 490, 1.757),
        _gw_row(4, 500, 1.9, _cmp(480, 1.85, 1.95, 2.3))]})
    assert "start with the gameweek 4 freeze" in html
    assert "gameweek 3 freeze" not in html


def test_osio_vertailulla_nayttaa_kolme_saraketta_samalla_n():
    from scripts.build_fpl_page import xp_accuracy_html
    log = {"gameweeks": [
        _gw_row(1, 490, 1.757),
        _gw_row(3, 500, 1.9, _cmp(480, 1.85, 1.95, 2.3)),
    ]}
    html = xp_accuracy_html(log)
    # GW3-rivi: vertailun n (480) ja kolme lukua, ei kokonais-n:aa (500)
    assert '<td class="num">GW3</td><td class="num">480</td>' in html
    assert "1.85" in html and "1.95" in html and "2.30" in html
    assert "GW1" in html
    assert "fpl_xp_gw_accuracy.json" in html
    # Poolattu positiorivi vain vertailukierroksilta: n=480, ei 480+490.
    assert '<td>MID</td><td class="num">480</td>' in html
    # Ei vertailuvaitetta: luvut puhuvat, teksti ei.
    low = html.lower()
    for banned in ("beats fpl", "better than fpl", "more accurate than",
                   "outperform", "odds", "solver", " pro "):
        assert banned not in low, banned


def test_osio_ei_em_dashia():
    from scripts.build_fpl_page import xp_accuracy_html
    html = xp_accuracy_html({"gameweeks": [_gw_row(2, 500, 2.0, _cmp(10, 1, 2, 3))]})
    assert "—" not in html
