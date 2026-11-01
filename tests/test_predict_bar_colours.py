# -*- coding: utf-8 -*-
"""Predictin todennakoisyyspalkki = hubin palkki (ulkoasuohjelma WP2, 1.11.2026).

MITATTU 1.11: SPA:n Predict-palkki oli amber (koti) / harmaa (tasapeli) /
tummempi harmaa (vieras), joten vierassuosikki (Arsenal 46 %) oli palkin
nakymattomin osa. Hubin ottelusivulla sama palkki on amber / himmea / teal.

Portti ratkaisee molempien pintojen CSS-muuttujat hex/rgba-arvoiksi ja vaatii
samat varit samoille rooleille. Lisaksi kumpikin voittaja-segmentti on
kirkkaampi kuin tasapeli (suosikki ei voi olla nakymattomin).
"""
from __future__ import annotations

import re
from pathlib import Path

from scripts import build_prediction_pages as bpp

ROOT = Path(__file__).resolve().parents[1]
SPA = ROOT / "web" / "pro-spa" / "src"
PREDICT = SPA / "lib" / "components" / "Predict.svelte"
THEME = SPA / "lib" / "theme.css"


def _spa_tokens() -> dict[str, str]:
    css = re.sub(r"/\*.*?\*/", "", THEME.read_text(encoding="utf-8"), flags=re.S)
    out: dict[str, str] = {}
    for blk in re.findall(r":root\s*\{(.*?)\}", css, re.S):
        for k, v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", blk):
            out[k] = v.strip()
    return out


def _resolve(val: str, tok: dict[str, str]) -> str:
    for _ in range(10):
        m = re.fullmatch(r"var\((--[\w-]+)(?:,.*)?\)", val.strip())
        if not m:
            break
        val = tok[m.group(1)]
    return re.sub(r"\s+", "", val.strip().lower())


def _decl(css: str, selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert m, selector
    b = re.search(r"background\s*:\s*([^;]+);", m.group(1))
    assert b, selector
    return b.group(1)


def spa_colours() -> dict[str, str]:
    src = PREDICT.read_text(encoding="utf-8")
    style = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", src, re.S))
    assert "opacity" not in re.search(r"\.seg-away\s*\{[^}]*\}", style).group(0)
    tok = _spa_tokens()
    return {r: _resolve(_decl(style, f".seg-{r}"), tok) for r in ("home", "draw", "away")}


def hub_colours() -> dict[str, str]:
    css = bpp.CSS
    tok = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", css))
    names = {"home": ".probbar .h", "draw": ".probbar .d", "away": ".probbar .a"}
    return {r: _resolve(_decl(css, sel), tok) for r, sel in names.items()}


def test_predict_palkki_samat_varit_kuin_hubissa():
    assert spa_colours() == hub_colours()


def test_voittajasegmentit_kirkkaampia_kuin_tasapeli():
    c = spa_colours()
    assert c["home"].startswith("#") and c["away"].startswith("#")
    assert c["draw"].startswith("rgba(") and float(c["draw"].rstrip(")").split(",")[-1]) < 0.5


def test_negatiivinen_kontrolli_vanha_palkki_ei_tasmaisi():
    vanha = {"home": "#f5c542", "draw": "#a8a29a", "away": "#a8a29a"}
    assert vanha != hub_colours()
