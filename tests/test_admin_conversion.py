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


def _users(n, comp=()):
    return [{"id": f"u{i}", "created_at": "2026-08-01T00:00:00Z",
             "user_metadata": ({"comp": True} if f"u{i}" in comp else {})}
            for i in range(n)]


# --- portti ---------------------------------------------------------------

def test_ilman_tokenia_403(monkeypatch):
    assert _wire(monkeypatch, _users(3)).get(REITTI).status_code == 403


def test_vaaralla_tokenilla_403(monkeypatch):
    c = _wire(monkeypatch, _users(3))
    assert c.get(REITTI, headers={"X-Admin-Token": "vaara"}).status_code == 403


# --- kolme amparia -------------------------------------------------------

def test_web_comp_ja_attribuoimaton_ovat_eri_amparit(monkeypatch):
    c = _wire(monkeypatch, _users(10, comp=["u2"]), web=["u0", "u1"],
              app_prem=["u2", "u3"])
    d = _get(c).json()
    assert d["total_accounts"] == 10
    assert d["premium_web"] == 2
    assert d["premium_comp"] == 1
    assert d["premium_unattributed"] == 1
    assert d["premium_accounts"] == 4


def test_comp_ei_ole_konversio_kummassakaan_rajassa(monkeypatch):
    """Comp-tili ei ole konversio: kukaan ei maksanut siita."""
    c = _wire(monkeypatch, _users(10, comp=["u2", "u3"]), web=["u0"],
              app_prem=["u2", "u3"])
    d = _get(c).json()
    assert d["premium_comp"] == 2 and d["premium_unattributed"] == 0
    assert d["conversion_pct_min"] == 10.0 and d["conversion_pct_max"] == 10.0


def test_negatiivinen_kontrolli_comp_merkinnan_lisays_ei_nosta_konversiota(monkeypatch):
    """DoD-vaatimus: comp-tilin merkitseminen saa vain LASKEA ylarajaa."""
    ilman = _get(_wire(monkeypatch, _users(10), web=["u0"], app_prem=["u2"])).json()
    kanssa = _get(_wire(monkeypatch, _users(10, comp=["u2"]), web=["u0"],
                        app_prem=["u2"])).json()
    assert ilman["conversion_pct_max"] == 20.0
    assert kanssa["conversion_pct_max"] == 10.0
    assert kanssa["conversion_pct_min"] == ilman["conversion_pct_min"] == 10.0


def test_attribuoimaton_tekee_luvusta_valin(monkeypatch):
    d = _get(_wire(monkeypatch, _users(10), web=["u0"], app_prem=["u2", "u3"])).json()
    assert d["conversion_pct_min"] == 10.0
    assert d["conversion_pct_max"] == 30.0
    assert d["conversion_exact"] is False


def test_kun_kaikki_on_attribuoitu_vali_sulkeutuu(monkeypatch):
    d = _get(_wire(monkeypatch, _users(10, comp=["u2"]), web=["u0"], app_prem=["u2"])).json()
    assert d["conversion_pct_min"] == d["conversion_pct_max"] == 10.0
    assert d["conversion_exact"] is True


def test_store_osto_ei_kaksoislaskeudu_web_tilauksen_kanssa(monkeypatch):
    c = _wire(monkeypatch, _users(4), web=["u0"], app_prem=["u0"])
    d = _get(c).json()
    assert d["premium_web"] == 1 and d["premium_unattributed"] == 0
    assert d["premium_accounts"] == 1


def test_comp_merkinta_ilman_premiumia_ei_lasketa(monkeypatch):
    """Merkitty mutta ei is_premium -> ei kuulu yhteenkaan ampariin."""
    d = _get(_wire(monkeypatch, _users(5, comp=["u4"]), web=["u0"], app_prem=["u1"])).json()
    assert d["premium_comp"] == 0 and d["premium_accounts"] == 2


