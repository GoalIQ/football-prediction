# -*- coding: utf-8 -*-
"""GW1-IKKUNA: preseason luetaan fixturesta, ei event.finished-lipusta
(DATAPOHJA-JATKOT kohta 1, yöajo 2.10.2026).

Juurisyy on sama luokka joka on dokumentoitu `fpl_gameweek.py`:n yläosassa
nelja kertaa kolmessa viikossa (3.9): FPL:n `event.finished` (koko
gameweekin aggregaatti) kaantyy vasta VIIMEISEN ottelun jalkeen, kun taas
yksittaisen ottelun oma `finished`-kentta kaantyy heti. `build_fpl_xp.py`
luki esikauden tilan event-tasolta, jolloin GW1-viikonloppuna (~3-4 vrk,
perjantain avausottelusta maanantain paatosotteluun) debytantti joka jo
pelasi ensimmaisen ottelunsa luettiin silti esikautiseksi, eika hanen
per-pelaaja-dataansa (element-summary) haettu lainkaan — kortti sanoi
"no Premier League minutes this season or last" vaikka han jo pelasi.

VAIHEET (sama rakenne kuin test_gameweek_phase_invariants.py):
  true_preseason   ei yhtaan ottelua pelattu (esikausi aidosti)
  gw1_window       GW1 kesken: osa otteluista paattynyt, osa ei (BUGI-IKKUNA)
  mid_season       useita GW:ita pelattu
  season_end       koko kausi pelattu
"""
from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from src.models.fpl_gameweek import season_underway

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts" / "build_fpl_xp.py"


def _fixture(gw: int, finished: bool, kickoff_ms: int = 1_700_000_000_000):
    return {"gameweek": gw, "kickoff_ms": kickoff_ms, "finished": finished,
            "home": "A", "away": "B"}


PHASES = [
    ("true_preseason", [
        _fixture(1, False), _fixture(1, False), _fixture(2, False),
    ], False),
    ("gw1_window", [
        _fixture(1, True), _fixture(1, True),
        _fixture(1, False), _fixture(1, False), _fixture(1, False),
    ], True),
    ("mid_season", [
        _fixture(1, True), _fixture(2, True), _fixture(3, True),
        _fixture(4, False), _fixture(4, False),
    ], True),
    ("season_end", [_fixture(g, True) for g in range(1, 39)], True),
]


@pytest.mark.parametrize("phase,fixtures,expected", PHASES)
def test_season_underway_tracks_individual_matches_not_the_whole_gameweek(
        phase, fixtures, expected):
    assert season_underway(fixtures) is expected, phase


def test_empty_fixtures_is_preseason():
    assert season_underway([]) is False
    assert season_underway(None) is False


def test_the_guard_itself_would_fail_on_the_old_event_level_check():
    """Negatiivinen kontrolli: GW1-ikkunassa VANHA event.finished-pohjainen
    laskenta antoi preseason=True (vika), uusi fixture-pohjainen antaa
    preseason=False (korjattu). Jos joku palauttaa build_fpl_xp.py:n lukemaan
    boot["events"]:ia uudelleen, tama testi nayttaa mika eroaa."""
    gw1_window_fixtures = PHASES[1][1]
    # event-taso: GW1 ei ole viela "finished" koska osa otteluista on kesken.
    boot_events_gw1_in_progress = [{"id": 1, "finished": False},
                                   {"id": 2, "finished": False}]
    old_preseason = not any(
        ev.get("finished") for ev in boot_events_gw1_in_progress)
    new_preseason = not season_underway(gw1_window_fixtures)
    assert old_preseason is True, "vanha logiikka: esikausi (VIKA)"
    assert new_preseason is False, "uusi logiikka: kausi on alkanut (korjattu)"
    assert old_preseason != new_preseason


def test_kutsupaikka_lukee_jaetun_funktion():
    """Saanto 6a kohta 1: build_fpl_xp.py EI laske esikautta itse
    (`not any(ev.get("finished") ...)`) vaan lukee `fplgw.season_underway`:n,
    joka on sama lahde kuin `completed_gameweeks`/`display_gameweek`
    kayttavat. Yksi lukija ei voi palauttaa vaaraa kahdella eri tavalla."""
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    found = False
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "preseason"):
            continue
        found = True
        call_src = ast.unparse(node.value)
        assert call_src == "not fplgw.season_underway(src['fixtures'])", call_src
    assert found, "preseason-sijoitusta ei loytynyt build_fpl_xp.py:sta"


def test_module_still_importable():
    """Varmistaa ettei muokkaus riko moduulin importin (ks.
    test_minutes_reason_season.py sama kuvio)."""
    importlib.import_module("scripts.build_fpl_xp")
