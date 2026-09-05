# -*- coding: utf-8 -*-
"""KORTTI-PROVENIENSSI-PORTTI (5.9.2026).

4.9 julkaisuun oli menossa kortti "The model's own FPL squad, GW3 - entry
116920", jonka 7/15 nimea eivat olleet entryn. Julkaisutarkistaja antoi LAPI,
koska se tarkisti etta entry on olemassa, ei etta kortin joukkue on entryn
joukkue. Nyt kortin generaattori vaatii todisteen freezen metasta, ja
verify_model_entry_matches_freeze kirjoittaa sen sinne deadlinen jalkeen.

DoD-fikstuuri: GW2->GW3-ketju sellaisena kuin se oli 4.9 aamulla (chain
verifioimattomasta GW1:sta) on None -> kortti kaatuu.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import fpl_model_entry as m  # noqa: E402

ENTRY = m.ENTRY_ID


def _frozen(gw, source=None, from_gw=None, verified=None, captain=1):
    meta = {"gw": gw, "deadline": "2026-09-04T17:30:00Z",
            "frozen_at": "2026-09-04T12:55:13Z"}
    if source is not None:
        meta["squad_source"] = source
    if from_gw is not None:
        meta["from_gw"] = from_gw
    if verified is not None:
        meta["entry_verified"] = verified
    xi = [{"id": i, "web_name": f"p{i}", "pos": 2, "price": 50, "team_short": "ARS"}
          for i in range(1, 12)]
    bench = [{"id": i, "web_name": f"p{i}", "pos": 3, "price": 45, "team_short": "AVL"}
             for i in range(12, 16)]
    return {"meta": meta, "captain": captain, "vice_captain": 2,
            "xi": xi, "bench": bench}


def _ok(gw):
    return m.verified_record(gw, ENTRY, squad_match=True, captain_match=True,
                             at="2026-09-04T18:10:00Z", common=15)


# --- puhdas funktio ---------------------------------------------------------

def test_free_optimum_root_is_not_the_entry():
    assert m.provenance(_frozen(1, "free_optimum")) is None
    assert m.provenance(_frozen(1)) is None  # vanha meta ilman kenttaa


def test_the_4_9_chain_would_have_failed():
    """gw2 = chain gw1:sta, gw1 = free_optimum ilman verifiointia."""
    gw1 = _frozen(1, "free_optimum")
    gw2 = _frozen(2, "chain", from_gw=1)
    assert m.provenance(gw2, gw1) is None


def test_reseed_from_entry_picks_is_the_entry():
    assert m.provenance(_frozen(3, "entry_picks")) == m.PROVENANCE_ENTRY_PICKS


def test_verified_beats_everything():
    f = _frozen(3, "chain", from_gw=2, verified=_ok(3))
    assert m.provenance(f, None) == m.PROVENANCE_VERIFIED


def test_chain_from_verified_link_is_accepted():
    gw3 = _frozen(3, "entry_picks", verified=_ok(3))
    gw4 = _frozen(4, "chain", from_gw=3)
    assert m.provenance(gw4, gw3) == m.PROVENANCE_CHAIN


def test_chain_from_unverified_reseed_is_not_enough():
    """Reseed ITSE on entryn runko, mutta seuraava lenkki lisaa mallin
    siirrot: ne ovat entryn siirrot vasta kun entry on syottanyt ne."""
    gw3 = _frozen(3, "entry_picks")
    gw4 = _frozen(4, "chain", from_gw=3)
    assert m.provenance(gw4, gw3) is None


def test_chain_prev_must_be_the_named_link():
    gw2 = _frozen(2, "entry_picks", verified=_ok(2))
    gw4 = _frozen(4, "chain", from_gw=3)
    assert m.provenance(gw4, gw2) is None


def test_mismatch_record_is_an_explicit_no():
    rec = m.verified_record(3, ENTRY, squad_match=False, captain_match=True,
                            at="x", common=7)
    assert rec["match"] is False
    gw3 = _frozen(3, "chain", from_gw=2, verified=rec)
    assert m.provenance(gw3, None) is None
    gw4 = _frozen(4, "chain", from_gw=3)
    assert m.provenance(gw4, gw3) is None


def test_captain_mismatch_is_not_a_match():
    rec = m.verified_record(3, ENTRY, squad_match=True, captain_match=False,
                            at="x", common=15)
    assert rec["match"] is False


def test_verified_for_another_gw_does_not_count():
    f = _frozen(4, "chain", from_gw=3, verified=_ok(3))
    assert m.provenance(f, None) is None


# --- portti generaattorissa -------------------------------------------------

def test_require_loads_prev_from_dir_and_fails_closed(tmp_path):
    (tmp_path / "gw1.json").write_text(json.dumps(_frozen(1, "free_optimum")))
    gw2 = _frozen(2, "chain", from_gw=1)
    with pytest.raises(m.ProvenienssiPuuttuu) as e:
        m.require_entry_provenance(gw2, tmp_path)
    assert "GW2" in str(e.value) and str(ENTRY) in str(e.value)


def test_require_accepts_chain_from_verified_on_disk(tmp_path):
    (tmp_path / "gw3.json").write_text(
        json.dumps(_frozen(3, "entry_picks", verified=_ok(3))))
    gw4 = _frozen(4, "chain", from_gw=3)
    assert m.require_entry_provenance(gw4, tmp_path) == m.PROVENANCE_CHAIN


def test_card_generator_is_wired():
    """Portti joka on olemassa muttei kytketty on inertti."""
    import config
    src = (config.PROJECT_ROOT / "scripts/render_frozen_squad_card.py"
           ).read_text(encoding="utf-8")
    assert "require_entry_provenance(frozen, FROZEN_DIR)" in src
    # portti ennen ensimmaista renderointiaskelta
    assert src.index("require_entry_provenance(frozen") < src.index("xi, bench = frozen")


def test_card_main_fails_closed_on_the_4_9_chain(tmp_path, monkeypatch):
    from scripts import render_frozen_squad_card as card
    fdir = tmp_path / "frozen"
    fdir.mkdir()
    (fdir / "gw1.json").write_text(json.dumps(_frozen(1, "free_optimum")))
    (fdir / "gw2.json").write_text(json.dumps(_frozen(2, "chain", from_gw=1)))
    monkeypatch.setattr(card, "FROZEN_DIR", fdir)
    monkeypatch.setattr(sys, "argv", ["x", "--gw", "2", "--out", str(tmp_path / "o")])
    with pytest.raises(m.ProvenienssiPuuttuu):
        card.main()
    assert not (tmp_path / "o" / "model-squad-gw2.html").exists()


# --- verify kirjoittaa metaan -----------------------------------------------

def test_verify_writes_record_only_when_fact_changes(tmp_path):
    import datetime as dt
    from scripts import verify_model_entry_matches_freeze as v
    p = tmp_path / "gw3.json"
    f = _frozen(3, "entry_picks")
    p.write_text(json.dumps(f), encoding="utf-8")
    now = dt.datetime(2026, 9, 4, 18, 0, tzinfo=dt.timezone.utc)
    v.record_verification(p, f, 3, squad_match=True, captain_match=True,
                          common=15, now=now)
    saved = json.loads(p.read_text(encoding="utf-8"))
    assert saved["meta"]["entry_verified"]["match"] is True
    assert saved["meta"]["entry_verified"]["at"] == "2026-09-04T18:00:00Z"
    # sama tosiasia myohemmin -> ei uudelleenkirjoitusta (aikaleima pysyy)
    later = now + dt.timedelta(days=1)
    v.record_verification(p, json.loads(p.read_text()), 3, squad_match=True,
                          captain_match=True, common=15, now=later)
    assert json.loads(p.read_text())["meta"]["entry_verified"]["at"] == "2026-09-04T18:00:00Z"
    # tosiasia muuttuu -> kirjoitetaan
    v.record_verification(p, json.loads(p.read_text()), 3, squad_match=False,
                          captain_match=True, common=7, now=later)
    saved = json.loads(p.read_text(encoding="utf-8"))
    assert saved["meta"]["entry_verified"]["match"] is False
    assert saved["meta"]["entry_verified"]["common"] == 7


def test_verify_main_records_on_real_flow(tmp_path, monkeypatch):
    from scripts import verify_model_entry_matches_freeze as v
    fdir = tmp_path / "frozen"
    fdir.mkdir()
    f = _frozen(3, "entry_picks", captain=1)
    (fdir / "gw3.json").write_text(json.dumps(f), encoding="utf-8")
    monkeypatch.setattr(v, "FROZEN_DIR", fdir)
    monkeypatch.setattr(v, "EXCEPTIONS_DIR", tmp_path / "exc")
    picks = [{"element": i, "is_captain": i == 1} for i in range(1, 16)]
    monkeypatch.setattr(v, "fetch_picks", lambda entry, gw: (picks, 200))
    monkeypatch.setattr(sys, "argv", ["x", "--gw", "3"])
    assert v.main() == 0
    saved = json.loads((fdir / "gw3.json").read_text(encoding="utf-8"))
    assert saved["meta"]["entry_verified"]["match"] is True
    assert m.provenance(saved) == m.PROVENANCE_VERIFIED
