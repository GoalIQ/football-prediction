# -*- coding: utf-8 -*-
"""Portti: minuuttilipun perustelu sanoo KAUDEN (29.9.2026, kuvaverifiointi).

Mitattu 29.9 pro.goaliq.appin pelaajakortista (Haaland GW6): kortti sanoi
samassa nakymassa "The model's view on starting, based on the player's own PL
minutes" (data_basis pl_history, kausien yli kantava historia) JA
"Part model, part price: thin Premier League sample" (minutes_source
price_blend). Ohut otos tarkoittaa TAMAN kauden minuutteja alle
PRICE_PRIOR_THIN_MINUUTIN, mutta teksti ei sanonut sita: 225 pelaajaa
artefaktissa kantoi molemmat lauseet, mukana eniten omistetut.

Portti lukee build_fpl_xp.py:n KUTSUPAIKAN (dict-literaali jossa
minutes_source on price_blend / price_prior), ei erillista funktiota.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts" / "build_fpl_xp.py"


def _perustelut() -> dict[str, ast.expr]:
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    out: dict[str, ast.expr] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = [k.value if isinstance(k, ast.Constant) else None for k in node.keys]
        if "minutes_source" not in keys or "minutes_override_reason" not in keys:
            continue
        src = node.values[keys.index("minutes_source")]
        if isinstance(src, ast.Constant) and src.value in ("price_blend", "price_prior"):
            out[src.value] = node.values[keys.index("minutes_override_reason")]
    return out


def _teksti(e: ast.expr) -> str:
    if isinstance(e, ast.Constant):
        return str(e.value)
    if isinstance(e, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in e.values)
    raise AssertionError(f"perustelu ei ole literaali: {ast.dump(e)[:80]}")


def test_molemmat_perustelut_loytyvat():
    p = _perustelut()
    assert set(p) == {"price_blend", "price_prior"}, p.keys()


def test_perustelu_rajaa_kauteen():
    for nimi, e in _perustelut().items():
        t = _teksti(e)
        assert "this season" in t, (nimi, t)
        assert "thin Premier League sample" not in t, (nimi, t)


def test_ohuen_otoksen_raja_luetaan_vakiosta():
    """Raja ei saa olla proosaa: jos PRICE_PRIOR_THIN_MINUTES muuttuu, lause seuraa."""
    e = _perustelut()["price_blend"]
    assert isinstance(e, ast.JoinedStr), "perustelu ei lue rajaa vakiosta"
    nimet = [ast.unparse(v.value) for v in e.values if isinstance(v, ast.FormattedValue)]
    assert nimet == ["xp.PRICE_PRIOR_THIN_MINUTES"], nimet
