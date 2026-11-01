# -*- coding: utf-8 -*-
"""SPA:n varisaannot (theme.css) komponenteissa (ulkoasuohjelma WP2, 1.11.2026).

theme.css: "teal — voitot, linkit; coral — hitit, pudotukset,
saatavuusliput" ja "primary on tayttonappi ... Sivulla saa olla YKSI".

MITATTU 1.11: My teamin "Change team" ja "Rate my draft" olivat coralia
(`.linklike { color: var(--giq-rust) }`, sama viidessa komponentissa), ja
ToolRow'n valittu segmentti ("Squad | Transfers | Chips", "Players | Teams")
oli amber-taytto. Coral linkkina lukee tappiona, ja navigaation taytto kilpailee
sivun ainoan ostonapin kanssa. Syy: 2.8:n magenta->rust-vaihto korvasi myos
linkkien ja valintatilojen vareja.

Portti: (1) mikaan linkki- tai toimintoselektori (linklike, *-btn, summary,
:hover, valittu tila .active / aria-current / aria-selected) ei vari tekstia
coraliksi, (2) mikaan valintatila ei saa amber-taustaa.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPA = ROOT / "web" / "pro-spa" / "src"

CORAL = re.compile(r"(?<![-\w])color\s*:\s*var\(--(giq-rust|giq-coral|negative)\)")
AMBER_BG = re.compile(r"background(?:-color)?\s*:\s*var\(--(accent|accent-strong|giq-gold|giq-gold-deep)\)")
INTERACTIVE = re.compile(r"linklike|(?:^|[\s.-])btn\b|-btn\b|\bsummary\b|:hover|clear-draft|sortbtn")
SELECTED = re.compile(r"\.active\b|aria-current|aria-selected|\[aria-pressed")


def _rules(path: Path):
    s = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
    if path.suffix == ".svelte":
        s = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", s, re.S))
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", s):
        yield " ".join(m.group(1).split()), m.group(2)


def _files():
    return list(SPA.rglob("*.svelte")) + list(SPA.rglob("*.css"))


def osumat(files=None, base: Path = SPA):
    coral, amber = [], []
    for f in files or _files():
        for sel, body in _rules(f):
            for part in sel.split(","):
                part = part.strip()
                if (INTERACTIVE.search(part) or SELECTED.search(part)) and CORAL.search(body):
                    coral.append(f"{f.relative_to(base)}: {part}")
                if SELECTED.search(part) and AMBER_BG.search(body):
                    amber.append(f"{f.relative_to(base)}: {part}")
    return coral, amber


def test_linkit_ja_valintatilat_eivat_ole_coralia():
    coral, _ = osumat()
    assert not coral, coral


def test_valittu_navigaatiosegmentti_ei_ole_amber_taytto():
    _, amber = osumat()
    assert not amber, amber


def test_negatiivinen_kontrolli(tmp_path):
    f = tmp_path / "X.svelte"
    f.write_text("<style>\n.linklike { color: var(--giq-rust); }\n"
                 ".seg a.active { color: var(--accent-contrast); background: var(--accent); }\n"
                 ".badge.down { color: var(--giq-rust); }\n</style>", encoding="utf-8")
    coral, amber = osumat([f], base=tmp_path)
    assert coral == ["X.svelte: .linklike"], coral
    assert amber == ["X.svelte: .seg a.active"], amber
