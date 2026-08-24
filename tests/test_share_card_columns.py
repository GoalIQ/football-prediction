# -*- coding: utf-8 -*-
"""JAKOKORTTI: sarakeindeksi on sopimus taulukon kanssa (24.8).

Kortti lukee sivun renderoidun taulukon `td[N]`-indekseilla, jotta se ei voi
nayttaa muuta kuin mita lukija nakee samalla sivulla. Hinta on hiljainen
vikatila: jos taulukon sarakejarjestys muuttuu, kortti ei jaa tyhjaksi vaan
nayttaa VAARAN sarakkeen oikean nakoisena. Kirjattu vastaava tapaus:
julkaistu luku vaarasta sarakkeesta.

Tama testi lukee molemmat puolet renderoidusta HTML:sta - theadin otsikot ja
kortin JS:n indeksit - eika luota kumpaankaan erikseen.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# sivu -> (taulukon valitsin-vihje, {korttikentta: odotettu otsikko})
# Otsikko verrataan pienella ja ilman lajittelunuolia.
CASES = {
    "points": {"name": "player", "team": "team", "tag": "pos",
               "mid": "xp", "value": "pts"},
    "expected-points": {"name": "player", "team": "team", "tag": "pos",
                        "mid": "price", "value": "6gw xp"},
    "xg-leaders": {"name": "player", "team": "team", "tag": "pos",
                   "mid": "xa", "value": "xg"},
}


def _page(nimi: str) -> str:
    p = ROOT / "fpl" / f"{nimi}.html"
    if not p.exists():
        pytest.skip(f"{p.name} ei ole rakennettu tassa puussa")
    return p.read_text(encoding="utf-8", errors="replace")


def _headers(html: str) -> list[str]:
    m = re.search(r"<thead>(.*?)</thead>", html, re.S)
    assert m, "sivulta puuttuu thead"
    ths = re.findall(r"<th[^>]*>(.*?)</th>", m.group(1), re.S)
    out = []
    for t in ths:
        t = re.sub(r"<[^>]+>", "", t)
        out.append(t.replace("▾", "").replace("▴", "").strip().lower())
    return out


def _card_indices(html: str) -> dict[str, int]:
    """Poimii kortin rows.push(...)-lohkosta kenttien td-indeksit."""
    m = re.search(r"rows\.push\(\{rank:rows\.length\+1,(.*?)\}\);", html, re.S)
    assert m, "sivulta puuttuu jakokortin rows.push"
    return {k: int(i) for k, i in re.findall(r"(\w+):\(td\[(\d+)\]", m.group(1))}


@pytest.mark.parametrize("sivu,odotus", CASES.items())
def test_card_reads_the_column_it_names(sivu, odotus):
    html = _page(sivu)
    hdr = _headers(html)
    idx = _card_indices(html)
    for kentta, otsikko in odotus.items():
        assert kentta in idx, f"{sivu}: kortista puuttuu kentta {kentta}"
        i = idx[kentta]
        assert i < len(hdr), f"{sivu}: {kentta} osoittaa sarakkeeseen {i}, otsikoita {len(hdr)}"
        assert hdr[i] == otsikko, (
            f"{sivu}: {kentta} lukee sarakkeen {i} ('{hdr[i]}'), odotettiin "
            f"'{otsikko}'. Taulukon sarakejarjestys on muuttunut - korjaa "
            f"kortin indeksi build_fpl_longtail.py:ssa.")


@pytest.mark.parametrize("sivu", list(CASES))
def test_card_button_and_script_are_both_present(sivu):
    """Negatiivinen kontrolli: pelkka nappi ilman JS:aa on kuollut nappi."""
    html = _page(sivu)
    assert 'id="sharecard"' in html, f"{sivu}: jakonappi puuttuu"
    assert "toBlob" in html, f"{sivu}: kortin renderointi-JS puuttuu"
