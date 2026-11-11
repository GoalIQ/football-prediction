# -*- coding: utf-8 -*-
"""Botin 1X2-track record: sivun teksti ja moduulin luku samasta lukijasta (7.11.2026).

MITATTU 7.11.2026: Bluesky-botin `track_record`-aihe oli postannut kahdesti,
molemmat kertaa vain xP-virheesta. Syy oli kolme vikaa paallekkain:

  (1) `public_surface.track_record_sentence` etsi lausetta "Across the N
      completed matches, the model called ... of matches", mutta /fpl on
      sanonut 26.9 alkaen "Across the N completed club matches, it called
      ... of them". Lukija palautti tyhjan, joten 1X2-luvuilla ei ollut
      julkista reittia (public_url None) ja portti hylkasi ne hiljaa.
  (2) Moduulin luku tuli `all_time`sta (53.7 % / 1067, sis. MM-kisojen
      maajoukkuemallin), vaikka jokainen sivu nayttaa seuramallin
      `public_headline`in (53.2 % / 1011).
  (3) Botin ohje linkittaa track record -postauksen sivulle
      /predictions#record, mutta luvun ainoa reitti oli /fpl, ja bsky_gate
      vaatii luvun nakyvan linkin sivulla. Korjattu (1)+(2) olisi silti
      hylatty jokaisessa ohjeen mukaisessa postauksessa.

KORJAUS (CLAUDE.md 6a): moduuli lukee saman `public_headline`in kuin sivut,
ensisijainen reitti on record-sivu ja /fpl varareitti. Tama portti ajaa
KUMMANKIN SIVUN OMAN builderin HTML:n lukijan lapi. Jos joku muuttaa
sanamuotoa, lukija lakkaa loytamasta sita ja testi kaatuu ennen kuin botti
hiljenee. Mitataan useassa tilassa (pieni ja iso otos, tasaluku, all_time
eri kuin seuramalli, ei perustasoa, vanha skeema), ei vain tanaan.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_fpl_page as b
from src.marketing import bsky_gate as gate
from src.marketing import public_surface as ps
from src.marketing import reply_module as rm
from src.marketing import reply_sections as rs
from src.models import accuracy as acc

ROOT = Path(__file__).resolve().parents[1]
BOTH = ("matches_graded", "pct_1x2", "decisive_n", "decisive_correct", "pct_decisive")
RECORD_ONLY = ("correct", "draws", "baseline_home_correct", "baseline_home_pct", "more_than_home")
PAGE_KEY = {"matches_graded": "n"}


def _agg(club_n, club_c, draws, base_c=None, all_n=None, all_pct=None, by_model=True):
    dec_n = club_n - draws
    a = {"updated_at": "2026-11-07T09:55:07+00:00",
         "all_time": {"n": all_n or club_n + 56, "correct_1x2": club_c + 35,
                      "pct_1x2": all_pct if all_pct is not None
                      else round((club_c + 35) / (club_n + 56), 4)}}
    if by_model:
        club = {"n": club_n, "correct_1x2": club_c, "pct_1x2": round(club_c / club_n, 4),
                "draw_n": draws, "decisive_n": dec_n, "decisive_correct": club_c,
                "pct_decisive": round(club_c / dec_n, 4), "logged_with_timestamp": club_n}
        if base_c is not None:
            club["baseline_home"] = {"n": club_n, "correct": base_c,
                                     "pct": round(base_c / club_n, 4)}
        a["by_model"] = {"club": club}
    return a


def _ctx(agg: dict) -> dict:
    return {"acc_club": b._club_block((agg.get("by_model") or {}).get("club")),
            "acc_head": acc.public_headline(agg),
            "acc_n": (agg.get("all_time") or {}).get("n"),
            "acc_pct_1x2": ((agg.get("all_time") or {}).get("pct_1x2") or 0) * 100,
            # Yksi liigarivi: by_comp_html ei renderoi mitaan ilman riveja (tuotannossa aina on).
            "by_comp": [{"code": "PL", "name": "Premier League", "n": 91, "correct": 41,
                         "pct": 45.05, "dec_n": 66, "dec_correct": 41, "pct_dec": 62.12,
                         "draw_n": 25}]}


def _fpl_html(agg: dict) -> str:
    """/fpl:n track record -lauseet SAMALLA funktiolla jolla build_fpl_page kirjoittaa ne."""
    body = "".join(f"<p>{s}</p>\n" for s in b.track_record_sentences(_ctx(agg)))
    return f'<html><body><section id="track-record">{body}</section></body></html>'


def _record_html(agg: dict) -> str:
    """Record-sivun karki + by-comp-summarivi SAMOILLA funktioilla kuin predictions.html."""
    c = _ctx(agg)
    if not c["acc_club"]:
        return "<html><body><section id=\"record\"></section></body></html>"
    return (f'<html><body><section id="record">{b.record_head_html(c)}'
            f"{b.by_comp_html(c)}</section></body></html>")


def _pages(agg: dict, record=True, fpl=True) -> dict:
    pages = {}
    if record:
        pages["track_record"] = {"url": rs.URL["track_record"], "gw": None,
                                 "rows": ps.record_table(_record_html(agg)) or {}}
    if fpl:
        pages["track_record_fpl"] = {"url": rs.URL["track_record_fpl"], "gw": None,
                                     "rows": ps.track_record_sentence(_fpl_html(agg)) or {}}
    return pages


TILAT = [
    pytest.param(_agg(1011, 538, 236, base_c=452), id="7.11-tuotanto"),
    pytest.param(_agg(40, 21, 9, base_c=17), id="pieni-otos"),
    pytest.param(_agg(12345, 6500, 3000, base_c=5600), id="viisinumeroinen"),
    pytest.param(_agg(1000, 500, 250, base_c=450), id="tasaluku-50%"),
    pytest.param(_agg(932, 484, 210, base_c=420, all_n=988, all_pct=0.5253),
                 id="all_time-eri-kuin-seuramalli"),
]


@pytest.mark.parametrize("agg", TILAT)
def test_record_sivu_nayttaa_jokaisen_moduulin_luvun(agg):
    rows = ps.record_table(_record_html(agg)) or {}
    sec = rs.track_record(agg, None)
    for k in BOTH + RECORD_ONLY:
        assert k in sec["values"], f"moduulista puuttuu {k}"
        page = rows.get(PAGE_KEY.get(k, k))
        assert page is not None, f"lukija ei loyda lukua {k} record-sivun HTML:sta"
        assert rm.norm_text(page) == rm.norm_text(sec["values"][k]["text"]), (k, page)


@pytest.mark.parametrize("agg", TILAT)
def test_fpl_varareitti_nayttaa_yhteiset_luvut(agg):
    rows = ps.track_record_sentence(_fpl_html(agg)) or {}
    sec = rs.track_record(agg, None)
    for k in BOTH:
        page = rows.get(PAGE_KEY.get(k, k))
        assert page is not None, f"lukija ei loyda lukua {k} /fpl:n lauseesta"
        assert rm.norm_text(page) == rm.norm_text(sec["values"][k]["text"]), (k, page)


@pytest.mark.parametrize("agg", TILAT)
def test_moduuli_lukee_otsikkoluvun_ei_all_timea(agg):
    head = acc.public_headline(agg)
    v = rs.track_record(agg, None)["values"]
    assert v["matches_graded"]["text"] == str(head["n"])
    assert v["pct_1x2"]["text"] == head["pct_text"]


@pytest.mark.parametrize("agg", TILAT)
def test_ensisijainen_reitti_on_record_sivu_ja_bsky_gate_hyvaksyy_linkin(agg):
    """Botin ohje: track_record linkittaa /predictions#record. Luvun sivun on oltava sama."""
    pages = _pages(agg)
    for k, v in rs.track_record(agg, None)["values"].items():
        url, err, _route = rm.verify_value(v, pages, 0, k)
        assert err is None and url == rs.URL["track_record"], (k, err, url)
        assert gate.page_of(url) == gate.page_of("/predictions#record")


