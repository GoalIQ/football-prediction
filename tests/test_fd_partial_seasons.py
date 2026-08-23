"""football_data_org.lataa: osittainen kausijoukko ei saa myrkyttää mallia.

Tausta (23.8.2026, FL1-TEAM-COVERAGE): tuotannon
`/api/teams?leagues=FRA-Ligue 1-FD` palautti 12 joukkuetta 18:sta ja
`/api/predict` antoi 404:n PSG:lle, Lillelle, Monacolle, Rennesille,
Angersille ja Le Havrelle. Mitattu: `seasons=2526` yksin palautti 18,
pari `2526`+`2627` palautti 12 — tasan ne jotka olivat ehtineet pelata
26/27-kaudella.

Juurisyy: epäonnistunut kausihaku putosi `lataa()`:n suodattimesta hiljaa ja
malli fitattiin jäljelle jääneellä kaudella. `_saa_malli` cachettaa mallin
prosessin eliniäksi → YKSI 429 instanssin käynnistyessä rikkoi liigan
pysyvästi, ilman virhettä tai lokiriviä.
"""
from __future__ import annotations

import pandas as pd
import pytest

import src.data.football_data_org as fdo


LIIGA = "FRA-Ligue 1-FD"


def _ottelu(koti: str, vieras: str) -> dict:
    return {
        "utcDate": "2026-08-22T15:00:00Z",
        "status": "FINISHED",
        "homeTeam": {"name": koti},
        "awayTeam": {"name": vieras},
        "score": {"fullTime": {"home": 1, "away": 0}},
    }


@pytest.fixture
def kaudet_stub(monkeypatch):
    """Ohjaa _hae_kausi-vastaukset kausikohtaisesti ilman verkkoa."""
    vastaukset: dict[str, dict | None] = {}

    def fake_hae(code, year, api_key):
        return vastaukset.get(year)

    monkeypatch.setattr(fdo, "_api_key", lambda: "avain")
    monkeypatch.setattr(fdo, "_hae_kausi", fake_hae)
    return vastaukset


def test_osittainen_kausijoukko_nostaa_eika_kavenna_hiljaa(kaudet_stub):
    """Yksi kausi onnistuu, toinen kaatuu → virhe, ei vajaata DataFramea."""
    kaudet_stub["2025"] = {"_error": "HTTP 429: too many requests"}
    kaudet_stub["2026"] = {"matches": [_ottelu("Lens", "Auxerre")]}

    with pytest.raises(fdo.OsittainenKausijoukko) as e:
        fdo.lataa(LIIGA, ["2526", "2627"])
    # viesti nimeää kauden ja syyn — muuten vikaa ei voi paikantaa lokista
    assert "2526" in str(e.value)
    assert "429" in str(e.value)


def test_kaikki_kaudet_onnistuvat_palauttaa_datan(kaudet_stub):
    kaudet_stub["2025"] = {"matches": [_ottelu("Paris Saint-Germain FC",
                                               "Lille OSC")]}
    kaudet_stub["2026"] = {"matches": [_ottelu("Lens", "Auxerre")]}

    df = fdo.lataa(LIIGA, ["2526", "2627"])
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    # 25/26:n joukkueet ovat mukana — juuri ne jotka tuotannosta puuttuivat
    nimet = set(df["home_team"]) | set(df["away_team"])
    assert {"Paris Saint-Germain FC", "Lille OSC"} <= nimet


def test_tyhja_mutta_onnistunut_kausi_ei_ole_virhe(kaudet_stub):
    """Esikausi: 0 ottelua on kelvollinen vastaus, ei epäonnistuminen."""
    kaudet_stub["2025"] = {"matches": [_ottelu("Lens", "Auxerre")]}
    kaudet_stub["2026"] = {"matches": []}

    df = fdo.lataa(LIIGA, ["2526", "2627"])
    assert len(df) == 1


def test_kaikkien_kausien_kaatuminen_palauttaa_tyhjan_ei_nosta(kaudet_stub):
    """Ei osittaista dataa → ei myrkytystä → vanha käytös säilyy."""
    kaudet_stub["2025"] = {"_error": "HTTP 500"}
    kaudet_stub["2026"] = None

    df = fdo.lataa(LIIGA, ["2526", "2627"])
    assert df.empty
