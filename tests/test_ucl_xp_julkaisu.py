"""Portti: UCL Fantasyn xP julkaistaan Premiumina samaa polkua kuin FPL.

Villen paatos 21.9.2026: UCL xP on Premium (linja "raakaluvut ilmaiseksi,
malli maksaa"). Kolme asiaa voi kadota hiljaa ja kukin mitataan erikseen:

  1. `/api/fantasy/xp?league=ucl` maskaa ilmaiskayttajalle (top-10 teaser
     kuten FPL); ilman maskia koko Premium-lista menisi ilmaiseksi.
  2. Artefaktin skeema on se jota SPA ja mobiili lukevat (sama kuin FPL/SPL).
  3. ucl-refresh sekä RAKENTAA etta COMMITTAA tiedoston (muisti:
     gw_recap.json oli 7 vrk jaassa koska `git add` puuttui).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
POS = ("GKP", "DEF", "MID", "FWD")
DATA_BASIS = {"domestic_league", "uefa_matches", "no_history"}


def _artefakti(n: int = 14) -> dict:
    pelaajat = []
    for i in range(n):
        xp = 10.0 - i * 0.5
        pelaajat.append({
            "id": 250000000 + i, "web_name": f"P{i}", "full_name": f"Player {i}",
            "team": "Club", "team_short": "CLB", "pos": POS[i % 4], "price": 5.0 + i % 3,
            "owned_pct": 1.0, "status": "a", "news": "", "xmins": 70.0, "p_start": 0.8,
            "data_basis": "domestic_league" if i % 2 else "uefa_matches",
            "xp_per_gw": round(xp / 3, 2), "xp_horizon_total": xp, "xp_next": round(xp / 3, 2),
            "xp_components": {"esiintyminen": 1.5},
            "gameweeks": [{"gw": g, "opponents": [{"opp": "OPP", "venue": "H"}],
                           "xp": round(xp / 3, 2)} for g in (2, 3, 4)],
        })
    return {"meta": {"product": "GoalIQ UCL Fantasy - expected points (xP)", "available": True,
                     "league": "INT-Champions League", "generated_at": "2026-09-21T16:00:00",
                     "deadline_gameweek": 2, "next_gameweek": 2, "current_gameweek": 2,
                     "horizon_gw": 3},
            "players": pelaajat}


@pytest.fixture
def ucl_tiedosto(tmp_path, monkeypatch):
    from src.models import fpl_xp
    p = tmp_path / "ucl_xp_projections.json"
    p.write_text(json.dumps(_artefakti()), encoding="utf-8")
    monkeypatch.setitem(fpl_xp.XP_PATHS, "ucl", p)
    return p


def test_ucl_on_rekisterissa():
    from src.models import fpl_xp
    assert fpl_xp.XP_PATHS["ucl"].name == "ucl_xp_projections.json"


def test_ilmaiskayttaja_saa_vain_teaserin(client, ucl_tiedosto, monkeypatch):
    import api.main as M
    monkeypatch.setattr(M, "is_premium_request", lambda request: False)
    r = client.get("/api/fantasy/xp?league=ucl")
    assert r.status_code == 200
    d = r.json()
    assert d["meta"].get("masked") is True
    assert len(d["players"]) == 10, "top-10 teaser kuten FPL"
    assert all("why" not in p for p in d["players"]), "why on vain FPL:n Premium-kentta"


def test_premium_saa_koko_listan(client, ucl_tiedosto, monkeypatch):
    import api.main as M
    monkeypatch.setattr(M, "is_premium_request", lambda request: True)
    d = client.get("/api/fantasy/xp?league=ucl").json()
    assert not d["meta"].get("masked")
    assert len(d["players"]) == 14
    # Jarjestys summan mukaan (sama sopimus kuin FPL:lla).
    tot = [p["xp_horizon_total"] for p in d["players"]]
    assert tot == sorted(tot, reverse=True)


def test_artefaktin_skeema_on_klienttien_skeema():
    """Rakentaja kirjoittaa kentat joita SPA/mobiili lukevat. Mitataan
    rakentajan omasta koodista (ei verkkoa): kenttalista tuota()-funktiossa."""
    src = (ROOT / "scripts" / "build_ucl_xp.py").read_text(encoding="utf-8")
    for kentta in ("web_name", "team_short", "pos", "price", "owned_pct", "status",
                   "xmins", "p_start", "data_basis", "xp_per_gw", "xp_horizon_total",
                   "xp_next", "gameweeks", "deadline_gameweek", "horizon_gw"):
        assert f'"{kentta}"' in src, kentta
    from scripts.build_ucl_xp import DATA_BASIS as DB, STATUS
    assert set(DB.values()) == DATA_BASIS
    assert set(STATUS.values()) <= {"a", "d", "i", "s", "u"}


def test_workflow_rakentaa_ja_committaa():
    wf = (ROOT / ".github" / "workflows" / "ucl-refresh.yml").read_text(encoding="utf-8")
    assert "python -m scripts.build_ucl_xp" in wf
    assert "git add data/ucl_xp_projections.json" in wf
    assert wf.index("scripts.build_uefa_model") < wf.index("scripts.build_ucl_xp"), \
        "xP lasketaan juuri bakatulla CL-mallilla"


def test_artefakti_ei_ole_gitignoressa():
    import subprocess
    r = subprocess.run(["git", "check-ignore", "-q", "data/ucl_xp_projections.json"],
                       cwd=ROOT, capture_output=True)
    assert r.returncode == 1
