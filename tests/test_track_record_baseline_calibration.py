"""Portti: record-sivun perustaso ja valinnan kalibrointi (ulkoasuohjelma WP12, 5.11.2026).

Auditointi 1.11: "52 % lakkaa nayttamasta kolikonheitolta" vasta, kun luku
esitetaan perustason rinnalla ja kalibrointina. Kolme invarianttia, jotka
ovat tosia vain jos luvut lasketaan YHDESSA paikassa (`accuracy._by_model`):

(1) Perustaso ja kalibrointi koskevat samoja rivejä kuin seuramallin luku:
    perustason n == lohkon n ja kalibrointilokeroiden n:ien summa == lohkon n.
    Jos pinta laskisi ne itse, "same 1000 matches" voisi olla epatosi.
(2) Harva lokero ei nay omana prosenttinaan: se yhdistetaan naapuriin
    keskelle pain eika riveja pudoteta (3 ottelun "67 %" oli 5.11 datassa).
(3) Sivu nayttaa laskureista muotoillun prosentin (2.11 sovelluksen
    tuplapyoristys 0.5965 -> "59.7%" vaikka 68/114 = 59.6 %), ja vanha
    artefakti ilman uusia kenttia ei kaada builderia eika nayta tyhjaa osiota.
"""
from __future__ import annotations

import re

from scripts import build_fpl_page as b
from src.models import accuracy as acc
from src.models.fmt import fmt_pct


def _row(i: int, p_pick: float, won: bool, outcome: str | None = None,
         comp: str = "PL", winner: str = "home") -> dict:
    if outcome is None:
        outcome = winner if won else ("draw" if i % 2 else
                                      ("away" if winner == "home" else "home"))
    p_other = round((1 - p_pick) / 2, 4)
    probs = ({"p_home": p_pick, "p_away": p_other} if winner == "home"
             else {"p_away": p_pick, "p_home": p_other})
    return {
        "match_id": f"m{i}", "competition": comp, "date": "2026-10-01",
        "logged_at": "2026-10-01T00:00:00+00:00", "predicted_winner": winner,
        "p_draw": p_other, **probs,
        "result": {"actual_outcome": outcome, "hit_1x2": won, "exact_hit": False},
    }


def _rows(spec: list[tuple[float, int, int]]) -> list[dict]:
    """spec: (pick-p, n, voitot) -> rivit."""
    out, i = [], 0
    for p, n, w in spec:
        for k in range(n):
            out.append(_row(i, p, k < w, winner="home" if i % 3 else "away"))
            i += 1
    return out


def test_perustaso_on_kotivoittojen_osuus_samoilla_riveilla():
    rows = [_row(0, 0.5, True, "home"), _row(1, 0.5, False, "away"),
            _row(2, 0.5, False, "draw"), _row(3, 0.5, True, "home")]
    assert acc._baseline_home(rows) == {"n": 4, "correct": 2, "pct": 0.5}
    assert acc._baseline_home([]) == {"n": 0, "correct": 0, "pct": None}


def test_kalibrointi_summautuu_riveihin_ja_yhdistaa_harvat_reunat():
    rows = _rows([(0.35, 40, 15), (0.45, 50, 23), (0.55, 30, 17),
                  (0.85, 6, 5), (0.95, 3, 2)])
    cal = acc._pick_calibration(rows)
    assert sum(x["n"] for x in cal) == len(rows) == 129
    assert sum(x["won"] for x in cal) == sum(1 for e in rows if e["result"]["hit_1x2"])
    # 80-90 (6) ja 90-100 (3) ovat harvoja -> yhdistyvat keskelle pain yhdeksi
    # 50-100 -lokeroksi (50-60 on lahin naapuri, koska 60-80 on tyhja).
    assert [(x["lo"], x["hi"]) for x in cal] == [(0.3, 0.4), (0.4, 0.5), (0.5, 1.0)]
    assert cal[-1]["n"] == 39 and cal[-1]["won"] == 24
    assert all(x["n"] >= acc.MIN_CAL_BIN_N for x in cal)


def test_kalibrointi_harva_keskilokero_ei_pudota_riveja():
    rows = _rows([(0.35, 40, 15), (0.45, 4, 2), (0.55, 40, 22)])
    cal = acc._pick_calibration(rows)
    assert sum(x["n"] for x in cal) == 84
    assert all(x["n"] >= acc.MIN_CAL_BIN_N for x in cal)


def test_kalibrointi_pieni_otos_on_tyhja():
    assert acc._pick_calibration(_rows([(0.5, acc.MIN_DISPLAY_N - 1, 10)])) == []


def test_by_model_club_kantaa_perustason_ja_kalibroinnin_samoista_riveista():
    agg = acc.compute_aggregate(acc.load_log())
    club = agg["by_model"]["club"]
    assert club["baseline_home"]["n"] == club["n"]
    assert sum(x["n"] for x in club["pick_calibration"]) == club["n"]
    assert sum(x["won"] for x in club["pick_calibration"]) == club["correct_1x2"]


