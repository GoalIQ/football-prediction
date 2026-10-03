# -*- coding: utf-8 -*-
"""Portti: GoalIQ ei hae eika tarjoile UEFAn sisaltoa.

3.10.2026 (Villen paatos): UCL Fantasy lopetettiin, eika GoalIQ hae
UEFAn palveluista mitaan (UCL Fantasy -syote, ottelut, sarjataulukot).

Tama portti tekee paluun mahdottomaksi ilman tietoista paatosta (CLAUDE.md
saanto 6a): (1) koodissa ei ole UEFA-isannan URL-osoitetta, (2) repossa ei
ole UEFA-pohjaista dataa, (3) API ei tarjoile UCL Fantasy -dataa vaikka
tiedosto ilmestyisi levylle, (4) julkiset sivut eivat linkita poistettuihin
/ucl-sivuihin eivatka lupaa UEFAn syotetta.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

UEFA_URL = re.compile(r"https?://(?:[a-z0-9-]+\.)*uefa\.com", re.I)
KOODI = ("api", "src", "scripts", ".github/workflows", "web/pro-spa/src")
PAATTEET = {".py", ".yml", ".yaml", ".ts", ".js", ".svelte", ".sh", ".json"}

KIELLETTY_DATA = ("data/ucl_fantasy.json", "data/ucl_xp_projections.json",
                  "data/uefa_matches/", "data/uefa_lineups/")

JULKISET = ("index.html", "faq.html", "predictions.html", "fpl.html", "spl.html",
            "career.html", "404.html", "llms.txt", "sitemap-core.xml")


def _koodi_tiedostot():
    for juuri in KOODI:
        d = ROOT / juuri
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if f.is_file() and f.suffix in PAATTEET and "node_modules" not in f.parts:
                yield f


def test_regex_tunnistaa_uefa_osoitteet():
    """Negatiivinen kontrolli: poistetut osoitteet olisivat osuneet."""
    for url in ("https://match.uefa.com/v5/matches",
                "https://standings.uefa.com/v1/standings",
                "https://gaming.uefa.com/en/uclfantasy/services/feeds",
                "https://www.uefa.com/termsconditions"):
        assert UEFA_URL.search(url), url
    assert not UEFA_URL.search("match.uefa.com mainitaan kommentissa ilman osoitetta")


def test_koodissa_ei_ole_uefa_osoitteita():
    osumat = []
    n = 0
    for f in _koodi_tiedostot():
        n += 1
        teksti = f.read_text(encoding="utf-8", errors="ignore")
        for i, rivi in enumerate(teksti.splitlines(), 1):
            if UEFA_URL.search(rivi):
                osumat.append(f"{f.relative_to(ROOT)}:{i}: {rivi.strip()[:120]}")
    assert n > 200, f"vain {n} kooditiedostoa luettiin - onko polku rikki?"
    assert not osumat, ("UEFA-osoite koodissa (haku lopetettu 3.10.2026, Villen "
                        "paatos):\n" + "\n".join(osumat))


def test_repossa_ei_ole_uefa_dataa():
    try:
        out = subprocess.run(["git", "ls-files", "data"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError) as e:  # pragma: no cover
        pytest.skip(f"git ei kaytettavissa: {e}")
    assert len(out) > 10, "git ls-files data palautti tuskin mitaan"
    loydot = [p for p in out if any(p == k or p.startswith(k) for k in KIELLETTY_DATA)]
    assert not loydot, f"UEFA-pohjaista dataa repossa: {loydot}"


def test_api_ei_tarjoile_ucl_fantasya_vaikka_tiedosto_olisi(client, monkeypatch, tmp_path):
    """Kutsupaikka: vaikka joku palauttaisi artefaktin levylle, /api/fantasy/xp
    ?league=ucl palauttaa tyhjan rungon (klientin tyhjatila)."""
    from src.models import fpl_xp

    f = tmp_path / "ucl_xp_projections.json"
    f.write_text(json.dumps({"meta": {"available": True, "next_gameweek": 2},
                             "players": [{"id": 1, "name": "X", "xp": 5.0}]}),
                 encoding="utf-8")
    monkeypatch.setitem(fpl_xp.XP_PATHS, "ucl", f)
    r = client.get("/api/fantasy/xp", params={"league": "ucl"})
    assert r.status_code == 200
    d = r.json()
    assert d["meta"]["available"] is False
    assert not d.get("players")


@pytest.mark.parametrize("nimi", JULKISET)
def test_julkinen_sivu_ei_linkita_ucl_sivuihin_eika_lupaa_uefan_syotetta(nimi):
    p = ROOT / nimi
    if not p.exists():
        pytest.skip(f"{nimi} puuttuu tasta puusta")
    h = p.read_text(encoding="utf-8")
    assert 'href="/ucl' not in h and "goaliq.app/ucl" not in h, f"{nimi} linkittaa /ucl-sivuihin"
    assert not re.search(r"UEFA'?s own (public )?(UCL Fantasy )?feed|UEFA feed data", h), \
        f"{nimi} lupaa UEFAn syotetta"
    assert "pro.goaliq.app/ucl" not in h, f"{nimi} mainostaa poistettua UCL Fantasy -osiota"
