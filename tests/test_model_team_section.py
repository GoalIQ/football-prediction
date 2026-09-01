# -*- coding: utf-8 -*-
"""Mallin oma FPL-rivi ilmaissivulla (1.9.2026).

MIKSI: julkaisutarkistaja mittasi fpl.html:sta 0 osumaa luvuille 41/50/108/79,
eli mallin kausisuoritus ei ollut MISSAAN sivulla - vain julkisessa
repo-tiedostossa, ilmaisessa API:ssa ja FPL:n omassa entryssa. Jokainen
kausisuoritusta koskeva postaus olisi siis linkannut sivulle jolla vaitetta ei
ole. Villen paatos 1.9: "ota github-linkki pois, tee verkkosivulle".

Nama testit vartioivat kolmea saantoa, jotka ovat koko syy miksi rivin voi
julkaista:
  1. tappio nakyy samassa taulukossa kuin voitto (rivi ei suodata)
  2. chip merkitaan (chip-kierros ei ole vertailukelpoinen)
  3. provisionaalinen kierros EI mene juoksevaan lukuun
"""
from __future__ import annotations


def _row(gw, points, average, provisional=False, chip=None):
    return {"gw": gw, "points": points, "fpl_average": average,
            "provisional": provisional, "active_chip": chip}


def _html(*rows):
    from scripts.build_fpl_page import model_team_html
    return model_team_html({"gameweeks": list(rows)})


def test_tyhja_loki_ei_renderoi_lohkoa():
    from scripts.build_fpl_page import model_team_html
    assert model_team_html(None) == ""
    assert model_team_html({"gameweeks": []}) == ""


def test_puuttuva_keskiarvo_ei_muutu_nollaksi():
    """Rivi jolta FPL:n keskiarvo puuttuu jatetaan pois. Nolla vaittaisi etta
    keskiarvo oli nolla (muisti: nolla-ei-ole-sama-kuin-ei-tietoa)."""
    h = _html(_row(1, 41, None), _row(2, 108, 79))
    assert "GW1" not in h and "GW2" in h


def test_tappio_ja_voitto_samassa_taulukossa_etumerkilla():
    h = _html(_row(1, 41, 50), _row(2, 108, 79, provisional=True,
                                    chip="wildcard"))
    assert "<td class=\"num\">41</td>" in h
    assert "<td class=\"num\">-9</td>" in h
    assert "<td class=\"num\">+29</td>" in h
    # Negatiivinen kontrolli: etumerkiton "29" ei riita, koska lukija ei nae
    # kummalle puolelle ero meni.
    assert ">29<" not in h


def test_chip_nakyy_lukijan_nimella():
    h = _html(_row(2, 108, 79, chip="wildcard"))
    assert "Wildcard" in h
    # Tuntematon koodi menee lapi raakana, keksitty nimi olisi pahempi.
    assert "Fantasy Chip" not in _html(_row(3, 60, 55, chip="mystery"))
    assert "mystery" in _html(_row(3, 60, 55, chip="mystery"))


def test_provisionaalinen_ei_mene_juoksevaan_lukuun():
    """🔴 Sama rehellisyyssaanto kuin build_gw_recap.py:ssa. GW1 -9 ja GW2 +29:
    jos provisionaalinen laskettaisiin mukaan, luku olisi +20. Testi kaatuu jos
    joku "korjaa" sen nayttamaan kauden kokonaisluvun."""
    h = _html(_row(1, 41, 50), _row(2, 108, 79, provisional=True))
    assert "GW1 is confirmed and the team is -9 against the average there." in h
    assert "GW2 is played but still provisional" in h
    assert "+20" not in h


def test_kaikki_provisionaalisia_ei_anna_kauden_lukua():
    h = _html(_row(1, 41, 50, provisional=True))
    assert "no season number to give" in h
    assert "-9" not in h.split("<table>")[0]


def test_kaksi_vahvistettua_kierrosta_summautuu():
    h = _html(_row(1, 41, 50), _row(2, 108, 79))
    assert ("Across the confirmed gameweeks, GW1 and GW2, the team is +20 "
            "against the average.") in h


def test_provisionaalinen_merkitaan_pistesolussa():
    h = _html(_row(2, 108, 79, provisional=True))
    assert "108 (provisional)" in h


def test_ankkuri_on_llms_txt_ssa():
    """Uusi lohko ilman llms.txt-rivia = GEO-sokea piste. Portti
    (check_llms_txt_sync) ajaa saman CI:ssa; tama kaatuu heti taalla."""
    import pathlib
    llms = (pathlib.Path(__file__).resolve().parents[1] / "llms.txt"
            ).read_text(encoding="utf-8")
    assert "goaliq.app/fpl#model-team" in llms
