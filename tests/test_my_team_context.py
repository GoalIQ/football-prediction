"""MY-TEAM-CONTEXT (3.9.2026): entry-konteksti tyokaluille jotka eivat ennen
lukeneet joukkuetta (GK rotation pairs, price watch, replacements,
differentials, compare).

Kolme vaitetta per tyokalu:
  (a) ilman entrya vastaus on IDENTTINEN vanhaan (negatiivinen kontrolli:
      ei uusia avaimia riveilla eika metassa),
  (b) entryn kanssa uudet kentat ovat oikein,
  (c) negatiivinen kontrolli aritmetiikalle (esim. budjetti vaarin pain
      kaataa affordable-lipun).

Hermeettinen: jaettu _mock_fpl-fixture (entry 424242 -> SQUAD_IDS, bank 1.5m),
GK-parit synteettisella poolilla + phase0:lla, resolve_squad monkeypatchattu
fpl_my_team-moduulista. Ei verkkoa.
"""
from __future__ import annotations

import copy

import pytest

import src.models.fpl_my_team as mt
import src.models.fpl_planner as pl
import src.models.fpl_price_watch as pw
import src.models.fpl_rate_team as rt
from src.models import fpl_value as fv
from tests.test_fpl_rate_team import (  # noqa: F401 — _mock_fpl-fixture kayttoon
    SQUAD_IDS, _mock_fpl,
)
from tests.test_fpl_value import _ctx, _phase0, _pool_player


# ---------------------------------------------------------------------------
# squad_context: fail-safe
# ---------------------------------------------------------------------------

def test_squad_context_none_without_entry_or_players():
    assert mt.squad_context({}, None, None) is None


def test_squad_context_entry_ok():
    ctx = mt.squad_context(rt.get_bootstrap(), 424242)
    assert ctx["available"] is True
    assert ctx["ids"] == set(SQUAD_IDS)
    assert ctx["bank_tenths"] == 15
    assert ctx["gw"] == 1
    meta = mt.squad_meta(ctx)
    assert meta["bank"] == 1.5 and meta["entry"] == 424242


def test_squad_context_entry_error_is_fail_safe(monkeypatch):
    """Esikausi-404 / vaara id ei saa kaataa tyokalua joka toimi ilman entrya."""
    def boom(*a, **k):
        raise rt.RateTeamError(404, "Entry 1 has no picks for GW1.")
    monkeypatch.setattr(mt, "resolve_squad", boom)
    ctx = mt.squad_context({}, 1)
    assert ctx["available"] is False and ctx["ids"] == set()
    assert "no picks" in ctx["note"]
    assert mt.squad_meta(ctx)["available"] is False


# ---------------------------------------------------------------------------
# GK rotation pairs
# ---------------------------------------------------------------------------

def _gk_fixture():
    pool = [
        _pool_player(11, "KeeperA", "ARS", 1, 55, 10.0, [5, 5]),
        _pool_player(13, "KeeperB", "MCI", 1, 50, 9.0, [4, 5]),
        _pool_player(14, "KeeperC", "TOT", 1, 45, 8.0, [4, 4]),
        _pool_player(20, "Outfield", "ARS", 3, 80, 20.0, [3, 3]),
    ]
    teams = [
        {"short": "ARS", "fixtures": [{"gw": 1, "cs_pct": 60.0},
                                      {"gw": 2, "cs_pct": 30.0}]},
        {"short": "MCI", "fixtures": [{"gw": 1, "cs_pct": 20.0},
                                      {"gw": 2, "cs_pct": 50.0}]},
        {"short": "TOT", "fixtures": [{"gw": 1, "cs_pct": 25.0},
                                      {"gw": 2, "cs_pct": 25.0}]},
    ]
    return pool, teams


