# -*- coding: utf-8 -*-
"""`element_names()` palauttaa nimet, ei tyhjaa dictia hiljaa.

11.9.2026: funktiosta puuttui `import requests`; NameError putosi
`except Exception`iin ja paluuarvo oli {} joka kerta. Vartija loysi
maarittelemattoman nimen, mutta ilman tata testia sama vika olisi voinut
palata toisessa muodossa (fail-open nielaisee mutaation).
"""
from __future__ import annotations

import requests

from src.models import fpl_grade as fg


class _Vastaus:
    status_code = 200

    def json(self):
        return {"elements": [{"id": 1, "web_name": "Haaland"},
                             {"id": 2, "web_name": "Salah"},
                             {"id": "x", "web_name": "roska"}]}


def test_element_names_palauttaa_nimet(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Vastaus())
    assert fg.element_names() == {1: "Haaland", 2: "Salah"}


def test_element_names_on_tyhja_vain_kun_haku_epaonnistuu(monkeypatch):
    """Kontrolli: tyhja dict on sallittu VAIN verkkovirheesta."""
    def kaatuu(*a, **k):
        raise requests.ConnectionError("ei verkkoa")
    monkeypatch.setattr(requests, "get", kaatuu)
    assert fg.element_names() == {}
