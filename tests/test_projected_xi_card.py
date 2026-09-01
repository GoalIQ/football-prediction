# -*- coding: utf-8 -*-
"""PROJECTED-XI-KORTTI (29.8.2026): portit joiden pitaa pysya kiinni.

1. top 15 jarjestyy GW-xP:lla (gameweeks[].xp), EI xp_per_gw:lla (mutaatio
   kaataa: horisonttikuningas ei nouse)
2. Thiaw / estolista ei paady kortille (top 15, XI, penkki) eika lapi
   tekstiportista; negatiivinen kontrolli: 'Projected' ei osu 'Pro'-estoon
3. ei-'a'-status jaa pois
4. gw_calls-kutsun muoto validi, upsert fail-closed deadlinen jalkeen,
   gradaus autosubeilla ja varakapteenilla
5. --dry-run ei kirjoita lokia
6. kortti ei saa erota lokista ennen deadlinea
"""
from __future__ import annotations

import datetime as _dt
import json

import pytest

from scripts.render_projected_xi_card import (build_html, eligible, free_hit_xi,
                                              gate, main, reconcile_with_log,
                                              top_projected, xi_call)
from src.models.gw_calls import (NEW_LOG, DeadlinePassed, grade_entry,
                                 score_projected_xi, upsert_call)

GW = 2
DL = "2026-08-28T17:30:00Z"
BEFORE = _dt.datetime(2026, 8, 28, 14, 0, tzinfo=_dt.timezone.utc)
AFTER = _dt.datetime(2026, 8, 28, 18, 0, tzinfo=_dt.timezone.utc)
CLUBS = ["ARS", "MCI", "LIV", "CHE", "TOT", "MUN", "NEW", "AVL"]


def _p(pid, name, pos, team, price, xp, status="a", xmins=90.0, xp_per_gw=None):
    return {"id": pid, "web_name": name, "pos": pos, "team": team,
            "team_short": team, "price": price, "status": status,
            "xmins": xmins, "p_start": 0.9, "owned_pct": 5.0,
            "xp_per_gw": xp if xp_per_gw is None else xp_per_gw,
            "xp_horizon_total": xp * 6,
            "gameweeks": [{"gw": GW, "xp": xp,
                           "opponents": [{"opp": "BOU", "venue": "H"}]},
                          {"gw": GW + 1, "xp": xp}]}


def _players():
    """Riittava pooli lailliseen 15:een: 3 GK, 8 DEF, 8 MID, 5 FWD, 8 seuraa,
    hinnat 4.0-6.5 (mahtuu 100.0m:iin)."""
    ps, pid = [], 1
    for i in range(3):
        ps.append(_p(pid, f"Gk{i}", "GKP", CLUBS[i], 4.5 if i else 5.0,
                     [4.0, 3.5, 1.0][i], xmins=[90, 90, 0][i])); pid += 1
    for i in range(8):
        ps.append(_p(pid, f"Def{i}", "DEF", CLUBS[i], 5.0, 4.6 - i * 0.3)); pid += 1
    for i in range(8):
        ps.append(_p(pid, f"Mid{i}", "MID", CLUBS[(i + 3) % 8], 6.0, 5.5 - i * 0.3)); pid += 1
    for i in range(5):
        ps.append(_p(pid, f"Fwd{i}", "FWD", CLUBS[(i + 5) % 8], 6.5, 5.2 - i * 0.4)); pid += 1
    return ps


def _data(players, deadline=DL):
    return {"meta": {"deadline_gameweek": GW, "next_gameweek": GW,
                     "deadline_utc": deadline, "generated_at": "2026-08-28T12:00:00"},
            "players": players}


# 1 -------------------------------------------------------------------------

def test_top15_orders_by_gameweek_xp_not_horizon_average():
    ps = _players()
    ps.append(_p(90, "HorizonKing", "MID", "ARS", 9.0, 2.0, xp_per_gw=9.0))
    ps.append(_p(91, "ThisWeek", "MID", "MCI", 9.0, 7.0, xp_per_gw=3.0))
    top = top_projected(ps, GW)
    assert top[0]["web_name"] == "ThisWeek"
    assert "HorizonKing" not in [p["web_name"] for p in top]
    xps = [next(g["xp"] for g in p["gameweeks"] if g["gw"] == GW) for p in top]
    assert xps == sorted(xps, reverse=True) and len(top) == 15


