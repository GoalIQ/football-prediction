# -*- coding: utf-8 -*-
"""KIELIPORTTI: suomea ei shipata julkisille englanninkielisille sivuille.

Julkaisutarkistaja loysi 24.8 suomenkielisia JS-kommentteja `fpl/stats.html`
:sta ja neljalta muulta sivulta. Ensimmainen versio tasta portista mittasi
SANALISTALLA ja se vanhentui valittomasti: lista oli
["kortti","rajaus","lukee","eika",...] eika yksikaan niista esiintynyt
riveilla "nolla olisi vaite ettei han laukonut kertaakaan" tai "lukuja
GW-otsikon alla". Portti oli vihrea ja suomi shippasi.

Kirjattu vikaluokka: portin sanalista vanhenee. Mittari on nyt MORFOLOGIA
eika sanasto - suomen tunnusloput ja aa/oo/ai-diftongit joita englannissa
ei esiinny - plus skandimerkit. Negatiivinen kontrolli on testissa mukana:
`test_gate_catches_planted_finnish` istuttaa suomenkielisen rivin ja vaatii
etta portti kaatuu.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SIVUT = ["points", "expected-points", "xg-leaders", "stats", "defence",
         "defcon", "differentials", "price-changes", "team-news"]

# Suomen tunnusloput ja kirjainyhdistelmat joita englanninkielisessa
# kommentissa ei kaytannossa esiinny. Tarkoituksella morfologinen: uusi
# suomenkielinen lause osuu naihin vaikka sen sanasto olisi tuntematon.
_FI = re.compile(
    r"[äöÄÖ]"
    r"|\b\w*(?:ttaa|ttaisi|isesti|ksessa|ssaan|staan|lla|lta|lle|sta|ksi)\b"
    r"|\b(?:eika|vaan|jotta|koska|mutta|silla|joten|vaikka|ilman|jokainen"
    r"|olisi|oli|onko|nayttaa|lukee|kertoo|antaa|tekee|tulee|pitaa)\b",
    re.IGNORECASE)


def _kommenttirivit(html: str) -> list[str]:
    out = []
    for rivi in html.split(chr(10)):
        t = rivi.strip()
        if t.startswith("//") or t.startswith("/*") or t.startswith("*"):
            out.append(t)
    return out


def _sivu(nimi: str) -> str:
    p = ROOT / "fpl" / f"{nimi}.html"
    if not p.exists():
        pytest.skip(f"{p.name} ei ole rakennettu")
    return p.read_text(encoding="utf-8", errors="replace")


@pytest.mark.parametrize("sivu", SIVUT)
def test_no_finnish_in_shipped_js(sivu):
    for t in _kommenttirivit(_sivu(sivu)):
        m = _FI.search(t)
        assert not m, (
            f"{sivu}: suomea shipatussa JS:ssa ({m.group(0)!r}): {t[:90]!r}")


def test_gate_catches_planted_finnish():
    """Negatiivinen kontrolli. Ilman tata portti voi olla pysyvasti sokea."""
    istutetut = [
        "// nolla olisi vaite ettei han laukonut kertaakaan.",
        "// lukuja GW-otsikon alla, loytyi vasta livesivulta",
        "// tama rivi kertoo mika sarake on lajiteltu",
        "// jokainen kortti nayttaa saman rajauksen",
    ]
    for rivi in istutetut:
        assert _FI.search(rivi), f"portti ei nae istutettua suomea: {rivi!r}"


def test_gate_does_not_flag_english():
    """Vaara positiivinen olisi yhta paha: portti hylkaisi kelvollisen rivin."""
    englanti = [
        "// null = the player was not matched to shot data.",
        "// The card must not fail on a missing asset: draw the wordmark.",
        "// Mins and Starts are windowable: without raw() they showed season",
        "// Sort marker in the header: the reader sees the order.",
        "// The price picker's default is the upper bound (99), not a filter.",
    ]
    for rivi in englanti:
        m = _FI.search(rivi)
        assert not m, f"portti hylkasi englannin ({m.group(0)!r}): {rivi!r}"
