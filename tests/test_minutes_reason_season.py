# -*- coding: utf-8 -*-
"""Portti: minuuttilipun perustelu nimeaa KAUDEN oikein joka vaiheessa (29.9.2026).

Mitattu 29.9 pro.goaliq.appin pelaajakortista (Haaland GW6): kortti sanoi
"thin Premier League sample" 225 pelaajalle joilla on pitka PL-historia.
Ohut otos tarkoittaa `cur_mins_by_player`ia: kauden aikana TAMAN kauden
minuutit, pre-seasonissa viime kauden arkiston minuutit (julkaisutarkistaja
k1 B2: kovakoodattu "this season" olisi ollut vaarin pre-seasonissa).

Saanto 6a kohta 3: sama funktio ajetaan molemmilla vaiheilla. Kohta 1:
kutsupaikka lukee funktion eika kirjoita proosaa itse.
"""
from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts" / "build_fpl_xp.py"
xpb = importlib.import_module("scripts.build_fpl_xp")


@pytest.mark.parametrize("preseason,kausi", [(False, "this season"), (True, "last season")])
@pytest.mark.parametrize("source", ["price_blend", "price_prior"])
def test_perustelu_nimeaa_vaiheen_kauden(source, preseason, kausi):
    t = xpb.minutes_reason(source, preseason)
    assert kausi in t, t
    assert "thin Premier League sample" not in t
    assert "minutes yet," not in t or not preseason, "pre-season ei voi sanoa 'yet'"


def test_ohuen_otoksen_raja_luetaan_vakiosta(monkeypatch):
    monkeypatch.setattr(xpb.xp, "PRICE_PRIOR_THIN_MINUTES", 1234)
    assert "under 1234 Premier League minutes" in xpb.minutes_reason("price_blend", False)


def test_tuntematon_lahde_ei_keksi_tekstia():
    with pytest.raises(ValueError):
        xpb.minutes_reason("override", False)


def test_kutsupaikka_lukee_funktion():
    """KUTSUPAIKKA: minutes_override_reason price_blend/price_prior-riveilla on
    `minutes_reason(<sama lahde>, preseason)`, ei kasin kirjoitettu lause."""
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    loydetty = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = [k.value if isinstance(k, ast.Constant) else None for k in node.keys]
        if "minutes_source" not in keys or "minutes_override_reason" not in keys:
            continue
        src = node.values[keys.index("minutes_source")]
        if not (isinstance(src, ast.Constant) and src.value in ("price_blend", "price_prior")):
            continue
        val = node.values[keys.index("minutes_override_reason")]
        assert isinstance(val, ast.Call) and ast.unparse(val.func) == "minutes_reason", ast.unparse(val)
        assert [ast.unparse(a) for a in val.args] == [repr(src.value), "preseason"], ast.unparse(val)
        loydetty[src.value] = True
    assert set(loydetty) == {"price_blend", "price_prior"}