def test_gk_pairs_without_squad_identical_to_before(monkeypatch):
    """(a) Negatiivinen kontrolli: ilman squadia vastaus on entinen — ei
    own_pair-avainta, ei transfers_needed/affordable riveilla, ei meta.squad."""
    pool, teams = _gk_fixture()
    monkeypatch.setattr(fv, "build_context", lambda: _ctx(pool))
    monkeypatch.setattr(fv, "load_phase0", lambda: _phase0(teams))
    out = fv.gk_rotation_pairs(top_n=3)
    assert "own_pair" not in out
    assert "squad" not in out["meta"] and "own_budget" not in out["meta"]
    assert set(out["meta"]) == {"available", "gw", "horizon_gw", "note"}
    for r in out["pairs"]:
        assert set(r) == {"avg_best_cs_pct", "combined_price", "gk_a", "gk_b",
                          "gw_split"}, r.keys()
    # Vanha golden: ARS+MCI avg 55, hinta 10.5, jarjestys ennallaan
    best = out["pairs"][0]
    assert {best["gk_a"]["team_short"], best["gk_b"]["team_short"]} == {"ARS", "MCI"}
    assert best["avg_best_cs_pct"] == pytest.approx(55.0)
    assert best["combined_price"] == pytest.approx(10.5)


def test_gk_pairs_common_gw_weighting(monkeypatch):
    """Pari jolla on 1/2 yhteista kierrosta ei voita paria jolla on 2/2,
    vaikka sen keskiarvo olisi korkeampi. `common_gws` nakyy vain lyhyella."""
    pool = [
        _pool_player(11, "KeeperA", "ARS", 1, 55, 10.0, [5, 5]),
        _pool_player(13, "KeeperB", "MCI", 1, 50, 9.0, [4, 5]),
        _pool_player(14, "KeeperC", "TOT", 1, 45, 8.0, [4, 4]),
    ]
    teams = [
        {"short": "ARS", "fixtures": [{"gw": 1, "cs_pct": 40.0},
                                      {"gw": 2, "cs_pct": 40.0}]},
        {"short": "MCI", "fixtures": [{"gw": 1, "cs_pct": 40.0},
                                      {"gw": 2, "cs_pct": 40.0}]},
        # TOT: vain GW1 (blank GW2) mutta 90 % -> pelkalla keskiarvolla
        # ARS+TOT (90) voittaisi ARS+MCI:n (40). Painotettuna 45 < 40? ei:
        # 90 * 1/2 = 45 > 40. Siksi TOT 70: 70 * 1/2 = 35 < 40.
        {"short": "TOT", "fixtures": [{"gw": 1, "cs_pct": 70.0}]},
    ]
    monkeypatch.setattr(fv, "build_context", lambda: _ctx(pool))
    monkeypatch.setattr(fv, "load_phase0", lambda: _phase0(teams))
    out = fv.gk_rotation_pairs(top_n=5)
    assert out["meta"]["horizon_gw"] == 2
    best = out["pairs"][0]
    assert {best["gk_a"]["team_short"], best["gk_b"]["team_short"]} == {"ARS", "MCI"}
    assert "common_gws" not in best, "taysi kattavuus: sama luku joka rivilla"
    short = [r for r in out["pairs"]
             if "TOT" in (r["gk_a"]["team_short"], r["gk_b"]["team_short"])]
    assert short and all(r["common_gws"] == 1 for r in short)
    # Raaka keskiarvo sailyy rehellisena rivilla (70 > 40) — rankkaus painottaa
    assert short[0]["avg_best_cs_pct"] == pytest.approx(70.0)
    assert "scaled by how many of the horizon gameweeks" in out["meta"]["note"]


def _squad(ids, bank_tenths, available=True, entry=424242):
    return {"available": available, "entry": entry, "ids": set(ids),
            "bank_tenths": bank_tenths, "gw": 1, "note": None}


