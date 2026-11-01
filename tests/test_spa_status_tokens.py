# -*- coding: utf-8 -*-
"""SPA:n --ok / --bad -tokenit (ulkoasuohjelma WP2, 1.11.2026).

MITATTU 1.11: `--ok` ja `--bad` olivat kaytossa (GwReview, WildcardPlan,
embed/fdr, spl) mutta maarittelematta, joten selain kaytti komponenttien
vaalean teeman fallbackeja #2e7d32 (3.55:1 kortilla #171512) ja #b3261e /
#c62828 (2.79:1 / 3.24:1). Kumpikaan ei lapaissyt AA:ta (4.5:1).

Portti: (1) tokenit maaritellaan theme.css:ssa ja ratkeavat hex-arvoon,
(2) kontrasti >= 4.5:1 jokaisella pinnalla jolla ne istuvat (--bg,
--surface, --surface-2; viimeinen maaritelma voittaa kuten selaimessa),
(3) mikaan komponentti ei kanna omaa fallback-literaalia, joka ohittaisi
tokenin jos se joskus katoaa. SPA:ssa on yksi (tumma) teema: tiedostossa ei
ole prefers-color-scheme- eika data-theme-lohkoa, mika myos tarkistetaan.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPA = ROOT / "web" / "pro-spa" / "src"
THEME = SPA / "lib" / "theme.css"
SURFACES = ("--bg", "--surface", "--surface-2")


def _tokens(css: str) -> dict[str, str]:
    """Kaikki :root-maaritelmat jarjestyksessa; myohempi voittaa."""
    out: dict[str, str] = {}
    for blk in re.findall(r":root\s*\{(.*?)\}", re.sub(r"/\*.*?\*/", "", css, flags=re.S), re.S):
        for name, val in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", blk):
            out[name] = val.strip()
    return out


def _resolve(tok: dict[str, str], name: str, depth: int = 0) -> str:
    v = tok[name]
    m = re.fullmatch(r"var\((--[\w-]+)(?:,.*)?\)", v)
    if m and depth < 10:
        return _resolve(tok, m.group(1), depth + 1)
    return v


def _lum(hexv: str) -> float:
    h = hexv.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    def ch(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b_ = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b_)


def contrast(a: str, b_: str) -> float:
    la, lb = sorted((_lum(a), _lum(b_)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_ok_ja_bad_maaritelty_ja_aa_jokaisella_pinnalla():
    tok = _tokens(THEME.read_text(encoding="utf-8"))
    for name in ("--ok", "--bad"):
        assert name in tok, f"{name} puuttuu theme.css:n :rootista"
        fg = _resolve(tok, name)
        assert re.fullmatch(r"#[0-9a-fA-F]{6}", fg), (name, fg)
        for s in SURFACES:
            bg = _resolve(tok, s)
            r = contrast(fg, bg)
            assert r >= 4.5, f"{name} {fg} pinnalla {s} {bg}: {r:.2f}:1 < 4.5:1"


def test_spa_ssa_on_yksi_teema():
    css = THEME.read_text(encoding="utf-8")
    assert "prefers-color-scheme" not in css and "data-theme" not in css, (
        "SPA sai toisen teeman: laske --ok/--bad-kontrasti myos sen pinnoilla")


def test_komponentit_eivat_kanna_omaa_fallbackia():
    osumat = []
    for f in list(SPA.rglob("*.svelte")) + list(SPA.rglob("*.css")):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"var\(--(ok|bad)\s*,", line):
                osumat.append(f"{f.relative_to(SPA)}:{i}: {line.strip()}")
    assert not osumat, osumat


def test_negatiivinen_kontrolli_vanhat_fallbackit_eivat_lapaisisi():
    tok = _tokens(THEME.read_text(encoding="utf-8"))
    card = _resolve(tok, "--surface")
    for old in ("#2e7d32", "#b3261e", "#c62828"):
        assert contrast(old, card) < 4.5, old
