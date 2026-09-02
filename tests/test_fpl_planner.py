"""#35 planner-suiten testit: FT/hit-matematiikka, laillisuus, baseline-gate,
captain-picker, differentials, compare. Hermeettinen (jaettu mock-fixture
test_fpl_rate_team-moduulista, monkeypatch rt-moduuliin jonka läpi planner käy)."""
from __future__ import annotations

import pytest

import src.models.fpl_planner as pl
import src.models.fpl_rate_team as rt
from tests.test_fpl_rate_team import (  # noqa: F401 — _mock_fpl-fixture käyttöön
    FAKE_BOOTSTRAP, FAKE_XP, POOL_BOOT, SQUAD_IDS, _mock_fpl,
)

# Heikko runko: huonoimmat MID:t (20-24) + huonoimmat DEF:t → plannerilla
# on aitoja upgradeja tehtävänä. (Pool: GKP 1-4, DEF 5-14, MID 15-24, FWD 25-30)
WEAK_SQUAD = [3, 4, 10, 11, 12, 13, 14, 20, 21, 22, 23, 24, 28, 29, 30]


def test_plan_structure_and_baseline_gate():
    out = pl.plan_transfers(entry=424242, horizon=3)
    assert [p["gw"] for p in out["plan"]] == [1, 2, 3]
    assert out["totals"]["plan_xp"] >= out["totals"]["baseline_xp_no_transfers"]
    assert out["totals"]["net_gain"] >= 0
    assert "doesn't try every possible plan" in out["meta"]["heuristic"]
    assert "optimum" not in out["meta"]["heuristic"]
    # HEURISTIC-I18N (29.8): parametrit vakaina kenttina, ja proosa kertoo
    # SAMAT luvut (muuten es/pt-kaannos ja en-proosa eroaisivat hiljaa).
    hp = out["meta"]["heuristic_params"]
    for key in ("max_transfers_per_gw", "hit_cost", "ft_carry_max",
                "top_candidates_per_pos", "low_confidence_weight", "calibrated"):
        assert key in hp, key
    assert hp["calibrated"] is False
    prose = out["meta"]["heuristic"]
    assert f"max {hp['max_transfers_per_gw']} transfers/GW" in prose
    assert f"FT carry max {hp['ft_carry_max']}" in prose
    assert f"looks at the {hp['top_candidates_per_pos']} best" in prose
    assert f"{hp['low_confidence_weight']:.2f} of their projection" in prose


def test_plan_best_squad_rolls_transfers():
    # SQUAD_IDS = poolin parhaat per positio → ei mielekkäitä siirtoja → roll
    out = pl.plan_transfers(players=SQUAD_IDS, horizon=3, bank=0.0)
    assert all(p["roll_transfer"] for p in out["plan"])
    assert out["totals"]["hits_taken"] == 0
    # FT-carry: 1 → 2 → 3 (katto 5)
    assert [p["free_transfers_left"] for p in out["plan"]] == [1, 2, 3]


def test_plan_weak_squad_makes_legal_upgrades():
    out = pl.plan_transfers(players=WEAK_SQUAD, horizon=3, bank=10.0, ft=1)
    moves = [m for p in out["plan"] for m in p["transfers"]]
    assert moves, "heikolle rungolle pitää löytyä upgradeja"
    assert out["totals"]["net_gain"] > 0
    # Simuloi suunnitelma: laillisuus + budjetti joka askeleella
    prices = {e["id"]: e["now_cost"] for e in POOL_BOOT}
    clubs_of = {e["id"]: e["team"] for e in POOL_BOOT}
    pos_of = {e["id"]: e["element_type"] for e in POOL_BOOT}
    squad = list(WEAK_SQUAD)
    bank = 100  # 10.0m kymmenyksinä
    for p in out["plan"]:
        for m in p["transfers"]:
            out_id, in_id = m["out"]["id"], m["in"]["id"]
            assert out_id in squad and in_id not in squad
            assert pos_of[out_id] == pos_of[in_id]
            bank += prices[out_id] - prices[in_id]
            assert bank >= 0, "budjetti ei saa mennä miinukselle"
            squad.remove(out_id)
            squad.append(in_id)
            counts = {}
            for sid in squad:
                counts[clubs_of[sid]] = counts.get(clubs_of[sid], 0) + 1
            assert all(v <= rt.MAX_PER_CLUB for v in counts.values())
    # Kiintiöt säilyvät (siirrot positio-samoja)
    from collections import Counter
    assert Counter(pos_of[i] for i in squad) == Counter(
        pos_of[i] for i in WEAK_SQUAD)