def test_gk_pairs_own_pair_transfers_and_affordable(monkeypatch):
    """(b) own_pair samalla kaavalla, transfers_needed 0/1/2, affordable =
    combined <= omat vahdit + bank. (c) bank pienemmaksi -> affordable kaatuu."""
    pool, teams = _gk_fixture()
    monkeypatch.setattr(fv, "build_context", lambda: _ctx(pool))
    monkeypatch.setattr(fv, "load_phase0", lambda: _phase0(teams))
    # Oma pari: KeeperB (MCI 5.0) + KeeperC (TOT 4.5) = 9.5m, bank 0.5 -> 10.0
    out = fv.gk_rotation_pairs(top_n=5, squad=_squad([13, 14, 20], 5))
    own = out["own_pair"]
    assert own is not None
    assert {own["gk_a"]["team_short"], own["gk_b"]["team_short"]} == {"MCI", "TOT"}
    # MCI+TOT: gw1 max(20,25)=25, gw2 max(50,25)=50 -> 37.5 (sama kaava)
    assert own["avg_best_cs_pct"] == pytest.approx(37.5)
    assert own["common_gws"] == 2 and own["transfers_needed"] == 0
    assert own["affordable"] is True
    assert own["rank"] == 3 and own["of"] == 3  # huonoin kolmesta
    assert out["meta"]["own_budget"] == pytest.approx(10.0)
    assert out["meta"]["squad"]["available"] is True
    by = {frozenset((r["gk_a"]["team_short"], r["gk_b"]["team_short"])): r
          for r in out["pairs"]}
    ars_mci = by[frozenset(("ARS", "MCI"))]   # 10.5m, KeeperA puuttuu
    ars_tot = by[frozenset(("ARS", "TOT"))]   # 10.0m, KeeperA puuttuu
    mci_tot = by[frozenset(("MCI", "TOT"))]   # oma
    assert mci_tot["transfers_needed"] == 0 and mci_tot["affordable"] is True
    assert ars_tot["transfers_needed"] == 1 and ars_tot["affordable"] is True
    assert ars_mci["transfers_needed"] == 1 and ars_mci["affordable"] is False
    # Kumpikaan vahti ei omassa rungossa -> 2
    out2 = fv.gk_rotation_pairs(top_n=5, squad=_squad([20], 200))
    assert all(r["transfers_needed"] == 2 for r in out2["pairs"])
    assert out2["own_pair"] is None
    assert "fewer than two of your keepers" in out2["meta"]["own_pair_note"]
    # (c) negatiivinen kontrolli: bank 0 -> 10.0m pari ei ole enaa varaa
    out3 = fv.gk_rotation_pairs(top_n=5, squad=_squad([13, 14, 20], 0))
    by3 = {frozenset((r["gk_a"]["team_short"], r["gk_b"]["team_short"])): r
           for r in out3["pairs"]}
    assert by3[frozenset(("ARS", "TOT"))]["affordable"] is False
    assert by3[frozenset(("MCI", "TOT"))]["affordable"] is True


def test_gk_pairs_squad_unavailable_keeps_list_and_explains(monkeypatch):
    pool, teams = _gk_fixture()
    monkeypatch.setattr(fv, "build_context", lambda: _ctx(pool))
    monkeypatch.setattr(fv, "load_phase0", lambda: _phase0(teams))
    ctx = {"available": False, "entry": 1, "ids": set(), "bank_tenths": 0,
           "gw": None, "note": "Entry 1 has no picks for GW1."}
    out = fv.gk_rotation_pairs(top_n=5, squad=ctx)
    assert out["own_pair"] is None
    assert out["meta"]["squad"]["available"] is False
    assert "no picks" in out["meta"]["squad"]["note"]
    assert "own_budget" not in out["meta"]
    assert len(out["pairs"]) == 3
    assert all("transfers_needed" not in r for r in out["pairs"])


def test_value_and_gk_entry_adds_owned_flag_and_fail_safe(monkeypatch):
    pool, teams = _gk_fixture()
    monkeypatch.setattr(fv, "build_context", lambda: _ctx(pool))
    monkeypatch.setattr(fv, "load_phase0", lambda: _phase0(teams))
    monkeypatch.setattr(fv, "squad_context",
                        lambda boot, entry, players=None: _squad([11, 20], 30))
    out = fv.value_and_gk(top_n_value=10, top_n_pairs=5, entry=424242)
    owned = {r["id"]: r["owned"] for r in out["players"]}
    assert owned[11] is True and owned[20] is True and owned[13] is False
    assert out["meta"]["squad"]["bank"] == 3.0
    assert "own_pair" in out["gk"]
    # Ilman entrya: ei owned-lippua, ei squad-metaa
    plain = fv.value_and_gk(top_n_value=10, top_n_pairs=5)
    assert all("owned" not in r for r in plain["players"])
    assert "squad" not in plain["meta"] and "own_pair" not in plain["gk"]


