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