def test_plan_hit_math_ft_zero():
    # ft=0 → jokainen siirto maksaa 4; siirto tehdään vain jos gain-4 >= MIN_GAIN
    out = pl.plan_transfers(players=WEAK_SQUAD, horizon=2, bank=10.0, ft=0)
    gw1 = out["plan"][0]
    for m in gw1["transfers"]:
        assert m["hit"] == pl.HIT_COST
        assert m["gain_xp_remaining"] - m["hit"] >= pl.MIN_GAIN_PER_TRANSFER
    assert out["totals"]["hits_taken"] == sum(
        1 for p in out["plan"] for m in p["transfers"] if m["hit"] > 0)
    # Portti 29.8: hero-verdikti kantaa saman hittimaaran kuin totals, jotta
    # klientti voi sanoa "after 2 hits (-8 xP)" eika "after a -4 hit".
    assert out["hold_verdict"]["hits_taken"] == out["totals"]["hits_taken"]


def test_plan_hold_verdict_best_squad_holds():
    # #63: paras runko -> 0 siirtoa -> eksplisiittinen hold-verdikti
    out = pl.plan_transfers(players=SQUAD_IDS, horizon=3, bank=0.0)
    hv = out["hold_verdict"]
    assert hv["verdict"] == "hold"
    assert hv["transfers_planned"] == 0
    assert hv["best_move_gain_xp"] is None
    assert hv["horizon_gws"] == 3
    assert hv["threshold_xp"] == rt.HOLD_THRESHOLD_XP
    # 29.8: aiemmin tassa luki `assert "holding" in message`. Se ei mitannut
    # vaitteen TARKKUUTTA, ja lause "No transfer beats your team" laksi
    # tarkastamattomana ulos viidelle pinnalle. Nyt mitataan kaksi asiaa:
    # lause nimeaa mita malli tarkisti, EIKA se saa palata ylikvanttoriin
    # ("beats" / "no plan"), jonka plannerin oma heuristiikkateksti kumoaa
    # samalla ruudulla ("it doesn't try every possible plan").
    assert "the model checked" in hv["message"]
    assert "beats" not in hv["message"].lower()
    assert "no plan" not in hv["message"].lower()
    assert "available" not in hv["message"].lower()


def test_plan_hold_verdict_weak_squad_transfers():
    # #63: heikko runko -> transfer-verdikti, netto = totals.net_gain (hitit jo
    # vähennetty) ja ylittää kynnyksen
    out = pl.plan_transfers(players=WEAK_SQUAD, horizon=3, bank=10.0, ft=1)
    hv = out["hold_verdict"]
    assert hv["verdict"] == "transfer"
    assert hv["transfers_planned"] > 0
    assert hv["best_move_gain_xp"] == out["totals"]["net_gain"]
    assert hv["best_move_gain_xp"] >= rt.HOLD_THRESHOLD_XP
    assert "Recommended" in hv["message"]
    assert hv["hits_taken"] == out["totals"]["hits_taken"]


def test_plan_param_validation():
    with pytest.raises(rt.RateTeamError):
        pl.plan_transfers(players=SQUAD_IDS, horizon=1)
    with pytest.raises(rt.RateTeamError):
        pl.plan_transfers(players=SQUAD_IDS, horizon=3, ft=99)


def test_captain_picker_top3_and_differential():
    out = pl.captain_picker(entry=424242)
    top3 = out["top3"]
    assert len(top3) == 3
    assert top3[0]["gw_xp"] >= top3[1]["gw_xp"] >= top3[2]["gw_xp"]
    assert top3[0]["gap_to_top"] == 0.0 and top3[2]["gap_to_top"] >= 0
    # top1 = FWD 25 (5.8, EO 40); differential = EO <= 10, eri kuin top1
    assert top3[0]["id"] == 25
    d = out["differential"]
    assert d is not None and d["owned_pct"] <= pl.CAPTAIN_DIFFERENTIAL_EO
    assert d["id"] != top3[0]["id"]


