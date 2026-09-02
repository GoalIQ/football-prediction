"""PAITAPAIVITYS 2.9: sama paita joka pinnalla.

Geometria (runko, hihat, hihansuut, kaulus) on kopioitu viiteen renderoijaan,
koska repot ja kielet eivat voi jakaa moduulia: team_colors.py (python-SVG ja
PIL), TeamKit.svelte, shareCard.ts (canvas), ja mobiilin TeamKit.tsx (eri repo,
tarkistetaan vain jos polku on olemassa tallä koneella). Kuviotaulu on
teamKits.ts:ssa (kaksi identtista kopiota) ja team_colors._KIT_BY_SHORT:issa.

Ilman tata testia yksi renderoija jaa vanhaan siluettiin hiljaa — sama
"kaksi totuutta" -vikaluokka kuin vareissa 17.7 ja WHY-labeleissa.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models import team_colors as tc  # noqa: E402

SVELTE = ROOT / "web/pro-spa/src/lib/components/TeamKit.svelte"
CANVAS = ROOT / "web/pro-spa/src/lib/shareCard.ts"
KITS_WEB = ROOT / "web/pro-spa/src/lib/teamKits.ts"
MOBILE_DIR = ROOT.parent / "goaliq-app"
MOBILE_TSX = MOBILE_DIR / "components/TeamKit.tsx"
KITS_MOBILE = MOBILE_DIR / "lib/teamKits.ts"


def _ts_const(src: str, name: str) -> str:
    """Poimi `const NAME = '...' + '...';` -merkkijono (yksi tai kaksi palaa)."""
    m = re.search(name + r"\s*=\s*((?:'[^']*'\s*\+?\s*)+);", src)
    assert m, f"{name} puuttuu"
    return "".join(re.findall(r"'([^']*)'", m.group(1)))


def _norm(d: str) -> str:
    return " ".join(d.split())


EXPECTED = {
    "JERSEY": _norm(tc._JERSEY),
    "SLEEVE_L": _norm(tc._SLEEVE_L),
    "SLEEVE_R": _norm(tc._SLEEVE_R),
    "CUFF_L": _norm(tc._CUFF_L),
    "CUFF_R": _norm(tc._CUFF_R),
    "COLLAR": _norm(tc._COLLAR),
}


def _check(src: str, names: dict[str, str], where: str) -> None:
    for key, ts_name in names.items():
        got = _norm(_ts_const(src, ts_name))
        assert got == EXPECTED[key], f"{where}: {ts_name} eroaa team_colors.py:sta"


def test_svelte_geometry_matches_python():
    src = SVELTE.read_text(encoding="utf-8")
    _check(src, {"JERSEY": "JERSEY_PATH", "SLEEVE_L": "SLEEVE_LEFT", "SLEEVE_R": "SLEEVE_RIGHT",
                 "CUFF_L": "CUFF_LEFT", "CUFF_R": "CUFF_RIGHT", "COLLAR": "COLLAR_PATH"}, "TeamKit.svelte")


def test_canvas_geometry_matches_python():
    src = CANVAS.read_text(encoding="utf-8")
    _check(src, {"JERSEY": "JERSEY", "SLEEVE_L": "SLEEVE_L", "SLEEVE_R": "SLEEVE_R",
                 "CUFF_L": "CUFF_L", "CUFF_R": "CUFF_R", "COLLAR": "COLLAR"}, "shareCard.ts")


def test_mobile_geometry_matches_python():
    if not MOBILE_TSX.exists():
        import pytest
        pytest.skip("goaliq-app ei ole tässä koneessa")
    src = MOBILE_TSX.read_text(encoding="utf-8")
    _check(src, {"JERSEY": "JERSEY_PATH", "SLEEVE_L": "SLEEVE_LEFT", "SLEEVE_R": "SLEEVE_RIGHT",
                 "CUFF_L": "CUFF_LEFT", "CUFF_R": "CUFF_RIGHT", "COLLAR": "COLLAR_PATH"}, "TeamKit.tsx")


def _ts_kit_table(src: str) -> dict[str, tuple[str, str]]:
    return {m.group(1): (m.group(2), m.group(3).upper())
            for m in re.finditer(r"^\s*([A-Z]{3}): \{ pattern: '(\w+)', secondary: '(#[0-9A-Fa-f]{6})' \}",
                                 src, re.M)}


def test_kit_table_web_matches_python():
    web = _ts_kit_table(KITS_WEB.read_text(encoding="utf-8"))
    py = {k: (p, (s or "").upper()) for k, (p, s) in tc._KIT_BY_SHORT.items()}
    assert web == py, {k: (web.get(k), py.get(k)) for k in set(web) | set(py) if web.get(k) != py.get(k)}


def test_kit_table_mobile_identical_to_web():
    if not KITS_MOBILE.exists():
        import pytest
        pytest.skip("goaliq-app ei ole tässä koneessa")
    a = KITS_WEB.read_text(encoding="utf-8").replace("\r\n", "\n")
    b = KITS_MOBILE.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert a == b, "teamKits.ts eroaa repojen valilla"


def test_all_pl_2627_teams_curated():
    """Jokaisella 26/27 PL-seuralla on rivi: yksivarisellakin paidalla kaulus ja
    hihansuut tarvitsevat kuratoidun varin."""
    pl = {"ARS", "AVL", "BHA", "BOU", "BRE", "CHE", "COV", "CRY", "EVE", "FUL",
          "HUL", "IPS", "LEE", "LIV", "MCI", "MUN", "NEW", "NFO", "SUN", "TOT"}
    missing = sorted(pl - set(tc._KIT_BY_SHORT))
    assert not missing, missing
