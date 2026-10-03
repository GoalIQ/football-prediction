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
def _fd_xg_ei_understatia(monkeypatch):
    """28.9 (XG-NELJA-LIIGAA-UNDERSTAT): loaderin FD-haara hakee ottelun xG:n
    Understatista. Testi ei saa riippua verkosta eika koneen Understat-
    valimuistista: haku kaatuu, jolloin rikastus on fail-open ja -FD-rivit
    pysyvat ilman xG:ta (sama kaikilla koneilla ja CI:ssa). Rikastuksen oma
    portti (tests/test_fd_xg.py) korvaa taman omalla syotteellaan."""
    from src.data import loader

    def ei_verkkoa(*a, **k):
        raise RuntimeError("Understat-haku FD-rikastukselle estetty testeissa (tests/conftest.py)")

    monkeypatch.setattr(loader, "_understat_rivit", ei_verkkoa)


# 3.10.2026: UEFA-live-haun esto poistettu, koska src/data/uefa_matches.py on
# poistettu (UEFA-haku lopetettu). Portti: tests/test_no_uefa_fetch.py.
