# -*- coding: utf-8 -*-
"""Portti: UK-kavija ei voi avata Stripe Checkoutia, muut voivat.

UK (ml. Mansaari): verkko-osto suljettu, Premium myydaan sovelluskauppojen
kautta (paatos 23.9.2026).

Vartioitavat invariantit:
  1. GB ja IM -> 403 `region_app_store_only` kaikilla kolmella
     checkout-reitilla, eika Stripe-sessiota synny.
  2. FI, US, JE, GG ja PUUTTUVA maa -> checkout toimii kuten ennen (fail-open:
     otsakkeen puuttuminen ei saa pysayttaa koko verkkomyyntia).
  3. Maa tulee vain CF-IPCountry-otsakkeesta: ei rungosta eika
     admin-esikatselusta.
  4. Rakenne: jokainen `stripe.checkout.Session.create`-kutsuja kutsuu estoa
     ENNEN sessiota, eika esto vuoda asiakasportaaliin tai webhookeihin
     (olemassa olevien UK-tilausten hallinta ei saa katketa).
"""
from __future__ import annotations

import ast
import copy
import types
from pathlib import Path

import pytest
import stripe
from fastapi.testclient import TestClient

import api.main as m
from src.regional_pricing import (
    COUNTRY_HEADER, REGION_STORE_ONLY_ERROR, WEB_CHECKOUT_STORE_ONLY,
    request_country, web_checkout_allowed,
)

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "admin-testi-token"
ORIGIN = "https://pro.goaliq.app"


@pytest.fixture
def client():
    return TestClient(m.app)


@pytest.fixture
def stripe_mock(monkeypatch):
    """Konfiguroi hinnat ja korvaa Session.create laskurilla."""
    monkeypatch.setattr(stripe, "api_key", "sk_test_x")
    monkeypatch.setattr(m, "STRIPE_PRICE_MONTHLY_ID", "price_monthly_test")
    monkeypatch.setattr(m, "STRIPE_PRICE_SEASON_ID", "price_season_test")
    monkeypatch.setattr(m, "STRIPE_PRICE_ID", "price_mobile_test")
    monkeypatch.delenv("STRIPE_REGIONAL_PRICES", raising=False)
    monkeypatch.setattr(m, "_GUEST_CHECKOUT_HITS", {})
    monkeypatch.setattr(
        m, "_get_supabase_user",
        lambda token: {"id": "user-123", "email": "test@example.com"}
        if token == "valid" else None)
    kutsut: list[dict] = []

    def luo(**kw):
        kutsut.append(kw)
        return types.SimpleNamespace(url="https://checkout.stripe.com/c/pay/test",
                                     id="cs_test_1")

    monkeypatch.setattr(stripe.checkout.Session, "create", staticmethod(luo))
    return kutsut


def _guest(client, headers=None, body=None, query=""):
    return client.post(f"/api/web/checkout/guest{query}",
                       json=body or {"plan": "season", "origin": ORIGIN},
                       headers=headers or {})


def _authed(client, headers=None):
    return client.post("/api/web/checkout",
                       json={"plan": "monthly", "origin": ORIGIN},
                       headers={"Authorization": "Bearer valid", **(headers or {})})


def _mobile(client, headers=None):
    return client.post("/api/checkout",
                       json={"user_id": "user-123", "email": "test@example.com"},
                       headers=headers or {})


REITIT = {"guest": _guest, "authed": _authed, "mobile": _mobile}


# --- 1. lukija ---------------------------------------------------------------

def test_lista_on_tasan_gb_ja_im():
    """Listan muutos on paatos, ei sivuvaikutus: testi kaatuu ja diff nayttaa sen.
    Mansaari (IM) on listalla, Kanaalisaaret (JE, GG) eivat."""
    assert WEB_CHECKOUT_STORE_ONLY == frozenset({"GB", "IM"})


@pytest.mark.parametrize("otsake, sallittu", [
    ("GB", False), ("gb", False), (" GB ", False),
    ("IM", False), ("im", False), ("JE", True), ("GG", True),
    ("FI", True), ("US", True), ("IE", True), ("NG", True),
    ("", True), ("XX", True), ("T1", True), ("GBR", True),
])
def test_lukija_cf_otsakkeesta(otsake, sallittu):
    assert web_checkout_allowed(request_country({COUNTRY_HEADER: otsake})) is sallittu


