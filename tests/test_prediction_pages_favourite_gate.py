# -*- coding: utf-8 -*-
"""SUOSIKKI-VAIN-KUN-ERO-YLITTAA-VIRHEEN pinnalla: ottelusivu + liigahubi.

Villen havainto 8.9: tuotanto nimesi Club Brugge suosikiksi 5,0 pp:n erolla
kun mallin oma mitattu virhe (8,2 pp) oli suurempi kuin tuo ero. Testit
antavat `error_pp`:n parametrina (ei lue data/accuracy.json:ia), jotta ne
ovat deterministisiä eivätkä riipu tuotannon senhetkisestä kalibroinnista.
"""
from datetime import datetime, timezone

from scripts.build_prediction_pages import render_league_hub, render_match_page

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def _entry(home="Club Brugge", away="Aston Villa", ph=0.405, pd_=0.240, pa=0.355):
    return {
        "home_team": home, "away_team": away,
        "p_home": ph, "p_draw": pd_, "p_away": pa,
        "predicted_winner": "home" if ph >= pa else "away",
        "kickoff": "2026-09-16T19:00:00Z", "date": "2026-09-16",
        "logged_at": "2026-09-15T10:00:00Z",
    }


def test_close_call_hero_does_not_name_a_favourite():
    e = _entry()
    html = render_match_page("CL", e, error_pp=8.2)
    assert "<strong>Club Brugge</strong> the favourite" not in html
    assert "gives Club Brugge a" not in html
    assert "too close to call" in html


def test_negative_control_clear_favourite_still_names_one():
    """Kontrolli: sama runko mutta selva suosikki (mitattu virhe pieni) -
    vanha kayttaytyminen sailyy silla etta se on aidosti oikein."""
    e = _entry(ph=0.70, pd_=0.20, pa=0.10)
    html = render_match_page("CL", e, error_pp=8.2)
    assert "favourite" in html
    assert "<strong>Club Brugge</strong>" in html
    assert "too close to call" not in html


def test_negative_control_same_gap_with_smaller_measured_error_names_favourite():
    """Sama Brugge-tapaus, mutta pienempi mitattu virhe (4.0 pp < 5.0 pp:n
    ero) -> suosikki saa nakya. Erottaa 'aina lahella'-bugin oikeasta
    kynnysvertailusta."""
    e = _entry()
    html = render_match_page("CL", e, error_pp=4.0)
    assert "favourite" in html
    assert "too close to call" not in html


def test_league_hub_shows_close_call_tag_instead_of_a_pick():
    rows = [_entry()]
    html = render_league_hub("CL", rows, now=NOW, error_pp=8.2)
    assert 'class="pick close-call">Too close to call<' in html
    assert "Club Brugge 41%" not in html and "Club Brugge 40%" not in html


def test_negative_control_league_hub_clear_favourite_keeps_the_pick():
    rows = [_entry(ph=0.70, pd_=0.20, pa=0.10)]
    html = render_league_hub("CL", rows, now=NOW, error_pp=8.2)
    assert 'class="pick close-call"' not in html
    assert 'class="pick">Club Brugge 70%<' in html


def test_missing_measurement_falls_back_to_old_behaviour():
    """error_pp=None (ei mitattu virhetta) ei saa vaimentaa mitaan pintaa -
    muuten puuttuva mittaus itsessaan piilottaisi jokaisen suosikin."""
    e = _entry()
    html = render_match_page("CL", e, error_pp=None)
    assert "favourite" in html
    assert "too close to call" not in html


def test_default_error_pp_reads_the_real_calibration_file_without_crashing():
    """Kytkentäportti: oletusarvo (`error_pp` ei annettu) lukee
    data/accuracy.json:n oikeasti - tämä ei mittaa lukua, vain että lukupolku
    ei kaadu tuotannon tiedostolla."""
    e = _entry(ph=0.70, pd_=0.20, pa=0.10)
    html = render_match_page("CL", e)  # ei error_pp -> lataa levylta
    assert "<h1>Club Brugge vs Aston Villa prediction</h1>" in html