def test_differential_finder_filters():
    out = pl.differential_finder(max_ownership=10.0)
    assert out["players"], "EO 5 % -pelaajia pitää löytyä"
    assert all(p["owned_pct"] <= 10.0 for p in out["players"])
    xs = [p["xp_horizon_total"] for p in out["players"]]
    assert xs == sorted(xs, reverse=True)
    only_mid = pl.differential_finder(max_ownership=10.0, pos="MID")
    assert only_mid["players"] and all(p["pos"] == "MID"
                                       for p in only_mid["players"])
    with pytest.raises(rt.RateTeamError):
        pl.differential_finder(pos="XYZ")


def test_model_vs_crowd_delta_fields_and_bounds():
    # #71: players-rivit kantavat delta-kentät ja arvot pysyvät rajoissa
    out = pl.differential_finder(max_ownership=10.0)
    for p in out["players"]:
        assert -100.0 <= p["model_vs_crowd_delta"] <= 100.0
        assert 0.0 <= p["model_pct"] <= 100.0
        assert 0.0 <= p["crowd_pct"] <= 100.0
        assert p["model_vs_crowd_delta"] == round(
            p["model_pct"] - p["crowd_pct"], 1)


def test_model_vs_crowd_lists():
    # Fixture: per positio 2 parasta EO 40, loput EO 5 → 3.-paras per positio
    # on "malli edellä joukkoa"; heikohko 40 %-omistettu on fade.
    out = pl.differential_finder()
    mvc = out["model_vs_crowd"]
    backs, fades = mvc["model_backs"], mvc["crowd_backs"]
    assert backs and all(
        p["model_vs_crowd_delta"] >= pl.MODEL_VS_CROWD_DELTA_MIN
        and p["model_pct"] >= pl.MODEL_VS_CROWD_MIN_MODEL_PCT for p in backs)
    assert fades and all(
        p["model_vs_crowd_delta"] <= -pl.MODEL_VS_CROWD_DELTA_MIN
        and p["crowd_pct"] >= pl.MODEL_VS_CROWD_MIN_CROWD_PCT for p in fades)
    # MID 17 (xP 5.0, EO 5) = poolin selkein "model backs" -tapaus
    assert 17 in {p["id"] for p in backs}
    # GKP 2 (xP 3.5, EO 40) = template-pelaaja jota malli ei rankkaa → fade
    assert 2 in {p["id"] for p in fades}
    # Rehellisyys: template-pelaajat joista malli on samaa mieltä (MID 15,
    # xP-ykkönen EO 40) eivät ole kummallakaan listalla
    ids = {p["id"] for p in backs} | {p["id"] for p in fades}
    assert 15 not in ids
    # Deltat laskevassa/nousevassa järjestyksessä
    bd = [p["model_vs_crowd_delta"] for p in backs]
    fd = [p["model_vs_crowd_delta"] for p in fades]
    assert bd == sorted(bd, reverse=True) and fd == sorted(fd)


def test_model_vs_crowd_pos_filter():
    out = pl.differential_finder(pos="MID")
    mvc = out["model_vs_crowd"]
    for p in mvc["model_backs"] + mvc["crowd_backs"]:
        assert p["pos"] == "MID"


def test_compare_players_verdict():
    out = pl.compare_players([15, 24])  # paras MID vs huonoin MID
    assert len(out["players"]) == 2
    # 29.8 COMPARE-START-PCT: rivi kantaa p_start:n (Start%:n ainoa lahde),
    # ei vain kerran pyoristettya predicted_starts:ia. Avaimen on oltava
    # olemassa myos kun arvo on None (klientti erottaa "ei tietoa" ja "vanha payload").
    for row in out["players"]:
        assert "p_start" in row, row.keys()
        if row["p_start"] is not None:
            assert 0.0 <= row["p_start"] <= 1.0
    assert out["verdict"]["pick"]["id"] == 15
    assert out["verdict"]["margin_xp_horizon"] > 0
    with pytest.raises(rt.RateTeamError):
        pl.compare_players([15])
    with pytest.raises(rt.RateTeamError):
        pl.compare_players([15, 15])
    with pytest.raises(rt.RateTeamError) as e:
        pl.compare_players([15, 99999])
    assert e.value.status_code == 404


# ---------------------------------------------------------------------------
# Endpoint-smoket
# ---------------------------------------------------------------------------

