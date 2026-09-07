# -*- coding: utf-8 -*-
"""Portti: uran summan IKKUNASAANTO on kahdessa kielessa, ja ne ajetaan.

TAUSTA (7.9.2026, portin kierrokset 18-21). Sama saanto ("onko luku vajaa, ja
minka ikkunan sisalla se on") elaa kahdessa toteutuksessa:

  * `goaliq-app/lib/careerAllTime.ts` -> `allTimeWindow()`
  * `career.html`:n inline-JS -> `atLabel`-lohko

Kortti ei voi importoida TS-moduulia, joten kopiota ei voi poistaa. Mutta
kaksi kopiota jotka VOIVAT erota eivat ole yksi lukija vaan kaksi lukijaa
joilla on sama tarkoitus - ja ne olivat 21. kierroksella jo eri mielta:
`all_time_through_gw === 0` antoi TS:ssa `gw` (-> "through GW0") ja
kortilla kausi-ikkunan.

Merkkijonovertailu ei kelpaa, koska kielet ovat eri. Siksi MOLEMMAT ajetaan
samalla syotetaululla ja vastauksia verrataan. Sama ratkaisu kuin
`test_shared_reader_parity.py`:ssa: skip kun `goaliq-app` ei ole
checkoutattuna (se on eri, privaatti repo).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

FP = Path(__file__).resolve().parents[1]
APP = FP.parent / "goaliq-app"
HARNESS = FP / "tests" / "js" / "career_card_harness.js"
PARITY = FP / "tests" / "js" / "alltime_parity.mjs"
PAGE = FP / "career.html"

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node puuttuu tasta ymparistosta")

# Syotetaulu. Jokainen rivi on tila jonka backend voi tuottaa, ja mukana ovat
# reunatapaukset joista kopiot ovat kerran jo olleet eri mielta.
SYOTTEET = [
    {"all_time_provisional": False},
    {"all_time_provisional": False, "all_time_through_gw": 2},
    {"all_time_provisional": True, "all_time_through_gw": 2},
    {"all_time_provisional": True, "all_time_through_gw": 38},
    {"all_time_provisional": True, "all_time_through_gw": 1},
    # 🔴 Tasta ne olivat eri mielta 21. kierroksella.
    {"all_time_provisional": True, "all_time_through_gw": 0},
    {"all_time_provisional": True, "all_time_through_gw": 0,
     "all_time_through_season": "2024/25"},
    {"all_time_provisional": True, "all_time_through_gw": None,
     "all_time_through_season": "2024/25"},
    {"all_time_provisional": True, "all_time_through_gw": None,
     "all_time_through_season": None},
    {"all_time_provisional": True},
]


def _tsn_vastaukset() -> list[str]:
    syotteet = [dict(s, all_time_points=2210) for s in SYOTTEET]
    r = subprocess.run(
        ["node", "--experimental-strip-types", "--no-warnings",
         str(PARITY), json.dumps(syotteet)],
        capture_output=True, text=True, timeout=60, cwd=str(FP))
    assert r.returncode == 0, f"parity-harness kaatui:\n{r.stderr}"
    return json.loads(r.stdout)


def _kortin_vastaus(summary: dict) -> str:
    """career.html:n haara samasta syotteesta, luettuna piirretysta
    labelista."""
    payload = {
        "manager": {"name": "T", "team_name": "T", "since": 2019},
        "past_seasons": [{"season": "2024/25", "points": 2210, "rank": 1}],
        "summary": {**{
            "seasons_played": 2, "all_time_points": 2210, "best_rank": 1,
            "avg_rank": 1, "since": 2019, "best_season": None,
            "provisional_gws_excluded": []}, **summary},
        "latest_season": {"available": True, "total_points": 149},
    }
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
    out = json.loads(r.stdout)
    label = next((b["label"] for b in out["blocks"]
                  if b["label"].startswith("All-time points")), None)
    if label is None:
        return "none"
    if " through GW" in label:
        return "gw"
    if " through " in label:
        return "season"
    return "full"


def test_ikkunasaanto_vastaa_samaa_molemmissa_toteutuksissa():
    if not (APP / "lib" / "careerAllTime.ts").exists():
        pytest.skip("goaliq-app ei ole checkoutattuna, pariteettia ei voi ajaa")

    ts = _tsn_vastaukset()
    assert len(ts) == len(SYOTTEET)

    erot = []
    for syote, ts_vastaus in zip(SYOTTEET, ts):
        kortti = _kortin_vastaus(syote)
        if kortti != ts_vastaus:
            erot.append(f"{syote} -> TS {ts_vastaus!r}, kortti {kortti!r}")
    assert not erot, (
        "ikkunasaannon kaksi toteutusta ovat eri mielta:\n  "
        + "\n  ".join(erot))


def test_kontrolli_taulukko_kattaa_kaikki_nelja_tilaa():
    """NEGATIIVINEN KONTROLLI: jos taulukko tuottaisi vain yhta vastausta,
    pariteetti olisi triviaalisti tosi (muisti: kontrolli-lapaisi-tyhjana)."""
    if not (APP / "lib" / "careerAllTime.ts").exists():
        pytest.skip("goaliq-app ei ole checkoutattuna")
    assert set(_tsn_vastaukset()) == {"full", "gw", "season", "none"}
