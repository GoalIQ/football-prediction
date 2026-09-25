# -*- coding: utf-8 -*-
"""Track recordiin lasketaan vain gradattu EI-void rivi, yksi lukija (25.9.2026).

Villen paatos 25.9: kesan MM-hubin 48 rivia (ei aikaleimaa, joten lupaus
"logged before kick-off" ei ole niille tarkistettavissa) pois track recordista,
merkittyna void NO_TIMESTAMP. Niilla ON tulos, joten ennen `void` ei olisi
riittanyt: aggregaatti, per-ottelu-taulukko ja call margin suodattivat kukin
`if e.get("result")`. Nyt kaikki lukevat `accuracy.counts_in_record`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.models import accuracy as acc

ROOT = Path(__file__).resolve().parents[1]
LOG = json.loads((ROOT / "data" / "prediction_log.json").read_text(encoding="utf-8"))


def _rivi(void=None, hit=True, logged_at="2026-09-01T10:00:00+00:00"):
    r = {"match_id": "x", "result": {"hit_1x2": hit, "actual_outcome": "home"},
         "logged_at": logged_at}
    if void:
        r["void"] = void
    return r


def test_void_rivi_tuloksella_ei_laske():
    """MUTAATIO: poista `and not e.get("void")` -> punainen."""
    assert acc.counts_in_record(_rivi()) is True
    assert acc.counts_in_record(_rivi(void="NO_TIMESTAMP")) is False
    assert acc.counts_in_record({"match_id": "y", "result": None}) is False


def test_aikaleimaton_rivi_ei_laske_ilman_void_merkintaakaan():
    """Uusi aikaleimaton lahde ei paase recordiin vaikka void unohtuisi.
    MUTAATIO: poista `and bool(e.get("logged_at"))` -> punainen."""
    assert acc.counts_in_record(_rivi(logged_at=None)) is False


def test_aggregaatti_ei_laske_void_riveja():
    log = {"predictions": [_rivi(), _rivi(void="NO_TIMESTAMP", hit=False)]}
    assert len(acc._resolved(log)) == 1


def test_kaikki_mm_hubin_rivit_ovat_void():
    seed = [r for r in LOG["predictions"] if str(r.get("source") or "").startswith("wc_hub")]
    assert len(seed) == 48
    assert all(r.get("void") == "NO_TIMESTAMP" and r.get("void_reason") for r in seed)


def test_track_recordissa_ei_yhtaan_aikaleimatonta_rivia():
    """Lupaus 'logged before kick-off': jokaisella lasketulla rivilla on
    kirjausaika. Tama on se ehto jonka vuoksi seed-rivit poistettiin."""
    lasketut = acc._resolved(LOG)
    assert lasketut, "tyhja track record"
    assert all(r.get("logged_at") for r in lasketut), [
        r["match_id"] for r in lasketut if not r.get("logged_at")][:5]


def _sivun_konteksti() -> dict:
    """Sama polku kuin CI:n bake: build_context artefakteista."""
    from scripts import build_fpl_page as bfp
    doc_path = ROOT / "data" / "fpl_projections_phase0.json"
    if not doc_path.exists():
        pytest.skip("fpl_projections_phase0.json puuttuu")
    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    # Aggregaatti lasketaan lokista tassa: data/accuracy.json voi olla hetken
    # lokia jaljessa (uudet odottavat rivit) ilman etta mikaan on rikki.
    return bfp.build_context(doc, acc.compute_aggregate(LOG))


def test_julkinen_taulukko_jattaa_pois_ja_kertoo_maaran():
    from scripts.build_fpl_page import record_table_html
    html = record_table_html(LOG["predictions"], _sivun_konteksti())
    # count() eika `in`: pytestin `not in` -diff valtavaan HTML:aan jumittaa.
    assert html.count("48 World Cup 2026 group-stage predictions") == 1
    assert html.count("data/prediction_log.json") == 1
    # mexico-south-africa oli seed-rivi: ei enaa taulukossa
    assert html.count("Mexico v South Africa") == 0


def test_sivun_luvut_eivat_laske_aikaleimattomia_eika_voideja():
    """'logged N predictions before kickoff' = rivit joilla on kirjausaika;
    'N further predictions ... upcoming' = accuracy.is_pending. Ennen 25.9
    `logged_total - n` laski void-rivit (siirretyt + 48 MM-rivia) tuleviksi.
    MUTAATIO: palauta `max(0, logged - n)` tai `acc.get("logged_total")`
    build_contextiin -> punainen."""
    c = _sivun_konteksti()
    preds = LOG["predictions"]
    assert c["acc_logged"] == sum(1 for e in preds if e.get("logged_at"))
    assert c["acc_pending"] == sum(1 for e in preds if acc.is_pending(e))
    assert c["acc_n"] == len(acc._resolved(LOG))


def test_call_margin_ei_laske_void_riveja():
    """Sivun call margin -lohko sanoo 'from N graded matches' samasta
    joukosta kuin record. MUTAATIO: `r.get("result")` measure_call_marginiin
    -> punainen."""
    from scripts.measure_call_margin import build
    out = build(ROOT / "data" / "prediction_log.json")
    assert out["n_graded_all"] == len(acc._resolved(LOG))


def test_laskemattomat_gradatut_ovat_aikaleimattomia_mm_riveja():
    """Record-nootti ja MM-hubin lohko sanovat 'World Cup 2026 group-stage
    predictions ... without a timestamp'. Jos joukkoon tulee muu kilpailu tai
    muu syy, sanamuoto on epatosi: paivita nootti ja tama testi yhdessa."""
    pois = [e for e in LOG["predictions"]
            if e.get("result") and not acc.counts_in_record(e)]
    assert pois
    assert all(e.get("competition") == "WC" and not e.get("logged_at")
               for e in pois), [e["match_id"] for e in pois
                                if e.get("competition") != "WC" or e.get("logged_at")][:5]
    # Lohkovaihe: kaikki pudotuspelit (32) ovat aikaleimallisia.
    wc_ts = [e for e in LOG["predictions"]
             if e.get("competition") == "WC" and acc.counts_in_record(e)]
    assert sum(1 for e in wc_ts if (e.get("date") or "") >= "2026-06-28") >= 32


def test_mm_hubin_lohko_nimeaa_erotuksen(tmp_path, monkeypatch):
    """MUTAATIO: poista pois_txt update_wc_recapista -> punainen."""
    from scripts import build_fpl_page as bfp
    hub = tmp_path / "wc.html"
    hub.write_text("<!-- GEN:WCRECAP-START --><!-- GEN:WCRECAP-END -->",
                   encoding="utf-8")
    monkeypatch.setattr(bfp, "WC_HUB_PATH", hub)
    assert bfp.update_wc_recap(acc.compute_aggregate(LOG), LOG["predictions"])
    html = hub.read_text(encoding="utf-8")
    assert html.count("across all") == 0
    assert html.count("48 group-stage predictions were added to the log "
                      "without a timestamp") == 1
