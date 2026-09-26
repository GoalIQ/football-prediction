"""Portti: track record nimeaa mallin oikein (PROVENANCE-LUKU-SIVULLE, 26.9.2026).

Blended all_time (609) sisaltaa 56 MM-kisojen ennustetta erillisesta
maajoukkuemallista. Sivut sanoivat "The GoalIQ model ... starting with the 2026
World Cup" ja "Built on a model with 49.4% ... across 609". Nyt:
  (1) kun by_model on saatavilla, lauseet ja ACC-TRUST kayttavat seuramallin
      lukuja ja MM-kisat kerrotaan erillisena mallina,
  (2) ilman by_modelia (vanha accuracy.json) mikaan lause ei nimea blended-
      lukua yhden mallin tulokseksi,
  (3) /predictionsin kilpailulohkossa on seuramallin summa samasta lahteesta,
      jotta alaviitteen luku loytyy linkin takaa,
  (4) ACC-TRUST-lauseella on yksi lukija (ei kopiota etusivulle ja predictionsiin).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from scripts import build_fpl_page as b
from src.models import accuracy as acc

ROOT = Path(__file__).resolve().parents[1]

BLENDED = {"acc_logged": 3286, "acc_n": 609, "acc_pct_1x2": 49.43, "acc_dec_n": 445,
           "acc_dec_c": 301, "acc_pct_dec": 67.64}


@pytest.fixture
def club():
    agg = acc.compute_aggregate(acc.load_log())
    return b._club_block(agg["by_model"]["club"])


def test_seuramallin_lohko_oikeasta_lokista(club):
    assert club["n"] == club["correct"] + (club["n"] - club["correct"])
    agg = acc.compute_aggregate(acc.load_log())
    assert club["n"] == agg["by_model"]["club"]["n"] < agg["all_time"]["n"]
    assert club["logged"] < agg["logged_with_timestamp"]


def test_lauseet_seuramallista_ja_mm_erikseen(club):
    c = {**BLENDED, "acc_club": club}
    teksti = " ".join(b.track_record_sentences(c))
    assert "The GoalIQ club model's predictions" in teksti
    # Tarkistaja B1: kirjattujen maara (sis. pelaamattomat) ei ole ilmaispinnalla.
    assert str(club["logged"]) not in teksti
    assert f"Across the {club['n']} completed club matches" in teksti
    assert b.fmt_pct(club["pct"]) in teksti
    assert "separate national-team model" in teksti
    # Blended-luku ei esiinny mallin tuloksena.
    assert "609" not in teksti and "49.4%" not in teksti
    assert "starting with the 2026 World Cup" not in teksti


def _luvut(teksti: str) -> set[str]:
    import re
    return set(re.findall(r"\d+(?:\.\d+)?%?", teksti.replace("1X2", "")))


def test_jokainen_track_record_luku_loytyy_kilpailulohkosta(club):
    # Tarkistaja B2 (saanto 6a, yksi lukija): lause ei saa sisaltaa lukua jota
    # linkin takana oleva kilpailulohko ei nayta. "2026" on vuosiluku.
    rivi = {"code": "WC", "name": "World Cup 2026", "n": 56, "correct": 35,
            "pct": 62.5, "dec_n": 0, "dec_c": 0, "pct_dec": 0.0, "draw_n": 0}
    c = {**BLENDED, "acc_club": club, "by_comp": [rivi]}
    lohko = b.by_comp_html(c)
    puuttuu = {x for x in _luvut(" ".join(b.track_record_sentences(c))) if x != "2026"
               and x not in lohko}
    assert not puuttuu, puuttuu


def test_fallbackin_luvut_ovat_chipin_luvut():
    # Tarkistaja B3: vanhan skeeman lauseissa vain luvut jotka chip nayttaa
    # ("49.4% ... across 609 completed matches, all competitions").
    c = {**BLENDED, "acc_club": None}
    sallitut = {str(c["acc_n"]), b.fmt_pct(c["acc_pct_1x2"]), "2026"}
    assert _luvut(" ".join(b.track_record_sentences(c))) <= sallitut
    assert _luvut(b.acc_trust_sentence(c)) <= sallitut


def test_vanha_skeema_ei_nimea_blended_lukua_malliksi():
    c = {**BLENDED, "acc_club": None}
    lauseet = b.track_record_sentences(c)
    teksti = " ".join(lauseet)
    assert "all competitions" in teksti
    assert "The GoalIQ model" not in teksti
    assert "the model called" not in teksti and "The model always" not in teksti
    assert b.acc_trust_sentence(c).endswith("all competitions.")
    assert "Built on a model" not in b.acc_trust_sentence(c)


def test_trust_lause_seuramallista(club):
    c = {**BLENDED, "acc_club": club}
    assert b.acc_trust_sentence(c) == (
        f"Built on a model with {b.fmt_pct(club['pct'])} correct 1X2 results "
        f"across {club['n']} completed club matches, every one logged before kick-off."
    )


def test_kilpailulohkossa_seuramallin_summa_ensimmaisena(club):
    rivi = {"code": "PL", "name": "Premier League", "n": 50, "correct": 22,
            "pct": 44.0, "dec_n": 0, "dec_c": 0, "pct_dec": 0.0, "draw_n": 0}
    html = b.by_comp_html({**BLENDED, "acc_club": club, "by_comp": [rivi]})
    i_total = html.index("All club matches")
    assert i_total < html.index("Premier League")
    assert f"{club['correct']} of {club['n']}" in html
    assert b.fmt_pct(club["pct"]) in html
    assert "national-team model" in html
    # Summarivilla sama alarivi kuin muilla (ratkenneet + tasapelit).
    assert f"({club['dec_c']} of {club['dec_n']})" in html
    assert f"{club['n'] - club['dec_n']} draws" in html
    # Ilman by_modelia summariviä ei keksita.
    ilman = b.by_comp_html({**BLENDED, "acc_club": None, "by_comp": [rivi]})
    assert "All club matches" not in ilman


def test_trust_lauseella_yksi_lukija():
    src = (ROOT / "scripts/build_fpl_page.py").read_text(encoding="utf-8")
    assert src.count("Built on a model with") == 1
    puu = ast.parse(src)
    kutsut = [n for n in ast.walk(puu) if isinstance(n, ast.Call)
              and getattr(n.func, "id", None) == "acc_trust_sentence"]
    assert len(kutsut) == 2, "etusivu ja /predictions lukevat saman funktion"
