"""Portti: artefaktista tuleva kopiokentta ei saa olla ei-ASCII tai em dash.

Loydos 29.8.2026 (julkaisuportti, EO-BY-TIER): `meta.metric` pumpataan sivulle
sellaisenaan (`escape(metric)`), eika mikaan copy-portti katso sita, koska se ei
ole sivupohjassa vaan data-ajossa. Sama koskee `public_note`-kenttaa.

Negatiivinen kontrolli jokaiselle vaitteelle. Erikseen mitataan etta portti
PAASTAA lapi oikean englanninkielisen lauseen: portti joka kaataa kaiken olisi
yhta hyodyton kuin portti joka paastaa kaiken.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_fpl_page import gw_exception_notes
from scripts.public_text import assert_public_copy, public_copy_problems

ROOT = Path(__file__).resolve().parents[1]
EO_PATH = ROOT / "data" / "fpl_elite_ownership.json"


def test_kelvollinen_englanti_lapaisee():
    text = "Effective ownership counts a captaincy twice."
    assert public_copy_problems(text, "x") == []
    assert assert_public_copy(text, "x") == text


def test_em_dash_kaataa():
    problems = public_copy_problems("Ownership counts twice — that is why.", "x")
    assert any("em dash" in p for p in problems)


def test_suomi_kaataa():
    problems = public_copy_problems("Tehollinen omistus laskee kapteenin kahdesti äänestyksessa.", "x")
    assert any("ei-ASCII" in p for p in problems)


def test_rikkinainen_encoding_kaataa():
    # /fpl/stats naytti taman merkin livena 27.8 (osoittautui konsolivirheeksi,
    # mutta vikaluokka on aito: kirjoituspolun encoding).
    problems = public_copy_problems("2026/27 season to date � early season", "x")
    assert any("U+FFFD" in p for p in problems)


def test_kaarevat_lainausmerkit_kaatavat():
    assert public_copy_problems("the “top” ranks", "x")


def test_portin_raja_kirjattu_pelkka_ascii_suomi_menee_lapi():
    """Portin tunnettu raja: se mittaa MERKKEJA, ei kielta.

    "Kapteeni lasketaan kahdesti." on puhdasta ASCIIta ja menee lapi. Talle ei
    ole tassa portissa korjausta; kielivahti on eri portti. Raja on kirjattu
    testina, jotta seuraava lukija ei luule taman kattavan kielivirheita.
    """
    assert public_copy_problems("Kapteeni lasketaan kahdesti.", "x") == []


def test_tyhja_kentta_kelpaa():
    assert assert_public_copy(None, "x") == ""
    assert assert_public_copy("   ", "x") == ""


def test_assert_kaataa_buildin():
    with pytest.raises(ValueError):
        assert_public_copy("Kapteeni lasketaan kahdesti päivityksessa.", "meta.metric")


def test_oikea_eo_artefakti_lapaisee():
    meta = json.loads(EO_PATH.read_text(encoding="utf-8")).get("meta") or {}
    metric = meta.get("metric")
    assert metric, "EO-artefaktissa ei ole meta.metricia - kontrolli lapaisisi tyhjana"
    assert assert_public_copy(metric, "eo meta.metric") == str(metric).strip()


def test_oikeat_poikkeusnootit_lapaisevat():
    notes = gw_exception_notes()
    assert notes, "yhtaan poikkeusnoottia ei loytynyt - kontrolli lapaisisi tyhjana"
    for gw, note in notes.items():
        assert public_copy_problems(note, f"gw{gw}") == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
