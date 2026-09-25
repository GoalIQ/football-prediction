# -*- coding: utf-8 -*-
"""/fpl/minutes-accuracy: bias-lause johdetaan taulukon riveista (25.9.2026).

MINACC-JA-NOTE-COPY-SYNCIIN. Sivu sanoi kasin kirjoitettuna "close to unbiased
for players who got on the pitch at all, and the whole overshoot sits with the
players who never appeared". Saman taulukon rivi "We expected 60+ and they
played" nayttaa +9,4, eli aloittajiksi arvioidut jotka pelasivat jaivat
9,4 min arviosta. Lukija nakee molemmat ja ne ovat ristiriidassa.

Portit:
1. vanha vaite ei voi palata (mutaatio: palauta kasin kirjoitettu lause)
2. jokainen lauseen luku on taulukon rivilla (sama artefakti)
3. vaiheinvariantti: aloittajien harha nimetaan vain kun data kantaa, ja
   "close to even" vain kun pelanneiden harha on pieni
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import build_fpl_longtail as lt

ROOT = Path(__file__).resolve().parents[1]
DOC = json.loads((ROOT / "data" / "fpl_minutes_validation.json").read_text(encoding="utf-8"))
NYT = datetime(2026, 9, 25, tzinfo=timezone.utc)


def _sivu(doc=DOC) -> str:
    html = lt.render_minutes_accuracy(doc, NYT)
    assert html, "sivu ei renderoitynyt"
    return html


def _rivi(doc, avain):
    return next(r for r in doc["slices_prior_only"] if r["slice"] == avain)


def test_vanha_vaite_ei_palaa():
    assert "whole overshoot sits with the players who never appeared" not in _sivu()


def test_lauseen_luvut_ovat_taulukon_riveilla():
    lause = lt.minacc_bias_lause(DOC)
    for avain in ("played >=1 min in GW1-6", "no minutes at all"):
        assert f"{_rivi(DOC, avain)['bias']:+.1f}" in lause, avain
    aloittajat = _rivi(DOC, "prior >=60 AND played")["bias"]
    assert f"{aloittajat:.1f} minutes under our estimate" in lause
    # ja sama luku nakyy sivun taulukossa
    assert f"{aloittajat:+.1f}" in _sivu()


def test_80_rivilla_on_nimike():
    assert "prior &gt;=80" not in _sivu() and "prior >=80" not in _sivu()
    assert "We expected 80+ and they played" in _sivu()


@pytest.mark.parametrize("aloittaja_bias,nimetaan", [(9.4, True), (5.0, True), (4.9, False), (1.0, False)])
def test_aloittajien_harha_nimetaan_vain_kun_data_kantaa(aloittaja_bias, nimetaan):
    d = copy.deepcopy(DOC)
    _rivi(d, "prior >=60 AND played")["bias"] = aloittaja_bias
    assert ("under our estimate" in lt.minacc_bias_lause(d)) is nimetaan


@pytest.mark.parametrize("pelasi_bias,tasan", [(-1.8, True), (2.9, True), (3.0, False), (-6.0, False)])
def test_close_to_even_vain_pienella_harhalla(pelasi_bias, tasan):
    d = copy.deepcopy(DOC)
    _rivi(d, "played >=1 min in GW1-6")["bias"] = pelasi_bias
    assert ("close to even" in lt.minacc_bias_lause(d)) is tasan


def test_puuttuvat_rivit_eivat_keksi_vaitetta():
    d = copy.deepcopy(DOC)
    d["slices_prior_only"] = [r for r in d["slices_prior_only"] if r["slice"] == "all"]
    assert lt.minacc_bias_lause(d) == "Bias is how far we were above what happened."


def test_nootin_luvut_loytyvat_tarkistussivulta():
    """Nootti 'We measured our own worst column' lahettaa lukijan
    /fpl/minutes-accuracy -sivulle (check_url). test_fpl_notes tarkistaa claims-
    listan vain nootin OMAA tekstia vasten; lukija tarkistaa ne kuitenkin tasta
    sivusta. Jos artefakti muuttuu, nootti on stale ja tama kaatuu."""
    notes = json.loads((ROOT / "data" / "fpl_notes.json").read_text(encoding="utf-8"))
    n = next(x for x in notes["notes"] if x["slug"] == "we-measured-our-own-worst-column")
    assert n["check_url"].endswith("/fpl/minutes-accuracy")
    sivu = _sivu()
    puuttuu = [c for c in n["claims"] if c not in sivu]
    assert not puuttuu, f"nootin luvut joita tarkistussivulla ei ole: {puuttuu}"


def test_nootin_luvut_ovat_artefaktin_kentat():
    """Lasnaolo sivulla ei erottele (9.4 on sivulla kahdesti: leikkaus- ja
    fold-taulukossa). Siksi jokainen claim sidotaan artefaktin kenttaan.
    MUTAATIO: muuta artefaktin 60+-pelanneiden bias -> punainen."""
    notes = json.loads((ROOT / "data" / "fpl_notes.json").read_text(encoding="utf-8"))
    n = next(x for x in notes["notes"] if x["slug"] == "we-measured-our-own-worst-column")
    odotus = {
        "415": str(DOC["population"]),
        "303": str(_rivi(DOC, "played >=1 min in GW1-6")["n"]),
        "112": str(_rivi(DOC, "no minutes at all")["n"]),
        "20.7": f"{_rivi(DOC, 'no minutes at all')['bias']:.1f}",
        "9.4": f"{_rivi(DOC, 'prior >=60 AND played')['bias']:.1f}",
        "21.8": f"{_rivi(DOC, 'played >=1 min in GW1-6')['mae']:.1f}",
    }
    assert sorted(n["claims"]) == sorted(odotus), "claims-lista muuttui: paivita sidonta"
    vaarat = {c: v for c, v in odotus.items() if c != v}
    assert not vaarat, f"nootti vs artefakti: {vaarat}"


@pytest.mark.parametrize("pelasi_bias,vastakohta", [(-1.8, True), (6.0, False)])
def test_vastakohta_vain_kun_edellinen_lause_sanoo_tasan(pelasi_bias, vastakohta):
    """Julkaisutarkistaja 25.9: 'Starters are different.' ilman 'close to even'
    -lausetta ennen sita ei vastaa mihinkaan."""
    d = copy.deepcopy(DOC)
    _rivi(d, "played >=1 min in GW1-6")["bias"] = pelasi_bias
    lause = lt.minacc_bias_lause(d)
    assert ("Starters are different." in lause) is vastakohta
    assert "under our estimate" in lause
