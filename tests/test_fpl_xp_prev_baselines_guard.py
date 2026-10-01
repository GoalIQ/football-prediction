# -*- coding: utf-8 -*-
"""DATAPOHJA-JATKOT kohta 2 (30.9.2026, yoajo 1.10): PREV_BASELINES_PATH on
kovakoodattu `fpl_prev_baselines_2526.json`. Kun 2027/28-kausi avautuu, polku
jaa 2025/26-arkistoon eika kukaan huomaa - `minutes_reason` sanoisi "last
season" 2026/27-datasta ja `carry_prev_season` sekoittaisi vaaraa kautta,
molemmat HILJAA. Tama testaa etta vanhentunut arkisto kaataa ajon eika vain
toisessa vaiheessa (rule 6a mekanismi 1+3): ennen flippia (kuluva kausi =
arkiston kausi + 1 -> OK) ja flipin jalkeen (kuluva kausi = arkiston kausi + 2
-> kovaaaninen virhe).
"""
from __future__ import annotations

from scripts.build_fpl_xp import (
    check_prev_baselines_season,
    expected_prev_baselines_season_key,
)


def _events(gw1_deadline: str):
    return [{"id": 1, "deadline_time": gw1_deadline},
            {"id": 2, "deadline_time": "2099-01-01T00:00:00Z"}]


def test_expected_key_derived_from_gw1_deadline_year():
    # GW1 2026-08-15 -> kausi 2026/27 -> edellinen kausi "2526"
    assert expected_prev_baselines_season_key(
        _events("2026-08-15T10:00:00Z")) == "2526"
    # Seuraava kausi: GW1 2027-08-14 -> edellinen "2627"
    assert expected_prev_baselines_season_key(
        _events("2027-08-14T10:00:00Z")) == "2627"


def test_expected_key_none_without_gw1_deadline():
    assert expected_prev_baselines_season_key([]) is None
    assert expected_prev_baselines_season_key(
        [{"id": 2, "deadline_time": "2026-01-01T00:00:00Z"}]) is None


def test_fresh_archive_before_season_flip_passes():
    """Nykytila (mitattu 1.10.2026): kuluva kausi 2026/27, arkisto '2526' -
    tama EI saa kaataa ajoa."""
    archive = {"meta": {"season_key": "2526"}}
    check_prev_baselines_season(archive, _events("2026-08-15T10:00:00Z"))  # ei poikkeusta


def test_stale_archive_after_season_flip_raises():
    """2027/28 avautuu, arkisto on yha '2526' (kaksi kautta jaljessa, pitaisi
    olla '2627') - kovaaaninen virhe, ei hiljainen vaarentuma."""
    archive = {"meta": {"season_key": "2526"}}
    try:
        check_prev_baselines_season(archive, _events("2027-08-14T10:00:00Z"))
    except RuntimeError as exc:
        assert "2526" in str(exc) and "2627" in str(exc)
    else:
        raise AssertionError(
            "vanhentunut arkisto EI kaatanut ajoa - negatiivinen kontrolli "
            "osoittaa etta vahti ei toimi")


def test_missing_meta_is_fail_open_not_this_check():
    """Tiedosto puuttuu kokonaan (lataus epaonnistui main()issa) -> meta on
    tyhja dict, archive_key None -> tama vahti ei ota kantaa (eri virhe)."""
    check_prev_baselines_season({"players": {}, "meta": {}},
                                _events("2026-08-15T10:00:00Z"))


def test_the_guard_itself_would_fail_on_the_old_hardcoded_behaviour():
    """Negatiivinen kontrolli koko tiedostolle: jos vahtia EI olisi (vanha
    koodi ei tarkistanut mitaan), vanhentunut arkisto etenisi huomaamatta -
    simuloitu tassa ohittamalla check_prev_baselines_season kokonaan ja
    toteamalla etta avaimet todella eroavat (muuten testi ei todista mitaan)."""
    archive_key = "2526"
    expected_key = expected_prev_baselines_season_key(
        _events("2027-08-14T10:00:00Z"))
    assert archive_key != expected_key
