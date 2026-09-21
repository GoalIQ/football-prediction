# -*- coding: utf-8 -*-
"""CHIP-ARVIO-EI-LUE-KAYTETTYJA-CHIPPEJA (21.9.2026, yöajo).

`scripts/freeze_model_squad_gw._chip_evaluation` laski pelattavat kierrokset
pelkästä deadlinesta (`[g for g in covered if g >= gw]`) eikä koskaan
tarkistanut oliko wildcard jo pelattu. Mitattu tuotannosta 18.9: entry 116920
pelasi wildcardin GW2:ssa, ja `gw5.json` silti suositteli sitä uudelleen.
`/api/fantasy/wildcard-plan` korjasi saman vian 3.9 (CHIP-EV-CHIPS-USED)
`fpl_chips`-lukijalla, mutta korjaus ei kulkeutunut freezeen.

Vaiheinvariantti (CLAUDE.md 6a-3): sama kysymys — "onko wildcard pelattu
TÄLLÄ puolikkaalla" — mitataan neljässä synteettisessä chip-historiassa,
ei vain tämänhetkisessä. Testi kohdistuu kahteen tasoon:
  (1) `_chip_played_gw`: puhdas lukija, joka johtaa vastauksen bootstrapista
      + entryn historiasta (fpl_chips.chip_state).
  (2) `_chip_evaluation`: että lukijan tulos oikeasti kulkeutuu
      `fpl_wildcard.wildcard_plan`iin eikä jää käyttämättömäksi.
`wildcard_plan`in oma kieltäytyminen (ei enää kutsujan `gws`-suodatuksen
varassa) testataan `test_wildcard_plan.py`:ssä.
"""
from __future__ import annotations

from unittest import mock

from scripts import freeze_model_squad_gw as freeze
from src.models import fpl_model_entry as entry_mod

# Sama chip-ikkunamuoto kuin test_chip_ev_chips_used.py: kaksi puolikasta,
# wildcard auki GW2-19 ja GW20-38.
BOOT = {"chips": [
    {"name": "wildcard", "start_event": 2, "stop_event": 19},
    {"name": "wildcard", "start_event": 20, "stop_event": 38},
]}


def _hist(chips):
    return ({"current": [], "chips": chips}, None)


def _no_history():
    return (None, "entryn historiaa ei saatu (verkkoa ei ole yöajossa)")


# ---------------------------------------------------------------------------
# 1. `_chip_played_gw` — vaiheinvariantti neljällä synteettisellä historialla
# ---------------------------------------------------------------------------

def test_ei_pelattu_palauttaa_none():
    """Puolikas auki, wildcardia ei ole pelattu -> saatavilla."""
    out = freeze._chip_played_gw(BOOT, 5, hae_historia=lambda _e: _hist([]))
    assert out is None


def test_pelattu_tassa_kierroksessa_palauttaa_gw():
    """Wildcard pelattu JUURI sillä kierroksella jolle freeze arvioi."""
    out = freeze._chip_played_gw(
        BOOT, 5, hae_historia=lambda _e: _hist([{"name": "wildcard", "event": 5}]))
    assert out == 5


def test_pelattu_aiemmin_samalla_puolikkaalla_palauttaa_alkuperaisen_gw():
    """Tämä on tuotannon mitattu tapaus: pelattu GW2:ssa, arvioidaan GW5:lle."""
    out = freeze._chip_played_gw(
        BOOT, 5, hae_historia=lambda _e: _hist([{"name": "wildcard", "event": 2}]))
    assert out == 2


def test_toisen_puoliskon_wildcard_on_auki_vaikka_eka_on_kaytetty():
    """Ensimmäinen puolikas käytetty, mutta kysytty GW liikkuu toiseen
    puolikkaaseen (GW20+) -> ei pelattu, saatavilla jälleen."""
    out = freeze._chip_played_gw(
        BOOT, 22, hae_historia=lambda _e: _hist([{"name": "wildcard", "event": 2}]))
    assert out is None


def test_historian_hakuvirhe_ei_kaada_vaan_palauttaa_none():
    """Yöajossa ei ole verkkoa: virhe historian haussa ei saa näyttää siltä
    että chip on pelattu (fail-open tähän suuntaan olisi väärä tapa - se ei
    SAA näyttää käytettynä sellaista jonka tilaa ei tiedetä; `_chip_evaluation`
    hoitaa kokonaisvirheen omalla except-haarallaan)."""
    out = freeze._chip_played_gw(BOOT, 5, hae_historia=lambda _e: _no_history())
    assert out is None


# ---------------------------------------------------------------------------
# 2. `_chip_evaluation` — tulos kulkeutuu oikeasti wildcard_plan:iin
# ---------------------------------------------------------------------------

def _patch_wildcard_plan(monkeypatch, spy_return=None):
    calls = []

    def _fake(*args, **kwargs):
        calls.append(kwargs)
        return spy_return if spy_return is not None else {"available": True}

    monkeypatch.setattr("src.models.fpl_wildcard.wildcard_plan", _fake)
    return calls


def test_chip_evaluation_valittaa_pelatun_chipin_wildcard_planille(monkeypatch):
    calls = _patch_wildcard_plan(monkeypatch)
    hae = lambda _e: _hist([{"name": "wildcard", "event": 2}])
    freeze._chip_evaluation([], [], 5, {}, BOOT, hae_historia=hae)
    assert len(calls) == 1
    assert calls[0]["chip_played_gw"] == 2, calls[0]


def test_negatiivinen_kontrolli_ei_pelattua_chippia_ei_valiteta_pelatuksi(monkeypatch):
    """Ilman pelattua chippiä `chip_played_gw` on None - `wildcard_plan`
    saa päättää normaalisti `gws`:n perusteella, kuten ennen tätä korjausta."""
    calls = _patch_wildcard_plan(monkeypatch)
    hae = lambda _e: _hist([])
    freeze._chip_evaluation([], [], 5, {}, BOOT, hae_historia=hae)
    assert len(calls) == 1
    assert calls[0]["chip_played_gw"] is None, calls[0]


def test_regressio_ilman_chip_played_gw_wildcard_plan_ei_kieltaydy():
    """Kontrasti joka todistaa etta testi mittaa oikeaa asiaa: KUTSUTTUNA
    vanhalla tavalla (ei chip_played_gw:tä lainkaan) `wildcard_plan` EI
    tiedä chipistä mitään, eli tämä on tasan se tila josta 18.9:n tuotantovika
    syntyi. Rivi elää tässä siltä varalta että joku poistaa parametrin."""
    from src.models import fpl_wildcard
    out = fpl_wildcard.wildcard_plan([], [], [5], [], {}, lambda squad, key: [])
    # Tyhjällä poolilla optimi epäonnistuu eri syystä (ei täyttä 15:tä) -
    # tämä testi ei väitä lopputulosta, vain sitä että vanha allekirjoitus
    # (ilman chip_played_gw:tä) yhä toimii eikä TypeErroria synny.
    assert "available" in out
