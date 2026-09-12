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
