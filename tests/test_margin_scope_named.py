# -*- coding: utf-8 -*-
"""Marginaalilohko nimeaa otoksensa, kun se eroaa heron luvusta.

🔴 MITATTU 12.9.2026, julkaisutarkistajan sivuloydos kun se tarkisti postausta
joka linkkasi tahan lohkoon.

`goaliq.app/predictions` naytti KAKSI eri kokonaislukua eika kertonut mista
ero tulee:
    hero:            "51.1% result accuracy across 477 completed matches"
    marginaalilohko: "Measured 12 Sep 2026 from 429 graded matches"

Ero on todellinen ja oikea: 48 MM-rivilla ei ole `p_home`/`p_away`-lukua
lainkaan (mitattu prediction_log.json:sta: 477 gradattua, joista 48 ilman
todennakoisyytta, kaikki competition='WC'), joten ne EIVAT voi olla
marginaalimittauksessa mukana. Mutta nimeamaton ero lukee virheelta, ja tama
on juuri se sivu jolle jokainen postaus ohjaa tarkistamaan vaitteen.

Sama vikaluokka kuin muistiinpanossa `lause-ja-luku-eri-lahteesta`: kaksi
oikeaa lukua eri otoksista samalla sivulla ilman etta kumpikaan kertoo otosta.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build_fpl_page import _margin_scope, call_margin_html  # noqa: E402
from src.models.call_margin import measure_margin  # noqa: E402


def _doc(**kw) -> dict:
    d = {"margin_pp": 16, "decisive_below_n": 93, "decisive_below_won": 44,
         "decisive_below_pct": 47, "decisive_above_n": 221,
         "decisive_above_won": 172, "decisive_above_pct": 78,
         "n_graded": 429, "n_graded_all": 477, "n_below_margin": 140,
         "measured_at": "2026-09-12T06:36:11+00:00", "buckets": []}
    d.update(kw)
    return d


# ---------------------------------------------------------------------------
# 1. Otoksen nimeaminen
# ---------------------------------------------------------------------------

def test_ero_nimetaan_kun_se_on_olemassa():
    teksti = _margin_scope(_doc())
    assert "477" in teksti and "48" in teksti
    assert "World Cup" in teksti


def test_ei_lisataan_mitaan_kun_eroa_ei_ole():
    """NEGATIIVINEN KONTROLLI: selite ei saa ilmestya turhaan.

    Jos MM-rivit joskus saavat todennakoisyyden, lause muuttuisi
    epatodeksi - siksi se on ehdollinen eika kiinteaa copya."""
    assert _margin_scope(_doc(n_graded_all=429)) == ""
    assert _margin_scope(_doc(n_graded_all=None)) == ""
    assert _margin_scope({}) == ""


def test_lohko_sanoo_molemmat_luvut():
    html = call_margin_html(_doc())
    assert "429 graded matches" in html
    assert "477 in the record above" in html


def test_vanha_pelkka_luku_ei_saa_palata():
    """MUTAATIO: lause joka paattyy '429 graded matches.' ilman otosta."""
    html = call_margin_html(_doc())
    assert "429 graded matches." not in html, \
        "otos jai nimeamatta - lukija nakee kaksi eri kokonaislukua"


# ---------------------------------------------------------------------------
# 2. Mittari laskee molemmat luvut samasta silmukasta
# ---------------------------------------------------------------------------

def _rivi(ph, pa, actual="home", hit=True, voided=False):
    return {"p_home": ph, "p_away": pa,
            "result": {"actual_outcome": actual, "hit_1x2": hit,
                       "voided": voided}}


def test_n_graded_all_kattaa_myos_todennakoisyydettomat():
    rivit = [_rivi(0.6, 0.2), _rivi(0.5, 0.3),
             _rivi(None, None), _rivi(0.4, None)]
    out = measure_margin(rivit)
    assert out["n_graded"] == 2, out["n_graded"]
    assert out["n_graded_all"] == 4, out["n_graded_all"]


def test_mitatoidyt_eivat_ole_kummassakaan():
    rivit = [_rivi(0.6, 0.2), _rivi(0.6, 0.2, voided=True)]
    out = measure_margin(rivit)
    assert out["n_graded"] == 1
    assert out["n_graded_all"] == 1


def test_kontrolli_mittari_ei_palauta_nollia():
    """Ilman tata molemmat ylla olevat menisivat lapi tyhjalla syotteella."""
    out = measure_margin([])
    assert out["n_graded"] == 0 and out["n_graded_all"] == 0


@pytest.mark.skipif(not (ROOT / "data" / "call_margin.json").is_file(),
                    reason="artefaktia ei ole")
def test_tuotantoartefakti_kantaa_kentan():
    """KONTROLLI: ilman tata sivukorjaus olisi vihrea vaikka artefakti ei
    koskaan anna `n_graded_all`ia - eli lause jaisi pois tuotannossa."""
    import json
    doc = json.loads((ROOT / "data" / "call_margin.json").read_text(encoding="utf-8"))
    assert isinstance(doc.get("n_graded_all"), int), doc.keys()
    assert doc["n_graded_all"] >= doc["n_graded"]


# ---------------------------------------------------------------------------
# 3. 29.9.2026 (TRACK-RECORD-NIMIKKEET kohta 5): mittaus vain seuramallista
# ---------------------------------------------------------------------------
# Marginaali koskee seuraotteluita, mutta se mitattiin koko lokista (609),
# jossa on 56 MM-rivia maajoukkuemallista TODENNAKOISYYKSINEEN. Seuramalli
# yksin: 553 -> 49 %, sivu sanoi 48 %. Lisaksi lohkon lause "logged without a
# win probability" olisi ollut epatosi heti kun MM-rivit rajataan pois.

def _loki(tmp_path, rivit):
    import json
    p = tmp_path / "prediction_log.json"
    p.write_text(json.dumps({"predictions": rivit}), encoding="utf-8")
    return p


def _lokirivi(comp, ph, pa, actual, hit, i):
    return {"id": f"r{i}", "competition": comp, "p_home": ph, "p_draw": 0.25,
            "p_away": pa, "date": "2026-08-20", "logged_at": "2026-08-19T10:00:00Z",
            "result": {"actual_outcome": actual, "hit_1x2": hit}}


def test_mittari_kayttaa_vain_seuramallin_riveja(tmp_path):
    from scripts.measure_call_margin import build
    from src.models.accuracy import counts_in_record
    seura = [_lokirivi("PL", 0.55, 0.20, "home", True, i) for i in range(30)]
    # MM-rivit joissa nimetty puoli haviaa aina: jos ne olisivat mukana,
    # osumat putoaisivat 30/30:sta.
    mm = [_lokirivi("WC", 0.55, 0.20, "away", False, 100 + i) for i in range(12)]
    assert all(counts_in_record(r) for r in seura + mm), "fikstuuri ei laske recordiin"
    out = build(_loki(tmp_path, seura + mm))
    assert out["scope"] == "club"
    assert out["n_graded"] == 30, out["n_graded"]
    assert out["n_graded_all"] == 42
    assert out["excluded"] == {"other_model": 12, "other_model_competitions": ["WC"],
                               "no_win_probability": 0}
    assert out["decisive_above_won"] == 30 and out["decisive_above_n"] == 30


def test_lause_johdetaan_poissulkulaskureista():
    d = _doc(n_graded=553, n_graded_all=609, scope="club",
             excluded={"other_model": 56, "other_model_competitions": ["WC"],
                       "no_win_probability": 0})
    teksti = _margin_scope(d)
    assert teksti == (" of the 609 in the record above; the other 56 are "
                      "World Cup fixtures from the national-team model"), teksti
    assert "without a win probability" not in teksti
    html = call_margin_html(d)
    assert "553 graded club matches of the 609" in html


def test_muu_kilpailu_ei_ole_world_cup():
    d = _doc(n_graded=553, n_graded_all=570, excluded={
        "other_model": 17, "other_model_competitions": ["UNL", "WC"],
        "no_win_probability": 0})
    assert "national-team fixtures" in _margin_scope(d)
    assert "World Cup" not in _margin_scope(d)


def test_kaksi_syyta_molemmat_nimetaan():
    d = _doc(n_graded=549, n_graded_all=609, excluded={
        "other_model": 56, "other_model_competitions": ["WC"], "no_win_probability": 4})
    t = _margin_scope(d)
    assert "56 are World Cup fixtures" in t and "4 are logged without a win probability" in t


def test_laskurit_eivat_selita_eroa_ei_keksita_syyta():
    """NEGATIIVINEN KONTROLLI: ero 56, laskurit sanovat 50 -> ei syylausetta."""
    d = _doc(n_graded=553, n_graded_all=609, excluded={
        "other_model": 50, "other_model_competitions": ["WC"], "no_win_probability": 0})
    t = _margin_scope(d)
    assert t == " of the 609 in the record above"


@pytest.mark.skipif(not (ROOT / "data" / "call_margin.json").is_file(),
                    reason="artefaktia ei ole")
def test_tuotantoartefakti_on_seuramallin():
    """KUTSUPAIKKA: committattu artefakti on mitattu rajatulla mittarilla."""
    import json
    doc = json.loads((ROOT / "data" / "call_margin.json").read_text(encoding="utf-8"))
    assert doc.get("scope") == "club", "artefakti on mitattu ilman seuramallirajausta"
