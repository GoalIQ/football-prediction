# -*- coding: utf-8 -*-
"""SPL-sivun datapohjalause ei saa erota artefaktista (3.9.2026).

Sivu sanoi "fitted on two seasons of SPL results" kun malli fittasi jo
kolmea kausiavainta ja 36 taman kauden ottelua. Luku oli tosi kun se
kirjoitettiin. CLAUDE.md saanto 6a: kovakoodattu luku joka kuvaa liikkuvaa
tilaa on suunnitteluvirhe, ei kirjoitusvirhe.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.update_spl_page_basis import (BEGIN, END, basis_html,
                                           seasons_and_matches)

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "spl.html"
XP = ROOT / "data" / "spl_xp_projections.json"


def _meta() -> dict:
    return json.loads(XP.read_text(encoding="utf-8")).get("meta") or {}


def test_page_carries_the_generated_block():
    html = PAGE.read_text(encoding="utf-8")
    assert BEGIN in html and END in html, (
        "spl.html:sta puuttuu GEN:SPL-BASIS-lohko — aja "
        "`python -m scripts.update_spl_page_basis`")


def test_page_matches_the_artefact():
    html = PAGE.read_text(encoding="utf-8")
    a, b = html.index(BEGIN), html.index(END) + len(END)
    assert html[a:b] == basis_html(_meta()), (
        "spl.html:n datapohjalause on eri kuin artefakti sanoo. Aja "
        "`python -m scripts.update_spl_page_basis` (ala korjaa kasin).")


def test_no_hardcoded_season_count_survives_outside_the_block():
    """Sama vaite kahdessa paikassa vanhenee toisesta. JSON-LD:n FAQ sanoi
    myos 'two seasons' — se on nyt sidottu samaan lukuun."""
    html = PAGE.read_text(encoding="utf-8")
    a, b = html.index(BEGIN), html.index(END) + len(END)
    muu = html[:a] + html[b:]
    kaudet, _ = seasons_and_matches(_meta())
    vaarat = {1: "one season", 2: "two seasons", 3: "three seasons",
              4: "four seasons"}
    vaarat.pop(kaudet, None)
    loydot = [s for s in vaarat.values() if s in muu]
    assert not loydot, (
        f"spl.html vaittaa muualla {loydot}, artefakti sanoo {kaudet} "
        "kautta. Paivita FAQ/JSON-LD samasta luvusta.")


def test_the_sentence_says_what_updates_per_round_and_what_does_not():
    """Villen kysymys 3.9: 'oppiiko se kans kierroksista'. Vastaus on eri
    joukkuevoimille ja minuuteille, ja sen on luettava sivulla."""
    t = re.sub(r"<[^>]+>", " ", basis_html(_meta()))
    assert "refitted on every result" in t or "refit on every result" in t
    assert "no per-round" in t and "season totals" in t


def test_generator_reads_the_numbers_and_does_not_invent_them():
    meta = {"team_strength_source": "GoalIQ Dixon-Coles, SPL results (ESPN) "
                                    "['2425', '2526', '2627'] incl. 36 played",
            "inseason_matches_in_fit": 36}
    assert seasons_and_matches(meta) == (3, 36)
    t = re.sub(r"<[^>]+>", " ", basis_html(meta))
    assert "three seasons" in t and "36 matches" in t
    # negatiivinen kontrolli: kausi ei ole alkanut -> ei keksitty lukua
    tyhja = re.sub(r"<[^>]+>", " ", basis_html(
        {"team_strength_source": "['2425', '2526']", "inseason_matches_in_fit": 0}))
    assert "two seasons" in tyhja and "0 matches" not in tyhja
