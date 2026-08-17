"""Lukujen kateportti: virkkeen jokainen luku on loydyttava faktalohkosta.

17.8: nama testit asuivat `tests/test_fpl_why.py`:ssa, joka poistettiin
maksullisen tekstirajapinnan mukana. Portti itse EI poistunut - sita kayttaa
`scripts/build_gw_digest.py` - joten testit siirrettiin tanne. Ilman tata
siirtoa elava portti olisi jaanyt ilman kattavuutta, ja sen kaikki kolme
tapausta ovat loytyneita bugeja eivatka kuviteltuja.

Faktalohko on tassa kirjoitettu kasin (aiemmin se tuli poistetun moduulin
`player_facts`-funktiosta). Portti ei valita mista dict tulee, ja kasin
kirjoitettu lohko tekee testista luettavan ilman tuotantodataa.
"""
from __future__ import annotations

import pytest

from src.models.number_grounding import (
    UNIT_NUMBERS,
    allowed_numbers,
    ungrounded_numbers,
)


@pytest.fixture
def facts() -> dict:
    return {
        "name": "B.Fernandes",
        "xp_this_gw": 5.8,
        "expected_minutes": 84,
        "start_probability_pct": 86,
        "last_season": {"goals": 9, "assists": 8},
        "per_90": {"xg": 0.68, "xa": 0.7},
        "next_opponents": ["HUL (A)", "IPS (H)"],
    }


def test_trailing_zero_stripping_does_not_leak_whole_numbers(facts):
    """LOYTYNYT BUGI: token '90' -> rstrip('0') -> '9', ja 9 oli faktoissa
    (viime kauden maalit) -> pohjaton luku lapaisi portin. Nollien karsinta
    kuuluu VAIN desimaaliosaan."""
    assert facts["last_season"]["goals"] == 9
    assert "90" not in allowed_numbers(facts)
    assert ungrounded_numbers("He made 900 passes.", facts) == ["900"]
    # Desimaalimuoto lapaisee yha: 0.7 == 0.70.
    assert ungrounded_numbers("0.70 assists per 90.", facts) == []


def test_per_90_is_the_only_unit_exemption(facts):
    assert UNIT_NUMBERS == {"90"}
    assert ungrounded_numbers("0.68 per 90.", facts) == []
    # Negatiivinen kontrolli: mikaan muu "yksikkoluku" ei ole vapautettu.
    assert ungrounded_numbers("Over 45 minutes.", facts) == ["45"]


def test_rounding_to_a_whole_number_is_not_grounded(facts):
    """5.8 EI oikeuta sanomaan 6: lukija tarkistaa luvun sivulta jossa
    lukee 5.8, ja nakee eri luvun kuin selitys vaittaa."""
    assert facts["xp_this_gw"] == 5.8
    assert ungrounded_numbers("Worth 6 points this week.", facts) == ["6"]


def test_clean_sentence_passes(facts):
    """Positiivinen kontrolli: pelkkia faktalohkon lukuja -> tyhja lista."""
    assert ungrounded_numbers("84 minutes and 5.8 points.", facts) == []
