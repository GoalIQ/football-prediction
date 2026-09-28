"""MINILIIGA-JULKISUUSSAANTO (28.9.2026, yoajo).

DoD (cos-reports/QUEUE.md): "negatiivinen kontrolli: kortti jossa on toisen
managerin koko nimi kaataa testin". Testi 3 rakentaa juuri sen kortin.
"""
from __future__ import annotations

import pytest

from src.models.mini_league_privacy import (
    OtherManagerNameLeaked,
    assert_no_other_manager_full_names,
    public_manager_label,
)


# ---------------------------------------------------------------------------
# 1. public_manager_label
# ---------------------------------------------------------------------------
def test_submitter_keeps_full_name():
    assert public_manager_label("Priya Ramaswamy", is_submitter=True) == "Priya Ramaswamy"


def test_other_manager_is_shortened_to_first_name_and_initial():
    assert public_manager_label("Tom Baxter", is_submitter=False) == "Tom B."


def test_single_word_name_is_left_as_is():
    """Yhdesta sanasta lyhentaminen ei suojaisi mitaan."""
    assert public_manager_label("Cher", is_submitter=False) == "Cher"


def test_empty_name_returns_empty():
    assert public_manager_label(None, is_submitter=False) == ""
    assert public_manager_label("  ", is_submitter=True) == ""


# ---------------------------------------------------------------------------
# 2. assert_no_other_manager_full_names — positiiviset polut
# ---------------------------------------------------------------------------
def test_submitter_full_name_is_allowed():
    text = "Priya Ramaswamy's league had the wildest GW3 collapse."
    assert_no_other_manager_full_names(
        text, ["Priya Ramaswamy", "Tom Baxter"], submitter_name="Priya Ramaswamy")


def test_anonymised_other_manager_is_allowed():
    text = "Tom B. finished last with a -4 captaincy call."
    assert_no_other_manager_full_names(
        text, ["Priya Ramaswamy", "Tom Baxter"], submitter_name="Priya Ramaswamy")


def test_first_name_alone_does_not_false_positive():
    """Etunimi yksinaan (osana anonymisoitua muotoa) ei saa laukaista
    kontrollia - muuten anonymisoitu teksti itse kaataisi portin."""
    text = "Tom's transfer in GW4 was a disaster."
    assert_no_other_manager_full_names(
        text, ["Priya Ramaswamy", "Tom Baxter"], submitter_name="Priya Ramaswamy")


# ---------------------------------------------------------------------------
# 3. NEGATIIVINEN KONTROLLI (DoD:n oma sanamuoto): kortti jossa on toisen
#    managerin koko nimi kaataa testin.
# ---------------------------------------------------------------------------
def test_negative_control_card_with_other_managers_full_name_fails():
    card_text = (
        "This mini-league's biggest disaster: Tom Baxter benched his "
        "captain and finished 47 points behind Priya Ramaswamy."
    )
    with pytest.raises(OtherManagerNameLeaked):
        assert_no_other_manager_full_names(
            card_text, ["Priya Ramaswamy", "Tom Baxter"],
            submitter_name="Priya Ramaswamy")


def test_negative_control_is_case_insensitive():
    """Muuten "tom baxter" pienella kirjaimella livahtaisi lapi."""
    with pytest.raises(OtherManagerNameLeaked):
        assert_no_other_manager_full_names(
            "biggest bottler this season: tom baxter",
            ["Priya Ramaswamy", "Tom Baxter"], submitter_name="Priya Ramaswamy")


def test_negative_control_parser_and_rule_would_not_pass_empty():
    """Kontrolli: jos kortti EI sisalla ketaan, portti ei saa huutaa tyhjasta
    (muuten se olisi aina punainen eika mittaisi mitaan)."""
    assert_no_other_manager_full_names(
        "GW4 was a quiet round for this league.",
        ["Priya Ramaswamy", "Tom Baxter"], submitter_name="Priya Ramaswamy")
