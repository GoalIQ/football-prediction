"""SUOSIKKI-VAIN-KUN-ERO-YLITTAA-VIRHEEN (10.9.2026).

Kolme vahtia CLAUDE.md 6a:n mukaan:
(1) yksi lukija: call_state on ainoa joka saa palauttaa "favourite"
(2) poikkeuslista perusteluineen: argmax-koodi saa elaa vain listatuissa
    tiedostoissa (track recordin kirjaus), ei pinnoilla
(3) invariantti synteettisilla vaiheilla: ero marginaalin alla, paalla,
    tasan; artefakti puuttuu; mittaus synteettisesta lokista molemmin puolin
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src.models import call_margin as cm

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# call_state: lukija
# ---------------------------------------------------------------------------
M16 = {"margin_pp": 16, "decisive_below_pct": 46, "measured_at": "2026-09-10T03:36:00+00:00"}


@pytest.mark.parametrize("ph,pa", [(0.405, 0.355), (0.355, 0.405), (0.40, 0.40),
                                   (0.45, 0.30)])
def test_gap_below_margin_names_nobody(ph, pa):
    c = cm.call_state(ph, 1 - ph - pa, pa, margin=M16)
    assert c["favourite"] is None
    assert c["too_close"] is True
    assert c["reason"] == "gap_below_margin"
    assert c["margin_pp"] == 16


@pytest.mark.parametrize("ph,pa,side", [(0.55, 0.20, "home"), (0.20, 0.55, "away"),
                                        (0.48, 0.32, "home")])
def test_gap_at_or_above_margin_names_side(ph, pa, side):
    c = cm.call_state(ph, 1 - ph - pa, pa, margin=M16)
    assert c["favourite"] == side
    assert c["too_close"] is False


def test_gap_exactly_margin_is_a_call():
    c = cm.call_state(0.46, 0.24, 0.30, margin=M16)
    assert c["gap_pp"] == 16.0 and c["favourite"] == "home"


def test_symmetry_home_away_swap_flips_favourite():
    a = cm.call_state(0.55, 0.25, 0.20, margin=M16)
    b = cm.call_state(0.20, 0.25, 0.55, margin=M16)
    assert (a["favourite"], b["favourite"]) == ("home", "away")
    assert a["gap_pp"] == b["gap_pp"]


def test_draw_as_argmax_does_not_become_favourite():
    # Tasapeli suurin, mutta koti-vieras-ero yli marginaalin: nimetty puoli
    # on koti (sama kuin named_winner) - "draw" ei ole koskaan favourite.
    c = cm.call_state(0.40, 0.42, 0.18, margin=M16)
    assert c["favourite"] == "home"


@pytest.mark.parametrize("p,want", [(0.405, 41), (0.395, 40), (0.125, 13), (0.5, 50),
                                    (0.4049, 40), (0.0, 0), (1.0, 100)])
def test_pct_int_rounds_half_up_like_js(p, want):
    assert cm.pct_int(p) == want


def test_gap_is_difference_of_displayed_percentages():
    # Portin loydos 10.9: lukijan vahennyslasku sivun prosenteista on sama
    # luku kuin lause. 0.4649 -> 46, 0.3049 -> 30: ero 16 = kutsu, vaikka
    # raaka ero 16.0 pp pyoristyisi eri tavalla.
    c = cm.call_state(0.4649, 0.23, 0.3049, margin=M16)
    assert c["gap_pp"] == 16 and isinstance(c["gap_pp"], int)
    assert c["favourite"] == "home"
    c = cm.call_state(0.4551, 0.24, 0.2951, margin=M16)   # 46 - 30 = 16
    assert c["gap_pp"] == 16
    c = cm.call_state(0.4549, 0.24, 0.2951, margin=M16)   # 45 - 30 = 15
    assert c["gap_pp"] == 15 and c["too_close"] is True


def test_call_state_carries_artefact_numbers_for_copy():
    m = {"margin_pp": 16, "decisive_below_pct": 46, "measured_at": "2026-09-10T03:36:00+00:00"}
    c = cm.call_state(0.405, 0.24, 0.355, margin=m)
    assert c["below_hit_pct"] == 46
    assert c["measured_at"] == "2026-09-10"
    c = cm.call_state(0.405, 0.24, 0.355, margin={"margin_pp": 16})
    assert c["below_hit_pct"] is None and c["measured_at"] is None


def test_missing_artefact_is_fail_closed():
    c = cm.call_state(0.70, 0.20, 0.10, margin=None)
    assert c["favourite"] is None
    assert c["too_close"] is None
    assert c["reason"] == "margin_unavailable"


def test_load_margin_rejects_garbage(tmp_path):
    p = tmp_path / "m.json"
    p.write_text('{"margin_pp": "16"}', encoding="utf-8")
    assert cm.load_margin(p) is None
    p.write_text('{"margin_pp": 0}', encoding="utf-8")
    assert cm.load_margin(p) is None
    p.write_text("not json", encoding="utf-8")
    assert cm.load_margin(p) is None
    p.write_text('{"margin_pp": 12}', encoding="utf-8")
    assert cm.load_margin(p)["margin_pp"] == 12


def test_live_artefact_present_and_derivable():
    """Artefakti on repossa ja sen luku johtuu sen omista luokista."""
    doc = json.loads(cm.MARGIN_PATH.read_text(encoding="utf-8"))
    assert isinstance(doc["margin_pp"], int) and doc["margin_pp"] >= cm.MARGIN_FLOOR_PP
    assert doc["buckets"], "luokat puuttuvat - luku ei ole johdettavissa"
    big_above = [b for b in doc["buckets"]
                 if b["gap_from_pp"] >= doc["margin_pp"] and b["n"] >= cm.MIN_BUCKET_N]
    assert big_above and all(b["decisive_hit_pct"] >= cm.DECISIVE_HIT_FLOOR * 100
                             for b in big_above)
    # copyn luvut johtuvat luokista, ei proosasta
    below = [b for b in doc["buckets"] if b["gap_from_pp"] < doc["margin_pp"]]
    assert doc["decisive_below_n"] == sum(b["decisive_n"] for b in below)
    assert doc["decisive_below_won"] == sum(b["decisive_won"] for b in below)
    assert doc["decisive_below_pct"] == round(
        100 * doc["decisive_below_won"] / doc["decisive_below_n"])
    assert doc["n_below_margin"] == sum(b["n"] for b in below)
    assert doc["measured_at"][:4] == "2026" or doc["measured_at"][:4] > "2026"


# ---------------------------------------------------------------------------
# measure_margin: synteettinen loki molemmin puolin
# ---------------------------------------------------------------------------
def _row(gap_pp: float, hit: bool, draw: bool = False) -> dict:
    ph = 0.40 + gap_pp / 200.0
    pa = 0.40 - gap_pp / 200.0
    actual = "draw" if draw else ("home" if hit else "away")
    return {"p_home": round(ph, 4), "p_away": round(pa, 4), "p_draw": 0.20,
            "result": {"actual_outcome": actual, "hit_1x2": hit and not draw}}


def _synthetic(edge: int, n_per_bucket: int = 30) -> list[dict]:
    rows = []
    for k in range(0, 40, cm.BUCKET_PP):
        good = k >= edge
        for i in range(n_per_bucket):
            # hyva luokka: 80 % osumaa ratkenneissa; huono: 50 %
            hit = (i % 5 != 0) if good else (i % 2 == 0)
            rows.append(_row(k + 1.0, hit))
    return rows


@pytest.mark.parametrize("edge", [8, 16, 24])
def test_measure_finds_the_synthetic_edge(edge):
    out = cm.measure_margin(_synthetic(edge))
    assert out["margin_pp"] == edge


def test_measure_all_noise_returns_none():
    rows = [_row(k + 1.0, i % 2 == 0) for k in range(0, 40, 4) for i in range(30)]
    assert cm.measure_margin(rows)["margin_pp"] is None
    assert cm.call_state(0.7, 0.2, 0.1, margin={"margin_pp": None})["favourite"] is None


def test_measure_small_buckets_do_not_decide():
    # Vain 5 rivia per luokka: mikaan luokka ei ole iso -> ei marginaalia.
    assert cm.measure_margin(_synthetic(16, n_per_bucket=5))["margin_pp"] is None


def test_measure_ignores_voided_and_unprobed_rows():
    rows = _synthetic(16)
    rows.append({"p_home": None, "p_away": 0.3, "result": {"actual_outcome": "home"}})
    rows.append({"p_home": 0.9, "p_away": 0.05,
                 "result": {"actual_outcome": "away", "voided": True, "hit_1x2": False}})
    assert cm.measure_margin(rows)["margin_pp"] == 16


# ---------------------------------------------------------------------------
# Sivut: too close -> ei "favourite"-sanaa
# ---------------------------------------------------------------------------
def _entry(ph, pd_, pa):
    return {"home_team": "Club Brugge", "away_team": "Aston Villa", "p_home": ph,
            "p_draw": pd_, "p_away": pa, "predicted_winner": "home",
            "date": "2026-09-16", "kickoff": "2026-09-16T19:00:00Z",
            "most_likely_score": "1-1", "competition": "CL", "match_id": "t-1",
            "logged_at": "2026-09-10T00:00:00+00:00"}


def test_match_page_too_close_has_no_favourite(monkeypatch):
    from scripts import build_prediction_pages as bpp
    monkeypatch.setattr(bpp, "call_state",
                        lambda ph, pd_, pa: cm.call_state(ph, pd_, pa, margin=M16))
    html = bpp.render_match_page("CL", _entry(0.405, 0.24, 0.355))
    assert "Too close to call" in html
    assert "the favourite" not in html
    assert "gives Club Brugge" not in html
    assert "about half" not in html
    # ero on naytettyjen prosenttien erotus: 41 - 36 = 5
    assert "at <strong>41%</strong>" in html and "at <strong>36%</strong>" in html
    assert "5 percentage points apart" in html
    assert "has won 46% of the matches that had a winner" in html
    assert "too close for the GoalIQ model to name a favourite" in html  # meta, alussa


def test_margin_block_numbers_come_from_artefact():
    from scripts.build_fpl_page import call_margin_html
    doc = {"margin_pp": 16, "n_graded": 407, "n_below_margin": 142,
           "decisive_below_n": 96, "decisive_below_won": 44, "decisive_below_pct": 46,
           "decisive_above_n": 200, "decisive_above_won": 157, "decisive_above_pct": 79,
           "measured_at": "2026-09-10T03:36:00+00:00",
           "buckets": [{"gap_from_pp": 0, "gap_to_pp": 8, "n": 32, "decisive_n": 24,
                        "decisive_won": 12, "decisive_hit_pct": 50.0},
                       {"gap_from_pp": 40, "gap_to_pp": 48, "open_ended": True, "n": 105,
                        "decisive_n": 89, "decisive_won": 79, "decisive_hit_pct": 88.8}]}
    html = call_margin_html(doc)
    assert 'id="margin"' in html
    assert "<td>0-8</td>" in html and "<td>40+</td>" in html and "40-48" not in html
    doc["buckets"][1]["gap_to_pp"] = None
    assert "<td>40+</td>" in call_margin_html(doc)
    assert "96 of them had a winner, and the named side won 44 of those (46%)" in html
    assert "157 of 200 (79%)" in html
    assert "Measured 10 Sep 2026 from 407 graded matches" in html
    assert "<th>With a winner</th>" in html and "<td>24</td>" in html
    for banned in ("about half", "clearly more", "every refresh", "not from a bookmaker"):
        assert banned not in html
    # puuttuva kentta -> ei lohkoa, ei puolikasta lausetta
    assert call_margin_html({**doc, "decisive_below_pct": None}) == ""
    assert call_margin_html(None) == ""


def test_match_page_clear_gap_names_favourite(monkeypatch):
    from scripts import build_prediction_pages as bpp
    monkeypatch.setattr(bpp, "call_state",
                        lambda ph, pd_, pa: cm.call_state(ph, pd_, pa, margin=M16))
    html = bpp.render_match_page("CL", _entry(0.60, 0.22, 0.18))
    assert "<strong>Club Brugge</strong> the favourite" in html
    assert "Too close to call" not in html


def test_match_page_away_favourite_reads_call_not_predicted_winner(monkeypatch):
    # predicted_winner sanoo "home" (kirjauskentta), mutta luvut sanovat
    # vieras: pinta lukee call_statea, ei kirjauskenttaa.
    from scripts import build_prediction_pages as bpp
    monkeypatch.setattr(bpp, "call_state",
                        lambda ph, pd_, pa: cm.call_state(ph, pd_, pa, margin=M16))
    html = bpp.render_match_page("CL", _entry(0.18, 0.22, 0.60))
    assert "<strong>Aston Villa</strong> the favourite" in html


def test_league_hub_too_close_row(monkeypatch):
    from datetime import datetime, timezone
    from scripts import build_prediction_pages as bpp
    monkeypatch.setattr(bpp, "call_state",
                        lambda ph, pd_, pa: cm.call_state(ph, pd_, pa, margin=M16))
    html = bpp.render_league_hub("CL", [_entry(0.405, 0.24, 0.355), _entry(0.6, 0.2, 0.2)],
                                 datetime.now(timezone.utc))
    assert html.count('class="pick close"') == 1
    assert 'class="pick">Club Brugge' in html


# ---------------------------------------------------------------------------
# Poikkeuslista: argmax vain track recordin kirjauksessa
# ---------------------------------------------------------------------------
ARGMAX = re.compile(
    r'predicted_winner"?\]?\s*==\s*"home"'
    r'|p_home(?:_win)?\s*>=?\s*p_away'
    r'|p_away(?:_win)?\s*>=?\s*p_draw'
    r'|>=\s*Math\.max\(\s*data\.p_draw'
    # 10.9: etusivun next_matches_block kaytti max((p_home, ..), (p_draw, ..))
    # -kuviota eika vertailua, ja livahti ohi. Kaikki max()-kutsut joissa
    # p_home/p_away/p_draw ovat KAHDESTI argumenttina ovat suosikin johtamista.
    # Kaksi eri p_-todennakoisyytta samassa max()-kutsussa; yksi (esim.
    # max(p_home, 0.001) -kerroinclamp) ei ole suosikin valinta.
    r'|\bmax\([^\n]*\bp_(?:home|away|draw)[^\n]*\bp_(?:home|away|draw)'
)
ALLOWED = {
    # track recordin kirjaus: julkaistu metodologia "always names the more
    # likely winner", ei pinta. Suosikin nayttaminen kulkee call_staten kautta.
    "src/models/accuracy.py",
    # tama testi
    "tests/test_call_margin.py",
}
SCAN_DIRS = ("scripts", "api", "src", "web/pro-spa/src")
SCAN_EXT = (".py", ".svelte", ".ts", ".js")


def test_no_surface_derives_favourite_itself():
    offenders = []
    for d in SCAN_DIRS:
        for f in (ROOT / d).rglob("*"):
            if f.suffix not in SCAN_EXT or "node_modules" in f.parts:
                continue
            rel = f.relative_to(ROOT).as_posix()
            if rel in ALLOWED:
                continue
            try:
                txt = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for m in ARGMAX.finditer(txt):
                line = txt.count("\n", 0, m.start()) + 1
                offenders.append(f"{rel}:{line}: {m.group(0)}")
    assert not offenders, (
        "Suosikki johdetaan pinnalla itse. Kayta call_state()a tai lisaa "
        "tiedosto ALLOWED-listaan perustelun kanssa:\n" + "\n".join(offenders))


def test_bucket_parameters_are_justified():
    """Luokkaleveys valittiin tuloksen tiedolla (4 pp antoi 28, 8 pp 16).
    Muutos naihin vaatii etta moduulin PERUSTELU-lohko paivitetaan samalla:
    testi kaataa jos luvut muuttuvat mutta perustelu ei mainitse niita."""
    assert (cm.BUCKET_PP, cm.MIN_BUCKET_N, cm.DECISIVE_HIT_FLOOR, cm.MARGIN_CAP_PP) == (8, 25, 0.60, 40), (
        "Paivita src/models/call_margin.py PERUSTELU-lohko (herkkyystaulukko) "
        "ja tama assertio samassa commitissa.")
    src = (ROOT / "src" / "models" / "call_margin.py").read_text(encoding="utf-8")
    assert "PERUSTELU" in src and "4 pp -> 28" in src and "8 pp -> 16" in src


def test_capped_bucket_has_no_false_upper_bound():
    rows = _synthetic(16) + [_row(60.0, True) for _ in range(30)]
    out = cm.measure_margin(rows)
    last = out["buckets"][-1]
    assert last["gap_from_pp"] == cm.MARGIN_CAP_PP
    assert last["open_ended"] is True and last["gap_to_pp"] is None
    assert last["n"] >= 30


def test_lede_link_is_fail_closed_without_anchor(monkeypatch, tmp_path):
    from scripts import build_prediction_pages as bpp
    monkeypatch.setattr(bpp, "call_state",
                        lambda ph, pd_, pa: cm.call_state(ph, pd_, pa, margin=M16))
    missing = tmp_path / "predictions.html"
    monkeypatch.setattr(bpp, "_MARGIN_ANCHOR_PATH", missing)
    html = bpp.render_match_page("CL", _entry(0.405, 0.24, 0.355))
    assert "predictions#margin" not in html and "does not call this one." in html
    missing.write_text('<div id="margin">x</div>', encoding="utf-8")
    html = bpp.render_match_page("CL", _entry(0.405, 0.24, 0.355))
    assert 'href="/predictions#margin"' in html


def test_next_matches_block_uses_call_state(monkeypatch):
    import datetime as dt
    from scripts import build_fpl_page as bfp
    monkeypatch.setattr(bfp, "call_state",
                        lambda ph, pd_, pa: cm.call_state(ph, pd_, pa, margin=M16))
    now = dt.datetime(2026, 9, 10, tzinfo=dt.timezone.utc)
    ko = now + dt.timedelta(days=1)
    rows = [
        {"home": "Club Brugge", "away": "Aston Villa", "p_home": 0.405, "p_draw": 0.24,
         "p_away": 0.355, "kickoff": ko, "comp": "Champions League", "url": "", "logged": "x"},
        {"home": "Liverpool", "away": "Burnley", "p_home": 0.70, "p_draw": 0.19,
         "p_away": 0.11, "kickoff": ko, "comp": "Premier League", "url": "", "logged": "x"},
    ]
    monkeypatch.setattr(bfp, "next_matches_rows", lambda log, now, limit: rows)
    html = bfp.next_matches_block({}, now)
    assert "Too close to call" in html and "41% · 24% · 36%" in html
    assert "Club Brugge <b>" not in html
    assert "Liverpool <b>70%</b>" in html


def test_allowed_files_exist():
    for rel in ALLOWED:
        assert (ROOT / rel).exists(), rel
