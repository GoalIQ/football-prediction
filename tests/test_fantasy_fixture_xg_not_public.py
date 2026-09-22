"""Ottelua edeltava xG ei lahde ulos /api/fantasyn tickerissa (Villen paatos
22.9.2026: "poista").

Julkinen tarkkuusloki siivottiin samana paivana, mutta kirjautumaton
`GET /api/fantasy` palautti `fixtures[]`-listassa `xg_home`/`xg_away` 60
tulevasta ottelusta (kuusi kierrosta) koneluettavana. Sama vuoto, eri reitti,
ja PREDICT_MASKin kiertotie: maski piilottaa saman luvun /api/predictista.

Sivun oma "projected goals" -rivi ei kulje tasta (build_fpl_page lukee
artefaktin), joten ilmaisen CS-%:n tarkistusreitti sailyy.

Vaiheet: rajattu vastaus (oletus horizon), horizon=all, ja artefakti itse
(sisainen data ei saa kadota).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.premium import FIXTURE_PRIVATE_FIELDS, public_fixture_rows

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


def _fixtures(params: dict | None = None) -> list[dict]:
    r = client.get("/api/fantasy", params=params or {})
    assert r.status_code == 200, r.text
    return r.json().get("fixtures") or []


def test_funktio_poistaa_vain_xgn():
    rivi = {"home": "Arsenal", "away": "Leeds", "xg_home": 1.9, "xg_away": 0.8,
            "p_home_win": 0.63, "cs_home_pct": 46.5, "fdr_home": 1}
    out = public_fixture_rows([rivi])[0]
    assert "xg_home" not in out and "xg_away" not in out
    assert out["p_home_win"] == 0.63 and out["cs_home_pct"] == 46.5 and out["fdr_home"] == 1
    assert public_fixture_rows(None) is None, "vieras tyyppi ei saa kaatua"


@pytest.mark.parametrize("params", [{}, {"horizon": "all"}, {"horizon": "1"}])
def test_kirjautumaton_vastaus_ei_kanna_xgta(params):
    fx = _fixtures(params)
    if not fx:
        pytest.skip("projektiossa ei ole otteluita")
    vuotavat = [f for f in fx if any(k in f for k in FIXTURE_PRIVATE_FIELDS)]
    assert vuotavat == [], f"{len(vuotavat)}/{len(fx)} ottelua kantaa xG:ta"


def test_muut_ticker_kentat_jaavat():
    """Erotteleva: jos vastaus olisi tyhja, edellinen testi olisi vihrea turhaan."""
    fx = _fixtures()
    if not fx:
        pytest.skip("projektiossa ei ole otteluita")
    assert any("cs_home_pct" in f for f in fx)
    assert any("p_home_win" in f for f in fx)


def test_artefaktissa_xg_on_yha():
    """Sisainen data sailyy: sivun 'projected goals' rakennetaan tasta."""
    p = ROOT / "data" / "fpl_projections_phase0.json"
    if not p.exists():
        pytest.skip("artefakti puuttuu")
    fx = json.loads(p.read_text(encoding="utf-8")).get("fixtures") or []
    if not fx:
        pytest.skip("artefaktissa ei otteluita")
    assert any(f.get("xg_home") is not None for f in fx), \
        "xG katosi artefaktista: silloin siivous tehtiin vaarassa paikassa"