def test_endpoint_plan(client):
    r = client.get("/api/fantasy/plan?entry=424242&horizon=3")
    assert r.status_code == 200
    assert r.json()["totals"]["net_gain"] >= 0
    assert r.headers["cache-control"] == "no-store"


def test_endpoint_captain(client):
    r = client.get("/api/fantasy/captain?entry=424242")
    assert r.status_code == 200 and len(r.json()["top3"]) == 3


def test_endpoint_differentials(client):
    r = client.get("/api/fantasy/differentials?max_ownership=10")
    assert r.status_code == 200 and r.json()["players"]


def test_endpoint_compare(client):
    r = client.get("/api/fantasy/compare?players=15,24")
    assert r.status_code == 200
    assert r.json()["verdict"]["pick"]["id"] == 15
    r = client.get("/api/fantasy/compare?players=15,abc")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# PI-16b (28.7): esikausi-polku KAIKISSA joukkuepohjaisissa työkaluissa
#
# Taustaa: FPL julkaisee kokoonpanot vasta GW1-deadlinen jälkeen, joten
# entry-ID-polku palauttaa 404:n koko esikauden. rate-team sai 28.7. sekä
# koneluettavan koodin että draft-fallbackin; planner, kapteenirankkeri ja
# plan-chains eivät. Nämä testit lukitsevat molemmat puolet sopimuksesta:
# (a) `X-GoalIQ-Error-Code` tulee kaikista, (b) `players=` toimii kaikissa.
# ---------------------------------------------------------------------------

def _entry_without_picks(monkeypatch):
    """Entry on olemassa, mutta picksit eivät ole julkisia (= esikausi)."""
    def fake_fetch(path):
        if path == "/bootstrap-static/":
            return FAKE_BOOTSTRAP
        if path == "/entry/424242/":
            return {"id": 424242}
        raise rt.RateTeamError(404, "Not found on the FPL API.")

    monkeypatch.setattr(rt, "_fetch_fpl", fake_fetch)
    rt._FPL_CACHE.clear()


@pytest.mark.parametrize("url", [
    "/api/fantasy/rate-team?entry=424242",
    "/api/fantasy/plan?entry=424242&horizon=3",
    "/api/fantasy/captain?entry=424242",
    "/api/fantasy/plan-chains?entry=424242&horizon=3",
])
def test_preseason_404_carries_machine_readable_code(client, monkeypatch, url):
    _entry_without_picks(monkeypatch)
    r = client.get(url)
    assert r.status_code == 404
    # Koodi headerissa, EI bodyssa: `detail` pysyy merkkijonona, joten jo
    # julkaistut klientit (mobiili 1.0.3, SPA) lukevat vastauksen ennallaan.
    assert r.headers.get("X-GoalIQ-Error-Code") == "picks_not_published"
    assert isinstance(r.json()["detail"], str)


@pytest.mark.parametrize("url", [
    "/api/fantasy/plan?horizon=3&players=",
    "/api/fantasy/captain?players=",
    "/api/fantasy/plan-chains?horizon=3&players=",
])
def test_draft_mode_works_without_entry(client, url):
    r = client.get(url + ",".join(str(i) for i in SQUAD_IDS))
    assert r.status_code == 200, r.text


def test_plan_chains_requires_entry_or_players(client):
    r = client.get("/api/fantasy/plan-chains?horizon=3")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# PLAN-CHAINS-SQUAD-SOURCE (29.8): plan-chains ei emittoinut squad_source-
# kenttää, joten PlanChains.svelte ei voinut näyttää stale-riviä tai
# "Use my saved 15" -nappia kuten TransferPlanner jo tekee /plan:n kautta.
# Sama sopimus kuin fpl_planner.plan_transfers (ks. test_transfer_engine_
# parity.py:n squad_source-testit) — tässä ajettuna FastAPI-endpointin läpi,
# koska plan-chainsilla ei ole erillistä testattavaa funktiota.
# ---------------------------------------------------------------------------

def _clear_plan_chains_cache():
    import api.fantasy_edge as fe
    fe._RESULT_CACHE.clear()


def test_plan_chains_squad_source_manual_is_never_stale(client):
    _clear_plan_chains_cache()
    r = client.get("/api/fantasy/plan-chains?horizon=3&players="
                    + ",".join(str(i) for i in SQUAD_IDS))
    assert r.status_code == 200, r.text
    src = r.json()["meta"]["squad_source"]
    assert src["mode"] == "manual" and src["stale"] is False


