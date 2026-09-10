# -*- coding: utf-8 -*-
"""MODEL-VS-CONSENSUS (10.9.2026): "FPL's own projection: x. Ours: y."

Portit:
  1. kynnys johdetaan gradatusta lokista, ei valita (derive_threshold);
     puuttuva/vanhentunut vertailu -> None -> rivia ei nayteta
  2. parametrit on pinnattu perusteluun (CALL-MARGIN-malli): muutos ilman
     docstringin taulukkoa kaatuu
  3. SPA:n projectionGap.ts ei kanna omaa numeerista kynnysta (yksi lukija)
  4. pinnan lause on sama Pythonin vakiossa ja Sveltessa (arvo, ei substring);
     jos mobiilin en.ts kantaa avaimen, senkin on oltava sama
  5. elava payload kantaa kentat ja elava loki tuottaa kynnyksen
"""
from __future__ import annotations

import datetime as dt
import json
import re
from html import escape
from pathlib import Path

import pytest

from src.models import fpl_projection_gap as pg
from tests.test_i18n_svelte_parity import EN, _en_values, _norm

ROOT = Path(__file__).resolve().parents[1]
SPA = ROOT / "web" / "pro-spa" / "src" / "lib"


def _doc(gw=3, ours=1.536, theirs=1.688, frozen="2026-09-04T12:16:41Z", n=501):
    return {"gameweeks": [{"gw": gw, "frozen_at": frozen,
                           "comparison": {"n": n, "mae": {"goaliq": ours, "fpl_ep_next": theirs}}}]}


NOW = dt.datetime(2026, 9, 10, tzinfo=dt.timezone.utc)


# --- 1. kynnyksen johtaminen ------------------------------------------------

def test_threshold_is_worst_mae_rounded_up_to_half():
    t = pg.derive_threshold(_doc(), now=NOW)
    assert t["min_abs_xp"] == 2.0 and t["min_rel"] == pg.MIN_REL_GAP
    assert t["basis_gw"] == 3 and t["basis_n"] == 501
    assert pg.derive_threshold(_doc(ours=0.9, theirs=1.01), now=NOW)["min_abs_xp"] == 1.5
    assert pg.derive_threshold(_doc(ours=1.0, theirs=0.7), now=NOW)["min_abs_xp"] == 1.0


def test_latest_frozen_comparison_wins_not_list_order():
    doc = {"gameweeks": [_doc(gw=4, ours=2.4, theirs=2.4, frozen="2026-09-09T00:00:00Z")["gameweeks"][0],
                         _doc(gw=3)["gameweeks"][0]]}
    assert pg.derive_threshold(doc, now=NOW)["basis_gw"] == 4


@pytest.mark.parametrize("doc", [
    None, {}, {"gameweeks": []},
    {"gameweeks": [{"gw": 1, "frozen_at": "2026-09-04T00:00:00Z", "comparison": None}]},
    {"gameweeks": [{"gw": 1, "frozen_at": "2026-09-04T00:00:00Z",
                    "comparison": {"mae": {"goaliq": 1.5}}}]},          # toinen MAE puuttuu
    {"gameweeks": [{"gw": 1, "comparison": {"mae": {"goaliq": 1.5, "fpl_ep_next": 1.6}}}]},  # ei aikaleimaa
])
def test_no_usable_comparison_means_no_threshold(doc):
    assert pg.derive_threshold(doc, now=NOW) is None


def test_stale_comparison_is_not_a_threshold():
    """Kesalla edellisen kauden MAE ei kuvaa uutta mallia (ehto vanhenee)."""
    old = _doc(frozen="2026-05-20T00:00:00Z")
    assert pg.derive_threshold(old, now=NOW) is None
    edge = NOW - dt.timedelta(days=pg.COMPARISON_MAX_AGE_DAYS)
    assert pg.derive_threshold(_doc(frozen=edge.strftime("%Y-%m-%dT%H:%M:%SZ")), now=NOW) is not None


# --- 2. parametrit pinnattu perusteluun ------------------------------------

def test_parameters_are_pinned_with_reason():
    """Kynnyksen suhteellinen osa ja pyoristys valittiin GW3:n jakaumasta
    (n=501). Muutos vaatii uuden mittauksen docstringin taulukkoon."""
    assert (pg.MIN_REL_GAP, pg.GAP_ROUND_TO, pg.COMPARISON_MAX_AGE_DAYS) == (0.30, 0.5, 60), (
        "Paivita src/models/fpl_projection_gap.py docstringin jakaumataulukko "
        "ja tama assertio samassa commitissa.")
    src = (ROOT / "src" / "models" / "fpl_projection_gap.py").read_text(encoding="utf-8")
    assert "KYNNYS JOHDETAAN" in src and "n=501" in src
    assert "|d| >= 2.0 JA  rel >= 30 %" in src and "<- valittu" in src


# --- gap_state ---------------------------------------------------------------

THR = {"min_abs_xp": 2.0, "min_rel": 0.30}


@pytest.mark.parametrize("ours,fpl,shown", [
    (6.2, 4.1, True),     # 2.1 abs, 34 %
    (4.1, 6.2, True),     # suunta ei vaikuta
    (9.0, 7.1, False),    # 1.9 abs < 2.0
    (12.0, 9.9, False),   # 2.1 abs mutta 17.5 % < 30 %
    (2.0, 0.0, True),     # 100 %
    (0.0, 0.0, False),
    (None, 4.0, False),
    (4.0, None, False),
    (float("nan"), 4.0, False),
])
def test_gap_state_rule(ours, fpl, shown):
    assert (pg.gap_state(ours, fpl, THR) is not None) is shown


