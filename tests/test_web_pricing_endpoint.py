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
        monkeypatch.setenv("STRIPE_REGIONAL_PRICES",
                           json.dumps({"season": {"NG": "price_season_ng"}}))
    else:
        monkeypatch.delenv("STRIPE_REGIONAL_PRICES", raising=False)
    hinnat = {
        "price_season_list": {"unit_amount": 2500, "currency": "eur"},
        "price_monthly_list": {"unit_amount": 399, "currency": "eur"},
        "price_season_ng": {"unit_amount": 900, "currency": "eur"},
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
    # Kuukausi ei ole kartassa -> listahinta. Tama on se epasuhta jonka
    # Ville huomasi: 3,99/kk = 47,88/v eli 5,3 x vuosihinta. Portti tekee
    # siita NAKYVAN eika hyvaksy sita hiljaa.
    assert d["plans"]["monthly"]["tier"] == "default"


def test_kuukausi_ei_saa_olla_vuotta_kalliimpi_samassa_maassa(client, monkeypatch):
    """Jos vuosihinta on alueellinen mutta kuukausi ei, kuukausitilaus maksaa
    moninkertaisesti vuositilaukseen nahden. Se ei ole hinnoittelua vaan
    ansa, ja se on helpompi huomata testissa kuin asiakkaan silmin."""
    _konfiguroi(monkeypatch)
    d = client.get("/api/web/pricing", headers={"CF-IPCountry": "NG"}).json()
    vuosi = d["plans"]["season"]["amount"]
    kk_vuodessa = d["plans"]["monthly"]["amount"] * 12
    assert kk_vuodessa > vuosi, "odottamaton: kuukausi halvempi kuin vuosi"
    # Dokumentoitu tila 20.9: epasuhta on TIEDOSSA ja odottaa alueellista
    # kuukausihintaa. Kun se lisataan, tama raja kiristetaan.
    assert kk_vuodessa / vuosi > 3, (
        "epasuhta on korjaantunut -> kirista tama testi vastaamaan uutta "
        "tilaa, ala poista sita")


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
