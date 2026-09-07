# -*- coding: utf-8 -*-
"""Portti: "lopullinen" on todistettava, ei oletettava.

TAUSTA (7.9.2026, julkaisutarkistaja A1). `gw-review` ja `my-team-ledger`
lukivat provisional-lipun johdetusta artefaktista `meta.provisional_gws`.
Positiivinen lista + `or []` teki puuttuvasta tiedosta vaitteen: artefakti
oli 1.9:lta (GW1-2), ja GW3 sai payloadiin `provisional=false` vaikka FPL
sanoi `finished=False, data_checked=False`.

Testit alla mittaavat suunnan: epavarmuus saa vain LISAANTYA lukijassa.
"""
from __future__ import annotations

import re
from pathlib import Path

from src.models.fpl_gw_finality import (final_gws, is_provisional,
                                        provisional_gws)

ROOT = Path(__file__).resolve().parents[1]

EVENTS = [
    {"id": 1, "finished": True,  "data_checked": True},
    {"id": 2, "finished": True,  "data_checked": True},
    {"id": 3, "finished": False, "data_checked": False},
]


def test_valmis_kierros_ei_ole_provisionaalinen():
    assert provisional_gws(EVENTS, [1, 2]) == []
    assert is_provisional(EVENTS, 1) is False


def test_kesken_oleva_kierros_on_provisionaalinen():
    """Tasan se tapaus joka meni lapi: GW3 kesken, artefakti hiljaa."""
    assert provisional_gws(EVENTS, [3]) == [3]
    assert is_provisional(EVENTS, 3, artifact_gws=[]) is True


def test_tuntematon_kierros_on_provisionaalinen():
    """Fail-closed: kierrosta jota ei ole eventeissa ei voi julistaa
    lopulliseksi. Juuri "ei tietoa" kaantyi ennen vaitteeksi."""
    assert provisional_gws(EVENTS, [9]) == [9]
    assert is_provisional(EVENTS, 9) is True


def test_puuttuva_bootstrap_tekee_kaikesta_provisionaalista():
    assert provisional_gws(None, [1, 2, 3]) == [1, 2, 3]
    assert is_provisional(None, 1) is True


def test_finished_ilman_data_checkedia_ei_riita():
    """Bonukset ja BPS ratkeavat vasta `data_checked`illa, eli
    `finished=True, data_checked=False` on ikkuna jossa luku viela liikkuu."""
    ev = [{"id": 4, "finished": True, "data_checked": False}]
    assert provisional_gws(ev, [4]) == [4]
    assert final_gws(ev) == set()


def test_artefakti_voi_lisata_mutta_ei_poistaa_epavarmuutta():
    """SUUNTAPORTTI. Vanha lista saa yha merkita kierroksen kesken olevaksi,
    mutta se ei saa tehda kesken olevasta lopullista."""
    # lisaa: GW1 on FPL:n mukaan valmis, mutta grader epailee
    assert provisional_gws(EVENTS, [1], artifact_gws=[1]) == [1]
    # ei poista: GW3 on kesken, eika tyhja artefakti muuta sita
    assert provisional_gws(EVENTS, [3], artifact_gws=[]) == [3]


def test_rikkinaiset_arvot_eivat_kaada_eivatka_valu_lopullisiksi():
    ev = [{"id": "3", "finished": True, "data_checked": True},
          {"id": True, "finished": True, "data_checked": True},
          None]
    # "3" merkkijonona ei ole int -> GW3 ei ole todistetusti valmis
    assert provisional_gws(ev, [3]) == [3]
    assert provisional_gws(EVENTS, ["ei-luku"]) == []
    assert is_provisional(EVENTS, None) is True


def test_api_ei_lue_provisionaalia_pelkasta_artefaktista():
    """NEGATIIVINEN KONTROLLI KOODIPOLULLE.

    Ilman tata korjaus voisi valua takaisin: joku lisaa uuden pinnan joka
    lukee `meta.provisional_gws` suoraan ja asettaa sen lipuksi. Portti
    vaatii etta jokainen `provisional_gws`-luku api/main.py:ssa kulkee
    fail-closed-lukijan lapi.
    """
    s = (ROOT / "api" / "main.py").read_text(encoding="utf-8", errors="replace")
    luvut = len(re.findall(r'get\("provisional_gws"\)', s))
    lukijat = s.count("fpl_gw_finality import provisional_gws")
    assert luvut > 0, "portti ei loyda artefaktilukua lainkaan (mittaako se mitaan?)"
    assert lukijat >= luvut, (
        f"{luvut} artefaktilukua mutta vain {lukijat} fail-closed-lukijaa - "
        "jokin pinta asettaa lipun suoraan johdetusta listasta")