def test_top15_mutation_by_xp_per_gw_would_differ():
    """Jos joku vaihtaa avaimen xp_per_gw:hen, testi 1 kaatuu: tassa
    todistetaan etta mutaatio tuottaa ERI listan (portti ei ole tautologia)."""
    ps = _players()
    ps.append(_p(90, "HorizonKing", "MID", "ARS", 9.0, 2.0, xp_per_gw=9.0))
    mutated = sorted(eligible(ps, GW), key=lambda p: -p["xp_per_gw"])[:15]
    assert mutated[0]["web_name"] == "HorizonKing"
    assert top_projected(ps, GW)[0]["web_name"] != "HorizonKing"


# 2 -------------------------------------------------------------------------

def test_thiaw_and_blocklist_never_on_card():
    ps = _players()
    ps.append(_p(90, "Thiaw", "DEF", "NEW", 4.0, 9.9))
    ps.append(_p(91, "M.Thiaw", "DEF", "NEW", 4.0, 9.8))
    ps.append(_p(92, "Bassey", "DEF", "AVL", 4.0, 9.7))
    bl = [{"name": "Bassey"}]
    names = {p["web_name"] for p in top_projected(ps, GW, blocklist=bl)}
    assert not names & {"Thiaw", "M.Thiaw", "Bassey"}
    sq = free_hit_xi(ps, GW, "t-thiaw", blocklist=bl)
    on_pitch = {p["web_name"] for p in sq["xi"] + sq["bench"]}
    assert not on_pitch & {"Thiaw", "M.Thiaw", "Bassey"}
    html, _ = build_html(_data(ps), blocklist=bl)
    assert "Thiaw" not in html and "Bassey" not in html


def test_gate_blocks_names_and_banned_copy_but_not_projected():
    bl = [{"name": "Thiaw"}]
    with pytest.raises(RuntimeError, match="blocked name"):
        gate("<td>Thiaw</td>", bl)
    with pytest.raises(RuntimeError, match="banned copy"):
        gate("<p>the odds say</p>", bl)
    with pytest.raises(RuntimeError, match="banned copy"):
        gate("<p>GoalIQ Pro</p>", bl)
    with pytest.raises(RuntimeError, match="banned copy"):
        gate("<p>a — b</p>", bl)
    with pytest.raises(RuntimeError, match="banned copy"):
        gate("<p>picked by the optimiser</p>", bl)
    gate("<p>Projected points, top 15. Free-hit XI.</p>", bl)  # negatiivinen kontrolli


# 3 -------------------------------------------------------------------------

def test_non_available_status_is_excluded():
    ps = _players()
    ps.append(_p(90, "Injured", "MID", "ARS", 9.0, 9.9, status="i"))
    ps.append(_p(91, "Doubt", "MID", "MCI", 9.0, 9.8, status="d"))
    ps.append(_p(92, "Susp", "MID", "LIV", 9.0, 9.7, status="s"))
    names = {p["web_name"] for p in top_projected(ps, GW)}
    assert not names & {"Injured", "Doubt", "Susp"}
    sq = free_hit_xi(ps, GW, "t-status")
    assert not {p["web_name"] for p in sq["xi"] + sq["bench"]} & {"Injured", "Doubt", "Susp"}


# 4 -------------------------------------------------------------------------

def test_xi_is_valid_and_call_format():
    sq = free_hit_xi(_players(), GW, "t-call")
    assert len(sq["xi"]) == 11 and len(sq["bench"]) == 4
    assert sq["captain"] in sq["xi"] and sq["vice"] in sq["xi"]
    assert sq["captain"]["gw_xp"] == max(p["gw_xp"] for p in sq["xi"])
    c = xi_call(sq)
    assert c["call"] == "projected_xi" and c["metric"] == "xi_gw_xp"
    assert c["player_id"] == sq["captain"]["id"]
    assert len(c["xi"]) == 11 and len(c["bench"]) == 4
    assert c["bench"][0]["pos"] == "GKP"  # penkkijarjestys: GK ensin
    assert c["formation"] == sq["formation"]
    n = {k: sum(1 for r in c["xi"] if r["pos"] == k) for k in ("GKP", "DEF", "MID", "FWD")}
    assert c["formation"] == f"{n['DEF']}-{n['MID']}-{n['FWD']}" and n["GKP"] == 1
    assert c["value"] == pytest.approx(sum(r["gw_xp"] for r in c["xi"]) + c["captain"]["gw_xp"], abs=0.01)
    for r in c["xi"] + c["bench"]:
        assert set(r) >= {"player_id", "web_name", "team_short", "pos", "gw_xp"}
    assert "—" not in json.dumps(c, ensure_ascii=False)


