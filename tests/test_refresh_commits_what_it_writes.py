# -*- coding: utf-8 -*-
"""Portti: refresh-ajon kirjoittama artefakti on myos committoitava.

TAUSTA (7.9.2026, julkaisutarkistajan 17. kierros). `data/gw_recap.json` oli
**JAASSA 7 vuorokautta**. `fpl-data-refresh.yml` ajaa `build_gw_recap`in joka
ajossa, skripti kirjoittaa oikeat luvut runnerin levylle - ja commit-askel
listaa 20 tiedostoa nimeltä, joista tama puuttui. Levy katoaa ajon mukana.

Mitattu: artefakti sanoi *"1 kierros, -9 vs keskiarvo, 0x yli keskiarvon"*
kun todellisuus oli 2 kierrosta ja +18. Se on **mallin julkinen track
record**, eli viikkopostauksen luku.

MIKSI MIKAAN EI HUUTANUT: askel onnistuu (skripti palauttaa 0), joten Step
healthin `::error::` ei laukea. Ja `tests/test_gw_recap.py` assertoi
`.gitignore`n poikkeusrivin - eli sen etta tiedosto SAA olla gitissa, ei
sita etta se PAATYY sinne. Sama vikaluokka kuin `vihrea-putki-nielee-
jaatymisen` ja `loki-voi-valehdella-onnistumisesta`.

Portti lukee workflow'n `git add` -listan ja vaatii, etta jokaisen
artefaktia kirjoittavan skriptin ulostulo on siella. Uusi skripti ei paase
listan ohi vahingossa: testi kaatuu ja kirjoittaja joutuu joko lisaamaan
rivin tai kirjoittamaan perustelun poikkeuslistalle.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from workflow_step_text import workflow_text_expanded  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows" / "fpl-data-refresh.yml"

# Skriptit jotka refresh ajaa ja jotka kirjoittavat `data/`-artefaktin.
# Arvo = tiedosto joka on committoitava.
KIRJOITTAJAT = {
    "build_gw_recap": "data/gw_recap.json",
    "build_team_confidence": "data/team_confidence.json",
    "build_fpl_price_watch": "data/fpl_price_watch.json",
    "build_fpl_defcon_gw": "data/fpl_defcon_gw.json",
    "build_fpl_player_leaders": "data/fpl_player_leaders.json",
    "build_fpl_stats": "data/fpl_player_stats.json",
    "build_fpl_cs_fdr": "data/fpl_cs_fdr.json",
    # 17.9 KAKSI-GRADERIA-YKSI-TIEDOSTO: freeze-graderi kirjoittaa omaan
    # sarjaansa, ei enaa entry-sarjaan.
    "grade_model_squad_gw": "data/model_squad_frozen_gw_scores.json",
    # 22.9 LANDING-KORTIT-GW3-VANHAT: etusivun kortit + kierrosmerkinta.
    # Ilman committia kortti paivittyisi runnerin levylle ja sivu jaisi
    # edelliseen kierrokseen - tasan se vika jonka askel korjaa.
    "refresh_site_cards": "assets/cards/cards.json",
}

# POIKKEUSLISTA: tiedosto jota refresh EI committaa, perusteluineen.
# Tyhja perustelu ei kelpaa.
POIKKEUKSET: dict[str, str] = {}


def _workflow() -> str:
    # 27.9: push-askel kutsuu scripts/ci_push_rebuild.sh:ta ja polut ovat
    # env-listoissa. Jaettu lukija laajentaa ne `git add` -riviksi; raaka
    # read_text ei nakisi niita lainkaan (portti olisi lakannut mittaamasta).
    return workflow_text_expanded(WF)


def _git_add_rivit(teksti: str) -> str:
    return "\n".join(r for r in teksti.splitlines() if "git add" in r)


def test_jokainen_artefaktin_kirjoittaja_on_myos_commit_listalla():
    wf = _workflow()
    addit = _git_add_rivit(wf)
    puuttuu = []
    for skripti, tiedosto in KIRJOITTAJAT.items():
        if skripti not in wf:
            continue  # ei ajossa tassa workflow'ssa
        if tiedosto in POIKKEUKSET:
            assert POIKKEUKSET[tiedosto].strip(), f"{tiedosto} ilman perustelua"
            continue
        if tiedosto not in addit:
            puuttuu.append(f"{skripti} kirjoittaa {tiedosto}")
    assert not puuttuu, (
        "refresh ajaa naita mutta ei committaa niiden ulostuloa - luvut "
        "elavat vain runnerin levylla:\n  " + "\n  ".join(puuttuu))


def test_gw_recap_on_listalla_nimenomaisesti():
    """Regressio: tama nimenomainen tiedosto oli jaassa 7 vrk."""
    assert "data/gw_recap.json" in _git_add_rivit(_workflow())


def test_kontrolli_havaitsin_lukee_oikeaa_lohkoa():
    """NEGATIIVINEN KONTROLLI havaitsimelle: ilman tata portti voisi olla
    vihrea siksi etta `_git_add_rivit` palauttaa tyhjaa (muisti:
    kontrolli-lapaisi-tyhjana)."""
    addit = _git_add_rivit(_workflow())
    polut = {t for r in addit.splitlines() for t in r.split()
             if "/" in t or t.endswith((".json", ".html"))}
    assert len(polut) >= 20, (
        f"git add -polkuja ei loytynyt odotetusti: {len(polut)}")
    # Ja tunnettu rivi on siella.
    assert "data/gw_calls.json" in addit
    # Keksitty tiedosto EI ole.
    assert "data/ei-ole-olemassa.json" not in addit
