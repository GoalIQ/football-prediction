# -*- coding: utf-8 -*-
"""CARD-PUBLISH-NIMIPORTTI: estolistan nimi kaataa julkaisun, ei renderointia."""
from __future__ import annotations

import json

from scripts.publish_gate import blocked_names, card_spec_from_page, load_blocklist, main, spec_text


def test_blocklist_has_thiaw_with_reason():
    bl = load_blocklist()
    thiaw = [e for e in bl if e["name"] == "Thiaw"]
    assert thiaw and thiaw[0]["reason"] and thiaw[0]["since"] == "2026-08-10"


def test_whole_word_match_only():
    bl = [{"name": "Thiaw"}]
    assert blocked_names("Thiaw tops the list", bl)
    assert blocked_names("thiaw (NEW) 5.0m", bl)          # kirjainkoko
    assert not blocked_names("Mathiaw and Thiawson", bl)  # osasana ei osu
    assert not blocked_names("Tarkowski, Bassey", bl)


def test_page_spec_is_read_and_gated(tmp_path):
    spec = {"title": "TOP", "subtitle": "s", "rows": [{"rank": 1, "name": "Thiaw", "value": "1"}]}
    h = "<table data-card-spec='" + json.dumps(spec).replace("'", "&#39;") + "'><tbody></tbody></table>"
    p = tmp_path / "x.html"
    p.write_text(h, encoding="utf-8")
    assert card_spec_from_page(h)["rows"][0]["name"] == "Thiaw"
    assert "Thiaw" in spec_text(spec)
    assert main(["--page", str(p)]) == 1
    p.write_text(h.replace("Thiaw", "Bassey"), encoding="utf-8")
    assert main(["--page", str(p)]) == 0


def test_text_mode():
    assert main(["--text", "Thiaw is the pick"]) == 1
    assert main(["--text", "Isak is the pick"]) == 0
