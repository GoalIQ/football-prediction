"""XP-POISSAOLO-PALUU (24.9.2026): pelikielto nollaa vain kielletyt kierrokset.

Ennen: FPL:n `s`-lippu antoi kertoimen 0 koko horisonttiin GW n..n+5, joten
yhden ottelun pelikielto pudotti pelaajan projektiosta ja siirtomoottori myi
hanet kuolleena paikkana, vaikka han palaa seuraavalla kierroksella.

FPL:n news kertoo paluupaivan ("Suspended until 17 Oct"), ja mitattu 24.9
(fpl_xp.SUSPENDED_UNTIL_RE-kommentti): paiva on joukkueen ensimmaisen kiellon
jalkeisen ottelun paiva, 4/4 nykyista ja 5/5 ratkennutta.

Mekanismit (CLAUDE.md 6a):
  (1) yksi lukija: `fpl_xp.suspension_return_date` + `suspension_round_factor`
      builderille ja `fpl_xp.returns_from_suspension` siirtomoottorille.
  (2) kutsupaikka AST:lla (test_xp_doubt_horizon.test_silmukka_... vaatii
      round_minutesin saavan mm_returnin ja return_factorin) + tassa.
  (3) vaiheet: kielletty kierros, paluukierros, tuplakierros jonka ensimmainen
      ottelu on kiellon aikana, tuntematon kickoff, lukematon news.
"""
from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path

import pytest

from scripts import build_fpl_xp as b
from src.models import fpl_transfers as tr
from src.models import fpl_xp as xp

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "scripts" / "build_fpl_xp.py").read_text(encoding="utf-8")
REF = dt.date(2026, 9, 24)
D = dt.date


def _mm(p_start=0.8, p_sub=0.5):
    return xp.recompute_minutes({
        "p_start_raw": p_start, "p_start": p_start * 0.95, "p_sub": p_sub,
        "e_min_start": 84.0, "e_min_sub": 22.0, "p60_start": 0.88,
        "p60_sub": 0.05, "n_obs": 12, "confidence": "high"})


# ---------------------------------------------------------------- lukija
@pytest.mark.parametrize("news,ref,odotettu", [
    ("Suspended until 17 Oct", REF, D(2026, 10, 17)),
    ("Suspended until 19 Oct", REF, D(2026, 10, 19)),
    ("Suspended until 3 Jan", D(2026, 12, 20), D(2027, 1, 3)),
    ("Suspended until 17 October", REF, D(2026, 10, 17)),
    # vanhentunut mutta alle 60 vrk: mennyt paiva -> kaikki ottelut sallittu
    ("Suspended until 29 Aug", REF, D(2026, 8, 29)),
])
def test_paluupaiva_luetaan_fpln_newsista(news, ref, odotettu):
    assert xp.suspension_return_date(news, ref) == odotettu


@pytest.mark.parametrize("news", [
    None, "", "Suspended", "Knee injury - Expected back 17 Oct",
    "Suspended until 31 Feb", "Suspended until 17 Foo", "suspended until tomorrow",
])
def test_lukematon_news_on_fail_closed(news):
    assert xp.suspension_return_date(news, REF) is None


@pytest.mark.parametrize("kickoffs,odotettu", [
    ([D(2026, 10, 11)], 0.0),                    # kielletty kierros
    ([D(2026, 10, 17)], 1.0),                    # paluupaiva = paluuottelu
    ([D(2026, 10, 24)], 1.0),                    # myohempi kierros
    ([D(2026, 10, 14), D(2026, 10, 18)], 0.5),   # tuplakierros kiellon rajalla
    ([None], 0.0),                               # tuntematon kickoff
    ([], 0.0),                                   # blank
])
def test_kierroksen_kerroin(kickoffs, odotettu):
    assert xp.suspension_round_factor(D(2026, 10, 17), kickoffs) == odotettu


