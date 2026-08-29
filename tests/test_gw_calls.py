"""GW-CALLS-LOKI (28.8.2026): kutsut lokiin ennen deadlinea, gradaus jalkeen.

Kolme asiaa jotka portin pitaa pitaa kiinni:
1. idempotenssi ennen deadlinea (sama GW paivittyy, ei tuplaa)
2. fail-closed deadlinen jalkeen (ei kirjausta, ei paivitysta, ei ohitusta)
3. negatiivinen kontrolli: gradaus EI merkitse osumaa kun pisteet eivat
   riita (muisti gate-substring-osuma-on-sokea: portti joka ei voi olla
   punainen ei mittaa mitaan).
"""
from __future__ import annotations

import datetime as _dt

import json
import pytest

from src.models.gw_calls import (DeadlinePassed, build_entry, grade_entry,
                                 gw_status, parse_utc, upsert)

DL = "2026-08-28T17:30:00Z"
BEFORE = parse_utc("2026-08-28T14:00:00Z")
AFTER = parse_utc("2026-08-28T17:30:00Z")  # tasan deadline = ohi


def _p(pid, name, pos="MID", p_haul=0.1, p_blank=0.3, p90=10, gw_xp=4.5):
    return {"id": pid, "web_name": name, "team_short": "XXX", "pos": pos,
            "gameweeks": [{"gw": 2, "xp": gw_xp}],
            "xp_dist": {"gw": 2, "n": 2000, "p_haul": p_haul,
                        "p_blank": p_blank, "p10": 1, "median": 4,
                        "p90": p90, "haul_pts": 10, "blank_pts": 2}}


def _frozen():
    return {"meta": {"gw": 2, "deadline": DL, "frozen_at": "2026-08-27T17:04:43Z",
                     "transfers": [{"out": 229, "in": 388, "hit": False}]},
            "captain": 388, "vice_captain": 115,
            "xi": [{"id": 388, "web_name": "Guehi", "team_short": "MCI",
                    "pos": 2, "xp": 4.76},
                   {"id": 115, "web_name": "De Cuyper", "team_short": "BHA",
                    "pos": 2, "xp": 4.6}],
            "bench": []}


def _standouts():
    return {"captain": _p(1, "Cap", p_haul=0.11),
            "ceiling": _p(2, "Ceil", p90=10),
            "safest": _p(3, "Safe", p_blank=0.2),
            "gamble": _p(4, "Gamb", p_haul=0.11, p_blank=0.4)}


def test_entry_kirjaa_viisi_kutsua_ja_siirrot():
    e = build_entry(_frozen(), _standouts(), {"generated_at": "x"}, BEFORE,
                    {229: {"web_name": "Tarkowski"}})
    calls = {c["call"]: c for c in e["calls"]}
    assert set(calls) == {"model_captain", "captain_pick", "ceiling",
                          "safest", "gamble"}
    assert calls["model_captain"]["web_name"] == "Guehi"
    assert calls["safest"]["metric"] == "p_3plus"
    assert calls["safest"]["value"] == pytest.approx(0.8)
    assert e["logged_at"] == "2026-08-28T14:00:00Z"
    assert e["deadline_utc"] == "2026-08-28T17:30:00Z"
    assert e["model_transfers"][0]["out_name"] == "Tarkowski"
    assert e["model_transfers"][0]["in_name"] == "Guehi"
    assert e["graded"] is None


def test_upsert_on_idempotentti_ennen_deadlinea():
    log = {"gameweeks": []}
    e1 = build_entry(_frozen(), _standouts(), {}, BEFORE)
    upsert(log, e1, BEFORE)
    later = BEFORE + _dt.timedelta(hours=1)
    s2 = _standouts()
    s2["captain"] = _p(9, "NewCap", p_haul=0.2)
    e2 = build_entry(_frozen(), s2, {}, later)
    upsert(log, e2, later)
    assert len(log["gameweeks"]) == 1, "sama GW ei saa tuplaantua"
    cap = [c for c in log["gameweeks"][0]["calls"] if c["call"] == "captain_pick"][0]
    assert cap["web_name"] == "NewCap", "viimeisin kortti voittaa ennen deadlinea"
    # DEADLINE-SNAPSHOT (29.8): ensimmainen kirjaus sailyy, viimeisin erikseen.
    assert log["gameweeks"][0]["logged_at"] == "2026-08-28T14:00:00Z"
    assert log["gameweeks"][0]["updated_at"] == "2026-08-28T15:00:00Z"


def test_kirjaus_deadlinen_jalkeen_on_kielletty():
    with pytest.raises(DeadlinePassed):
        build_entry(_frozen(), _standouts(), {}, AFTER)
    log = {"gameweeks": []}
    e = build_entry(_frozen(), _standouts(), {}, BEFORE)
    upsert(log, e, BEFORE)
    with pytest.raises(DeadlinePassed):
        upsert(log, e, AFTER)
    assert log["gameweeks"][0]["logged_at"] == "2026-08-28T14:00:00Z"
    assert log["gameweeks"][0]["updated_at"] == "2026-08-28T14:00:00Z"


