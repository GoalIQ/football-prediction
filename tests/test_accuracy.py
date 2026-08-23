"""Tarkkuus-track-record -putken testit (#100).

Kattaa: 1X2/exact/decisive-osumalogiikan, aggregaatin (reuse backtest-Brier),
seed-parsinnan WC-hubista (= julkaistu 21/40), endpointin muodon ja
WC pre-match -helperin neutraali-venue-symmetrian (peili predict_wc:stä).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.models import accuracy as acc


# ---------------------------------------------------------------------------
# Pien-helpurit
# ---------------------------------------------------------------------------
def test_outcome_from_score():
    assert acc.outcome_from_score(2, 0) == "home"
    assert acc.outcome_from_score(1, 1) == "draw"
    assert acc.outcome_from_score(0, 3) == "away"


def test_named_winner_never_draw():
    assert acc.named_winner(0.6, 0.2) == "home"
    assert acc.named_winner(0.2, 0.5) == "away"
    # tasan -> home (deterministinen tie-break)
    assert acc.named_winner(0.3, 0.3) == "home"


# ---------------------------------------------------------------------------
# upsert + set_result idempotenssi + osumalogiikka
# ---------------------------------------------------------------------------
def _entry(mid, winner, mls=None, p=(None, None, None), date="2026-06-20"):
    return {
        "match_id": mid, "source": "test", "competition": "WC", "date": date,
        "home_team": "A", "away_team": "B",
        "p_home": p[0], "p_draw": p[1], "p_away": p[2],
        "xg_home": None, "xg_away": None,
        "most_likely_score": mls, "predicted_winner": winner,
        "logged_at": None, "result": None,
    }


def test_upsert_is_idempotent():
    log = acc.empty_log()
    assert acc.upsert_prediction(log, _entry("m1", "home")) is True
    assert acc.upsert_prediction(log, _entry("m1", "away")) is False  # ei ylikirjoita
    assert len(log["predictions"]) == 1
    assert log["predictions"][0]["predicted_winner"] == "home"


def test_set_result_hit_and_exact():
    log = acc.empty_log()
    acc.upsert_prediction(log, _entry("m1", "home", mls="2-1"))
    assert acc.set_result(log, "m1", 2, 1) is True
    res = log["predictions"][0]["result"]
    assert res["actual_outcome"] == "home"
    assert res["hit_1x2"] is True
    assert res["exact_hit"] is True
    assert res["actual_score"] == "2-1"
    # idempotentti: toinen reconcile ei muuta
    assert acc.set_result(log, "m1", 0, 5) is False


def test_set_result_draw_is_miss_for_named_winner():
    log = acc.empty_log()
    acc.upsert_prediction(log, _entry("m1", "home", mls="2-1"))
    acc.set_result(log, "m1", 1, 1)  # tasapeli
    res = log["predictions"][0]["result"]
    assert res["actual_outcome"] == "draw"
    assert res["hit_1x2"] is False
    assert res["exact_hit"] is False  # 2-1 != 1-1


def test_exact_hit_none_without_mls():
    log = acc.empty_log()
    acc.upsert_prediction(log, _entry("m1", "home", mls=None))  # seed-tyyppi
    acc.set_result(log, "m1", 3, 0)
    assert log["predictions"][0]["result"]["exact_hit"] is None


# ---------------------------------------------------------------------------
# 90 min -gradaus (Villen päätös 20.7 ilta, kumosi saman päivän FT-AET-kokeilun):
# täysajalla tasan ollut pudotuspeli = tasapeli, ET JA pilkut samalla säännöllä.
# ---------------------------------------------------------------------------
def test_set_result_extra_time_win_graded_as_90min_draw():
    log = acc.empty_log()
    acc.upsert_prediction(log, _entry("m1", "home", mls="1-1"))
    # 90 min 1-1, koti voitti jatkoajalla 3-2 (esim. Argentina-Cape Verde)
    assert acc.set_result(log, "m1", 3, 2, duration="EXTRA_TIME",
                          regular_home=1, regular_away=1) is True
    res = log["predictions"][0]["result"]
    assert res["actual_score"] == "3-2"          # näyttötulos säilyy
    assert res["duration"] == "EXTRA_TIME"
    assert res["regular_score"] == "1-1"
    assert res["actual_outcome"] == "draw"       # 90 min -gradaus
    assert res["hit_1x2"] is False               # ET-voitto ei ole 1X2-osuma
    assert res["exact_hit"] is True              # mls 1-1 == 90 min 1-1


def test_set_result_final_shape_et_win_is_miss():
    # GRADE-90-ankkuri: regular 0-0, lopputulos 1-0 aet, pick home → MISSI.
    log = acc.empty_log()
    acc.upsert_prediction(log, _entry("m1", "home", mls="1-0"))
    acc.set_result(log, "m1", 1, 0, duration="EXTRA_TIME",
                   regular_home=0, regular_away=0)
    res = log["predictions"][0]["result"]
    assert res["actual_outcome"] == "draw"
    assert res["hit_1x2"] is False
    assert res["exact_hit"] is False             # mls 1-0 != 90 min 0-0


def test_set_result_penalty_shootout_graded_as_90min():
    log = acc.empty_log()
    acc.upsert_prediction(log, _entry("m1", "away", mls="0-1"))
    acc.set_result(log, "m1", 1, 1, duration="PENALTY_SHOOTOUT",
                   regular_home=1, regular_away=1)
    res = log["predictions"][0]["result"]
    assert res["actual_outcome"] == "draw"
    assert res["hit_1x2"] is False
    assert res["exact_hit"] is False
    assert res["duration"] == "PENALTY_SHOOTOUT"


def test_set_result_regular_time_win_unchanged():
    # Regressiosuoja: normaali 90 min -ratkaisu gradataan kuten ennenkin.
    log = acc.empty_log()
    acc.upsert_prediction(log, _entry("m1", "home", mls="2-1"))
    acc.set_result(log, "m1", 2, 1)
    res = log["predictions"][0]["result"]
    assert res["actual_outcome"] == "home"
    assert res["hit_1x2"] is True
    assert res["exact_hit"] is True


def test_regrade_flips_ft_aet_graded_et_win_back_to_draw():
    # Siirtymä FT-AET-välitilasta (20.7 päivä) 90 min -normiin: FT-AET gradasi
    # ET-voiton osumaksi → regrade kääntää tasapeliksi/missiksi, rivi ei putoa.
    log = acc.empty_log()
    acc.upsert_prediction(log, _entry("m1", "home", mls="2-0"))
    acc.set_result(log, "m1", 3, 2, duration="EXTRA_TIME",
                   regular_home=1, regular_away=1)
    orig_reconciled = log["predictions"][0]["result"]["reconciled_at"]
    # simuloi FT-AET-normilla gradattu lohko (kuten prediction_logissa 20.7 päivällä)
    log["predictions"][0]["result"].update(
        {"actual_outcome": "home", "hit_1x2": True}
    )

    assert acc.regrade_result(log, "m1", 3, 2, duration="EXTRA_TIME",
                              regular_home=1, regular_away=1) is True
    assert len(log["predictions"]) == 1          # union: rivi ei putoa
    res = log["predictions"][0]["result"]
    assert res["hit_1x2"] is False               # gradaus kääntyi 90 miniin
    assert res["actual_outcome"] == "draw"
    assert res["actual_score"] == "3-2"
    assert res["regular_score"] == "1-1"
    assert res["reconciled_at"] == orig_reconciled
    assert res["regraded_at"] is not None
    # ennustekentät koskemattomat
    assert log["predictions"][0]["predicted_winner"] == "home"


def test_regrade_noop_for_regular_match():
    log = acc.empty_log()
    acc.upsert_prediction(log, _entry("m1", "home", mls="2-1"))
    acc.set_result(log, "m1", 2, 1)
    assert acc.regrade_result(log, "m1", 2, 1) is False  # ei muutosta
    assert "regraded_at" not in log["predictions"][0]["result"]


# ---------------------------------------------------------------------------
# Aggregaatti (sis. Brier täysiltä riveiltä)
# ---------------------------------------------------------------------------
def test_compute_aggregate_metrics():
    log = acc.empty_log()
    # 2 täyttä-jakauma-riviä + 1 seed-tyyppinen (vain voittaja)
    acc.upsert_prediction(log, _entry("f1", "home", mls="2-1", p=(0.6, 0.25, 0.15)))
    acc.upsert_prediction(log, _entry("f2", "away", mls="0-1", p=(0.2, 0.3, 0.5)))
    acc.upsert_prediction(log, _entry("s1", "home", mls=None, p=(None, None, None)))
    acc.set_result(log, "f1", 2, 1)   # home, exact hit
    acc.set_result(log, "f2", 1, 1)   # draw -> miss
    acc.set_result(log, "s1", 3, 0)   # home, hit (1x2)

    agg = acc.compute_aggregate(log)
    at = agg["all_time"]
    assert at["n"] == 3
    assert at["correct_1x2"] == 2          # f1 + s1
    assert at["pct_1x2"] == pytest.approx(2 / 3, abs=1e-4)
    assert at["decisive_n"] == 2           # f1 (home), s1 (home); f2 ended draw
    assert at["decisive_correct"] == 2
    assert at["exact_n"] == 2              # vain f1, f2 (mls tunnetaan)
    assert at["exact_correct"] == 1        # f1
    assert at["brier_n"] == 2              # vain täydet jakaumat
    # MIN_DISPLAY_N-gate: exact_n/brier_n (2) < 30 → näytettävä arvo nullataan,
    # ali-otoskoot säilyvät raportoituina (data kertyy taustalla).
    assert at["pct_exact"] is None
    assert at["brier"] is None
    assert agg["pending"] == 0
    assert agg["logged_total"] == 3


def test_small_sample_exact_brier_gated():
    """exact/Brier nullataan kun ali-otos < MIN_DISPLAY_N, näkyy rajalla."""
    # Alle rajan (1 täysi-jakauma-rivi) → molemmat null, 1X2 ennallaan
    log = acc.empty_log()
    acc.upsert_prediction(log, _entry("a", "home", mls="2-1", p=(0.6, 0.25, 0.15)))
    acc.set_result(log, "a", 2, 1)
    at = acc.compute_aggregate(log)["all_time"]
    assert at["pct_1x2"] is not None       # 1X2 ei koskaan gateta
    assert at["pct_exact"] is None
    assert at["brier"] is None
    assert at["exact_n"] == 1 and at["brier_n"] == 1  # ali-otos yhä raportoitu

    # >= MIN_DISPLAY_N täysi-jakauma-rivillä → exact + Brier näkyvät
    log = acc.empty_log()
    for i in range(acc.MIN_DISPLAY_N):
        acc.upsert_prediction(log, _entry(f"f{i}", "home", mls="2-1",
                                          p=(0.6, 0.25, 0.15), date=f"2026-06-{i % 28 + 1:02d}"))
        acc.set_result(log, f"f{i}", 2, 1)
    at = acc.compute_aggregate(log)["all_time"]
    assert at["exact_n"] == acc.MIN_DISPLAY_N
    assert at["brier_n"] == acc.MIN_DISPLAY_N
    assert at["pct_exact"] is not None
    assert at["brier"] is not None


def test_empty_aggregate_shape():
    agg = acc.empty_aggregate()
    assert agg["all_time"]["n"] == 0
    assert agg["all_time"]["pct_1x2"] is None
    assert agg["rolling"]["window"] == acc.DEFAULT_ROLLING_WINDOW
    assert agg["calibration"] == []
    assert agg["recent"] == []


# ---------------------------------------------------------------------------
# Seed-parsinta WC-hubista = julkaistu 21/40
# ---------------------------------------------------------------------------
def test_seed_parse_matches_published_record():
    # 21/40 = ryhmävaiheen JULKAISTU track-record = immutaabeli historia. Pinnataan
    # arkistoituun ryhmävaihe-hubiin (tests/fixtures/) EIKÄ live-WC_HUB_HTML:ään:
    # live-hub rullaa kierroksittain eteenpäin (R32 → predictions-taulu, ei enää 40
    # ryhmävaiherivin track-recordia), joten golden-check ei saa riippua siitä.
    from scripts.accuracy_pipeline import parse_seed_rows
    fixture = Path(__file__).parent / "fixtures" / "wc-hub-groupstage.html"
    rows = parse_seed_rows(fixture.read_text(encoding="utf-8"))
    assert len(rows) == 40, f"odotettiin 40 seed-riviä, saatiin {len(rows)}"

    log = acc.empty_log()
    for r in rows:
        hs, as_ = r.pop("_seed_score")
        acc.upsert_prediction(log, r)
        acc.set_result(log, r["match_id"], hs, as_)
    at = acc.compute_aggregate(log)["all_time"]
    assert at["n"] == 40
    assert at["correct_1x2"] == 21          # WC-hubin julkaistu 21/40
    assert at["decisive_correct"] == 21
    assert at["decisive_n"] == 27           # 13 tasapeliä -> 27 ratkaisevaa
    assert at["pct_1x2"] == pytest.approx(0.525, abs=1e-3)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
def test_accuracy_endpoint_shape(client):
    r = client.get("/api/accuracy")
    assert r.status_code == 200
    b = r.json()
    for key in ("updated_at", "all_time", "rolling", "calibration", "recent"):
        assert key in b
    for key in ("n", "pct_1x2", "decisive_n", "exact_n", "brier"):
        assert key in b["all_time"]


# ---------------------------------------------------------------------------
# WC pre-match -helper: neutraali-venue-symmetria (peili predict_wc:stä)
# ---------------------------------------------------------------------------
def test_wc_prematch_symmetry():
    a = acc.wc_prematch_prediction("Brazil", "France")
    b = acc.wc_prematch_prediction("France", "Brazil")
    assert a is not None and b is not None
    assert a["p_home"] == pytest.approx(b["p_away"], abs=1e-9)
    assert a["p_away"] == pytest.approx(b["p_home"], abs=1e-9)
    assert a["p_draw"] == pytest.approx(b["p_draw"], abs=1e-9)
    assert a["xg_home"] == pytest.approx(b["xg_away"], abs=1e-9)
    assert a["xg_away"] == pytest.approx(b["xg_home"], abs=1e-9)
    # nimetty voittaja peilautuu
    assert {a["predicted_winner"], b["predicted_winner"]} <= {"home", "away"}


def test_wc_prematch_non_wc_team_returns_none():
    assert acc.wc_prematch_prediction("Finland", "Brazil") is None


# ---------------------------------------------------------------------------
# #110: domestic-liigat — nimiresolveri, opt-in-portti, logaus, by_competition
# ---------------------------------------------------------------------------
BSA_MODEL_TEAMS = [
    "Athletico-PR", "Atletico GO", "Atletico-MG", "Bahia", "Botafogo RJ",
    "Bragantino", "Ceara", "Chapecoense-SC", "Corinthians", "Coritiba",
    "Criciuma", "Cruzeiro", "Cuiaba", "Flamengo RJ", "Fluminense",
    "Fortaleza", "Gremio", "Internacional", "Juventude", "Mirassol",
    "Palmeiras", "Remo", "Santos", "Sao Paulo", "Sport Recife", "Vasco",
    "Vitoria",
]

# Live-FD:n BSA-nimet (verifioitu /api/fixtures-listasta 17.7) → odotettu
# mallinimi. Kattaa normalisointipolun (aksentit, klubi-tokenit) + overridet.
BSA_FD_TO_MODEL = {
    "Botafogo FR": "Botafogo RJ",
    "CA Mineiro": "Atletico-MG",
    "CA Paranaense": "Athletico-PR",
    "Chapecoense AF": "Chapecoense-SC",
    "Clube do Remo": "Remo",
    "Coritiba FBC": "Coritiba",
    "CR Flamengo": "Flamengo RJ",
    "Cruzeiro EC": "Cruzeiro",
    "EC Bahia": "Bahia",
    "EC Vitória": "Vitoria",
    "Fluminense FC": "Fluminense",
    "Grêmio FBPA": "Gremio",
    "Mirassol FC": "Mirassol",
    "RB Bragantino": "Bragantino",
    "São Paulo FC": "Sao Paulo",
    "SC Corinthians Paulista": "Corinthians",
    "SC Internacional": "Internacional",
    "SE Palmeiras": "Palmeiras",
    "Santos FC": "Santos",
    "Fortaleza EC": "Fortaleza",
    "CR Vasco da Gama": "Vasco",
}


def test_resolve_domestic_name_covers_live_bsa_names():
    from scripts.accuracy_pipeline import (
        DOMESTIC_COMPETITIONS, resolve_domestic_name,
    )
    overrides = DOMESTIC_COMPETITIONS["BSA"]["overrides"]
    for fd_name, expected in BSA_FD_TO_MODEL.items():
        got = resolve_domestic_name(fd_name, BSA_MODEL_TEAMS, overrides)
        assert got == expected, f"{fd_name!r}: odotettiin {expected!r}, saatiin {got!r}"


def test_resolve_domestic_name_unknown_returns_none():
    from scripts.accuracy_pipeline import resolve_domestic_name
    assert resolve_domestic_name("FC Nobody United", BSA_MODEL_TEAMS, {}) is None
    # Chapecoense ilman overrideä EI saa arvautua väärin normalisoinnilla —
    # "chapecoense" ⊆ "chapecoense sc" -osajoukko osuu yhteen kandidaattiin → OK,
    # mutta moniselitteinen ei koskaan: kaksi kandidaattia → None.
    assert resolve_domestic_name(
        "Atletico", ["Atletico-MG", "Atletico GO"], {}
    ) is None


def test_enabled_domestic_codes_gating(monkeypatch):
    from scripts import accuracy_pipeline as ap
    monkeypatch.delenv("ACC_DOMESTIC_COMPETITIONS", raising=False)
    assert ap.enabled_domestic_codes() == []          # oletus: OFF (GO-portti)
    monkeypatch.setenv("ACC_DOMESTIC_COMPETITIONS", "")
    assert ap.enabled_domestic_codes() == []
    monkeypatch.setenv("ACC_DOMESTIC_COMPETITIONS", "bsa, PL ,TYPO")
    assert ap.enabled_domestic_codes() == ["BSA", "PL"]  # typo ohitetaan


def test_tyhja_api_base_putoaa_oletukseen(monkeypatch):
    """TYHJA EI OLE PUUTTUVA (19.8).

    Workflow valittaa `${{ vars.ACC_PREDICT_API_BASE }}`, joka on tyhja
    merkkijono myos silloin kun repo-muuttujaa ei ole. `os.environ.get(k, def)`
    palautti silloin tyhjan, base oli "" ja jokainen kutsu meni osoitteeseen
    "/api/teams" -> MissingSchema -> domestic-logaus ohitettiin YHDEKSALLE
    liigalle kerralla, hiljaa varoituksen takana. Repo-migraatio 17.8 pyyhki
    muuttujat, ja se jaadytti julkisen track recordin.
    """
    import importlib
    from scripts import accuracy_pipeline as ap
    for arvo in ("", "   "):
        monkeypatch.setenv("ACC_PREDICT_API_BASE", arvo)
        importlib.reload(ap)
        assert ap.PREDICT_API_BASE == "https://api.goaliq.app"
    monkeypatch.delenv("ACC_PREDICT_API_BASE", raising=False)
    importlib.reload(ap)
    assert ap.PREDICT_API_BASE == "https://api.goaliq.app"
    # eksplisiittinen arvo voittaa, ja perassa oleva kauttaviiva siivotaan
    monkeypatch.setenv("ACC_PREDICT_API_BASE", "https://x.test/")
    importlib.reload(ap)
    assert ap.PREDICT_API_BASE == "https://x.test"
    monkeypatch.delenv("ACC_PREDICT_API_BASE", raising=False)
    importlib.reload(ap)


def test_wolves_resolvoituu_championshipissa():
    """FD sanoo koko nimen, malli sanoo "Wolves", eika kumpikaan ole toisen
    osajono. Ilman aliasta 45 ottelua ohitettiin yhdessa ajossa (19.8)."""
    from scripts.accuracy_pipeline import (
        DOMESTIC_COMPETITIONS, resolve_domestic_name)
    ov = DOMESTIC_COMPETITIONS["ELC"]["overrides"]
    teams = ["Wolves", "Preston", "Stoke", "West Ham"]
    assert resolve_domestic_name("Wolverhampton Wanderers FC", teams, ov) == "Wolves"


def test_teams_haku_yrittaa_uudelleen(monkeypatch):
    """Yksi epaonnistunut kutsu ohitti KOKO liigan kolmeksi tunniksi (19.8:
    Bundesliga ja Serie A saivat 404:n, kaksi minuuttia myohemmin 200)."""
    from scripts import accuracy_pipeline as ap

    class _R:
        def __init__(self, code, teams=None):
            self.status_code = code
            self._t = teams or []

        def json(self):
            return {"teams": self._t}

    kutsut = []

    def fake_get(url, params=None, timeout=None):
        kutsut.append(params["leagues"])
        return _R(404) if len(kutsut) < 3 else _R(200, ["Bayern", "Dortmund"])

    monkeypatch.setattr(ap, "PREDICT_API_BASE", "https://x.test")
    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)
    assert ap._fetch_model_teams("GER-Bundesliga-FD") == ["Bayern", "Dortmund"]
    assert len(kutsut) == 3


def test_teams_haku_luovuttaa_siististi(monkeypatch):
    """Kolmen yrityksen jalkeen None — liiga ohitetaan, ajo ei kaadu."""
    from scripts import accuracy_pipeline as ap

    def fake_get(url, params=None, timeout=None):
        raise RuntimeError("verkko nurin")

    monkeypatch.setattr(ap, "PREDICT_API_BASE", "https://x.test")
    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)
    assert ap._fetch_model_teams("ITA-Serie A-FD") is None


def _fd_match(mid, home, away, utc, status="TIMED", score=None):
    m = {
        "id": mid, "status": status, "utcDate": utc,
        "homeTeam": {"name": home}, "awayTeam": {"name": away},
    }
    if score is not None:
        m["status"] = "FINISHED"
        m["score"] = {"duration": "REGULAR",
                      "fullTime": {"home": score[0], "away": score[1]}}
    return m


def test_log_domestic_matches_prematch_only_and_idempotent():
    from datetime import datetime, timezone
    from scripts.accuracy_pipeline import log_domestic_matches

    now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    matches = [
        _fd_match(1001, "EC Bahia", "Chapecoense AF", "2026-07-18T00:30:00Z"),
        # jo alkanut → EI logata jälkikäteen
        _fd_match(1002, "Fluminense FC", "RB Bragantino", "2026-07-17T00:30:00Z"),
        # nimi joka ei resolvoidu → skip, ei kaatumista
        _fd_match(1003, "FC Nobody United", "EC Bahia", "2026-07-19T00:30:00Z"),
        # pelattu → ei logata
        _fd_match(1004, "SE Palmeiras", "Cruzeiro EC", "2026-07-16T00:30:00Z",
                  score=(2, 0)),
    ]

    def fake_predict(league, home, away):
        assert league == "BRA-Serie A"
        return {
            "home_team": home, "away_team": away,
            "p_home": 0.5, "p_draw": 0.3, "p_away": 0.2,
            "xg_home": 1.4, "xg_away": 0.9,
            "most_likely_score": "1-0", "predicted_winner": "home",
        }

    log = acc.empty_log()
    added, skipped = log_domestic_matches(
        log, "BSA", matches, BSA_MODEL_TEAMS, fake_predict, now=now)
    assert added == 1 and skipped == 1
    e = log["predictions"][0]
    assert e["match_id"] == "fd-1001"
    assert e["competition"] == "BSA"
    assert e["league"] == "BRA-Serie A"
    assert e["home_team"] == "Bahia"
    assert e["away_team"] == "Chapecoense-SC"
    assert e["predicted_winner"] == "home"

    # idempotentti: toinen ajo ei duplikoi
    added2, _ = log_domestic_matches(
        log, "BSA", matches, BSA_MODEL_TEAMS, fake_predict, now=now)
    assert added2 == 0
    assert len(log["predictions"]) == 1


# ---------------------------------------------------------------------------
# PRE-KICKOFF REFRESH (23.8.2026) — ennuste jäätyy kickoffiin, ei ensinäkemään
# ---------------------------------------------------------------------------
def _pending_entry(mid, kickoff, *, comp="ELC", league="ENG-Championship",
                   winner="home", logged_at="2026-08-01T00:00:00+00:00"):
    return {
        "match_id": mid, "source": "fd", "competition": comp, "league": league,
        "date": kickoff[:10], "kickoff": kickoff,
        "home_team": "Preston", "away_team": "Wolves",
        "p_home": 0.37, "p_draw": 0.30, "p_away": 0.33,
        "xg_home": 1.34, "xg_away": 1.26,
        "most_likely_score": "1-1", "predicted_winner": winner,
        "logged_at": logged_at, "result": None,
    }


def _away_predict(league, home, away):
    return {
        "home_team": home, "away_team": away,
        "p_home": 0.2844, "p_draw": 0.291, "p_away": 0.4246,
        "xg_home": 1.18, "xg_away": 1.484,
        "most_likely_score": "1-1", "predicted_winner": "away",
    }


def test_refresh_updates_upcoming_and_freezes_at_kickoff():
    """Ikkunassa oleva tuleva ottelu päivittyy; kickoffin ohittanut EI."""
    from datetime import datetime, timezone
    from scripts.accuracy_pipeline import refresh_prematch_predictions

    now = datetime(2026, 8, 22, 6, 0, tzinfo=timezone.utc)
    log = acc.empty_log()
    log["predictions"] += [
        _pending_entry("fd-1", "2026-08-22T14:00:00Z"),   # 8 h päässä -> päivittyy
        _pending_entry("fd-2", "2026-08-22T05:00:00Z"),   # jo alkanut -> lukossa
        _pending_entry("fd-3", "2026-09-30T14:00:00Z"),   # ikkunan ulkona -> ei
    ]

    paivitetyt, ohitetut = refresh_prematch_predictions(
        log, _away_predict, codes=["ELC"], now=now, window_h=48, sweep_max=0)

    assert (paivitetyt, ohitetut) == (1, 0)
    e1, e2, e3 = log["predictions"]
    assert e1["predicted_winner"] == "away" and e1["p_away"] == 0.4246
    assert e1["first_logged_at"] == "2026-08-01T00:00:00+00:00"
    assert e1["logged_at"] != "2026-08-01T00:00:00+00:00"
    assert e1["refresh_count"] == 1
    # kickoffin jälkeen ja ikkunan ulkopuolella: bittitarkasti ennallaan
    for e in (e2, e3):
        assert e["predicted_winner"] == "home" and e["p_home"] == 0.37
        assert "refreshed_at" not in e and "first_logged_at" not in e


def test_refresh_skips_resolved_void_and_disabled_competitions():
    from datetime import datetime, timezone
    from scripts.accuracy_pipeline import refresh_prematch_predictions

    now = datetime(2026, 8, 22, 6, 0, tzinfo=timezone.utc)
    log = acc.empty_log()
    gradattu = _pending_entry("fd-10", "2026-08-22T14:00:00Z")
    log["predictions"].append(gradattu)
    acc.set_result(log, "fd-10", 1, 3)
    siirretty = _pending_entry("fd-11", "2026-08-22T14:00:00Z")
    siirretty["void"] = True
    log["predictions"].append(siirretty)
    # kilpailu jota ei ole kytketty päälle
    log["predictions"].append(
        _pending_entry("fd-12", "2026-08-22T14:00:00Z", comp="BSA",
                       league="BRA-Serie A"))

    paivitetyt, ohitetut = refresh_prematch_predictions(
        log, _away_predict, codes=["ELC"], now=now, window_h=48, sweep_max=0)

    assert (paivitetyt, ohitetut) == (0, 0)
    assert all(e["predicted_winner"] == "home" for e in log["predictions"])


def test_refresh_keeps_old_prediction_when_api_fails():
    """Kaatunut /api/predict EI saa tyhjentää tai rikkoa jo logattua riviä."""
    from datetime import datetime, timezone
    from scripts.accuracy_pipeline import refresh_prematch_predictions

    now = datetime(2026, 8, 22, 6, 0, tzinfo=timezone.utc)
    log = acc.empty_log()
    log["predictions"].append(_pending_entry("fd-20", "2026-08-22T14:00:00Z"))
    ennen = dict(log["predictions"][0])

    paivitetyt, ohitetut = refresh_prematch_predictions(
        log, lambda *_: None, codes=["ELC"], now=now, window_h=48, sweep_max=0)

    assert (paivitetyt, ohitetut) == (0, 1)
    assert log["predictions"][0] == ennen


def test_refresh_cap_takes_nearest_kickoffs_first():
    """Katto ei ole hiljainen ja se pudottaa kaukaisimmat kickoffit."""
    from datetime import datetime, timezone
    from scripts.accuracy_pipeline import refresh_prematch_predictions

    now = datetime(2026, 8, 22, 0, 0, tzinfo=timezone.utc)
    log = acc.empty_log()
    for i, tunti in enumerate((20, 4, 12)):
        log["predictions"].append(
            _pending_entry(f"fd-3{i}", f"2026-08-22T{tunti:02d}:00:00Z"))

    paivitetyt, _ = refresh_prematch_predictions(
        log, _away_predict, codes=["ELC"], now=now, window_h=48, limit=2,
        sweep_max=0)

    assert paivitetyt == 2
    paivittyi = {e["match_id"] for e in log["predictions"]
                 if e["predicted_winner"] == "away"}
    assert paivittyi == {"fd-31", "fd-32"}   # 04:00 ja 12:00, ei 20:00


def test_sweep_refreshes_far_future_oldest_first():
    """Ikkunan ulkopuoliset sivut päivittyvät kierrossa, vanhin ensin."""
    from datetime import datetime, timezone
    from scripts.accuracy_pipeline import refresh_prematch_predictions

    now = datetime(2026, 8, 22, 6, 0, tzinfo=timezone.utc)
    log = acc.empty_log()
    # kaikki kaukana kickoffista -> ei kuumassa ikkunassa
    log["predictions"] += [
        _pending_entry("fd-vanha", "2027-03-03T15:00:00Z",
                       logged_at="2026-08-01T00:00:00+00:00"),
        _pending_entry("fd-uudempi", "2027-03-10T15:00:00Z",
                       logged_at="2026-08-19T00:00:00+00:00"),
        # juuri päivitetty -> alle min-iän, ei kosketa
        _pending_entry("fd-tuore", "2027-03-17T15:00:00Z",
                       logged_at="2026-08-22T02:00:00+00:00"),
    ]

    paivitetyt, _ = refresh_prematch_predictions(
        log, _away_predict, codes=["ELC"], now=now, window_h=48,
        sweep_max=1, sweep_min_age_h=20)

    assert paivitetyt == 1
    vanha, uudempi, tuore = log["predictions"]
    assert vanha["predicted_winner"] == "away"      # vanhin ensin
    assert uudempi["predicted_winner"] == "home"    # katto -> seuraavaan ajoon
    assert tuore["predicted_winner"] == "home"      # alle min-iän


def test_sweep_skips_recently_refreshed_even_without_cap():
    """Min-ikä on oma vahtinsa: katto EI saa olla se joka rajaa tuoreen pois."""
    from datetime import datetime, timezone
    from scripts.accuracy_pipeline import refresh_prematch_predictions

    now = datetime(2026, 8, 22, 6, 0, tzinfo=timezone.utc)
    log = acc.empty_log()
    log["predictions"] += [
        _pending_entry("fd-vanha", "2027-03-03T15:00:00Z",
                       logged_at="2026-08-01T00:00:00+00:00"),
        _pending_entry("fd-tuore", "2027-03-17T15:00:00Z",
                       logged_at="2026-08-22T02:00:00+00:00"),   # 4 h sitten
    ]

    # katto ei sido (10 >> 2) -> jos tuore päivittyy, min-ikä ei ole voimassa
    paivitetyt, _ = refresh_prematch_predictions(
        log, _away_predict, codes=["ELC"], now=now, window_h=48,
        sweep_max=10, sweep_min_age_h=20)

    assert paivitetyt == 1
    vanha, tuore = log["predictions"]
    assert vanha["predicted_winner"] == "away"
    assert tuore["predicted_winner"] == "home"
    assert "refreshed_at" not in tuore


def test_sweep_off_leaves_far_future_untouched():
    from datetime import datetime, timezone
    from scripts.accuracy_pipeline import refresh_prematch_predictions

    now = datetime(2026, 8, 22, 6, 0, tzinfo=timezone.utc)
    log = acc.empty_log()
    log["predictions"].append(_pending_entry("fd-kaukana", "2027-03-03T15:00:00Z"))

    paivitetyt, _ = refresh_prematch_predictions(
        log, _away_predict, codes=["ELC"], now=now, window_h=48, sweep_max=0)

    assert paivitetyt == 0
    assert log["predictions"][0]["predicted_winner"] == "home"


# ---------------------------------------------------------------------------
# LEAD-TIME: mitä track record oikeasti mittaa
# ---------------------------------------------------------------------------
def test_lead_hours_and_by_lead_split():
    log = acc.empty_log()
    tuore = _entry("fd-40", "home", mls="2-1", date="2026-08-22")
    tuore.update(kickoff="2026-08-22T14:00:00Z",
                 logged_at="2026-08-22T02:00:00+00:00")
    vanha = _entry("fd-41", "home", mls="2-1", date="2026-08-22")
    vanha.update(kickoff="2026-08-22T14:00:00Z",
                 logged_at="2026-08-01T14:00:00+00:00")
    siemen = _entry("fd-42", "home", mls="2-1", date="2026-08-22")
    siemen.update(kickoff="2026-08-22T14:00:00Z")   # logged_at = None
    for e in (tuore, vanha, siemen):
        acc.upsert_prediction(log, e)
        acc.set_result(log, e["match_id"], 2, 1)

    assert acc.lead_hours(tuore) == 12.0
    assert acc.lead_hours(vanha) == 504.0
    assert acc.lead_hours(siemen) is None

    by_lead = acc.compute_aggregate(log)["by_lead"]
    assert by_lead["fresh"]["n"] == 1
    assert by_lead["stale"]["n"] == 1
    assert by_lead["unknown"]["n"] == 1
    assert by_lead["fresh_max_lead_h"] == acc.LEAD_FRESH_MAX_H
    # headline ei muutu lead-jaosta
    assert acc.compute_aggregate(log)["all_time"]["n"] == 3


def test_domestic_reconcile_via_combined_matches():
    """WC-lokirivit + domestic-rivi reconciloituvat samasta yhdistelmälistasta
    eikä WC-riveihin kosketa (fd-id:t uniikkeja)."""
    from datetime import datetime, timezone
    from scripts.accuracy_pipeline import cmd_reconcile, log_domestic_matches

    now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    log = acc.empty_log()
    # olemassa oleva WC-rivi (jo reconciloitu) — ei saa muuttua
    acc.upsert_prediction(log, _entry("fd-500", "home", mls="2-1"))
    acc.set_result(log, "fd-500", 2, 1)
    wc_before = dict(log["predictions"][0]["result"])

    matches = [_fd_match(1001, "EC Bahia", "Chapecoense AF",
                         "2026-07-18T00:30:00Z")]

    def fake_predict(league, home, away):
        return {"home_team": home, "away_team": away,
                "p_home": 0.5, "p_draw": 0.3, "p_away": 0.2,
                "xg_home": 1.4, "xg_away": 0.9,
                "most_likely_score": "1-0", "predicted_winner": "home"}

    log_domestic_matches(log, "BSA", matches, BSA_MODEL_TEAMS, fake_predict,
                         now=now)
    # ottelu pelataan: FINISHED 90 min 1-1 → named winner home = miss
    finished = [_fd_match(1001, "EC Bahia", "Chapecoense AF",
                          "2026-07-18T00:30:00Z", score=(1, 1))]
    cmd_reconcile(log, finished)
    dom = next(e for e in log["predictions"] if e["match_id"] == "fd-1001")
    assert dom["result"]["actual_outcome"] == "draw"
    assert dom["result"]["hit_1x2"] is False
    assert log["predictions"][0]["result"] == wc_before  # WC-rivi koskematon


def test_aggregate_by_competition_split():
    log = acc.empty_log()
    acc.upsert_prediction(log, _entry("w1", "home", mls="2-1"))      # WC
    acc.set_result(log, "w1", 2, 1)                                   # hit
    e = _entry("b1", "away", mls="0-1")
    e["competition"] = "BSA"
    acc.upsert_prediction(log, e)
    acc.set_result(log, "b1", 2, 0)                                   # miss
    agg = acc.compute_aggregate(log)
    assert agg["all_time"]["n"] == 2                                  # blended
    assert agg["all_time"]["correct_1x2"] == 1
    bc = agg["by_competition"]
    assert bc["WC"]["n"] == 1 and bc["WC"]["correct_1x2"] == 1        # WC säilyy
    assert bc["BSA"]["n"] == 1 and bc["BSA"]["correct_1x2"] == 0


# ---------------------------------------------------------------------------
# 10.8.2026: siirretty ottelu ei ole "odottaa tulosta".
#
# Nelja 29.7. BSA-ottelua oli FD:ssa POSTPONED. Ne eivat gradautuneet (oikein,
# niita ei pelattu) mutta ne jaivat pending-tilaan — ja koska pending-lista on
# kickoff-jarjestyksessa nousevasti, ne istuivat JULKISEN "tulevat ennusteet"
# -lohkon KARJESSA 12 paivaa, sekä mobiilissa etta webissa.
# ---------------------------------------------------------------------------
def test_postponed_match_is_voided_not_pending():
    from scripts.accuracy_pipeline import cmd_reconcile

    log = acc.empty_log()
    acc.upsert_prediction(log, _entry("fd-900", "home", mls="1-0"))
    acc.upsert_prediction(log, _entry("fd-901", "home", mls="1-0"))

    cmd_reconcile(log, [
        _fd_match(900, "A", "B", "2026-07-29T00:00:00Z", status="POSTPONED"),
        _fd_match(901, "C", "D", "2026-09-01T00:00:00Z", status="TIMED"),
    ])

    voided = next(e for e in log["predictions"] if e["match_id"] == "fd-900")
    normal = next(e for e in log["predictions"] if e["match_id"] == "fd-901")
    assert voided["void"] == "POSTPONED"
    assert voided.get("result") is None
    # Negatiivinen kontrolli: tavallinen pelaamaton rivi EI saa void-merkintaa.
    # Ilman tata testi menisi lapi myos jos jokainen gradaamaton mitatoitaisiin.
    assert "void" not in normal

    agg = acc.compute_aggregate(log)
    assert agg["pending"] == 1
    assert agg["voided"] == 1


def test_voided_match_is_not_graded_if_replayed_later():
    """Kuukausia myohemmin pelattu ottelu EI saa gradautua heinakuun
    ennusteella: se koski eri joukkuetilannetta."""
    from scripts.accuracy_pipeline import cmd_reconcile

    log = acc.empty_log()
    acc.upsert_prediction(log, _entry("fd-902", "home", mls="1-0"))
    cmd_reconcile(log, [_fd_match(902, "A", "B", "2026-07-29T00:00:00Z",
                                  status="POSTPONED")])
    # sama id palaa myohemmin pelattuna
    cmd_reconcile(log, [_fd_match(902, "A", "B", "2026-11-02T00:00:00Z",
                                  score=(2, 0))])

    e = next(x for x in log["predictions"] if x["match_id"] == "fd-902")
    assert e["void"] == "POSTPONED"
    assert e.get("result") is None


def test_is_pending_is_the_single_source_for_both_surfaces():
    """API ja generoidut sivut kayttavat SAMAA predikaattia.

    10.8: void-suodatin lisattiin ensin vain accuracy.pending_rows'iin, ja
    build_fpl_page rakensi oman listansa omalla ehdollaan -> mobiili
    korjaantui ja web olisi jaanyt nayttamaan neljaa siirrettya ottelua.
    Sama vikaluokka kuin 8.8. SPA:n Fixtures/Table.
    """
    import inspect
    from scripts import build_fpl_page as bp

    assert acc.is_pending({}) is True
    assert acc.is_pending({"result": {"actual_outcome": "home"}}) is False
    assert acc.is_pending({"void": "POSTPONED"}) is False
    # Sivubuilderi kayttaa jaettua predikaattia eika omaa ehtoaan.
    assert bp.acc_is_pending is acc.is_pending
    src = inspect.getsource(bp.update_predictions)
    assert 'not e.get("result")' not in src, (
        "sivubuilderilla on taas oma pending-ehto - kaytä acc_is_pending")
