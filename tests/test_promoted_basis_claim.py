# -*- coding: utf-8 -*-
"""Nousijavaite: sivu ja kortti EIVAT saa vaittaa muuta kuin ajettu fitti.

26.8.2026: `goaliq.app/fpl` kertoi ilmaispinnalla etta Coventry/Hull/Ipswich
"runs on a measured baseline from recent promoted sides instead of a rating of
its own", ja GW2-jakokortin alaviite sanoi "baseline rating with no PL history
yet". Molemmat olivat epatosia sina paivana:

  fpl_xp_projections.json (generoitu 25.8 18:27)
    completed_gameweeks              = [1]
    promoted_baseline_values.applied_to = []      <- ei sovellettu kehenkaan

GW1 pelattiin 21.-24.8, joten (a) PL-historiaa ON ja (b) jokaisella kolmella on
oma luokitus. Vaite oli kovakoodattua proosaa joka ei liikkunut mallin mukana —
sama vikaluokka jonka `meta.caveat` sai korjatun 23.8.

Portti mittaa RENDEROIDYN tuloksen molemmista haaroista ja ajaa negatiivisen
kontrollin: jos `basis` kaannetaan, vaitteen ON vaihduttava. Ilman kontrollia
testi lapaisisi myos kovakoodatulla tekstilla.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_fpl_page import _strength_basis_note  # noqa: E402

BASELINE_WORDS = ("baseline",)
OWN_FIT_WORDS = ("rating", "match")


def _ctx(done: int, thin: list[dict]) -> dict:
    return {
        "season": "2026/27",
        "team_strength_source": "GoalIQ Dixon-Coles, Understat PL ['2526', '2627']",
        "completed_gws": done,
        "promoted_thin": thin,
    }


def test_esikausi_johdanto_katoaa_kun_kierros_on_pelattu():
    ennen = _strength_basis_note(_ctx(0, []))
    jalkeen = _strength_basis_note(_ctx(1, [{"team": "Coventry", "own_matches": 1}]))
    assert ennen.startswith("Pre-season")
    # NEGATIIVINEN KONTROLLI: sama funktio, eri tila -> eri vaite.
    assert "Pre-season" not in jalkeen
    assert "1 gameweek of 2026/27 included" in jalkeen


def test_baselinea_ei_vaiteta_kun_sita_ei_sovelleta():
    thin = [{"team": "Coventry", "own_matches": 1},
            {"team": "Hull", "own_matches": 1},
            {"team": "Ipswich", "own_matches": 1}]
    teksti = _strength_basis_note(_ctx(1, thin))
    assert not any(w in teksti for w in BASELINE_WORDS), teksti
    assert all(w in teksti for w in OWN_FIT_WORDS), teksti
    for nimi in ("Coventry", "Hull", "Ipswich"):
        assert nimi in teksti, f"{nimi} puuttuu varauksesta: {teksti}"

    # NEGATIIVINEN KONTROLLI: tyhja thin-lista = baseline on kaytossa ->
    # vaitteen ON palattava. Jos tama ei kaannny, teksti on kovakoodattu.
    palaa = _strength_basis_note(_ctx(1, []))
    assert any(w in palaa for w in BASELINE_WORDS), palaa


def test_artefaktin_ja_lipun_on_oltava_samaa_mielta():
    """team_confidence.json:n `basis` vs. ajetun fitin `applied_to`."""
    conf = json.loads((ROOT / "data" / "team_confidence.json")
                      .read_text(encoding="utf-8"))
    meta = json.loads((ROOT / "data" / "fpl_xp_projections.json")
                      .read_text(encoding="utf-8"))["meta"]
    applied = set((meta.get("promoted_baseline_values") or {}).get("applied_to")
                  or meta.get("promoted_baseline_teams") or [])
    promoted = [t for t in conf["teams"] if t.get("is_promoted")]
    assert promoted, "nousijoita ei ole — lippu on rikki"
    for t in promoted:
        odotettu = "promoted_baseline" if t["model_team"] in applied else "own_thin_fit"
        assert t.get("basis") == odotettu, (
            f"{t['model_team']}: basis={t.get('basis')} mutta fitti sanoo "
            f"{odotettu} (applied_to={sorted(applied)})")
        if odotettu == "own_thin_fit":
            assert (t.get("own_matches") or 0) > 0, (
                f"{t['model_team']}: oma fitti mutta 0 ottelua — luku on "
                f"johdettu vaarin")
            assert "baseline" not in (t.get("note") or ""), t["note"]


def test_nousijan_varaus_ei_ole_vain_kapealla_naytolla():
    """Varaus renderoidaan ILMAN .m-only-luokkaa; vaihtuvuus-% saa jaada."""
    html = (ROOT / "fpl.html").read_text(encoding="utf-8")
    conf = json.loads((ROOT / "data" / "team_confidence.json")
                      .read_text(encoding="utf-8"))
    nousijat = [t["model_team"] for t in conf["teams"] if t.get("is_promoted")]
    osumat = 0
    for nimi in nousijat:
        avain = f'<td class="team">{nimi}<span class="'
        i = html.find(avain)
        assert i >= 0, f"{nimi}: riville ei ole alarivia lainkaan"
        luokat = html[i + len(avain):html.index('"', i + len(avain))]
        assert "m-only" not in luokat, (
            f"{nimi}: varaus on .m-only eli naky vain alle 560px — "
            f"tyopoytalukija jaa ilman ({luokat})")
        assert "is-caveat" in luokat, luokat
        osumat += 1
    # LASKE OSUMAT, ALA TARKISTA OLEMASSAOLOA (25.8 opetus).
    assert osumat == len(nousijat) == 3, f"{osumat} osumaa, {len(nousijat)} nousijaa"
