# -*- coding: utf-8 -*-
"""Kortin nakyvin sarake on luettavissa myos puhelimella.

🔴 MITATTU 12.9.2026 `check_claim_route`illa. `/fpl/expected-points#gw-xp`
-taulun Opponent-sarake on `.m-hide` eli VAIN tyopoydalla, mutta jakokortin
(`gen_share_card.py xp`) toiseksi nakyvin palsta on FIXTURE - ja saman aamun
postaus (M85) lahettaa lukijan tasan tahan ankkuriin. FPL-liikenne on
enimmakseen puhelimella, joten kortin naytettavin luku oli juuri se jota
lukija ei nahnyt perilla.

Sama vikaluokka kuin `FPL-SIVU-OTTELUIDEN-XG` (kortti vaittaa, sivu ei nayta)
ja `maski-katkaisee-ilmaispinnan-hiljaa`: sivu nayttaa toimivalta, koska
puuttuva sarake ei ole virhe vaan uskottava naky.

Korjaus kayttaa talon omaa kuviota (`build_fpl_page.py`, 10.8): piilotettu
sarake tuodaan riville `.m-only`-alarivina, joka KATOAA kun "Show all
columns" palauttaa sarakkeen - eli lukua ei nayteta kahdesti kummassakaan
tilassa.

MITATTU 390 px:n LAITE-EMULAATIOLLA (ei ikkunan koolla; muisti
`cdp-laite-emulaatio-on-mittari`), DPR 3, viewport 390x844:
    ennen:   alarivia ei ole, sarake piilossa -> vastustaja EI luettavissa
    jalkeen: alarivi nakyy ("MCI (H)"), sarake yha piilossa
    taulukon leveys 533 px molemmissa (ei uutta ylivuotoa)
    rivin korkeus 55 -> 75 px
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ART = ROOT / "data" / "fpl_xp_projections.json"


def _section() -> str:
    from scripts.build_fpl_longtail import _gw_xp_section
    return _gw_xp_section(json.loads(ART.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# 1. Ehto yksin, synteettisilla riveilla
# ---------------------------------------------------------------------------

def _rivi(opps):
    return {"web_name": "Testi", "team_short": "TST", "pos": "MID",
            "price": 5.0,
            "gameweeks": [{"gw": 4, "xp": 4.0, "opponents": opps}]}


@pytest.mark.parametrize("opps,odotus", [
    ([{"opp": "MCI", "venue": "H"}], "MCI (H)"),
    ([{"opp": "SUN", "venue": "A"}], "SUN (A)"),
    # Tuplakierros: MOLEMMAT, kuten sarakkeessakin.
    ([{"opp": "AVL", "venue": "H"}, {"opp": "BHA", "venue": "A"}],
     "AVL (H), BHA (A)"),
    # Blank: sarake sanoo "blank", niin sanoo alarivikin.
    ([], "blank"),
])
def test_alarivi_sanoo_saman_kuin_sarake(opps, odotus):
    """Yksi lukija: alarivi ja sarake tulevat samasta `opponent_text`ista."""
    from scripts.build_fpl_longtail import _opponent_sub
    from src.models.fpl_gw_xp import opponent_text
    html = _opponent_sub(_rivi(opps), 4)
    assert odotus in html, html
    assert opponent_text(_rivi(opps), 4) == odotus


def test_ei_alarivia_kun_kierrosta_ei_ole():
    """KONTROLLI: tyhja ei saa tuottaa tyhjaa spania."""
    from scripts.build_fpl_longtail import _opponent_sub
    tyhja = {"web_name": "X", "gameweeks": []}
    assert _opponent_sub(tyhja, 4) == ""


def test_alarivi_on_m_only():
    """MUTAATIO: ilman `m-only` vastustaja nakyisi KAHDESTI kun lukija
    painaa "Show all columns" - sarakkeessa ja alarivilla."""
    from scripts.build_fpl_longtail import _opponent_sub
    html = _opponent_sub(_rivi([{"opp": "MCI", "venue": "H"}]), 4)
    assert "m-only" in html, html
    assert "m-sub" in html, html


# ---------------------------------------------------------------------------
# 2. Tuotantosivu: molemmat pinnat, ei kumpaakaan kahdesti
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not ART.is_file(), reason="artefaktia ei ole")
def test_jokaisella_rivilla_on_vastustaja_molemmissa_muodoissa():
    html = _section()
    rivit = re.findall(r"<tr><td class=\"n\">\d+</td>.*?</tr>", html, re.S)
    assert len(rivit) >= 10, len(rivit)
    for i, r in enumerate(rivit):
        alarivi = re.search(r'<span class="m-only m-sub opp">([^<]+)</span>', r)
        sarake = re.search(r'<td class="m-hide">([^<]*)</td>', r)
        assert alarivi, f"rivi {i+1}: alarivi puuttuu"
        assert sarake, f"rivi {i+1}: sarake puuttuu"
        assert alarivi.group(1) == sarake.group(1), (
            f"rivi {i+1}: alarivi {alarivi.group(1)!r} != sarake "
            f"{sarake.group(1)!r} - kaksi lukijaa")


@pytest.mark.skipif(not ART.is_file(), reason="artefaktia ei ole")
def test_sarake_on_yha_olemassa_tyopoydalle():
    """Alarivi EI korvaa saraketta: leveallä naytolla sarake on parempi."""
    assert '<td class="m-hide">' in _section()


@pytest.mark.skipif(not ART.is_file(), reason="artefaktia ei ole")
def test_kontrolli_osio_ei_ole_tyhja():
    """Ilman tata ylla olevat menisivat lapi tyhjalla osiolla
    (muisti: kontrolli-lapaisi-tyhjana)."""
    html = _section()
    assert 'id="gw-xp"' in html
    assert html.count('class="m-only m-sub opp"') >= 10
