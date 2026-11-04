"""Kausipassin provisio (WP6, Villen paatos 4.11.2026: 30 % myos passista).

Julkaisutarkistaja 4.11 loysi kaksi aukkoa ennen kuin yksikaan passi oli
myyty:

  1. Leima kirjoitettiin `_fulfil_season_pass`in VIIMEISENA. Funktio palaa
     ennen sita kolmella polulla (aktiivinen web-tilaus, avoin oikeus,
     premium_source-leima kaatuu = migraatio ajamatta). Viimeinen olisi
     tarkoittanut, ettei YKSIKAAN passi saa provisiota.
  2. Koodilla ostetun passin attribuutio nojasi pelkkaan
     `session.discounts`iin. Tilauksella on varapolku (tilauksen oma
     discount), passilla ei ollut. Nyt: session `total_details.breakdown`.
"""
from __future__ import annotations

import pytest

import api.main as m


class _Retriever:
    def __init__(self, sess=None, fails=False):
        self.sess = sess
        self.fails = fails
        self.calls: list = []

    def retrieve(self, sess_id, **kw):
        self.calls.append((sess_id, kw))
        if self.fails:
            raise RuntimeError("stripe down")
        return self.sess


def _wire_session(monkeypatch, retr: _Retriever):
    class _Checkout:
        Session = retr
    monkeypatch.setattr(m.stripe, "checkout", _Checkout)


def _breakdown(code):
    return {"total_details": {"breakdown": {"discounts": [
        {"amount": 750, "discount": {"promotion_code": {"code": code}}}]}}}


def test_kertamaksun_koodi_luetaan_breakdownista(monkeypatch):
    retr = _Retriever(_breakdown("DAZ"))
    _wire_session(monkeypatch, retr)
    sess = {"id": "cs_1", "mode": "payment", "payment_intent": "pi_1"}
    assert m._affiliate_code_from_session(sess) == ("DAZ", "promo")
    assert retr.calls == [("cs_1", {"expand": ["total_details.breakdown"]})]


def test_payloadin_discounts_riittaa_ilman_hakua(monkeypatch):
    retr = _Retriever(_breakdown("DAZ"))
    _wire_session(monkeypatch, retr)
    sess = {"id": "cs_1", "mode": "payment",
            "discounts": [{"promotion_code": {"code": "WOLFY"}}]}
    assert m._affiliate_code_from_session(sess) == ("WOLFY", "promo")
    assert retr.calls == []


def test_haun_virhe_ei_kaada_ja_ref_jaa_viimeiseksi_sanaksi(monkeypatch):
    retr = _Retriever(fails=True)
    _wire_session(monkeypatch, retr)
    sess = {"id": "cs_1", "mode": "payment", "metadata": {"ref": "ROWAN"}}
    assert m._affiliate_code_from_session(sess) == ("ROWAN", "ref")


def test_tilauksella_ei_tehda_ylimaaraista_sessiohakua(monkeypatch):
    retr = _Retriever(_breakdown("DAZ"))
    _wire_session(monkeypatch, retr)
    sess = {"id": "cs_1", "mode": "subscription", "metadata": {"ref": "ROWAN"}}
    assert m._affiliate_code_from_session(sess) == ("ROWAN", "ref")
    assert retr.calls == []


@pytest.fixture
def fulfil(monkeypatch):
    """`_fulfil_season_pass` ilman kantaa: kirjaa leimakutsut."""
    leimat: list = []
    monkeypatch.setattr(m, "_affiliate_code_from_session", lambda obj: ("DAZ", "promo"))
    monkeypatch.setattr(m, "_stamp_affiliate_payment",
                        lambda pi, code, src: leimat.append((pi, code, src)) or True)
    monkeypatch.setattr(m, "_get_web_subscription", lambda *a, **k: None)
    monkeypatch.setattr(m, "_upsert_web_subscription", lambda row: True)
    monkeypatch.setattr(m, "_get_profile_premium_state", lambda uid: None)
    monkeypatch.setattr(m, "_stamp_premium_source", lambda uid, src: True)
    monkeypatch.setattr(m, "_update_profile", lambda uid, d: True)
    return leimat


SESSIO = {"id": "cs_1", "mode": "payment", "payment_intent": "pi_1", "customer": "cus_1"}


def test_leima_kirjoitetaan_normaalissa_ostossa(fulfil):
    m._fulfil_season_pass("u1", dict(SESSIO))
    assert fulfil == [("pi_1", "DAZ", "promo")]


def test_leima_kirjoitetaan_vaikka_migraatio_puuttuu(fulfil, monkeypatch):
    """premium_source-leima kaatuu -> profiilia ei avata, mutta provisio
    kuuluu silti luojalle: maksu on mennyt lapi."""
    monkeypatch.setattr(m, "_stamp_premium_source", lambda uid, src: False)
    m._fulfil_season_pass("u1", dict(SESSIO))
    assert fulfil == [("pi_1", "DAZ", "promo")]


def test_leima_kirjoitetaan_aktiivisen_tilauksen_paalle(fulfil, monkeypatch):
    """Rivi ei korvaannu (hyvitys kasin); jos passi hyvitetaan, raportti
    laskee sen passes_refunded-lukuun eika provisiota makseta."""
    monkeypatch.setattr(m, "_get_web_subscription",
                        lambda *a, **k: {"stripe_subscription_id": "sub_1",
                                         "status": "active",
                                         "current_period_end": "2099-01-01T00:00:00+00:00"})
    monkeypatch.setattr(m.season_pass, "web_row_active", lambda row, *a, **k: True)
    m._fulfil_season_pass("u1", dict(SESSIO))
    assert fulfil == [("pi_1", "DAZ", "promo")]


def test_leiman_virhe_ei_esta_oikeutta(fulfil, monkeypatch):
    avattu: list = []
    monkeypatch.setattr(m, "_affiliate_code_from_session",
                        lambda obj: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(m, "_update_profile", lambda uid, d: avattu.append(d) or True)
    m._fulfil_season_pass("u1", dict(SESSIO))
    assert avattu and avattu[0]["is_premium"] is True
