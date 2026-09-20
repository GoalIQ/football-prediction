# -*- coding: utf-8 -*-
"""Portti: puuttuva ymparistomuuttuja ei saa olla nakymaton.

🔴 MITATTU 20.9.2026. Renderin ymparisto pyyhkiytyi yhdella vaaralla
API-kutsulla. Seuraus oli NAKYMATON: palvelu kaynnistyi, vastasi 200 ja
tarjoili dataa normaalisti. Silti kaksi asiaa oli rikki:

  - ostaminen (STRIPE_SECRET_KEY puuttui),
  - maskaus (PREMIUM_ENFORCE puuttui -> oletus off -> koko Premium-lista
    479 pelaajaa annettiin ilmaiseksi).

Kumpikaan ei kirjoittanut lokiin mitaan, eika mikaan pinta kertonut siita.
Vika loytyi sattumalta: uusi /api/web/pricing palautti tyhjan listan.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api.main as m


@pytest.fixture
def client():
    return TestClient(m.app)


def test_health_endpoint_kertoo_puuttuvat(client, monkeypatch):
    for k in m._PAKOLLISET_ENV:
        monkeypatch.delenv(k, raising=False)
    d = client.get("/api/health/env").json()
    assert d["ok"] is False
    assert set(d["missing"]) == set(m._PAKOLLISET_ENV)


def test_health_endpoint_on_vihrea_kun_kaikki_on(client, monkeypatch):
    for k in m._PAKOLLISET_ENV:
        monkeypatch.setenv(k, "x")
    d = client.get("/api/health/env").json()
    assert d["ok"] is True and d["missing"] == []


def test_health_ei_paljasta_arvoja(client, monkeypatch):
    """Salaisuus lokiin tai vastaukseen olisi pahempi kuin puuttuva muuttuja."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_SALAISUUS123")
    teksti = client.get("/api/health/env").text
    assert "SALAISUUS123" not in teksti and "sk_live" not in teksti


def test_premium_enforce_on_listalla():
    """Tama on se muuttuja jonka puuttuminen ANTAA TUOTTEEN ILMAISEKSI.

    `api/premium.py`: PREMIUM_ENFORCE oletus on off, jolloin
    `is_premium_request` palauttaa aina True. Se oli tietoinen valinta
    kayttoonottovaiheessa, mutta se tarkoittaa etta unohtunut muuttuja ei
    kaada mitaan - se vain lakkaa laskuttamasta. Siksi se on tassa listassa.
    """
    assert "PREMIUM_ENFORCE" in m._PAKOLLISET_ENV
    assert "ILMAISEKSI" in m._PAKOLLISET_ENV["PREMIUM_ENFORCE"].upper()


def test_jokaisella_on_seuraus_kirjoitettuna():
    """Pelkka nimilista ei kerro mita rikkoutuu. Lukija naki 20.9 kahdeksan
    nimea eika tiennyt kumpi niista pysaytti myynnin."""
    for k, miksi in m._PAKOLLISET_ENV.items():
        assert miksi and len(miksi) > 10, f"{k}: seuraus kirjoittamatta"
