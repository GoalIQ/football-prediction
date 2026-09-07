# -*- coding: utf-8 -*-
"""Portti: kontrollimerkit lahdekoodissa tekevat regexista INERTIN.

🔴 TAUSTA (7.9.2026). Kirjoitin regexeja heredocien lapi, ja `\\b` paatyi
tiedostoon LITERAALINA BACKSPACENA (0x08). Regex nayttaa oikealta editorissa
ja grepissa, mutta se ei osu koskaan - eli portti on vihrea vaarasta syysta.
Siita on jo muisti (`regexin-b-muuttuu-backspaceksi`), ja se toistui silti
saman paivan aikana nelja kertaa.

Ensimmainen versio tasta portista loysi heti kaksi VANHAA tapausta:

  tests/test_share_card_server_rows.py:420
      re.search(r"\\x08XG\\x08", arvo)   <- piti olla \\bXG\\b
      -> `assert not re.search(...)` oli aina tosi, portti inertti

  scripts/check_llms_txt_sync.py:119
      re.sub(r"...</\\x01>", ...)        <- piti olla </\\1>
      -> script/style-lohkoja ei poistettu koskaan

🔴 JA SE OLI ITSE VAJAA (portin 23. kierros, B5). Paatelistalla oli
`.svelte` ja `.html`, mutta hakemistolista oli `("src","scripts","tests",
"api")` - joissa on **0 svelte-tiedostoa ja 1 html**. Julkinen sivusto
(28 juuritason `.html`) ja SPA (65 `.svelte`) olivat skannauksen
ulkopuolella, ja kaksi paatetta listalla eivat voineet osua mihinkaan.
Portti NAYTTI kattavammalta kuin oli.

Siksi alla on `test_kontrolli_jokainen_pate_ja_juuri_todella_skannataan`,
joka istuttaa tavun jokaiseen (juuri x pate) -yhdistelmaan ja vaatii etta
jokainen raportoidaan. Uusi pate ei voi jaada kuolleeksi.

Sallitut kontrollimerkit ovat tab, LF ja CR.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (juuri, rekursiivinen). Juuritason tiedostot skannataan ilman rekursiota,
# jotta emme kavele `node_modules`iin tai `.venv`iin.
JUURET: tuple[tuple[str, bool], ...] = (
    ("src", True),
    ("scripts", True),
    ("tests", True),
    ("api", True),
    ("web/pro-spa/src", True),
    (".github/workflows", True),
    (".", False),          # repojuuren *.html, *.js, *.yml
)
PAATTEET = (".py", ".js", ".mjs", ".cjs", ".ts", ".svelte", ".html", ".yml",
            ".yaml")
OHITA = {"node_modules", ".venv", "__pycache__", ".git", "build", "dist",
         ".svelte-kit"}
SALLITUT = {9, 10, 13}


def _tiedostot():
    for juuri, rekursiivinen in JUURET:
        base = ROOT / juuri
        if not base.exists():
            continue
        polut = base.rglob("*") if rekursiivinen else base.glob("*")
        for f in polut:
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


def _skannaa() -> tuple[list[str], int]:
    ongelmat, n = [], 0
    for f in _tiedostot():
        n += 1
        for rivi, b in _osumat(f.read_bytes()):
            ongelmat.append(
                f"{f.relative_to(ROOT).as_posix()}:{rivi} 0x{b:02x}")
    return ongelmat, n


def test_lahteessa_ei_ole_kontrollimerkkeja():
    ongelmat, skannattu = _skannaa()
    assert skannattu > 300, f"skanneri loysi vain {skannattu} tiedostoa"
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
    assert _osumat(b"\trivi\r\n") == []           # tab, CR, LF sallittuja


def test_kontrolli_jokainen_pate_ja_juuri_todella_skannataan(tmp_path):
    """🔴 PORTIN 23. KIERROS (B5). Paatelistalla oli kaksi patetta joita
    hakemistolista ei voinut osua. Portti NAYTTI kattavammalta kuin oli.

    Istutetaan tavu jokaiseen (juuri x pate) -yhdistelmaan ja vaaditaan
    etta jokainen raportoidaan. Uusi pate tai juuri ei voi jaada kuolleeksi
    ilman etta tama kaatuu.
    """
    istutetut = []
    try:
        for juuri, _ in JUURET:
            base = ROOT / juuri
            if not base.exists():
                continue
            for pate in PAATTEET:
                f = base / f"_kontrollimerkki_koe{pate}"
                f.write_bytes(b"x = 1  " + bytes([8]) + b"\n")
                istutetut.append(f)
        assert istutetut, "yhtaan koetiedostoa ei voitu kirjoittaa"
        ongelmat, _ = _skannaa()
        loytyi = {o.split(":")[0] for o in ongelmat}
        puuttuu = [f.relative_to(ROOT).as_posix() for f in istutetut
                   if f.relative_to(ROOT).as_posix() not in loytyi]
        assert not puuttuu, (
            "nama (juuri x pate) -yhdistelmat EIVAT ole skannauksessa:\n  "
            + "\n  ".join(puuttuu))
    finally:
        for f in istutetut:
            f.unlink(missing_ok=True)

    # Ja siivous onnistui: portti on taas vihrea.
    ongelmat, _ = _skannaa()
    assert not ongelmat, ongelmat
