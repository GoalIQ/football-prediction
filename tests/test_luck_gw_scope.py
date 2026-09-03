# -*- coding: utf-8 -*-
"""Paattyneen kierroksen luvut eivat saa vuotaa toisen kierroksen sarakkeeseen.

Vika (3.9.2026, Villen havainto): "My team" nayttti GW2:n toteutuneet pisteet
siina missa pitaisi lukea GW3:n xP. Ehto `picksGw === lastFinished.gw` luettiin
merkiksi siita etta kierros juuri paattyi, mutta FPL pitaa entryn picksit
edellisessa kierroksessa deadlineen asti — eli ehto on tosi koko sen ikkunan
jonka kayttaja kayttaa SEURAAVAN kierroksen suunnitteluun.

Mekanismi (CLAUDE.md saanto 6a):
  (1) yksi lukija: `settledGwReadable` molemmilla pinnoilla. Kartta jaa
      tyhjaksi kun katsottava kierros ei ole se jolta toteumat ovat.
  (2) tama testi: jos joku rakentaa kartan uudelleen suoraan
      `lastFinished.players`-lohkosta ilman lukijaa, testi kaatuu.
  (3) vaiheparametroitu totuustaulu ajetaan mobiilissa
      (`goaliq-app/lib/fantasyDisplay.test.ts`), jossa TS on ajettavissa.

Mobiilin lahde on toisessa reposssa eika luettavissa taalta (sama rajoite kuin
test_luck_parity.py:ssa) — tama testi pinnaa TAMAN repon pinnan.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LUCK_TS = ROOT / "web" / "pro-spa" / "src" / "lib" / "luck.ts"
PITCH = ROOT / "web" / "pro-spa" / "src" / "lib" / "components" / "TeamPitchManager.svelte"

# Lohko joka rakentaa toteumakartan. Haetaan nimella, ei rivinumerolla.
LUCK_MAP_RE = re.compile(
    r"const luckById = \$derived\.by\(\(\) => \{(.*?)\n\t\}\);", re.S)


def _luck_map_body() -> str:
    m = LUCK_MAP_RE.search(PITCH.read_text(encoding="utf-8"))
    assert m, "TeamPitchManager: luckById-lohkoa ei loytynyt (nimi vaihtui?)"
    return m.group(1)


def test_helper_exists_and_is_not_a_constant():
    """Lukija on olemassa ja sen ehto on aito (ei `return true`)."""
    src = LUCK_TS.read_text(encoding="utf-8")
    assert "export function settledGwReadable(" in src
    body = src.split("export function settledGwReadable(", 1)[1]
    # Negatiivinen kontrolli: kaikki kolme haaraa on kirjoitettu ulos.
    assert "if (!sameSquad || luckGw == null) return false;" in body
    assert "if (selGw == null) return true;" in body
    assert "return selGw === luckGw;" in body


def test_pitch_builds_the_map_only_through_the_reader():
    """Kartta rakennetaan lukijan takana, ei suoraan lohkosta."""
    body = _luck_map_body()
    assert "settledGwReadable(premium ? selGw : null, luckGw, luckSameSquad)" in body, (
        "luckById lukee last_finished-lohkon ilman settledGwReadablea — "
        "silloin paattyneen kierroksen pisteet voivat nakya tulevan "
        "kierroksen sarakkeessa (vika 3.9.2026).")
    # Portti ei saa lapaista pelkasta maininnasta: ehdon on oltava
    # AIKAISEMMIN kuin silmukka joka tayttaa kartan.
    gate = body.index("settledGwReadable(")
    fill = body.index("for (const r of lastFinished.players)")
    assert gate < fill, "ehto on silmukan JALKEEN — kartta ehtii tayttya"


def test_forecast_column_is_the_default():
    """Oletusvalinta on ennustekierros, ei paattynyt."""
    src = PITCH.read_text(encoding="utf-8")
    assert "defaultGw != null && gwsAvailable.includes(defaultGw)" in src, (
        "oletus-GW luetaan chip-listalta (johon paattynyt kuuluu) eika "
        "ennustelistalta — silloin naytto voi avautua tulokseen")
    # Paattynyt kierros on oma chippinsa, eli kayttaja EI menetä nakymaa.
    assert "gwChips" in src and "result" in src