def test_plan_chains_squad_source_entry_stale_when_deadline_gw_is_next(
        client, monkeypatch):
    xp = dict(FAKE_XP)
    xp["meta"] = {**FAKE_XP["meta"], "deadline_gameweek": 2}
    monkeypatch.setattr(rt, "load_xp", lambda: xp)
    _clear_plan_chains_cache()
    r = client.get("/api/fantasy/plan-chains?entry=424242&horizon=3")
    assert r.status_code == 200, r.text
    src = r.json()["meta"]["squad_source"]
    assert src["mode"] == "entry" and src["gw"] == 1 and src["stale"] is True
    assert src["deadline_gw"] == 2


def test_plan_chains_squad_source_is_structured_not_prose(client):
    _clear_plan_chains_cache()
    r = client.get("/api/fantasy/plan-chains?horizon=3&players="
                    + ",".join(str(i) for i in SQUAD_IDS))
    assert r.status_code == 200, r.text
    ss = r.json()["meta"]["squad_source"]
    assert set(ss) == {"mode", "gw", "deadline_gw", "stale"}


# ---------------------------------------------------------------------------
# 28.7 (Villen bugilöytö): siirtoehdotuksen delta on AVAUSKOKOONPANON hyöty.
#
# Vanha kaava (in.xP - out.xP) lupasi kakkosvahdin vaihdosta "+18.74 xP over
# the horizon", vaikka XI-xP ei muuttunut lainkaan (todennettu tuotannosta:
# 315.31 -> 315.31). Syvyysparannus ei ole pisteparannus.
# ---------------------------------------------------------------------------

def test_bench_only_upgrade_reports_no_xi_gain():
    """Kakkosvahdin paivitys ei saa nayttaa hyotya jos ykkosvahti ei vaihdu.

    Synteettinen pooli, koska jaettu mock-runko ei osunut tahan haaraan
    lainkaan: sen klubit olivat jo taynna ja kandidaatit karsiutuivat ennen
    deltan laskentaa (0 ehdotusta molemmilla toteutuksilla). Testi jonka
    negatiivinen kontrolli ei kaada ei mittaa mitaan.
    """
    pool, pid = [], 0

    def mk(t, price, xp, club):
        nonlocal_pid = None
        return {"id": 0, "web_name": "", "element_type": t, "price": price,
                "xp_horizon_total": xp, "xp_per_gw": xp / 6, "club": club,
                "team_short": f"C{club:02d}", "gameweeks": []}

    def add(t, price, xp, club, name):
        nonlocal pid
        pid += 1
        p = mk(t, price, xp, club)
        p["id"], p["web_name"] = pid, name
        pool.append(p)
        return p

    gk_start = add(1, 45, 60.0, 1, "GK_START")     # pelaa
    gk_bench = add(1, 45, 6.0, 2, "GK_BENCH")      # penkilla
    gk_free = add(1, 45, 30.0, 9, "GK_FREE")       # parempi kuin penkki,
    #                                                heikompi kuin ykkonen
    squad = [gk_start, gk_bench]
    for i in range(5):
        squad.append(add(2, 45, 30.0 - i, 10 + i, f"DEF{i}"))
    for i in range(5):
        squad.append(add(3, 45, 40.0 - i, 20 + i, f"MID{i}"))
    for i in range(3):
        squad.append(add(4, 45, 35.0 - i, 30 + i, f"FWD{i}"))
    assert len(squad) == 15

    out = rt.transfer_suggestions(squad, pool, bank_tenths=0)
    names = [(s["out"]["web_name"], s["in"]["web_name"],
              s["delta_xp_horizon"]) for s in out["suggestions"]]
    assert not any(o == "GK_BENCH" and i == "GK_FREE" for o, i, _d in names), (
        f"kakkosvahdin vaihto luvattiin hyotyna: {names}")
    assert out["hold"] is True, f"ei aitoja parannuksia, mutta hold=False: {names}"


