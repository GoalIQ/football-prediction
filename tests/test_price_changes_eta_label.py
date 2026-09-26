"""Portti: hintapaivityksen hetki ilman lukijan aikavyohyketta
(PRICE-ETA-PALVELINSIVUT, 26.9.2026, julkaisutarkistaja B1-B3).

Staattinen sivu ja backend eivat tieda lukijan aikaa. FPL paivittaa 23:00Z
(Aasiassa aamu), offset 1 on aina 24-48 h paassa, ja "next update" vanhenee
heti paivityksen jalkeen. YKSI muotoilija (src/price_update_time.py) hubille ja
GW review -lauseelle: absoluuttinen UK-hetki `eta_at`:sta, mennyt tai puuttuva
hetki -> ei aikalausetta.
"""
from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path

from scripts import build_fpl_longtail as L
from src.models import fpl_gw_review as GR
from src.models import fpl_model_says as MS
from src.price_update_time import price_update_parts

ROOT = Path(__file__).resolve().parents[1]
ENNEN = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)
JALKEEN = datetime(2026, 9, 26, 23, 30, tzinfo=timezone.utc)
AT = "2026-09-26T23:00:00Z"


def _row(**kw):
    return {"web_name": "X", "now_cost": 5.0, "confidence": 0.9, **kw}


def test_muotoilija_uk_aika_ja_kellojen_siirto():
    assert price_update_parts(AT, ENNEN) == ("Sun 27 Sep", "00:00")
    # 25.10.2026 jalkeen UK on GMT: 23:00Z = 23:00 samana paivana.
    assert price_update_parts("2026-10-31T23:00:00Z", ENNEN) == ("Sat 31 Oct", "23:00")


def test_muotoilija_mennyt_puuttuva_tai_virheellinen_on_none():
    assert price_update_parts(AT, JALKEEN) is None
    assert price_update_parts(AT, datetime(2026, 9, 26, 23, tzinfo=timezone.utc)) is None
    for huono in (None, "", "huomenna", "2026-09-26T23:00:00", 5):
        assert price_update_parts(huono, ENNEN) is None, huono


def test_hubin_rivi():
    assert (L._eta_label(_row(eta_days=0, eta_at=AT), ENNEN)
            == "projected for the Sun 27 Sep price update, 00:00 UK time")
    assert L._eta_label(_row(eta_days=0, eta_at=AT), JALKEEN) == "no date yet"
    for eta in (0, 1, 3, None):
        assert L._eta_label(_row(eta_days=eta), ENNEN) == "no date yet"


def test_hubin_sivulla_ei_suhteellisia_paivasanoja():
    pw = {"meta": {"available": True},
          "risers": [_row(web_name="A", eta_days=0, eta_at=AT),
                     _row(web_name="B", eta_days=1)],
          "fallers": [_row(web_name="C", eta_days=2)]}
    html = L.render_price_changes(pw, ENNEN)
    body = html.split("<body", 1)[-1]
    for sana in ("projected tonight", "projected tomorrow", "projected in "):
        assert sana not in body, sana
    assert "projected for the Sun 27 Sep price update, 00:00 UK time" in body
    # Meta-kuvaus ei vaita "tonight's risers" (tarkistaja B3).
    assert "tonight's risers" not in html


def _lause(now, **kw):
    return MS.flag_lines({"price": [{"web_name": "X", "direction": "rise",
                                     "progress_pct": 68, **kw}]}, now=now)[0]["text"]


def test_gw_review_lause_absoluuttinen_tai_ei_mitaan():
    assert _lause(ENNEN, eta_days=0, eta_at=AT) == (
        "X is 68% of the way to a price rise, at the Sun 27 Sep price update "
        "(00:00 UK time) if it gets there.")
    # Paivitys meni jo: ei "next update" -lupausta.
    assert _lause(JALKEEN, eta_days=0, eta_at=AT) == "X is 68% of the way to a price rise."
    # Pelkka offset ei tuota aikaa (1 = aina 24-48 h paassa).
    for eta in (0, 1, 2, None):
        teksti = _lause(ENNEN, eta_days=eta).lower()
        for sana in ("tonight", "tomorrow", "today", "within a day", "next price update"):
            assert sana not in teksti, (eta, teksti)


def test_gw_review_valittaa_eta_atin_kutsupaikassa():
    pw = {"risers": [{"id": 7, "web_name": "X", "progress_pct": 68,
                      "eta_days": 0, "eta_at": AT, "confidence": 0.7}],
          "fallers": [{"id": 9, "web_name": "Y", "progress_pct": 50}]}
    liput = GR.price_flags(pw, [7])
    assert liput == [{"id": 7, "web_name": "X", "direction": "rise",
                      "progress_pct": 68, "eta_days": 0, "eta_at": AT,
                      "confidence": 0.7}]
    # Kutsupaikka kayttaa apufunktiota (ei omaa kopiota ilman eta_at:ia).
    puu = ast.parse((ROOT / "src/models/fpl_gw_review.py").read_text(encoding="utf-8"))
    kutsut = [n for n in ast.walk(puu) if isinstance(n, ast.Call)
              and getattr(n.func, "id", None) == "price_flags"]
    assert len(kutsut) == 1
