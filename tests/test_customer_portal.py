# -*- coding: utf-8 -*-
"""customer-portal (6.9, STRIPE-PORTAL-LINKKI-SPA): asiakas verifioidusta
tokenista, ei pyynnon rungosta; palautusosoite allowlistista.

Vikaluokka: aiempi endpoint loi portaalisession mille tahansa sahkopostille
ilman tunnistautumista. Portaalissa voi peruuttaa tilauksen ja nahda laskut.
"""
from __future__ import annotations
import types
import pytest
from fastapi.testclient import TestClient
import api.main as m


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(m.stripe, "api_key", "sk_test_x", raising=False)
    calls = {}

    class _Customers:
        @staticmethod
        def list(email=None, limit=1):
            calls["email"] = email
            return types.SimpleNamespace(data=[types.SimpleNamespace(id="cus_1")]
                                         if email == "jack@example.com" else [])

    class _Portal:
        class Session:
            @staticmethod
            def create(customer=None, return_url=None):
                calls["customer"] = customer
                calls["return_url"] = return_url
                return types.SimpleNamespace(url="https://billing.stripe.com/session/x")

    monkeypatch.setattr(m.stripe, "Customer", _Customers, raising=False)
    monkeypatch.setattr(m.stripe, "billing_portal", _Portal, raising=False)
    return TestClient(m.app), calls


def _identity(monkeypatch, user_id, email):
    monkeypatch.setattr(m, "verify_token_identity", lambda tok: (user_id, email) if tok == "good" else (None, None))


def test_no_token_is_401_and_body_email_is_ignored(client, monkeypatch):
    c, calls = client
    _identity(monkeypatch, "u1", "jack@example.com")
    r = c.post("/api/customer-portal", json={"email": "jack@example.com"})
    assert r.status_code == 401
    assert "email" not in calls, "Stripea ei saa kysya ilman tunnistautumista"


def test_bad_token_is_401(client, monkeypatch):
    c, calls = client
    _identity(monkeypatch, "u1", "jack@example.com")
    r = c.post("/api/customer-portal", json={}, headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401
    assert "email" not in calls


def test_customer_comes_from_the_token_not_the_body(client, monkeypatch):
    c, calls = client
    _identity(monkeypatch, "u1", "jack@example.com")
    r = c.post("/api/customer-portal", json={"email": "victim@example.com"},
               headers={"Authorization": "Bearer good"})
    assert r.status_code == 200, r.text
    assert calls["email"] == "jack@example.com"
    assert calls["customer"] == "cus_1"
    assert r.json()["portal_url"].startswith("https://billing.stripe.com/")


def test_app_subscriber_without_stripe_customer_gets_404_with_store_hint(client, monkeypatch):
    c, calls = client
    _identity(monkeypatch, "u2", "appuser@example.com")
    r = c.post("/api/customer-portal", json={}, headers={"Authorization": "Bearer good"})
    assert r.status_code == 404
    assert "App Store" in r.json()["detail"]


@pytest.mark.parametrize("requested,expected", [
    (None, "https://pro.goaliq.app/"),
    ("https://pro.goaliq.app/team", "https://pro.goaliq.app/team"),
    ("https://pro.goaliq.app?tab=account", "https://pro.goaliq.app?tab=account"),
    ("goaliq://subscription-managed", "goaliq://subscription-managed"),
    ("https://evil.example.com/", "https://pro.goaliq.app/"),
    ("https://pro.goaliq.app.evil.com/", "https://pro.goaliq.app/"),
    ("javascript:alert(1)", "https://pro.goaliq.app/"),
])
def test_return_url_allowlist(requested, expected):
    assert m._portal_return_url(requested) == expected


def test_return_url_reaches_stripe(client, monkeypatch):
    c, calls = client
    _identity(monkeypatch, "u1", "jack@example.com")
    r = c.post("/api/customer-portal", json={"return_url": "https://evil.example.com/"},
               headers={"Authorization": "Bearer good"})
    assert r.status_code == 200
    assert calls["return_url"] == "https://pro.goaliq.app/"
