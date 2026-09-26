"""Portti: hubin /fpl/price-changes ei kayta lukijan aikaan sidottuja sanoja
(PRICE-ETA-PALVELINSIVUT, 26.9.2026).

Staattinen sivu ei tieda lukijan aikavyohyketta. FPL paivittaa hinnat 23:00Z,
joka on Aasiassa aamu ja Amerikoissa ilta, joten "projected tonight" oli
vaarin osalle lukijoista. Rivi naytetaan absoluuttisena hetkena UK-aikana
`eta_at`:sta (sama lahde kuin SPA:n ja mobiilin lib/priceEta). Kellonaika on
oikea myos kellojen siirron yli (BST -> GMT 25.10.2026).
"""
from __future__ import annotations

from datetime import datetime, timezone

from scripts import build_fpl_longtail as L


def _row(**kw):
    return {"web_name": "X", "now_cost": 5.0, "confidence": 0.9, **kw}


def test_eta_at_absoluuttisena_uk_aikana():
    assert (L._eta_label(_row(eta_days=0, eta_at="2026-09-26T23:00:00Z"))
            == "projected for the Sun 27 Sep update, 00:00 UK time")


def test_kellojen_siirron_jalkeen_gmt():
    # 25.10.2026 jalkeen UK on GMT: 23:00Z = 23:00 samana paivana.
    assert (L._eta_label(_row(eta_days=0, eta_at="2026-10-31T23:00:00Z"))
            == "projected for the Sat 31 Oct update, 23:00 UK time")


def test_ilman_eta_atia_ei_paivaa_vaikka_eta_days_olisi():
    for eta in (0, 1, 3, None):
        assert L._eta_label(_row(eta_days=eta)) == "no date yet"
    assert L._eta_label(_row(eta_days=0, eta_at="huomenna")) == "no date yet"


def test_sivulla_ei_suhteellisia_paivasanoja():
    pw = {"meta": {"available": True},
          "risers": [_row(web_name="A", eta_days=0, eta_at="2026-09-26T23:00:00Z"),
                     _row(web_name="B", eta_days=1)],
          "fallers": [_row(web_name="C", eta_days=2)]}
    html = L.render_price_changes(pw, datetime(2026, 9, 26, 12, tzinfo=timezone.utc))
    body = html.split("<body", 1)[-1]
    for sana in ("projected tonight", "projected tomorrow", "projected in "):
        assert sana not in body, sana
    assert "projected for the Sun 27 Sep update, 00:00 UK time" in body
