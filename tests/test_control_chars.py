# -*- coding: utf-8 -*-
"""Portti: kontrollimerkit lahdekoodissa tekevat regexista INERTIN.

🔴 TAUSTA (7.9.2026). Kirjoitin regexeja heredocien lapi, ja `\\b` paatyi
tiedostoon LITERAALINA BACKSPACENA (0x08). Regex nayttaa oikealta editorissa
ja grepissa, mutta se ei osu koskaan - eli portti on vihrea vaarasta syysta.
Siita on jo muisti (`regexin-b-muuttuu-backspaceksi`), ja se toistui silti
saman paivan aikana kolmesti.

Muistaminen ei riita, joten tassa on mekanismi. Skannaus loysi heti kaksi
VANHAA tapausta joita kukaan ei ollut huomannut:

  tests/test_share_card_server_rows.py:420
      re.search(r"\\x08XG\\x08", arvo)   <- piti olla \\bXG\\b
      -> `assert not re.search(...)` oli aina tosi, portti inertti

  scripts/check_llms_txt_sync.py:119
      re.sub(r"...</\\x01>", ...)        <- piti olla </\\1>
      -> script/style-lohkoja ei poistettu koskaan

Sallitut kontrollimerkit ovat tab, LF ja CR.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HAKEMISTOT = ("src", "scripts", "tests", "api")
PAATTEET = (".py", ".js", ".mjs", ".ts", ".svelte", ".html", ".yml", ".yaml")
OHITA = {"node_modules", ".venv", "__pycache__", ".git", "build", "dist"}
SALLITUT = {9, 10, 13}


def _tiedostot():
    for h in HAKEMISTOT:
        for f in (ROOT / h).rglob("*"):
            if not f.is_file() or f.suffix not in PAATTEET:
                continue
            if OHITA & set(f.parts):
                continue
            yield f


def _osumat(data: bytes) -> list[tuple[int, int]]:
    """[(rivi, tavu)] kontrollimerkeista."""
    ulos, rivi = [], 1
    for b in data:
        if b == 10:
            rivi += 1
        elif (b < 32 or b == 127) and b not in SALLITUT:
            ulos.append((rivi, b))
    return ulos


def test_lahteessa_ei_ole_kontrollimerkkeja():
    ongelmat = []
    skannattu = 0
    for f in _tiedostot():
        skannattu += 1
        for rivi, b in _osumat(f.read_bytes()):
            ongelmat.append(
                f"{f.relative_to(ROOT).as_posix()}:{rivi} 0x{b:02x}")
    assert skannattu > 200, f"skanneri loysi vain {skannattu} tiedostoa"
    assert not ongelmat, (
        "kontrollimerkkeja lahteessa - yleisin syy on regexin \\b joka on "
        "kirjoitettu heredocin lapi ja muuttunut backspaceksi (0x08). Regex "
        "nayttaa oikealta mutta EI OSU KOSKAAN:\n  " + "\n  ".join(ongelmat))


def test_kontrolli_havaitsin_loytaa_backspacen():
    """NEGATIIVINEN KONTROLLI: ilman tata portti voisi olla vihrea siksi
    ettei `_osumat` loyda mitaan."""
    assert _osumat(b'r"\\bXG\\b"') == []          # oikea, escapattu
    assert _osumat(b'r"\x08XG\x08"') == [(1, 8), (1, 8)]
    assert _osumat(b"rivi1\nrivi2\x01") == [(2, 1)]
    # Tab, LF ja CR ovat sallittuja.
    assert _osumat(b"\trivi\r\n") == []
