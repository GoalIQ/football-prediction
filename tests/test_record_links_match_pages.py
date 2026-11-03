# -*- coding: utf-8 -*-
"""Track record -rivit linkittavat oikeaan ottelusivuun (LOYDETTAVYYS-2, 3.11.2026).

TAUSTA. /predictions-sivun record-taulussa oli 3 286 rivia eika yksikaan
linkittanyt mihinkaan, vaikka ottelusivuja oli 3 221. Sivu on haun ainoa
ei-brandi-sisaantulo jolla oli nayttoja, ja ottelusivut olivat sen alla
orpoja.

LUPAUS: rivi linkittaa vain TAMAN ottelun sivuun (kilpailu + koti + vieras +
paiva). Samalla parilla on monta ottelua eri kausina, ja vain myohempi saa
paivasuffiksin, joten parista johdettu slug osoittaisi vaaraan otteluun.
Vaara linkki on pahempi kuin ei linkkia.

YKSI LUKIJA: linkit tulevat `build_prediction_pages.published_match_pages`ista,
joka kayttaa samaa `load_feed` + `page_rows` + `match_page_path` -ketjua kuin
sivujen kirjoitus (CLAUDE.md 6a kohta 1).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from html import unescape

import pytest

from scripts import build_prediction_pages as bpp
from scripts import build_fpl_page as bfp
from src.models import accuracy as acc

CTX = {"acc_pending": 0, "by_comp": []}
ROW = re.compile(r'<tr data-comp="([^"]+)">(.*?)</tr>', re.S)
HREF = re.compile(r'<td class="team"><a href="([^"]+)">(.*?)</a></td>')
TEAM = re.compile(r'<td class="team">(?:<a [^>]*>)?(.*?)(?:</a>)?</td>')


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(bpp, "OUT_ROOT", tmp_path / "predictions")
    monkeypatch.setattr(bpp, "SITEMAP_PRED_PATH", tmp_path / "sitemap.xml")
    monkeypatch.setattr(bpp, "PREDICTIONS_HTML", tmp_path / "none.html")
    monkeypatch.setattr(bpp, "LLMS_TXT", tmp_path / "llms.txt")
    monkeypatch.setattr(bpp, "_deploy_file_count", lambda: 1)
    return tmp_path


def _rows(html: str) -> list[dict]:
    """Record-taulun rivit: kilpailu, ensimmainen solu (paiva/kickoff),
    ottelusolun teksti ja linkki."""
    out = []
    for comp, body in ROW.findall(html):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", body, re.S)
        m = HREF.search(body)
        out.append({
            "comp": comp,
            "first": unescape(re.sub(r"<[^>]+>", "", cells[0])),
            "team": unescape(TEAM.search(body).group(1)),
            "href": m.group(1) if m else None,
        })
    return out


def _page_match(path) -> tuple[str, str, str]:
    """(kickoff-paiva, koti, vieras) sivun omasta SportsEvent-JSON-LD:sta."""
    html = path.read_text(encoding="utf-8")
    for blk in re.findall(r'<script type="application/ld\+json">\n(.*?)\n</script>',
                          html, re.S):
        d = json.loads(blk)
        if d.get("@type") == "SportsEvent":
            return (d["startDate"][:10], d["homeTeam"]["name"], d["awayTeam"]["name"])
    raise AssertionError(f"{path}: ei SportsEvent-lohkoa")


def _assert_links_hit_written_pages(html: str, out_root) -> int:
    """Jokainen href osuu builderin kirjoittamaan sivuun, ja sivun ottelu on
    rivin ottelu (paiva + joukkueet). Palauttaa linkkien maaran."""
    rows = [r for r in _rows(html) if r["href"]]
    hrefs = [r["href"] for r in rows]
    # Kaksi rivia samaan sivuun = ainakin toinen on vaaran ottelun linkki.
    assert len(hrefs) == len(set(hrefs)), "kaksi record-rivia samaan ottelusivuun"
    for r in rows:
        assert r["href"].startswith("/predictions/"), r
        f = out_root.parent / (r["href"].lstrip("/") + ".html")
        assert f.exists(), f"linkki ilman sivua: {r['href']}"
        day, home, away = _page_match(f)
        assert r["team"] == f"{home} v {away}", (r, home, away)
        # Gradatun rivin ensimmainen solu on paiva, pending-rivin kickoff.
        assert r["first"][:10] == day, (r, day)
    return len(rows)


# ---------------------------------------------------------------------------
# 1. Oikea loki: builder kirjoittaa sivut, record linkittaa niihin
# ---------------------------------------------------------------------------
def test_jokainen_record_linkki_osuu_kirjoitettuun_saman_ottelun_sivuun(
        sandbox, monkeypatch):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    log = acc.load_log()
    monkeypatch.setattr(bpp.acc, "load_log", lambda: json.loads(json.dumps(log)))
    assert bpp.main(now) == 0
    written = {p.relative_to(sandbox / "predictions").as_posix()
               for p in (sandbox / "predictions").rglob("*.html")
               if p.name != "index.html"}
    html = bfp.record_table_html(log["predictions"], CTX, now)
    n = _assert_links_hit_written_pages(html, sandbox / "predictions")
    rows = _rows(html)
    linked_files = {r["href"][len("/predictions/"):] + ".html" for r in rows if r["href"]}
    # Kaikki linkit osuvat kirjoitettuihin; ja jokainen kirjoitettu sivu jonka
    # ottelu on recordissa saa linkin (ei hiljaa puuttuvia).
    assert linked_files <= written
    in_record = {e.get("match_id") for e in log["predictions"]
                 if acc.counts_in_record(e) or acc.is_pending(e)}
    pages = bpp.published_match_pages(log, now)
    expected = {p["file"] for mid, p in pages.items() if mid in in_record}
    assert linked_files == expected and n == len(expected) > 0
    # 3.11 mitattu: 3 221 / 3 277 datarivista (loput 56 ovat MM-riveja,
    # joilla ei ole ottelusivua).
    print(f"record-rivit {len(rows)}, linkitettyja {n}")
    assert all(r["href"] is None for r in rows if r["comp"] == "WC")


def test_reader_ei_muuta_kutsujan_lokia():
    now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
    log = {"predictions": [_e("m1", 2)]}
    before = json.dumps(log, sort_keys=True)
    bpp.published_match_pages(log, now)
    assert json.dumps(log, sort_keys=True) == before


# ---------------------------------------------------------------------------
# 2. Erottelevat kontrollit synteettisella lokilla
# ---------------------------------------------------------------------------
NOW = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
RESULT = {"home_score": 2, "away_score": 1, "actual_outcome": "home",
          "actual_score": "2-1", "hit_1x2": True, "duration": "REGULAR",
          "reconciled_at": "2026-01-01T00:00:00+00:00"}


def _e(mid, days, result=None, home="Arsenal FC", away="Chelsea FC", comp="PL",
       now=NOW, **kw):
    ko = now + timedelta(days=days)
    e = {"match_id": mid, "competition": comp, "home_team": home, "away_team": away,
         "kickoff": ko.strftime("%Y-%m-%dT%H:%M:%SZ"), "date": ko.strftime("%Y-%m-%d"),
         "p_home": 0.55, "p_draw": 0.25, "p_away": 0.20, "predicted_winner": "home",
         "logged_at": (ko - timedelta(days=3)).isoformat(), "result": result}
    e.update(kw)
    return e


def _synthetic_log(now=NOW):
    return {"predictions": [
        # Sama pari kahtena kautena: vanha pitaa perusslugin, uusi saa paivan.
        _e("old", -300, RESULT, now=now),
        _e("new", 5, now=now),
        # Siirretty ottelu: kickoff 10 vrk sitten, ei tulosta, ei void -> ei sivua.
        _e("postponed", -10, home="Everton FC", away="Fulham FC", now=now),
        # MM: ei ottelusivuja.
        _e("wc", -20, RESULT, home="Spain", away="Argentina", comp="WC", now=now),
        # Ilman match_id:ta ei tunnistetta -> ei linkkia (fail-closed).
        _e("", 3, home="Leeds United", away="Brentford FC", now=now),
        # Nayttonimikartta (PD): linkki ja teksti nayttonimella.
        _e("pd1", 4, home="FC Barcelona", away="Elche CF", comp="PD", now=now),
    ]}


def test_synteettinen_loki_linkit_osuvat_omiin_sivuihin(sandbox, monkeypatch):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    log = _synthetic_log(now)
    monkeypatch.setattr(bpp, "_attach_confidence", lambda by_comp: 1)
    monkeypatch.setattr(bpp.acc, "load_log", lambda: json.loads(json.dumps(log)))
    assert bpp.main(now) == 0
    html = bfp.record_table_html(log["predictions"], CTX, now)
    assert _assert_links_hit_written_pages(html, sandbox / "predictions") == 3
    by_team = {}
    for r in _rows(html):
        by_team.setdefault(r["team"], []).append(r)
    old_new = sorted(by_team["Arsenal FC v Chelsea FC"], key=lambda r: r["first"])
    # Vanha ottelu -> perusslug, uusi -> paivasuffiksi. Ei ristiin.
    assert old_new[0]["href"] == "/predictions/premier-league/arsenal-fc-vs-chelsea-fc"
    assert old_new[1]["href"] == (
        "/predictions/premier-league/arsenal-fc-vs-chelsea-fc-"
        + (now + timedelta(days=5)).strftime("%Y-%m-%d"))
    assert by_team["Everton FC v Fulham FC"][0]["href"] is None
    assert by_team["Spain v Argentina"][0]["href"] is None
    assert by_team["Leeds United v Brentford FC"][0]["href"] is None
    assert by_team["Barcelona v Elche"][0]["href"] == "/predictions/la-liga/barcelona-vs-elche"


def test_vaara_paiva_tai_joukkue_ei_saa_linkkia(monkeypatch):
    """Erotteleva kontrolli: lukijan kartta osoittaa samalla match_id:lla
    eri ottelun (paiva tai joukkue eri) -> ei linkkia.
    MUTAATIO: poista tunnistetarkistus `_record_match_cell`ista -> punainen."""
    import scripts.build_prediction_pages as real
    log = {"predictions": [_e("new", 5)]}
    good = real.published_match_pages(log, NOW)
    assert bfp._record_match_cell(log["predictions"][0], good).startswith(
        '<td class="team"><a href="/predictions/premier-league/arsenal-fc-vs-chelsea-fc"')
    for change in ({"date": "2025-08-17"}, {"home_team": "Everton FC"},
                   {"competition": "ELC"}):
        bad = {"new": {**good["new"], **change}}
        cell = bfp._record_match_cell(log["predictions"][0], bad)
        assert cell == '<td class="team">Arsenal FC v Chelsea FC</td>', (change, cell)
    # Tuntematon match_id -> ei linkkia.
    assert "<a " not in bfp._record_match_cell(_e("muu", 5), good)


def test_pelkat_pelatut_kilpailu_saa_eri_sivut_samalle_parille():
    """Kauden loppu: kilpailussa ei tulevia, vain pelattuja. Ennen 3.11
    `load_feed` antoi tiedostonimen vain tulevien kilpailuille, joten saman
    parin kaksi pelattua ottelua saivat saman URLin.
    MUTAATIO: palauta `for comp, rows in upcoming.items()` -> punainen."""
    log = {"predictions": [_e("a", -300, RESULT), _e("b", -2, RESULT)]}
    pages = bpp.published_match_pages(log, NOW)
    assert pages["a"]["path"] != pages["b"]["path"]
    assert pages["b"]["path"].endswith((NOW - timedelta(days=2)).strftime("%Y-%m-%d"))


def test_linkki_on_yksi_a_elementti_solussa():
    """DOM oli jo 33 146 elementtia: vain yksi <a> soluun, ei kaareita."""
    html = bfp.record_table_html(_synthetic_log()["predictions"], CTX, NOW)
    for body in (b for _, b in ROW.findall(html)):
        cell = re.search(r'<td class="team">(.*?)</td>', body).group(1)
        assert len(re.findall(r"<[a-z]", cell)) <= 1, cell
