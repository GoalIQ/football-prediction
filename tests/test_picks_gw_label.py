"""RATE-TEAM-PICKS-GW-LABEL (27.8.2026).

Vikaluokka: FPL ei julkaise tulevan kierroksen pickeja ennen deadlinea
(GW2-picksit 404 deadlineen asti), joten rate my team nayttaa GW{n-1}:n
rungon. Ilman selitysrivia kayttaja paattelee etta tuote on rikki (Villen
kysymys 26.8). Mitattu 27.8 myos ettei siirto-overlay ole mahdollinen:
GW2-siirtoja tehty 7,67 M (bootstrapin transfers_in_event), mutta 0/121
otoksen entrylla yksikaan ei nay julkisessa /transfers/-listassa ennen
deadlinea — FPL piilottaa nekin.

QUEUE-rivin vaatima mutaatiokontrolli: `picks_gw == deadline_gameweek`
-> rivi EI nay.
"""
from __future__ import annotations

import pytest

from src.models.fpl_rate_team import deadline_time_for, picks_outdated


def test_picks_from_previous_gw_flags_outdated():
    """GW1-picksit, deadline-GW 2 -> lippu paalla (rivi naytetaan)."""
    assert picks_outdated(1, 2) is True


def test_picks_equal_to_deadline_gw_is_not_outdated():
    """QUEUE-rivin mutaatiokontrolli: picks_gw == deadline_gameweek ->
    rivi EI nay. Tama on normaalitila deadlinen jalkeen ~30 min viiveella
    (404 -> 503 -> 200, mitattu GW1)."""
    assert picks_outdated(2, 2) is False


def test_two_gameweek_gap_shows_no_line():
    """Julkaisuportin blokkaava loydos 27.8: picks_gw ja deadline_gameweek
    tulevat ERI lahteista (elava bootstrap 10 min cachella vs artefaktin
    3 h cron), ja deadlinen ymparilla ne voivat erota kaksi kierrosta.
    Silloin rivi vaittaisi "GW1 squad, GW3 picks..." kayttajalle jonka
    GW2-runko on jo julkinen -> ei rivia kun ero != 1."""
    assert picks_outdated(1, 3) is False


def test_picks_never_flagged_backwards():
    """picks_gw > deadline_gameweek (ei pitaisi esiintya) -> ei lippua.
    Vaara suunta olisi eri vaite kuin 'FPL ei ole viela julkaissut'."""
    assert picks_outdated(3, 2) is False


@pytest.mark.parametrize("picks,dl", [
    (None, 2), (1, None), (None, None),
    ("1", 2), (1, "2"), (1.0, 2), (1, 2.0),
])
def test_missing_or_broken_fields_fail_closed(picks, dl):
    """Vanha payload tai rikkinainen kentta -> False, rivia ei nayteta.
    Vaara rivi ('FPL makes GW... public after the deadline') olisi
    huonompi kuin puuttuva."""
    assert picks_outdated(picks, dl) is False


def test_bool_is_not_a_gameweek():
    """bool on intin alaluokka (True < 2 on tosi) — sama ansa joka on jo
    kirjattu planning_start_gw-testeihin. Ei saa sytyttaa rivia."""
    assert picks_outdated(True, 2) is False
    assert picks_outdated(1, True) is False


def test_deadline_time_found_for_gw():
    bs = {"events": [
        {"id": 1, "deadline_time": "2026-08-21T17:30:00Z"},
        {"id": 2, "deadline_time": "2026-08-28T17:30:00Z"},
    ]}
    assert deadline_time_for(bs, 2) == "2026-08-28T17:30:00Z"


def test_deadline_time_missing_gw_or_broken_input_is_none():
    bs = {"events": [{"id": 1, "deadline_time": "2026-08-21T17:30:00Z"}]}
    assert deadline_time_for(bs, 9) is None
    assert deadline_time_for(bs, None) is None
    assert deadline_time_for(bs, True) is None
    assert deadline_time_for({}, 1) is None
    assert deadline_time_for({"events": [{"id": 1, "deadline_time": 123}]},
                             1) is None
