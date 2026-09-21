"""Yhteiset fixturet: in-process TestClient ilman lifespan-kontekstia.

TestClient(app) ILMAN with-lohkoa ei aja startup-eventtejä → warmup-säie
(6 domestic-fittiä) ei käynnisty. Domestic-testit fittaavat on-demand (slow),
WC-testit lataavat vain esirakennetun data/wc_model.json:in (nopea).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client() -> TestClient:
    from api.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_fd_http_cache():
    """#49: FD-TTL-cache on prosessitason tila — nollataan joka testissä ettei
    cache vuoda testien välillä (mock-vastaus vs cachetettu edellinen)."""
    import api.main as m
    m._FD_HTTP_CACHE.clear()
    yield
    m._FD_HTTP_CACHE.clear()


@pytest.fixture(autouse=True)
def _uefa_ei_verkkoa(monkeypatch, tmp_path_factory):
    """21.9: UEFA-yhteisfitti hakee kuluvan kauden match.uefa.com:sta. Testi ei
    saa riippua verkosta eika koneen levyvalimuistista: live-haku kaatuu ja
    valimuisti on tyhja hakemisto, jolloin kuluva kausi on tyhja ja vain
    vendoroidut kaudet ovat kaytossa (sama kaikilla koneilla ja CI:ssa)."""
    from src.data import uefa_matches

    def ei_verkkoa(*a, **k):
        raise RuntimeError("UEFA-live-haku estetty testeissa (tests/conftest.py)")

    monkeypatch.setattr(uefa_matches, "_hae_raaka", ei_verkkoa)
    monkeypatch.setattr(uefa_matches, "CACHE_DIR", tmp_path_factory.mktemp("uefa_matches"))
