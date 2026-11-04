# -*- coding: utf-8 -*-
"""KIERROSVAIHDON VAHTI (3.9.2026, Villen pyynto: "tee nyt sillee etta se
automaattisesti paivittyy ettei joka kierroksen jalkee tarvi korjailla
bugeja").

MIKSI TAMA ON OLEMASSA. Yhden paivan aikana neljä eri vikaa oli SAMAA
LUOKKAA: pinta tai testi oli sidottu kauden VAIHEESEEN eika koodiin, ja se
hajosi kun kierros vaihtui.

  1. `tests.yml` punainen 28.8 alkaen: yksi testi odotti sivulta
     "fitted on 1 match" (vanheni GW2:n jalkeen) ja toinen vaati elavaan
     artefaktiin mennytta deadlinea (punainen aina kierrosten valissa).
  2. My teamin kentta nayttivat GW2:n lukuja kun GW3 oli auki: valittu
     kierros sailyi "kelvollisena" koska artefaktin `gameweeks[]` alkaa yha
     menneesta kierroksesta.
  3. xG-leaders nayttivat liigasta lahteneita: FPL pitaa heidat
     bootstrapissa kauden loppuun, ja pudotus laukesi vain puuttumisesta.
  4. Chip timing ehdotti wildcardia joka oli jo pelattu, eika tuntenut
     kauden kahta chippisarjaa.

Yhteinen nimittaja: invariantti mitattiin AJANHETKELLA jolloin se sattui
pitamaan. Nama testit ajavat samat funktiot KOLMESSA vaiheessa
synteettisella datalla, joten vika loytyy commitilla eika kierroksen
vaihtuessa. Ei verkkoa, ei elavia artefakteja.

VAIHEET:
  before   deadline edessa      (GW3 auki, mitaan ei pelattu)
  live     kierros kesken       (GW3:n deadline mennyt, ottelut kesken)
  after    kierros gradattu     (GW3 valmis, GW4 auki)
"""
from __future__ import annotations

import pytest

from api import fantasy_edge as fe
from src.models import fpl_chips
from src.models.fpl_gameweek import actionable_gameweek
from src.models.fpl_leaders import rank_xg_leaders
from src.models.fpl_rate_team import _player_gameweeks

HORIZON = [2, 3, 4, 5, 6, 7]

# (nimi, deadline_gameweek, payloadin oma GW)
PHASES = [
    ("before", 3, 3),   # GW3:n deadline edessa
    ("live", 4, 3),     # GW3 kesken: seuraava deadline on GW4:n
    ("after", 4, 4),    # GW3 gradattu, GW4 auki
]


def _pool(gws=HORIZON):
    return [{"id": 1, "gameweeks": [{"gw": g, "opponents": [], "xp": 4.0}
                                    for g in gws]}]


def _player(gws=HORIZON):
    return {"gameweeks": [{"gw": g, "opponents": [], "xp": 4.0} for g in gws]}


@pytest.mark.parametrize("phase,dl_gw,payload_gw", PHASES)
def test_no_surface_offers_a_gameweek_before_the_one_it_is_about(
        phase, dl_gw, payload_gw):
    """Pinta ei saa tarjota kierrosta jota ennen sen oma kierros alkaa.

    Tama on My teamin kenttavika yleistettyna: kayttajan valinta sailyy niin
    kauan kuin vaihtoehto on listalla, joten mennyt kierros ei saa olla
    listalla lainkaan."""
    gws = [g["gw"] for g in _player_gameweeks(_player(), min_gw=payload_gw)]
    assert gws, phase
    assert min(gws) >= payload_gw, (phase, gws)
    # negatiivinen kontrolli: ilman rajaa mennyt kierros olisi mukana
    assert min(g["gw"] for g in _player_gameweeks(_player())) == HORIZON[0]


@pytest.mark.parametrize("phase,dl_gw,payload_gw", PHASES)
def test_chip_windows_never_include_a_closed_gameweek(phase, dl_gw, payload_gw):
    """Chipin voi pelata vain kierrokselle jonka deadline on edessa."""
    playable = fe._playable_gws(_pool(), {"meta": {"deadline_gameweek": dl_gw}})
    assert playable, phase
    assert min(playable) >= dl_gw, (phase, playable)
    assert all(g in HORIZON for g in playable)


