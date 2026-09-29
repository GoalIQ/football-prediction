# -*- coding: utf-8 -*-
"""XP-HORISONTIN-ALKU (29.9.2026): ennustepinnat kesken kierroksen.

xP-artefaktin `gameweeks[]` alkaa kesken olevasta kierroksesta
(next_gameweek), koska rate_team, h2h ja rival tarvitsevat sen. Kartoitus
29.9 loysi kuusi ENNUSTEpintaa jotka lukivat raakarivit ja nayttaisivat
kesken GW6:n (deadline_gameweek 7) lukitun kierroksen tulevana:
  - fpl_planner.captain_picker (/api/fantasy/captain, mobiilin FantasyEdge)
  - api/fantasy_edge captain_top5 (/api/fantasy/edge, SPA EdgeMode + mobiili)
  - render_model_xi ("... over GW6-GW11 (6 gameweeks)" GW7-11:n summalle)
  - build_fpl_why.player_facts ("..., with ARS (H) ... to come", GW6:n vastustaja)
  - fpl_xp.driver_facts / attach_why ("Fixtures"-ajuri GW6:sta)
Yksikaan testi ei kattanut niita: vaihetestit mittasivat vain
`_player_gameweeks`, `_playable_gws` ja `actionable_gameweek`.

Saanto 6a kohta 3: sama kutsupaikka ajetaan synteettisilla vaiheilla:
ennen deadlinea (next 6, dl 6), kesken kierroksen (next 6, dl 7) ja
negatiivinen kontrolli (projektio ei kata dl-kierrosta -> kuluva).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest

from src.models import fpl_planner as pl

BEFORE = (6, 6)      # (next_gameweek, deadline_gameweek)
LIVE = (6, 7)


# ---------------------------------------------------------------------------
# 1. Kapteeni: captain_picker (kutsupaikka build_contextin kautta)
# ---------------------------------------------------------------------------

def _cap_pool(gws=(6, 7, 8)):
    """GW6-kuningas ja GW7-kuningas + taytteet: jarjestys paljastaa kierroksen."""
    def row(i, name, xp6, xp7):
        return {"id": i, "web_name": name, "team_short": "T%d" % i,
                "owned_pct": 30.0, "element_type": 3,
                "gameweeks": [{"gw": g, "xp": {6: xp6, 7: xp7}.get(g, 1.0)} for g in gws]}
    pool = [row(1, "GW6king", 9.0, 2.0), row(2, "GW7king", 3.0, 8.0)]
    pool += [row(10 + k, f"F{k}", 1.0, 1.0) for k in range(10)]
    return pool


def _run_captain(monkeypatch, phase, gws=(6, 7, 8)):
    nxt, dl = phase
    pool = _cap_pool(gws)
    xp_data = {"meta": {"next_gameweek": nxt, "deadline_gameweek": dl,
                        "generated_at": "2026-10-10T12:00:00Z"}, "players": pool}
    by_id = {p["id"]: p for p in pool}
    monkeypatch.setattr(pl, "build_context", lambda: (xp_data, {}, pool, by_id))
    monkeypatch.setattr(pl, "resolve_squad",
                        lambda *a, **k: ([p["id"] for p in pool], None, 0, nxt))
    monkeypatch.setattr(pl, "clamp_gw_to_projections", lambda gw, pool_, xp: gw)
    monkeypatch.setattr(pl, "optimal_xi", lambda squad: squad[:11])
    monkeypatch.setattr(pl, "apply_availability_gate", lambda xi, boot: (xi, []))
    return pl.captain_picker(entry=1)


def test_kapteeni_ennen_deadlinea_kuluva(monkeypatch):
    out = _run_captain(monkeypatch, BEFORE)
    assert out["meta"]["gw"] == 6
    assert out["top3"][0]["web_name"] == "GW6king"


def test_kapteeni_kesken_kierroksen_deadline_kierros(monkeypatch):
    out = _run_captain(monkeypatch, LIVE)
    assert out["meta"]["gw"] == 7
    assert out["top3"][0]["web_name"] == "GW7king"
    assert out["top3"][0]["gw_xp"] == 8.0


def test_kapteeni_ilman_kattavuutta_pysyy(monkeypatch):
    """NEGATIIVINEN KONTROLLI: projektio ei kata GW7:aa -> kuluva kierros."""
    out = _run_captain(monkeypatch, LIVE, gws=(6,))
    assert out["meta"]["gw"] == 6


# ---------------------------------------------------------------------------
# 2. Kapteeni: /api/fantasy/edge (kutsupaikka endpointin kautta)
# ---------------------------------------------------------------------------

@pytest.fixture()
def edge_client(monkeypatch):
    from fastapi.testclient import TestClient
    import api.fantasy_edge as fe
    import api.main as m

    def make(phase, gws=(6, 7, 8)):
        nxt, dl = phase
        pool = _cap_pool(gws)
        for p in pool:
            p["xp_horizon_total"] = sum(g["xp"] for g in p["gameweeks"])
            p["price"] = 60
        xp_data = {"meta": {"next_gameweek": nxt, "deadline_gameweek": dl,
                            "generated_at": "2026-10-10T12:00:00Z"}, "players": pool}
        by_id = {p["id"]: p for p in pool}
        monkeypatch.setattr(fe, "build_context", lambda: (xp_data, {}, pool, by_id))
        monkeypatch.setattr(fe, "_fetch_fpl", lambda path: {"summary_overall_rank": 1000})
        monkeypatch.setattr(fe, "resolve_squad",
                            lambda *a, **k: ([p["id"] for p in pool], None, 0, nxt))
        monkeypatch.setattr(fe, "clamp_gw_to_projections", lambda gw, pool_, xp: gw)
        monkeypatch.setattr(fe, "optimal_xi", lambda squad: squad[:11])
        monkeypatch.setattr(fe, "apply_availability_gate", lambda pool_, boot: (pool_, []))
        monkeypatch.setattr(fe, "is_premium_request", lambda request: True)
        return TestClient(m.app)
    return make


def test_edge_kesken_kierroksen_deadline_kierros(edge_client):
    r = edge_client(LIVE).get("/api/fantasy/edge?entry=1&mode=protect")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["meta"]["gw"] == 7
    rows = d.get("captain_top5") or d.get("captain") or []
    assert rows and rows[0]["web_name"] == "GW7king", rows[:2]


def test_edge_ennen_deadlinea_kuluva(edge_client):
    d = edge_client(BEFORE).get("/api/fantasy/edge?entry=1&mode=protect").json()
    assert d["meta"]["gw"] == 6
    rows = d.get("captain_top5") or d.get("captain") or []
    assert rows[0]["web_name"] == "GW6king"


# ---------------------------------------------------------------------------
# 3. /fpl/model-xi: ikkuna vaikutettavista kierroksista
# ---------------------------------------------------------------------------

def test_model_xi_ikkuna_kesken_kierroksen():
    from tests.test_model_xi_window_and_role import _nakyva, _xp as mxi_xp
    from scripts.build_fpl_longtail import render_model_xi
    xp = mxi_xp(list(range(6, 12)))
    xp["meta"].update({"next_gameweek": 6, "deadline_gameweek": 7})
    html = render_model_xi(xp, datetime(2026, 10, 10, 18, tzinfo=timezone.utc))
    nakyva = _nakyva(html)
    assert "GW7-GW11" in nakyva and "5 gameweeks" in nakyva, nakyva[:400]
    assert "GW6-GW11" not in html


def test_model_xi_ennen_deadlinea_koko_lista():
    from tests.test_model_xi_window_and_role import _nakyva, _xp as mxi_xp
    from scripts.build_fpl_longtail import render_model_xi
    xp = mxi_xp(list(range(6, 12)))
    xp["meta"].update({"next_gameweek": 6, "deadline_gameweek": 6})
    nakyva = _nakyva(render_model_xi(xp, datetime(2026, 10, 9, 8, tzinfo=timezone.utc)))
    assert "GW6-GW11" in nakyva and "6 gameweeks" in nakyva


# ---------------------------------------------------------------------------
# 4. WHY: player_facts (build_fpl_why) ja driver_facts / attach_why
# ---------------------------------------------------------------------------

def _why_player():
    opp = {6: "ARS", 7: "CHE", 8: "LIV", 9: "MCI"}
    return {"id": 1, "web_name": "A", "team": "T", "pos": "MID", "price": 8.0,
            "owned_pct": 10.0, "xmins": 85, "p_start": 0.9, "xp_horizon_total": 20.0,
            "gameweeks": [{"gw": g, "xp": 5.0, "opponents": [{"opp": opp[g], "venue": "H"}]}
                          for g in (6, 7, 8, 9)]}


def test_why_faktat_alkavat_vaikutettavasta():
    from scripts.build_fpl_why import player_facts
    f = player_facts(_why_player(), 7, 3)
    assert f["next_opponents"][0].startswith("CHE"), f["next_opponents"]
    assert not any(o.startswith("ARS") for o in f["next_opponents"])
    assert "xp_next_3_gws" in f


def test_why_main_horisontti_vaikutettavista():
    """KUTSUPAIKKA: main laskee horisontin actionable_gameweeksilla."""
    import inspect
    import scripts.build_fpl_why as bw
    src = inspect.getsource(bw.main)
    assert "horizon = len(fplgw.actionable_gameweeks(meta, gws)) or len(gws)" in src


def test_driver_facts_fixtures_vaikutettavasta():
    from src.models.fpl_xp import driver_facts
    assert driver_facts(_why_player(), 7)["fixtures"].startswith("CHE")
    # NEGATIIVINEN KONTROLLI: ilman rajausta ensimmainen on GW6:n vastustaja.
    assert driver_facts(_why_player())["fixtures"].startswith("ARS")


@pytest.mark.parametrize("phase,first", [(BEFORE, "ARS"), (LIVE, "CHE")])
def test_attach_why_valittaa_vaikutettavan_kierroksen(phase, first):
    """KUTSUPAIKKA: attach_why lukee meta.deadline_gameweekin."""
    from src.models.fpl_xp import attach_why
    nxt, dl = phase
    payload = {"meta": {"next_gameweek": nxt, "deadline_gameweek": dl},
               "players": [_why_player()]}
    entries = {"1": {"sentence": "S.", "drivers": ["fixtures"], "source": "template"}}
    out = attach_why(payload, entries)
    facts = out["players"][0]["why"]["driver_facts"]
    assert facts["fixtures"].startswith(first), facts
