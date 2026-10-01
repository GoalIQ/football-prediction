# -*- coding: utf-8 -*-
"""DATAPOHJA-JATKOT kohta 1 (30.9.2026, yoajo 1.10): GW1-ikkunan vaihetesti.

`preseason` paatti aiemmin bootstrapin event-tason `finished`-lipusta, joka
pysyy False'na KOKO GW1:n ajan (kickoff - viimeisen ottelun gradaus,
~3-4 vrk). Sina ikkunassa builder kaytti jaadytettya 25/26-arkistoa vaikka
GW1:ssa debytoinut oli jo pelannut, ja kortti vaitti "no Premier League
minutes this season" virheellisesti. Korjaus: `season_has_started` lukee
ottelun kickoff-aikaa (ei voi laahata), ei event['finished']-lippua
(fpl_gameweek.completed_gameweeks on sama akseli).

Rule 6a -vaihetesti: sama funktio ajetaan KOLMESSA vaiheessa synteettisella
datalla (ei verkkoa, ei elavia artefakteja), jotta vika loytyy commitilla
eika seuraavan elokuun kauden avauksessa.

VAIHEET:
  before   ei yhtaan ottelua pelattu  (aito esikausi)
  live     GW1 kesken: eka ottelu kickoffannut, event['finished'] viela False
  after    GW1 gradattu: event['finished'] True
"""
from __future__ import annotations

from scripts.build_fpl_xp import season_has_started

PAST_MS = 1_600_000_000_000   # 2020 - aina menneisyydessa
FUTURE_MS = 1_900_000_000_000  # 2030 - aina tulevaisuudessa


def _fixtures(*kickoffs_ms):
    return [{"gameweek": 1, "kickoff_ms": ms, "finished": False}
            for ms in kickoffs_ms]


def _old_preseason(events) -> bool:
    """Korjausta edeltava ehto, tassa vain NEGATIIVISTA kontrollia varten."""
    return not any(ev.get("finished") for ev in events)


def test_before_no_fixture_has_kicked_off_is_preseason():
    assert season_has_started(_fixtures(FUTURE_MS, FUTURE_MS)) is False


def test_live_first_fixture_kicked_off_is_not_preseason():
    """GW1 kesken: ensimmainen ottelu kaynnissa/pelattu, event ei viela
    `finished`. Tama ON kohta jossa vanha ehto oli vaarin."""
    fixtures = _fixtures(PAST_MS, FUTURE_MS)
    assert season_has_started(fixtures) is True
    # negatiivinen kontrolli: event-tason finished-ehto EI naekisi tata -
    # juuri tama ristiriita oli DATAPOHJA-JATKOT kohta 1:n vika.
    events = [{"id": 1, "finished": False}]
    assert _old_preseason(events) is True, (
        "vanha ehto piti GW1:n esikautena viela kesken kierroksen - "
        "jos tama kaatuu, negatiivinen kontrolli ei enaa todista mitaan")


def test_after_gameweek_finished_is_not_preseason():
    fixtures = _fixtures(PAST_MS, PAST_MS)
    assert season_has_started(fixtures) is True


def test_no_fixtures_at_all_is_preseason():
    """Puuttuva/tyhja fixtures-lista (esim. kutsupaikan virhe) -> turvallinen
    oletus on esikausi, ei kaatuminen."""
    assert season_has_started([]) is False
    assert season_has_started(None) is False


def test_fixture_without_kickoff_time_is_ignored_not_crashed():
    assert season_has_started([{"gameweek": 1, "kickoff_ms": None}]) is False
