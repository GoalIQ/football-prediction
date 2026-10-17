"""Lainaeste (FPL scout_risks) nollaa xP:n ja minuutit estokierroksella."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import build_fpl_xp  # noqa: E402
from src.models import fpl_xp as xp  # noqa: E402


def _el(*risks):
    return {"scout_risks": list(risks)}


def test_reader_picks_only_loan_ineligible():
    e = _el({"property": "loan_ineligible", "gameweek": 12},
            {"property": "suspension_risk", "gameweek": 13},
            {"property": "loan_ineligible", "gameweek": "16"},
            {"property": "loan_ineligible", "gameweek": None})
    assert xp.loan_ineligible_gws(e) == {12, 16}


def test_reader_missing_or_bad_field():
    assert xp.loan_ineligible_gws({}) == set()
    assert xp.loan_ineligible_gws({"scout_risks": None}) == set()
    assert xp.loan_ineligible_gws({"scout_risks": ["x"]}) == set()


def test_playable_contexts_phases():
    ctxs = [{"opp": "A"}]
    blocked = {12}
    # estokierros horisontissa: ei otteluita
    assert xp.playable_contexts(ctxs, 12, blocked) == []
    # estokierros ei horisontissa / toinen kierros: ennallaan
    assert xp.playable_contexts(ctxs, 13, blocked) == ctxs
    # jo pelattu kierros (ei estoa joukossa): ennallaan
    assert xp.playable_contexts(ctxs, 5, blocked) == ctxs


def test_builder_uses_reader_and_filter():
    src = inspect.getsource(build_fpl_xp.main)
    assert "xp.loan_ineligible_gws(e)" in src
    assert "xp.playable_contexts(" in src
