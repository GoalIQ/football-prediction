"""Henkilokohtaiset FPL-tyokalut Premiumiin (Villen paatos 17.10.2026).

Spec: goaliq-app cos-reports/2026-10-17-tyokalut-maksumuuriin-spec.md.

Kolme porttia (CLAUDE.md 6a):

  (a) VAIHEINVARIANTTI (6a kohta 3). Lukitus on AJASTETTU KYTKIN
      (`api.premium.PERSONAL_TOOLS_ENFORCE_FROM`, 21.10.2026 00:00 UTC).
      Testi joka ajettaisiin vain tanaan mittaisi vain "ennen"-haaraa ja
      lakkaisi olemasta tosi 21.10. Siksi sama funktio ajetaan synteettisilla
      hetkilla ennen ja jalkeen kytkimen, jokaisella kutsujatyypilla.
  (b) AJONAIKAINEN MASKI JOKAISELLA REITILLA. TestClient: anonyymi kytkimen
      jalkeen -> `meta.masked` + `meta.locked_tool` ja henkilokohtainen data
      typistetty; Premium -> taysi; admin ilman esikatselua -> ei lukitusta;
      admin + `X-Preview-Lock: 1` -> maski jo ennen kytkinta. FPL-kutsut
      monkeypatchataan builder-tasolla: testi ei saa riippua live-FPL:sta
      (tests.yml kaatui 17.10 juuri live-FPL:n 503:een).
  (c) KUTSUPAIKKAPORTTI. Jokainen henkilokohtainen reitti kutsuu kytkinta ja
      maskia, ja jokaisella on ajonaikainen testi (b):ssa. Muisti
      `testi-kutsuu-funktiota-ei-kutsupaikkaa`: maskifunktion yksikkotesti ei
      todista etta reitti kutsuu sita.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

import api.premium as prem  # noqa: E402
from test_premium_enforcement import (  # noqa: E402
    FREE_EXPECTED, GATED_EXPECTED, PARTIAL_EXPECTED, PERSONAL_TOOL_ROUTES,
)

UTC = timezone.utc
KYTKIN = datetime(2026, 10, 21, 0, 0, tzinfo=UTC)
ENNEN = KYTKIN - timedelta(seconds=1)
JALKEEN = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
KAUDEN_LOPPU = datetime(2027, 5, 30, 18, 0, tzinfo=UTC)

ADMIN = "testi-admin-token-17-10"


# ---------------------------------------------------------------------------
# Kutsujat
# ---------------------------------------------------------------------------

def _request(headers: dict | None = None) -> Request:
    raw = [(k.lower().encode("latin-1"), v.encode("latin-1"))
           for k, v in (headers or {}).items()]
    return Request({"type": "http", "method": "GET", "path": "/",
                    "headers": raw, "query_string": b""})


@pytest.fixture()
def kutsujat(monkeypatch):
    """Enforcement paalla, admin-token konfiguroitu, premium-token tunnettu.

    Ilmaisikkuna kiinni injektoimalla (ei kellosta): muuten kirjautunut
    ei-premium saisi premiumin ikkunan aikana ja testi mittaisi ikkunaa.
    """
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN)
    monkeypatch.setattr(prem, "free_premium_window_active",
                        lambda *a, **k: False)
    monkeypatch.setattr(prem, "_verify_token_user_id",
                        lambda t: {"premium-ok": "user-premium",
                                   "free-ok": "user-free"}.get(t))
    monkeypatch.setattr(prem, "_profile_is_premium",
                        lambda uid: uid == "user-premium")
    monkeypatch.setattr(prem, "_web_subscription_active", lambda uid: False)
    with prem._PREMIUM_CACHE_LOCK:
        prem._PREMIUM_CACHE.clear()
    yield {
        "anonyymi": {},
        "kirjautunut-ilmainen": {"Authorization": "Bearer free-ok"},
        "premium": {"Authorization": "Bearer premium-ok"},
        "admin": {"X-Admin-Token": ADMIN},
        "admin-esikatselu": {"X-Admin-Token": ADMIN, "X-Preview-Lock": "1"},
        "vaara-admin-esikatselu": {"X-Admin-Token": "vaara",
                                   "X-Preview-Lock": "1"},
    }
    with prem._PREMIUM_CACHE_LOCK:
        prem._PREMIUM_CACHE.clear()


# ---------------------------------------------------------------------------
# (a) Vaiheinvariantti
# ---------------------------------------------------------------------------

#: kutsuja -> odotettu maski vaiheittain (ennen, kytkimen hetki, jalkeen,
#: kauden loppu). Taulukko ON vaite: muutos tarkoittaa etta joku muuttaa sita
#: kuka saa henkilokohtaiset tyokalut.
ODOTUS = {
    "anonyymi": (False, True, True, True),
    "kirjautunut-ilmainen": (False, True, True, True),
    "premium": (False, False, False, False),
    "admin": (False, False, False, False),
    "admin-esikatselu": (True, True, True, True),
    # Esikatseluotsake ilman kelvollista admin-tokenia on tavallinen kutsu.
    "vaara-admin-esikatselu": (False, True, True, True),
}
VAIHEET = (ENNEN, KYTKIN, JALKEEN, KAUDEN_LOPPU)


def test_kytkimen_hetki_on_paatos():
    """Hetki pinnataan: sen siirto nakyy diffissa paatoksena."""
    assert prem.PERSONAL_TOOLS_ENFORCE_FROM == KYTKIN
    assert prem.PERSONAL_TOOLS_ENFORCE_FROM.tzinfo is not None
    assert prem.FREE_PERSONAL_TOOL_ROWS == 0


@pytest.mark.parametrize("kutsuja", sorted(ODOTUS))
def test_vaiheinvariantti_jokaiselle_kutsujalle(kutsujat, kutsuja):
    """Sama funktio, synteettiset hetket: ennen kytkinta ei maskia
    (paitsi ylläpitäjän esikatselu), kytkimen hetkesta kauden loppuun maski
    jokaiselle ei-Premiumille."""
    req = _request(kutsujat[kutsuja])
    saatu = tuple(prem.personal_tools_mask_applies(req, now=t) for t in VAIHEET)
    assert saatu == ODOTUS[kutsuja], (kutsuja, saatu)


@pytest.mark.parametrize("kutsuja", sorted(ODOTUS))
def test_kello_luetaan_yhdesta_paikasta(kutsujat, monkeypatch, kutsuja):
    """Erotteleva kontrolli edelliselle: reitit kutsuvat kytkinta ILMAN
    `now`-parametria, joten kellon on tultava `_utcnow`ista. Jos funktio
    lukisi kellon muualta, tama mittaisi nykyhetkea eika vaihetta."""
    req = _request(kutsujat[kutsuja])
    saatu = []
    for t in VAIHEET:
        monkeypatch.setattr(prem, "_utcnow", lambda t=t: t)
        saatu.append(prem.personal_tools_mask_applies(req))
    assert tuple(saatu) == ODOTUS[kutsuja], (kutsuja, saatu)


def test_ennen_kytkinta_ei_yhtaan_premium_hakua(kutsujat, monkeypatch):
    """Ennen kytkinta vastaus ja viive ovat ennallaan: is_premium_requestia
    (Supabase) ei kutsuta lainkaan."""
    def ei_saa_kutsua(_req):
        raise AssertionError("premium-haku ennen kytkinta")
    monkeypatch.setattr(prem, "is_premium_request", ei_saa_kutsua)
    for kutsuja in ("anonyymi", "premium", "kirjautunut-ilmainen"):
        assert prem.personal_tools_mask_applies(
            _request(kutsujat[kutsuja]), now=ENNEN) is False


def test_enforcement_pois_ei_maskaa_koskaan(kutsujat, monkeypatch):
    """Sama linja kuin muissa maskeissa: PREMIUM_ENFORCE pois -> kaikki
    premiumia, paitsi ylläpitäjän eksplisiittinen esikatselu."""
    monkeypatch.setenv("PREMIUM_ENFORCE", "off")
    for t in VAIHEET:
        assert prem.personal_tools_mask_applies(_request(), now=t) is False
        assert prem.personal_tools_mask_applies(
            _request(kutsujat["admin-esikatselu"]), now=t) is True


@pytest.mark.parametrize("window_open", [True, False],
                         ids=["ikkuna-auki", "ikkuna-kiinni"])
def test_anonyymi_lukittu_ilmaisikkunasta_riippumatta(kutsujat, monkeypatch,
                                                      window_open):
    """Ilmaisikkuna koskee kirjautuneita. Anonyymi pysyy lukittuna."""
    monkeypatch.setattr(prem, "free_premium_window_active",
                        lambda *a, **k: window_open)
    assert prem.personal_tools_mask_applies(_request(), now=JALKEEN) is True


# ---------------------------------------------------------------------------
# Maskifunktiot (yksikko): muoto, ei mutaatiota, ei em dashia
# ---------------------------------------------------------------------------

def _rate_team_full() -> dict:
    return {
        "meta": {"mode": "entry", "entry": 424242, "gw": 8, "free_transfers": 1,
                 "chips": {"played": [], "remaining": []},
                 "horizon_total_from": 8, "horizon_total_gw": 5,
                 "note_code": "rate_team.note.model_projections"},
        "team": {"players": [{"id": 1, "web_name": "Pelaaja Yksi",
                              "xp_per_gw": 6.1, "is_captain": True}],
                 "missing_ids": [99], "bank": 1.5},
        "last_finished": {"gw": 7, "players": [{"id": 1, "points": 12}]},
        "season_rank": {"overall_rank": 123456},
        "rating": {"team_xp_gw": 61.2, "team_xp_horizon": 301.5,
                   "team_xp_horizon_no_captain": 290.1, "percentile": 87.4,
                   "rating": 87, "rating_max": 100, "beats_benchmark": False,
                   "optimal_proven": True, "optimal_team_xp": 333.3,
                   "gap_to_optimal_xp": 43.2, "strongest_line": "MID",
                   "weakest_line": "DEF"},
        "captain": {"pick": {"id": 1, "web_name": "Pelaaja Yksi", "gw_xp": 7.7},
                    "alternative": None},
        "transfers": {"suggestions": [{"out": {"web_name": "Pelaaja Kaksi"},
                                       "in": {"web_name": "Pelaaja Kolme"},
                                       "delta_xp_horizon": 4.4}],
                      "hold": False, "window_gws": [8, 9, 10],
                      "note": "Deltas are per single transfer",
                      "hold_verdict": {"verdict": "transfer",
                                       "message": "worth a transfer"}},
    }


def test_rate_team_esimaku_kentat():
    full = _rate_team_full()
    out = prem.mask_rate_team_preview_payload(full)
    r = out["rating"]
    # Esimaku jaa arvoineen.
    for f in prem.RATE_TEAM_PREVIEW_RATING_FIELDS:
        assert r[f] == full["rating"][f], f
    # Premium-kentat: avain sailyy, arvo on paikanpitaja.
    for f, p in prem.RATE_TEAM_PREMIUM_RATING_FIELDS.items():
        assert r[f] == p, f
    assert set(r) == set(full["rating"])
    assert out["team"] == {"players": [], "missing_ids": [], "bank": 1.5}
    assert out["captain"] is None and out["last_finished"] is None
    assert out["season_rank"] == full["season_rank"]
    assert out["transfers"] == {"suggestions": [], "hold": None,
                                "window_gws": [], "note": None,
                                "hold_verdict": None}
    m = out["meta"]
    assert m["masked"] is True and m["locked_tool"] == "rate-my-team"
    assert m["entry"] == 424242 and m["chips"] == full["meta"]["chips"]
    assert "rating.team_xp_gw" in m["premium_fields"]
    assert "captain" in m["premium_fields"]
    # Alkuperaista ei mutatoida (premium-kutsut jakavat saman olion).
    assert full == _rate_team_full()


def test_rate_team_esimaku_typistaa_uuden_kentan_oletuksena():
    """6a kohta 1: builderiin lisatty uusi lohko ei vuoda unohduksen takia."""
    full = _rate_team_full()
    full["uusi_lohko"] = {"players": [{"web_name": "Vuoto"}], "x": 1.0}
    full["rating"]["uusi_luku"] = 5.5
    out = prem.mask_rate_team_preview_payload(full)
    assert out["uusi_lohko"] is None
    assert out["rating"]["uusi_luku"] is None
    assert "Vuoto" not in repr(out)


LOCK_MASKS = {
    "mask_model_squad_payload": "rate-my-team",
    "mask_gw_review_payload": "gw-review",
    "mask_my_team_ledger_payload": "season-ledger",
    "mask_fit_payload": "fit-checker",
    "mask_defcon_live_payload": "defcon-live",
    "mask_h2h_payload": "league",
}


@pytest.mark.parametrize("nimi", sorted(LOCK_MASKS))
def test_lukittu_maski_pitaa_avaimet_ja_typistaa(nimi):
    full = {"meta": {"available": True, "gw": 7, "generated_at": "g"},
            "players": [{"id": 1, "web_name": "Vuotava Nimi"}],
            "totals": {"projected": 55.5, "rows": [1, 2]},
            "message": "Vuotava Nimi costs 2.0 xP", "p_a": 0.61}
    kopio = repr(full)
    out = getattr(prem, nimi)(full)
    assert set(out) == set(full)
    assert out["players"] == [] and out["message"] is None
    assert out["totals"] == {"projected": None, "rows": []}
    assert out["p_a"] is None
    assert "Vuotava Nimi" not in repr(out)
    m = out["meta"]
    assert m["masked"] is True and m["locked_tool"] == LOCK_MASKS[nimi]
    assert m["available"] is False and m["gw"] == 7
    assert m["mask"] and "—" not in m["mask"] and "–" not in m["mask"]
    assert repr(full) == kopio, "alkuperainen mutatoitui"


def test_kaikki_maskiselitteet_ilman_em_dashia():
    """Selitteet ovat julkisessa API-vastauksessa (englanti, ei em dashia)."""
    full = _rate_team_full()
    selitteet = [prem.mask_rate_team_preview_payload(full)["meta"]["mask"],
                 prem.mask_price_watch_entry_payload(
                     {"meta": {}, "risers": [], "fallers": []})["meta"]["mask"],
                 prem.mask_differentials_entry_payload(
                     {"meta": {}, "players": []})["meta"]["mask"]]
    selitteet += [getattr(prem, n)({"meta": {}})["meta"]["mask"]
                  for n in LOCK_MASKS]
    for s in selitteet:
        assert s and "—" not in s and "–" not in s, s
        assert s.isascii(), s


# ---------------------------------------------------------------------------
# (b) Reitit: synteettiset builderit
# ---------------------------------------------------------------------------

def _fake_rate_team(monkeypatch):
    import src.models.fpl_rate_team as rt
    monkeypatch.setattr(rt, "rate_team", lambda **kw: _rate_team_full())


def _fake_model_squad(monkeypatch):
    import src.models.fpl_rate_team as rt
    xp_data = {"meta": {"generated_at": "lukko-fixture", "horizon_gw": 6,
                        "next_gameweek": 8, "horizon_total_from": 8,
                        "horizon_total_gw": 5}, "players": []}
    rivit = [{"id": 100 + i, "web_name": f"Mallirivi{i}", "team_short": "AAA",
              "element_type": 1 + (i % 4)} for i in range(15)]
    monkeypatch.setattr(rt, "build_context", lambda *a, **k: (xp_data, {}, [], {}))
    monkeypatch.setattr(rt, "free_optimum", lambda pool, key: {
        "xi": rivit[:11], "bench": rivit[11:], "xi_xp": 312.34, "proven": True})


def _fake_gw_review(monkeypatch):
    from src.data import fpl_api
    from src.models import fpl_actuals
    import src.models.model_squad_scores as mss
    picks = {"picks": [{"element": 90010, "multiplier": 2, "is_captain": True,
                        "position": 1},
                       {"element": 90011, "multiplier": 1, "position": 2}],
             "entry_history": {"points": 20, "event_transfers_cost": 0},
             "active_chip": None, "automatic_subs": []}
    boot = {"teams": [{"id": 1, "short_name": "AAA"}],
            "element_types": [{"id": 3, "singular_name_short": "MID"}],
            "elements": [{"id": 90010, "web_name": "Katsaus Kymppi", "team": 1,
                          "element_type": 3, "chance_of_playing_next_round": 75,
                          "news": "Knock"},
                         {"id": 90011, "web_name": "Katsaus Ykkonen", "team": 1,
                          "element_type": 3, "chance_of_playing_next_round": None,
                          "news": ""}],
            "events": [{"id": 3, "finished": True, "data_checked": True}]}
    monkeypatch.setattr(fpl_api, "fetch_entry_picks", lambda *a, **k: picks)
    monkeypatch.setattr(fpl_api, "fetch_bootstrap", lambda *a, **k: boot)
    monkeypatch.setattr(fpl_actuals, "frozen_xp_for",
                        lambda gw: {90010: 5.0, 90011: 3.0})
    monkeypatch.setattr(fpl_actuals, "points_for",
                        lambda gw, *a, **k: {90010: 8, 90011: 2})
    monkeypatch.setattr(fpl_actuals, "frozen_meta", lambda gw: {
        "frozen_at": "2026-10-03T09:00:00Z", "deadline": "2026-10-03T10:30:00Z"})
    monkeypatch.setattr(mss, "provisional_hint_gws", lambda: [])


def _fake_ledger(monkeypatch):
    from src.data import fpl_api
    from src.models import fpl_actuals
    import src.models.model_squad_scores as mss
    monkeypatch.setattr(fpl_actuals, "frozen_xp_for", lambda gw: {90010: 5.0})
    monkeypatch.setattr(fpl_api, "fetch_entry_history", lambda *a, **k: {
        "current": [{"event": 1, "points": 58, "event_transfers_cost": 0,
                     "points_on_bench": 3}]})
    monkeypatch.setattr(fpl_api, "fetch_entry_picks", lambda *a, **k: {
        "picks": [{"element": 90010, "multiplier": 2}]})
    monkeypatch.setattr(fpl_api, "fetch_bootstrap", lambda *a, **k: {"events": [
        {"id": 1, "finished": True, "data_checked": True,
         "average_entry_score": 50}]})
    monkeypatch.setattr(fpl_api, "fetch_fixtures", lambda *a, **k: [
        {"event": 1, "finished_provisional": True,
         "kickoff_time": "2026-08-22T14:00:00Z"}])
    monkeypatch.setattr(mss, "provisional_hint_gws", lambda: [])


def _fake_fit(monkeypatch):
    import src.models.fpl_fit as ff
    rivi = {"id": 7, "web_name": "Sovitus Pelaaja", "team_short": "AAA",
            "pos": "MID", "price": 8.0, "xp_horizon_total": 30.1,
            "xp_per_gw": 6.0}
    monkeypatch.setattr(ff, "fit_squad", lambda ids: {
        "meta": {"horizon_gw": 6, "horizon_total_from": 8, "horizon_total_gw": 5,
                 "next_gameweek": 8, "generated_at": "g", "budget_cap": 100.0,
                 "squad_cost": 99.5, "bank": 0.5},
        "locked": [rivi], "xi": [rivi] * 11, "bench": [rivi] * 4,
        "totals": {"xi_xp_horizon": 300.1, "optimal_xp_horizon": 310.2,
                   "delta_xp": -10.1, "optimal_proven": True},
        "message": "Fitting Sovitus Pelaaja costs 10.1 xP"})


def _fake_defcon_live(monkeypatch):
    import src.models.fpl_defcon_live as dl
    monkeypatch.setattr(dl, "load_defcon_live", lambda **kw: {
        "meta": {"available": True, "gw": 8, "generated_at": "g",
                 "gw_state": "live", "thresholds": {"DEF": 10}, "note": "rule"},
        "players": [{"id": 5, "web_name": "Puolustaja Live", "defcon": 9,
                     "threshold": 10, "story": {"tag": "CLOSE", "line": "x"}}]})


def _fake_h2h(monkeypatch):
    import api.fantasy_edge as fe
    xp_data = {"meta": {"generated_at": "g"}}
    monkeypatch.setattr(fe, "build_context", lambda *a, **k: (xp_data, {}, [], {}))
    monkeypatch.setattr(fe, "_resolve_gw", lambda boot, gw: 8)
    monkeypatch.setattr(fe, "clamp_gw_to_projections", lambda g, pool, xp: 8)
    monkeypatch.setattr(fe, "_entry_xi_xp", lambda entry, *a: (
        55.0 if entry == 1 else 50.0, 100.0, 11, [], f"Joukkue {entry}"))


_PW_PAYLOAD = {"meta": {"generated_at": "g", "disclaimer": "estimate"},
               "risers": [{"id": 1, "web_name": "Nousija", "eta_days": 0},
                          {"id": 2, "web_name": "Toinen", "eta_days": 2}],
               "fallers": [{"id": 3, "web_name": "Laskija", "eta_days": 1}]}


def _fake_price_watch(monkeypatch, kutsut: list):
    import copy as _copy
    import src.models.fpl_my_team as mt
    import src.models.fpl_price_watch as pw
    import src.models.fpl_rate_team as rt
    monkeypatch.setattr(pw, "load_price_watch",
                        lambda *a, **k: _copy.deepcopy(_PW_PAYLOAD))
    monkeypatch.setattr(rt, "get_bootstrap", lambda: {})

    def squad(boot, entry, players=None):
        kutsut.append(entry)
        return {"available": True, "entry": entry, "ids": {1, 3},
                "bank_tenths": 15, "gw": 8, "note": None}
    monkeypatch.setattr(mt, "squad_context", squad)


def _fake_differentials(monkeypatch, kutsut: list):
    import api.main as m
    import src.models.fpl_planner as pl

    def finder(max_ownership=10.0, pos=None, squad=None, **kw):
        out = {"meta": {"max_ownership": max_ownership, "generated_at": "g"},
               "players": [{"id": 4, "web_name": "Erottaja"}]}
        if squad is not None:
            out["meta"]["squad"] = {"entry": squad["entry"], "available": True}
            out["meta"]["owned_excluded"] = 1
            out["template_missing"] = [{"id": 9, "web_name": "Pohjapelaaja"}]
        return out

    def squad_ctx(entry, players=None):
        kutsut.append(entry)
        return None if entry is None else {"available": True, "entry": entry,
                                           "ids": {4}}
    monkeypatch.setattr(pl, "differential_finder", finder)
    monkeypatch.setattr(m, "_squad_ctx", squad_ctx)


# reitti -> (URL, fake, tarkistus maskatulle, tarkistus taydelle)

def _tarkista_rate_team_maski(d):
    assert d["team"]["players"] == [] and d["captain"] is None
    assert d["transfers"]["suggestions"] == []
    assert d["transfers"]["hold_verdict"] is None
    assert d["rating"]["rating"] == 87 and d["rating"]["weakest_line"] is None
    assert d["rating"]["team_xp_gw"] == 0.0
    assert d["last_finished"] is None
    assert d["season_rank"] == {"overall_rank": 123456}


def _tarkista_rate_team_taysi(d):
    assert d["team"]["players"] and d["captain"]["pick"]["web_name"]
    assert d["rating"]["weakest_line"] == "DEF"


REITIT = {
    "/api/fantasy/rate-team": (
        "/api/fantasy/rate-team?entry=424242", _fake_rate_team,
        "rate-my-team", _tarkista_rate_team_maski, _tarkista_rate_team_taysi,
        ("Pelaaja Yksi", "Pelaaja Kolme")),
    "/api/fantasy/model-squad": (
        "/api/fantasy/model-squad", _fake_model_squad, "rate-my-team",
        lambda d: (d["players"] == []
                   and d["meta"]["xi_xp_horizon"] is None
                   and d["meta"]["generated_at"] == "lukko-fixture") or
        pytest.fail(repr(d)),
        lambda d: len(d["players"]) == 15 or pytest.fail(repr(d)),
        ("Mallirivi",)),
    "/api/fantasy/gw-review": (
        "/api/fantasy/gw-review?entry=424242&gw=3", _fake_gw_review,
        "gw-review",
        lambda d: (d["review"]["players"] == []
                   and d["review"]["best_call"] is None
                   and d["flags"] == {"availability": [], "price": []}
                   and d["model_says"] == []
                   and d["meta"]["available"] is False
                   and d["meta"]["fpl_points"] is None
                   and d["meta"]["reviewed_gw"] == 3) or pytest.fail(repr(d)),
        lambda d: (d["meta"]["available"] is True
                   and len(d["review"]["players"]) == 2) or pytest.fail(repr(d)),
        ("Katsaus Kymppi", "Katsaus Ykkonen")),
    "/api/fantasy/my-team-ledger": (
        "/api/fantasy/my-team-ledger?entry=424242", _fake_ledger,
        "season-ledger",
        lambda d: (d["gameweeks"] == [] and d["meta"]["graded_gws"] == 0
                   and d["meta"]["available"] is False
                   and all(v is None for v in d["totals"].values()))
        or pytest.fail(repr(d)),
        lambda d: (d["meta"]["graded_gws"] == 1
                   and d["gameweeks"][0]["actual"] == 58) or pytest.fail(repr(d)),
        ()),
    "/api/fantasy/fit": (
        "/api/fantasy/fit?locked=7", _fake_fit, "fit-checker",
        lambda d: (d["xi"] == [] and d["locked"] == [] and d["bench"] == []
                   and d["message"] is None
                   and all(v is None for v in d["totals"].values())
                   and d["meta"]["squad_cost"] is None
                   and d["meta"]["budget_cap"] == 100.0) or pytest.fail(repr(d)),
        lambda d: len(d["xi"]) == 11 or pytest.fail(repr(d)),
        ("Sovitus Pelaaja",)),
    "/api/fantasy/defcon-live": (
        "/api/fantasy/defcon-live?entry=424242", _fake_defcon_live,
        "defcon-live",
        lambda d: (d["players"] == [] and d["meta"]["gw"] == 8
                   and d["meta"]["available"] is False) or pytest.fail(repr(d)),
        lambda d: len(d["players"]) == 1 or pytest.fail(repr(d)),
        ("Puolustaja Live",)),
    "/api/fantasy/h2h": (
        "/api/fantasy/h2h?entry_a=1&entry_b=2", _fake_h2h, "league",
        lambda d: (d["p_a"] is None and d["p_b"] is None
                   and d["entry_a"]["team_name"] is None
                   and d["entry_a"]["missing_ids"] == []
                   and d["meta"]["method"]) or pytest.fail(repr(d)),
        lambda d: (0 < d["p_a"] < 1 and d["entry_a"]["xi_xp"] == 55.0)
        or pytest.fail(repr(d)),
        ("Joukkue 1", "Joukkue 2")),
}

# Reitit joiden julkinen osa jaa ilmaiseksi: maski laukeaa vain `entry`n
# kanssa. Mitataan omissa testeissaan alla (spy: joukkuetta ei haeta).
# Captain: ilman entrya (draft) 15.8-esimaku (yksi valinta) jaa.
ENTRY_REITIT = {"/api/fantasy/price-watch", "/api/fantasy/differentials",
                "/api/fantasy/captain"}


def _get(client, url, headers):
    r = client.get(url, headers=headers)
    assert r.status_code == 200, (url, r.status_code, r.text[:300])
    return r


@pytest.fixture()
def client():
    import api.main as m
    return TestClient(m.app)


@pytest.mark.parametrize("reitti", sorted(REITIT))
def test_anonyymi_kytkimen_jalkeen_saa_lukitun(client, kutsujat, monkeypatch,
                                                reitti):
    url, fake, slug, maskattu, _taysi, nimet = REITIT[reitti]
    fake(monkeypatch)
    monkeypatch.setattr(prem, "_utcnow", lambda: JALKEEN)
    for kutsuja in ("anonyymi", "kirjautunut-ilmainen"):
        r = _get(client, url, kutsujat[kutsuja])
        d = r.json()
        assert d["meta"]["masked"] is True, (reitti, kutsuja)
        assert d["meta"]["locked_tool"] == slug
        assert d["meta"]["mask"]
        maskattu(d)
        vuoti = [n for n in nimet if n in r.text]
        assert not vuoti, f"{reitti} ({kutsuja}) vuoti: {vuoti}"


@pytest.mark.parametrize("reitti", sorted(REITIT))
def test_premium_saa_tayden_kytkimen_jalkeen(client, kutsujat, monkeypatch,
                                             reitti):
    url, fake, _slug, _maskattu, taysi, _nimet = REITIT[reitti]
    fake(monkeypatch)
    monkeypatch.setattr(prem, "_utcnow", lambda: JALKEEN)
    d = _get(client, url, kutsujat["premium"]).json()
    assert "locked_tool" not in (d.get("meta") or {}), reitti
    assert (d.get("meta") or {}).get("masked") is not True, reitti
    taysi(d)


@pytest.mark.parametrize("reitti", sorted(REITIT))
def test_admin_ilman_esikatselua_ei_lukitusta(client, kutsujat, monkeypatch,
                                              reitti):
    """CI ja skriptit. Rate-teamilla admin (ei premium-tokenia) saa 5.9:n
    ei-Premium-rajan (siirrot pois), mutta EI uutta lukitusta."""
    url, fake, _slug, _maskattu, taysi, _nimet = REITIT[reitti]
    fake(monkeypatch)
    monkeypatch.setattr(prem, "_utcnow", lambda: JALKEEN)
    d = _get(client, url, kutsujat["admin"]).json()
    assert "locked_tool" not in (d.get("meta") or {}), reitti
    taysi(d)


@pytest.mark.parametrize("reitti", sorted(REITIT))
def test_admin_esikatselu_lukitsee_ennen_kytkinta(client, kutsujat,
                                                  monkeypatch, reitti):
    url, fake, slug, maskattu, _taysi, _nimet = REITIT[reitti]
    fake(monkeypatch)
    monkeypatch.setattr(prem, "_utcnow", lambda: ENNEN)
    d = _get(client, url, kutsujat["admin-esikatselu"]).json()
    assert d["meta"]["masked"] is True and d["meta"]["locked_tool"] == slug
    maskattu(d)


@pytest.mark.parametrize("reitti", sorted(REITIT))
def test_anonyymi_ennen_kytkinta_ei_lukitusta(client, kutsujat, monkeypatch,
                                              reitti):
    """NEGATIIVINEN KONTROLLI: ennen 21.10 sama kutsu ei lukitu. Ilman tata
    edellinen lapaisisi myos silloin jos maski olisi paalla aina."""
    url, fake, _slug, _maskattu, taysi, _nimet = REITIT[reitti]
    fake(monkeypatch)
    monkeypatch.setattr(prem, "_utcnow", lambda: ENNEN)
    d = _get(client, url, kutsujat["anonyymi"]).json()
    assert "locked_tool" not in (d.get("meta") or {}), reitti
    taysi(d)


def test_rate_team_anonyymi_ennen_kytkinta_saa_5_9_maskin(client, kutsujat,
                                                          monkeypatch):
    """Ennen kytkinta ei-Premiumin raja on 5.9-maski (siirrot pois), ei
    esimaku eika taysi vastaus."""
    _fake_rate_team(monkeypatch)
    monkeypatch.setattr(prem, "_utcnow", lambda: ENNEN)
    d = _get(client, "/api/fantasy/rate-team?entry=424242",
             kutsujat["anonyymi"]).json()
    assert d["meta"]["masked"] is True and "locked_tool" not in d["meta"]
    assert d["transfers"]["suggestions"] == []
    assert d["team"]["players"] and d["captain"]["pick"]


# --- price-watch + differentials: julkinen lista jaa, entry lukittu --------

def test_price_watch_entry_lukittu_julkinen_lista_jaa(client, kutsujat,
                                                      monkeypatch):
    kutsut: list = []
    _fake_price_watch(monkeypatch, kutsut)
    monkeypatch.setattr(prem, "_utcnow", lambda: JALKEEN)
    d = _get(client, "/api/fantasy/price-watch?entry=424242",
             kutsujat["anonyymi"]).json()
    assert d["meta"]["masked"] is True
    assert d["meta"]["locked_tool"] == "price-watch"
    assert "owned" not in d and "squad" not in d["meta"]
    assert [r["id"] for r in d["risers"]] == [1, 2]
    assert all("owned" not in r for r in d["risers"] + d["fallers"])
    assert kutsut == [], "lukitulle haettiin joukkue FPL:sta"


def test_price_watch_ilman_entrya_ennallaan_kytkimen_jalkeen(client, kutsujat,
                                                             monkeypatch):
    """Julkinen lista: ei lippua, ei kytkimen vaikutusta."""
    kutsut: list = []
    _fake_price_watch(monkeypatch, kutsut)
    monkeypatch.setattr(prem, "_utcnow", lambda: JALKEEN)
    d = _get(client, "/api/fantasy/price-watch", kutsujat["anonyymi"]).json()
    assert "masked" not in d["meta"] and "locked_tool" not in d["meta"]
    assert len(d["risers"]) == 2 and kutsut == []


@pytest.mark.parametrize("kutsuja,vaihe,lukittu", [
    ("premium", JALKEEN, False), ("admin", JALKEEN, False),
    ("anonyymi", ENNEN, False), ("admin-esikatselu", ENNEN, True)])
def test_price_watch_entry_muut_kutsujat(client, kutsujat, monkeypatch,
                                         kutsuja, vaihe, lukittu):
    kutsut: list = []
    _fake_price_watch(monkeypatch, kutsut)
    monkeypatch.setattr(prem, "_utcnow", lambda: vaihe)
    d = _get(client, "/api/fantasy/price-watch?entry=424242",
             kutsujat[kutsuja]).json()
    if lukittu:
        assert d["meta"]["locked_tool"] == "price-watch" and "owned" not in d
        assert kutsut == []
    else:
        assert "locked_tool" not in d["meta"]
        assert d["owned"]["n_rising"] == 1 and d["meta"]["squad"]["entry"] == 424242
        assert kutsut == [424242]


def test_differentials_entry_lukittu_julkinen_lista_jaa(client, kutsujat,
                                                        monkeypatch):
    kutsut: list = []
    _fake_differentials(monkeypatch, kutsut)
    monkeypatch.setattr(prem, "_utcnow", lambda: JALKEEN)
    r = _get(client, "/api/fantasy/differentials?max_ownership=10&entry=424242",
             kutsujat["anonyymi"])
    d = r.json()
    assert d["meta"]["masked"] is True
    assert d["meta"]["locked_tool"] == "differentials"
    assert "template_missing" not in d and "squad" not in d["meta"]
    assert [p["id"] for p in d["players"]] == [4]
    assert "Pohjapelaaja" not in r.text
    assert kutsut == [], "lukitulle haettiin joukkue FPL:sta"


def test_differentials_ilman_entrya_ennallaan_kytkimen_jalkeen(client, kutsujat,
                                                               monkeypatch):
    """scripts/build_reply_module.py hakee taman anonyymina ILMAN entrya
    (Bluesky-vastausmoduuli). Vastaus ei saa muuttua kytkimen jalkeen."""
    kutsut: list = []
    _fake_differentials(monkeypatch, kutsut)
    monkeypatch.setattr(prem, "_utcnow", lambda: ENNEN)
    ennen = _get(client, "/api/fantasy/differentials?max_ownership=10",
                 kutsujat["anonyymi"]).json()
    monkeypatch.setattr(prem, "_utcnow", lambda: JALKEEN)
    jalkeen = _get(client, "/api/fantasy/differentials?max_ownership=10",
                   kutsujat["anonyymi"]).json()
    assert ennen == jalkeen
    assert "masked" not in jalkeen["meta"] and jalkeen["players"]


@pytest.mark.parametrize("kutsuja,vaihe,lukittu", [
    ("premium", JALKEEN, False), ("admin", JALKEEN, False),
    ("anonyymi", ENNEN, False), ("admin-esikatselu", ENNEN, True)])
def test_differentials_entry_muut_kutsujat(client, kutsujat, monkeypatch,
                                           kutsuja, vaihe, lukittu):
    kutsut: list = []
    _fake_differentials(monkeypatch, kutsut)
    monkeypatch.setattr(prem, "_utcnow", lambda: vaihe)
    d = _get(client, "/api/fantasy/differentials?max_ownership=10&entry=424242",
             kutsujat[kutsuja]).json()
    if lukittu:
        assert d["meta"]["locked_tool"] == "differentials"
        assert "template_missing" not in d and kutsut == []
    else:
        assert "locked_tool" not in d["meta"]
        assert d["template_missing"] and kutsut == [424242]


# --- captain: oma XI (entry) lukittu, draft-esimaku jaa ---------------------

_KAPTEENIT = [{"id": 90001 + i, "web_name": f"Kapteeni Ehdokas{i}",
               "team_short": "AAA", "gw_xp": 7.0 - i, "owned_pct": 30.0,
               "gap_to_top": float(i)} for i in range(3)]


def _fake_captain(monkeypatch):
    import copy as _copy
    import src.models.fpl_planner as pl

    def picker(entry=None, gw=None, players=None):
        return {"meta": {"gw": 8, "generated_at": "g",
                         "availability_gate": {
                             "checked": True, "note": "gate",
                             "dropped": [{"id": 90009,
                                          "web_name": "Sivussa Oleva"}]}},
                "top3": _copy.deepcopy(_KAPTEENIT),
                "differential": {"id": 90008, "web_name": "Erikois Kapteeni",
                                 "gw_xp": 5.1, "owned_pct": 2.0}}
    monkeypatch.setattr(pl, "captain_picker", picker)


_CAP_ENTRY = "/api/fantasy/captain?entry=424242"
_CAP_DRAFT = "/api/fantasy/captain?players=" + ",".join(
    str(i) for i in range(1, 16))


def test_captain_entry_lukittu_kytkimen_jalkeen(client, kutsujat, monkeypatch):
    _fake_captain(monkeypatch)
    monkeypatch.setattr(prem, "_utcnow", lambda: JALKEEN)
    for kutsuja in ("anonyymi", "kirjautunut-ilmainen"):
        r = _get(client, _CAP_ENTRY, kutsujat[kutsuja])
        d = r.json()
        assert d["meta"]["masked"] is True, kutsuja
        assert d["meta"]["locked_tool"] == "rate-my-team"
        assert d["meta"]["free_rows"] == 0 and d["meta"]["total_rows"] == 3
        assert d["top3"] == [] and d["differential"] is None
        assert d["meta"]["availability_gate"]["dropped"] == []
        m = d["meta"]["mask"]
        assert m.isascii() and "—" not in m and "–" not in m
        vuoti = [n for n in ("Kapteeni Ehdokas", "Erikois Kapteeni",
                             "Sivussa Oleva") if n in r.text]
        assert not vuoti, f"{kutsuja} vuoti: {vuoti}"


def test_captain_draft_esimaku_jaa_kytkimen_jalkeen(client, kutsujat,
                                                    monkeypatch):
    """Ilman entrya (draft) 15.8-raja pysyy: yksi valinta, ei lukitusta."""
    _fake_captain(monkeypatch)
    monkeypatch.setattr(prem, "_utcnow", lambda: JALKEEN)
    d = _get(client, _CAP_DRAFT, kutsujat["anonyymi"]).json()
    assert "locked_tool" not in d["meta"]
    assert d["meta"]["masked"] is True
    assert [p["web_name"] for p in d["top3"]] == ["Kapteeni Ehdokas0"]
    assert d["differential"] is None


@pytest.mark.parametrize("kutsuja,vaihe,url,odotus", [
    # (kutsuja, hetki, URL, "lukittu" | "esimaku" | "taysi")
    ("anonyymi", ENNEN, _CAP_ENTRY, "esimaku"),
    ("anonyymi", ENNEN, _CAP_DRAFT, "esimaku"),
    ("premium", JALKEEN, _CAP_ENTRY, "taysi"),
    ("premium", JALKEEN, _CAP_DRAFT, "taysi"),
    # Admin ilman esikatselua ei ole premium: 15.8-raja, ei lukitusta.
    ("admin", JALKEEN, _CAP_ENTRY, "esimaku"),
    ("admin-esikatselu", ENNEN, _CAP_ENTRY, "lukittu"),
    ("admin-esikatselu", ENNEN, _CAP_DRAFT, "esimaku"),
], ids=["anon-ennen-entry", "anon-ennen-draft", "premium-entry",
        "premium-draft", "admin-entry", "esikatselu-entry",
        "esikatselu-draft"])
def test_captain_vaiheet_ja_kutsujat(client, kutsujat, monkeypatch, kutsuja,
                                     vaihe, url, odotus):
    _fake_captain(monkeypatch)
    monkeypatch.setattr(prem, "_utcnow", lambda: vaihe)
    d = _get(client, url, kutsujat[kutsuja]).json()
    if odotus == "lukittu":
        assert d["meta"]["locked_tool"] == "rate-my-team"
        assert d["top3"] == [] and d["differential"] is None
    elif odotus == "esimaku":
        assert "locked_tool" not in d["meta"]
        assert len(d["top3"]) == prem.FREE_CAPTAIN_PICKS == 1
        assert d["differential"] is None
    else:
        assert d["meta"].get("masked") is not True
        assert len(d["top3"]) == 3 and d["differential"]["web_name"]


def test_captain_entry_maski_ei_mutatoi():
    full = {"meta": {"availability_gate": {"dropped": [{"id": 1}]}},
            "top3": [{"id": 1}], "differential": {"id": 2}}
    kopio = repr(full)
    out = prem.mask_captain_entry_payload(full)
    assert out["top3"] == [] and out["differential"] is None
    assert repr(full) == kopio


def test_reply_moduuli_hakee_differentialsin_ilman_entrya():
    """Kutsupaikka: Bluesky-vastausmoduulin URL ei kanna entrya, joten se saa
    julkisen listan myos kytkimen jalkeen (ks. edellinen testi)."""
    src = (ROOT / "scripts" / "build_reply_module.py").read_text(encoding="utf-8")
    urlit = re.findall(r'f?"[^"\n]*?/api/fantasy/differentials[^"\n]*"', src)
    assert urlit, "differentials-kutsu katosi build_reply_modulesta"
    assert all("entry" not in u for u in urlit), urlit


# ---------------------------------------------------------------------------
# (c) Kutsupaikkaportti
# ---------------------------------------------------------------------------

def _rungot() -> dict[str, str]:
    pat = re.compile(r'@(?:app|router)\.(?:get|post)\("(/api/fantasy/[^"]+)"')
    out: dict[str, str] = {}
    for tiedosto in ("main.py", "fantasy_edge.py"):
        rivit = (ROOT / "api" / tiedosto).read_text(encoding="utf-8").split("\n")
        osumat = [(i, m.group(1)) for i, ln in enumerate(rivit)
                  if (m := pat.match(ln.strip()))]
        for k, (i, polku) in enumerate(osumat):
            loppu = osumat[k + 1][0] if k + 1 < len(osumat) else len(rivit)
            out[polku] = "\n".join(rivit[i:loppu])
    return out


@pytest.mark.parametrize("reitti", sorted(PERSONAL_TOOL_ROUTES))
def test_reitti_kutsuu_kytkinta_ja_maskia(reitti):
    runko = _rungot().get(reitti)
    assert runko, f"{reitti} ei loydy"
    assert "request: Request" in runko, f"{reitti}: ei Request-parametria"
    kutsut = runko.count("personal_tools_mask_applies(request)")
    assert kutsut >= 1, f"{reitti}: ei kutsu personal_tools_mask_applies"
    assert re.search(r"return mask_\w+_payload\(", runko), (
        f"{reitti}: kytkin ilman maskia")


def test_jokaisella_henkilokohtaisella_reitilla_on_ajonaikainen_testi():
    """Uusi henkilokohtainen reitti ei paase PERSONAL_TOOL_ROUTESiin ilman
    TestClient-mittausta (REITIT tai ENTRY_REITIT). Ilman tata kutsupaikka-
    portti olisi pelkka merkkijonohaku."""
    katetut = set(REITIT) | ENTRY_REITIT
    assert katetut == PERSONAL_TOOL_ROUTES, (
        sorted(PERSONAL_TOOL_ROUTES ^ katetut))


def test_henkilokohtainen_reitti_ei_ole_ilmainen_luokittelussa():
    assert not (PERSONAL_TOOL_ROUTES & FREE_EXPECTED)
    assert PERSONAL_TOOL_ROUTES <= (GATED_EXPECTED | PARTIAL_EXPECTED)
