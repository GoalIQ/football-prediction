"""PLANNER-FREEZE-DIVERGENCE (28.8.2026): yksi siirtomoottori kaikille pinnoille.

Mitattu 28.8 livesta: freeze, /api/fantasy/plan ja rate-team antoivat samalle
15:lle kolme eri vastausta (White/De Cuyper vs Mendy/Tzolakis vs "hold").
Nama testit lukitsevat sen etta (1) planner ja rate-team ja freeze lukevat
saman moottorin, (2) yhdistelmahaku loytaa "vapauta rahaa ensin" -parin,
(3) luottamuspaino laskee hintapriori-pelaajan todistetun ohi, ja (4) jokaiselle
portille on negatiivinen kontrolli (muisti: gate-substring-osuma-on-sokea).
Hermeettinen: synteettinen pooli, ei verkkoa.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

import src.models.fpl_planner as pl
import src.models.fpl_rate_team as rt
from src.models import fpl_transfers as tr
from tests.test_fpl_rate_team import (  # noqa: F401 - _mock_fpl-fixture
    FAKE_BOOTSTRAP, FAKE_XP, _mock_fpl,
)
from tests.test_fpl_planner import WEAK_SQUAD

ROOT = Path(__file__).resolve().parents[1]


def _p(pid, pos, price, xp, club=None, **extra):
    """Synteettinen poolipelaaja: yksi kierros (gw 2), xp = koko ikkuna."""
    row = {"id": pid, "web_name": f"P{pid}", "team_short": "T", "element_type": pos,
           "club": club if club is not None else pid, "price": price,
           "owned_pct": 1.0, "xp_per_gw": xp, "xp_horizon_total": xp,
           "gameweeks": [{"gw": 2, "opponents": [], "xp": xp}]}
    row.update(extra)
    return row


def _legal_squad(xp=5.0, price=50):
    """2 GK, 5 DEF, 5 MID, 3 FWD; kaikki eri seuroista."""
    squad = []
    pid = 1
    for pos, n in ((1, 2), (2, 5), (3, 5), (4, 3)):
        for _ in range(n):
            squad.append(_p(pid, pos, price, xp))
            pid += 1
    return squad


# ---------------------------------------------------------------------------
# 1. Pariteetti: rate-team, planner ja freeze lukevat saman moottorin
# ---------------------------------------------------------------------------
def test_rate_team_suggestions_come_from_engine():
    squad = _legal_squad()
    pool = squad + [_p(90, 3, 50, 9.0)]
    top = rt.transfer_suggestions(squad, pool, 0)["suggestions"][0]
    eng = tr.single_moves(squad, pool, 0, None, top_k=1)[0]
    assert (top["out"]["id"], top["in"]["id"]) == (eng["out"]["id"], eng["in"]["id"])
    assert top["delta_xp_horizon"] == round(eng["gain"], 2)
    assert top["confidence_weight"] == 1.0
    assert "delta_xp_weighted" in top


def test_planner_first_gw_matches_engine(_mock_fpl):
    out = pl.plan_transfers(players=WEAK_SQUAD, horizon=6, bank=10.0, ft=1)
    _xp, _boot, pool, by_id = rt.build_context()
    squad = [by_id[i] for i in WEAK_SQUAD]
    gws = [g["gw"] for g in out["plan"]]
    step = tr.plan_gw(squad, pool, 100, gws, 1)
    got = [(m["out"]["id"], m["in"]["id"]) for m in out["plan"][0]["transfers"]]
    want = [(m["out"]["id"], m["in"]["id"]) for m in step["moves"]]
    assert got == want
    assert out["meta"]["engine"] == "transfers.v2"  # ei moduulipolkua julkiseen payloadiin
    assert out["meta"]["horizon"] == 6


def _load_freeze():
    spec = importlib.util.spec_from_file_location(
        "freeze_model_squad_gw", ROOT / "scripts" / "freeze_model_squad_gw.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _prev_from(squad):
    rivit = [{"id": p["id"], "web_name": p["web_name"], "pos": p["element_type"],
              "price": p["price"], "club": p["club"]} for p in squad]
    return {"meta": {"budget": 100.0}, "xi": rivit[:11], "bench": rivit[11:]}


def test_freeze_uses_same_engine_as_planner():
    m = _load_freeze()
    squad = _legal_squad()
    pool = squad + [_p(90, 3, 50, 9.0), _p(91, 2, 50, 7.0)]
    out = m._constrained_from_prev(_prev_from(squad), pool, 2, ft=1)
    step = tr.plan_gw(squad, pool, 100 * 10 - 15 * 50, [2], 1,
                      max_moves=max(tr.MAX_TRANSFERS_PER_GW, 1))
    assert [(t["out"], t["in"]) for t in out["transfers"]] == \
        [(mv["out"]["id"], mv["in"]["id"]) for mv in step["moves"]]
    assert out["engine"] == "fpl_transfers.plan_gw"


# ---------------------------------------------------------------------------
# 2. Hit-saanto on yksi: netto >= 0.5
# ---------------------------------------------------------------------------
def test_hit_needs_net_gain_over_min():
    m = _load_freeze()
    squad = _legal_squad()
    # +4.3 brutto: vanha freeze otti hitin (4.3 > 4.0), moottori ei (netto 0.3)
    pool = squad + [_p(90, 3, 50, 9.3)]
    out = m._constrained_from_prev(_prev_from(squad), pool, 2, ft=0)
    assert out["transfers"] == [] and out["hits"] == 0
    # +4.6 brutto -> netto 0.6 >= 0.5 -> hitti otetaan
    pool = squad + [_p(90, 3, 50, 9.6)]
    out = m._constrained_from_prev(_prev_from(squad), pool, 2, ft=0)
    assert [t["in"] for t in out["transfers"]] == [90]
    assert out["hits"] == 1 and out["transfers"][0]["hit"] is True


def test_free_transfer_still_needs_min_gain():
    m = _load_freeze()
    squad = _legal_squad()
    pool = squad + [_p(90, 3, 50, 5.4)]           # +0.4 < 0.5 -> ei siirtoa
    out = m._constrained_from_prev(_prev_from(squad), pool, 2, ft=2)
    assert out["transfers"] == [] and out["ft_left"] == 2
    pool = squad + [_p(90, 3, 50, 5.5)]           # +0.5 -> ilmainen siirto
    out = m._constrained_from_prev(_prev_from(squad), pool, 2, ft=2)
    assert [t["in"] for t in out["transfers"]] == [90]
    assert out["hits"] == 0 and out["ft_left"] == 1


# ---------------------------------------------------------------------------
# 3. Yhdistelmahaku: "vapauta rahaa ensin"
# ---------------------------------------------------------------------------
def _pair_case():
    squad = _legal_squad(price=50)
    # DEF-lahtija (id 3) hinta 50; paras tulokas X maksaa 52 -> ei mahdu yksin
    # (pankki 0). MID-lahtija (id 8) 50 -> Y maksaa 47 ja on hieman parempi:
    # yksin +0.3 (alle kynnyksen), mutta vapauttaa 3 -> X mahtuu.
    x = _p(90, 2, 52, 12.0)          # DEF, +7.0 vs lahtija
    y = _p(91, 3, 47, 5.3)           # MID, +0.3
    return squad, squad + [x, y], x, y


def test_pair_search_finds_money_freeing_combo():
    squad, pool, x, y = _pair_case()
    assert tr.single_moves(squad, pool, 0, [2], top_k=5) == [] or \
        all(m["in"]["id"] != x["id"] for m in tr.single_moves(squad, pool, 0, [2]))
    step = tr.plan_gw(squad, pool, 0, [2], 2)
    ins = [m["in"]["id"] for m in step["moves"]]
    assert x["id"] in ins and y["id"] in ins
    assert all(m["pair"] for m in step["moves"])
    # rahaa vapauttava siirto ensin -> pankki ei kay miinuksella
    assert step["moves"][0]["in"]["id"] == y["id"]
    assert step["bank_tenths"] == 0 + (50 - 47) + (50 - 52)


def test_pair_is_not_taken_when_it_does_not_beat_singles():
    """Negatiivinen kontrolli: kun paras yksittainen siirto on jo hyva ja pari
    ei lisaa vahintaan MIN_GAIN:ia, pari EI valikoidu."""
    squad = _legal_squad(price=50)
    good = _p(90, 3, 50, 12.0)       # +7.0 yksin, mahtuu
    weak = _p(91, 2, 50, 5.2)        # +0.2, ei kynnyksen yli
    step = tr.plan_gw(squad, squad + [good, weak], 0, [2], 2)
    assert [m["in"]["id"] for m in step["moves"]] == [90]
    assert step["moves"][0]["pair"] is False


def _squad_with_weak_mid():
    """Runko jossa heikko MID (id 9, xp 5.0) on PAKOSTI avauksessa: penkki
    tayttyy vielä heikommista (GK2, kaksi DEF:ia, yksi FWD xp 1.0)."""
    squad = _legal_squad(xp=20.0)
    def _set(i, xp):
        squad[i]["xp_horizon_total"] = xp
        squad[i]["xp_per_gw"] = xp
        squad[i]["gameweeks"] = [{"gw": 2, "opponents": [], "xp": xp}]
    _set(8, 5.0)
    for i in (1, 5, 6, 14):
        _set(i, 1.0)
    return squad


# ---------------------------------------------------------------------------
# 4. Luottamuspaino
# ---------------------------------------------------------------------------
def test_confidence_weight_prefers_proven_over_price_prior(monkeypatch):
    """MEKANISMI, ei tuotantoarvo.

    🔴 3.9: tama testi lukitsi arvon 0.75 aritmetiikkaansa
    (`10.0 * 0.75 - 5.0`). Kun paino mitattiin ja asetettiin 1.0:aan
    (`scripts/measure_promoted_bias.py`: malli ALIarvioi nousijaseuroja,
    ei yliarvioi), testi kaatui — vaikka mekanismi oli ehja. Testi asettaa
    nyt alennuksen ITSE, jolloin se mittaa etta paino VAIKUTTAA
    jarjestykseen ja etta naytto- ja paatosluku erottuvat. Tuotantoarvo on
    eri kysymys ja se on pinnattu `tests/test_promoted_weight_measured.py`:ssa
    mittausta vasten."""
    monkeypatch.setattr(tr, "LOW_CONFIDENCE_WEIGHT", 0.75)
    squad = _squad_with_weak_mid()
    proven = _p(90, 3, 50, 9.0)
    prior = _p(91, 3, 50, 10.0, data_basis="no_history")   # raakana parempi
    moves = tr.single_moves(squad, squad + [proven, prior], 0, [2], top_k=2)
    assert moves[0]["in"]["id"] == proven["id"]
    assert moves[0]["confidence_weight"] == 1.0
    prior_move = next(m for m in moves if m["in"]["id"] == prior["id"])
    assert prior_move["confidence_weight"] == 0.75
    # 3.9: molemmat painot nimetaan erikseen — rivilla nakynyt paino oli
    # TULIJAN, mutta paatoksen teki usein LAHTIJAN alennus.
    assert prior_move["confidence_weight_in"] == 0.75
    assert prior_move["confidence_weight_out"] == 1.0
    # nayttoluku on painottamaton, paatosluku painotettu
    assert prior_move["gain"] == pytest.approx(5.0)
    assert prior_move["gain_weighted"] == pytest.approx(10.0 * 0.75 - 5.0)


def test_confidence_weight_negative_control(monkeypatch):
    """Paino 1.0 -> hintapriori-pelaaja voittaa raakaluvulla. Jos tama ei
    kaanny, portti mittaa jotain muuta kuin painoa."""
    monkeypatch.setattr(tr, "LOW_CONFIDENCE_WEIGHT", 1.0)
    squad = _squad_with_weak_mid()
    proven = _p(90, 3, 50, 9.0)
    prior = _p(91, 3, 50, 10.0, data_basis="no_history")
    moves = tr.single_moves(squad, squad + [proven, prior], 0, [2], top_k=1)
    assert moves[0]["in"]["id"] == prior["id"]


# 🔴 3.9: `expected` oli `tr.LOW_CONFIDENCE_WEIGHT`, ja kun se on 1.0 nama
# rivit vaittavat vain "1.0 == 1.0" — portti olisi jaanyt sokeaksi tasan
# silloin kun tuotantoarvo lakkasi olemasta alennus. Alennus asetetaan tassa,
# jotta ehdot mitataan riippumatta tuotantoarvosta.
LIPUTETUT = [
    ("data_basis", "no_history"),
    ("minutes_source", "price_prior"),
    ("is_promoted", True),
]
LIPUTTAMATTOMAT = [
    ("minutes_confidence", "low"),   # kaikilla 516:lla 28.8 -> ei ehto
    ("data_basis", "limited_history"),
]


@pytest.mark.parametrize("field,value", LIPUTETUT)
def test_confidence_weight_lipputtaa(field, value, monkeypatch):
    monkeypatch.setattr(tr, "LOW_CONFIDENCE_WEIGHT", 0.5)
    assert tr.confidence_weight({field: value}) == 0.5


@pytest.mark.parametrize("field,value", LIPUTTAMATTOMAT)
def test_confidence_weight_ei_liputa(field, value, monkeypatch):
    monkeypatch.setattr(tr, "LOW_CONFIDENCE_WEIGHT", 0.5)
    assert tr.confidence_weight({field: value}) == 1.0


def test_pool_carries_promoted_flag(_mock_fpl, monkeypatch):
    xp = dict(FAKE_XP)
    xp["meta"] = {**FAKE_XP["meta"], "team_confidence": {"teams": {
        "Club 3": {"is_promoted": True}}}}
    monkeypatch.setattr(rt, "load_xp", lambda: xp)
    _x, _b, pool, by_id = rt.build_context()
    assert all("is_promoted" in p for p in pool)
    # FAKE_XP-pelaajilla ei ole team-kenttaa -> lippu False kaikilla (ei kaadu)
    assert not any(p["is_promoted"] for p in pool)


# ---------------------------------------------------------------------------
# 5. Stale-squad-vihje
# ---------------------------------------------------------------------------
def test_plan_squad_source_manual_is_never_stale(_mock_fpl):
    out = pl.plan_transfers(players=WEAK_SQUAD, horizon=3, bank=10.0)
    src = out["meta"]["squad_source"]
    assert src["mode"] == "manual" and src["stale"] is False and "note" not in src


def test_plan_squad_source_entry_stale_when_deadline_gw_is_next(_mock_fpl, monkeypatch):
    xp = dict(FAKE_XP)
    xp["meta"] = {**FAKE_XP["meta"], "deadline_gameweek": 2}
    monkeypatch.setattr(rt, "load_xp", lambda: xp)
    out = pl.plan_transfers(entry=424242, horizon=3)
    src = out["meta"]["squad_source"]
    assert src["mode"] == "entry" and src["gw"] == 1 and src["stale"] is True
    assert src["deadline_gw"] == 2 and "note" not in src  # proosa klientin i18n:sta


def test_plan_squad_source_entry_not_stale_without_gap(_mock_fpl):
    # deadline_gameweek puuttuu (vanha payload) -> ei vaitetta
    out = pl.plan_transfers(entry=424242, horizon=3)
    assert out["meta"]["squad_source"]["stale"] is False


def test_squad_source_is_structured_not_prose(_mock_fpl):
    """28.8 julkaisuportti: backend ei kirjoita proosaa (klientti renderoi
    i18n:sta) ja deadline_gw tulee samasta lahteesta kuin picks_outdated."""
    out = pl.plan_transfers(players=WEAK_SQUAD, horizon=6, bank=10.0, ft=1)
    ss = out["meta"]["squad_source"]
    assert set(ss) == {"mode", "gw", "deadline_gw", "stale"}
    assert "note" not in ss
    assert ss["mode"] == "manual" and ss["stale"] is False
    # Negatiivinen kontrolli: vanha proosa ei saa palata mihinkaan payloadiin
    import json
    blob = json.dumps(out)
    assert "Enter your current 15" not in blob
    assert "thin-sample" not in blob and "global optimum" not in blob
