# -*- coding: utf-8 -*-
"""XP-HORIZON-ALKANUT-KIERROS, osa 2 (17.9.2026): JOKAINEN reitti joka
tarjoilee `xp_horizon_total`in tai siita johdetun summan kertoo OMASSA
metassaan mita summattiin.

SOPIMUS (kiinnitetty 17.9; SPA ja mobiili odottavat naita kaikilta
xP-summaa tarjoilevilta reiteilta: xp, compare, value, differentials,
rate-team, fit, spl):
  meta.horizon_total_from   int = ensimmainen summattu kierros (actionable)
  meta.horizon_total_gw     int = montako kierrosta summattiin

MITATTU 17.9 (synteettinen kesken-kierroksen vaihe, ks. probe raportissa):
poolin `xp_horizon_total` oli jo vaikutettavien kierrosten summa
(build_context ajaa attach_horizon_total_actionable:n), mutta vain
/api/fantasy/xp kantoi meta-avaimet. rate-team, fit, model-squad,
differentials, value, compare, edge, rival ja player-stats rakensivat
metansa kasin ja tarjoilivat summan ilman ikkunaa: klientti joka nimeaa
ikkunan `horizon_gw`:sta (sarakkeiden maara) kirjoittaa "next 6 GW" viiden
kierroksen summalle.

KOLME MEKANISMIA (CLAUDE.md 6a):
  (1) yksi lukija: `fpl_xp.horizon_total_meta(meta)` kopioi avaimet
      `attach_horizon_total_actionable`in kirjoittamasta metasta. Se ei
      laske mitaan itse, joten se ei voi olla eri mielta summan kanssa.
  (2) poikkeuslista perusteluineen: `EXEMPT` nimeaa jokaisen /api/fantasy-
      reitin joka EI tarjoile horisonttisummaa ja sanoo miksi. Uusi reitti
      ei paase lapi ennen kuin se on joko `TESTED`- tai `EXEMPT`-listalla,
      ja poikkeuksen vaite mitataan: probattava reitti ajetaan ja sen
      vastauksesta ei saa loytya summa-avainta.
  (3) invariantti mitataan vaiheessa jossa se voi rikkoutua: fikstuuri on
      KESKEN KIERROKSEN (GW1 alkanut, GW2:n deadline edessa). Vaikutettava
      summa on 5 x xp_gw ja raaka 6 x xp_gw, joten vanha koodi ei lapaise
      yhtakaan rivia, ja meta-avainten puuttuminen kaataa reitin nimelta.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api.main as m
import src.models.fpl_rate_team as rt
from src.models import fpl_player_stats as ps
from src.models import fpl_xp
from src.models.fpl_xp import horizon_total_meta
from tests.test_fpl_player_stats import _gw_doc, _gw_row, _stats_doc, _stats_row
from tests.test_fpl_rate_team import FAKE_PICKS, POOL_BOOT, POOL_PLAYERS

ROOT = Path(__file__).resolve().parents[1]
NEWLINE = chr(10)

# VAIHE: GW1 kesken (is_current), GW2:n deadline edessa. Artefaktin rivit
# GW1-6, vaikutettavat GW2-6 -> from=2, gw=5. Poolin xp_gw on vakio per
# pelaaja: raaka summa 6*xp_gw, vaikutettava 5*xp_gw. Vanha koodi (summa
# koko listasta) tuottaa siis ERI luvun jokaisella rivilla, ei vain
# puuttuvan avaimen.
NEXT_GW, DEADLINE_GW, HORIZON = 1, 2, 6
EXPECT_FROM, EXPECT_GW = 2, 5
XP_GW = {p["id"]: float(p["xp_per_gw"]) for p in POOL_PLAYERS}

# 🔴 18.9: ALKANEEN KIERROKSEN RIVI ON ERI SUURUINEN KUIN MUUT (2 x xp_gw).
# Poolin rivit olivat vakio per pelaaja, jolloin putken keskiarvo
# (raaka summa / 6) ja rajattu keskiarvo (rajattu summa / 5) ovat SAMA LUKU
# eika `xp_per_gw`-porttia voi erottaa exit-koodista. Nyt raaka summa on
# 7 x xp_gw ja raaka keskiarvo 7/6 x xp_gw, eli vanha kaytos tuottaa eri
# luvun jokaisella rivilla — myos keskiarvossa.
RAW_MULT = 7.0
RAW_TOTAL = {i: round(RAW_MULT * x, 2) for i, x in XP_GW.items()}
RAW_PER_GW = {i: round(RAW_MULT * x / HORIZON, 2) for i, x in XP_GW.items()}

BOOT = {
    "events": [{"id": 1, "is_current": True, "is_next": False, "finished": False},
               {"id": 2, "is_current": False, "is_next": True, "finished": False}],
    "elements": POOL_BOOT,
    "teams": [{"id": i, "name": f"Club{i}", "short_name": f"C{i:02d}"}
              for i in range(1, 11)],
}


def _fake_xp() -> dict:
    players = copy.deepcopy(POOL_PLAYERS)
    for p in players:
        # ARTEFAKTIN MUOTO: kentat ovat PUTKEN kirjoittamat (summa ja
        # keskiarvo koko listasta), koska tasan se on se raaka payload jonka
        # serve-polun lukijan pitaa korjata.
        p["gameweeks"][0]["xp"] = round(2 * float(p["xp_per_gw"]), 2)
        p["xp_horizon_total"] = round(sum(g["xp"] for g in p["gameweeks"]), 2)
        p["xp_per_gw"] = round(p["xp_horizon_total"] / HORIZON, 2)
    return {"meta": {"available": True, "season": "2026/27",
                     "generated_at": "meta-routes-fixture",
                     "next_gameweek": NEXT_GW, "deadline_gameweek": DEADLINE_GW,
                     "horizon_gw": HORIZON},
            "players": players}


@pytest.fixture(autouse=True)
def _mock(monkeypatch, tmp_path):
    def fake_fetch(path):
        if path == "/bootstrap-static/":
            return BOOT
        if path == "/entry/424242/":
            return {"id": 424242, "summary_overall_rank": 1000}
        if path == "/entry/424242/event/1/picks/":
            return FAKE_PICKS
        if path == "/entry/424242/history/":
            return {"chips": [], "current": [], "past": []}
        raise rt.RateTeamError(404, "Not found on the FPL API.")
    monkeypatch.setattr(rt, "_fetch_fpl", fake_fetch)
    monkeypatch.setattr(rt, "load_xp", _fake_xp)
    import api.fantasy_edge as fe
    monkeypatch.setattr(fe, "load_xp", _fake_xp)   # /api/fantasy/xp.csv
    rt._OPTIMAL_XP_CACHE.clear()
    rt._FPL_CACHE.clear()

    # /api/fantasy/xp lukee artefaktin levylta omalla polullaan
    xp_file = tmp_path / "xp.json"
    xp_file.write_text(json.dumps(_fake_xp()), encoding="utf-8")
    monkeypatch.setitem(fpl_xp.XP_PATHS, "fpl", xp_file)

    # player-stats lukee kolme levytiedostoa + elavan projektion
    # `load_xp_actionable`n kautta. Elava projektio kulkee AIDON lukijan
    # lapi samasta tiedostosta, jotta testi mittaa tuotantopolun.
    stats = _stats_doc([_stats_row(15, "P15", "MID"), _stats_row(16, "P16", "MID")],
                       finished=1)
    gw = _gw_doc({15: [_gw_row(1, 6)], 16: [_gw_row(1, 2)]}, max_gw=1)

    def fake_sources():
        return stats, gw, {}, fpl_xp.load_xp_actionable(xp_file)
    monkeypatch.setattr(ps, "load_sources", fake_sources)
    yield
    rt._OPTIMAL_XP_CACHE.clear()
    rt._FPL_CACHE.clear()


# ---------------------------------------------------------------------------
# Reittiluettelo: TESTED tarjoilee summan, EXEMPT ei (perustelu pakollinen)
# ---------------------------------------------------------------------------

# polku -> probe-URL. Jokainen palauttaa 200 fikstuurilla, kantaa summan ja
# kertoo ikkunan metassa.
TESTED: dict[str, str] = {
    "/api/fantasy/xp": "/api/fantasy/xp",
    "/api/fantasy/rate-team": "/api/fantasy/rate-team?entry=424242",
    "/api/fantasy/fit": "/api/fantasy/fit?locked=15",
    "/api/fantasy/model-squad": "/api/fantasy/model-squad",
    "/api/fantasy/differentials": "/api/fantasy/differentials?max_ownership=10",
    "/api/fantasy/value": "/api/fantasy/value?top_n=5&pairs_n=3",
    "/api/fantasy/compare": "/api/fantasy/compare?players=15,16",
    "/api/fantasy/edge": "/api/fantasy/edge?entry=424242",
    "/api/fantasy/rival": "/api/fantasy/rival?entry=424242&rival=424242&gap=10",
    "/api/fantasy/player-stats": "/api/fantasy/player-stats",
    # career: malliteaser tarjoilee rate-teamin `team_xp_horizon`in
    "/api/fantasy/career": "/api/fantasy/career?entry=424242",
}

# polku -> (probe-URL tai None, perustelu). Probattava reitti AJETAAN ja sen
# vastauksesta ei saa loytya summa-avainta; ilman probea reitin runko
# tarkistetaan lahteesta (ei xP-poolia, ei summakenttaa).
EXEMPT: dict[str, tuple[str | None, str]] = {
    "/api/fantasy": (None,
        "Phase 0: CS% + FDR joukkuetasolla (fpl_phase0), ei pelaajan xP-summaa."),
    "/api/fantasy/xp.csv": ("/api/fantasy/xp.csv",
        "CSV:lla ei ole metaa. Sarake `xp_horizon_total` on sama lukija kuin "
        "/api/fantasy/xp:lla (attach_horizon_total_actionable), ja se "
        "mitataan tassa rivi rivilta 5*xp_gw:ksi."),
    "/api/fantasy/plan": ("/api/fantasy/plan?entry=424242",
        "Siirtosuunnitelma: voitto lasketaan ikkunalta jonka meta nimeaa "
        "itse (gw_from, gw_to, horizon_gws); riveilla ei horisonttisummaa."),
    "/api/fantasy/captain": ("/api/fantasy/captain?entry=424242",
        "GW-kohtainen gw_xp, ei horisonttisummaa."),
    "/api/fantasy/replacements": ("/api/fantasy/replacements?player=15",
        "Ikkunasummat ikkunalta jonka meta.gws nimeaa; riveilla ei "
        "xp_horizon_totalia."),
    "/api/fantasy/chip-ev": ("/api/fantasy/chip-ev?entry=424242",
        "Chip-ikkunat nimetaan itse (meta.horizon_gws, windows[].gw)."),
    "/api/fantasy/wildcard-plan": ("/api/fantasy/wildcard-plan?entry=424242",
        "Rivit kantavat `xp_window`in ikkunalta jonka `window`/`window_gws` "
        "nimeaa; poolin xp_horizon_total ylikirjoitetaan sisaisesti "
        "ikkunasummalla (fpl_wildcard._optimi) eika sita tarjoilla."),
    "/api/fantasy/plan-chains": ("/api/fantasy/plan-chains?entry=424242",
        "Ketjujen voitto lasketaan horisontilta jonka meta nimeaa "
        "(horizon); riveilla ei xp_horizon_totalia."),
    "/api/fantasy/h2h": ("/api/fantasy/h2h?entry_a=424242&entry_b=424242",
        "Yhden kierroksen XI-xP (xi_xp per gw), ei horisonttisummaa."),
    "/api/fantasy/league/{league_id}": (None,
        "FPL-liigataulukko; ei xP-poolia."),
    "/api/fantasy/price-watch": (None,
        "Hinnanmuutosennuste (fpl_price_watch); ei xP-poolia."),
    "/api/fantasy/gw-review": (None,
        "Gradattu kierros (fpl_gw_review); ei eteenpain katsovaa summaa."),
    "/api/fantasy/my-team-ledger": (None,
        "Pistekirjanpito (fpl_my_team_ledger); ei xP-poolia."),
    "/api/fantasy/model-race": (None,
        "Gradatut mallipisteet lokista (fpl_model_race); ei xP-poolia."),
    "/api/fantasy/xg-leaders": (None,
        "xG-rankkaus (fpl_leaders); ei xP-poolia."),
    "/api/fantasy/defcon-leaders": (None,
        "DefCon-rankkaus (fpl_leaders); ei xP-poolia."),
    "/api/fantasy/defcon-gw": (None,
        "DefCon per kierros (fpl_leaders); ei xP-poolia."),
    "/api/fantasy/defcon-live": (None,
        "DefCon live (fpl_defcon_live); ei xP-poolia."),
    "/api/fantasy/defcon/{player_id}": (None,
        "Yhden pelaajan DefCon (fpl_leaders); ei xP-poolia."),
}

# Avaimet jotka OVAT horisonttisumma tai siita johdettu luku. Ikkunasummat
# joilla on oma nimetty ikkuna (xp_window, gain, ev_total) eivat kuulu tahan.
SUM_KEYS = {"xp_horizon_total", "xp_horizon", "team_xp_horizon",
            "team_xp_horizon_no_captain", "xi_xp_horizon",
            "optimal_xp_horizon", "margin_xp_horizon"}
# Avaimet joiden arvo on YHDEN pelaajan summa: tarkistetaan 5*xp_gw.
ROW_KEYS = {"xp_horizon_total", "xp_horizon"}


def _sum_sites(obj, path: str = "$", ctx_id=None) -> list[tuple]:
    """[(polku, avain, arvo, lahin id)] jokaisesta summa-avaimesta."""
    out: list[tuple] = []
    if isinstance(obj, dict):
        cid = obj.get("id") if isinstance(obj.get("id"), int) else ctx_id
        for k, v in obj.items():
            if k in SUM_KEYS:
                out.append((f"{path}.{k}", k, v, cid))
            out.extend(_sum_sites(v, f"{path}.{k}", cid))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(_sum_sites(v, f"{path}[{i}]", ctx_id))
    return out


def _reitit(kohde, prefix: str = "") -> list[str]:
    """Kaikki reitit MYOS include_routerin takaa.

    MITATTU 20.9.2026. fastapi >= 0.141 ei enaa kopioi `include_router`in
    reitteja `app.routes`iin: se lisaa YHDEN `_IncludedRouter`-olion, jonka
    `path` on None ja jonka takana oikeat reitit ovat
    `original_router.routes`issa (prefix `include_context.prefix`issa).
    Endpointit vastaavat normaalisti — mitattu eristetylla probella:
    `GET /api/fantasy/chip-ev` -> 200 samalla kun `app.routes` ei tuntenut
    sita. Vanhemmissa (0.136) reitit ovat suoraan listassa.

    Portti luki vain `app.routes`ia, joten CI (fastapi 0.141.1, py3.11) oli
    punainen ja lokaali (0.136.1, py3.14) vihrea. Vika oli PORTISSA, ei
    sovelluksessa: se vaitti yhdeksan endpointin kadonneen vaikka ne
    vastaavat. Kavellaan siis rakenteen lapi versiosta riippumatta.
    """
    out: list[str] = []
    for r in getattr(kohde, "routes", []):
        polku = getattr(r, "path", None)
        if polku:
            out.append(prefix + polku)
        sisempi = getattr(r, "original_router", None)
        if sisempi is not None:
            ctx = getattr(r, "include_context", None)
            out.extend(_reitit(sisempi, prefix + (getattr(ctx, "prefix", "") or "")))
    return out


def _all_paths() -> set[str]:
    return {p for p in _reitit(m.app) if p.startswith("/api/fantasy")}


def test_reittiluku_nakee_include_routerin_takaa():
    """Portti mitataan ASENNETTUA fastapia vasten, ei oletettua versiota.

    Ilman tata `_reitit` voi hiljaa lakata nakemasta include_routerin
    reitteja seuraavassa fastapi-muutoksessa, ja silloin YLLA oleva portti
    lapaisisi vaarin perustein: se vaittaisi reittien kadonneen (tai
    paastaisi uuden vartioimattoman reitin lapi) vaikka sovellus tarjoilee
    ne. Tama testi kaatuu heti kun rakenne muuttuu, ja kertoo mihin katsoa.

    Synteettinen app, ei tuotannon reitteja: mitataan MEKANISMI.
    """
    from fastapi import APIRouter, FastAPI
    import fastapi as _fa

    r = APIRouter()

    @r.get("/chip-ev")
    def _a():                                    # pragma: no cover
        return {}

    sovellus = FastAPI()

    @sovellus.get("/api/fantasy/xp")
    def _b():                                    # pragma: no cover
        return {}

    sovellus.include_router(r, prefix="/api/fantasy")
    loydetyt = set(_reitit(sovellus))
    assert "/api/fantasy/xp" in loydetyt, loydetyt
    assert "/api/fantasy/chip-ev" in loydetyt, (
        f"_reitit ei nae include_routerin reittia (fastapi {_fa.__version__}). "
        "Rakenne on muuttunut: katso miten reitit ovat app.routes-listassa "
        "(0.136: suoraan; 0.141: _IncludedRouter.original_router.routes + "
        "include_context.prefix) ja paivita _reitit. Loydetyt: {loydetyt}")

    # Ja endpoint VASTAA molemmissa: portin pitaa kertoa reitista jota
    # sovellus oikeasti tarjoilee, ei siita mita listarakenne sattuu
    # nayttamaan. Ilman tata rivia testi hyvaksyisi listan joka on
    # tosi mutta irrallaan siita mita palvelin tekee.
    with TestClient(sovellus) as cl:
        assert cl.get("/api/fantasy/chip-ev").status_code == 200


def test_every_fantasy_route_is_tested_or_exempt_with_a_reason():
    paths = _all_paths()
    assert paths, "reittilistaus tyhja"
    listed = set(TESTED) | set(EXEMPT)
    assert not (set(TESTED) & set(EXEMPT)), set(TESTED) & set(EXEMPT)
    assert paths - listed == set(), (
        f"Uusi /api/fantasy-reitti ilman paatosta: {sorted(paths - listed)}. "
        "Jos se tarjoilee xp_horizon_totalin (tai siita johdetun summan), "
        "lisaa se TESTED-listaan ja kirjoita meta `horizon_total_meta`illa; "
        "muuten EXEMPT-listaan perusteluineen.")
    # 20.9: tama rivi oli punainen CI:ssa (py3.11) ja vihrea lokaalisti
    # (py3.14) — puuttuvat olivat TASMALLEEN ne 9 reittia jotka tulevat
    # `api.fantasy_edge`in routerista. Portin viesti osoitti vaaraan
    # suuntaan: reitit eivat olleet poistuneet LISTALTA vaan APPISTA.
    # Portti joka ei kerro mita se NAKI maksaa kokonaisen CI-kierroksen
    # per arvaus, joten se kertoo nyt.
    if listed - paths:
        import sys as _sys
        import fastapi as _fa
        try:
            import api.fantasy_edge as _fe
            fe_reitit = sorted(getattr(r, "path", "") for r in _fe.router.routes)
            fe_tiedosto = getattr(_fe, "__file__", "?")
        except Exception as _e:                     # pragma: no cover
            fe_reitit, fe_tiedosto = ["import kaatui: " + repr(_e)], "?"
        _api_mod = sorted(k for k in _sys.modules if k.startswith("api"))
        raise AssertionError(NEWLINE.join([
            "poistunut reitti listalla: " + str(sorted(listed - paths)),
            "  python           : " + _sys.version.split()[0],
            "  fastapi          : " + _fa.__version__,
            "  api.main         : " + str(getattr(m, "__file__", "?")),
            "  api.fantasy_edge : " + str(fe_tiedosto),
            "  routerin reitit  : " + str(fe_reitit),
            "  appin fantasy    : " + str(sorted(paths)),
            "  api.* sys.modules: " + str(_api_mod),
            "  -> Jos routerilla ON puuttuvat reitit mutta appilla EI, "
            "app.include_router ajettiin ennen kuin router oli valmis: "
            "sovellus tarjoilisi 404:n yhdeksalle endpointille.",
        ]))
    for p, (_probe, why) in EXEMPT.items():
        assert why and len(why) > 20, p


@pytest.mark.parametrize("enforce", ["off", "on"])
@pytest.mark.parametrize("path", sorted(TESTED))
def test_route_serving_the_sum_names_the_window(monkeypatch, enforce, path):
    monkeypatch.setenv("PREMIUM_ENFORCE", enforce)
    r = TestClient(m.app).get(TESTED[path])
    assert r.status_code == 200, (path, r.status_code, r.text[:200])
    data = r.json()
    sites = _sum_sites(data)
    if enforce == "off":
        assert sites, f"{path}: ei summa-avainta vastauksessa; siirra EXEMPT-listaan"
    # Maski voi pudottaa summarivit (rival, transfers), avaimet jaavat:
    # klientti nimeaa ikkunan samasta metasta kummassakin tilassa.
    meta = data.get("meta") or {}
    assert meta.get("horizon_total_from") == EXPECT_FROM, (path, meta)
    assert meta.get("horizon_total_gw") == EXPECT_GW, (path, meta)
    # Rivin luku on VAIKUTETTAVIEN kierrosten summa, ei raaka. Maskattu
    # (null) rivi ohitetaan: player-stats nollaa premium-kentat freelle.
    checked = 0
    for where, key, val, cid in sites:
        if key not in ROW_KEYS or val is None or cid not in XP_GW:
            continue
        want = round(EXPECT_GW * XP_GW[cid], 2)
        raw = RAW_TOTAL[cid]
        assert val == pytest.approx(want), (path, where, val, want)
        assert val != pytest.approx(raw), (path, where, "raaka summa lapaisi")
        checked += 1
    row_sites = [s for s in sites if s[1] in ROW_KEYS]
    if enforce == "off" and row_sites:
        assert checked, f"{path}: yhtaan pelaajarivia ei tarkistettu"
    if sites and not row_sites:
        # Vain joukkuetason summa (model-squad, career): sen johdos
        # tarkistetaan reitin omassa testissa alla.
        assert path in TEAM_LEVEL_ONLY, (path, [s[0] for s in sites][:3])


# ---------------------------------------------------------------------------
# xp_per_gw: SUMMAN JOHDOS, SAMA IKKUNA (18.9, adversariaalinen tarkistus)
# ---------------------------------------------------------------------------
#
# 🔴 MITATTU 18.9: `xp_per_gw` jai putken kokonaishorisontin keskiarvoksi
# samalla kun `xp_horizon_total` rajattiin. Ne tarjoillaan VIEREKKAIN ja
# /fpl/differentials selittaa niiden suhteen auki ("xP/GW is the N-gameweek
# projection divided by N"): kesken kierroksen sarake sanoi 6.41, summa
# 31.97 ja sivun oma lasku 31.97/6 = 5.33. Lukija joka teki sivun kertoman
# laskun sai eri luvun kuin sivu nayttaa. Kentta oli pudonnut yhden lukijan
# ulkopuolelle aanettomasti: reittiportin `SUM_KEYS` ei sisaltanyt sita
# eika poikkeuslistalla ollut sille perustelua. Nyt molemmat tulevat
# `attach_horizon_total_actionable`ista ja tama portti kavelee jokaisen
# reitin vastauksen.
PER_GW_KEY = "xp_per_gw"

# Reitti jolla `xp_per_gw` esiintyy ILMAN horisonttisummaa: perustelu
# pakollinen, muuten uusi reitti voi tarjoilla keskiarvon jonka ikkunaa
# mikaan ei kerro.
PER_GW_WITHOUT_SUM = {
    "/api/fantasy/wildcard-plan":
        "Wildcard-optimi ylikirjoittaa poolin `xp_horizon_total`in sisaisesti "
        "ikkunasummalla (`fpl_wildcard._optimi`) eika tarjoile sita; rivien "
        "`xp_per_gw` on poolin luku, jonka ikkunan `window`/`window_gws` "
        "nimeaa vastauksessa erikseen.",
}


def _per_gw_sites(obj, path: str = "$", ctx_id=None) -> list[tuple]:
    """[(polku, xp_per_gw, summa tai None, lahin id)] jokaisesta rivista
    jolla on `xp_per_gw`."""
    out: list[tuple] = []
    if isinstance(obj, dict):
        cid = obj.get("id") if isinstance(obj.get("id"), int) else ctx_id
        if PER_GW_KEY in obj:
            sums = [obj[k] for k in ROW_KEYS if k in obj]
            out.append((path, obj[PER_GW_KEY], sums[0] if sums else None, cid))
        for k, v in obj.items():
            out.extend(_per_gw_sites(v, f"{path}.{k}", cid))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(_per_gw_sites(v, f"{path}[{i}]", ctx_id))
    return out


_PER_GW_ROUTES = sorted(set(TESTED) | {p for p, (probe, _) in EXEMPT.items() if probe})


@pytest.mark.parametrize("path", _PER_GW_ROUTES)
def test_per_gw_is_the_sum_divided_by_the_same_window(monkeypatch, path):
    monkeypatch.setenv("PREMIUM_ENFORCE", "off")
    url = TESTED.get(path) or EXEMPT[path][0]
    r = TestClient(m.app).get(url)
    assert r.status_code == 200, (path, r.status_code, r.text[:200])
    if not r.headers.get("content-type", "").startswith("application/json"):
        return  # CSV tarkistetaan rivi rivilta omassa testissaan
    sites = [x for x in _per_gw_sites(r.json()) if x[1] is not None]
    checked = 0
    for where, per_gw, total, cid in sites:
        if total is None:
            assert path in PER_GW_WITHOUT_SUM, (
                f"{path}{where} tarjoilee xp_per_gw:n ilman horisonttisummaa. "
                "Lisaa PER_GW_WITHOUT_SUM-listalle perusteluineen tai tarjoile "
                "summa, jotta ikkuna on luettavissa.")
            continue
        want = round(total / EXPECT_GW, 2)
        assert per_gw == pytest.approx(want, abs=0.011), (path, where, per_gw, want)
        if cid in RAW_PER_GW:
            # ...ja se EI ole putken koko horisontin keskiarvo
            assert per_gw != pytest.approx(RAW_PER_GW[cid]), (path, where, per_gw)
        checked += 1
    # Reitti joka EI tarjoile keskiarvoa lainkaan on kunnossa; jos se
    # tarjoilee, vahintaan yhden rivin on oltava tarkistettu (muuten portti
    # olisi vihrea siksi ettei se loyda mitaan).
    if sites and path not in PER_GW_WITHOUT_SUM:
        assert checked, f"{path}: xp_per_gw loytyi mutta yhtaan ei tarkistettu"


def test_the_per_gw_walker_sees_an_unpaired_average():
    """Negatiivinen kontrolli walkerille: keskiarvo ilman summaa loytyy,
    ja putken keskiarvo (7/6 x xp_gw) EI ole sama luku kuin rajattu."""
    sites = _per_gw_sites({"players": [{"id": 15, "xp_per_gw": 1.0}]})
    assert sites == [("$.players[0]", 1.0, None, 15)]
    assert RAW_PER_GW[15] != pytest.approx(round(RAW_TOTAL[15] / EXPECT_GW, 2))
    assert RAW_PER_GW[15] != pytest.approx(XP_GW[15])


# Reitit joilla on vain joukkuetason summa; johdos tarkistetaan tassa.
TEAM_LEVEL_ONLY = {"/api/fantasy/model-squad", "/api/fantasy/career"}


def test_model_squad_xi_sum_is_the_actionable_sum_of_its_eleven():
    data = TestClient(m.app).get(TESTED["/api/fantasy/model-squad"]).json()
    xi = data["players"][:11]
    want = round(sum(EXPECT_GW * XP_GW[p["id"]] for p in xi), 2)
    raw = round(sum(RAW_TOTAL[p["id"]] for p in xi), 2)
    assert data["meta"]["xi_xp_horizon"] == pytest.approx(want)
    assert data["meta"]["xi_xp_horizon"] != pytest.approx(raw)


def test_career_teaser_carries_rate_team_sum_and_window():
    c = TestClient(m.app)
    career = c.get(TESTED["/api/fantasy/career"]).json()
    rated = c.get(TESTED["/api/fantasy/rate-team"]).json()
    teaser = career["model_teaser"]
    assert teaser["team_xp_horizon"] == rated["rating"]["team_xp_horizon"]
    # ikkuna nimetaan SEKA vastauksen metassa etta teaserissa, jossa
    # `horizon_gw` (6) muuten lukisi viiden kierroksen summan otsikoksi
    for blk in (career["meta"], teaser):
        assert blk["horizon_total_from"] == EXPECT_FROM, blk
        assert blk["horizon_total_gw"] == EXPECT_GW, blk


@pytest.mark.parametrize("path", sorted(p for p, (probe, _) in EXEMPT.items() if probe))
def test_exempt_route_really_serves_no_horizon_sum(monkeypatch, path):
    """Poikkeuksen vaite mitataan: reitti ajetaan ja summa-avainta ei loydy."""
    monkeypatch.setenv("PREMIUM_ENFORCE", "off")
    probe, why = EXEMPT[path]
    r = TestClient(m.app).get(probe)
    assert r.status_code == 200, (path, r.status_code, r.text[:200])
    if not r.headers.get("content-type", "").startswith("application/json"):
        # CSV: ei metaa, mutta sarakkeen on oltava sama luku kuin /xp:lla.
        lines = [ln for ln in r.text.lstrip("﻿").splitlines() if ln.strip()]
        assert lines[0].startswith("sep="), lines[0]
        header = lines[1].split(",")
        i_id, i_sum = header.index("id"), header.index("xp_horizon_total")
        rows = [ln.split(",") for ln in lines[2:]]
        assert rows
        for row in rows:
            pid, val = int(row[i_id]), float(row[i_sum])
            assert val == pytest.approx(round(EXPECT_GW * XP_GW[pid], 2)), (pid, val)
            assert val != pytest.approx(RAW_TOTAL[pid]), (pid, val)
        return
    sites = _sum_sites(r.json())
    assert not sites, (
        f"{path} tarjoilee horisonttisumman ({[s[0] for s in sites][:3]}) "
        f"mutta on EXEMPT-listalla: '{why}'. Siirra TESTED-listaan.")


_ROUTE_FILES = ("api/main.py", "api/fantasy_edge.py")
_POOL_NAMES = {"build_context", "load_xp", "load_xp_actionable", "rate_team",
               "free_optimum", "_projection_pool"}
_POOL_MODULES = {"src.models.fpl_planner", "src.models.fpl_value",
                 "src.models.fpl_fit", "src.models.fpl_xp"}


def _route_functions() -> dict[str, ast.FunctionDef]:
    out: dict[str, ast.FunctionDef] = {}
    for rel in _ROUTE_FILES:
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        for n in tree.body:
            if not isinstance(n, ast.FunctionDef):
                continue
            for d in n.decorator_list:
                if (isinstance(d, ast.Call) and d.args
                        and isinstance(d.args[0], ast.Constant)
                        and isinstance(d.args[0].value, str)
                        and d.args[0].value.startswith("/api/fantasy")):
                    out[d.args[0].value] = n
    return out


@pytest.mark.parametrize("path", sorted(p for p, (probe, _) in EXEMPT.items() if not probe))
def test_exempt_route_without_probe_does_not_touch_the_pool(path):
    """Reitti jota fikstuuri ei voi ajaa: runko ei saa lukea xP-poolia eika
    kirjoittaa summakenttaa. Jos se alkaa lukea, sille on annettava probe."""
    fn = _route_functions()[path]
    names = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Name):
            names.add(n.id)
        elif isinstance(n, ast.Attribute):
            names.add(n.attr)
        elif isinstance(n, ast.Constant) and n.value in SUM_KEYS:
            names.add(n.value)
        elif isinstance(n, ast.ImportFrom) and n.module in _POOL_MODULES:
            names.add(n.module)
    bad = names & (_POOL_NAMES | SUM_KEYS | _POOL_MODULES)
    assert not bad, (path, sorted(bad))


# ---------------------------------------------------------------------------
# Lahdeportti: jokainen TESTED-reitin metan kirjoittaja kutsuu lukijaa
# ---------------------------------------------------------------------------

META_WRITERS = [
    ("src/models/fpl_planner.py", "differential_finder"),
    ("src/models/fpl_planner.py", "compare_players"),
    ("src/models/fpl_value.py", "value_list"),
    ("src/models/fpl_fit.py", "fit_squad"),
    ("src/models/fpl_rate_team.py", "rate_team"),
    ("src/models/fpl_player_stats.py", "aggregate"),
    ("api/main.py", "fantasy_model_squad"),
    ("api/fantasy_edge.py", "fantasy_edge"),
    ("api/fantasy_edge.py", "fantasy_rival"),
    ("src/models/fpl_career.py", "_model_teaser"),
]


@pytest.mark.parametrize("path,func", META_WRITERS)
def test_meta_writer_calls_the_one_reader(path, func):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    fn = next((n for n in tree.body
               if isinstance(n, ast.FunctionDef) and n.name == func), None)
    assert fn is not None, (path, func)
    calls = {(n.func.id if isinstance(n.func, ast.Name)
              else getattr(n.func, "attr", None))
             for n in ast.walk(fn) if isinstance(n, ast.Call)}
    assert "horizon_total_meta" in calls, (
        f"{path}:{func} ei kutsu horizon_total_meta() - reitti tarjoilisi "
        "summan ilman ikkunaa")


# ---------------------------------------------------------------------------
# Lukija: kopioi, ei laske
# ---------------------------------------------------------------------------

def test_reader_copies_the_attached_meta_and_never_computes():
    assert horizon_total_meta({}) == {"horizon_total_from": None,
                                      "horizon_total_gw": None}
    assert horizon_total_meta(None) == {"horizon_total_from": None,
                                        "horizon_total_gw": None}
    attached = fpl_xp.attach_horizon_total_actionable(_fake_xp())["meta"]
    assert horizon_total_meta(attached) == {"horizon_total_from": EXPECT_FROM,
                                            "horizon_total_gw": EXPECT_GW}
    # Ei omaa laskentaa: arvo tulee metasta sellaisenaan.
    assert horizon_total_meta({"horizon_total_from": 7, "horizon_total_gw": 3,
                               "next_gameweek": 1, "deadline_gameweek": 2}) \
        == {"horizon_total_from": 7, "horizon_total_gw": 3}


def test_the_walker_sees_a_sum_without_meta():
    """Negatiivinen kontrolli portille: vastaus jossa summa on mutta meta
    puuttuu EI lapaise samaa tarkistusta."""
    payload = {"meta": {"horizon_gw": 6},
               "players": [{"id": 15, "xp_horizon_total": 33.0}]}
    sites = _sum_sites(payload)
    assert sites == [("$.players[0].xp_horizon_total", "xp_horizon_total", 33.0, 15)]
    assert payload["meta"].get("horizon_total_from") != EXPECT_FROM
    # sisakkain (player-stats: goaliq.xp_horizon_total) perii rivin id:n
    nested = {"players": [{"id": 16, "goaliq": {"xp_horizon_total": 1.0}}]}
    assert _sum_sites(nested)[0][3] == 16


# ---------------------------------------------------------------------------
# SPL: sama reitti, artefaktissa ei deadline_gameweekia
# ---------------------------------------------------------------------------

def test_spl_route_names_the_window_from_next_gameweek(monkeypatch, tmp_path):
    """SPL-artefakti (build_spl_xp) kirjoittaa `deadline_gameweek: null`,
    joten actionable putoaa `next_gameweek`iin ja summa kattaa koko listan.

    🔴 18.9 (julkaisutarkistajan B3): ENNEN tata rivi oli
    `horizon_total_from == 1` ja docstring sanoi "kertovat sen
    rehellisesti". Se EI ollut rehellista: kentta on klientille lupaus
    "summa alkaa seuraavasta deadlinesta", ja SPL:lla alku oli
    `next_gameweek` toisessa asussa - kentta jonka drift on SPL-feedissa
    mittaamatta (jono SPL-DEADLINE-GW-MITTAUS) ja jota seka mobiilin etta
    SPA:n lukija kieltaytyy lukemasta ikkunan alkuna. Mitattu 18.9
    tuotannosta: SPL palauttaa next_gameweek 8, deadline_gameweek None.
    Nyt SPL saa LUKUMAARAN muttei alkua, eli kortti sanoo "6-GW horizon"
    eika "GW8-GW13" / "next 6 GWs". Summa ja jarjestys ennallaan.
    Ks. tests/test_xp_horizon_window_licence.py."""
    doc = _fake_xp()
    doc["meta"]["deadline_gameweek"] = None
    doc["meta"]["next_gameweek"] = 1
    p = tmp_path / "spl.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setitem(fpl_xp.XP_PATHS, "spl", p)
    r = TestClient(m.app).get("/api/fantasy/xp?league=spl")
    assert r.status_code == 200
    data = r.json()
    assert data["meta"]["horizon_total_from"] is None
    assert data["meta"]["horizon_total_gw"] == HORIZON
    by = {q["id"]: q for q in data["players"]}
    assert by[15]["xp_horizon_total"] == pytest.approx(RAW_TOTAL[15])
    # koko lista summassa -> keskiarvo on sama kuin putkella
    assert by[15]["xp_per_gw"] == pytest.approx(RAW_PER_GW[15])
