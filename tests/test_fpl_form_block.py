# -*- coding: utf-8 -*-
"""PLAYER-FORM (27.8): FPL:n form-lohko emittoidaan vain kun se tarkoittaa
jotain. Fail-closed: esikausi tai 0 pelattua kierrosta 30 pv ikkunassa ->
None. Luku bootstrapista sellaisenaan, otoskoko kierroksina."""
from __future__ import annotations

import datetime as _dt

from scripts.build_fpl_xp import FORM_BASIS, _form_block

NOW = _dt.datetime(2026, 8, 27, 12, 0, tzinfo=_dt.timezone.utc)


def _boot(*events):
    return {"events": [
        {"id": i + 1, "finished": fin, "deadline_time": dl}
        for i, (fin, dl) in enumerate(events)]}


def test_live_season_one_gw_in_window():
    boot = _boot((True, "2026-08-21T17:30:00Z"), (False, "2026-08-28T17:30:00Z"))
    out = _form_block({"form": "17.0"}, boot, preseason=False, now=NOW)
    assert out == {"value": 17.0, "gws": 1, "basis": FORM_BASIS}


def test_preseason_is_none_even_if_bootstrap_carries_a_number():
    boot = _boot((True, "2026-08-21T17:30:00Z"))
    assert _form_block({"form": "5.5"}, boot, preseason=True, now=NOW) is None


def test_no_finished_gw_in_window_is_none():
    """Negatiivinen kontrolli: pelattu kierros 31 pv sitten ei ole ikkunassa,
    ja tuleva kierros ei ole pelattu -> ei rivia, vaikka form > 0."""
    boot = _boot((True, "2026-07-20T17:30:00Z"), (False, "2026-08-28T17:30:00Z"))
    assert _form_block({"form": "3.0"}, boot, preseason=False, now=NOW) is None


def test_window_counts_only_finished_gws_inside_30_days():
    boot = _boot((True, "2026-07-20T17:30:00Z"),   # ulkona
                 (True, "2026-08-14T17:30:00Z"),   # sisalla
                 (True, "2026-08-21T17:30:00Z"),   # sisalla
                 (False, "2026-08-28T17:30:00Z"))  # ei pelattu
    out = _form_block({"form": "4.5"}, boot, preseason=False, now=NOW)
    assert out["gws"] == 2 and out["value"] == 4.5


def test_zero_form_is_emitted_as_zero_not_hidden():
    """0.0 pistetta on tieto (pelasi, ei pisteita), ei puuttuva arvo."""
    boot = _boot((True, "2026-08-21T17:30:00Z"))
    out = _form_block({"form": "0.0"}, boot, preseason=False, now=NOW)
    assert out is not None and out["value"] == 0.0
