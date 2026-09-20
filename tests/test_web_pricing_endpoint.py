# -*- coding: utf-8 -*-
"""Portti: sivun nayttama hinta on sama jonka asiakas maksaa.

MITATTU 20.9.2026: SPA:n lappu oli kovakoodattu 25 EUR, ja aluehinnan
kytkemisen jalkeen nigerialainen olisi nahnyt maksumuurilla 25 ja
Checkoutissa 9. Paatos tehdaan maksumuurilla (web: 383 pro_page_viewed ->
20 upgrade_tapped), joten vaara luku juuri siina kohdassa mitatoi koko
aluehinnan.

Endpoint hakee summan STRIPESTA. Tama testi vartioi sita, ettei se ala
hakea sita mistaan muualta - konfiguraatiosta luettu luku voisi ajautua eri
arvoon kuin veloitettava, ja se nakyisi vasta asiakkaan kuitissa.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import api.main as m


@pytest.fixture
def client():
    return TestClient(m.app)


def _konfiguroi(monkeypatch, *, regional=True):
    monkeypatch.setattr(m, "STRIPE_PRICE_SEASON_ID", "price_season_list")
    monkeypatch.setattr(m, "STRIPE_PRICE_MONTHLY_ID", "price_monthly_list")
    monkeypatch.setattr(m.stripe, "api_key", "sk_test_x", raising=False)
    monkeypatch.setattr(m, "_HINTA_CACHE", {})
    if regional:
        monkeypatch.setenv("STRIPE_REGIONAL_PRICES", json.dumps(
            {"season": {"NG": "price_season_ng"},
             "monthly": {"NG": "price_monthly_ng"}}))
    else:
        monkeypatch.delenv("STRIPE_REGIONAL_PRICES", raising=False)
    hinnat = {
        "price_season_list": {"unit_amount": 2500, "currency": "eur"},
        "price_monthly_list": {"unit_amount": 399, "currency": "eur"},
        "price_season_ng": {"unit_amount": 900, "currency": "eur"},
        "price_monthly_ng": {"unit_amount": 149, "currency": "eur"},
    }
    monkeypatch.setattr(m.stripe.Price, "retrieve",
                        staticmethod(lambda pid, **kw: hinnat[pid]))


def test_listahinta_ilman_maata(client, monkeypatch):
    _konfiguroi(monkeypatch)
    d = client.get("/api/web/pricing").json()
    assert d["country"] is None
    assert d["plans"]["season"] == {"amount": 25.0, "currency": "EUR", "tier": "default"}
    assert d["plans"]["monthly"]["amount"] == 3.99


def test_aluehinta_cf_otsakkeesta(client, monkeypatch):
    _konfiguroi(monkeypatch)
    d = client.get("/api/web/pricing", headers={"CF-IPCountry": "NG"}).json()
    assert d["country"] == "NG"
    assert d["plans"]["season"] == {"amount": 9.0, "currency": "EUR", "tier": "NG"}
    # Kuukausi on myos alueellinen. Ville huomasi 20.9 etta pelkka
    # vuosihinnan alentaminen teki kuukaudesta 5,3 x vuosihinnan - se ei ole
    # hinnoittelua vaan ansa.
    assert d["plans"]["monthly"] == {"amount": 1.49, "currency": "EUR", "tier": "NG"}


def test_kuukausi_ei_saa_olla_vuotta_kalliimpi_samassa_maassa(client, monkeypatch):
    """Jos vuosihinta on alueellinen mutta kuukausi ei, kuukausitilaus maksaa
    moninkertaisesti vuositilaukseen nahden. Se ei ole hinnoittelua vaan
    ansa, ja se on helpompi huomata testissa kuin asiakkaan silmin."""
    _konfiguroi(monkeypatch)
    d = client.get("/api/web/pricing", headers={"CF-IPCountry": "NG"}).json()
    vuosi = d["plans"]["season"]["amount"]
    kk_vuodessa = d["plans"]["monthly"]["amount"] * 12
    suhde = kk_vuodessa / vuosi
    assert suhde > 1, "odottamaton: kuukausi halvempi kuin vuosi"
    # Listahinnan suhde on 47,88 / 25 = 1,92. Aluehinnan on oltava samaa
    # luokkaa: jos se karkaa yli kahden, kuukausitilaus on taas ansa.
    # 20.9 kiristetty 3:sta 2,5:een kun alueellinen kuukausihinta luotiin
    # (1,49/kk -> 17,88/v vs 9/v = 1,99).
    assert suhde < 2.5, (
        f"kuukausi on {suhde:.1f} x vuosihinta aluemaassa. Listahinnassa "
        "suhde on 1,9. Luo alueellinen kuukausihinta tai laske se.")


def test_stripe_virhe_ei_kaada_vaan_jattaa_planin_pois(client, monkeypatch):
    """SPA putoaa omaan oletukseensa. Tyhja hinta olisi pahempi kuin vanha."""
    _konfiguroi(monkeypatch)

    def kaatuu(pid, **kw):
        raise RuntimeError("stripe down")

    monkeypatch.setattr(m.stripe.Price, "retrieve", staticmethod(kaatuu))
    d = client.get("/api/web/pricing").json()
    assert d["plans"] == {}


def test_summa_tulee_stripesta_ei_konfiguraatiosta():
    """Kutsupaikkaportti: jos endpoint alkaa lukea summan muualta, se voi
    ajautua eri arvoon kuin veloitettava."""
    import ast
    from pathlib import Path
    lahde = Path(m.__file__).read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(lahde).body
              if isinstance(n, ast.FunctionDef) and n.name == "web_pricing")
    koodi = ast.unparse(fn)
    assert "_stripe_price_amount" in koodi
    assert "resolve_price" in koodi
