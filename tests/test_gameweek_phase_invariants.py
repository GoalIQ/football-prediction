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
