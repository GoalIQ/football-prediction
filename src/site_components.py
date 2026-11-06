# -*- coding: utf-8 -*-
"""Jaetut komponentit hubille ja SPA:lle (ulkoasuohjelma WP15 / C2, 6.11.2026).

Ensimmainen viipale on nappi `.giq-btn`. Mitattu 6.11 ennen tata: hubissa 17 ja
SPA:ssa 16 eri CTA-valitsinta. Primary oli landingilla tayteinen, /fpl:ssa ja
ottelusivuilla aariviiva ja SPA:n maksunapissa kolmas tyyli, joten landingin
ilme katkesi ennen kassaa.

MIKSI ARVOT OVAT LITERAALEJA EIKA SIVUN MUUTTUJIA: `--ink` on landingilla
tumma ja predictions.html:ssa vaalea, ja osalla juurisivuista ei ole omaa
:root-lohkoa. `var(--ink)` antaisi saman napin eri sivuilla eri varin. Arvot
tulevat `web/design-tokens.json`:sta, joka on varien ainoa lahde.

MIKSI VALITSIN ON KAKSOISLUOKKA: `.content a{color:...}` (0,1,1) voittaisi
tavallisen `.giq-btn--primary`:n (0,1,0) ja amber-teksti amberilla pohjalla
katoaisi. `.giq-btn.giq-btn--primary` on (0,2,0) ja :hover (0,3,0), joten ne
voittavat sivun yleiset linkkisaannot lahdejarjestyksesta riippumatta.

JAKELU: hub saa tyylin `SITE_NAV_CSS`:n mukana, jonka kaikki generaattorit jo
liittavat ja `build_site_chrome` kirjoittaa juurisivuille. SPA saa saman
merkkijonon tiedostosta `web/pro-spa/src/lib/giq-components.css`, jonka
`build_site_chrome` kirjoittaa. Portti: `tests/test_site_components.py`.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPA_CSS_PATH = ROOT / "web" / "pro-spa" / "src" / "lib" / "giq-components.css"

_COLORS = json.loads(
    (ROOT / "web" / "design-tokens.json").read_text(encoding="utf-8"))["colors"]

MONO = '"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace'

#: Variantti -> (taytto, reuna, teksti, painoarvo, hover-taytto, hover-reuna, hover-teksti).
#: Vain tokenien nimia, jotta portti voi todistaa etta vari on paletissa.
VARIANTS = {
    "primary": ("gold", "gold", "ink", 700, "cream", "cream", "ink"),
    "ghost": (None, "teal", "teal", 600, "teal", "teal", "ink"),
    "green": (None, "green", "green", 600, "green", "green", "ink"),
    "quiet": (None, "line-strong", "cream", 600, None, "cream", "cream"),
}


def _color(token: str | None) -> str:
    return "transparent" if token is None else _COLORS[token]


def btn_css() -> str:
    """Napin koko tyyli yhtena merkkijonona, ilman <style>-elementtia."""
    out = [
        ".giq-btn.giq-btn{display:inline-flex;align-items:center;"
        "justify-content:center;gap:8px;box-sizing:border-box;min-height:44px;"
        "max-width:100%;padding:13px 20px;background:transparent;"
        "border:2px solid transparent;border-radius:0;"
        f"font-family:{MONO};font-size:13.5px;font-weight:700;line-height:1.25;"
        "letter-spacing:.1em;text-align:center;text-decoration:none;"
        "text-transform:uppercase;cursor:pointer;}",
        f".giq-btn.giq-btn:focus-visible{{outline:2px solid {_COLORS['cream']};"
        "outline-offset:2px;}",
        ".giq-btn.giq-btn:disabled{opacity:.6;cursor:not-allowed;}",
    ]
    for name, (bg, border, fg, weight, hbg, hborder, hfg) in VARIANTS.items():
        sel = f".giq-btn.giq-btn--{name}"
        out.append(f"{sel}{{background:{_color(bg)};border-color:{_color(border)};"
                   f"color:{_color(fg)};font-weight:{weight};}}")
        out.append(f"{sel}:hover{{background:{_color(hbg)};"
                   f"border-color:{_color(hborder)};color:{_color(hfg)};}}")
    # Puhelimella isot kirjaimet ja .1em eivat mahdu: hinta katkesi kahtia
    # ("3.99 / EUR/MO") ja landingin nuoli putosi omalle rivilleen (mitattu 6.11).
    out.append("@media (max-width:480px){.giq-btn.giq-btn{padding:13px 14px;"
               "letter-spacing:.04em;}}")
    return "".join(out)


def spa_css() -> str:
    """SPA:n generoitu tiedosto. Sama tyyli kuin hubissa, otsikko edessa."""
    return ("/* GENEROITU: src/site_components.py, aja "
            "python -m scripts.build_site_chrome. Ala muokkaa kasin. */\n"
            + btn_css() + "\n")