def test_puuttuva_otsake_sallii():
    assert web_checkout_allowed(request_country({})) is True


# --- 2. GB ja IM estetty kaikilla reiteilla, Stripea ei kutsuta -------------

@pytest.mark.parametrize("reitti", list(REITIT))
@pytest.mark.parametrize("maa", ["GB", "IM"])
def test_estetty_maa_saa_403_ja_virhekoodin(client, stripe_mock, reitti, maa):
    r = REITIT[reitti](client, headers={"CF-IPCountry": maa})
    assert r.status_code == 403, r.text
    d = r.json()
    assert d["error"] == REGION_STORE_ONLY_ERROR == "region_app_store_only"
    assert d["country"] == maa
    # Vanha SPA-versio nayttaa `detail`in sellaisenaan: sen on oltava ohje, ei koodi.
    assert "App Store" in d["detail"] and "Google Play" in d["detail"]
    assert r.headers["cache-control"] == "no-store"
    assert stripe_mock == [], f"Stripe-sessio luotiin kavijalle maasta {maa}"


@pytest.mark.parametrize("reitti", list(REITIT))
@pytest.mark.parametrize("maa", ["FI", "US", "JE", "GG", None],
                         ids=["FI", "US", "JE", "GG", "ei-otsaketta"])
def test_muut_maat_ja_puuttuva_maa_sallitaan(client, stripe_mock, reitti, maa):
    otsakkeet = {"CF-IPCountry": maa} if maa else {}
    r = REITIT[reitti](client, headers=otsakkeet)
    assert r.status_code == 200, r.text
    assert len(stripe_mock) == 1


def test_gb_ei_kuluta_guest_kiintiota(client, stripe_mock, monkeypatch):
    """Esto ennen rate limitia: GB-yritykset eivat tayta IP:n kiintiota."""
    monkeypatch.setattr(m, "_GUEST_CHECKOUT_LIMIT", 1)
    otsakkeet = {"CF-IPCountry": "GB", "CF-Connecting-IP": "203.0.113.7"}
    for _ in range(3):
        assert _guest(client, headers=otsakkeet).status_code == 403
    assert m._GUEST_CHECKOUT_HITS.get("203.0.113.7") is None


def test_authed_gb_estetaan_ennen_supabasea(client, stripe_mock, monkeypatch):
    kysytty = []
    monkeypatch.setattr(m, "_get_supabase_user", lambda t: kysytty.append(t) or None)
    r = _authed(client, headers={"CF-IPCountry": "GB"})
    assert r.status_code == 403
    assert kysytty == []


# --- 3. maata ei voi valita clientilta ---------------------------------------

def test_runko_ei_ohita_estoa(client, stripe_mock):
    r = _guest(client, headers={"CF-IPCountry": "GB"},
               body={"plan": "season", "origin": ORIGIN, "country": "FI"})
    assert r.status_code == 403
    r = _guest(client, headers={"CF-IPCountry": "FI"},
               body={"plan": "season", "origin": ORIGIN, "country": "GB"})
    assert r.status_code == 200


