# -*- coding: utf-8 -*-
"""Portti: career.html:n `drawCard(d)` ei saa uudelleenmaaritella `d`ta.

TAUSTA (KORTTI-MUUTTUJAN-VARJOSTUS, 11.9.2026, portin 17. kierroksen
sivuloydos). `career.html:694` teki `var d = t.xp_vs_benchmark;` SISALLA
`drawCard(d)`-funktiota. JavaScriptin `var` on FUNKTIOSKOOPPINEN, ei
lohkoskoopattu, joten tama korvasi funktion oman `d`-parametrin (kortin koko
payload) luvulla lopusta funktiota - jos joku myohempi rivi lukisi `d.jotain`
saisi hiljaisen `undefined`in. Tanaan tama ei kaadu, koska ainoa haara joka
lukee `d.past_seasons` on sen `if`/`else`-parin TOINEN puoli - mutta se on
ansa seuraavalle muokkaajalle, ei todiste ettei vikaa voi syntya (CLAUDE.md
6a: "suunnittele niin ettei vikaa voi syntya", mekanismi 2 - poikkeuslista
jossa on perustelu, testi kaatuu jos joku palauttaa saman ansan).

Tama EI ole `portti-joka-etsii-merkkijonoa-ei-mittaa-arvoa`: emme testaa mita
kortti PIIRTAA (siihen on `test_career_card_render.py`:n harness, joka ajaa
`drawCard`in oikeasti) vaan koodin OMAA muotoa - sama tapa kuin
`test_optimality_claim_family.py` skannaa vaiteperheen. Kahta eri tarkoitusta
varten, ei paallekkaisia.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "career.html"


def _draw_card_source() -> str:
    """Sama poiminta kuin `tests/js/career_card_harness.js`: <script>-lohko
    jossa drawCard maaritellaan, funktion body ekaan tasoltaan tasapainoisin
    aaltosulkein."""
    html = PAGE.read_text(encoding="utf-8")
    blocks = re.findall(r"<script>\r?\n([\s\S]*?)</script>", html)
    src = next((b for b in blocks if "function drawCard(" in b), None)
    assert src is not None, "drawCard-lohkoa ei loytynyt career.html:sta"
    m = re.search(r"function drawCard\((\w+)\)\s*\{", src)
    assert m is not None, "drawCard-signaturea ei tunnistettu"
    param = m.group(1)
    start = m.end()
    depth = 1
    i = start
    while depth > 0:
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
        i += 1
    return param, src[start:i - 1]


def _redeclares(body: str, name: str) -> bool:
    return re.search(rf"\b(?:var|let|const)\s+{re.escape(name)}\b\s*=", body) is not None


def test_draw_card_never_reassigns_its_own_parameter():
    param, body = _draw_card_source()
    assert param == "d", "drawCard:n parametrin nimi vaihtui - paivita testin oletus"
    assert not _redeclares(body, param), (
        f"drawCard uudelleenmaarittelee oman parametrinsa `{param}` - "
        "var on funktioskoopattu, joten tama varjostaisi payloadin lopusta "
        "funktiota (KORTTI-MUUTTUJAN-VARJOSTUS)")


def test_mutation_the_check_actually_fires():
    """Negatiivinen kontrolli: testi joka lapaisee tyhjana ei ole testi.
    Injektoi tasan se rivi joka oli 11.9 asti oikeassa koodissa, ja
    varmista etta `_redeclares` nakee sen."""
    param, body = _draw_card_source()
    mutated = body.replace(
        "var diffXp = t.xp_vs_benchmark;", "var d = t.xp_vs_benchmark;", 1)
    assert mutated != body, "mutaatio ei osunut - testin oma odotus vanhentui"
    assert _redeclares(mutated, param)
    # Ja puhdas koodi ei laukaise samaa tarkistusta turhaan.
    assert not _redeclares(body, param)
