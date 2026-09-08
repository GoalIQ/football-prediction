"""Portti: lahteen katkos ei saa nayttaa kattavuusaukolta.

🔴 MITATTU VIKA (8.9.2026, Villen kaverin bugiraportista johtanut selvitys).
football-data.co.uk oli KOKONAAN alhaalla — 503 myos sivun juuresta, header
`Retry-After: 61`. Neljan liigan koko Predict-pinta kuoli:

    GET /api/teams?leagues=ENG-Championship&seasons=2526&seasons=2627
      -> 404 {"detail": "No match data found for leagues=(...), seasons=(...)"}

Sama 404 tuli myos Eredivisielle, Primeira Ligalle ja Brasileiraolle, ja
`POST /api/predict` samoin. Vastaus VAITTI ettei liigalle ole otteludataa.
Se ei ollut totta: data on olemassa, lahde ei vastannut. Ero on kayttajalle
eri asia ("tata ei ole" vs "yrita uudelleen") ja meille eri korjaus.

Loaderilla oli syy tiedossa koko ajan — `LoaderTulokset.virheet` sisalsi
`football-data.co.uk: HTTPError: 503`. Ohut kaari `lataa_otteludata` heitti
sen pois palauttaessaan pelkan DataFramen, ja API joutui arvaamaan.

MIKSI EI MERKKIJONOSTA PAATTELEMALLA: virhetekstin nuuskiminen jalkikateen
olisi sama sokea kuvio joka on kaatanut meidat ennenkin. Katkos kirjataan nyt
`LoaderTulokset.katkokset`-kenttaan SIINA KOHDASSA jossa se tiedetaan, eli
poikkeuskasittelijassa.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.data import loader


@pytest.fixture(autouse=True)
def _tyhjenna_diagnoosi():
    with loader._DIAG_LOCK:
        loader._VIIMEISIN_DIAGNOOSI.clear()
    yield
    with loader._DIAG_LOCK:
        loader._VIIMEISIN_DIAGNOOSI.clear()


def _tulos(data: pd.DataFrame, virheet=None, katkokset=None) -> loader.LoaderTulokset:
    t = loader.LoaderTulokset()
    t.data = data
    t.virheet = dict(virheet or {})
    t.katkokset = dict(katkokset or {})
    return t


def test_katkos_talletetaan_ja_luetaan(monkeypatch):
    """Tasan 8.9 mitattu tila: lahde vastasi 503:lla."""
    monkeypatch.setattr(
        loader,
        "lataa_otteludata_yksityiskohtaisesti",
        lambda liigat, kaudet: _tulos(
            pd.DataFrame(),
            virheet={"ENG-Championship": "football-data.co.uk: HTTPError: 503"},
            katkokset={"ENG-Championship": "football-data.co.uk: HTTPError"},
        ),
    )
    df = loader.lataa_otteludata(["ENG-Championship"], ["2526", "2627"])
    assert df.empty
    virheet, katkokset = loader.viimeisin_diagnoosi(
        ["ENG-Championship"], ["2526", "2627"]
    )
    assert katkokset, "katkos katosi ohuen kaaren lapi — API joutuisi arvaamaan"
    assert "ENG-Championship" in katkokset


def test_aito_kattavuusaukko_ei_ole_katkos(monkeypatch):
    """NEGATIIVINEN KONTROLLI. Jos kaikki tyhja tulkittaisiin katkokseksi,
    503 alkaisi vastata myos kausille joita ei oikeasti ole julkaistu — ja
    klientti jaisi ikuiseen uudelleenyritykseen."""
    monkeypatch.setattr(
        loader,
        "lataa_otteludata_yksityiskohtaisesti",
        lambda liigat, kaudet: _tulos(
            pd.DataFrame(),
            virheet={"INT-Champions League": "football-data.co.uk: ei dataa kausille"},
            katkokset={},
        ),
    )
    loader.lataa_otteludata(["INT-Champions League"], ["2627"])
    virheet, katkokset = loader.viimeisin_diagnoosi(["INT-Champions League"], ["2627"])
    assert virheet
    assert not katkokset


def test_onnistunut_haku_ei_jata_vanhaa_diagnoosia(monkeypatch):
    """Jaanyt diagnoosi vaittaisi katkosta liigalle joka on jo kunnossa."""
    avain = (["ENG-Championship"], ["2526", "2627"])
    monkeypatch.setattr(
        loader,
        "lataa_otteludata_yksityiskohtaisesti",
        lambda liigat, kaudet: _tulos(
            pd.DataFrame(), katkokset={"ENG-Championship": "x: HTTPError"}
        ),
    )
    loader.lataa_otteludata(*avain)
    assert loader.viimeisin_diagnoosi(*avain)[1]

    monkeypatch.setattr(
        loader,
        "lataa_otteludata_yksityiskohtaisesti",
        lambda liigat, kaudet: _tulos(pd.DataFrame({"home_team": ["A"]})),
    )
    loader.lataa_otteludata(*avain)
    assert loader.viimeisin_diagnoosi(*avain) == ({}, {})


def test_tuntematon_avain_on_en_tieda_eika_ei_katkosta():
    """Kutsujan on erotettava 'ei kysytty' ja 'ei katkosta'. Tyhja pari
    tarkoittaa edellista, ja `viimeisin_diagnoosi`n docstring sanoo sen —
    tama lukitsee sen etta paluuarvo on tyhja eika esim. None."""
    assert loader.viimeisin_diagnoosi(["EI-OLE"], ["9999"]) == ({}, {})


# ---------------------------------------------------------------------------
# API:n haara. Vika oli VASTAUKSESSA, joten portti mittaa vastauksen.
# ---------------------------------------------------------------------------


def test_api_vastaa_503_katkokseen_ja_404_aitoon_puutteeseen(monkeypatch):
    from fastapi import HTTPException

    import api.main as main

    monkeypatch.setattr(
        main, "_lataa_otteludata_cached", lambda liigat, kaudet: pd.DataFrame()
    )

    monkeypatch.setattr(
        loader,
        "viimeisin_diagnoosi",
        lambda liigat, kaudet: ({"L": "x"}, {"L": "football-data.co.uk: HTTPError"}),
    )
    with pytest.raises(HTTPException) as exc:
        main._fit_malli(("ENG-Championship",), ("2526", "2627"), 0.005, 0.0, False, False)
    assert exc.value.status_code == 503
    assert "temporary outage" in str(exc.value.detail)
    # Vanha teksti syytti API-avainta ja ilmaista tieria datasta jonka lahde
    # kylla tarjoaa. Se ei saa palata.
    assert "free tier" not in str(exc.value.detail).lower()

    monkeypatch.setattr(loader, "viimeisin_diagnoosi", lambda liigat, kaudet: ({}, {}))
    with pytest.raises(HTTPException) as exc:
        main._fit_malli(("INT-Champions League",), ("2627",), 0.005, 0.0, False, False)
    assert exc.value.status_code == 404
