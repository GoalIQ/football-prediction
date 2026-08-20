"""FPL-THIN-BLEND (20.8): ohuen otoksen nousijablendin PL-kytkenta.

Mittaus joka oikeutti kytkennan: scripts/backtest_thin_blend.py — 197
parittaista ennustetta, log loss -0,0438 (t -3,36), voitto jokaisessa
viidessa liigassa erikseen. Nama testit vartioivat kytkennan MEKANIIKKAA:
oikea kausi, oikea kohortti, ja ennen kaikkea esikausi-no-op (kaytos ennen
GW1-tuloksia on bittitarkasti entinen).
"""
from __future__ import annotations

import math

import pandas as pd

from src.models.dixon_coles import DixonColesModel
from src.models.promoted_baseline import (
    COHORT_DOWN,
    COHORT_UP,
    FROZEN_BASELINE,
    PROMOTED_BY_SEASON,
    REFERENCE_BY_LEAGUE,
    blendaa_ohuet_nousijat,
    kauden_ottelumaarat,
)


def test_kauden_ottelumaarat_laskee_koti_ja_vieras():
    df = pd.DataFrame({
        "season": ["2627", "2627", "2526"],
        "home_team": ["Hull", "Coventry", "Hull"],
        "away_team": ["Coventry", "Arsenal", "Arsenal"],
    })
    counts = kauden_ottelumaarat(df, "2627")
    # 2526-rivi EI saa nakya: vain aktiivinen kausi lasketaan.
    assert counts == {"Hull": 1, "Coventry": 2, "Arsenal": 1}


def test_kauden_ottelumaarat_kestaa_int_kauden():
    df = pd.DataFrame({
        "season": [2627], "home_team": ["Hull"], "away_team": ["Coventry"],
    })
    assert kauden_ottelumaarat(df, "2627") == {"Hull": 1, "Coventry": 1}


def _pl_dc(**extra) -> DixonColesModel:
    """PL-stubi: viitetrio (Ipswich/Leicester/Southampton) EI ole fitissa —
    ikkuna 2526+2627 ei sisalla sita — joten baseline on FROZEN, sama
    varakeino jota taydenna_nousijat kayttaa."""
    dc = DixonColesModel(per_team_home_adv=True)
    dc.attack = {"Arsenal": 0.5, "Hull": 0.1, **extra.get("attack", {})}
    dc.defence = {"Arsenal": -0.4, "Hull": 0.2, **extra.get("defence", {})}
    dc.home_advantage_per_team = {"Arsenal": 0.2, "Hull": 0.1}
    return dc


def test_pl_ohut_nousija_blendataan_frozen_baselineen():
    dc = _pl_dc()
    info = blendaa_ohuet_nousijat(
        dc, ["ENG-Premier League"], ["2526", "2627"], {"Hull": 1})
    assert "Hull" in info["blended"]
    assert info["source"] == "frozen"
    # w = 1/6: parametri on baseline + w * (fit - baseline).
    odotus = FROZEN_BASELINE["attack"] + (1 / 6) * (0.1 - FROZEN_BASELINE["attack"])
    assert math.isclose(dc.attack["Hull"], odotus, abs_tol=1e-9)
    # Vakiintunut joukkue ei liiku (negatiivinen kontrolli).
    assert dc.attack["Arsenal"] == 0.5


def test_esikausi_on_noop_bittitarkasti():
    """0 kauden ottelua -> ei kosketa mihinkaan. Tama on regressiotae:
    ennen GW1-tuloksia kaikki kolme fittia kayttaytyvat tasan kuten ennen."""
    dc = _pl_dc()
    ennen = (dict(dc.attack), dict(dc.defence), dict(dc.home_advantage_per_team))
    info = blendaa_ohuet_nousijat(
        dc, ["ENG-Premier League"], ["2526", "2627"], {})
    assert info["blended"] == {}
    assert (dc.attack, dc.defence, dc.home_advantage_per_team) == ennen


def test_taysi_otos_on_noop():
    dc = _pl_dc()
    info = blendaa_ohuet_nousijat(
        dc, ["ENG-Premier League"], ["2526", "2627"], {"Hull": 6})
    assert info["blended"] == {}
    assert dc.attack["Hull"] == 0.1


def test_championship_kohortit_saavat_eri_baselinen():
    """Wolves (PL:sta pudonnut) blendataan pudonneiden viiteryhmaan,
    Bolton (League Onesta noussut) nousseiden — yksi baseline kaikille
    kuudelle tekisi West Hamista yhta heikon kuin Lincolnista."""
    ryhmat = PROMOTED_BY_SEASON["2627"]["ENG-Championship"]
    viitteet = REFERENCE_BY_LEAGUE["ENG-Championship"]
    assert "Wolves" in ryhmat[COHORT_DOWN] and "Bolton" in ryhmat[COHORT_UP]

    dc = DixonColesModel(per_team_home_adv=True)
    # Viiteryhmat fitissa eri tasoilla: pudonneet vahvoja, nousseet heikkoja.
    dc.attack = {t: 0.3 for t in viitteet[COHORT_DOWN]}
    dc.attack.update({t: -0.5 for t in viitteet[COHORT_UP]})
    dc.attack.update({"Wolves": 0.0, "Bolton": 0.0})
    dc.defence = {t: 0.0 for t in dc.attack}
    dc.home_advantage_per_team = {t: 0.0 for t in dc.attack}

    info = blendaa_ohuet_nousijat(
        dc, ["ENG-Championship"], ["2526", "2627"],
        {"Wolves": 1, "Bolton": 1})
    assert set(info["blended"]) == {"Wolves", "Bolton"}
    # Sama fitattu 0.0, sama n -> ero tulee VAIN kohortin baselinesta.
    # Wolves kohti +0.3, Bolton kohti -0.5.
    assert dc.attack["Wolves"] > 0.2
    assert dc.attack["Bolton"] < -0.35


def test_ohut_ilman_viiteryhmaa_nakyy_skipattuna():
    """Ei-PL-liiga ilman fitissa olevaa viiteryhmaa: ohut nousija EI saa
    frozenia (PL-skaalaa) — se skipataan NAKYVASTI, ei hiljaa."""
    dc = DixonColesModel(per_team_home_adv=True)
    dc.attack = {"AC Monza": 0.1}
    dc.defence = {"AC Monza": 0.0}
    dc.home_advantage_per_team = {}
    info = blendaa_ohuet_nousijat(
        dc, ["ITA-Serie A-FD"], ["2526", "2627"], {"AC Monza": 2})
    assert info["blended"] == {}
    assert info.get("skipped_thin") == ["AC Monza"]
    assert dc.attack["AC Monza"] == 0.1