def test_gradattua_rivia_ei_kirjoiteta_yli():
    log = {"gameweeks": []}
    e = build_entry(_frozen(), _standouts(), {}, BEFORE)
    upsert(log, e, BEFORE)
    grade_entry(log["gameweeks"][0], {1: 12}, {1: 90}, provisional=False,
                now=AFTER + _dt.timedelta(days=3))
    with pytest.raises(DeadlinePassed):
        upsert(log, build_entry(_frozen(), _standouts(), {}, BEFORE), BEFORE)


def test_gradaus_osuma_ja_negatiivinen_kontrolli():
    e = build_entry(_frozen(), _standouts(), {}, BEFORE)
    pts = {388: 6, 1: 12, 2: 9, 3: 2, 4: 10}
    mins = {k: 90 for k in pts}
    grade_entry(e, pts, mins, provisional=True, now=AFTER)
    g = e["graded"]["by_call"]
    assert g["captain_pick"]["met"] is True      # 12 >= 10
    assert g["gamble"]["met"] is True            # 10 >= 10
    assert g["ceiling"]["met"] is False          # 9 < p90 10
    assert g["safest"]["met"] is False           # 2 = blank, ei 3+
    assert g["model_captain"]["captain_total"] == 12
    assert g["model_captain"]["met"] is None
    assert e["graded"]["provisional"] is True


def test_puuttuva_pelaaja_on_none_ei_nolla():
    e = build_entry(_frozen(), _standouts(), {}, BEFORE)
    grade_entry(e, {}, {}, provisional=True, now=AFTER)
    for r in e["graded"]["by_call"].values():
        assert r["points"] is None and r["met"] is None


def test_provisionaalinen_gradataan_uudelleen_lopullista_ei():
    e = build_entry(_frozen(), _standouts(), {}, BEFORE)
    grade_entry(e, {1: 12}, {1: 90}, provisional=True, now=AFTER)
    grade_entry(e, {1: 13}, {1: 90}, provisional=False, now=AFTER)
    assert e["graded"]["by_call"]["captain_pick"]["points"] == 13
    grade_entry(e, {1: 99}, {1: 90}, provisional=False, now=AFTER)
    assert e["graded"]["by_call"]["captain_pick"]["points"] == 13


def test_gw_status_kaikki_ottelut_pelattu():
    boot = {"events": [{"id": 2, "data_checked": False}]}
    fx = [{"event": 2, "finished_provisional": True} for _ in range(10)]
    st = gw_status(boot, fx)
    assert st[2] == {"gradable": True, "provisional": True}
    fx[3]["finished_provisional"] = False
    assert gw_status(boot, fx)[2]["gradable"] is False


def test_sivun_osio_sanoo_before_vain_kun_aikaleimat_todistavat():
    from scripts.build_fpl_page import _fmt_logged, gw_calls_html
    row = {"gw": 2, "logged_at": "2026-08-28T14:05:00Z",
           "deadline_utc": DL, "calls": [], "graded": None}
    assert "3 h 25 min before the deadline" in _fmt_logged(row)
    row["logged_at"] = "2026-08-28T18:00:00Z"
    assert "after the deadline" in _fmt_logged(row)
    assert "before" not in _fmt_logged(row)
    assert gw_calls_html({"gameweeks": []}) == ""
    # DEADLINE-SNAPSHOT (29.8): Logged-sarake nayttaa viimeisimman kirjauksen.
    row = {"gw": 2, "logged_at": "2026-08-27T17:04:00Z",
           "updated_at": "2026-08-28T16:00:00Z", "deadline_utc": DL,
           "calls": [], "graded": None}
    assert "1 h 30 min before the deadline" in _fmt_logged(row)
    assert "28 Aug 16:00" in _fmt_logged(row)
    e = build_entry(_frozen(), _standouts(), {}, BEFORE)
    html = gw_calls_html({"gameweeks": [e]})
    assert "pending" in html and "Guehi (MCI)" in html
    assert "—" not in html


# ---------------------------------------------------------------- poikkeusnootti (29.8)
# Portti k2 (M70): sivu ei kertonut etta GW2-rivi (Guehi C) ja entry (wildcard,
# B.Fernandes C) eroavat; lukija loysi sen vasta entry-linkista. Nootti tulee
# samasta tiedostosta jolla entry-vahti sallii eron, ja vain sen englannin-
# kielisesta public_note-kentasta.

def _log_row(gw: int) -> dict:
    return {"gw": gw, "deadline_utc": "2026-08-28T17:30:00Z",
            "logged_at": "2026-08-28T17:13:07Z", "graded": None,
            "calls": [{"call": "model_captain", "player_id": 388, "web_name": "Guéhi",
                       "team_short": "MCI", "pos": "DEF", "metric": "gw_xp",
                       "value": 4.76, "criterion": "captain return, points doubled"}]}


def test_exception_note_renders_under_its_gameweek():
    from scripts.build_fpl_page import gw_calls_html
    html = gw_calls_html({"gameweeks": [_log_row(2)]}, {2: "The row is scored as written."})
    assert 'class="gw-note"' in html and "The row is scored as written." in html
    # nootti tulee ENNEN kierroksen kutsurivia (rivin alla visuaalisesti = sama lohko)
    assert html.index("gw-note") < html.index("Model squad captain")


