"""Mallin rivin gradaus + provisionaalisuuden kanto pintaan (25.8.2026).

🔴 TAUSTA: `/api/fantasy/model-race` luki `data/model_squad_gw_scores.json`:aa
jota EI OLLUT OLEMASSA eika mikaan kirjoittanut. Jonossa oli useita riveja
joiden heratysehto oli "GW1 gradattu", ja endpoint vastasi "First scores land
once GW1 finishes" viela senkin jalkeen kun GW1 oli pelattu. Este ei ollut
FPL:n lippu vaan puuttuva gradaaja - selite nimesi vaaran mekanismin.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from src.models.fpl_model_race import build_race

ROOT = Path(__file__).resolve().parents[1]


def _load_grader():
    spec = importlib.util.spec_from_file_location(
        "grade_model_squad", ROOT / "scripts" / "grade_model_squad.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Gradattavuus: finished_provisional per ottelu, EI event.finished
# ---------------------------------------------------------------------------
def _boot(events):
    return {"events": events}


def test_kierros_on_gradattavissa_kun_kaikki_ottelut_pelattu():
    """🔴 Tama on koko skriptin olemassaolon syy.

    Mitattu 25.8 klo 07 UTC: GW1 pelattiin 21.-24.8, kaikki 10 ottelua olivat
    `finished_provisional: true`, mutta `event.finished` ja `data_checked`
    olivat molemmat yha False. `event.finished`:in odottaminen olisi pitanyt
    kierroksen poissa tuotteesta yli vuorokauden sen paattymisen jalkeen.
    """
    g = _load_grader()
    boot = _boot([{"id": 1, "finished": False, "data_checked": False,
                   "average_entry_score": 48}])
    fixtures = [{"event": 1, "finished_provisional": True} for _ in range(10)]
    st = g._gw_status(boot, fixtures)
    assert st[1]["gradable"] is True, (
        "kierros jonka kaikki ottelut on pelattu on gradattavissa, vaikka "
        "FPL ei olisi viela kaantanyt event.finished-lippua")
    assert st[1]["provisional"] is True, "data_checked False -> provisionaalinen"
    assert st[1]["fpl_average"] == 48


def test_kesken_oleva_kierros_ei_ole_gradattavissa():
    """Yksikin pelaamaton ottelu estaa gradauksen. Ilman tata kierros
    gradattaisiin kesken, ja `points` kasvaisi jalkikateen."""
    g = _load_grader()
    boot = _boot([{"id": 2, "finished": False, "data_checked": False,
                   "average_entry_score": 0}])
    fixtures = ([{"event": 2, "finished_provisional": True} for _ in range(9)]
                + [{"event": 2, "finished_provisional": False}])
    assert g._gw_status(boot, fixtures)[2]["gradable"] is False


def test_data_checked_poistaa_provisionaalisuuden():
    g = _load_grader()
    boot = _boot([{"id": 1, "finished": True, "data_checked": True,
                   "average_entry_score": 48}])
    fixtures = [{"event": 1, "finished_provisional": True}]
    st = g._gw_status(boot, fixtures)
    assert st[1]["gradable"] is True
    assert st[1]["provisional"] is False


def test_kierros_ilman_otteluita_jaa_pois():
    """Tyhja fixture-lista ei ole 'kaikki pelattu'. `all([])` on True, joten
    ilman tata vartiointia tuleva kierros olisi 'gradattavissa'."""
    g = _load_grader()
    boot = _boot([{"id": 38, "finished": False, "data_checked": False,
                   "average_entry_score": 0}])
    assert 38 not in g._gw_status(boot, [])


# ---------------------------------------------------------------------------
# Provisionaalisuus kannetaan pintaan asti
# ---------------------------------------------------------------------------
def test_provisionaalinen_kierros_merkitaan_payloadissa():
    """Luku saa nakya heti, mutta se EI saa esiintya lopullisena."""
    race = build_race({"gameweeks": [
        {"gw": 1, "points": 41, "fpl_average": 48, "provisional": True},
    ]}, None)
    assert race["meta"]["graded_gws"] == 1
    assert race["meta"]["provisional_gws"] == [1]
    assert race["gameweeks"][0]["provisional"] is True


def test_lopullinen_kierros_ei_kanna_lippua():
    race = build_race({"gameweeks": [
        {"gw": 1, "points": 41, "fpl_average": 48, "provisional": False},
    ]}, None)
    assert race["meta"]["provisional_gws"] == []
    assert race["gameweeks"][0]["provisional"] is False


def test_puuttuva_lippu_luetaan_lopulliseksi_ei_kaadu():
    """Vanha lokirivi ilman kenttaa: kaytos entinen, ei poikkeusta."""
    race = build_race({"gameweeks": [
        {"gw": 1, "points": 41, "fpl_average": 48},
    ]}, None)
    assert race["meta"]["provisional_gws"] == []
    assert race["gameweeks"][0]["provisional"] is False


def test_sekaotos_merkitsee_vain_provisionaaliset():
    race = build_race({"gameweeks": [
        {"gw": 1, "points": 41, "fpl_average": 48, "provisional": False},
        {"gw": 2, "points": 55, "fpl_average": 50, "provisional": True},
    ]}, None)
    assert race["meta"]["provisional_gws"] == [2]
    assert race["meta"]["graded_gws"] == 2
    assert [r["provisional"] for r in race["gameweeks"]] == [False, True]


def test_tyhja_loki_sanoo_yha_ettei_ole_alkanut():
    """Regressiovahti: provisionaalisuuden lisays ei saa rikkoa esikauden
    polkua, joka vastaa available=False + selite."""
    race = build_race({"gameweeks": []}, None)
    assert race["meta"]["available"] is False
    assert race["meta"]["graded_gws"] == 0
    assert race["gameweeks"] == []


# ---------------------------------------------------------------------------
# 25.8: idempotenssi — muuttumaton data ei saa tuottaa committia
# ---------------------------------------------------------------------------
def test_muuttumaton_rivi_sailyttaa_graded_at_leiman(tmp_path, monkeypatch):
    """🔴 `graded_at` on "milloin TAMA RIVI gradattiin", ei "milloin skripti
    viimeksi ajoi".

    Mitattu 25.8: cronin ensimmainen ajo tuotti committin jossa diff oli
    PELKAT kaksi aikaleimaa. 6 h cronilla se olisi neljä turhaa committia
    vuorokaudessa ikuisesti, ja git-historia lakkaisi kertomasta milloin luku
    oikeasti muuttui.
    """
    g = _load_grader()
    out = tmp_path / "scores.json"
    monkeypatch.setattr(g, "OUT_PATH", out)

    boot = _boot([{"id": 1, "finished": False, "data_checked": False,
                   "average_entry_score": 48}])
    fixtures = [{"event": 1, "finished_provisional": True}]
    monkeypatch.setattr(g.fpl_api, "fetch_bootstrap", lambda **kw: boot)
    monkeypatch.setattr(g.fpl_api, "fetch_fixtures", lambda **kw: fixtures)
    monkeypatch.setattr(g.fpl_api, "fetch_entry_history", lambda *a, **kw: {
        "current": [{"event": 1, "points": 41, "points_on_bench": 12,
                     "event_transfers_cost": 0}]})
    monkeypatch.setattr(g.fpl_api, "fetch_entry_picks", lambda *a, **kw: {
        "active_chip": None, "automatic_subs": [],
        "picks": [{"element": 426, "multiplier": 2, "is_captain": True}]})
    monkeypatch.setattr(g.fpl_api, "fetch_event_live", lambda *a, **kw: {
        "elements": [{"id": 426, "stats": {"total_points": 1}}]})

    import json as _j
    eka = g.build(verbose=False)

    # 🔴 EI "aja kahdesti ja vertaa". Ensimmainen versio tasta testista teki
    # tasan niin, ja MUTAATIOTESTI PALJASTI SEN SOKEAKSI: molemmat ajot osuvat
    # samaan sekuntiin, ja `.replace(microsecond=0)` pyoristaa leimat samaksi
    # myos silloin kun idempotenssi on rikki. Kolme mutaatiota meni lapi.
    #
    # Nyt levylla oleva leima on ERIKSEEN VANHA, joten "sailytettiin" ja
    # "generoitiin nyt" eroavat vuosilla eivatka mikrosekunneilla.
    VANHA = "2020-01-01T00:00:00+00:00"
    levylla = _j.loads(_j.dumps(eka))
    levylla["meta"]["generated_at"] = VANHA
    levylla["gameweeks"][0]["graded_at"] = VANHA
    out.write_text(_j.dumps(levylla, ensure_ascii=False), encoding="utf-8")

    toka = g.build(verbose=False)

    assert toka["gameweeks"][0]["graded_at"] == VANHA, (
        "muuttumaton rivi sai uuden graded_at-leiman -> cron committaisi "
        "joka ajolla")
    assert toka["meta"]["generated_at"] == VANHA, (
        "muuttumaton tiedosto sai uuden generated_at-leiman")
    # ...ja kaikki muu on identtista
    assert {k: v for k, v in toka["gameweeks"][0].items() if k != "graded_at"} ==            {k: v for k, v in eka["gameweeks"][0].items() if k != "graded_at"}


def test_muuttunut_pistemaara_paivittaa_leiman(tmp_path, monkeypatch):
    """...mutta oikea muutos SAA uuden leiman. Ilman tata idempotenssikorjaus
    olisi jaadyttanyt leiman ikuisesti ja piilottanut bonuspaivityksen."""
    g = _load_grader()
    out = tmp_path / "scores.json"
    monkeypatch.setattr(g, "OUT_PATH", out)
    import json as _j
    out.write_text(_j.dumps({
        "meta": {"generated_at": "2026-08-25T00:00:00+00:00"},
        "gameweeks": [{"gw": 1, "points": 39, "bench_points": 12,
                       "transfer_cost": 0, "fpl_average": 48,
                       "captain_id": 426, "captain_points_added": 1,
                       "active_chip": None, "autosubs": [],
                       "provisional": True,
                       "graded_at": "2026-08-25T00:00:00+00:00"}],
    }), encoding="utf-8")

    boot = _boot([{"id": 1, "finished": False, "data_checked": False,
                   "average_entry_score": 48}])
    monkeypatch.setattr(g.fpl_api, "fetch_bootstrap", lambda **kw: boot)
    monkeypatch.setattr(g.fpl_api, "fetch_fixtures",
                        lambda **kw: [{"event": 1, "finished_provisional": True}])
    # bonukset nostivat 39 -> 41
    monkeypatch.setattr(g.fpl_api, "fetch_entry_history", lambda *a, **kw: {
        "current": [{"event": 1, "points": 41, "points_on_bench": 12,
                     "event_transfers_cost": 0}]})
    monkeypatch.setattr(g.fpl_api, "fetch_entry_picks", lambda *a, **kw: {
        "active_chip": None, "automatic_subs": [],
        "picks": [{"element": 426, "multiplier": 2, "is_captain": True}]})
    monkeypatch.setattr(g.fpl_api, "fetch_event_live", lambda *a, **kw: {
        "elements": [{"id": 426, "stats": {"total_points": 1}}]})

    uusi = g.build(verbose=False)
    assert uusi["gameweeks"][0]["points"] == 41
    assert uusi["gameweeks"][0]["graded_at"] != "2026-08-25T00:00:00+00:00", (
        "oikea muutos ei saanut uutta leimaa")
    assert uusi["meta"]["generated_at"] != "2026-08-25T00:00:00+00:00"