def test_delta_never_exceeds_raw_player_difference():
    """XI-hyöty on aina <= pelaajien raakaerotus (matemaattinen yläraja).
    Jos tämä kaatuu, haarukointi karsii vääriä kandidaatteja."""
    pool = rt._projection_pool(FAKE_XP, {e["id"]: e for e in POOL_BOOT})
    by_id = {p["id"]: p for p in pool}
    # SQUAD_IDS on poolin PARAS runko -> ei parannuksia. Heikko runko on se
    # jolla siirtoja ylipaataan on (sama fixture kuin planner-testeissa).
    squad = [by_id[i] for i in WEAK_SQUAD]
    out = rt.transfer_suggestions(squad, pool, bank_tenths=30)
    assert out["suggestions"], "heikolle rungolle pitää löytyä parannuksia"
    for s in out["suggestions"]:
        assert s["delta_xp_horizon"] <= s["delta_xp_squad"] + 1e-6


# ---------------------------------------------------------------------------
# ROWAN-REPLACEMENTS (2.9): "who replaces X" — sama pelipaikka, hintahaarukka,
# ikkunan xP, omistus, yksi mitattu syy. Fixture: MID 15-24 kaikki 70 (7.0m),
# xP 5.5 -> 3.6, EO 40 % kahdella parhaalla.
# ---------------------------------------------------------------------------

def test_replacements_same_pos_bracket_sorted_and_reason():
    out = pl.replacements(20, gws=5)          # MID 20 = xP 4.4/GW
    assert out["target"]["id"] == 20 and out["target"]["pos"] == "MID"
    assert out["meta"]["gws"] == [1, 2, 3, 4, 5]
    rows = out["players"]
    assert len(rows) == 5
    assert [r["id"] for r in rows] == [15, 16, 17, 18, 19]  # xP-jarjestys, ei lahtijaa
    assert all(r["pos"] == "MID" for r in rows)
    assert all(out["meta"]["price_min"] <= r["price"] <= out["meta"]["price_max"]
               for r in rows)
    assert out["meta"]["bracket_widened"] is False
    xs = [r["xp_window"] for r in rows]
    assert xs == sorted(xs, reverse=True)
    # 5 x 5.5 - 5 x 4.4 = 5.5
    assert rows[0]["xp_window"] == 27.5 and rows[0]["xp_gap_vs_target"] == 5.5
    assert rows[0]["owned_pct"] == 40.0
    for r in rows:
        assert r["reason"]["kind"] in ("minutes", "fixture", "flat")
        assert r["reason"]["text"], "Ville 2.9: syy joka rivilla"
        assert len(r["gameweeks"]) == 5
    # Fixture: tasainen xP joka GW + ei p_start -> syy on xP-ero, ja luku on
    # sama kuin rivin oma gap (yksi lahde kahdelle kentalle).
    # Fixture: tasainen xP -> paras kierros on ikkunan ensimmainen (tasapeli
    # -> aikaisin), ei piikki. Teksti on eri fakta kuin vs-sarake.
    # Tasainen xP -> ei erottuvaa viikkoa (portti k3: "the biggest week" ei
    # pida kun ero on alle esitystarkkuuden) -> vaihteluvali.
    assert rows[0]["reason"]["kind"] == "flat"
    assert rows[0]["reason"]["text"] == "no standout week, 5.5-5.5 xP"
    assert out["meta"]["reason_note"].endswith("over GW1-GW5, not a single gameweek.")


def test_replacements_errors():
    with pytest.raises(rt.RateTeamError) as e:
        pl.replacements(99999)
    assert e.value.status_code == 404
    for kw in ({"gws": 0}, {"gws": 7}, {"bracket": -1}, {"bracket": 9}, {"top_n": 0}):
        with pytest.raises(rt.RateTeamError) as e:
            pl.replacements(20, **kw)
        assert e.value.status_code == 400


def test_replacements_bracket_widens_and_reports(monkeypatch):
    """Hintaskaalan paassa +-0.5m on tyhja -> haarukka levenee 0.5m askelin
    ja meta kertoo seka pyydetyn etta kaytetyn. Ei hiljaista levennysta."""
    xp_data, boot, pool, by_id = pl.build_context()
    # MID 15 hinnoitellaan 10.0m -> +-0.5m ei osu keneenkaan (muut 7.0m);
    # +-3.0m osuu kaikkiin.
    pool = [dict(p, price=100) if p["id"] == 15 else p for p in pool]
    monkeypatch.setattr(pl, "build_context",
                        lambda: (xp_data, boot, pool, {p["id"]: p for p in pool}))
    out = pl.replacements(15, gws=5, bracket=0.5)
    m = out["meta"]
    assert m["bracket_requested"] == 0.5 and m["bracket"] == 3.0
    assert m["bracket_widened"] is True
    assert m["price_min"] == 7.0 and m["price_max"] == 13.0
    assert [r["id"] for r in out["players"]] == [16, 17, 18, 19, 20]


