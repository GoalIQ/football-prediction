"""football-data.org 429: odotetaan palvelimen ilmoittama aika (21.9.2026).

Tausta: kiintio (10/min) on avainkohtainen ja sita kayttavat samaan aikaan
Render-API, ucl-refresh ja muut workflow't. Vanha kasittely odotti 8 s ja
yritti kerran, vaikka palvelin sanoi "Wait 31 seconds" - toinen yritys osui
samaan ikkunaan. ucl-refresh 21.9 12:56 UTC: Serie A 26/27 ja Ligue 1
molemmat kaudet putosivat, UEFA-mallin kalibroituvat liigat 5 -> 3 ja Napoli
oli 36 CL-seurasta 33:s.

Hermeettinen: requests.get ja time.sleep mockataan, kello on simuloitu.
"""
from __future__ import annotations

import pytest

import src.data.football_data_org as fdo


class _Resp:
    def __init__(self, status: int, headers: dict | None = None, text: str = "", data=None):
        self.status_code = status
        self.headers = headers or {}
        self.text = text
        self._data = data if data is not None else {"matches": []}

    def json(self):
        return self._data


@pytest.fixture
def kello(monkeypatch):
    """Simuloitu kello: sleep siirtaa kelloa, ei odota oikeasti."""
    tila = {"t": 1000.0, "unet": []}

    def fake_sleep(s):
        tila["unet"].append(s)
        tila["t"] += s

    monkeypatch.setattr(fdo.time, "sleep", fake_sleep)
    monkeypatch.setattr(fdo.time, "time", lambda: tila["t"])
    monkeypatch.setattr(fdo, "_FDORG_LAST_CALL_AT", [0.0])
    return tila


def _palvelin(monkeypatch, kello, vapautuu_sekunnissa: float, otsake: bool = True):
    """Palvelin joka vastaa 429 kunnes kiintio-ikkuna vapautuu."""
    alku = kello["t"]
    kutsut = []

    def fake_get(url, headers=None, timeout=None):
        kutsut.append(kello["t"])
        jaljella = vapautuu_sekunnissa - (kello["t"] - alku)
        if jaljella > 0:
            h = {"X-RequestCounter-Reset": str(int(jaljella))} if otsake else {}
            return _Resp(429, headers=h, text=(
                '{"message":"You reached your request limit. Wait %d seconds.",'
                '"errorCode":429}' % int(jaljella)))
        return _Resp(200, data={"matches": [{"id": 1}]})

    monkeypatch.setattr(fdo.requests, "get", fake_get)
    return kutsut


def test_odottaa_otsakkeen_ajan_ja_onnistuu(monkeypatch, kello):
    """Tuotannon tapaus: 'Wait 31 seconds'. Vanha koodi (8 s + 1 yritys) epaonnistui."""
    _palvelin(monkeypatch, kello, vapautuu_sekunnissa=31)
    data = fdo._fetch_from_api("SA", "2026", "avain")
    assert "_error" not in data, data
    assert data["matches"] == [{"id": 1}]


def test_viestin_wait_n_seconds_riittaa_ilman_otsaketta(monkeypatch, kello):
    _palvelin(monkeypatch, kello, vapautuu_sekunnissa=31, otsake=False)
    data = fdo._fetch_from_api("FL1", "2526", "avain")
    assert "_error" not in data, data


def test_budjetti_rajaa_odotuksen(monkeypatch, kello):
    """Jos joku kayttaa avainta jatkuvasti, ei jaada odottamaan ikuisesti."""
    _palvelin(monkeypatch, kello, vapautuu_sekunnissa=10_000)
    data = fdo._fetch_from_api("FL1", "2627", "avain")
    assert "_error" in data and "429" in data["_error"]
    assert sum(kello["unet"]) <= fdo._RETRY_429_BUDJETTI_SEC + fdo._FDORG_MIN_INTERVAL_SEC


@pytest.mark.parametrize("otsake,teksti,odotus", [
    ({"X-RequestCounter-Reset": "31"}, "", 32.0),
    ({}, "Wait 16 seconds.", 17.0),
    ({}, "", 61.0),
    ({"X-RequestCounter-Reset": "999"}, "", 62.0),
])
def test_odotuksen_luku(otsake, teksti, odotus):
    assert fdo._odotus_429(_Resp(429, headers=otsake, text=teksti)) == odotus
