# -*- coding: utf-8 -*-
"""API-VIRHETELEMETRIA (30.8.2026): reittikohtaiset statusluokat.

Taustaa: Barryn 400 (@UnitedCynic 28.8) oli tuotannossa viisi vuorokautta ja
loytyi vasta kun han twiittasi siita. Tama laskuri on halvin mahdollinen tapa
nahda sama asia itse.

Vaarin menemisen tavat, ja siksi jokaiselle oma testi:
1. avaimena raakapolku -> kardinaliteetti raajahtaa JA kayttajadata (entry-id)
   paatyy muistiin,
2. telemetria kaataa pyynnon,
3. endpoint vuotaa ilman tokenia,
4. `since` puuttuu, jolloin luku ei ole tulkittavissa deployn jalkeen.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("ADMIN_TOKEN", "testi-admin-token")

from fastapi.testclient import TestClient  # noqa: E402

from api import main as m  # noqa: E402

TOKEN = {"x-admin-token": os.environ["ADMIN_TOKEN"]}


@pytest.fixture
def client():
    with m._ERR_LOCK:
        m._ERR_COUNTS.clear()
    return TestClient(m.app)


def _counts(client):
    return client.get("/api/admin/error-counts", headers=TOKEN).json()


def test_endpoint_vaatii_tokenin(client):
    assert client.get("/api/admin/error-counts").status_code == 403


def test_endpoint_palauttaa_sincen(client):
    d = _counts(client)
    assert d["since"] and d["since"].endswith("Z")
    assert "routes" in d


def test_avain_on_reittipohja_ei_raakapolku(client):
    """Kaksi eri query-stringia = YKSI avain. Jos avaimena olisi raakapolku,
    jokainen entry-id ja parametriyhdistelma olisi oma rivinsa muistissa -
    seka kardinaliteettiongelma etta kayttajadataa."""
    client.get("/api/predict?home=Arsenal&away=Chelsea")
    client.get("/api/predict?home=Everton&away=Fulham")
    reitit = _counts(client)["routes"]
    osumat = [k for k in reitit if k.startswith("/api/predict")]
    assert osumat == ["/api/predict"], reitit
    assert not any("Arsenal" in k or "?" in k for k in reitit)


def test_reitittamaton_polku_ei_paady_avaimeksi(client):
    """404 tuntemattomaan polkuun on yksi kori. Muuten kuka tahansa voisi
    kasvattaa muistinkulutusta kutsumalla satunnaisia polkuja."""
    client.get("/api/ei-ole-olemassa-1")
    client.get("/api/ei-ole-olemassa-2")
    reitit = _counts(client)["routes"]
    assert "<unrouted>" in reitit
    assert reitit["<unrouted>"]["4xx"] == 2
    assert not any("ei-ole-olemassa" in k for k in reitit)


def test_statusluokat_erotellaan():
    assert m._status_class(200) == "ok"
    assert m._status_class(302) == "ok"
    assert m._status_class(400) == "4xx"
    assert m._status_class(404) == "4xx"
    assert m._status_class(500) == "5xx"
    assert m._status_class(503) == "5xx"


def test_kattoraja_estaa_rajattoman_kasvun(client):
    """Negatiivinen kontrolli katolle: taytetaan sanakirja yli rajan ja
    varmistetaan etta uudet menevat overflow-koriin eivat omiksi riveikseen."""
    with m._ERR_LOCK:
        for i in range(m._ERR_MAX_ROUTES):
            m._ERR_COUNTS[f"/tekaistu/{i}"] = {"ok": 1, "4xx": 0, "5xx": 0}
    client.get("/api/ei-ole-olemassa-3")
    reitit = _counts(client)["routes"]
    assert "<overflow>" in reitit
    assert len([k for k in reitit if k.startswith("/tekaistu/")]) == m._ERR_MAX_ROUTES


def test_telemetria_ei_kaada_pyyntoa(client, monkeypatch):
    """TARKEIN: jos laskuri kaatuu, pyynnon PITAA silti onnistua. Telemetria
    ei ole syy palvella 500:aa."""
    class Rikki:
        def __enter__(self):
            raise RuntimeError("lukko rikki")
        def __exit__(self, *a):
            return False
    monkeypatch.setattr(m, "_ERR_LOCK", Rikki())
    r = client.get("/api/ei-ole-olemassa-4")
    assert r.status_code == 404   # ei 500


def test_vastaus_ei_sisalla_kayttajadataa(client):
    """Vastauksessa saa olla vain reittipohjia ja lukuja."""
    client.get("/api/predict?home=Arsenal&away=Chelsea")
    d = _counts(client)
    for avain, rivi in d["routes"].items():
        assert avain.startswith("/") or avain in {"<unrouted>", "<overflow>"}
        assert set(rivi) <= {"ok", "4xx", "5xx"}
        assert all(isinstance(v, int) for v in rivi.values())