def test_value_endpoint_with_entry(client, monkeypatch):
    """Endpoint: entry 424242 (mock) -> squad = SQUAD_IDS (GK 1 ja 2, bank 1.5).
    POOL_PLAYERS team_short = C01.. -> phase0 samoilla koodeilla."""
    teams = [{"short": f"C{i:02d}", "fixtures": [{"gw": 1, "cs_pct": 30.0 + i}]}
             for i in range(1, 5)]
    monkeypatch.setattr(fv, "load_phase0", lambda: _phase0(teams))
    r = client.get("/api/fantasy/value?top_n=5&pairs_n=6&entry=424242")
    assert r.status_code == 200
    b = r.json()
    assert b["meta"]["squad"]["available"] is True
    assert b["meta"]["squad"]["bank"] == 1.5
    own = b["gk"]["own_pair"]
    assert own is not None
    assert {own["gk_a"]["id"], own["gk_b"]["id"]} == {1, 2}
    assert own["transfers_needed"] == 0
    for p in b["gk"]["pairs"]:
        assert p["transfers_needed"] in (0, 1, 2)
        assert isinstance(p["affordable"], bool)
    # Ilman entrya taysin entinen muoto
    b0 = client.get("/api/fantasy/value?top_n=5&pairs_n=6").json()
    assert "squad" not in b0["meta"] and "own_pair" not in b0["gk"]
    assert all("transfers_needed" not in p for p in b0["gk"]["pairs"])
    # Vaara entry -> 200, lista sailyy, meta selittaa
    b1 = client.get("/api/fantasy/value?top_n=5&pairs_n=6&entry=1").json()
    assert b1["meta"]["squad"]["available"] is False
    assert b1["gk"]["own_pair"] is None and b1["gk"]["pairs"]


def test_value_endpoint_players_mode(client, monkeypatch):
    teams = [{"short": f"C{i:02d}", "fixtures": [{"gw": 1, "cs_pct": 30.0 + i}]}
             for i in range(1, 5)]
    monkeypatch.setattr(fv, "load_phase0", lambda: _phase0(teams))
    ids = ",".join(str(i) for i in SQUAD_IDS)
    b = client.get(f"/api/fantasy/value?pairs_n=6&players={ids}").json()
    assert b["meta"]["squad"]["available"] is True
    assert b["gk"]["own_pair"]["transfers_needed"] == 0
    assert client.get("/api/fantasy/value?players=1,x").status_code == 400


# ---------------------------------------------------------------------------
# Price watch
# ---------------------------------------------------------------------------

def _pw_payload():
    return {
        "meta": {"available": True, "generated_at": "t", "disclaimer": "d",
                 "official_projection": True},
        "risers": [
            {"id": 15, "web_name": "P15", "now_cost": 7.0, "status": "rising_soon",
             "confidence": 1.0, "progress_pct": 100.0, "net_event": 1,
             "already_changed_today": False, "eta_days": 0},
            {"id": 30, "web_name": "P30", "now_cost": 7.5, "status": "rising_watch",
             "confidence": 0.5, "progress_pct": 60.0, "net_event": 1,
             "already_changed_today": False, "eta_days": 2},
        ],
        "fallers": [
            {"id": 5, "web_name": "P5", "now_cost": 5.0, "status": "falling_soon",
             "confidence": 1.0, "progress_pct": 100.0, "net_event": -1,
             "already_changed_today": False, "eta_days": 0},
            {"id": 25, "web_name": "P25", "now_cost": 7.5, "status": "falling_watch",
             "confidence": 0.4, "progress_pct": 40.0, "net_event": -1,
             "already_changed_today": False},
        ],
    }


