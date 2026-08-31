"""Tavoitefunktio 1: ilmais->Premium-konversio aggregaattina (31.8.2026).

Autopilotin DIGEST on sanonut 29.8 lahtien "ilmais->Premium-konversio:
mitataan sessiossa", eli ENSISIJAISTA tavoitefunktiota ei ollut mitattu
kertaakaan automaattisesti. Itsekehittyva silmukka ei voi optimoida
mittaria jota se ei nae.

🔴 KOLME ASIAA JOTKA MENISIVAT HILJAA PIELEEN:

1. **Epaonnistunut haku nollana.** Sama vikaluokka kuin luojaraportissa ja
   ilmaisikkunaraportissa. Tyhja lista nayttaisi konversiolta 0 %.
2. **Ilmaisikkuna vaaristaa luvun.** Kun Premium on ilmainen webissa,
   kukaan ei osta sita webista. DIGEST nayttaisi putoavan kayran ja
   ajaisi jahtaamaan haamua.
3. **Henkilotiedot CI:hin.** Vastaus saa sisaltaa vain summia: ei
   sahkoposteja, ei id:ta, ei rivikohtaisia tilauksia.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

import api.main as m

REITTI = "/api/admin/conversion"


class _Resp:
    def __init__(self, payload, status=200):
        self._p, self.status_code, self.text = payload, status, str(payload)

    def json(self):
        return self._p


def _wire(monkeypatch, users, web=(), app_prem=(), users_status=200,
          sub_status=200, window=False):
    monkeypatch.setattr(m, "SUPABASE_URL", "https://supa.test")
    monkeypatch.setattr(m, "SUPABASE_SERVICE_ROLE_KEY", "key")
    monkeypatch.setenv("ADMIN_TOKEN", "adm")
    monkeypatch.setattr(m, "free_premium_window_active", lambda: window)

    def fake_get(url, params=None, headers=None, timeout=None):
        if "admin/users" in url:
            if users_status != 200:
                return _Resp({"msg": "nope"}, users_status)
            page = (params or {}).get("page", 1)
            return _Resp({"users": users if page == 1 else []})
        if sub_status != 200:
            return _Resp({"msg": "nope"}, sub_status)
        if "web_subscriptions" in url:
            return _Resp([{"user_id": u, "status": "active"} for u in web])
        if "profiles" in url:
            return _Resp([{"id": u} for u in set(web) | set(app_prem)])
        return _Resp([])

    monkeypatch.setattr(m.requests, "get", fake_get)
    return TestClient(m.app)


def _get(c):
    return c.get(REITTI, headers={"X-Admin-Token": "adm"})


def _users(n):
    return [{"id": f"u{i}", "created_at": "2026-08-01T00:00:00Z"} for i in range(n)]


# --- portti ---------------------------------------------------------------

def test_ilman_tokenia_403(monkeypatch):
    assert _wire(monkeypatch, _users(3)).get(REITTI).status_code == 403


def test_vaaralla_tokenilla_403(monkeypatch):
    c = _wire(monkeypatch, _users(3))
    assert c.get(REITTI, headers={"X-Admin-Token": "vaara"}).status_code == 403


# --- luku -----------------------------------------------------------------

def test_laskee_konversion_summista(monkeypatch):
    c = _wire(monkeypatch, _users(10), web=["u0", "u1"], app_prem=["u2"])
    d = _get(c).json()
    assert d["total_accounts"] == 10
    assert d["premium_web"] == 2 and d["premium_app"] == 1
    assert d["premium_accounts"] == 3
    assert d["conversion_pct"] == 30.0


def test_store_osto_ei_kaksoislaskeudu_web_tilauksen_kanssa(monkeypatch):
    """`app` = is_premium ILMAN web-tilausta. u0 on molemmissa listoissa."""
    c = _wire(monkeypatch, _users(4), web=["u0"], app_prem=["u0"])
    d = _get(c).json()
    assert d["premium_web"] == 1 and d["premium_app"] == 0
    assert d["premium_accounts"] == 1


def test_nolla_premiumia_on_nolla_ei_none(monkeypatch):
    d = _get(_wire(monkeypatch, _users(5))).json()
    assert d["premium_accounts"] == 0 and d["conversion_pct"] == 0.0


def test_ei_yhtaan_tilia_ei_jaa_nollalla(monkeypatch):
    d = _get(_wire(monkeypatch, [])).json()
    assert d["total_accounts"] == 0 and d["conversion_pct"] is None


# --- fail-closed: nolla ei ole sama kuin "ei tietoa" ----------------------

def test_tililistan_virhe_on_503_ei_nolla(monkeypatch):
    r = _get(_wire(monkeypatch, _users(5), users_status=500))
    assert r.status_code == 503
    assert "not zero accounts" in r.json()["detail"]


def test_tilaushaun_virhe_on_503_ei_nolla(monkeypatch):
    r = _get(_wire(monkeypatch, _users(5), sub_status=500))
    assert r.status_code == 503
    assert "not zero subscribers" in r.json()["detail"]


# --- ilmaisikkuna ---------------------------------------------------------

def test_ikkunan_aikana_luku_merkitaan_vertailukelvottomaksi(monkeypatch):
    d = _get(_wire(monkeypatch, _users(10), web=["u0"], window=True)).json()
    assert d["window_active"] is True
    assert d["comparable"] is False
    assert "free window" in d["caveat"]


def test_negatiivinen_kontrolli_ikkunan_ulkopuolella_luku_on_vertailukelpoinen(monkeypatch):
    """Ilman tata edellinen testi lapaisisi myos jos comparable on AINA False."""
    d = _get(_wire(monkeypatch, _users(10), web=["u0"], window=False)).json()
    assert d["window_active"] is False
    assert d["comparable"] is True


# --- tietosuoja -----------------------------------------------------------

def test_vastaus_ei_sisalla_yhtaan_kayttajatunnistetta(monkeypatch):
    """CI lukee taman. Vain summia: ei id:ta, ei sahkoposteja, ei rivejä."""
    import json
    c = _wire(monkeypatch, _users(6), web=["u0", "u1"], app_prem=["u2"])
    teksti = json.dumps(_get(c).json())
    for kielletty in ("u0", "u1", "u2", "@", "email"):
        assert kielletty not in teksti, kielletty