def test_exception_note_only_for_matching_gameweek():
    """NEGATIIVINEN KONTROLLI: GW3:n nootti ei tartu GW2:n riviin."""
    from scripts.build_fpl_page import gw_calls_html
    html = gw_calls_html({"gameweeks": [_log_row(2)]}, {3: "wrong gw"})
    assert "gw-note" not in html and "wrong gw" not in html


def test_exception_note_escapes_html():
    from scripts.build_fpl_page import gw_calls_html
    html = gw_calls_html({"gameweeks": [_log_row(2)]}, {2: "<b>x</b>"})
    assert "&lt;b&gt;x&lt;/b&gt;" in html and "<b>x</b>" not in html


def test_gw_exception_notes_reads_only_public_note(tmp_path):
    from scripts.build_fpl_page import gw_exception_notes
    (tmp_path / "gw2.json").write_text(json.dumps({
        "gw": 2, "reason": "suomenkielinen syy", "decided_by": "Ville",
        "decided_at": "2026-08-28", "public_note": "  English note  "}), encoding="utf-8")
    (tmp_path / "gw3.json").write_text(json.dumps({
        "gw": 3, "reason": "vain suomea", "decided_by": "Ville", "decided_at": "x"}),
        encoding="utf-8")                      # ei public_note -> ei riviä
    (tmp_path / "gw4.json").write_text(json.dumps({
        "gw": 9, "public_note": "gw mismatch"}), encoding="utf-8")   # gw != nimi
    (tmp_path / "gw5.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "gw6.exception.json").write_text(json.dumps({"gw": 6, "public_note": "z"}),
                                                 encoding="utf-8")   # vaara nimi
    notes = gw_exception_notes(tmp_path)
    assert notes == {2: "English note"}
    assert "suomenkielinen" not in json.dumps(notes)


def test_gw_exception_notes_missing_dir_is_empty(tmp_path):
    from scripts.build_fpl_page import gw_exception_notes
    assert gw_exception_notes(tmp_path / "nope") == {}


def test_live_gw2_exception_has_english_public_note():
    """Repon oikea poikkeus kantaa nootin jonka sivu renderoi (portti 29.8)."""
    from scripts.build_fpl_page import gw_exception_notes, EXCEPTIONS_DIR
    if not (EXCEPTIONS_DIR / "gw2.json").exists():
        pytest.skip("gw2-poikkeus poistettu")
    notes = gw_exception_notes()
    assert 2 in notes and "B.Fernandes" in notes[2]
    assert "\u2014" not in notes[2]          # ei em dashia


# ---------------------------------------------------------------- entry_actual (29.8)
# `model_transfers` on mallin AIKOMUS freezesta. GW2:ssa se listasi 3 siirtoa ja
# 2 hittia, mutta tili pelasi wildcardin: 0 siirtoa, 0 hittia. Sivun lahdelinkki
# nayttaa lohkon ilman kontekstia -> lukija lukee sen tilin tekemisiksi
# (julkaisuportti 29.8). `entry_actual` on FPL:n oma luku samasta kierroksesta.

def test_entry_actual_reads_both_sources():
    from src.models.gw_calls import entry_actual
    out = entry_actual(
        {"event": 2, "event_transfers": 0, "event_transfers_cost": 0, "points": 15},
        {"active_chip": "wildcard",
         "picks": [{"element": 426, "is_captain": True},
                   {"element": 411, "is_vice_captain": True}]})
    assert out == {"transfers": 0, "transfers_cost": 0, "points": 15,
                   "chip": "wildcard", "captain": 426}


def test_entry_actual_without_sources_is_none_not_zero():
    """NEGATIIVINEN KONTROLLI: puuttuva data ei saa nayttaa nollalta siirrolta."""
    from src.models.gw_calls import entry_actual
    assert entry_actual(None, None) is None


def test_entry_actual_partial_sources():
    from src.models.gw_calls import entry_actual
    only_hist = entry_actual({"event_transfers": 2, "event_transfers_cost": 4}, None)
    assert only_hist["transfers"] == 2 and "chip" not in only_hist
    only_picks = entry_actual(None, {"active_chip": None, "picks": []})
    assert only_picks["chip"] is None and only_picks["captain"] is None
    assert "transfers" not in only_picks


def test_live_gw2_row_carries_entry_actual():
    """Repon GW2-rivi kantaa tilin oikeat luvut: wildcard, ei siirtoja."""
    import config
    log = json.loads((config.DATA_DIR / "gw_calls.json").read_text(encoding="utf-8"))
    row = next((r for r in log["gameweeks"] if int(r["gw"]) == 2), None)
    if row is None:
        pytest.skip("GW2-rivi poistettu")
    ea = row.get("entry_actual")
    assert ea, "GW2-rivilta puuttuu entry_actual"
    assert ea["chip"] == "wildcard" and ea["transfers"] == 0
    assert row["model_transfers"], "model_transfers pitaa sailya (mallin aikomus)"

