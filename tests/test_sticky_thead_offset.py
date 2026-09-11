# -*- coding: utf-8 -*-
"""Portti: sticky-otsikkorivilla EI saa olla palkin korkeutta offsetina.

🔴 MITATTU VIKA 11.9.2026 (Villen havainto "listat katkeaa"). Lisasin
`thead th { top: var(--bar-h) }` jotta otsikkorivi ei jaisi uuden 52 px:n
ylapalkin alle. Se oli vaarin: `.table-wrap` on `overflow-x: auto`, eli se on
OMA scrollport, ja sticky-offset mitataan lahimpaan scrollporttiin. Otsikko
asettui 52 px kaaren sisapuolelle ja PEITTI rivin 1. Mitattu livena
pro.goaliq.app/players/leaders: `thBottom` 760, `row1Top` 708, eli osuma 52 px
tasan. Kayttajalle se nakyi niin, etta listan kohdalla 1 luki otsikkorivi.

Vika ei nay yhdessakaan muussa portissa: CSS on validia, svelte-check on
vihrea, ja komponenttitestit eivat renderoi selaimessa. Siksi tama portti
lukee saantoa suoraan teemasta.

Vaite: `thead th`in `top` on 0 (tai puuttuu), koska kaari rullaa itse palkin
alle. Jos joku palauttaa offsetin, taman on kaaduttava ja kirjoittajan on
mitattava rivi 1 uudelleen.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "web" / "pro-spa" / "src" / "lib" / "theme.css"


def _css() -> str:
    assert THEME.exists(), f"{THEME} puuttuu"
    return THEME.read_text(encoding="utf-8")


def thead_top_arvot(css: str) -> list[str]:
    """`thead th`-saantojen `top`-arvot, kommentit riisuttuna."""
    puhdas = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    ulos = []
    for m in re.finditer(r"thead\s+th\s*\{(.*?)\}", puhdas, flags=re.S):
        for t in re.findall(r"(?<![\w-])top\s*:\s*([^;]+);", m.group(1)):
            ulos.append(t.strip())
    return ulos


def test_portti_ei_mittaa_tyhjaa() -> None:
    css = _css()
    assert "thead th" in css
    assert thead_top_arvot(css), "thead th -saantoa ei loytynyt"


def test_sticky_otsikolla_ei_ole_palkkioffsetia() -> None:
    huonot = [t for t in thead_top_arvot(_css()) if t not in ("0", "0px")]
    assert not huonot, (
        f"thead th top = {huonot}. `.table-wrap` on oma scrollport, joten "
        "offset tyontaa otsikkorivin kaaren sisalle ja peittaa rivin 1. "
        "Jos tama on tarkoitus, mittaa ensin selaimella etta rivi 1 nakyy."
    )


def test_negatiivinen_kontrolli_offset_kaataa() -> None:
    """Ilman tata portti voisi lapaista siksi, ettei jasennin loyda saantoa."""
    rikottu = _css().replace("thead th {", "thead th {\n\ttop: var(--bar-h, 0px);", 1)
    huonot = [t for t in thead_top_arvot(rikottu) if t not in ("0", "0px")]
    assert huonot == ["var(--bar-h, 0px)"], huonot


def test_negatiivinen_kontrolli_kommentti_ei_riita() -> None:
    """Kommentissa oleva `top: 52px` ei saa laukaista porttia."""
    rikottu = _css().replace("thead th {", "/* top: 52px */\nthead th {", 1)
    assert [t for t in thead_top_arvot(rikottu) if t not in ("0", "0px")] == []