# ---------------------------------------------------------------- builder
def _el(news="Suspended until 17 Oct", status="s", pid=398, added="2026-09-13T17:00:09Z"):
    return {"id": pid, "status": status, "chance_of_playing_next_round": 0,
            "news": news, "news_added": added}


def test_suspension_returns_lukee_vain_s_ja_luettavan_paivan():
    els = [_el(), _el(pid=2, news="Suspended"), _el(pid=3, status="i", news="Suspended until 17 Oct"),
           {"id": 4, "status": "a", "news": ""}]
    assert b.suspension_returns(els, REF) == {398: D(2026, 10, 17)}


def test_returning_elements_vapauttaa_vain_palaajan():
    els = [_el(), {"id": 7, "status": "d", "chance_of_playing_next_round": 50}]
    out = {e["id"]: e for e in b.returning_elements(els, {398: D(2026, 10, 17)})}
    assert out[398]["status"] == "a" and out[398]["chance_of_playing_next_round"] is None
    assert out[7]["status"] == "d", "joukkuetoverin lippu pysyy"


def _xmins(g_factor):
    flagged = xp.apply_availability(_mm(), "s", 0)
    return b.round_minutes(flagged, _el(), 7, 6, availability_in_value=False,
                           mm_return=_mm(), return_factor=g_factor)["xmins"]


def test_kielletty_kierros_pysyy_nollassa():
    assert _xmins(0.0) == 0.0


def test_paluukierros_saa_paluuajon_minuutit():
    assert _xmins(1.0) == pytest.approx(_mm()["xmins"])


def test_tuplakierros_kiellon_rajalla_puolittuu():
    assert _xmins(0.5) == pytest.approx(xp.scale_availability(_mm(), 0.5)["xmins"])


def test_ilman_paluupaivaa_vanha_kaytos():
    flagged = xp.apply_availability(_mm(), "s", 0)
    out = b.round_minutes(flagged, _el(news="Suspended"), 9, 6, availability_in_value=False)
    assert out["xmins"] == 0.0


def test_ehdollinen_ohitus_voittaa_paluun():
    mm = _mm(0.3)
    out = b.round_minutes(mm, _el(), 9, 6, availability_in_value=True,
                          mm_return=_mm(), return_factor=1.0)
    assert out is mm


def test_otsikkokierroksella_fpln_chance_nolla_voittaa_paivan():
    """Kutsupaikka: _return_factor palauttaa 0 otsikkokierrokselle kun FPL:n
    chance on 0, vaikka paiva sallisi. FPL:n luku koskee juuri sita kierrosta."""
    main = next(n for n in ast.parse(SRC).body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    fn = next(n for n in ast.walk(main)
              if isinstance(n, ast.FunctionDef) and n.name == "_return_factor")
    src = ast.unparse(fn)
    assert "g == headline_gw and e.get('chance_of_playing_next_round') == 0" in src
    assert "xp.suspension_round_factor(" in src


def test_paluuajo_ajetaan_returning_elementsilla():
    assert "returning_elements(boot['elements'], returning)" in ast.unparse(ast.parse(SRC))


# ---------------------------------------------------------------- siirtomoottori
def _row(**kw):
    base = {"status": "s", "news": "Suspended until 17 Oct", "chance_next": 0}
    return {**base, **kw}


def test_palaava_pelikieltopelaaja_ei_ole_kuollut_paikka():
    assert tr.needs_repair(_row()) is False
    assert tr.unavailable_by_fpl(_row()) is False
    assert tr.repair_reason(_row()) == "status:s"  # syy sailyy, mutta korjausta ei tehda


@pytest.mark.parametrize("row", [
    _row(news="Suspended"),                       # lukematon paiva
    _row(no_projection=True, no_projection_reason="unavailable"),  # kielto yli horisontin
    _row(status="i", news="Suspended until 17 Oct"),  # ei pelikielto
])
def test_muut_pysyvat_korjattavina(row):
    assert tr.needs_repair(row) is True
    assert tr.unavailable_by_fpl(row) is True
