# -*- coding: utf-8 -*-
"""\"The model plays no chips\" on mitattava vaite, ei vakio (12.9.2026).

🔴 MITATTU LAHTEESTA. `src/models/fpl_model_race.py` palautti
`"model_plays_chips": False` **kovakoodattuna vakiona** kahdessa kohdassa, ja
SPA renderoi sen varassa lauseen:

    web/pro-spa/src/lib/components/SeasonRace.svelte
    {#if !data.meta.model_plays_chips}
        The model's squad is locked before every deadline and plays no chips.

Samaan aikaan `data/model_squad_gw_scores.json` sanoo:

    GW1  41 p  active_chip None
    GW2 108 p  active_chip 'wildcard'
    GW3  72 p  active_chip '3xc'

Eli **kauden kaksi isointa lukua ovat chip-lukuja** ja lause niiden alla
sanoi ettei chippeja pelata. FPL:n oma historia vahvistaa: entry 116920
chips = wildcard (GW2, 28.8 17:17:50Z) ja 3xc (GW3, 4.9 10:09:04Z).

Moduulin docstring perusteli kentan sanomalla etta se on olemassa "jotta
paneelin ei tarvitse paatella sita copysta" — mutta kentta ei lukenut
mitaan. Portti oli nimi, ei mittaus.

Tama testi kaataa vakion. Julkinen sanamuoto on oma asiansa ja vaatii
julkaisutarkistajan + Villen GO:n; tama vartioi vain etta LIPPU kertoo
totuuden, jottei mikaan pinta voi vaittaa vastakkaista vahingossa.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.models.fpl_model_race import build_race

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "data" / "model_squad_gw_scores.json"


def _loki(rivit):
    return {"meta": {"entry_id": 1}, "gameweeks": rivit}


def _rivi(gw, points, chip=None):
    return {"gw": gw, "points": points, "active_chip": chip,
            "fpl_average": 50, "transfer_cost": 0, "provisional": False}


def test_chip_rivi_kaantaa_lipun():
    d = build_race(_loki([_rivi(1, 41), _rivi(2, 108, "wildcard")]),
                   None, premium=True)
    assert d["meta"]["model_plays_chips"] is True
    assert d["meta"]["chips_played"] == ["wildcard"]


def test_ilman_chippeja_lippu_on_false():
    """Negatiivinen kontrolli: portti ei saa olla aina punainen."""
    d = build_race(_loki([_rivi(1, 41), _rivi(2, 60)]), None, premium=True)
    assert d["meta"]["model_plays_chips"] is False
    assert d["meta"]["chips_played"] == []


def test_useampi_chip_luetellaan_kertaalleen():
    d = build_race(_loki([_rivi(1, 41, "3xc"), _rivi(2, 108, "wildcard"),
                          _rivi(3, 72, "3xc")]), None, premium=True)
    assert d["meta"]["chips_played"] == ["3xc", "wildcard"]


def test_tyhja_loki_ei_vaita_ettei_chippeja_pelata():
    d = build_race(_loki([]), None, premium=True)
    assert d["meta"]["model_plays_chips"] is False
    assert d["meta"]["chips_played"] == [], (
        "tyhja lista kertoo 'ei pelattu', ei 'ei pelata'")


def test_repon_oma_loki_kertoo_totuuden():
    """🔴 Eläva tila: jos tama kaatuu vaitteella False, jokin pinta lupaa
    juuri nyt jotain mika ei ole totta."""
    if not LOG.exists():
        pytest.skip("model_squad_gw_scores.json puuttuu")
    d = build_race(json.loads(LOG.read_text(encoding="utf-8")), None,
                   premium=True)
    pelatut = d["meta"]["chips_played"]
    lokista = sorted({r["active_chip"] for r in
                      json.loads(LOG.read_text(encoding="utf-8"))["gameweeks"]
                      if r.get("active_chip")})
    assert pelatut == lokista
    assert d["meta"]["model_plays_chips"] is bool(lokista)


def test_lippu_ei_ole_kovakoodattu_lahteessa():
    """Vakio ei saa palata. Merkkijonoportti on tassa perusteltu: se vartioi
    tasan sen muodon joka oli vika (`\"model_plays_chips\": False` ilman
    ehtoa) eika yrita korvata ylla olevia kaytostesteja."""
    src = (ROOT / "src" / "models" / "fpl_model_race.py").read_text(
        encoding="utf-8")
    # Sallittu: tyhjan lokin haara, jossa se on tosiasia.
    osumat = [r for r in src.split("\n")
              if '"model_plays_chips": False' in r and "chips_played" not in r]
    assert not osumat, (
        f"model_plays_chips kovakoodattu ilman chips_played-kontekstia: "
        f"{osumat}")