@pytest.mark.parametrize("phase,dl_gw,payload_gw", PHASES)
def test_actionable_gameweek_follows_the_deadline_not_the_clock(
        phase, dl_gw, payload_gw):
    assert actionable_gameweek({"deadline_gameweek": dl_gw}) == dl_gw


@pytest.mark.parametrize("phase,dl_gw,payload_gw", PHASES)
def test_played_chip_stays_dropped_in_every_phase(phase, dl_gw, payload_gw):
    """Pelattu chip ei palaa listalle kun kierros vaihtuu."""
    boot = {"chips": [{"name": "wildcard", "start_event": 2, "stop_event": 19},
                      {"name": "wildcard", "start_event": 20, "stop_event": 38}]}
    st = fpl_chips.chip_state(
        boot, {"chips": [{"name": "wildcard", "event": 2}]}, dl_gw)
    assert st["wc"]["windows"][0]["available"] is False, phase
    assert not fpl_chips.gw_allowed(st, "wc", dl_gw), phase
    # toisen puolikkaan kopio sailyy tarjolla kaikissa vaiheissa
    assert fpl_chips.gw_allowed(st, "wc", 25), phase


@pytest.mark.parametrize("phase,dl_gw,payload_gw", PHASES)
def test_players_who_left_the_league_never_reappear(phase, dl_gw, payload_gw):
    """FPL pitaa lahteneen bootstrapissa kauden loppuun, joten suodattimen on
    luettava status eika puuttumista - joka vaiheessa."""
    rows = []
    for pid, status in ((1, "u"), (2, "a")):
        rows.append({
            "id": pid, "web_name": f"P{pid}", "team_short": "TST",
            "pos": "FWD", "price": 7.0, "owned_pct": 1.0, "status": status,
            "basis": "2026/27", "games_total": 5,
            "recent_games": [{"round": g, "opp": "OPP", "venue": "H",
                              "minutes": 90, "xg": 0.5, "xa": 0.1,
                              "xgi": 0.6, "dc": 3} for g in range(1, 6)],
        })
    out = rank_xg_leaders({"meta": {"available": True}, "players": rows},
                          window=5, top_n=10)
    assert [r["id"] for r in out["players"]] == [2], phase


def test_the_guard_itself_would_fail_on_the_old_behaviour():
    """Negatiivinen kontrolli koko tiedostolle: jos mennytta kierrosta EI
    suodateta, ensimmainen testi kaatuu. Ilman tata vahti voisi olla
    vihrea siksi ettei se mittaa mitaan."""
    gws = [g["gw"] for g in _player_gameweeks(_player(), min_gw=None)]
    assert min(gws) < PHASES[0][2]


# ---------------------------------------------------------------------------
# WP2 (1.11.2026): /fpl:n nollapelitaulukko ei nayta kierrosta jonka deadline
# on mennyt.
#
# MITATTU 1.11: sivu sanoi "Gameweek 9 is being played" ja "Next deadline:
# Gameweek 10", mutta sen ensimmainen taulukko oli "Gameweek 9 clean sheet
# probabilities" (display_gameweek piti kesken olevan kierroksen). Lisaksi
# sivu paistetaan uudelleen pitkin paivaa jo committattua payloadia vasten,
# joten payloadin `deadline_gameweek` voi olla deadlinen jalkeen vanha
# ("live-stale"). Lukija `open_gameweek` tarkistaa saman payloadin
# deadline-listan kellosta.
# ---------------------------------------------------------------------------
import datetime as _dt  # noqa: E402

from src.models.fpl_gameweek import clean_sheet_table_gameweek  # noqa: E402

_UTC = _dt.timezone.utc
_DL = {3: _dt.datetime(2026, 9, 12, 10, 0, tzinfo=_UTC),
       4: _dt.datetime(2026, 9, 19, 10, 0, tzinfo=_UTC),
       5: _dt.datetime(2026, 9, 26, 10, 0, tzinfo=_UTC)}


