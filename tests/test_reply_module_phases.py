"""Reply-moduulin lukija synteettisilla kierrosvaiheilla (saanto 6a.3).

`load_reply_module` ei saa palauttaa lukua joka ei enaa pida. Testi joka
ajetaan vain "nyt" (maaottelutauolla, 18 vrk ennen deadlinea) olisi vihrea
siihen asti kun vaihe vaihtuu. Siksi sama lukija ajetaan kellolla ja datalla
jokaisessa vaiheessa:

  ennen deadlinea        -> palauttaa, karsii pyydettyihin lukuihin
  kesken kierroksen      -> GW N kieltaytyy (deadline mennyt); GW N+1 toimii,
                            ja last_gw on edellinen PELATTU kierros
  gradauksen jalkeen     -> last_gw = juuri pelattu kierros
  pitka tauko            -> regeneroitu projektio samoilla luvuilla kelpaa,
                            muuttunut valittu luku ei, muuttunut valitsematon
                            ei kaada; FPL-statuksen muutos kaataa; statushaun
                            virhe kaataa (fail-closed)
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone

import pytest

from src.marketing import reply_module as rm
from src.marketing import reply_sections as rs

DL6 = datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc)
DL7 = datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)


def _player(pid, name, team, xp_by_gw, gw_dist, p_start=0.93, own=12.3):
    return {
        "id": pid, "web_name": name, "team": team, "team_short": team, "pos": "MID",
        "status": "a", "price": 8.0, "xmins": 88.0, "p_start": p_start, "owned_pct": own,
        "xp_per_gw": round(sum(xp_by_gw.values()) / len(xp_by_gw), 2),
        "xp_horizon_total": round(sum(xp_by_gw.values()), 2),
        "gameweeks": [{"gw": g, "opponents": [{"opp": "LEE", "venue": "H"}], "xp": x}
                      for g, x in sorted(xp_by_gw.items())],
        "xp_dist": {"gw": gw_dist, "n": 2000, "p_haul": 0.14, "p_blank": 0.17},
    }


def _xp(deadline_gw: int, deadline: datetime, generated: str, bump: dict | None = None):
    bump = bump or {}
    ps = [
        _player(1, "Alpha", "ARS", {6: 6.84, 7: 5.0}, deadline_gw),
        _player(2, "Beta", "MUN", {6: 6.01, 7: 5.2}, deadline_gw),
        _player(3, "Gamma", "MCI", {6: 5.48, 7: 6.0}, deadline_gw),
        _player(4, "Delta", "LIV", {6: 4.10, 7: 4.4}, deadline_gw),
        _player(5, "Eps", "CHE", {6: 3.90, 7: 3.9}, deadline_gw),
        _player(6, "Zeta", "NEW", {6: 3.10, 7: 3.2}, deadline_gw),
    ]
    for p in ps:
        for g in p["gameweeks"]:
            if (p["id"], g["gw"]) in bump:
                g["xp"] = bump[(p["id"], g["gw"])]
    return {"meta": {"available": True, "generated_at": generated,
                     "deadline_gameweek": deadline_gw, "next_gameweek": deadline_gw,
                     "deadline_utc": deadline.isoformat()},
            "players": ps}


def _phase0(gw: int, generated: str, ars_cs: float = 46.5):
    return {"meta": {"generated_at": generated},
            "teams": [{"name": "Arsenal", "short": "ARS",
                       "fixtures": [{"gw": gw, "opponent": "Leeds", "opponent_short": "LEE",
                                     "venue": "H", "cs_pct": ars_cs}]},
                      {"name": "Hull", "short": "HUL",
                       "fixtures": [{"gw": gw, "opponent": "Everton", "opponent_short": "EVE",
                                     "venue": "H", "cs_pct": 38.6}]}]}


def _write(d, name, obj):
    (d / name).write_text(json.dumps(obj), encoding="utf-8")


STATUS = {i: {"status": "a", "chance": None, "news": ""} for i in range(1, 7)}


def _build(tmp_path, gw, deadline, xp, phase0):
    """Rakenna moduuli SAMOILLA osiofunktioilla kuin generaattori."""
    dd = tmp_path / "data"
    md = tmp_path / "modules"
    dd.mkdir(exist_ok=True)
    md.mkdir(exist_ok=True)
    _write(dd, "fpl_xp_projections.json", xp)
    _write(dd, "fpl_projections_phase0.json", phase0)
    from src.models.fpl_xp import load_xp_actionable
    x = load_xp_actionable(dd / "fpl_xp_projections.json")
    sections = {"captain_top5": rs.captain_top5(x, gw, []),
                "player_lookup": rs.player_lookup(x, gw, []),
                "cs_top": rs.cs_top(phase0, gw)}
    # Kaikille luvuille reitti (synteettinen "sivu" = sama teksti).
    for _k, v, _r, _s in rm.iter_values(sections):
        v["public_url"] = "https://goaliq.app/test"
        v["verified_at"] = "2026-09-22T00:00:00+00:00"
        v.pop("routes", None)
    module = {"schema": rm.SCHEMA, "gw": gw, "deadline_utc": deadline.isoformat(),
              "generated_at": "2026-09-22T08:00:00+00:00",
              "sources": {"xp": {"stamp": rm.source_stamp("xp", dd)},
                          "phase0": {"stamp": rm.source_stamp("phase0", dd)}},
              "named_players": {str(i): dict(s, web_name=f"p{i}") for i, s in STATUS.items()},
              "sections": sections}
    (md / f"gw{gw}.json").write_text(json.dumps(module), encoding="utf-8")
    return dd, md


def _load(dd, md, gw, now, keys=None, status=None, sections=None):
    return rm.load_reply_module(gw, keys=keys, sections=sections, now=now, data_dir=dd,
                                module_dir=md, fpl_status=lambda: status or STATUS)


K_ALPHA = "captain_top5.alpha-ars.gw_xp"
K_ZETA = "player_lookup.zeta-new.gw_xp"
K_ARS = "cs_top.ars.cs_pct"


# ---------------------------------------------------------------------------
def test_before_deadline_returns_only_requested_numbers(tmp_path):
    dd, md = _build(tmp_path, 6, DL6, _xp(6, DL6, "g1"), _phase0(6, "p1"))
    now = DL6 - timedelta(days=18)
    m = _load(dd, md, 6, now, keys=[K_ALPHA, K_ARS])
    idx = rm.value_index(m["sections"])
    assert set(idx) == {K_ALPHA, K_ARS}
    assert idx[K_ALPHA]["text"] == "6.8" and idx[K_ARS]["text"] == "46.5%"
    assert "named_players" not in m


def test_deadline_passed_refuses_even_one_second_after(tmp_path):
    dd, md = _build(tmp_path, 6, DL6, _xp(6, DL6, "g1"), _phase0(6, "p1"))
    with pytest.raises(rm.ReplyModuleRefused, match="deadline passed"):
        _load(dd, md, 6, DL6 + timedelta(seconds=1), keys=[K_ARS])
    # Juuri ennen: toimii.
    _load(dd, md, 6, DL6 - timedelta(seconds=1), keys=[K_ARS])


def test_mid_round_next_gameweek_module_is_the_one_that_works(tmp_path):
    """Kesken GW6:n (deadline mennyt, ottelut kesken): GW6 kieltaytyy, GW7 toimii."""
    dd, md = _build(tmp_path, 6, DL6, _xp(6, DL6, "g1"), _phase0(6, "p1"))
    now = DL6 + timedelta(hours=30)
    with pytest.raises(rm.ReplyModuleRefused):
        _load(dd, md, 6, now, keys=[K_ARS])
    tmp7 = tmp_path / "g7"
    tmp7.mkdir()
    dd7, md7 = _build(tmp7, 7, DL7, _xp(7, DL7, "g2"), _phase0(7, "p2"))
    m = _load(dd7, md7, 7, now, keys=["captain_top5.gamma-mci.gw_xp"])
    assert rm.value_index(m["sections"])["captain_top5.gamma-mci.gw_xp"]["text"] == "6.0"


def _events(gw_finished_checked: dict):
    return [{"id": g, "finished": f, "data_checked": c, "average_entry_score": 50 + g}
            for g, (f, c) in sorted(gw_finished_checked.items())]


def _entry(g, pts=40):
    return {"entry_history": {"event": g, "points": pts, "event_transfers_cost": 0},
            "picks": [{"element": 9, "multiplier": 2}]}


def test_last_gw_mid_round_is_the_previous_played_round():
    """Kesken GW6:n moduuli GW7:lle: GW6 ei ole pelattu -> last_gw = GW5."""
    ev = _events({4: (True, True), 5: (True, True), 6: (False, False)})
    out = rs.last_gw(_entry(5), ev, None, 7)
    assert out["available"] and out["gw"] == 5
    # GW6:n pisteita ei ole haettu -> ei vaaraa kierrosta vaan kieltaytyminen.
    out6 = rs.last_gw(_entry(6), ev, None, 7)
    assert not out6["available"]


def test_last_gw_after_grading_is_the_round_just_played():
    ev = _events({5: (True, True), 6: (True, True)})
    out = rs.last_gw(_entry(6, pts=61), ev, None, 7)
    assert out["gw"] == 6 and out["values"]["entry_points"]["text"] == "61"
    assert out["values"]["fpl_average"]["text"] == "56"
    # finished mutta FPL ei ole tarkistanut (bonus kesken): ei viela tulos.
    ev2 = _events({5: (True, True), 6: (True, False)})
    assert rs.last_gw(_entry(6), ev2, None, 7)["gw"] == 5


def test_captain_multiplier_comes_from_entry_picks():
    calls = {"gameweeks": [{"gw": 5, "calls": [{"call": "model_captain", "player_id": 9,
                                                "web_name": "Haaland", "team_short": "MCI"}]}]}
    ev = _events({5: (True, True)})
    e = _entry(5)
    e["picks"] = [{"element": 9, "multiplier": 3}]
    out = rs.last_gw(e, ev, calls, 6, live_points={9: 9})
    assert out["captain"]["values"]["captain_return"]["text"] == "27"


def test_long_break_regenerated_same_numbers_still_loads(tmp_path):
    dd, md = _build(tmp_path, 6, DL6, _xp(6, DL6, "g1"), _phase0(6, "p1"))
    # Paivittainen availability-ajo: uusi generated_at, samat luvut.
    _write(dd, "fpl_xp_projections.json", _xp(6, DL6, "g2-regenerated"))
    m = _load(dd, md, 6, DL6 - timedelta(days=10), keys=[K_ALPHA])
    assert rm.value_index(m["sections"])[K_ALPHA]["text"] == "6.8"


def test_long_break_changed_selected_number_refuses(tmp_path):
    dd, md = _build(tmp_path, 6, DL6, _xp(6, DL6, "g1"), _phase0(6, "p1"))
    # 6.84 -> 6.86 pyoristyy yha 6.9:ksi? Ei: 6.84 -> "6.8", 6.86 -> "6.9".
    _write(dd, "fpl_xp_projections.json", _xp(6, DL6, "g2", bump={(1, 6): 6.86}))
    with pytest.raises(rm.ReplyModuleRefused, match="changed"):
        _load(dd, md, 6, DL6 - timedelta(days=10), keys=[K_ALPHA])


def test_display_threshold_sub_rounding_change_does_not_refuse(tmp_path):
    """Kynnys on nayttotarkkuus: 6.84 -> 6.81 nakyy yha "6.8"."""
    dd, md = _build(tmp_path, 6, DL6, _xp(6, DL6, "g1"), _phase0(6, "p1"))
    _write(dd, "fpl_xp_projections.json", _xp(6, DL6, "g2", bump={(1, 6): 6.81}))
    _load(dd, md, 6, DL6 - timedelta(days=10), keys=[K_ALPHA])


def test_changed_unselected_number_does_not_block_selected_ones(tmp_path):
    dd, md = _build(tmp_path, 6, DL6, _xp(6, DL6, "g1"), _phase0(6, "p1"))
    _write(dd, "fpl_xp_projections.json", _xp(6, DL6, "g2", bump={(6, 6): 1.0}))
    _load(dd, md, 6, DL6 - timedelta(days=10), keys=[K_ALPHA])
    with pytest.raises(rm.ReplyModuleRefused):
        _load(dd, md, 6, DL6 - timedelta(days=10), keys=[K_ZETA])


def test_phase0_regenerated_with_new_clean_sheet_refuses(tmp_path):
    dd, md = _build(tmp_path, 6, DL6, _xp(6, DL6, "g1"), _phase0(6, "p1"))
    _write(dd, "fpl_projections_phase0.json", _phase0(6, "p2", ars_cs=44.9))
    with pytest.raises(rm.ReplyModuleRefused, match="46.5"):
        _load(dd, md, 6, DL6 - timedelta(days=5), keys=[K_ARS])


def test_named_player_status_change_refuses(tmp_path):
    dd, md = _build(tmp_path, 6, DL6, _xp(6, DL6, "g1"), _phase0(6, "p1"))
    hurt = copy.deepcopy(STATUS)
    hurt[1] = {"status": "d", "chance": 50, "news": "Knock - 50% chance of playing"}
    with pytest.raises(rm.ReplyModuleRefused, match="status changed"):
        _load(dd, md, 6, DL6 - timedelta(days=3), keys=[K_ALPHA], status=hurt)
    # Joukkuetason luku (ei nimettya pelaajaa) ei riipu pelaajan tilasta.
    _load(dd, md, 6, DL6 - timedelta(days=3), keys=[K_ARS], status=hurt)


def test_status_fetch_failure_is_fail_closed(tmp_path):
    dd, md = _build(tmp_path, 6, DL6, _xp(6, DL6, "g1"), _phase0(6, "p1"))

    def boom():
        raise OSError("network down")
    with pytest.raises(rm.ReplyModuleRefused, match="status check failed"):
        rm.load_reply_module(6, keys=[K_ALPHA], now=DL6 - timedelta(days=1), data_dir=dd,
                             module_dir=md, fpl_status=boom)


def test_unknown_key_and_missing_module_refuse(tmp_path):
    dd, md = _build(tmp_path, 6, DL6, _xp(6, DL6, "g1"), _phase0(6, "p1"))
    with pytest.raises(rm.ReplyModuleRefused, match="keys not in module"):
        _load(dd, md, 6, DL6 - timedelta(days=1), keys=["captain_top5.nobody-xxx.gw_xp"])
    with pytest.raises(rm.ReplyModuleRefused, match="no reply module"):
        _load(dd, md, 7, DL6 - timedelta(days=1), keys=[K_ARS])


def test_distribution_from_a_different_gameweek_is_not_offered():
    """Kesken kierroksen xp_dist on kuluvan kierroksen: sita ei tarjota GW N+1:lle."""
    p = _player(1, "Alpha", "ARS", {7: 5.0}, gw_dist=6)
    vals = rs.player_values(p, 7)
    assert "p_10plus" not in vals and "p_blank" not in vals
    assert "gw_xp" in vals