def test_replacements_reason_minutes_and_peak(monkeypatch):
    xp_data, boot, pool, by_id = pl.build_context()
    pool = [dict(p) for p in pool]
    by = {p["id"]: p for p in pool}
    by[20]["p_start"] = 0.55                      # lahtija epavarma
    by[15]["p_start"] = 0.92                      # -> minutes
    by[16]["p_start"] = 0.60                      # ei minutes; tee GW3-piikki
    by[16]["gameweeks"] = [{"gw": g, "opponents": [{"opp": "C09", "venue": "H"}] if g == 3 else [],
                            "xp": 9.0 if g == 3 else 4.0} for g in range(1, 7)]
    monkeypatch.setattr(pl, "build_context", lambda: (xp_data, boot, pool, by))
    out = pl.replacements(20, gws=5)
    rows = {r["id"]: r for r in out["players"]}
    assert rows[15]["reason"]["kind"] == "minutes"
    assert rows[15]["reason"]["text"] == "projected to start 92% of games, P20 55% of starts"
    assert rows[16]["reason"]["kind"] == "fixture"
    assert rows[16]["reason"]["gw"] == 3
    assert rows[16]["reason"]["text"] == "best week GW3 C09 (H), 9.0 xP"


def test_replacements_minutes_reason_caps_at_99(monkeypatch):
    """Portti k3: 100 % on varmuusvaite jaettavassa kuvassa -> katto 99."""
    xp_data, boot, pool, by_id = pl.build_context()
    pool = [dict(p) for p in pool]
    by = {p["id"]: p for p in pool}
    by[20]["p_start"] = 0.5
    by[15]["p_start"] = 1.0
    monkeypatch.setattr(pl, "build_context", lambda: (xp_data, boot, pool, by))
    out = pl.replacements(20, gws=5)
    r = {x["id"]: x for x in out["players"]}[15]
    assert r["reason"]["value"] == 99 and r["reason"]["text"].startswith("projected to start 99%")


def test_replacements_availability_gate_drops_live_out(monkeypatch):
    """Elavassa bootstrapissa sivuun merkitty ei ole korvaaja; lahtija saa
    olla sivussa (se on usein kysymyksen syy)."""
    import copy
    xp_data, boot, pool, by_id = pl.build_context()
    boot2 = copy.deepcopy(boot)
    for e in boot2["elements"]:
        if e["id"] in (15, 20):
            e["status"] = "i"
    monkeypatch.setattr(pl, "build_context",
                        lambda: (xp_data, boot2, pool, by_id))
    out = pl.replacements(20, gws=5)
    ids = [r["id"] for r in out["players"]]
    assert 15 not in ids and ids == [16, 17, 18, 19, 21]
    assert [d["id"] for d in out["meta"]["availability_gate"]["dropped"]
            if d["id"] == 15]


def test_endpoint_replacements(client):
    r = client.get("/api/fantasy/replacements?player=20")
    assert r.status_code == 200
    body = r.json()
    assert body["target"]["id"] == 20 and len(body["players"]) == 5
    assert r.headers.get("cache-control") == "no-store"
    assert client.get("/api/fantasy/replacements?player=99999").status_code == 404
    assert client.get("/api/fantasy/replacements").status_code == 422
    assert client.get("/api/fantasy/replacements?player=20&gws=9").status_code == 422


def test_endpoint_replacements_masked_without_premium(client, monkeypatch):
    """FANTASY-TOOLS-ENDPOINT-AUTH (2.9): anonyymi ei saa listaa kun enforcement
    on paalla; premium saa taman. Negatiivinen kontrolli: enforce off -> taysi."""
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    r = client.get("/api/fantasy/replacements?player=20")
    assert r.status_code == 200
    b = r.json()
    assert b["meta"]["masked"] is True and len(b["players"]) == 1
    assert b["target"]["id"] == 20 and b["players"][0]["id"] == 15
    monkeypatch.setenv("PREMIUM_ENFORCE", "off")
    b = client.get("/api/fantasy/replacements?player=20").json()
    assert "masked" not in b["meta"] and len(b["players"]) == 5
