"""FREEZE-VS-ENTRY-PORTTI: peritty runko on entryn runko, tai ei jaadyteta.

TAUSTA (4.9.2026, Villen loydos). Julkaisuun menossa ollut kortti sanoi
*"The model's own FPL squad, GW3 - entry 116920 - public on
fantasy.premierleague.com"* ja seitseman nimea yhdestatoista oli eri kuin
entryn oikeat pickit. `freeze_model_squad_gw._prev_freeze` perii rungon
EDELLISESTA FREEZESTA eika koskaan FPL:sta, joten ketju erosi entrysta
lopullisesti kun entry pelasi wildcardin GW2:ssa - eika mikaan huutanut,
koska jokainen portti verifioi luvut samasta vaarasta artefaktista.

DoD (jonorivi): portin ON kaadettava GW2:n oikea wildcard-tilanne
takautuvasti ajettuna. `test_gw2_wildcard_takautuvasti` ajaa tasan sen
mitatuilla id-joukoilla (7/15 yhteista).

Invariantti mitataan JOKAISESSA vaiheessa, ei vain nykyhetkessa: sama runko,
yksi siirto, wildcard, kauden ensimmainen kierros (ei pelattuja), verkko
alhaalla ja 404. Kolme viimeista ovat fail-closed-haaroja - niissa vastaus ei
saa olla "ei eroa" vaan "ei tiedeta".
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import freeze_model_squad_gw as freeze
from src.models import fpl_model_entry as entry_mod


# --- mitatut id-joukot 4.9.2026 (entry 116920, GW2) ------------------------
# gw2.json:n runko vs entryn GW2-pickit: 7/15 yhteista.
GW2_FREEZE_IDS = {
    # 8 nimea joita entryssa EI ollut (Anderson, Gomez, Lammens, Mykolenko,
    # Ndiaye, Steele, Thiago, Thiaw) + 7 yhteista.
    901, 902, 903, 904, 905, 906, 907, 908,
    101, 102, 103, 104, 105, 106, 107,
}
GW2_ENTRY_IDS = {
    4, 51, 171, 290, 427, 569, 572, 586,
    101, 102, 103, 104, 105, 106, 107,
}

EVENTS_GW2_PELATTU = [
    {"id": 1, "finished": True},
    {"id": 2, "finished": True},
    {"id": 3, "finished": False},
]
EVENTS_EI_PELATTUJA = [
    {"id": 1, "finished": False},
    {"id": 2, "finished": False},
]


def _runko(ids: set[int]) -> dict:
    """Freeze-tiedoston muoto: 11 + 4."""
    jarj = sorted(ids)
    def rivi(i):
        return {"id": i, "web_name": "P%d" % i}
    return {"xi": [rivi(i) for i in jarj[:11]],
            "bench": [rivi(i) for i in jarj[11:]]}


def _picks(ids: set[int]) -> list[dict]:
    return [{"element": i} for i in sorted(ids)]


def _hae(mapping: dict[int, set[int]]):
    """Fikstuurihakija: gw -> entryn pickit. Puuttuva gw = 404."""
    def hae(entry, gw):
        if gw not in mapping:
            raise entry_mod.EntryHakuVirhe("404 fikstuuri: ei GW%d-rivia" % gw)
        return _picks(mapping[gw])
    return hae


# --- 1. sama runko lapaisee -------------------------------------------------

def test_sama_runko_ei_estä():
    prev = _runko(GW2_ENTRY_IDS)
    virhe = freeze.entry_mismatch(
        2, prev, EVENTS_GW2_PELATTU, hae=_hae({2: GW2_ENTRY_IDS}))
    assert virhe is None


# --- 2. DoD: GW2:n wildcard takautuvasti ------------------------------------

def test_gw2_wildcard_takautuvasti():
    """Sama tilanne joka meni lapi 4.9 asti: 7/15 yhteista."""
    prev = _runko(GW2_FREEZE_IDS)
    virhe = freeze.entry_mismatch(
        2, prev, EVENTS_GW2_PELATTU, hae=_hae({2: GW2_ENTRY_IDS}))
    assert virhe is not None
    assert "EI OLE ENTRYN RUNKO" in virhe
    assert "7/15" in virhe


# --- 3. yksi siirto riittaa -------------------------------------------------

def test_yksi_siirto_estaa():
    """Ero ei tarvitse olla wildcard. Yksi vaihdettu pelaaja on jo eri
    joukkue, ja jaadytys on immutable."""
    entry_ids = set(GW2_ENTRY_IDS)
    prev_ids = (entry_ids - {4}) | {999}
    virhe = freeze.entry_mismatch(
        2, _runko(prev_ids), EVENTS_GW2_PELATTU, hae=_hae({2: entry_ids}))
    assert virhe is not None
    assert "14/15" in virhe


def test_seuranvaihdos_ei_ole_ero():
    """Pelaajan seuran vaihtuminen EI muuta id:ta - ketju ei saa kaatua
    siirtoikkunaan. (4.9: Guehi, Ndiaye ja Anderson siirtyivat Cityyn
    deadline-paivana ja aiheuttivat erillisen seurakattovian.)"""
    ids = set(GW2_ENTRY_IDS)
    virhe = freeze.entry_mismatch(
        2, _runko(ids), EVENTS_GW2_PELATTU, hae=_hae({2: ids}))
    assert virhe is None


# --- 4. fail-closed-haarat --------------------------------------------------

def test_verkkovirhe_on_fail_closed():
    def hae(entry, gw):
        raise entry_mod.EntryHakuVirhe("verkkovirhe: ConnectionError()")
    virhe = freeze.entry_mismatch(
        2, _runko(GW2_ENTRY_IDS), EVENTS_GW2_PELATTU, hae=hae)
    assert virhe is not None
    assert "fail-closed" in virhe
    assert "verkkovirhe" in virhe


def test_404_molemmista_on_fail_closed():
    virhe = freeze.entry_mismatch(
        2, _runko(GW2_ENTRY_IDS), EVENTS_GW2_PELATTU, hae=_hae({}))
    assert virhe is not None
    assert "fail-closed" in virhe


def test_404_perityssa_putoaa_viimeisimpaan_pelattuun():
    """Peritty kierros voi olla viela pelaamatta (404). Silloin vertailu
    tehdaan viimeisimpaan pelattuun - ei ohiteta."""
    kutsutut = []

    def hae(entry, gw):
        kutsutut.append(gw)
        if gw == 3:
            raise entry_mod.EntryHakuVirhe("404 fikstuuri")
        return _picks(GW2_ENTRY_IDS)

    virhe = freeze.entry_mismatch(
        3, _runko(GW2_ENTRY_IDS), EVENTS_GW2_PELATTU, hae=hae)
    assert kutsutut == [3, 2]
    assert virhe is None


def test_ei_pelattuja_kierroksia_sallitaan():
    """Kauden ensimmainen freeze: entrylla ei ole julkisia pickseja
    lainkaan, joten ketju ei ole viela voinut erota."""
    virhe = freeze.entry_mismatch(
        1, _runko(GW2_FREEZE_IDS), EVENTS_EI_PELATTUJA, hae=_hae({}))
    assert virhe is None


# --- 5. poikkeuslista EI vaimenna tata porttia ------------------------------

def test_poikkeustiedosto_ei_vaimenna_porttia(tmp_path, monkeypatch):
    """`data/model_squad_exceptions/gw2.json` tekee CI:sta vihrean
    `verify_model_entry_matches_freeze`ssa. Se EI saa antaa lupaa rakentaa
    uutta kausisitoumusta vaaran rungon paalle - juuri se poikkeus on syy
    miksi ketju erosi entrysta huomaamatta."""
    import scripts.verify_model_entry_matches_freeze as verify

    poikkeukset = tmp_path / "model_squad_exceptions"
    poikkeukset.mkdir()
    (poikkeukset / "gw2.json").write_text(
        '{"gw": 2, "reason": "wildcard", "decided_by": "Ville",'
        ' "decided_at": "2026-08-29"}', encoding="utf-8")
    monkeypatch.setattr(verify, "EXCEPTIONS_DIR", poikkeukset)
    # kontrolli: poikkeus on oikeasti voimassa verify-skriptille
    poikkeus, err = verify.load_exception(2)
    assert err is None and poikkeus is not None

    virhe = freeze.entry_mismatch(
        2, _runko(GW2_FREEZE_IDS), EVENTS_GW2_PELATTU,
        hae=_hae({2: GW2_ENTRY_IDS}))
    assert virhe is not None, "poikkeus vaimensi freeze-portin"


# --- 6. puhtaan vertailun omat kontrollit -----------------------------------

def test_vertaa_on_puhdas_ja_symmetrinen():
    ero = entry_mod.vertaa({1, 2, 3}, {2, 3, 4})
    assert ero.puuttuu == frozenset({1})
    assert ero.ylimaaraiset == frozenset({4})
    assert not ero.sama
    assert entry_mod.vertaa({1, 2}, {1, 2}).sama


def test_squad_ids_lukee_myos_penkin():
    """Vieras nimi voi olla kokonaan penkilla: pelkka XI ei riita."""
    runko = {"xi": [{"id": i} for i in range(1, 12)],
             "bench": [{"id": i} for i in (90, 91, 92, 93)]}
    assert entry_mod.squad_ids(runko) == set(range(1, 12)) | {90, 91, 92, 93}


def test_latest_played_gw_vaiheittain():
    """Invariantti mitataan jokaisessa vaiheessa (muisti: invariantti joka
    vaiheessa, ei nykyhetkessa)."""
    assert entry_mod.latest_played_gw([]) is None
    assert entry_mod.latest_played_gw(EVENTS_EI_PELATTUJA) is None
    assert entry_mod.latest_played_gw(EVENTS_GW2_PELATTU) == 2
    # kesken kierroksen: deadline mennyt muttei finished -> ei viela pelattu
    kesken = [{"id": 1, "finished": True}, {"id": 2, "finished": False}]
    assert entry_mod.latest_played_gw(kesken) == 1
    # kaksinumeroiset: max ei ole merkkijonovertailu
    iso = [{"id": 9, "finished": True}, {"id": 10, "finished": True}]
    assert entry_mod.latest_played_gw(iso) == 10


def test_kontrolli_fikstuuri_ei_ole_tyhja():
    """Testi joka vertaa tyhjaa tyhjaan lapaisee aina."""
    assert len(GW2_FREEZE_IDS) == 15
    assert len(GW2_ENTRY_IDS) == 15
    assert len(GW2_FREEZE_IDS & GW2_ENTRY_IDS) == 7


def test_negatiivinen_kontrolli_portti_kutsutaan_mainissa():
    """Portti joka on olemassa muttei kytketty on inertti."""
    lahde = Path(freeze.__file__).read_text(encoding="utf-8")
    assert "entry_mismatch(edellinen[0], edellinen[1], events)" in lahde
    # ...ja sen tulos johtaa paluuseen, ei pelkkaan tulostukseen
    i = lahde.index("_esto = entry_mismatch(")
    lohko = lahde[i:i + 200]
    assert "return 1" in lohko, lohko


@pytest.mark.parametrize("puuttuvat", [1, 5, 15])
def test_ero_kuvaus_nimeaa_pelaajat(puuttuvat):
    entry_ids = set(range(1, 16))
    prev_ids = set(range(1, 16 - puuttuvat)) | set(
        range(900, 900 + puuttuvat))
    ero = entry_mod.vertaa(prev_ids, entry_ids)
    teksti = ero.kuvaus({i: "P%d" % i for i in prev_ids})
    assert "rungossa mutta EI entryssa" in teksti
    assert "P900" in teksti
