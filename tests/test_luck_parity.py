# -*- coding: utf-8 -*-
"""LUCK-PITCH: kynnysten pariteetti SPA:n ja mobiilin valilla (1.9.2026).

Sama saanto ajetaan kolmella pinnalla: mobiilin pitch
(`goaliq-app/lib/fantasyDisplay.ts`), taman repon SPA (`$lib/luck`) ja
jakokortit. Mobiili on toisessa reposssa eika ole luettavissa taalta, joten
tama testi pinnaa TAMAN pinnan kanoniseen lukuun: jos joku viilaa kynnysta
vain toisella pinnalla, testi kaatuu ja pakottaa kirjaamaan muutoksen molempiin.

Kanoniset luvut (dokumentoitu molempien tiedostojen kommentissa):
    haul  >= 10 pistetta
    blank <= 2 pistetta
    korkea xP >= 5.0
"""
import re
from pathlib import Path

import pytest

LUCK_TS = Path(__file__).resolve().parents[1] / "web" / "pro-spa" / "src" / "lib" / "luck.ts"

CANON = {"LUCK_HAUL_PTS": 10, "LUCK_BLANK_PTS": 2, "LUCK_HIGH_XP": 5}


def _constants(src: str) -> dict[str, int]:
    out = {}
    for name in CANON:
        m = re.search(rf"export const {name} = (-?\d+(?:\.\d+)?);", src)
        if m:
            out[name] = float(m.group(1))
    return out


def test_luck_module_exists():
    assert LUCK_TS.is_file(), f"puuttuu: {LUCK_TS}"


def test_kynnykset_ovat_kanonisia():
    got = _constants(LUCK_TS.read_text(encoding="utf-8"))
    assert got == pytest.approx(CANON), (
        "SPA:n luck-kynnykset eroavat kanonisista. Jos muutos on tarkoitettu, "
        "muuta MOLEMMAT pinnat (mobiili lib/fantasyDisplay.ts) ja tama testi."
    )


def test_negatiivinen_kontrolli_havaitsee_muutetun_kynnyksen():
    """Portti joka lapaisee kaiken ei ole portti."""
    mutated = LUCK_TS.read_text(encoding="utf-8").replace(
        "export const LUCK_HAUL_PTS = 10;", "export const LUCK_HAUL_PTS = 11;"
    )
    assert _constants(mutated)["LUCK_HAUL_PTS"] == 11
    assert _constants(mutated) != pytest.approx(CANON)


def test_vertailusuunnat_ovat_inklusiivisia():
    """`>` haul-rajalla pudottaisi tasan 10 pistetta tehneen tuomiotta, ja
    `<` blank-rajalla tekisi saman 2 pisteen kohdalla. Molemmat ovat hiljaisia:
    merkki vain puuttuisi eika mikaan huutaisi."""
    src = LUCK_TS.read_text(encoding="utf-8")
    assert "actual >= LUCK_HAUL_PTS" in src
    assert "actual <= LUCK_BLANK_PTS" in src
    assert "xp >= LUCK_HIGH_XP" in src


def test_kaikki_nelja_tuomiota_ovat_olemassa():
    src = LUCK_TS.read_text(encoding="utf-8")
    for verdict in ("called", "lucky", "robbed", "cold"):
        assert f"'{verdict}'" in src, f"tuomio {verdict} puuttuu"
        assert f"{verdict}:" in src, f"merkki tuomiolle {verdict} puuttuu"


def test_tyhja_rivi_ei_tuota_nollasummaa():
    """`squadLuck([]) -> null`, koska 0 pistetta / 0 xP olisi vaite
    kierroksesta jota ei ole pelattu."""
    src = LUCK_TS.read_text(encoding="utf-8")
    assert "if (rows.length === 0) return null;" in src
