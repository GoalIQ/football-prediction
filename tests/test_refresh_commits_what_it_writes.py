# -*- coding: utf-8 -*-
"""Portti: refresh-ajon kirjoittama artefakti on myos committoitava.

TAUSTA (7.9.2026, julkaisutarkistajan 17. kierros). `data/gw_recap.json` oli
**JAASSA 7 vuorokautta**. `fpl-data-refresh.yml` ajaa `build_gw_recap`in joka
ajossa, skripti kirjoittaa oikeat luvut runnerin levylle - ja commit-askel
listaa 20 tiedostoa nimeltä, joista tama puuttui. Levy katoaa ajon mukana.

Mitattu: artefakti sanoi *"1 kierros, -9 vs keskiarvo, 0x yli keskiarvon"*
kun todellisuus oli 2 kierrosta ja +18. Se on **mallin julkinen track
record**, eli viikkopostauksen luku.

MIKSI MIKAAN EI HUUTANUT: askel onnistuu (skripti palauttaa 0), joten Step
healthin `::error::` ei laukea. Ja `tests/test_gw_recap.py` assertoi
`.gitignore`n poikkeusrivin - eli sen etta tiedosto SAA olla gitissa, ei
sita etta se PAATYY sinne. Sama vikaluokka kuin `vihrea-putki-nielee-
jaatymisen` ja `loki-voi-valehdella-onnistumisesta`.

Portti lukee workflow'n `git add` -listan ja vaatii, etta jokaisen
artefaktia kirjoittavan skriptin ulostulo on siella. Uusi skripti ei paase
listan ohi vahingossa: testi kaatuu ja kirjoittaja joutuu joko lisaamaan
rivin tai kirjoittamaan perustelun poikkeuslistalle.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows" / "fpl-data-refresh.yml"

# Skriptit jotka refresh ajaa ja jotka kirjoittavat `data/`-artefaktin.
# Arvo = tiedosto joka on committoitava.
KIRJOITTAJAT = {
    "build_gw_recap": "data/gw_recap.json",
    "build_team_confidence": "data/team_confidence.json",
    "build_fpl_price_watch": "data/fpl_price_watch.json",
    "build_fpl_defcon_gw": "data/fpl_defcon_gw.json",
    "build_fpl_player_leaders": "data/fpl_player_leaders.json",
    "build_fpl_stats": "data/fpl_player_stats.json",
    "build_fpl_cs_fdr": "data/fpl_cs_fdr.json",
}

# POIKKEUSLISTA: tiedosto jota refresh EI committaa, perusteluineen.
# Tyhja perustelu ei kelpaa.
POIKKEUKSET: dict[str, str] = {}


def _workflow() -> str:
    return WF.read_text(encoding="utf-8", errors="replace")


def _git_add_rivit(teksti: str) -> str:
    return "\n".join(r for r in teksti.splitlines() if "git add" in r)


def test_jokainen_artefaktin_kirjoittaja_on_myos_commit_listalla():
    wf = _workflow()
    addit = _git_add_rivit(wf)
    puuttuu = []
    for skripti, tiedosto in KIRJOITTAJAT.items():
        if skripti not in wf:
            continue  # ei ajossa tassa workflow'ssa
        if tiedosto in POIKKEUKSET:
            assert POIKKEUKSET[tiedosto].strip(), f"{tiedosto} ilman perustelua"
            continue
        if tiedosto not in addit:
            puuttuu.append(f"{skripti} kirjoittaa {tiedosto}")
    assert not puuttuu, (
        "refresh ajaa naita mutta ei committaa niiden ulostuloa - luvut "
        "elavat vain runnerin levylla:\n  " + "\n  ".join(puuttuu))


def test_gw_recap_on_listalla_nimenomaisesti():
    """Regressio: tama nimenomainen tiedosto oli jaassa 7 vrk."""
    assert "data/gw_recap.json" in _git_add_rivit(_workflow())


def test_kontrolli_havaitsin_lukee_oikeaa_lohkoa():
    """NEGATIIVINEN KONTROLLI havaitsimelle: ilman tata portti voisi olla
    vihrea siksi etta `_git_add_rivit` palauttaa tyhjaa (muisti:
    kontrolli-lapaisi-tyhjana)."""
    addit = _git_add_rivit(_workflow())
    assert addit.count("git add") >= 10, (
        f"git add -rivit ei loytynyt odotetusti: {addit.count('git add')}")
    # Ja tunnettu rivi on siella.
    assert "data/gw_calls.json" in addit
    # Keksitty tiedosto EI ole.
    assert "data/ei-ole-olemassa.json" not in addit
