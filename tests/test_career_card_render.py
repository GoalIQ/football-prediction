# -*- coding: utf-8 -*-
"""Portti: career.html:n KORTTI ajetaan, ei grepata.

TAUSTA (7.9.2026, portin 17. kierros). Kortin haarat oli vartioitu
merkkijonotesteilla ("lahteessa lukee `points_net`"), ja nelja mutaatiota
selvisi koko 3 200 testin sarjasta: `if (skipped.length)` poistettuna,
`no_final_gw_yet`-haara poistettuna, chip-suodatin poistettuna. Kortti on
tuotteen julkisin pinta, koska kuva irtoaa sovelluksesta ja jaa elamaan
ilman meita.

Tama harness ajaa `drawCard`in Nodella ja lukee mita `statBlock` saa -
eli mita kortille TODELLA kirjoitetaan. Ks. muistit
`portti-joka-etsii-merkkijonoa-ei-mittaa-arvoa` ja
`jakokortti-verifioi-kuvana`.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "js" / "career_card_harness.js"
PAGE = ROOT / "career.html"

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node puuttuu tasta ymparistosta")


def _render(payload: dict) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as fh:
        json.dump(payload, fh)
        polku = fh.name
    try:
        r = subprocess.run(["node", str(HARNESS), str(PAGE), polku],
                           capture_output=True, text=True, timeout=60)
    finally:
        Path(polku).unlink(missing_ok=True)
    assert r.returncode == 0, f"harness kaatui:\n{r.stderr}"
    return json.loads(r.stdout)


def _arvo(out: dict, label: str) -> str:
    for b in out["blocks"]:
        if b["label"].lower() == label.lower():
            return b["value"]
    raise AssertionError(f"korttiin ei piirretty lohkoa {label!r}: "
                         f"{[b['label'] for b in out['blocks']]}")


def _payload(**yli) -> dict:
    p = {
        "manager": {"name": "Test Manager", "team_name": "Test XI",
                    "since": 2019},
        "past_seasons": [{"season": "2024/25", "points": 2210, "rank": 120000}],
        "summary": {"seasons_played": 2, "all_time_points": 2210,
                    "all_time_provisional": False, "best_rank": 120000,
                    "avg_rank": 120000, "since": 2019,
                    "best_season": {"season": "2024/25", "points": 2210,
                                    "rank": 120000},
                    "provisional_gws_excluded": []},
        "latest_season": {"available": True, "total_points": 149,
                          "best_gw": {"gw": 3, "points": 70, "points_net": 62},
                          "overall_rank": 500000, "chips_used": []},
    }
    for k, v in yli.items():
        if isinstance(v, dict) and isinstance(p.get(k), dict):
            p[k] = {**p[k], **v}
        else:
            p[k] = v
    return p


def test_harness_toimii_ja_piirtaa_perustilan():
    """NEGATIIVINEN KONTROLLI koko harnessille: jos tama on tyhja, kaikki
    muut testit ovat vihreita tyhjyyden takia."""
    out = _render(_payload())
    assert len(out["blocks"]) >= 4, out["blocks"]
    assert _arvo(out, "All-time points") == "2,210"


def test_kortti_nayttaa_parhaan_kierroksen_NETTONA():
    """M-kierros 16: mutaatio `points_net` -> `points` lapaisi 3 213 testia.
    70 on brutto, 62 netto; lukijan oma FPL-sivu sanoo 62."""
    out = _render(_payload())
    tama = _arvo(out, "This season")
    assert "62" in tama, tama
    assert "70" not in tama, tama


def test_kesken_oleva_kierros_sanotaan_kortilla():
    """M11b: `if (skipped.length)` poistettuna kortti nayttti summan
    selittamatta miksi se eroaa lukijan omasta FPL-sivusta."""
    out = _render(_payload(summary={"provisional_gws_excluded": [3]}))
    assert "GW3 still being scored" in _arvo(out, "This season")
    # Kontrolli: ilman kesken olevaa kierrosta lauseketta EI ole.
    puhdas = _render(_payload())
    assert "still being scored" not in _arvo(puhdas, "This season")


def test_kolme_saatavuustilaa_ovat_kolme_eri_lausetta():
    """M12b + portin 17. kierros B3. `available=False` tarkoitti kolmea eri
    asiaa, ja kortti sanoi kaikissa "New season - Starts GW1"."""
    kesken = _render(_payload(latest_season={
        "available": False, "season_state": "no_final_gw_yet"}))
    assert _arvo(kesken, "This season") == "Not final yet"

    tuntematon = _render(_payload(latest_season={
        "available": False, "season_state": "unconfirmed"}))
    assert _arvo(tuntematon, "This season") == "Not confirmed"

    esikausi = _render(_payload(latest_season={
        "available": False, "season_state": "not_started"}))
    assert _arvo(esikausi, "New season") == "Starts GW1"


def test_vajaa_uran_summa_merkitaan_labeliin():
    """Portin 17. kierros B4: uran summa ei saa nayttaa taydelliselta kun
    kuluvan kauden panos on 0."""
    out = _render(_payload(summary={"all_time_provisional": True}))
    assert _arvo(out, "All-time points (confirmed)") == "2,210"
    # Kontrolli: ilman lippua label on tavallinen.
    assert _arvo(_render(_payload()), "All-time points") == "2,210"
