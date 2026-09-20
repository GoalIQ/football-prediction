# -*- coding: utf-8 -*-
"""Portti: aluehinta ei voi tulla clientilta eika vahingossa vaarasta maasta.

MITATTU 20.9.2026: 53/56 `purchase_error`ista on kayttajan oma peruutus
maksuruudussa, ja yli puolet maksumuurin nahneista on markkinoilla joissa
25 EUR/v on iso raha. Aluehinta on siis oikea liike - mutta se avaa kaksi
uutta tapaa havita rahaa, ja molemmat vartioidaan tassa:

  (1) kuka tahansa ilmoittaa maakseen halvimman markkinan -> hinta on
      clientin valittavissa,
  (2) konfiguraatiovirhe antaa halvan hinnan vaaralle maalle -> kukaan ei
      huomaa, koska liian halpa hinta ei nay valituksina.

Molemmat suljetaan samalla saannolla: maa luetaan CF-otsakkeesta ja
tuntematon maa saa TAYDEN hinnan.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.regional_pricing import request_country, resolve_price

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = "price_default_season"
KARTTA = '{"season": {"NG": "price_ng", "KE": "price_ke"}, "monthly": {"NG": "price_ng_m"}}'


# --- 1. fail-closed: tuntematon maa saa taysin hinnan ----------------------

@pytest.mark.parametrize("maa", ["", "XX", "T1", "FI", "GB", "US", "ZZ", "N", "NGA"])
def test_tuntematon_tai_listaamaton_maa_saa_taysin_hinnan(monkeypatch, maa):
    monkeypatch.setenv("STRIPE_REGIONAL_PRICES", KARTTA)
    hinta, tier = resolve_price("season", request_country({"cf-ipcountry": maa}), DEFAULT)
    assert hinta == DEFAULT, f"{maa!r} sai alehinnan {hinta}"
    assert tier == "default"


def test_listattu_maa_saa_aluehinnan(monkeypatch):
    monkeypatch.setenv("STRIPE_REGIONAL_PRICES", KARTTA)
    # "ng " mukana tahallaan: valilyonti otsakkeessa on muotoseikka, ei
    # tuntematon maa. Jos se putoaisi oletushintaan, nigerialainen maksaisi
    # taysin hinnan otsakkeen siivousvirheen takia emmekä nakisi sita mistaan.
    for otsake in ("NG", "ng", "Ng", "ng "):
        hinta, tier = resolve_price("season", request_country({"cf-ipcountry": otsake}), DEFAULT)
        assert (hinta, tier) == ("price_ng", "NG"), otsake


def test_plan_ei_vuoda_toiselle(monkeypatch):
    """`monthly`-kartassa ei ole KE:ta -> KE maksaa kuukaudesta taysin."""
    monkeypatch.setenv("STRIPE_REGIONAL_PRICES", KARTTA)
    hinta, tier = resolve_price("monthly", request_country({"cf-ipcountry": "KE"}), DEFAULT)
    assert (hinta, tier) == (DEFAULT, "default")


@pytest.mark.parametrize("konffi", ["", "   ", "ei-jsonia", "[]", "null", '{"season": "price_x"}'])
def test_rikkinainen_konfiguraatio_putoaa_oletushintaan(monkeypatch, konffi):
    """Rikkinainen kartta ei saa kaataa ostoa eika arvata hintaa."""
    monkeypatch.setenv("STRIPE_REGIONAL_PRICES", konffi)
    hinta, tier = resolve_price("season", "NG", DEFAULT)
    assert (hinta, tier) == (DEFAULT, "default"), konffi


def test_ilman_konfiguraatiota_kaytos_on_sama_kuin_ennen(monkeypatch):
    monkeypatch.delenv("STRIPE_REGIONAL_PRICES", raising=False)
    assert resolve_price("season", "NG", DEFAULT) == (DEFAULT, "default")


@pytest.mark.parametrize("vaara", [
    "prod_ABC123",          # tuote, ei hinta: yleisin kasin liittamisen virhe
    "GoalIQ Premium",       # nimi
    "1TptqDFLROrR5x8w",     # tunniste ilman prefiksia
    "  ",                   # tyhja
])
def test_vaaran_muotoinen_tunniste_putoaa_oletushintaan(monkeypatch, vaara):
    """Vaara tunniste ei saa KAATAA ostosta vaan pudota listahintaan.

    Ilman tata typo Renderin muuttujassa rikkoisi ostamisen tasan niilla
    markkinoilla joita varten aluehinta rakennettiin, ja se nakyisi vain
    checkout_failed-tapahtumina - ei kenellekaan ennen kuin joku katsoo.
    """
    import json as _json
    monkeypatch.setenv("STRIPE_REGIONAL_PRICES",
                       _json.dumps({"season": {"NG": vaara}}))
    assert resolve_price("season", "NG", DEFAULT) == (DEFAULT, "default")


# --- 2. maa EI saa tulla clientilta ---------------------------------------

def test_maa_luetaan_vain_cf_otsakkeesta():
    """Jos maa tulisi clientin kentasta, hinta olisi ostajan valittavissa."""
    assert request_country({"x-country": "NG", "accept-language": "en-NG"}) == ""
    assert request_country({"cf-ipcountry": "NG"}) == "NG"


def test_endpointit_eivat_lue_maata_pyynnon_rungosta():
    lahde = (ROOT / "api" / "main.py").read_text(encoding="utf-8")
    for kielletty in ("req.country", "req.region", "req.locale", "req.market"):
        assert kielletty not in lahde, (
            f"{kielletty}: maa tulee pyynnon rungosta -> ostaja valitsee hintansa")


# --- 3. kutsupaikka: hinta ei saa palata kovakoodatuksi --------------------

def _checkout_funktiot() -> list[ast.FunctionDef]:
    tree = ast.parse((ROOT / "api" / "main.py").read_text(encoding="utf-8"))
    out = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            koodi = ast.unparse(n)
            if "stripe.checkout.Session.create" in koodi and "line_items" in koodi:
                out.append(n)
    return out


def test_jokainen_checkout_kutsuu_aluehintalukijaa():
    """Muisti `testi-kutsuu-funktiota-ei-kutsupaikkaa`: ilman tata voi lisata
    kolmannen checkout-polun joka ohittaa aluehinnan aanettomasti."""
    fns = _checkout_funktiot()
    assert len(fns) >= 2, f"checkout-funktioita loytyi {len(fns)} - portti mittaa vaaraa asiaa"
    for fn in fns:
        koodi = ast.unparse(fn)
        if "STRIPE_PRICE_SEASON_ID" not in koodi:
            continue            # muu checkout-polku (esim. vanha Streamlit)
        assert "resolve_price(" in koodi, (
            f"{fn.name} rakentaa Stripe-session ilman resolve_price():ta")
        assert "price_tier" in koodi, (
            f"{fn.name} ei kirjaa price_tieria metadataan -> toteutunutta "
            "tuottoa ei voi jakaa hintatasoittain")


# --- 4. skripti ja lukija ovat samaa mielta muodosta ----------------------

def test_setter_skriptin_tuottama_json_kelpaa_lukijalle(monkeypatch):
    """`set_regional_prices.py` kirjoittaa muuttujan, `resolve_price` lukee sen.

    Jos ne olisivat eri mielta muodosta, muuttuja nayttaisi oikealta Renderin
    kayttoliittymassa ja jokainen maksaisi silti listahinnan - eika mikaan
    kertoisi siita. Tama on kaytannossa koko luovutuspolun ainoa liitos.
    """
    import json
    import importlib.util
    polku = ROOT / "scripts" / "set_regional_prices.py"
    spec = importlib.util.spec_from_file_location("srp", polku)
    srp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(srp)

    monkeypatch.setenv("STRIPE_REGIONAL_PRICES",
                       json.dumps(srp.kartta(season="price_abc123", monthly="price_m1"),
                                  separators=(",", ":")))
    for maa in srp.MARKKINAT:
        assert resolve_price("season", maa, DEFAULT) == ("price_abc123", maa), maa
    # Listaamaton maa maksaa yha listahinnan.
    assert resolve_price("season", "GB", DEFAULT) == (DEFAULT, "default")
    # Molemmat planit samassa kutsussa: muuttuja kirjoitetaan yli, joten
    # yhden planin kerrallaan asettaminen pyyhkisi toisen hiljaa.
    for maa in srp.MARKKINAT:
        assert resolve_price("monthly", maa, DEFAULT) == ("price_m1", maa), maa
    # Vain season annettuna kuukausi jaa listahintaan.
    import json as _j
    monkeypatch.setenv("STRIPE_REGIONAL_PRICES",
                       _j.dumps(srp.kartta(season="price_abc123")))
    assert resolve_price("monthly", "NG", DEFAULT) == (DEFAULT, "default")


def test_setter_hylkaa_vaaran_tunnisteen():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "srp", ROOT / "scripts" / "set_regional_prices.py")
    srp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(srp)
    for vaara in ("prod_ABC", "GoalIQ Premium", "", "1Tptq"):
        with pytest.raises(SystemExit):
            srp.kartta(season=vaara)
