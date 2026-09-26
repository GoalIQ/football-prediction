"""Portti: tarkkuus malleittain (PROVENANCE-SEURAMALLI-609, 26.9.2026).

pro.goaliq.app:n alaviite sanoi "the same match model ... 49% correct 1X2
across 609 logged matches", vaikka 56 riveista oli maajoukkuemallin
MM-ennusteita. Seuramalli yksin oli 266/553 = 48,1 %. Jako tehdaan
`accuracy.model_of`:ssa yhdessa paikassa; tama portti pitaa huolen etta
(1) jokainen lokin kilpailukoodi on luokiteltu (uusi liiga ei putoa hiljaa
kumpaankaan), (2) lohkot summautuvat headlineen ja by_competitioniin, ja
(3) SPA:n alaviite lukee seuramallin lohkoa eika blended-lukua.
"""
from __future__ import annotations

from pathlib import Path

from src.models import accuracy as acc

ROOT = Path(__file__).resolve().parents[1]


def _entry(mid, competition, winner="home"):
    return {
        "match_id": mid, "source": "test", "competition": competition,
        "date": "2026-09-01", "home_team": "A", "away_team": "B",
        "p_home": 0.5, "p_draw": 0.3, "p_away": 0.2,
        "xg_home": None, "xg_away": None,
        "most_likely_score": "1-0", "predicted_winner": winner,
        "logged_at": "2026-09-01T00:00:00+00:00", "result": None,
    }


def test_jokainen_lokin_kilpailukoodi_on_luokiteltu():
    log = acc.load_log()
    koodit = {e.get("competition") for e in log["predictions"]}
    luokittelemattomat = sorted(str(k) for k in koodit if acc.model_of(k) is None)
    assert not luokittelemattomat, (
        f"Lokissa luokittelemattomia kilpailukoodeja: {luokittelemattomat}. "
        "Lisaa ne accuracy.CLUB_COMPETITIONS- tai NATIONAL_COMPETITIONS-joukkoon; "
        "muuten ne eivat nay kummankaan mallin tarkkuudessa."
    )


def test_joukot_eivat_leikkaa():
    assert not (acc.CLUB_COMPETITIONS & acc.NATIONAL_COMPETITIONS)


def test_lohkot_summautuvat_headlineen_ja_kilpailuriveihin():
    agg = acc.compute_aggregate(acc.load_log())
    bm = agg["by_model"]
    assert bm["unclassified_n"] == 0
    assert bm["club"]["n"] + bm["national"]["n"] == agg["all_time"]["n"]
    assert bm["club"]["correct_1x2"] + bm["national"]["correct_1x2"] == agg["all_time"]["correct_1x2"]
    comp = agg["by_competition"]
    assert bm["club"]["n"] == sum(v["n"] for k, v in comp.items() if k in acc.CLUB_COMPETITIONS)
    assert bm["national"]["n"] == sum(v["n"] for k, v in comp.items() if k in acc.NATIONAL_COMPETITIONS)
    # Kirjattujen maara jakautuu samoin (sivun "has logged N" -lause).
    assert (bm["club"]["logged_with_timestamp"] + bm["national"]["logged_with_timestamp"]
            == agg["logged_with_timestamp"])
    # MM-rivit ovat maajoukkuemallin, eivat seuramallin.
    if "WC" in comp:
        assert bm["national"]["n"] >= comp["WC"]["n"] > 0
        assert bm["club"]["n"] == agg["all_time"]["n"] - bm["national"]["n"]


def test_tuntematon_koodi_ei_putoa_hiljaa_kumpaankaan():
    log = acc.empty_log()
    for mid, comp in [("c1", "PL"), ("n1", "WC"), ("x1", "XYZ")]:
        acc.upsert_prediction(log, _entry(mid, comp))
        acc.set_result(log, mid, 1, 0)
    bm = acc.compute_aggregate(log)["by_model"]
    assert bm["club"]["n"] == 1
    assert bm["national"]["n"] == 1
    assert bm["unclassified_n"] == 1


def test_spa_alaviite_ei_vaita_blended_lukua_samaksi_malliksi():
    # Julkaisutarkistaja 26.9 (versio B): lause rajataan seuramalliin eika siina
    # ole lukua ennen kuin /predictions nayttaa seuramallin summan samasta
    # lahteesta. Blended-luku (all_time) ei saa palata tahan lauseeseen.
    src = (ROOT / "web/pro-spa/src/lib/components/Provenance.svelte").read_text(encoding="utf-8")
    assert "pre-match-logged club predictions" in src
    assert "all_time" not in src and "fetchAccuracy" not in src
    assert "https://goaliq.app/predictions#record" in src
