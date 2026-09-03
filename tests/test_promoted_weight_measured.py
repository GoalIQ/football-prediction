# -*- coding: utf-8 -*-
"""Nousijapaino on mitattu luku, ei oletus.

Tausta (3.9.2026). `LOW_CONFIDENCE_WEIGHT` oli 0.75 ja moduulin oma docstring
sanoi sen olevan oletus. Se ei ollut kosmeettinen: paino ohjasi entry
116920:n ykkosehdotusta, jonka PAINOTTAMATON hyoty oli -0.87 xP. Mitattuna
(`scripts/measure_promoted_bias.py`, GW1+GW2) malli ALIarvioi nousijaseuroja
enemman kuin muita, eli alennus painoi alaspain vaaraa ryhmaa.

Mekanismi (CLAUDE.md 6a kohta 2): alennuksen saa palauttaa, mutta silloin
tiedostossa on oltava mittaus joka perustelee sen. Unohduksesta syntyva
"laitetaan 0.9 kun tuntuu oikealta" kaatuu tahan; tietoinen muutos joutuu
kirjoittamaan n:n, biaksen ja z:n diffiin.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "models" / "fpl_transfers.py"


def _weight() -> float:
    m = re.search(r"^LOW_CONFIDENCE_WEIGHT = ([\d.]+)$",
                  SRC.read_text(encoding="utf-8"), re.M)
    assert m, "LOW_CONFIDENCE_WEIGHT ei ole moduulitason vakio"
    return float(m.group(1))


def test_alennus_vaatii_mittauksen_samassa_tiedostossa():
    s = SRC.read_text(encoding="utf-8")
    w = _weight()
    if w >= 1.0:
        return  # ei alennusta -> ei perusteluvelvollisuutta
    # Alennus on voimassa: mittauksen on oltava nakyvissa ja tuore.
    assert "measure_promoted_bias" in s, (
        "alennuskerroin ilman viittausta mittausskriptiin")
    assert re.search(r"\bn=\s*\d+", s), "mittauksesta puuttuu otoskoko"
    assert re.search(r"\bz\s*[+-]?\d", s), "mittauksesta puuttuu z"
    assert "bias -" in s or "bias  -" in s, (
        "alennus edellyttaa NEGATIIVISTA biasta (malli yliarvioi); "
        "kirjattu mittaus ei nayta sellaista")


def test_mittausskripti_on_olemassa_ja_ajettavissa():
    """Luku ilman toistettavaa mittausta on oletus toisessa asussa."""
    p = ROOT / "scripts" / "measure_promoted_bias.py"
    assert p.exists()
    s = p.read_text(encoding="utf-8")
    # Lahde: deadline-freeze, ei jalkikateen laskettu projektio.
    assert "fpl_xp_frozen" in s
    assert "event/{gw}/live/" in s
    # Nousijalista artefaktista, ei kovakoodattuna.
    assert "is_promoted" in s
    assert "COV" not in s.split('"""')[2] if s.count('"""') > 2 else True


def test_nykyinen_arvo_vastaa_kirjattua_mittausta():
    """3.9 mitattu: bias +1.059 (aliarvio), ero ei merkitseva -> 1.0."""
    s = SRC.read_text(encoding="utf-8")
    assert _weight() == 1.0
    assert "bias +1.059" in s, "mittaus ei ole kirjattu tiedostoon"
    assert "z +1.51" in s