def test_upsert_call_before_deadline_and_fail_closed_after():
    c = xi_call(free_hit_xi(_players(), GW, "t-upsert"))
    log = json.loads(json.dumps(NEW_LOG))
    upsert_call(log, GW, DL, c, BEFORE, source={"projection_generated_at": "x"})
    row = log["gameweeks"][0]
    assert row["gw"] == GW and row["deadline_utc"] == DL
    assert [x["call"] for x in row["calls"]] == ["projected_xi"]
    # idempotentti: toinen kirjaus korvaa, ei tuplaa; muut kutsut sailyvat
    row["calls"].insert(0, {"call": "captain_pick", "player_id": 1})
    upsert_call(log, GW, DL, dict(c, value=1.0), BEFORE + _dt.timedelta(hours=1))
    assert [x["call"] for x in row["calls"]] == ["captain_pick", "projected_xi"]
    assert row["calls"][1]["value"] == 1.0
    # DEADLINE-SNAPSHOT (29.8): logged_at = ensimmainen, updated_at = viimeisin
    assert row["logged_at"] == "2026-08-28T14:00:00Z"
    assert row["updated_at"] == "2026-08-28T15:00:00Z"
    with pytest.raises(DeadlinePassed):
        upsert_call(log, GW, DL, c, AFTER)
    assert row["logged_at"] == "2026-08-28T14:00:00Z"
    assert row["updated_at"] == "2026-08-28T15:00:00Z"


def _xi_call_fixture():
    def r(pid, pos, xp=4.0):
        return {"player_id": pid, "web_name": f"P{pid}", "team_short": "X",
                "pos": pos, "gw_xp": xp}
    xi = [r(1, "GKP")] + [r(i, "DEF") for i in (2, 3, 4)] \
        + [r(i, "MID") for i in (5, 6, 7, 8)] + [r(i, "FWD") for i in (9, 10, 11)]
    bench = [r(12, "GKP"), r(13, "MID"), r(14, "DEF"), r(15, "FWD")]
    return {"call": "projected_xi", "player_id": 5, "xi": xi, "bench": bench,
            "captain": r(5, "MID"), "vice_captain": r(9, "FWD"),
            "formation": "3-4-3", "metric": "xi_gw_xp", "value": 50.0}


def test_grading_captain_doubled_autosub_and_vice():
    c = _xi_call_fixture()
    pts = {i: 2 for i in range(1, 16)}
    mins = {i: 90 for i in range(1, 16)}
    g = score_projected_xi(c, pts, mins)
    assert g["points"] == 11 * 2 + 2 and g["doubled"] == 5 and g["autosubs"] == []
    # kapteeni 5 (MID) ja DEF 3 eivat pelaa -> vara 9 tuplataan; penkki
    # jarjestyksessa: MID 13 ei voi korvata DEF 3:a (DEF jaisi 2:een) mutta
    # korvaa MID 5:n; DEF 14 korvaa DEF 3:n; FWD 15 jaa penkille
    mins2 = {**mins, 5: 0, 3: 0}
    pts2 = {**pts, 5: 0, 3: 0, 9: 7, 14: 6}
    g2 = score_projected_xi(c, pts2, mins2)
    assert g2["doubled"] == 9 and g2["captain_points"] == 7
    assert g2["autosubs"] == [{"out": 5, "in": 13}, {"out": 3, "in": 14}]
    assert g2["points"] == (8 * 2 + 6 + 2 + 7) + 7
    # varakapteenikaan ei pelaa -> ei tuplausta
    g3 = score_projected_xi(c, {**pts2, 9: 0}, {**mins2, 9: 0})
    assert g3["doubled"] is None and g3["captain_points"] == 0
    # negatiivinen kontrolli: penkkilainen jolla 0 min ei tule sisaan
    mins3 = {**mins, 3: 0, 14: 0, 13: 0, 15: 0}
    assert score_projected_xi(c, pts, mins3)["autosubs"] == []
    # puuttuva pelaaja -> None, ei nolla
    assert score_projected_xi(c, {k: v for k, v in pts.items() if k != 7}, mins)["points"] is None
    # grade_entry osaa rivin jossa on seka pelaajakutsu etta XI-kutsu
    entry = {"calls": [{"call": "captain_pick", "player_id": 5,
                        "xp_dist": {"haul_pts": 10}}, c]}
    grade_entry(entry, pts, mins, provisional=True, now=AFTER)
    assert entry["graded"]["by_call"]["projected_xi"]["points"] == 24
    assert entry["graded"]["by_call"]["captain_pick"]["met"] is False


