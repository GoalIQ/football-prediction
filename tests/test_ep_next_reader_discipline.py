# -*- coding: utf-8 -*-
"""LUKIJAKURI ep_next:lle (D5, 22.9.2026).

FPL:n `ep_next` viittaa aina bootstrapin is_next-kierrokseen. Deadlinen
jalkeen se on jo seuraavan kierroksen luku, ja `ep_this` paivittyy
deadlinen jalkeen. Siksi jaadytetty ep_next on kierroksen deadline-arvo vain
jos freeze todisti sen (scripts/freeze_fpl_xp_gw.fpl_reference_gate) ja
gradaus luki sen yhden lukijan kautta
(src/models/fpl_xp_accuracy.frozen_players).

Tama testi estaa kolmannen reitin syntymisen unohduksesta: jos uusi tiedosto
lukee avainta "ep_next" tai "ep_this" suoraan, testi kaatuu ja kirjoittaja
joutuu joko kayttamaan lukijaa tai perustelemaan poikkeuksen alla.
AST-pohjainen: kommentit ja docstringit eivat laukaise, vain avaimena
kaytetty merkkijonovakio.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYS = {"ep_next", "ep_this"}
SCAN_DIRS = ("scripts", "src", "api")

# Tiedosto -> miksi se saa kasitella avainta suoraan. Rivi ilman perustelua
# ei ole perustelu.
ALLOWED = {
    "scripts/freeze_fpl_xp_gw.py": (
        "KIRJOITTAJA: lukee live-bootstrapin ep_next:n ja kirjoittaa sen "
        "freezeen vain kun fpl_reference_gate todistaa sen deadline-arvoksi."),
    "src/models/fpl_xp_accuracy.py": (
        "LUKIJA: frozen_players() riisuu todistamattoman ep_next:n; "
        "grade_players/vs_fpl_ep_next saavat rivit vain sen kautta."),
}


def _key_constants(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and n.value in KEYS]


def _scan() -> dict[str, list[int]]:
    hits = {}
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for f in base.rglob("*.py"):
            if "node_modules" in f.parts:
                continue
            lines = _key_constants(f)
            if lines:
                hits[f.relative_to(ROOT).as_posix()] = lines
    return hits


def test_ep_next_luetaan_vain_nimetyista_paikoista():
    hits = _scan()
    extra = {f: ln for f, ln in hits.items() if f not in ALLOWED}
    assert not extra, (
        "Uusi tiedosto lukee FPL:n ep_next/ep_this-avainta suoraan: "
        f"{extra}. Lue jaadytetty arvo fpl_xp_accuracy.frozen_players():n "
        "kautta, tai lisaa tiedosto ALLOWED-listaan perustelun kanssa.")


def test_poikkeuslista_ei_vanhene():
    """Poikkeus joka ei enaa lue avainta on kuollut rivi joka peittaisi
    myohemman lisayksen samaan tiedostoon ilman uutta harkintaa."""
    hits = _scan()
    stale = [f for f in ALLOWED if f not in hits]
    assert not stale, f"ALLOWED-rivi ilman osumaa: {stale}"
    assert all(len(why) > 40 for why in ALLOWED.values())


def test_skanneri_loytaa_suoran_lukijan(tmp_path):
    """Mutaatiokontrolli: skanneri tunnistaa avaimen get()- ja []-muodossa
    mutta ei kommentissa eika docstringissa."""
    f = tmp_path / "x.py"
    f.write_text('"""ep_next docstring."""\n'
                 "# ep_next kommentti\n"
                 "a = row.get('ep_next')\n"
                 "b = el['ep_this']\n", encoding="utf-8")
    assert _key_constants(f) == [3, 4]