def _cs_meta(dl_gw: int, cur: int) -> dict:
    # `deadlines` = kauden jaljella olevat deadlinet PAYLOADIN rakennushetkella.
    return {"deadline_gameweek": dl_gw, "next_gameweek": cur,
            "deadlines": [{"gw": g, "utc": t.isoformat()} for g, t in _DL.items() if g >= dl_gw]}


# (vaihe, payloadin deadline_gameweek, payloadin next_gameweek, kello)
CS_PHASES = [
    ("before", 3, 3, _DL[3] - _dt.timedelta(hours=1)),
    ("live-stale", 3, 3, _DL[3] + _dt.timedelta(hours=1)),
    ("live", 4, 3, _DL[3] + _dt.timedelta(hours=1)),
    ("after", 4, 4, _DL[3] + _dt.timedelta(days=3)),
]


@pytest.mark.parametrize("phase,dl_gw,cur,now", CS_PHASES)
def test_clean_sheet_table_never_shows_a_closed_gameweek(phase, dl_gw, cur, now):
    gw = clean_sheet_table_gameweek(_cs_meta(dl_gw, cur), None, now)
    assert gw in _DL, (phase, gw)
    assert _DL[gw] > now, (phase, gw, "deadline mennyt")
    # ja se on ENSIMMAINEN avoin kierros, ei mika tahansa tuleva
    assert gw == min(g for g, t in _DL.items() if t > now), (phase, gw)


def test_clean_sheet_guard_would_fail_on_the_old_reader():
    """Negatiivinen kontrolli: vanha lukija (display_gameweek) ja pelkka
    actionable_gameweek antavat live-stale-vaiheessa suljetun GW3:n."""
    from src.models.fpl_gameweek import display_gameweek
    meta = _cs_meta(3, 3)
    assert display_gameweek(meta, None) == 3
    assert actionable_gameweek(meta) == 3
    assert clean_sheet_table_gameweek(meta, None, _DL[3] + _dt.timedelta(hours=1)) == 4


def _real_phase0():
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "data" / "fpl_projections_phase0.json"
    if not p.exists():
        pytest.skip("fpl_projections_phase0.json puuttuu")
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.mark.parametrize("phase", ["before", "live-stale", "after"])
def test_fpl_page_cs_table_call_site_in_every_phase(phase):
    """KUTSUPAIKKA: build_context + oikea payload synteettisella kellolla.

    Vaiheet johdetaan payloadin omista deadlineista, joten testi ei vanhene
    kierroksen mukana (6a, mekanismi 3)."""
    import copy
    from scripts import build_fpl_page as b
    fpl = copy.deepcopy(_real_phase0())
    meta = fpl["meta"]
    dls = sorted(((int(d["gw"]), _dt.datetime.fromisoformat(d["utc"])) for d in meta.get("deadlines") or []),
                 key=lambda x: x[1])
    near = {f["gw"] for t in fpl["teams"] for f in t.get("fixtures") or []
            if (f.get("tier") or "near") == "near" and f.get("cs_pct") is not None}
    if len(dls) < 2 or dls[1][0] not in near:
        pytest.skip("kauden loppu: ei kahta deadlinea lahihorisontissa")
    (g0, d0), (g1, _d1) = dls[0], dls[1]
    if phase == "before":
        now = d0 - _dt.timedelta(hours=1)
        meta["deadline_gameweek"] = g0
    elif phase == "live-stale":
        now = d0 + _dt.timedelta(hours=1)
        meta["deadline_gameweek"] = g0
    else:
        now = d0 + _dt.timedelta(hours=1)
        meta["deadline_gameweek"] = g1
        meta["deadlines"] = [d for d in meta["deadlines"] if int(d["gw"]) != g0]
    want = g0 if phase == "before" else g1
    c = b.build_context(fpl, {"all_time": {}, "logged_with_timestamp": 0, "pending": 0,
                              "updated_at": "2026-11-01T00:00:00+00:00"}, now=now)
    assert c["cs_gw"] == want, (phase, c["cs_gw"], want)
    # Taulukon rivit ovat TAMAN kierroksen otteluita, ei kesken olevan.
    by_team = {t["name"]: [f for f in t["fixtures"] if f["gw"] == want] for t in fpl["teams"]}
    assert c["cs_rows"]
    for r in c["cs_rows"]:
        assert any(f["opponent"] == r["opponent"] for f in by_team[r["team"]]), (phase, r["team"])
    # ja deadline-rivi puhuu samasta kierroksesta
    assert f"Next deadline: Gameweek {want}," in b._deadline_row(c)