def test_record_sivun_puuttuessa_fpl_on_varareitti():
    agg = _agg(1011, 538, 236, base_c=452)
    pages = _pages(agg, record=False)
    for k in BOTH:
        url, err, _ = rm.verify_value(rs.track_record(agg, None)["values"][k], pages, 0, k)
        assert err is None and url == rs.URL["track_record_fpl"], (k, err)


def test_ilman_perustasoa_kotivertailun_lukuja_ei_ole():
    agg = _agg(1011, 538, 236)
    v = rs.track_record(agg, None)["values"]
    assert not any(k in v for k in ("baseline_home_correct", "baseline_home_pct", "more_than_home"))
    rows = ps.record_table(_record_html(agg)) or {}
    assert "baseline_home_pct" not in rows and rows.get("n") == "1011"


def test_vanha_skeema_ei_anna_seuramallin_lukuja():
    """Ilman by_modelia sivut nayttavat kaikkien kilpailujen lukuja: botti ei saa
    kutsua sita seuramallin luvuksi, joten 1X2-arvoja ei ole lainkaan."""
    agg = _agg(1011, 538, 236, by_model=False)
    v = rs.track_record(agg, None)["values"]
    assert not any(k in v for k in BOTH + RECORD_ONLY)
    assert ps.track_record_sentence(_fpl_html(agg)) is None
    assert ps.record_table(_record_html(agg)) is None


def test_committed_artefakti_kulkee_saman_reitin():
    """Sama ketju committattua data/accuracy.json:ia vasten (tuotannon skeema)."""
    agg = json.loads((ROOT / "data" / "accuracy.json").read_text(encoding="utf-8"))
    if not ((agg.get("by_model") or {}).get("club") or {}).get("n"):
        pytest.skip("artefaktissa ei seuramallin lohkoa")
    test_record_sivu_nayttaa_jokaisen_moduulin_luvun(agg)
    test_fpl_varareitti_nayttaa_yhteiset_luvut(agg)
    test_ensisijainen_reitti_on_record_sivu_ja_bsky_gate_hyvaksyy_linkin(agg)


def test_fetch_surfaces_hakee_record_sivun_ja_jasentaa_sen():
    """Kytkenta, ei vain lukija: generaattorin oma sivuhaku vie track_recordin
    record-sivulle ja /fpl-varareitin /fpl:lle (fake fetch, ei verkkoa)."""
    from types import SimpleNamespace
    agg = _agg(1011, 538, 236, base_c=452)
    html = {"https://goaliq.app/predictions": _record_html(agg),
            "https://goaliq.app/fpl": _fpl_html(agg)}
    asked = []

    def fake(url):
        asked.append(url)
        return SimpleNamespace(status=200, fetched_at="2026-11-07T12:00:00Z",
                               html=html.get(url, "<html></html>"))

    pages, _meta, errs = rm.fetch_surfaces({"track_record", "track_record_fpl"}, 10, fetch=fake)
    assert "https://goaliq.app/predictions" in asked
    assert pages["track_record"]["url"] == "https://goaliq.app/predictions#record"
    assert pages["track_record"]["rows"]["baseline_home_correct"] == "452"
    assert pages["track_record_fpl"]["rows"]["n"] == "1011"
    for k, v in rs.track_record(agg, None)["values"].items():
        url, err, _ = rm.verify_value(v, pages, 10, k)
        assert err is None and url == "https://goaliq.app/predictions#record", (k, err)
