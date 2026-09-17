# -*- coding: utf-8 -*-
"""RESEED-FT-KOVAKOODATTU (17.9.2026): FT-saldo luetaan FPL:n historiasta,
ei vakiosta.

🔴 TAUSTA. `entry_seed` kirjoitti `"ft_left": 0` perustelulla "wildcard-
kierroksen jalkeen rullausta ei ole". Perustelu oli wildcard-spesifinen,
ehto ei: GW5-reseedin (data/model_squad_reseed/gw5.json) lahde on GW4, joka
ei ollut wildcard. Entry 116920:n historia 17.9: event_transfers [0,0,0,0],
chipit GW2 wildcard ja GW3 3xc. FPL:n saanto (2024/25-): kausi alkaa 1 FT:lla,
kayttamaton rullaa +1 kattoon 5, wildcard/free hit -kierros sailyttaa saldon
sellaisenaan (ei kuluta, ei kerryta). Siis GW2 1 -> GW3 1 -> GW4 2 -> GW5 3.
Vanha koodi antoi moottorille 1 siirron kun FPL antaa 3 (freezen oma katto
FT_MAX leikkaa siita 2:een - se on tietoinen konservatiivinen valinta, ks.
`FT_MAX`in kommentti, eika tama rivi muuta sita).

Kolme mekanismia (CLAUDE.md 6a):
  (1) yksi lukija: `fpl_entry_history.free_transfers_for_gw` on sama kavely
      kuin `infer_free_transfers` (API, rate-team) - ei toista FT-saantoa.
      Freeze saa sen `entry_state`in kautta samassa paketissa kuin pankin.
  (2) `entry_seed`illa ei ole vakiota: `attach_entry_state` on ainoa
      kirjoittaja, reseedille ja ketjulle.
  (3) invariantti `_ft_available(meta) == min(ft_fpl, FT_MAX)` mitataan
      synteettisilla vaiheilla: rullaus, wildcard-lahde, free hit -lahde,
      kulutus, hitit, katto - ei vain GW5:n tilanteella.

Hermeettinen: synteettiset dictit FPL:n muodossa, ei verkkoa.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import re
from pathlib import Path

import pytest

from src.models import fpl_entry_history as hist

ROOT = Path(__file__).resolve().parents[1]


def _load_freeze():
    spec = importlib.util.spec_from_file_location(
        "freeze_model_squad_gw", ROOT / "scripts" / "freeze_model_squad_gw.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _history(transfers_per_gw, chips=(), bank=8, value=1002):
    """`transfers_per_gw` = [GW1:n siirrot, GW2:n, ...]; chips = [(nimi, gw)]."""
    return {"current": [{"event": g, "event_transfers": n,
                         "event_transfers_cost": 0, "bank": bank,
                         "value": value}
                        for g, n in enumerate(transfers_per_gw, start=1)],
            "chips": [{"name": n, "event": g} for n, g in chips]}


# Entry 116920 sellaisena kuin FPL sen julkaisi 17.9.2026.
H_116920 = _history([0, 0, 0, 0], chips=[("wildcard", 2), ("3xc", 3)])


# ---------------------------------------------------------------------------
# 1. Lukija: sama kavely kuin infer_free_transfers, rajattuna kierrokseen
# ---------------------------------------------------------------------------
def test_entry_116920_saldo_kierroksittain():
    f = hist.free_transfers_for_gw
    assert f(H_116920, 2) == 1, "GW1 rajaton -> GW2:een 1 FT"
    assert f(H_116920, 3) == 1, "wildcard GW2 sailyttaa 1, ei kerryta"
    assert f(H_116920, 4) == 2, "3xc ei ole FT-chip: GW3 kerryttaa"
    assert f(H_116920, 5) == 3, "GW5: FPL:n saldo 3 (vanha koodi: ft_left 0 -> 1)"
    # ...ja sama kuin koko historian kavely seuraavalle kierrokselle
    assert f(H_116920, 5) == hist.infer_free_transfers(H_116920)


def test_lukija_ei_lue_tulevaa_rivia():
    """6a.3: freeze ajetaan ENNEN deadlinea, mutta jos historiassa on jo
    GW5:n rivi (ajo myohassa), GW5:n saldo ei saa muuttua siita."""
    h = _history([0, 0, 0, 0, 2], chips=[("wildcard", 2)])
    assert hist.free_transfers_for_gw(h, 5) == 3
    assert hist.infer_free_transfers(h) == 2, "koko historia: GW6:lle 3-2+1"


def test_puuttuva_rivi_on_none_ei_arvaus():
    h = _history([0, 0])                          # GW1, GW2
    assert hist.free_transfers_for_gw(h, 3) == 2
    assert hist.free_transfers_for_gw(h, 4) is None, "rivi GW3 puuttuu"
    assert hist.free_transfers_for_gw(h, 1) is None, "GW1: rajattomat"
    assert hist.free_transfers_for_gw(None, 2) is None
    assert hist.free_transfers_for_gw({"current": []}, 2) is None


def test_entry_state_kantaa_ft_saldon_samassa_paketissa_kuin_pankin():
    boot = {"elements": [{"id": i, "now_cost": 50, "cost_change_start": 0}
                         for i in range(1, 16)]}
    tila = hist.entry_state(H_116920, 4, list(range(1, 16)), [], boot)
    assert tila["ft_available_next"] == 3
    assert tila["ft_source"] == "inferred_from_history"
    assert tila["bank_tenths"] == 8


# ---------------------------------------------------------------------------
# 2. Freeze: vaiheet ja identiteetti _ft_available(meta) == min(ft_fpl, FT_MAX)
# ---------------------------------------------------------------------------
def _seed(m, history, source_gw):
    ids = list(range(1, 16))
    pool = [{"id": i, "web_name": f"P{i}", "element_type": 3, "club": i,
             "price": 50, "xp_horizon_total": 1.0, "gameweeks": []} for i in ids]
    boot = {"elements": [{"id": i, "now_cost": 50, "cost_change_start": 0,
                          "element_type": 3, "team": i, "status": "a"}
                         for i in ids], "teams": []}
    siemen, virhe = m.entry_seed(
        source_gw, pool, boot,
        hae=lambda e, gw: [{"element": i} for i in ids],
        hae_historia=lambda e: (history, None),
        hae_siirrot=lambda e: ([], None))
    assert virhe is None, virhe
    return siemen["meta"]


VAIHEET = [
    # (nimi, historia, source_gw, FPL:n saldo seuraavalle, vanha ft_left)
    ("rullaus 116920 GW5", H_116920, 4, 3, 0),
    ("wildcard-lahde saldolla 1",
     _history([0, 0], chips=[("wildcard", 2)]), 2, 1, 0),
    ("wildcard-lahde saldolla 2 (sailyy, ei kerry)",
     _history([0, 0, 0], chips=[("wildcard", 3)]), 3, 2, 0),
    ("free hit -lahde saldolla 2",
     _history([0, 0, 0], chips=[("freehit", 3)]), 3, 2, 0),
    # GW1 -> 1, GW2 -> 2, GW3 kayttaa 2 -> 0 -> +1 = 1
    ("kulutus: 2 siirtoa saldolla 2 -> 0 -> +1",
     _history([0, 0, 2]), 3, 1, 0),
    # GW1 -> 1, GW2 -> 2, GW3 -> 3, GW4 kayttaa 2 -> 1 -> +1 = 2
    ("osittainen kulutus: 2 siirtoa saldolla 3 -> 1 -> +1",
     _history([0, 0, 0, 2]), 4, 2, 0),
    ("hitit eivat vie miinukselle: 5 siirtoa saldolla 2",
     _history([0, 0, 5]), 3, 1, 0),
    ("yksi siirto joka kierros pitaa saldon 1:ssa",
     _history([0, 1, 1, 1]), 4, 1, 0),
    ("katto 5 ilman siirtoja 8 kierrosta",
     _history([0] * 8), 8, 5, 0),
]


@pytest.mark.parametrize("nimi,historia,source_gw,ft_fpl,vanha", VAIHEET,
                         ids=[v[0] for v in VAIHEET])
def test_ft_left_seuraa_fpln_saldoa_joka_vaiheessa(nimi, historia, source_gw,
                                                   ft_fpl, vanha):
    m = _load_freeze()
    meta = _seed(m, historia, source_gw)
    assert meta["ft_available_fpl"] == ft_fpl
    assert meta["ft_source"] == "inferred_from_history"
    assert meta["ft_left"] == max(0, ft_fpl - m.FT_PER_GW)
    # Identiteetti: moottori saa FPL:n saldon, katto leikkaa.
    assert m._ft_available(meta) == min(ft_fpl, m.FT_MAX)
    # Erotteleva: vanha vakio 0 olisi antanut moottorille tasan 1 aina kun
    # FPL antaa enemman.
    if ft_fpl > 1:
        assert meta["ft_left"] != vanha, nimi
        assert m._ft_available({"ft_left": vanha}) == 1 < m._ft_available(meta)


def test_katto_on_yha_freezen_oma_paatos():
    """FT_MAX (2) on tietoinen konservatiivinen valinta; tama rivi ei muuta
    sita. Katto nakyy erotuksena `ft_available_fpl` vs `_ft_available`."""
    m = _load_freeze()
    meta = _seed(m, _history([0] * 8), 8)
    assert meta["ft_available_fpl"] == 5
    assert m._ft_available(meta) == m.FT_MAX == 2


def test_ketjupolku_lukee_fpln_saldon_ei_perityn_freezen_kirjanpitoa():
    """Peritty gw*.json sanoo ft_left 0 (freezen oma kirjanpito), FPL:n
    historia sanoo 3 -> attach ylikirjoittaa: entry_mismatch-portti takaa
    etta entry on peritty runko, joten FPL on totuus."""
    m = _load_freeze()
    prev = {"meta": {"gw": 4, "ft_left": 0, "budget": 100.0},
            "xi": [{"id": i} for i in range(1, 12)],
            "bench": [{"id": i} for i in range(12, 16)]}
    boot = {"elements": [{"id": i, "now_cost": 50, "cost_change_start": 0}
                         for i in range(1, 16)]}
    tila = hist.entry_state(H_116920, 4, list(range(1, 16)), [], boot)
    m.attach_entry_state(prev, tila)
    assert prev["meta"]["ft_left"] == 2
    assert prev["meta"]["ft_available_fpl"] == 3
    assert m._ft_available(prev["meta"]) == 2


def test_jaadytetty_rivi_kirjaa_fpln_saldon_ja_lahteen(monkeypatch, tmp_path):
    """main(): output-meta kantaa `ft_available_fpl` ja `ft_source`, jotta
    lukija nakee katon leikkauksen artefaktista."""
    from tests.test_freeze_chain_continuity import _aja_freeze_main
    _m, rc, out = _aja_freeze_main(monkeypatch, tmp_path, bootstrap_ids=[15])
    assert rc == 0 and out.exists()
    meta = json.loads(out.read_text(encoding="utf-8"))["meta"]
    assert meta["ft_available_fpl"] == 1
    assert meta["ft_source"] == "test"
    assert meta["ft_available"] == 1


# ---------------------------------------------------------------------------
# 3. Lahdeportti: siemenessa ei ole vakiota, attach on ainoa kirjoittaja
# ---------------------------------------------------------------------------
def test_entry_seed_ei_kirjoita_ft_leftia():
    m = _load_freeze()
    src = inspect.getsource(m.entry_seed)
    body = src.split('"""', 2)[2]
    # Vakio olisi tasan se vika: mika tahansa `ft_left` siemenen koodissa
    # (kommentit mukaan lukien) on epailyttava, joten sallitaan vain
    # tausta-kommentin muoto lainausmerkeissa.
    assert '"ft_left": 0' not in body.replace('`"ft_left": 0`', "")
    assert "ft_left" not in "".join(
        l for l in body.splitlines() if not l.strip().startswith("#"))
    assert "attach_entry_state(" in body


