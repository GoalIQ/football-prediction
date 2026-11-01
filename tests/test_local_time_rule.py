# -*- coding: utf-8 -*-
"""Yksi aikavyohykesaanto hubille ja SPA:lle (ulkoasuohjelma WP2, 1.11.2026).

MITATTU 1.11: hub "Next deadline: Gameweek 10, 6 November at 18:30 UTC" ja
ottelusivu "Sun 01 Nov 2026, 16:30 UTC"; SPA "Fri 6 Nov, 20:30 EET" ja
Fixtures pelkka "18:30". Sama hetki nakyi kahtena eri aikana.

Saanto (src/local_time.py): staattinen HTML kantaa UTC:n nimettyna (oikein
ilman JS:aa), `<time datetime>` hetken, ja skripti vaihtaa tekstin lukijan
aikaan vyohykkeen nimen kanssa samaan muotoon kuin SPA:n formatDeadline.

Portit: (1) time_tag vaatii UTC-nimen, (2) jokainen generaattori kayttaa
time_tagia (deadline, ottelusivu, liigahub, etusivun ottelutaulukko,
longtailin deadline) ja sivulla on skripti, (3) skripti tuottaa Nodessa
Helsingin ajassa "Fri 6 Nov, 20:30 EET" ja jattaa UTC:n title-attribuuttiin.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess

import pytest

from src import local_time as LT

DL = dt.datetime(2026, 11, 6, 18, 30, tzinfo=dt.timezone.utc)


def test_time_tag_vaatii_utc_nimen_ja_kantaa_hetken():
    t = LT.time_tag(DL, "6 November at 18:30 UTC")
    assert t == ('<time datetime="2026-11-06T18:30:00Z" data-giq-local>'
                 "6 November at 18:30 UTC</time>")
    with pytest.raises(ValueError):
        LT.time_tag(DL, "6 November at 18:30")
    # Naiivi aika tulkitaan UTC:ksi, ei rakentajan paikallisajaksi.
    assert 'datetime="2026-11-06T18:30:00Z"' in LT.time_tag(DL.replace(tzinfo=None), "x UTC")


def test_fpl_deadline_rivi_ja_skripti():
    from scripts import build_fpl_page as b
    c = {"deadlines": [{"gw": 10, "utc": "2026-11-06T18:30:00+00:00"},
                       {"gw": 11, "utc": "2026-11-21T11:00:00+00:00"}], "cs_gw": 10}
    rivi = b._deadline_row(c)
    assert ('Next deadline: Gameweek 10, <time datetime="2026-11-06T18:30:00Z" '
            'data-giq-local>6 November at 18:30 UTC</time>.') in rivi
    # Sama kierros kuin taulukossa, ei listan ensimmainen.
    assert "Gameweek 11" in b._deadline_row({**c, "cs_gw": 11})


def test_generoitu_fpl_sivu_kantaa_skriptin():
    from pathlib import Path
    html = (Path(__file__).resolve().parents[1] / "fpl.html").read_text(encoding="utf-8")
    assert re.search(r'Next deadline: Gameweek \d+, <time datetime="[^"]+Z" data-giq-local>', html)
    assert LT.LOCAL_TIME_JS in html


def test_ottelusivu_ja_liigahub_kayttavat_saantoa():
    from scripts import build_prediction_pages as bpp
    html = bpp._kickoff_html("2026-11-01T16:30:00Z")
    assert html == ('<time datetime="2026-11-01T16:30:00Z" data-giq-local>'
                    "Sun 01 Nov 2026, 16:30 UTC</time>")
    # Vahvistamaton aika (00:00-paikkamerkki) jaa tekstiksi.
    assert "<time" not in bpp._kickoff_html("2026-11-01T00:00:00Z")
    sivu = bpp._page("t", "d", "https://goaliq.app/x", "<h1>x</h1>" + html, "<p>y</p>", [])
    assert LT.LOCAL_TIME_JS in sivu
    # Ilman lokalisoitavaa aikaa ei turhaa skriptia.
    assert LT.LOCAL_TIME_JS not in bpp._page("t", "d", "https://goaliq.app/x", "<h1>x</h1>", "<p>y</p>", [])


def test_ottelusivun_ja_liigahubin_kutsupaikat():
    """KUTSUPAIKAT: oikea ottelusivu ja liigahubin rivi, ei vain apufunktio."""
    from scripts import build_prediction_pages as bpp
    e = {"home_team": "Liverpool", "away_team": "Arsenal", "kickoff": "2026-11-01T16:30:00Z",
         "p_home": 0.25, "p_draw": 0.29, "p_away": 0.46, "competition": "PL",
         "match_id": "x1", "logged_at": "2026-10-31T09:00:00+00:00"}
    tag = '<time datetime="2026-11-01T16:30:00Z" data-giq-local>Sun 01 Nov 2026, 16:30 UTC</time>'
    rivi = bpp._hub_row(bpp.LEAGUES["PL"], e, False)
    # WP11: hubin rivin paiva on ryhman otsikossa, joten UTC-varateksti on lyhyt;
    # sama elementti ja sama skripti (selaimessa sama muoto kuin muualla).
    assert '<time datetime="2026-11-01T16:30:00Z" data-giq-local>16:30 UTC</time>' in rivi
    sivu = bpp.render_match_page("PL", e, dt.datetime(2026, 10, 31, 12, tzinfo=dt.timezone.utc))
    assert f"kickoff {tag}" in sivu
    assert LT.LOCAL_TIME_JS in sivu


def test_etusivun_ottelutaulukko_kayttaa_saantoa():
    from scripts import build_fpl_page as b
    src = b.next_matches_block.__code__.co_names
    assert "time_tag" in src and "local_time_script" in src
    assert "Kick-off UTC" not in open(b.__file__, encoding="utf-8").read()


def _node_run(tz: str, html_text: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node puuttuu")
    stub = (
        "var els=[{a:{datetime:'2026-11-06T18:30:00Z'},title:'',textContent:%s,"
        "getAttribute:function(k){return this.a[k];}}];"
        "global.document={readyState:'complete',querySelectorAll:function(){return els;},"
        "addEventListener:function(){}};"
        "%s\n"
        "process.stdout.write(JSON.stringify({text:els[0].textContent,title:els[0].title}));"
    ) % (json.dumps(html_text), LT.LOCAL_TIME_JS)
    env = {**os.environ, "TZ": tz}
    out = subprocess.run([node, "-e", stub], capture_output=True, text=True, env=env, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_skripti_lokalisoi_kuten_spa():
    r = _node_run("Europe/Helsinki", "6 November at 18:30 UTC")
    assert r == {"text": "Fri 6 Nov, 20:30 EET", "title": "6 November at 18:30 UTC"}
    r = _node_run("Europe/London", "6 November at 18:30 UTC")
    assert r["text"] == "Fri 6 Nov, 18:30 GMT"
