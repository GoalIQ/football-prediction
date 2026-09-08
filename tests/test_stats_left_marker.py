"""Portti: /fpl/stats-taulukko merkitsee status 'u' -pelaajat "(left)".

TAUSTA (8.9.2026, jono STATS-LEFT-MERKINTA): status `u` -rivilla ei ollut
merkintaa taulukossa, joten liigasta lahtenyt pelaaja nayttaa samalta kuin
aktiivinen. Sarake on datassa (scripts/build_fpl_stats.py: COLS sisaltaa
"status") mutta fpl/stats.html:n renderi ei lukenut sita ollenkaan.

Ajaa OIKEAN client-JS:n (paint()/draw()) nodella, ei grep-tarkistusta
merkkijonolle (muisti: `portti-joka-etsii-merkkijonoa-ei-mittaa-arvoa`).
Sarakejarjestys tulee `build_fpl_stats.COLS`:sta, ei omasta kopiosta, jotta
testi ei voi hiljaa erkaantua julkisesta sarakesopimuksesta.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from scripts.build_fpl_stats import COLS

FP = Path(__file__).resolve().parents[1]
HARNESS = FP / "tests" / "js" / "stats_table_harness.js"
PAGE = FP / "fpl" / "stats.html"

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node puuttuu tasta ymparistosta")

DEFAULTS = {
    "id": 0, "name": "X", "team": "TST", "pos": "MID", "price": 5.0,
    "own": 1.0, "status": "a", "mins": 900, "starts": 10,
    "g": 1, "xg": 1.0, "threat": 100.0, "a": 1, "xa": 1.0, "xgi": 2.0,
    "creativity": 50.0, "tkl": 10, "cbi": 5, "rec": 20, "dc": 15,
    "cs": 2, "gc": 10, "xgc": 10.0, "saves": 0,
    "pts": 50, "ppg": 5.0, "bps": 100, "bonus": 5, "ict": 100.0,
    "yc": 1, "rc": 0, "pen": 0, "cor": 0, "fk": 0,
    "sh": None, "sot": None, "box": None, "head": None, "hvc": None,
    "npxg": None, "spxg": None, "kp": None, "xgchain": None,
    "xgbuildup": None,
}


def _row(**overrides) -> list:
    d = {**DEFAULTS, **overrides}
    return [d[c] for c in COLS]


def _run(rows: list) -> dict:
    payload = {"c": COLS, "r": rows}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as fh:
        json.dump(payload, fh)
        polku = fh.name
    try:
        r = subprocess.run(["node", str(HARNESS), str(PAGE), polku],
                           capture_output=True, text=True, timeout=60,
                           encoding="utf-8")
    finally:
        Path(polku).unlink(missing_ok=True)
    assert r.returncode == 0, f"harness kaatui:\n{r.stderr}"
    return json.loads(r.stdout)


def test_status_u_saa_left_merkinnan() -> None:
    out = _run([_row(id=1, name="Gone", status="u", mins=500)])
    assert "(left)" in out["tbodyHTML"], out["tbodyHTML"]


def test_status_a_ei_saa_left_merkintaa() -> None:
    """Negatiivinen kontrolli: aktiivinen pelaaja ei saa merkintaa."""
    out = _run([_row(id=2, name="Here", status="a", mins=500)])
    assert "(left)" not in out["tbodyHTML"], out["tbodyHTML"]


def test_molemmat_samassa_taulukossa_vain_lahtenyt_merkitaan() -> None:
    out = _run([
        _row(id=1, name="Gone", status="u", mins=500, pts=10),
        _row(id=2, name="Here", status="a", mins=900, pts=90),
    ])
    html = out["tbodyHTML"]
    gone_i = html.find("Gone")
    here_i = html.find("Here")
    assert gone_i != -1 and here_i != -1
    assert html.count("(left)") == 1
    gone_cell_end = html.find("</td>", gone_i)
    assert "(left)" in html[gone_i:gone_cell_end]
