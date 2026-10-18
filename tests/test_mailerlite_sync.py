"""Uudet tilit MailerLiten tervetuloryhmään (18.10.2026, Villen päätös: tervetuloviesti, ei blastia).

Neljä asiaa, jotka menisivät hiljaa pieleen:
1. Perunut tilaaja tilataan uudelleen (upsert ei saa lähettää resubscribe- eikä status-kenttää).
2. Ilmaispaketin katto (250) täyttyy ja uusi tili jää ulos ilman että kukaan huomaa (katto_esti).
3. Sähköpostiosoite vuotaa vastaukseen, joka päätyy julkisen repon Actions-lokiin.
4. Epäonnistunut tilihaku näyttää "nolla uutta tiliä" (503, ei tyhjää onnistumista).
"""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

import api.main as m
from src import mailerlite_sync as ms

NYT = dt.datetime(2026, 10, 18, 12, tzinfo=dt.timezone.utc)


def _u(email, paivaa_sitten=1, vahvistettu=True, **kw):
    luotu = (NYT - dt.timedelta(days=paivaa_sitten)).isoformat().replace("+00:00", "Z")
    return {"email": email, "created_at": luotu,
            "email_confirmed_at": luotu if vahvistettu else None, **kw}


def test_synkattavat_vain_tuoreet_vahvistetut_oikeat():
    users = [
        _u("Uusi@Gmail.com"), _u("uusi@gmail.com"), _u("vanha@gmail.com", paivaa_sitten=40),
        _u("vahvistamaton@gmail.com", vahvistettu=False), _u("testi@example.com"),
        _u("anon@gmail.com", is_anonymous=True), {"email": None}, _u("rajalla@gmail.com", paivaa_sitten=13),
    ]
    assert ms.synkattavat(users, NYT, 14) == ["rajalla@gmail.com", "uusi@gmail.com"]


class _R:
    def __init__(self, status=200, data=None):
        self.status_code, self._d = status, data or {}

    def json(self):
        return self._d

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ms.requests.HTTPError(str(self.status_code))


class _Sessio:
    def __init__(self, olemassa=(), tilaajia=10, ryhma=True, post_status=201):
        self.olemassa, self.tilaajia, self.ryhma, self.post_status = set(olemassa), tilaajia, ryhma, post_status
        self.postit = []

    def get(self, url, headers=None, params=None, timeout=None):
        if url.endswith("/groups"):
            return _R(200, {"data": [{"id": 77, "name": ms.RYHMA}] if self.ryhma else []})
        if url.endswith("/subscribers"):
            return _R(200, {"total": self.tilaajia})
        email = ms.requests.utils.unquote(url.rsplit("/", 1)[1])
        return _R(200 if email in self.olemassa else 404)

    def post(self, url, headers=None, json=None, timeout=None):
        self.postit.append(json)
        return _R(self.post_status)


def _ml(**kw):
    s = _Sessio(**kw)
    return ms.MailerLite("t", session=s, tauko=0), s


def test_lisaa_vain_uudet_eika_koskaan_tilaa_uudelleen():
    ml, s = _ml(olemassa={"jo@gmail.com"})
    tulos = ms.synkkaa([_u("jo@gmail.com"), _u("uusi@gmail.com")], ml, nyt=NYT)
    assert tulos["tila"] == "ok" and tulos["lisatty"] == 1 and tulos["jo_listalla"] == 1
    assert s.postit == [{"email": "uusi@gmail.com", "groups": ["77"]}]
    for p in s.postit:
        assert "resubscribe" not in p and "status" not in p


def test_katto_estaa_ja_nakyy():
    ml, s = _ml(tilaajia=ms.KATTO - ms.VARA)
    tulos = ms.synkkaa([_u("a@gmail.com"), _u("b@gmail.com")], ml, nyt=NYT)
    assert tulos["tila"] == "katto" and tulos["katto_esti"] == 2 and tulos["lisatty"] == 0
    assert s.postit == []


def test_puuttuva_ryhma_on_virhe_ei_nolla():
    ml, _ = _ml(ryhma=False)
    assert ms.synkkaa([_u("a@gmail.com")], ml, nyt=NYT)["tila"] == "virhe"


def test_epaonnistunut_lisays_on_virhe():
    ml, _ = _ml(post_status=422)
    tulos = ms.synkkaa([_u("a@gmail.com")], ml, nyt=NYT)
    assert tulos["tila"] == "virhe" and tulos["virheita"] == 1


REITTI = "/api/admin/mailerlite-sync"


@pytest.fixture
def asiakas(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "adm")
    monkeypatch.delenv("MAILERLITE_API_TOKEN", raising=False)
    return TestClient(m.app)


def test_reitti_vaatii_adminin_ja_avaimen(asiakas, monkeypatch):
    assert asiakas.post(REITTI).status_code == 403
    assert asiakas.post(REITTI, headers={"X-Admin-Token": "adm"}).status_code == 400


def test_reitti_tilihaun_virhe_on_503(asiakas, monkeypatch):
    monkeypatch.setattr(m, "_supabase_users", lambda: None)
    r = asiakas.post(REITTI, headers={"X-Admin-Token": "adm", "X-MailerLite-Token": "t"})
    assert r.status_code == 503


def test_reitti_kutsuu_synkkaa_eika_palauta_osoitteita(asiakas, monkeypatch):
    sessio = _Sessio()
    # Reitti käyttää oikeaa kelloa, joten tili luodaan nyt (kiinteä NYT vanhenisi 14 vrk:ssa).
    nyt = dt.datetime.now(dt.timezone.utc).isoformat()
    monkeypatch.setattr(m, "_supabase_users",
                        lambda: [{"email": "uusi@gmail.com", "created_at": nyt, "email_confirmed_at": nyt}])
    alkuperainen = ms.MailerLite
    monkeypatch.setattr(ms, "MailerLite", lambda token: alkuperainen(token, session=sessio, tauko=0))
    r = asiakas.post(REITTI, headers={"X-Admin-Token": "adm", "X-MailerLite-Token": "t"})
    assert r.status_code == 200, r.text
    assert r.json()["lisatty"] == 1 and sessio.postit
    assert "@" not in r.text
