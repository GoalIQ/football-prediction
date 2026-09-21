# -*- coding: utf-8 -*-
"""XP-OVERRIDE-OHITTAA-SAATAVUUDEN (21.9.2026, yöajo).

`set_p_start` (`src/models/fpl_xp.py`) korvasi aloitus-tn:n SUORAAN eikä
ajanut `apply_availability`a uudelleen. Ohitus korjaa vanhentuneen
minuuttihistorian ("viime kauden minuutit eivät kuvaa nykyistä roolia"), ei
pelaajan NYKYISTÄ FPL-saatavuutta — ne ovat kaksi eri kysymystä, ja ennen
tätä korjausta jälkimmäinen katosi kokonaan override-polulla. Julkaisuportin
oma teksti (`src/doubt_copy.py`, `/fpl` + `/fpl/team-news`) väittää
pelaamistodennäköisyyden olevan AINA mukana xP:ssä — override oli ainoa
polku jolla se ei pitänyt paikkaansa.

Ei laukea tuotannossa TÄNÄÄN (molemmat shipatut overridet ovat status `a`
maalivahteja, joten `apply_availability` on niille no-op) — vika syntyisi
vasta seuraavasta overridesta joka osuu epävarmaan pelaajaan.

Vaiheinvariantti (CLAUDE.md 6a-3): sama kysymys - "onko saatavuus mukana
ohituksen jälkeen" - mitataan jokaisessa FPL-statuksessa, ei vain
oletusarvossa `a`.
"""
from __future__ import annotations

import pytest

from src.models import fpl_xp as xp

MM = {
    "p_start_raw": 0.20, "p_start": 0.20, "p_sub": 0.10,
    "e_min_start": 80.0, "e_min_sub": 20.0,
    "p60_start": 0.9, "p60_sub": 0.1,
}


def test_negatiivinen_kontrolli_status_a_ei_skaalaa():
    """Molemmat shipatut overridet (maalivahdit) ovat tätä tapausta: ei
    regressiota niille. Todistaa että seuraavat testit mittaavat SKAALAUSTA,
    ei jotain `set_p_start`in muuta sivuvaikutusta."""
    out = xp.set_p_start(dict(MM), 0.90, "a", None)
    assert out["p_start"] == pytest.approx(0.90)
    assert out["p_start_raw"] == pytest.approx(0.90)


def test_status_d_skaalaa_chancella():
    """Tämä on rivi jota nykyinen (korjaamaton) koodi EI läpäise: ilman
    korjausta p_start jäisi 0.90:een riippumatta chancesta."""
    out = xp.set_p_start(dict(MM), 0.90, "d", 50)
    assert out["p_start"] == pytest.approx(0.90 * 0.5)
    assert out["p_start_raw"] == pytest.approx(0.90 * 0.5)


def test_status_d_ilman_chancea_kayttaa_apply_availabilityn_oletusta():
    """`apply_availability`in oma sopimus: `chance is None` status `d`:llä
    -> f=0.5 (sama fallback kuin muuallakin projektissa)."""
    out = xp.set_p_start(dict(MM), 0.80, "d", None)
    assert out["p_start"] == pytest.approx(0.80 * 0.5)


@pytest.mark.parametrize("status", ["i", "s", "u", "n"])
def test_ulkona_statukset_nollaavat_ohituksen(status):
    """Loukkaantunut/myyty/poissuljettu/ei-ehdolla: ohitusarvo EI SAA
    näkyä ollenkaan, vaikka CSV pyytäisi 0.90:tä - täsmälleen sama sääntö
    kuin `apply_availability`illa muualla mallissa."""
    out = xp.set_p_start(dict(MM), 0.90, status, None)
    assert out["p_start"] == pytest.approx(0.0)
    assert out["p_start_raw"] == pytest.approx(0.0)


def test_oletusargumentit_sailyttavat_vanhan_kutsumuodon():
    """Vanha kutsumuoto (kaksi argumenttia) toimii yhä identtisesti - tämä
    on tahallinen taaksepäinyhteensopivuus, ei aukko: `status` oletuu
    `a`:ksi eli 'ei tietoa -> oletetaan saatavilla', sama fail-open-oletus
    kuin `e.get("status", "a")` muualla `build_fpl_xp.py`:ssä."""
    old_style = xp.set_p_start(dict(MM), 0.90)
    new_style_explicit_a = xp.set_p_start(dict(MM), 0.90, "a", None)
    assert old_style == new_style_explicit_a