def _ctx(agg: dict) -> dict:
    return {"acc_club": b._club_block(agg["by_model"]["club"]),
            "acc_head": acc.public_headline(agg)}


def test_sivun_luvut_ovat_otsikkoluku_ja_laskureista_muotoiltu():
    agg = acc.compute_aggregate(acc.load_log())
    c = _ctx(agg)
    html = b.record_head_html(c)
    club = agg["by_model"]["club"]
    # Mallin rivi = sama luku kuin otsikkopinnoilla (public_headline).
    assert f'{c["acc_head"]["pct_text"]}</span>' in html
    assert f'{club["correct_1x2"]} of {club["n"]}' in html
    base = club["baseline_home"]
    assert f'{fmt_pct(100 * base["correct"] / base["n"])}</span>' in html
    assert f'{base["correct"]} of {base["n"]}' in html
    for x in club["pick_calibration"]:
        assert f'{fmt_pct(100 * x["won"] / x["n"])}</span>' in html
        assert f'{x["won"]} of {x["n"]}' in html
    assert b.PREDICTION_LOG_URL in html


def test_tuplapyoristys_ei_vuoda_sivulle():
    # 68/114 = 59.649..% -> "59.6%". Tallennettu 0.5965*100 antaisi "59.7%".
    rows = _rows([(0.65, 114, 68)])
    for e in rows:
        e["competition"] = "ELC"
    club = {**acc._metrics_block(rows), "logged_with_timestamp": len(rows),
            "baseline_home": acc._baseline_home(rows),
            "pick_calibration": acc._pick_calibration(rows)}
    assert club["pick_calibration"][0]["pct_won"] == 0.5965
    html = b.record_head_html({"acc_club": b._club_block(club)})
    assert "59.6%</span>" in html and "59.7%" not in html


def test_vanha_artefakti_ilman_uusia_kenttia_ei_nayta_tyhjaa_osiota():
    agg = acc.compute_aggregate(acc.load_log())
    club = dict(agg["by_model"]["club"])
    club.pop("baseline_home")
    club.pop("pick_calibration")
    html = b.record_head_html({"acc_club": b._club_block(club)})
    assert "Against the simplest rule" not in html
    assert "How often the pick won" not in html
    assert b.PREDICTION_LOG_URL in html  # raakaloki-linkki ei riipu uusista kentista
    assert b.record_head_html({"acc_club": None}) == ""


def test_perustaso_eri_otoksesta_ei_renderoidy():
    """Jos perustason n ei ole lohkon n, "Same N matches" olisi epatosi."""
    agg = acc.compute_aggregate(acc.load_log())
    club = dict(agg["by_model"]["club"])
    club["baseline_home"] = {**club["baseline_home"], "n": club["n"] - 1}
    club["pick_calibration"] = club["pick_calibration"][:-1]
    html = b.record_head_html({"acc_club": b._club_block(club)})
    assert "Against the simplest rule" not in html
    assert "How often the pick won" not in html


def test_raakaloki_lause_kattaa_jokaisen_void_koodin():
    """Julkaisutarkistaja 5.11: lause luettelee void-syyt (postponed, cancelled,
    World Cup ilman aikaleimaa). Uusi koodi (esim. ABANDONED) tekisi siita
    vajaan hiljaa, joten jokaisen lokin void-arvon on oltava listalla."""
    log = acc.load_log()
    koodit = {str(e["void"]) for e in log["predictions"] if e.get("void")}
    assert koodit, "lokissa ei ole yhtaan void-rivia: tarkista lukija"
    tuntemattomat = sorted(koodit - b.TRK_VOID_REASONS)
    assert not tuntemattomat, (
        f"Uusi void-koodi lokissa: {tuntemattomat}. Paivita record_head_html:n "
        "raakaloki-lause (julkaisutarkistajan kautta) ja TRK_VOID_REASONS.")
    # NO_TIMESTAMP-rivit ovat MM-rivejä, kuten lause sanoo.
    nts = [e for e in log["predictions"] if e.get("void") == "NO_TIMESTAMP"]
    assert all(acc.model_of(e.get("competition")) == "national" for e in nts)


def test_predictions_html_karki_ennen_by_competitionia():
    agg = acc.compute_aggregate(acc.load_log())
    c = _ctx(agg)
    blk = (f"<style>{b.TRK_CSS}</style>" + b.record_head_html(c)
           + b.by_comp_html({**c, "by_comp": [{"name": "X", "pct": 50.0,
                                                "correct": 1, "n": 2,
                                                "dec_n": 0}]}))
    assert blk.index("Against the simplest rule") < blk.index("By competition")
    assert not re.search(r"\d\.\d{2,}%", blk), "prosentissa yli 1 desimaali"
