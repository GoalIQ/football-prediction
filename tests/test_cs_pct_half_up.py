# -*- coding: utf-8 -*-
"""/fpl:n clean sheet -prosentti pyoristyy kuten SPA (Math.round / toFixed).

27.9.2026 (julkaisutarkistaja, PRO-JOUKKUENAKYMA): /fpl muotoili ruudukon
solun `format(x, ".0f")`:lla, joka pyoristaa tasapisteen parilliseen. Mitattu
tuotannosta: Arsenal-Leeds GW6 cs_pct 46.5 -> /fpl "46%", kun pron
Teams-nakyma ja uusi joukkuepaneeli nayttavat "47%". Klubisivu linkkaa nyt
paneeliin, joten sama lukija nakee saman ottelun kahdella luvulla.

Yksi muotoilija (`src.models.fmt.fmt_fixed`, ROUND_HALF_UP floatin tarkasta
arvosta = JS toFixed). Portti ajaa renderoijat tasapisteilla ja kieltaa vanhan
muodon lahteesta, jottei uusi CS-solu palaa `.0f`:aan.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_fmt_fixed_rounds_ties_up_like_js():
    from src.models.fmt import fmt_fixed

    assert fmt_fixed(46.5) == "47"
    assert fmt_fixed(45.5) == "46"
    assert fmt_fixed(44.25, 1) == "44.3"
    assert fmt_fixed(44.0, 1) == "44.0", "nollia ei riisuta (vrt. fmt_pct)"
    # Negatiivinen kontrolli: vanha muoto antaa eri luvun juuri tassa.
    assert format(46.5, ".0f") == "46"


def test_grid_cell_and_class_use_half_up():
    from scripts import build_fpl_page as B

    fx = {"gw": 6, "opponent": "Leeds", "opponent_short": "LEE", "venue": "H",
          "fdr": 2, "cs_pct": 46.5}
    c = {"gws": [6], "fdr_rows": [{"team": "Arsenal", "cells": [[fx]],
                                   "n": 1, "avg_cs": 46.5, "avg_fdr": 2.0}]}
    html = B.fdr_grid_html(c)
    assert "LEE (H) 47%" in html
    assert "LEE (H) 46%" not in html


def test_run_and_avg_cells_use_half_up():
    from scripts import build_fpl_page as B

    assert ">45%</span>" in B._run_cell({"run_cs_pct": 44.5, "run_n": 6})
    assert "<strong>44.3%</strong>" in B.avg_cells({"n": 6, "avg_cs": 44.25, "avg_fdr": 2.0})


def test_no_banker_rounding_for_cs_in_source():
    src = (ROOT / "scripts" / "build_fpl_page.py").read_text(encoding="utf-8")
    assert not re.search(r'cs_pct"\]\), "\.0f"\)', src)
    assert "{v:.0f}%</span>" not in src
    assert 'r["avg_cs"]:.1f' not in src
