# -*- coding: utf-8 -*-
"""START-PCT-KAKSOISPYORISTYS (27.8): sama pelaaja, sama Start% joka sivulla.

Julkaisuportti mittasi 27.8 etta Rogers oli 92 % `/fpl/predicted-lineups`- ja
`/fpl/club/chelsea`-sivuilla mutta 91 % `/fpl/expected-points`-sivulla: yksi
polku tulosti jo kerran pyoristetyn `predicted_starts`in (91.5 -> 92), toinen
`p_start*100` (91.47 -> 91). Kumpi tahansa julkaistu luku oli kumottavissa
toisella omalla sivullamme. Tama portti lukee luvut RENDEROIDUISTA sivuista,
ei koodista, ja vaatii ne identtisiksi.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FPL = ROOT / "fpl"


def _sivu(rel: str) -> str:
    p = FPL / rel
    if not p.exists():
        pytest.skip(f"{rel} ei ole rakennettu")
    return p.read_text(encoding="utf-8", errors="replace")


def _teksti(solu: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", solu)).strip()


def _predicted_lineups() -> dict[tuple[str, str], int]:
    """{(slug, nimi): start%} predicted-lineups-sivun seurataulukoista."""
    h = _sivu("predicted-lineups.html")
    out: dict[tuple[str, str], int] = {}
    for m in re.finditer(r'<h2 id="([^"]+)">.*?</h2>\s*<div class="lb-wrap">'
                         r"<table class=\"lb\">(.*?)</table>", h, re.S):
        slug, table = m.group(1), m.group(2)
        for tr in re.findall(r"<tr>(.*?)</tr>", table, re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(tds) < 4:
                continue
            pm = re.search(r"(\d+)%", _teksti(tds[-1]))
            if pm:
                out[(slug, _teksti(tds[0]).rstrip("!").strip())] = int(pm.group(1))
    assert out, "predicted-lineups: yhtaan Start%-rivia ei loytynyt"
    return out


def _club_pages() -> dict[tuple[str, str], int]:
    out: dict[tuple[str, str], int] = {}
    for f in sorted((FPL / "club").glob("*.html")):
        h = f.read_text(encoding="utf-8", errors="replace")
        slug = f.stem
        for tr in re.findall(r"<tr>(.*?)</tr>", h, re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(tds) != 4:
                continue
            last = _teksti(tds[-1])
            pm = re.fullmatch(r"(\d+)%", last)
            if pm:
                out[(slug, _teksti(tds[0]).rstrip("!").strip())] = int(pm.group(1))
    return out


def _expected_points() -> dict[str, int]:
    """{nimi: start%} expected-points-taulukosta (Start%-sarake theadista)."""
    h = _sivu("expected-points.html")
    thead = re.search(r"<thead>(.*?)</thead>", h, re.S)
    assert thead
    ots = [_teksti(t).lower() for t in re.findall(r"<th[^>]*>(.*?)</th>", thead.group(1), re.S)]
    assert "start%" in ots, ots
    j = ots.index("start%")
    nimi_j = ots.index("player")
    out: dict[str, int] = {}
    body = re.search(r"<tbody[^>]*>(.*?)</tbody>", h, re.S).group(1)
    for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) <= max(j, nimi_j):
            continue
        v = _teksti(tds[j])
        if v.isdigit():
            out.setdefault(_teksti(tds[nimi_j]), int(v))
    assert out, "expected-points: Start%-sarake tyhja"
    return out


def test_predicted_lineups_and_club_pages_agree():
    pl = _predicted_lineups()
    club = _club_pages()
    yhteiset = set(pl) & set(club)
    assert len(yhteiset) >= 50, f"liian vahan yhteisia riveja: {len(yhteiset)}"
    erot = {k: (pl[k], club[k]) for k in yhteiset if pl[k] != club[k]}
    assert not erot, f"Start% eroaa predicted-lineups vs club: {erot}"


def test_expected_points_agrees_with_predicted_lineups():
    pl = _predicted_lineups()
    ep = _expected_points()
    # web_name ei ole avain (9 duplikaattia): vertaa vain nimia jotka ovat
    # predicted-lineupsissa tasan kerran.
    laskuri: dict[str, int] = {}
    for (_, n) in pl:
        laskuri[n] = laskuri.get(n, 0) + 1
    pl_by_name = {n: v for (s, n), v in pl.items() if laskuri[n] == 1}
    yhteiset = set(pl_by_name) & set(ep)
    assert len(yhteiset) >= 20, f"liian vahan yhteisia nimia: {len(yhteiset)}"
    erot = {n: (pl_by_name[n], ep[n]) for n in yhteiset if pl_by_name[n] != ep[n]}
    assert not erot, f"Start% eroaa predicted-lineups vs expected-points: {erot}"


def test_start_pct_rounds_half_up_like_math_round():
    """Sama pyoristys kuin SPA:n/mobiilin Math.round: 0.905 -> 91, ei 90."""
    from scripts.build_fpl_longtail import start_pct
    assert start_pct({"p_start": 0.905}) == 91
    assert start_pct({"p_start": 0.9147}) == 91
    assert start_pct({"p_start": 0.915}) == 92
    assert start_pct({"predicted_starts": 91.5}) == 92
    assert start_pct({}) is None