# ---------------------------------------------------------------------------
# 4.11.2026: /fpl:n FDR-ruudukko ("Fixture difficulty for the next six
# gameweeks") otti artefaktin KAIKKI lahikierrokset, joten Understat-katkon
# aikana (payload 1.11) sen ensimmainen sarake oli jo pelattu GW9 ja rivin
# yhteenveto laski senkin. Ruudukko alkaa nyt samasta kierroksesta kuin
# nollapelitaulukko, ja Games / Avg CS% / Avg FDR lasketaan naytetyista
# soluista. Sama kutsupaikka ja samat vaiheet kuin ylla.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("phase", ["before", "live-stale", "after"])
def test_fpl_page_fdr_grid_never_shows_a_closed_gameweek(phase):
    import copy
    from scripts import build_fpl_page as b
    fpl = copy.deepcopy(_real_phase0())
    meta = fpl["meta"]
    dls = sorted(((int(d["gw"]), _dt.datetime.fromisoformat(d["utc"])) for d in meta.get("deadlines") or []),
                 key=lambda x: x[1])
    near = {f["gw"] for t in fpl["teams"] for f in t.get("fixtures") or []
            if (f.get("tier") or "near") == "near" and f.get("cs_pct") is not None}
    if len(dls) < 2 or dls[1][0] not in near:
        pytest.skip("kauden loppu: ei kahta deadlinea lahihorisontissa")
    (g0, d0), (g1, _d1) = dls[0], dls[1]
    if phase == "before":
        now = d0 - _dt.timedelta(hours=1)
        meta["deadline_gameweek"] = g0
    elif phase == "live-stale":
        now = d0 + _dt.timedelta(hours=1)
        meta["deadline_gameweek"] = g0
    else:
        now = d0 + _dt.timedelta(hours=1)
        meta["deadline_gameweek"] = g1
        meta["deadlines"] = [d for d in meta["deadlines"] if int(d["gw"]) != g0]
    want = g0 if phase == "before" else g1
    c = b.build_context(fpl, {"all_time": {}, "logged_with_timestamp": 0, "pending": 0,
                              "updated_at": "2026-11-01T00:00:00+00:00"}, now=now)
    assert c["gws"] and min(c["gws"]) == want == c["cs_gw"], (phase, c["gws"], want)
    if phase != "before":
        # Negatiivinen kontrolli datasta: suljettu kierros OLI artefaktissa,
        # eli testi ei mene lapi vain siksi etta sita ei ollut.
        assert g0 in near and g0 not in c["gws"], (phase, sorted(near), c["gws"])
    for r in c["fdr_rows"]:
        shown = [f for cell in r["cells"] for f in cell]
        assert r["n"] == len(shown), (phase, r["team"], r["n"], len(shown))
        if shown:
            import numpy as np
            assert r["avg_cs"] == round(float(np.mean([float(f["cs_pct"]) for f in shown])), 1), (phase, r["team"])


def test_fdr_grid_rows_unchanged_when_nothing_is_cut():
    """Rajaamaton rivi = artefaktin oma yhteenveto (sama kaava kuin
    build_fpl_phase0), eli korjaus ei muuta sivua tavallisena paivana."""
    from scripts import build_fpl_page as b
    fpl = _real_phase0()
    first = min(f["gw"] for t in fpl["teams"] for f in t["fixtures"])
    for t in fpl["teams"]:
        near = {**t, "fixtures": [f for f in t["fixtures"]
                                  if (f.get("tier") or "near") == "near" and f.get("cs_pct") is not None]}
        r = b._from_gameweek(near, first)
        assert (r["next_n"], r["next_avg_cs_pct"], r["next_avg_fdr"]) == (
            t["next_n"], t["next_avg_cs_pct"], t["next_avg_fdr"]), t["name"]
