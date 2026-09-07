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


# ---------------------------------------------------------------------------
# PORTIN 4. KIERROS (C9): `_ennen_deadlinea` ja `meta.fpl_points` elivat vain
# koodissa. Fikstuuri kirjoitetaan korjatusta tapauksesta.
# ---------------------------------------------------------------------------

def test_basis_vaite_on_johdettu_eika_ehdoton():
    """`meta.basis` sanoi EHDOTTOMASTI "frozen before the deadline" vaikka
    mikaan ei mitannut sita. Sama vaite kuin kortin `freezeNote()`, joten
    sama saanto: fail-closed, puuttuva aikaleima -> vaitetta ei tehda."""
    from src.models.fpl_gw_review import _ennen_deadlinea

    # Mitattu gw3-freeze: 12:16:41Z vs deadline 17:30:00Z.
    assert _ennen_deadlinea({"frozen_at": "2026-09-04T12:16:41Z",
                             "deadline": "2026-09-04T17:30:00Z"}) is True
    # Freeze deadlinen JALKEEN -> ei vaitetta.
    assert _ennen_deadlinea({"frozen_at": "2026-09-04T18:00:00Z",
                             "deadline": "2026-09-04T17:30:00Z"}) is False
    # Puuttuva, tyhja tai rikkinainen -> ei vaitetta (fail-closed).
    for fmeta in ({}, {"frozen_at": None, "deadline": None},
                  {"frozen_at": "roska", "deadline": "2026-09-04T17:30:00Z"},
                  {"frozen_at": "2026-09-04T12:16:41Z"}):
        assert _ennen_deadlinea(fmeta) is False, fmeta
    # Tasan sama hetki ei ole "ennen".
    assert _ennen_deadlinea({"frozen_at": "2026-09-04T17:30:00Z",
                             "deadline": "2026-09-04T17:30:00Z"}) is False


def test_review_meta_kantaa_fpl_oman_luvun():
    """C1/C2: FPL:n oma kierrospistemaara on payloadissa, jotta kortti voi
    sanoa sen sen sijaan etta se pehmentaisi omaa lukuaan."""
    from src.models.fpl_gw_review import build_review

    picks = {
        "entry_history": {"points": 58, "event_transfers_cost": 0},
        "active_chip": "3xc",
        "picks": [{"element": i, "multiplier": 1 if i <= 11 else 0,
                   "is_captain": False, "is_vice_captain": False}
                  for i in range(1, 16)],
    }
    frozen = {i: 6.0 for i in range(1, 16)}
    points = {i: 7 for i in range(1, 16)}
    info = {i: {"web_name": f"P{i}", "team_short": "ARS", "pos": "MID"}
            for i in range(1, 16)}
    out = build_review(3, picks, frozen, points, info)
    assert out["meta"]["fpl_points"] == 58
    assert out["meta"]["total_picks"] == 15
    assert out["meta"]["chip"] == "3xc"
    # C5: raaka summa kulkee erikseen, jotta lause ja rivi pyoristavat kerran.
    assert out["review"]["projected_raw"] == 66.0

    # Puuttuva luku ei saa muuttua nollaksi (nolla olisi vaite).
    picks_ilman = dict(picks, entry_history={})
    out2 = build_review(3, picks_ilman, frozen, points, info)
    assert out2["meta"]["fpl_points"] is None