def test_attach_on_ainoa_ft_left_kirjoittaja():
    m = _load_freeze()
    lahde = Path(m.__file__).read_text(encoding="utf-8")
    assert lahde.count('["ft_left"] =') == 1
    attach = inspect.getsource(m.attach_entry_state)
    assert 'meta["ft_left"] =' in attach
    assert "ft_available_next" in attach
    assert "free_transfers_for_gw" in inspect.getsource(hist.entry_state)


def test_ft_katto_on_yksi_vakio_kolmessa_moduulissa():
    """FPL:n FT-katto (5) on saanto, ei malliparametri, ja sille on YKSI
    vakio: `fpl_entry_history.FT_MAX`. Moottori (`fpl_transfers.FT_CARRY_MAX`)
    ja planner lukevat sen sielta. Kolme kirjaimellista `= 5`:ta olisi kolme
    paikkaa jotka voivat erota kun saanto muuttuu."""
    from src.models import fpl_planner as pl
    from src.models import fpl_transfers as tr
    assert tr.FT_CARRY_MAX == pl.FT_CARRY_MAX == hist.FT_MAX == 5
    for mod in (tr, pl):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert not re.search(r"^FT_CARRY_MAX\s*=\s*\d+", src, re.M), (
            f"{mod.__name__}: FT_CARRY_MAX on kirjaimellinen luku, ei lukija")
    assert re.search(r"^FT_MAX\s*=\s*5\b",
                     Path(hist.__file__).read_text(encoding="utf-8"), re.M), \
        "saannon ainoa kirjaimellinen paikka"
