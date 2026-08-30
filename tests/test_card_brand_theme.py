# -*- coding: utf-8 -*-
"""Korttien varitaema tulee sivun paletista, ei omasta (30.8.2026).

Villen huomio: "kortissa vaara variteema". Mitattu: molemmat
korttigeneraattorit maarittelivat `--teal:#2ED6C2` ja kayttivat sita
KOROSTUSVARINA (logo, xP-luvut, kentan luvut, summa). Turkoosia ei esiinny
goaliq.app/fpl:lla missaan paitsi kayttamattomana :root-rivina.

Merkki oli lisaksi pelkkaa turkoosia tekstia "GoalIQ" ilman amber-laatikkoa,
eli KOLMAS merkkiversio - tasan se jonka Villen 1.8.2026 paatos poisti
(`src/brand.py`: "logo on kaikilla sivuilla sama, ja se on se keltaisella
pohjalla oleva IQ"). Merkkia oli silloin kolmea versiota; tama olisi ollut
neljas.

Portti: kortit lukevat merkin `src/brand.py`:sta eivatka maarittele omaa.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CARD_SCRIPTS = sorted(ROOT.glob("scripts/render_*card*.py"))
#: Varit joita sivun paletti EI sisalla renderoituna.
OFF_PALETTE = re.compile(r"#2ED6C2", re.I)


def test_card_scripts_found():
    """Kontrolli: tyhja glob lapaisisi kaikki portit alla."""
    assert len(CARD_SCRIPTS) >= 2, [p.name for p in CARD_SCRIPTS]


def test_no_card_uses_a_colour_outside_the_site_palette():
    bad = []
    for p in CARD_SCRIPTS:
        txt = p.read_text(encoding="utf-8", errors="ignore")
        for m in OFF_PALETTE.finditer(txt):
            bad.append(f"{p.name}:{txt[:m.start()].count(chr(10)) + 1}")
    assert not bad, ("kortti kayttaa varia jota sivun paletissa ei "
                     "renderoidu: %s" % bad)


def test_negative_control_the_pattern_would_catch_teal():
    """Ilman tata edellinen lapaisisi kuviolla joka ei osu mihinkaan."""
    assert OFF_PALETTE.search("--teal:#2ED6C2;")
    assert not OFF_PALETTE.search("--amber:#F5C542;")


def test_cards_take_the_mark_from_the_shared_brand_module():
    """Merkki YHDESTA lahteesta. Villen 1.8 paatos."""
    for p in CARD_SCRIPTS:
        txt = p.read_text(encoding="utf-8", errors="ignore")
        assert "from src.brand import logo_svg" in txt, p.name
        assert "logo_svg(" in txt, p.name


def test_cards_do_not_hand_roll_a_wordmark_without_the_mark():
    """Pelkka teksti-GoalIQ ilman laatikkoa on se kolmas versio."""
    for p in CARD_SCRIPTS:
        txt = p.read_text(encoding="utf-8", errors="ignore")
        assert '"brand">GoalIQ<' not in txt, p.name


def test_shared_mark_is_amber_on_ink():
    from src.brand import AMBER, INK, logo_svg
    svg = logo_svg(28)
    assert AMBER == "#F5C542" and INK == "#0B0A09"
    assert f'fill="{AMBER}"' in svg
    assert "IQ" in svg