# 5 -------------------------------------------------------------------------

def test_dry_run_renders_but_does_not_write_log(tmp_path, monkeypatch):
    import scripts.render_projected_xi_card as mod
    future = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(days=3)
              ).strftime("%Y-%m-%dT%H:%M:%SZ")
    xp = tmp_path / "xp.json"
    xp.write_text(json.dumps(_data(_players(), deadline=future)), encoding="utf-8")
    log_path = tmp_path / "gw_calls.json"
    monkeypatch.setattr(mod, "XP_PATH", xp)
    monkeypatch.setattr(mod, "CALLS_LOG_PATH", log_path)
    monkeypatch.setattr(mod.shutil, "which", lambda n: None)  # ei Chromea testissa
    monkeypatch.delenv("ProgramFiles", raising=False)
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    assert main(["--dry-run", "--out", str(tmp_path / "out")]) == 0
    assert (tmp_path / "out" / f"goaliq_projected_xi_gw{GW}.html").exists()
    assert not log_path.exists(), "dry-run ei saa kirjoittaa lokia"
    # ilman dry-runia kirjoitetaan (deadline tulevaisuudessa)
    assert main(["--out", str(tmp_path / "out")]) == 0
    row = json.loads(log_path.read_text(encoding="utf-8"))["gameweeks"][0]
    assert row["gw"] == GW and row["calls"][0]["call"] == "projected_xi"


def test_write_refused_after_deadline(tmp_path, monkeypatch):
    import scripts.render_projected_xi_card as mod
    xp = tmp_path / "xp.json"
    xp.write_text(json.dumps(_data(_players())), encoding="utf-8")  # DL 28.8 ohi
    log_path = tmp_path / "gw_calls.json"
    monkeypatch.setattr(mod, "XP_PATH", xp)
    monkeypatch.setattr(mod, "CALLS_LOG_PATH", log_path)
    monkeypatch.setattr(mod.shutil, "which", lambda n: None)
    monkeypatch.delenv("ProgramFiles", raising=False)
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    assert main(["--out", str(tmp_path / "out")]) == 1
    assert not log_path.exists()


# 6 -------------------------------------------------------------------------

def test_card_must_match_log_before_deadline_and_follows_log_after():
    ps = _players()
    sq = free_hit_xi(ps, GW, "t-rec")
    c = xi_call(sq)
    log = {"gameweeks": [{"gw": GW, "deadline_utc": DL, "logged_at": "x", "calls": [c]}]}
    assert reconcile_with_log(sq, GW, log, BEFORE) is sq  # sama -> sellaisenaan
    other = json.loads(json.dumps(c))
    other["xi"][1], other["bench"][1] = other["bench"][1], other["xi"][1]
    log2 = {"gameweeks": [{"gw": GW, "deadline_utc": DL, "logged_at": "x", "calls": [other]}]}
    with pytest.raises(RuntimeError, match="log"):
        reconcile_with_log(sq, GW, log2, BEFORE)
    after = reconcile_with_log(sq, GW, log2, AFTER)
    assert [p["id"] for p in after["xi"]] == [r["player_id"] for r in other["xi"]]
    assert reconcile_with_log(sq, GW + 5, log2, BEFORE) is sq  # ei rivia -> sellaisenaan


def test_html_has_numbers_one_decimal_and_no_em_dash():
    ps = _players()
    ps.append(_p(90, "Star", "MID", "ARS", 9.0, 7.26))
    html, payload = build_html(_data(ps), now=BEFORE)
    assert "GW2 projected points" in html and "Star" in html
    assert "7.3" in html and "7.26" not in html
    assert "—" not in html and "entry 116920" in html
    assert "28 Aug 17:30 UTC" in html and "card made 28 Aug 14:00 UTC" in html
    gate(html, [{"name": "Thiaw"}])
    assert payload["call"]["call"] == "projected_xi"


def test_right_panel_footnote_describes_the_right_panel_not_the_left():
    """QUEUE: KORTTI-BEST15-KAKSIMERKITYS. Ennen: oikean paneelin (XI +
    penkki) alaviite sanoi "Best 15 ... under the same squad rules", mutta
    "Best 15" on VASEMMAN paneelin top-lista (TOP_N=15). Alaviite kuvasi siis
    naapuripaneelia eika omaansa."""
    html, _ = build_html(_data(_players()), now=BEFORE)
    assert "Best XI inside the 100.0m budget" in html
    assert "cheapest cover that still projects minutes" in html


