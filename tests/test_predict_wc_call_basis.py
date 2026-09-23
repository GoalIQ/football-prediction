# -*- coding: utf-8 -*-
"""Maajoukkue-ennuste ei lainaa seuramallin osumaprosenttia (23.9.2026).

MIKSI: /api/predict-wc palautti saman `call`-kentan kuin seuramalli, eli
below_hit_pct = seuralokista mitattu "nimetty puoli voitti 48 %". Web ja
mobiili nayttavat sen "Too close to call" -laatikossa maajoukkueottelun alla,
vaikka samalla ruudulla lukee "these predictions aren't in the public track
record". Mitattu 24.-25.9 otoksesta: 2/14 UNL-ottelua too_close
(Kosovo-Republic of Ireland gap 8, Italy-Belgium gap 7).

Portti: funktio (below_hit_pct None, suosikkilogiikka ennallaan) JA
kutsupaikka (predict_wc kayttaa maajoukkuelukijaa, ei call_statea suoraan).
"""
import re
from pathlib import Path

from src.models.call_margin import call_state, call_state_national

ROOT = Path(__file__).resolve().parent.parent
MARGIN = {"margin_pp": 16, "decisive_below_pct": 48, "measured_at": "2026-09-23"}


def test_national_call_has_no_hit_rate_but_same_favourite_rule():
    for p in [(0.40, 0.27, 0.33), (0.83, 0.13, 0.04), (0.20, 0.25, 0.55)]:
        club = call_state(*p, margin=MARGIN)
        nat = call_state_national(*p, margin=MARGIN)
        assert nat["below_hit_pct"] is None
        assert nat["basis"] == "club_log"
        for k in ("favourite", "too_close", "gap_pp", "margin_pp", "reason"):
            assert nat[k] == club[k], (p, k)


def test_negative_control_club_call_does_carry_the_hit_rate():
    """Ilman tata edellinen lapaisisi, vaikka artefakti ei antaisi lukua."""
    assert call_state(0.40, 0.27, 0.33, margin=MARGIN)["below_hit_pct"] == 48


def test_predict_wc_uses_the_national_reader():
    src = (ROOT / "api" / "main.py").read_text(encoding="utf-8")
    i = src.index("def predict_wc(")
    j = src.find("\n@app.", i)
    body = src[i:j if j > 0 else None]
    assert "call=call_state_national(" in body
    assert not re.search(r"call=call_state\(", body)
