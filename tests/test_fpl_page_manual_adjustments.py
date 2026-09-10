# -*- coding: utf-8 -*-
"""MODEL-OVERRIDES-JULKISUUS (10.9.2026): kasin tehdyt joukkuesaadot
(fpl_xp_projections.meta.team_overrides) nakyvat goaliq.app/fpl-sivun
metodologiassa taulukkona. Portti kaatuu jos payloadissa on override-avain
tai -rivi jota sivu ei renderoi.
"""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

import pytest

from scripts.build_fpl_page import MANUAL_ADJUSTMENT_KEYS, manual_adjustments_html

ROOT = Path(__file__).resolve().parents[1]

ROW = {"team": "Newcastle United", "found": True, "attack_delta": -0.1,
       "defence_delta": 0.05, "attack_mult": 0.9, "review_by": "2026-10-05",
       "reason": "Lost three starters & a manager"}


def _xp(rows):
    return {"meta": {"team_overrides": rows}}


def test_empty_list_says_none():
    html = manual_adjustments_html(_xp([]))
    assert "Manual adjustments in the current projection" in html
    assert "None." in html and "<table" not in html


def test_missing_block_is_not_reported_as_none():
    html = manual_adjustments_html({"meta": {}})
    assert "None." not in html and "does not carry" in html
    assert "None." not in manual_adjustments_html(None)


def test_every_override_field_is_on_the_page():
    html = manual_adjustments_html(_xp([ROW]))
    assert "<table" in html
    assert "Newcastle United" in html
    assert "-0.10" in html and "+0.05" in html and "x0.90" in html
    assert "2026-10-05" in html and "Review by" in html
    assert "Lost three starters &amp; a manager" in html
    assert "<td>yes</td>" in html


def test_unmatched_team_is_said_not_hidden():
    html = manual_adjustments_html(_xp([dict(ROW, found=False)]))
    assert "no, team name not matched" in html


def test_missing_mult_is_not_rendered_as_one():
    old = {k: v for k, v in ROW.items() if k != "attack_mult"}
    html = manual_adjustments_html(_xp([old]))
    assert "x1.00" not in html and "not recorded" in html


def test_page_template_places_block_under_methodology():
    src = (ROOT / "scripts" / "build_fpl_page.py").read_text(encoding="utf-8")
    i_meth = src.index('<h2 id="methodology">Methodology</h2>')
    i_call = src.index("{manual_adjustments_html(xp)}")
    i_tools = src.index('<h2 id="tools">')
    assert i_meth < i_call < i_tools


def test_builder_keys_equal_page_keys():
    """Builderi kirjoittaa taman avainjoukon; sivu osaa taman avainjoukon.
    Uusi avain toiseen ilman toista kaatuu tassa."""
    src = (ROOT / "scripts" / "build_fpl_xp.py").read_text(encoding="utf-8")
    m = re.search(r'"team_overrides": \[\s*\{k: r\.get\(k\) for k in \((.*?)\)\}', src, re.S)
    assert m, "build_fpl_xp: team_overrides-lohko ei ole tunnistettavassa muodossa"
    builder_keys = set(re.findall(r'"([a-z_]+)"', m.group(1)))
    assert builder_keys == set(MANUAL_ADJUSTMENT_KEYS), (
        f"vain builderissa {sorted(builder_keys - set(MANUAL_ADJUSTMENT_KEYS))}, "
        f"vain sivulla {sorted(set(MANUAL_ADJUSTMENT_KEYS) - builder_keys)}")


def test_live_payload_overrides_are_all_rendered():
    path = ROOT / "data" / "fpl_xp_projections.json"
    if not path.exists():
        pytest.skip("ei payloadia")
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = (doc.get("meta") or {}).get("team_overrides")
    html = manual_adjustments_html(doc)
    if rows is None:
        pytest.skip("payload ilman team_overrides-lohkoa (rakennettu ennen lohkoa)")
    if not rows:
        assert "None." in html
        return
    for r in rows:
        extra = set(r) - set(MANUAL_ADJUSTMENT_KEYS)
        assert not extra, f"payloadissa avain jota sivu ei renderoi: {sorted(extra)}"
        assert r["team"] in html and str(r["review_by"]) in html
        assert escape(str(r.get("reason") or "")[:40]) in html


def test_negative_control_unknown_key_is_caught():
    row = dict(ROW, xmins_mult=0.8)
    assert set(row) - set(MANUAL_ADJUSTMENT_KEYS) == {"xmins_mult"}