def test_price_watch_annotate_owned_unit():
    out = pw.annotate_owned(_pw_payload(), set(SQUAD_IDS))
    assert [r["owned"] for r in out["risers"]] == [True, False]
    assert [r["owned"] for r in out["fallers"]] == [True, True]
    o = out["owned"]
    assert o["n_rising"] == 1 and o["n_falling"] == 2
    assert o["n_tonight"] == 2                      # 15 ja 5 eta 0; 25 ilman etaa
    assert [x["web_name"] for x in o["falling"]] == ["P5", "P25"]
    assert o["squad_size"] == 15


def test_price_watch_endpoint_with_and_without_entry(client, monkeypatch):
    monkeypatch.setattr(pw, "load_price_watch", lambda *a, **k: _pw_payload())
    # (a) ilman entrya: ei owned-lohkoa eika owned-lippua riveilla
    b0 = client.get("/api/fantasy/price-watch").json()
    assert "owned" not in b0 and "squad" not in b0["meta"]
    assert all("owned" not in r for r in b0["risers"] + b0["fallers"])
    # (b) entryn kanssa
    b = client.get("/api/fantasy/price-watch?entry=424242").json()
    assert b["meta"]["squad"]["available"] is True
    assert b["owned"]["n_rising"] == 1 and b["owned"]["n_falling"] == 2
    assert b["owned"]["n_tonight"] == 2
    # (c) vaara entry -> lista sailyy, meta selittaa, ei owned-lohkoa
    b1 = client.get("/api/fantasy/price-watch?entry=1").json()
    assert b1["meta"]["squad"]["available"] is False
    assert "owned" not in b1 and len(b1["risers"]) == 2


# ---------------------------------------------------------------------------
# Differentials
# ---------------------------------------------------------------------------

def test_differentials_without_squad_identical():
    out = pl.differential_finder(max_ownership=10.0)
    assert "template_missing" not in out and "squad" not in out["meta"]
    assert all("owned" not in p for p in out["players"])


def test_differentials_with_squad_excludes_owned_and_lists_template():
    # Runko: kaikki 40 %:n template-pelaajat PAITSI DEF 6 ja MID 16; lisaksi
    # 5 %:n pelaajia 9, 19 (differentiaaleja jotka jo omistetaan).
    squad = _squad([1, 2, 5, 7, 8, 9, 10, 15, 17, 18, 19, 20, 25, 26, 27], 15)
    out = pl.differential_finder(max_ownership=10.0, squad=squad)
    ids = [p["id"] for p in out["players"]]
    assert 9 not in ids and 19 not in ids, "omistettu ei ole differentiaali sinulle"
    assert out["meta"]["owned_excluded"] == 9   # DEF 7-10, MID 17-20, FWD 27 (EO 5 %)
    assert all(p["owned"] is False for p in out["players"])
    tm = [p["id"] for p in out["template_missing"]]
    assert set(tm) == {6, 16}
    assert all(p["owned_pct"] == 40.0 for p in out["template_missing"])
    assert out["meta"]["squad"]["available"] is True
    # Vertailukontrolli: ilman squadia 9 ja 19 OVAT listalla
    assert 9 in [p["id"] for p in pl.differential_finder(max_ownership=10.0)["players"]]
    # crowd_backs kantaa owned-lipun mutta ei suodatu (omistettu template
    # jota malli ei rankkaa on juuri se tieto omistajalle)
    for p in out["model_vs_crowd"]["crowd_backs"]:
        assert "owned" in p


def test_differentials_template_missing_is_empty_when_you_own_the_template():
    """Tiukempi kuin edge: alle 20 % ei ole template -> tyhja lista, ei
    ensimmaista 5 %:n pelaajaa 'template'-nimella."""
    squad = _squad(SQUAD_IDS, 15)   # omistaa kaikki 40 %:n pelaajat
    out = pl.differential_finder(max_ownership=10.0, squad=squad)
    assert out["template_missing"] == []


