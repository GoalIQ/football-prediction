# -*- coding: utf-8 -*-
"""Botin 1X2-track record: sivun lause ja moduulin luku samasta lukijasta (7.11.2026).

MITATTU 7.11.2026: Bluesky-botin `track_record`-aihe oli postannut kahdesti,
molemmat kertaa vain xP-virheesta. Syy oli kaksi vikaa paallekkain:

  (1) `public_surface.track_record_sentence` etsi lausetta "Across the N
      completed matches, the model called ... of matches", mutta /fpl on
      sanonut 26.9 alkaen "Across the N completed club matches, it called
      ... of them". Lukija palautti tyhjan, joten 1X2-luvuilla ei ollut
      julkista reittia (public_url None) ja portti hylkasi ne hiljaa.
  (2) Moduulin luku tuli `all_time`sta (53.7 % / 1067, sis. MM-kisojen
      maajoukkuemallin), vaikka jokainen sivu nayttaa seuramallin
      `public_headline`in (53.2 % / 1011).

KORJAUS (CLAUDE.md 6a): moduuli lukee saman `public_headline`in kuin sivut,
ja tama portti ajaa SIVUN OMAN builderin lauseet lukijan lapi. Jos joku
muuttaa lauseen sanamuotoa, lukija lakkaa loytamasta sita ja testi kaatuu
ennen kuin botti hiljenee. Mitataan useassa tilassa (pieni ja iso otos,
tasaluku, all_time eri kuin seuramalli, vanha skeema), ei vain tanaan.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_fpl_page as b
from src.marketing import public_surface as ps
from src.marketing import reply_module as rm
from src.marketing import reply_sections as rs
from src.models import accuracy as acc

ROOT = Path(__file__).resolve().parents[1]
ONE_X_TWO = ("matches_graded", "pct_1x2", "decisive_n", "decisive_correct", "pct_decisive")
PAGE_KEY = {"matches_graded": "n"}


def _agg(club_n, club_c, draws, all_n=None, all_pct=None, by_model=True):
    dec_n = club_n - draws
    a = {"updated_at": "2026-11-07T09:55:07+00:00",
         "all_time": {"n": all_n or club_n + 56, "correct_1x2": club_c + 35,
                      "pct_1x2": all_pct if all_pct is not None
                      else round((club_c + 35) / (club_n + 56), 4)}}
    if by_model:
        a["by_model"] = {"club": {
            "n": club_n, "correct_1x2": club_c, "pct_1x2": round(club_c / club_n, 4),
            "draw_n": draws, "decisive_n": dec_n, "decisive_correct": club_c,
            "pct_decisive": round(club_c / dec_n, 4), "logged_with_timestamp": club_n}}
    return a


def _page_html(agg: dict) -> str:
    """Sivun track record -lauseet SAMALLA funktiolla jolla build_fpl_page kirjoittaa ne."""
    c = {"acc_club": b._club_block((agg.get("by_model") or {}).get("club")),
         "acc_head": acc.public_headline(agg),
         "acc_n": (agg.get("all_time") or {}).get("n"),
         "acc_pct_1x2": ((agg.get("all_time") or {}).get("pct_1x2") or 0) * 100}
    body = "".join(f"<p>{s}</p>\n" for s in b.track_record_sentences(c))
    return f'<html><body><section id="track-record">{body}</section></body></html>'


TILAT = [
    pytest.param(_agg(1011, 538, 236), id="7.11-tuotanto"),
    pytest.param(_agg(40, 21, 9), id="pieni-otos"),
    pytest.param(_agg(12345, 6500, 3000), id="viisinumeroinen"),
    pytest.param(_agg(1000, 500, 250), id="tasaluku-50%"),
    pytest.param(_agg(932, 484, 210, all_n=988, all_pct=0.5253), id="all_time-eri-kuin-seuramalli"),
]


@pytest.mark.parametrize("agg", TILAT)
def test_jokaisella_1x2_luvulla_on_reitti_sivun_omaan_lauseeseen(agg):
    rows = ps.track_record_sentence(_page_html(agg)) or {}
    sec = rs.track_record(agg, None)
    for k in ONE_X_TWO:
        assert k in sec["values"], f"moduulista puuttuu {k}"
        page = rows.get(PAGE_KEY.get(k, k))
        assert page is not None, f"lukija ei loyda lukua {k} builderin lauseesta"
        assert rm.norm_text(page) == rm.norm_text(sec["values"][k]["text"]), (k, page)


@pytest.mark.parametrize("agg", TILAT)
def test_moduuli_lukee_otsikkoluvun_ei_all_timea(agg):
    head = acc.public_headline(agg)
    v = rs.track_record(agg, None)["values"]
    assert v["matches_graded"]["text"] == str(head["n"])
    assert v["pct_1x2"]["text"] == head["pct_text"]


@pytest.mark.parametrize("agg", TILAT)
def test_verify_value_antaa_julkisen_reitin(agg):
    pages = {"track_record": {"url": rs.URL["track_record"], "gw": None,
                              "rows": ps.track_record_sentence(_page_html(agg)) or {}}}
    for k in ONE_X_TWO:
        url, err, route = rm.verify_value(rs.track_record(agg, None)["values"][k], pages, 0, k)
        assert err is None and url == rs.URL["track_record"], (k, err)


def test_vanha_skeema_ei_anna_seuramallin_lukuja():
    """Ilman by_modelia sivu nayttaa kaikkien kilpailujen lauseen: botti ei saa
    kutsua sita seuramallin luvuksi, joten 1X2-arvoja ei ole lainkaan."""
    agg = _agg(1011, 538, 236, by_model=False)
    v = rs.track_record(agg, None)["values"]
    assert not any(k in v for k in ONE_X_TWO)
    assert ps.track_record_sentence(_page_html(agg)) is None


def test_committed_artefakti_kulkee_saman_reitin():
    """Sama ketju committattua data/accuracy.json:ia vasten (tuotannon skeema)."""
    agg = json.loads((ROOT / "data" / "accuracy.json").read_text(encoding="utf-8"))
    if not ((agg.get("by_model") or {}).get("club") or {}).get("n"):
        pytest.skip("artefaktissa ei seuramallin lohkoa")
    test_jokaisella_1x2_luvulla_on_reitti_sivun_omaan_lauseeseen(agg)
