"""LUCK-PITCH-tuloskortin lauseet: mobiili ja SPA sanovat saman (2.9.2026).

Julkaisutarkistaja hylkasi kortin tekstin kolmella kierroksella, ja jokainen
korjaus piti tehda kahteen tiedostoon kasin:
  goaliq-app/lib/fantasyResultCopy.ts              (mobiili, testattu nodella)
  web/pro-spa/src/lib/components/TeamPitchManager.svelte  (SPA, ei testia)

Tama testi lukee molemmat ja vertaa funktioiden `projectionLine`,
`swingInfo` ja `swingLineEn` KAIKKIA merkkijonoliteraaleja: jos toiseen
pintaan korjataan lause ja toinen jaa, joukot eroavat ja testi kaatuu.
Rungon muotoilua (prettier, tyyppinimet) ei verrata - se vaihtelee eika
ole se mika lukijalle nakyy.

Sama kaava kuin tests/test_luck_parity.py (kynnysvakiot). Mobiilirepo on
sisarkansio; jos sita ei ole (CI), testi ohitetaan eika kaadu.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

HERE = Path(__file__).resolve()
WEB = HERE.parents[1] / "web" / "pro-spa" / "src" / "lib" / "components" / "TeamPitchManager.svelte"
MOBILE = HERE.parents[2] / "goaliq-app" / "lib" / "fantasyResultCopy.ts"

FUNCS = ("projectionLine", "swingInfo", "swingLineEn")


def _function_body(src: str, name: str) -> str:
    m = re.search(r"function " + name + r"\(", src)
    assert m, f"{name} puuttuu"
    i = src.index("{", m.end())
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
    raise AssertionError(f"{name}: sulkeva aaltosulku puuttuu")


def _literals(body: str) -> set[str]:
    out: set[str] = set()
    for m in re.finditer(r"`([^`]*)`|'([^']*)'", body):
        s = m.group(1) if m.group(1) is not None else m.group(2)
        if s:
            out.add(s)
    return out


@pytest.mark.skipif(not MOBILE.exists(), reason="goaliq-app ei ole sisarkansiona")
@pytest.mark.parametrize("name", FUNCS)
def test_kortin_lauseet_ovat_samat_molemmilla_pinnoilla(name: str):
    web = _literals(_function_body(WEB.read_text(encoding="utf-8"), name))
    mob = _literals(_function_body(MOBILE.read_text(encoding="utf-8"), name))
    assert web == mob, (
        f"{name}: vain webissa {sorted(web - mob)} · vain mobiilissa {sorted(mob - web)}"
    )


def test_hylatyt_sanamuodot_eivat_palaa():
    """Portin hylkaamat muodot (k1-k3) eivat saa palata kummallekaan pinnalle.
    Kommentit riisutaan ensin: niissa hylatty muoto SAA olla perusteluna."""
    for path in (WEB, MOBILE):
        if not path.exists():
            continue
        src = path.read_text(encoding="utf-8")
        src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
        src = re.sub(r"//[^\n]*", "", src)
        src = re.sub(r"<!--.*?-->", "", src, flags=re.DOTALL)
        for bad in ("alone was", "of that", "of it.", "logged before kickoff, graded in public"):
            assert bad not in src, f"{path.name}: hylatty sanamuoto '{bad}' on yha koodissa"
