# -*- coding: utf-8 -*-
"""Nousija-alaviite tulee YHDESTA paikasta, ei kolmesta kovakoodauksesta.

30.8 julkaisutarkistaja: `render_projected_xi_card.py` ja
`render_standouts_card.py` kirjoittivat molemmat merkkijonon "one PL match".
Oikea arvo on datassa (`team_confidence.own_matches`), se on 1 tanaan ja 2 kun
GW2 gradataan ma 31.8 - eli VAARIN silla hetkella kun kortit julkaistaan
(standouts 3.9, projected XI 4.9).

Sama kovakoodaus shippasi jo GW2-kortilla 25.8 ja korjattiin 26.8
`gen_share_card.py`:hyn dynaamiseksi. Kaksi uudempaa generaattoria ei
kutsunut korjausta (muisti: hylatty-sanamuoto-palaa-uudessa-generaattorissa).

Tama portti kaatuu jos NELJAS generaattori tekee saman.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CARD_SCRIPTS = sorted(ROOT.glob("scripts/*card*.py"))
HARDCODED = re.compile(r"rating fitted on (one|two|\d+) PL match", re.I)


def test_card_generators_exist():
    """Kontrolli: jos glob ei loyda mitaan, portti lapaisee tyhjana."""
    assert len(CARD_SCRIPTS) >= 3, [p.name for p in CARD_SCRIPTS]


def test_no_card_generator_hardcodes_the_promoted_match_count():
    bad = []
    for p in CARD_SCRIPTS:
        txt = p.read_text(encoding="utf-8", errors="ignore")
        for m in HARDCODED.finditer(txt):
            line = txt[:m.start()].count("\n") + 1
            # gen_share_card rakentaa lauseen f-stringilla datasta; sen oma
            # rivi ei ole kovakoodaus vaan malli.
            if "{n}" in txt[max(0, m.start() - 40):m.end() + 10]:
                continue
            bad.append(f"{p.name}:{line}")
    assert not bad, ("kovakoodattu nousija-alaviite: %s. Kayta "
                     "scripts.gen_share_card.promoted_footnote()" % bad)


def test_negative_control_pattern_would_catch_a_hardcode():
    """Ilman tata edellinen lapaisisi myos kuviolla joka ei osu mihinkaan."""
    assert HARDCODED.search("* promoted side, rating fitted on one PL match so far")
    assert HARDCODED.search("rating fitted on 2 PL matches")
    assert not HARDCODED.search("* promoted side, baseline rating with no PL history")


def test_shared_helper_is_importable_and_reads_data():
    from scripts.gen_share_card import promoted_footnote
    out = promoted_footnote()
    assert "promoted side" in out
    # luku tulee datasta, joten se ei saa olla kirjoitettu sanana koodissa
    assert re.search(r"\d+ PL match", out) or "no PL history" in out, out