def test_negative_control_best15_wording_does_not_return_on_the_right():
    """Kontrolli: vanha, kahta paneelia sekoittava sanamuoto ei saa palata."""
    html, _ = build_html(_data(_players()), now=BEFORE)
    assert "Best 15 for this gameweek alone under the same squad rules" not in html


def test_entry_footer_says_this_is_not_the_models_own_team():
    """QUEUE: KORTTI-ENTRY-EROTUS. Ennen: "The model plays too: entry
    116920" nimesi entry 116920:n tasan talla kortilla, jonka oikea puoli on
    free-hit-XI jota malli EI pelaa (wildcard GW2:ssa). Uusi teksti sanoo
    eksplisiittisesti etta tama EI ole mallin oma joukkue."""
    html, _ = build_html(_data(_players()), now=BEFORE)
    assert "Not the model&#39;s own team" in html
    assert "entry 116920" in html


def test_negative_control_the_model_plays_too_wording_does_not_return():
    """Kontrolli: vanha sanamuoto, joka nimeaa entryn korjaamatta
    yhdistysta, ei saa palata."""
    html, _ = build_html(_data(_players()), now=BEFORE)
    assert "The model plays too" not in html


# ---------------------------------------------------------------------------
# Seurakatto top-15-listalla (Villen päätös 30.8)
# ---------------------------------------------------------------------------
# Ilman kattoa GW3-lista oli 8x MCI + 3x HUL viidestatoista, eli 11/15
# kahdesta ottelusta. Malli ei ollut vaarassa (molemmat kohtaavat nousijan),
# mutta FPL sallii korkeintaan 3 per seura, joten viisi rivia oli
# saantojen takia pelikelvottomia.

def _pl(i, name, club, xp, pos="MID"):
    return {"id": i, "web_name": name, "team": club, "team_short": club[:3].upper(),
            "pos": pos, "price": 5.0, "status": "a",
            "gameweeks": [{"gw": 3, "xp": xp}]}


def _by_gw(players, gw=3):
    from scripts.render_projected_xi_card import top_projected
    return top_projected(players, gw, n=15)


def test_no_more_than_three_players_from_one_club():
    import collections
    from src.models.fpl_rate_team import MAX_PER_CLUB
    # 8 pelaajaa samasta seurasta karjessa + tayte muualta
    players = [_pl(i, f"City{i}", "Man City", 9.0 - i * 0.1) for i in range(8)]
    players += [_pl(100 + i, f"Other{i}", f"Club{i}", 5.0 - i * 0.1) for i in range(20)]
    got = _by_gw(players)
    counts = collections.Counter(p["team"] for p in got)
    assert len(got) == 15
    assert max(counts.values()) <= MAX_PER_CLUB, counts
    assert counts["Man City"] == MAX_PER_CLUB


def test_the_three_kept_are_the_highest_scoring_of_that_club():
    """Katto ei saa pudottaa vaaria: jaljelle jaavat kolme parasta."""
    players = [_pl(i, f"City{i}", "Man City", 9.0 - i * 0.1) for i in range(8)]
    players += [_pl(100 + i, f"Other{i}", f"Club{i}", 5.0 - i * 0.1) for i in range(20)]
    kept = [p["web_name"] for p in _by_gw(players) if p["team"] == "Man City"]
    assert kept == ["City0", "City1", "City2"], kept


def test_negative_control_list_below_the_cap_is_untouched():
    """Kontrolli: ilman tata testi lapaisisi toteutuksella joka pudottaa
    rivejä muutenkin."""
    players = [_pl(i, f"P{i}", f"Club{i % 10}", 9.0 - i * 0.1) for i in range(15)]
    got = _by_gw(players)
    assert len(got) == 15
    assert [p["web_name"] for p in got] == [f"P{i}" for i in range(15)]


def test_cap_uses_the_shared_constant_not_a_local_number():
    """Kortin kaksi puoliskoa eivat saa ajautua eri saantoon.

    Oikea puoli (free_optimum) kayttaa MAX_PER_CLUBia; vasemman on
    kaytettava samaa. Jos joku muuttaa vakiota, taman on seurattava.
    """
    import collections
    from unittest import mock
    players = [_pl(i, f"City{i}", "Man City", 9.0 - i * 0.1) for i in range(8)]
    players += [_pl(100 + i, f"Other{i}", f"Club{i}", 5.0 - i * 0.1) for i in range(20)]
    with mock.patch("src.models.fpl_rate_team.MAX_PER_CLUB", 2):
        counts = collections.Counter(p["team"] for p in _by_gw(players))
    assert counts["Man City"] == 2, counts
