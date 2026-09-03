# -*- coding: utf-8 -*-
"""SIVU-NOUSIJAVARAUS-VANHENTUNUT (30.8.2026): kausivaraus tulee DATASTA.

Sivu renderoi kovakoodattua lausetta *"there are no Premier League results to
fit a team rating on and the model starts them from a baseline"*. Se oli tosi
ennen GW1:ta. Data sanoi jo `own_matches = 1` / `basis = own_thin_fit`, ja
artefaktin oma `note` kertoi sen oikein - korttien alaviite luki notea, sivu
ei. Kovakoodattu kausivaraus on pahin laatunsa: se NAYTTAA hoidetulta koko sen
ajan kun se on jo vaara (muisti: ehto-ei-vanhene-teksti-vanhenee).

Ajo: .venv/Scripts/python -m pytest tests/test_tflag_note_from_data.py -q
"""
import re

from scripts.build_fpl_longtail import _tflag_note

XP = {"meta": {"team_confidence": {"teams": {
    "Coventry": {"flag": "promoted", "note": "Promoted side. Rating fitted on 1 match."},
    "Hull": {"flag": "promoted", "note": "Promoted side. Rating fitted on 1 match."},
    "Aston Villa": {"flag": "high_turnover", "note": "29% of minutes left."},
}}}}
ROWS = [{"web_name": "A", "team_short": "COV", "team_flag": "promoted"}]


def _teksti(h: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()


def test_varaus_tulee_artefaktin_notesta():
    t = _teksti(_tflag_note(XP, ROWS, ROWS))
    assert "Rating fitted on 1 match." in t
    assert "29% of minutes left." in t


def test_vanhentunut_kovakoodattu_lause_on_poissa():
    """Negatiivinen kontrolli nimenomaan sille lauseelle joka vanheni."""
    t = _teksti(_tflag_note(XP, ROWS, ROWS))
    assert "no Premier League results to fit a team rating on" not in t
    assert "starts them from a baseline" not in t


def test_sama_note_ryhmitellaan_eika_toisteta():
    t = _teksti(_tflag_note(XP, ROWS, ROWS))
    assert t.count("Rating fitted on 1 match.") == 1, t
    assert "Coventry, Hull" in t


def test_ilman_lippuja_ei_selitetta():
    assert _tflag_note({"meta": {"team_confidence": {"teams": {}}}}, [], []) == ""


def test_lippu_ilman_notea_ei_keksi_perustelua():
    """Puuttuva note -> joukkue nimetaan, mutta SYYTA ei keksita.

    Selite ei silti katoa kokonaan: sen loppuosa kertoo mita lippu tarkoittaa
    ja loytyyko merkki taulukosta, ja se on tosi ilman noteakin.
    """
    xp = {"meta": {"team_confidence": {"teams": {
        "Coventry": {"flag": "promoted", "note": ""}}}}}
    t = _teksti(_tflag_note(xp, ROWS, ROWS))
    assert "Coventry" in t
    assert "The flag means the projection is working with weaker information" in t
    for keksitty in ("fitted on", "baseline", "minutes left"):
        assert keksitty not in t, t


def test_tuotannon_sivulla_ei_ole_vanhentunutta_varausta():
    """Elava mittaus rakennetulta sivulta.

    KORJATTU 2.9.2026: edellinen versio vertasi kovakoodattua otteluMaaraa
    ("fitted on 1 match"), ja se on tasan sama vikaluokka jonka tama testi
    alunperin loysi (ehto-ei-vanhene-teksti-vanhenee) — GW2:n jalkeen data
    sanoo jo "fitted on 2 matches" ja putki oli punainen kahdesti (tests.yml
    2.9). Testi lukee nyt SAMAN artefaktin josta sivu rakennetaan ja vertaa
    sen `note`-kenttaa sivulla nakyvaan tekstiin, joten se ei vanhene
    uudelleen kun otteluMaara kasvaa."""
    import json
    from html import escape
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    f = root / "fpl" / "expected-points.html"
    xp_path = root / "data" / "fpl_xp_projections.json"
    if not f.exists() or not xp_path.exists():
        return
    h = f.read_text(encoding="utf-8")
    assert "no Premier League results to fit a team rating on" not in h
    m = re.search(r'<p class="note"><strong>Flagged teams\.</strong>.*?</p>', h, re.S)
    assert m, "sivulta puuttuu Flagged teams -selite"
    teams = (json.loads(xp_path.read_text(encoding="utf-8")).get("meta", {})
             .get("team_confidence", {}).get("teams", {}))
    promoted = [t for t, v in teams.items() if v.get("flag") == "promoted"
                and str(v.get("note") or "").strip()]
    if not promoted:
        return
    note = str(teams[promoted[0]]["note"]).strip()
    assert escape(note) in m.group(0), (
        "sivun selite ei vastaa artefaktin notea — kovakoodattu teksti on "
        "vanhentunut (muisti: ehto-ei-vanhene-teksti-vanhenee)")