def test_admin_esikatselu_ei_vaikuta_checkoutiin(client, stripe_mock, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    admin = {"X-Admin-Token": TOKEN}
    r = _guest(client, headers={**admin, "CF-IPCountry": "GB"}, query="?as_country=FI")
    assert r.status_code == 403
    r = _guest(client, headers={**admin, "CF-IPCountry": "FI"}, query="?as_country=GB")
    assert r.status_code == 200


# --- 4. hintapinta kertoo SPA:lle saman asian --------------------------------

def _pricing_ilman_stripea(monkeypatch):
    monkeypatch.setattr(m, "_stripe_price_amount", lambda pid: None)


@pytest.mark.parametrize("maa, odotus", [("GB", False), ("IM", False), ("FI", True),
                                          ("US", True), ("JE", True), (None, True)])
def test_pricing_kertoo_web_checkoutin(client, monkeypatch, maa, odotus):
    _pricing_ilman_stripea(monkeypatch)
    r = client.get("/api/web/pricing", headers={"CF-IPCountry": maa} if maa else {})
    assert r.status_code == 200
    assert r.json()["web_checkout"] is odotus


def test_pricing_admin_esikatselu_gb(client, monkeypatch):
    """Tuotantotodennus Suomesta: `?as_country=GB` + admin-token nayttaa
    UI-signaalin. Checkoutin estoa se EI todenna (ks. edellinen osio)."""
    _pricing_ilman_stripea(monkeypatch)
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    d = client.get("/api/web/pricing?as_country=GB",
                   headers={"X-Admin-Token": TOKEN, "CF-IPCountry": "FI"}).json()
    assert d["preview"] is True and d["country"] == "GB"
    assert d["web_checkout"] is False


# --- 5. olemassa olevat tilaukset: portaali ei esty ---------------------------

def test_asiakasportaali_toimii_gb_kavijalle(client, monkeypatch):
    """Olemassa olevan UK-tilauksen hallinta (peruutus, kortti, laskut) ei saa
    katketa: esto koskee vain uuden checkoutin luontia."""
    monkeypatch.setattr(m.stripe, "api_key", "sk_test_x", raising=False)
    monkeypatch.setattr(m, "verify_token_identity",
                        lambda tok: ("u1", "sub@example.com") if tok == "good" else (None, None))

    class _Customers:
        @staticmethod
        def list(email=None, limit=1):
            return types.SimpleNamespace(data=[types.SimpleNamespace(id="cus_1")])

    class _Portal:
        class Session:
            @staticmethod
            def create(customer=None, return_url=None):
                return types.SimpleNamespace(url="https://billing.stripe.com/session/x")

    monkeypatch.setattr(m.stripe, "Customer", _Customers, raising=False)
    monkeypatch.setattr(m.stripe, "billing_portal", _Portal, raising=False)
    r = client.post("/api/customer-portal", json={},
                    headers={"Authorization": "Bearer good", "CF-IPCountry": "GB"})
    assert r.status_code == 200, r.text
    assert r.json()["portal_url"].startswith("https://billing.stripe.com/")


# --- 6. rakenne: uusi checkout-polku ei voi ohittaa estoa --------------------

def _funktiot() -> list[ast.FunctionDef]:
    tree = ast.parse((ROOT / "api" / "main.py").read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _koodi(fn: ast.FunctionDef) -> str:
    """Funktion koodi ilman docstringia (kommentit ast.unparse pudottaa itse).
    Docstring joka mainitsee Session.createn ei ole kutsu."""
    runko = fn.body
    if (runko and isinstance(runko[0], ast.Expr)
            and isinstance(runko[0].value, ast.Constant)
            and isinstance(runko[0].value.value, str)):
        kopio = copy.copy(fn)
        kopio.body = runko[1:] or [ast.Pass()]
        return ast.unparse(kopio)
    return ast.unparse(fn)


def test_jokainen_checkout_kutsuu_estoa_ennen_sessiota():
    """6a kohta (1)+(2): ilman tata kolmas checkout-polku voisi myyda UK:hon
    aanettomasti, eika mikaan pinta kertoisi siita."""
    loydetyt = []
    for fn in _funktiot():
        koodi = _koodi(fn)
        if "stripe.checkout.Session.create" not in koodi:
            continue
        loydetyt.append(fn.name)
        esto = koodi.find("_checkout_region_block(request")
        sessio = koodi.find("stripe.checkout.Session.create")
        assert esto != -1, f"{fn.name} luo Stripe-session ilman UK-estoa"
        assert esto < sessio, f"{fn.name}: esto vasta session jalkeen"
        assert "return esto" in koodi, f"{fn.name} kutsuu estoa mutta ei palauta sita"
    assert len(loydetyt) >= 3, f"checkout-funktioita {loydetyt}: portti mittaa vaaraa asiaa"


def test_esto_ei_vuoda_portaaliin_eika_webhookeihin():
    """Esto kuuluu vain checkoutiin. Portaalissa tai webhookissa se katkaisisi
    olemassa olevan UK-tilauksen hallinnan tai uusimisen kirjauksen."""
    kayttajat = {fn.name for fn in _funktiot()
                 if fn.name != "_checkout_region_block"
                 and "_checkout_region_block(" in _koodi(fn)}
    checkoutit = {fn.name for fn in _funktiot()
                  if "stripe.checkout.Session.create" in _koodi(fn)}
    assert kayttajat == checkoutit
    assert "create_portal_session" not in kayttajat
