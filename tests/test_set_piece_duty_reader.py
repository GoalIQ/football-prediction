# -*- coding: utf-8 -*-
"""Erikoistilannevastuu = 1. tai 2. ottaja, yksi lukija (WHY-SETPIECE-KYNNYS).

🔴 MITATTU 24.9.2026 (julkaisutarkistaja). "Why this pick" -lause
(`data/fpl_why.json`) sanoi "...and set piece duties" 12 pelaajasta joiden
paras FPL-jarjestys oli 3. tai huonompi (Odegaard 3/-/4, Gomez -/-/5,
Rashford -/-/3, L.Miley -/5/-). Syy: `build_fpl_why.player_facts` hyvaksyi
minka tahansa jarjestysnumeron (`if sp.get(k)`), kun kortti, SPA:n badget ja
`driver_facts` kayttivat rajaa 1-2. Sama loysa kynnys blokattiin
ilmaissivulta jo 10.9.

Nyt molemmat lukevat `fpl_xp.set_piece_duties`ia. Portit:
1. lukijan raja synteettisilla jarjestyksilla (1, 2, 3, 5, puuttuva, roska)
2. why-faktalohko ja runkolause eivat vaita vastuuta 3. ottajalle
3. sama ehto kaikilla artefaktin pelaajilla (ei vain esimerkeilla)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build_fpl_why import player_facts, template_drivers, template_sentence  # noqa: E402
from src.models.fpl_xp import driver_facts, set_piece_duties  # noqa: E402

ARTEFAKTI = ROOT / "data" / "fpl_xp_projections.json"


def _pelaaja(sp: dict) -> dict:
    return {"id": 7, "web_name": "Testi", "team": "Arsenal", "pos": "MID",
            "price": 6.0, "owned_pct": 5.0, "xmins": 80.0, "p_start": 0.9,
            "xp_horizon_total": 20.0, "gameweeks": [], "set_pieces": sp}


@pytest.mark.parametrize("sp,odotus", [
    ({"pens": 1, "corners": None, "fk": None}, {"pens": 1}),
    ({"pens": None, "corners": 2, "fk": 2}, {"corners": 2, "fk": 2}),
    ({"pens": 3, "corners": None, "fk": 4}, {}),          # Odegaard 3/-/4
    ({"pens": None, "corners": None, "fk": 5}, {}),       # Gomez -/-/5
    ({"pens": 2, "corners": 3, "fk": 1}, {"pens": 2, "fk": 1}),
    ({"pens": 0, "corners": True, "fk": "1"}, {}),        # roska ei ole vastuu
    ({}, {}),
    (None, {}),
])
def test_lukijan_raja_on_toinen_ottaja(sp, odotus):
    assert set_piece_duties(sp) == odotus


def test_kolmas_ottaja_ei_saa_vastuuta_why_lauseessa():
    """MUTAATIO: palauta `takers = [k for k in (...) if sp.get(k)]`
    player_factsiin -> punainen."""
    facts = player_facts(_pelaaja({"pens": 3, "corners": None, "fk": 4}), 6, 6)
    assert "set_piece_duties" not in facts
    assert "set piece" not in template_sentence(facts)
    assert "set_pieces" not in template_drivers(facts)


def test_positiivinen_kontrolli_ensimmainen_ottaja_saa_vastuun():
    """Ilman tata portti lapaisisi myos jos lause ei koskaan mainitsisi
    erikoistilanteita."""
    facts = player_facts(_pelaaja({"pens": 1, "corners": 2, "fk": None}), 6, 6)
    assert facts.get("set_piece_duties") == ["pens", "corners"]
    assert "set piece" in template_sentence(facts)


def test_driver_facts_ja_why_ovat_samaa_mielta():
    """Kaksi pintaa, yksi raja: jos toinen nimeaa ottajan, toisenkin on."""
    for sp in ({"pens": 3, "corners": None, "fk": 4},
               {"pens": None, "corners": 2, "fk": None},
               {"pens": 1, "corners": 1, "fk": 1}):
        p = _pelaaja(sp)
        assert (("set_piece_duties" in player_facts(p, 6, 6))
                == ("set_pieces" in driver_facts(p))), sp


@pytest.mark.skipif(not ARTEFAKTI.exists(), reason="artefakti puuttuu")
def test_koko_artefakti_ei_vaita_vastuuta_kolmannelle():
    """Mitattu koko poolista, ei esimerkeista: jokainen pelaaja jonka paras
    jarjestys on 3. tai huonompi."""
    d = json.loads(ARTEFAKTI.read_text(encoding="utf-8"))
    rikkeet, kolmansia = [], 0
    for p in d.get("players") or []:
        sp = p.get("set_pieces") or {}
        orders = [v for v in sp.values() if isinstance(v, (int, float))
                  and not isinstance(v, bool)]
        if not orders or min(orders) < 3:
            continue
        kolmansia += 1
        facts = player_facts(p, 6, 6)
        if "set_piece_duties" in facts or "set piece" in template_sentence(facts):
            rikkeet.append(p.get("web_name"))
    assert not rikkeet, rikkeet
    assert kolmansia > 0, "artefaktissa ei yhtaan 3.+ ottajaa - testi ei mittaa"
