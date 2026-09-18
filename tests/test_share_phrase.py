# -*- coding: utf-8 -*-
"""src/models/share_phrase.py: osuus -> lause on funktio, ei sanalista.

Katso moduulin docstring ja tests/test_minutes_claim_matches_source.py
(MINUUTTIPORTTI-TYYPILLINEN, 18.9.2026)."""
from __future__ import annotations

import pytest

from src.models.share_phrase import one_in_n_phrase, share_in_ten_phrase


def test_nykyinen_mittaus_tuottaa_nykyisen_lauseen():
    """Ankkuroi funktion tulos data/preseason_minutes_bias.json:n LUKUIHIN
    (0.413 ja 0.167), ei toisin päin — jos joku muuttaa funktiota niin että
    se ei enää tuota livekopion sanoja, tämä kaatuu ensin."""
    assert share_in_ten_phrase(0.413, "en") == "four in ten"
    assert share_in_ten_phrase(0.413, "es") == "cuatro de cada diez"
    assert share_in_ten_phrase(0.413, "pt") == "quatro em cada dez"
    assert one_in_n_phrase(0.167, "en") == "one in six"
    assert one_in_n_phrase(0.167, "es") == "uno de cada seis"
    assert one_in_n_phrase(0.167, "pt") == "um em cada seis"


def test_luku_muuttuu_lause_muuttuu():
    """Ydinominaisuus: lause on JOHDETTU luvusta, ei kiinteä sanalista.

    Jos mittaus muuttuisi (esim. seuraava kausi antaa share_within_5=0.61),
    funktion pitää heijastaa se — muuten portti voisi jäädä vihreäksi
    vanhalla sanamuodolla vaikka luku olisi muuttunut."""
    assert share_in_ten_phrase(0.61, "en") == "six in ten"
    assert share_in_ten_phrase(0.24, "en") == "two in ten"
    assert one_in_n_phrase(0.10, "en") == "one in ten"
    assert one_in_n_phrase(0.05, "en") == "one in twenty"


def test_pyoristys_rajat_eivat_karkaa_yli_kymmenen_tai_alle_yhden():
    """Negatiivinen kontrolli: syöte joka pyöristyisi 0:aan tai yli 10:een ei
    saa tuottaa merkityksetöntä lausetta ("zero in ten", "eleven in ten")."""
    assert share_in_ten_phrase(0.0, "en") == "one in ten"
    assert share_in_ten_phrase(1.0, "en") == "ten in ten"
    assert share_in_ten_phrase(0.999, "en") == "ten in ten"


def test_tuntematon_kieli_kaatuu_eika_vaikene():
    with pytest.raises(ValueError):
        share_in_ten_phrase(0.4, "fi")
    with pytest.raises(ValueError):
        one_in_n_phrase(0.1, "fi")


def test_nolla_osuus_ei_voi_olla_yksi_jostakin():
    """`one_in_n_phrase` jakaa 1/share — nolla kaataa sen sijaan että
    palauttaisi äärettömän tai väärän N:n."""
    with pytest.raises(ValueError):
        one_in_n_phrase(0.0, "en")