def test_gap_state_without_threshold_is_closed():
    assert pg.gap_state(6.2, 4.1, None) is None
    assert pg.gap_state(6.2, 4.1, {}) is None


def test_parse_fpl_num_missing_is_none_not_zero():
    assert pg.parse_fpl_num("4.5") == 4.5
    assert pg.parse_fpl_num("") is None and pg.parse_fpl_num(None) is None
    assert pg.parse_fpl_num("x") is None and pg.parse_fpl_num("nan") is None
    boot = {"elements": [{"id": 1, "ep_next": "3.2"}, {"id": 2, "ep_next": ""}, {"ep_next": "1"}]}
    assert pg.ep_next_by_id(boot) == {1: 3.2, 2: None}
    assert pg.fpl_next_event_id({"events": [{"id": 3, "is_next": False}, {"id": 4, "is_next": True}]}) == 4
    assert pg.fpl_next_event_id({"events": []}) is None


# --- 3. SPA:n kopio ei kanna omaa kynnysta -----------------------------------

def test_spa_projection_gap_has_no_numeric_threshold():
    ts = (SPA / "projectionGap.ts").read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", "", ts, flags=re.S)
    code = re.sub(r"//[^\n]*", "", code)
    nums = re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w])", code)
    assert set(nums) <= {"0"}, f"projectionGap.ts kantaa omaa lukua: {nums}"
    assert "thr.min_abs_xp" in code and "thr.min_rel" in code
    assert "Math.max(o, f)" in code, "suhteellinen ehto lasketaan suuremmasta luvusta kuten Pythonissa"


def test_svelte_card_reads_threshold_from_meta_only():
    sv = (SPA / "components" / "PlayerCard.svelte").read_text(encoding="utf-8")
    assert "meta?.projection_gap" in sv and "meta?.fpl_ep_next_gw" in sv
    assert "p.fpl_ep_next" in sv
    # kortti ei saa laskea kynnysta itse
    assert not re.search(r"min_abs_xp\s*[:=]\s*\d", sv)


# --- 4. pinnan lause on sama joka pinnalla -----------------------------------

def test_surface_sentence_is_verbatim_in_svelte():
    sv = _norm((SPA / "components" / "PlayerCard.svelte").read_text(encoding="utf-8"))
    want = _norm(pg.SURFACE_SENTENCE)
    assert want and want in sv, f"PlayerCard ei sisalla lausetta {want!r} samana"
    assert _norm("FPL's own projection: {x}. Ours: {y}. today") not in sv


def test_surface_does_not_say_consensus_or_others():
    """Villen paatos 10.9: vertailukohta on FPL:n oma luku, ei 'consensus'."""
    sv = (SPA / "components" / "PlayerCard.svelte").read_text(encoding="utf-8")
    body = re.sub(r"<!--.*?-->", "", sv, flags=re.S)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    body = re.sub(r"//[^\n]*", "", body)
    for bad in ("consensus", "others say", "the crowd"):
        assert bad not in body.lower(), bad


def test_mobile_en_key_matches_when_present():
    """Mobiilin en.ts ei ole tassa haarassa. Jos avain on siella, sen on
    oltava sama lause; jos ei ole, portti sanoo sen raporttiin (xfail)."""
    if not EN.exists():
        pytest.skip("goaliq-app ei ole checkoutattu")
    v = _en_values().get("fantasy.playercard.fpl_projection")
    if v is None:
        pytest.xfail("fantasy.playercard.fpl_projection puuttuu mobiilin en.ts:sta (lisataan mobiilihaarassa)")
    assert _norm(v) == _norm(pg.SURFACE_SENTENCE)


# --- 5. elava payload ja loki -------------------------------------------------

def test_live_accuracy_log_yields_threshold_or_is_stale():
    path = ROOT / "data" / "fpl_xp_gw_accuracy.json"
    if not path.exists():
        pytest.skip("ei lokia")
    doc = json.loads(path.read_text(encoding="utf-8"))
    t = pg.derive_threshold(doc)
    latest = [g for g in doc.get("gameweeks", []) if isinstance(g.get("comparison"), dict)]
    if not latest:
        assert t is None
        return
    fro = pg._parse_utc(latest[-1].get("frozen_at"))
    if fro and (dt.datetime.now(dt.timezone.utc) - fro).days <= pg.COMPARISON_MAX_AGE_DAYS:
        assert t is not None and t["min_abs_xp"] >= 0.5


def test_builder_writes_the_fields_the_card_reads():
    src = (ROOT / "scripts" / "build_fpl_xp.py").read_text(encoding="utf-8")
    assert "pgap.PLAYER_FIELD" in src and "pgap.META_FIELD" in src and "pgap.META_GW_FIELD" in src
    api = (SPA / "api.ts").read_text(encoding="utf-8")
    assert f"{pg.PLAYER_FIELD}?:" in api and f"{pg.META_FIELD}?:" in api and f"{pg.META_GW_FIELD}?:" in api


def test_freeze_uses_the_same_parser():
    src = (ROOT / "scripts" / "freeze_fpl_xp_gw.py").read_text(encoding="utf-8")
    assert "from src.models.fpl_projection_gap import parse_fpl_num" in src
    assert "def _num(" not in src


def test_api_passes_player_and_meta_through():
    """API ei suodata pelaajakenttia: lukija on payload (yksi lukija)."""
    api = (ROOT / "api" / "main.py").read_text(encoding="utf-8")
    assert f'"{pg.PLAYER_FIELD}"' not in api and f'"{pg.META_FIELD}"' not in api, (
        "api/main.py kasittelee projektiokenttaa erikseen: yksi lukija rikkoutuu")
    assert escape(pg.SURFACE_LABEL)  # vakio olemassa