def test_nolla_premiumia_on_nolla_ei_none(monkeypatch):
    d = _get(_wire(monkeypatch, _users(5))).json()
    assert d["premium_accounts"] == 0
    assert d["conversion_pct_min"] == 0.0 and d["conversion_pct_max"] == 0.0


def test_ei_yhtaan_tilia_ei_jaa_nollalla(monkeypatch):
    d = _get(_wire(monkeypatch, [])).json()
    assert d["total_accounts"] == 0
    assert d["conversion_pct_min"] is None and d["conversion_pct_max"] is None
    assert d["conversion_exact"] is False


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


# --- comp-merkinta (POST /api/admin/comp-premium) -------------------------
#
# Merkinta on ainoa tapa erottaa comp store-ostosta: sita EI voi paatella
# nykydatasta jalkikateen, koska comp on kirjoitettu kasin is_premiumiin.

MERKINTA = "/api/admin/comp-premium"


def _wire_put(monkeypatch, users, put_status=200):
    c = _wire(monkeypatch, users)
    nahty = {}

    def fake_put(url, json=None, headers=None, timeout=None):
        nahty["url"], nahty["json"] = url, json
        return _Resp({}, put_status)

    monkeypatch.setattr(m.requests, "put", fake_put)
    return c, nahty


def _kayttaja(email, meta=None):
    return {"id": "u0", "email": email, "created_at": "2026-08-01T00:00:00Z",
            "user_metadata": meta or {}}


def test_merkinta_vaatii_admin_tokenin(monkeypatch):
    c, _ = _wire_put(monkeypatch, [_kayttaja("a@b.c")])
    assert c.post(MERKINTA, json={"email": "a@b.c"}).status_code == 403


def test_merkinta_asettaa_comp_lipun(monkeypatch):
    c, nahty = _wire_put(monkeypatch, [_kayttaja("a@b.c")])
    r = c.post(MERKINTA, json={"email": "a@b.c"},
               headers={"X-Admin-Token": "adm"})
    assert r.status_code == 200
    assert r.json()["comp_before"] is False and r.json()["comp_now"] is True
    assert nahty["json"]["user_metadata"]["comp"] is True


def test_merkinta_ei_pudota_muuta_metadataa(monkeypatch):
    """creator-coden opetus: kasin editointi ylikirjoittaa herkasti `ref`in."""
    c, nahty = _wire_put(monkeypatch, [
        _kayttaja("a@b.c", {"ref": "WOLFY", "creator_code": "WOLFY"})])
    c.post(MERKINTA, json={"email": "a@b.c"}, headers={"X-Admin-Token": "adm"})
    meta = nahty["json"]["user_metadata"]
    assert meta["ref"] == "WOLFY" and meta["creator_code"] == "WOLFY"
    assert meta["comp"] is True


def test_merkinnan_poisto_jattaa_muun_metadatan(monkeypatch):
    c, nahty = _wire_put(monkeypatch, [
        _kayttaja("a@b.c", {"comp": True, "ref": "DAZ"})])
    r = c.post(MERKINTA, json={"email": "a@b.c", "comp": False},
               headers={"X-Admin-Token": "adm"})
    assert r.json()["comp_before"] is True and r.json()["comp_now"] is False
    assert "comp" not in nahty["json"]["user_metadata"]
    assert nahty["json"]["user_metadata"]["ref"] == "DAZ"


def test_tuntematon_sahkoposti_on_404_ei_hiljainen_ok(monkeypatch):
    c, _ = _wire_put(monkeypatch, [_kayttaja("a@b.c")])
    r = c.post(MERKINTA, json={"email": "ei@ole.c"},
               headers={"X-Admin-Token": "adm"})
    assert r.status_code == 404


def test_supabasen_virhe_kirjoituksessa_on_502(monkeypatch):
    c, _ = _wire_put(monkeypatch, [_kayttaja("a@b.c")], put_status=500)
    r = c.post(MERKINTA, json={"email": "a@b.c"},
               headers={"X-Admin-Token": "adm"})
    assert r.status_code == 502