def test_differentials_endpoint_entry(client):
    b = client.get("/api/fantasy/differentials?max_ownership=10&entry=424242").json()
    assert b["meta"]["squad"]["entry"] == 424242
    assert all(p["id"] not in SQUAD_IDS for p in b["players"])
    assert "template_missing" in b
    b0 = client.get("/api/fantasy/differentials?max_ownership=10").json()
    assert "template_missing" not in b0


# ---------------------------------------------------------------------------
# Replacements
# ---------------------------------------------------------------------------

def test_replacements_without_squad_identical():
    out = pl.replacements(20, gws=5)
    assert "squad" not in out["meta"] and "budget" not in out["meta"]
    assert [r["id"] for r in out["players"]] == [15, 16, 17, 18, 19]
    assert out["meta"]["price_max"] == 7.5


def test_replacements_with_squad_budget_and_owned_excluded():
    """Lahtija 20 rungossa, bank 1.5 -> budjetti 8.5m; omistetut 15, 16 pois."""
    squad = _squad([20, 15, 16], 15)
    out = pl.replacements(20, gws=5, squad=squad)
    assert out["meta"]["target_owned"] is True
    assert out["meta"]["budget"] == pytest.approx(8.5)
    assert out["meta"]["price_max"] == pytest.approx(8.5)
    assert out["meta"]["price_min"] == pytest.approx(6.5)   # alaraja ennallaan
    assert out["meta"]["owned_excluded"] == 2
    ids = [r["id"] for r in out["players"]]
    assert 15 not in ids and 16 not in ids
    assert ids == [17, 18, 19, 21, 22]
    assert "bank plus P20's current price (8.5m)" in out["meta"]["budget_note"]
    # (c) negatiivinen kontrolli: budjetti alle lahtijan hinnan (bank 0,
    # lahtijan hinta 7.0) -> price_max 7.0, ei 7.5
    out0 = pl.replacements(20, gws=5, squad=_squad([20], 0))
    assert out0["meta"]["price_max"] == pytest.approx(7.0)
    assert out0["meta"]["budget"] == pytest.approx(7.0)


def test_replacements_target_not_in_squad_keeps_bracket():
    squad = _squad([15, 16], 15)
    out = pl.replacements(20, gws=5, squad=squad)
    assert out["meta"]["target_owned"] is False
    assert out["meta"]["budget"] is None
    assert out["meta"]["price_max"] == 7.5
    assert "not in your squad" in out["meta"]["budget_note"]
    assert [r["id"] for r in out["players"]] == [17, 18, 19, 21, 22]


def test_replacements_endpoint_entry_and_mask_keeps_meta(client, monkeypatch):
    b = client.get("/api/fantasy/replacements?player=20&entry=424242").json()
    assert b["meta"]["target_owned"] is False      # 20 ei SQUAD_IDS:ssa
    assert b["meta"]["owned_excluded"] == 5        # 15-19
    assert [r["id"] for r in b["players"]] == [21, 22, 23, 24]
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    bm = client.get("/api/fantasy/replacements?player=20&entry=424242").json()
    assert bm["meta"]["masked"] is True and len(bm["players"]) == 1
    assert bm["meta"]["squad"]["available"] is True   # maski ei syo metaa
    monkeypatch.setenv("PREMIUM_ENFORCE", "off")


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------

def test_compare_owned_flag_only_with_squad():
    plain = pl.compare_players([15, 24])
    assert all("owned" not in r for r in plain["players"])
    assert "squad" not in plain["meta"]
    out = pl.compare_players([15, 24], squad=_squad(SQUAD_IDS, 15))
    owned = {r["id"]: r["owned"] for r in out["players"]}
    assert owned == {15: True, 24: False}
    assert out["meta"]["squad"]["entry"] == 424242
    # Verdict ei muutu omistuksesta
    assert out["verdict"] == plain["verdict"]


def test_compare_endpoint_entry(client):
    b = client.get("/api/fantasy/compare?players=15,24&entry=424242").json()
    assert [r["owned"] for r in b["players"]] == [True, False]
    b1 = client.get("/api/fantasy/compare?players=15,24&entry=1").json()
    assert b1["meta"]["squad"]["available"] is False
    assert all("owned" not in r for r in b1["players"])
