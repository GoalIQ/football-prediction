"""RATE-TEAM-FREEHIT-PALAUTUS: Free Hit -joukkue palautuu, ja lukija tietaa sen.

🔴 MIKSI (25.9.2026, mitattu FPL:sta). Entry 895045 (FPL overall #1) pelasi
GW5:llä Free Hitin. `/api/fantasy/rate-team?entry=895045` palautti
`picks_gw: 5` ja arvioi GW6-GW11:lle FH-joukkueen, vaikka FPL palauttaa
joukkueen GW6:ksi GW4:n kokoonpanoon. Sama `resolve_squad` syottaa plannerin,
kapteenin, ketjut, edgen ja my team -kontekstin, joten jokainen suunnittelu-
pinta suunnitteli joukkueelle jota ei ole.

Invariantti mitataan JOKAISESSA vaiheessa (CLAUDE.md 6a (3)): FH-kierros
kesken, FH-kierros ohi, ei FH:ta, kaksi perakkaista FH:ta, eksplisiittinen
kierros ja puuttuva edeltava kierros.
"""
from __future__ import annotations

import copy

import pytest

import src.models.fpl_rate_team as rt
from tests.test_fpl_rate_team import POOL_BOOT, POOL_PLAYERS, SQUAD_IDS

ENTRY = 515151
# FH-joukkue: eri 15 samasta poolista (GK 3-4, DEF 10-14, MID 20-24, FWD 28-30)
FH_IDS = [3, 4, 10, 11, 12, 13, 14, 20, 21, 22, 23, 24, 28, 29, 30]


def _picks(ids, *, chip=None, bank=15, cap=None):
    cap = cap if cap is not None else ids[7]
    return {"active_chip": chip,
            "picks": [{"element": e, "is_captain": e == cap,
                       "is_vice_captain": False} for e in ids],
            "entry_history": {"bank": bank}}


def _xp(completed):
    return {"meta": {"available": True, "season": "2026/27",
                     "generated_at": f"fh-{completed}", "next_gameweek": 2,
                     "deadline_gameweek": 3, "completed_gameweeks": completed,
                     "horizon_gw": 5},
            "players": POOL_PLAYERS}


BOOT = {
    "events": [{"id": 1, "is_current": False, "is_next": False, "finished": True},
               {"id": 2, "is_current": True, "is_next": False, "finished": False},
               {"id": 3, "is_current": False, "is_next": True, "finished": False}],
    "elements": POOL_BOOT,
    "teams": [{"id": i} for i in range(1, 11)],
}


def _install(monkeypatch, picks_by_gw, completed, boot=BOOT):
    xp = _xp(completed)

    def fake_fetch(path):
        if path == "/bootstrap-static/":
            return boot
        if path == f"/entry/{ENTRY}/":
            return {"id": ENTRY}
        for gw, data in picks_by_gw.items():
            if path == f"/entry/{ENTRY}/event/{gw}/picks/":
                return copy.deepcopy(data)
        raise rt.RateTeamError(404, "Not found on the FPL API.")

    monkeypatch.setattr(rt, "_fetch_fpl", fake_fetch)
    monkeypatch.setattr(rt, "load_xp", lambda: xp)
    rt._OPTIMAL_XP_CACHE.clear()
    rt._FPL_CACHE.clear()


@pytest.fixture(autouse=True)
def _clear():
    yield
    rt._OPTIMAL_XP_CACHE.clear()
    rt._FPL_CACHE.clear()


FH_GW2 = {1: _picks(SQUAD_IDS, bank=15), 2: _picks(FH_IDS, chip="freehit", bank=3)}


def _team_ids(out):
    return sorted(p["id"] for p in out["team"]["players"])


# --- rate_team: kentta seuraa vaihetta -------------------------------------

def test_fh_kierros_kesken_kentta_nayttaa_pelatun_joukkueen(monkeypatch):
    _install(monkeypatch, FH_GW2, completed=[1])
    out = rt.rate_team(entry=ENTRY)
    assert _team_ids(out) == sorted(FH_IDS)
    assert out["meta"]["picks_gw"] == 2
    assert out["meta"]["freehit_in_play"] == 2
    assert out["meta"]["freehit_reverted_from"] is None


def test_fh_kierroksen_jalkeen_arvioidaan_palautunut_joukkue(monkeypatch):
    _install(monkeypatch, FH_GW2, completed=[1, 2])
    out = rt.rate_team(entry=ENTRY)
    assert _team_ids(out) == sorted(SQUAD_IDS)
    # pankki palautuu myos: FH-kierroksen 0.3m ei ole kayttajan pankki
    assert out["team"]["bank"] == 1.5
    assert out["meta"]["freehit_reverted_from"] == 2
    assert out["meta"]["freehit_in_play"] is None
    # B1 (julkaisutarkistaja 25.9): picks_gw = arvioidun rungon kierros, jotta
    # klienttien "sama runko kuin viimeksi pelattu" (picks_gw == last_finished.gw)
    # ei piirra FH-joukkuetta kentalle palautuneen rungon selitteen alle.
    assert out["meta"]["picks_gw"] == 1
    # ...mutta julkaisulause lasketaan FH-kierroksesta (GW3-picksit tulevat
    # vasta GW3:n deadlinen jalkeen)
    assert out["meta"]["picks_outdated"] is True


@pytest.mark.parametrize("completed", [[1], [1, 2]])
def test_liput_eivat_koskaan_ole_paalla_yhtaaikaa(monkeypatch, completed):
    _install(monkeypatch, FH_GW2, completed=completed)
    meta = rt.rate_team(entry=ENTRY)["meta"]
    assert not (meta["freehit_in_play"] and meta["freehit_reverted_from"])


# --- yksi lukija: suunnittelijat saavat aina palautuneen --------------------

@pytest.mark.parametrize("completed", [[1], [1, 2]])
def test_resolve_squad_palauttaa_aina_ilman_eksplisiittista_kierrosta(monkeypatch, completed):
    _install(monkeypatch, FH_GW2, completed=completed)
    ids, cap, bank, picks_gw = rt.resolve_squad(BOOT, ENTRY, None, None, None, None)
    assert sorted(ids) == sorted(SQUAD_IDS)
    assert bank == 15 and picks_gw == 2


def test_kutsupaikka_my_team_konteksti_saa_palautuneen(monkeypatch):
    """Testi kutsuu KUTSUPAIKKAA eika vain lukijaa: my team -konteksti merkitsee
    tyokaluissa omistetut pelaajat, ja FH-joukkue olisi merkinnyt vaarat."""
    _install(monkeypatch, FH_GW2, completed=[1])
    from src.models import fpl_my_team
    ctx = fpl_my_team.squad_context(BOOT, ENTRY, None)
    assert ctx["available"] and ctx["ids"] == set(SQUAD_IDS)


def test_eksplisiittinen_kierros_saa_pelatun_joukkueen(monkeypatch):
    """gw-review pyytaa menneen kierroksen sellaisena kuin se pelattiin."""
    _install(monkeypatch, FH_GW2, completed=[1, 2])
    ids, *_ = rt.resolve_squad(BOOT, ENTRY, 2, None, None, None)
    assert sorted(ids) == sorted(FH_IDS)
    out = rt.rate_team(entry=ENTRY, gw=2)
    assert _team_ids(out) == sorted(FH_IDS)
    assert out["meta"]["freehit_reverted_from"] is None


# --- rajatapaukset ----------------------------------------------------------

def test_ilman_free_hitia_ei_muutosta(monkeypatch):
    _install(monkeypatch, {1: _picks(FH_IDS), 2: _picks(SQUAD_IDS, chip="wildcard")},
             completed=[1, 2])
    out = rt.rate_team(entry=ENTRY)
    assert _team_ids(out) == sorted(SQUAD_IDS)
    assert out["meta"]["freehit_reverted_from"] is None
    assert out["meta"]["freehit_in_play"] is None


def test_kaksi_perakkaista_free_hitia_kavelee_kaksi_askelta(monkeypatch):
    boot = copy.deepcopy(BOOT)
    boot["events"] = [
        {"id": 1, "is_current": False, "is_next": False, "finished": True},
        {"id": 2, "is_current": False, "is_next": False, "finished": True},
        {"id": 3, "is_current": True, "is_next": False, "finished": False},
        {"id": 4, "is_current": False, "is_next": True, "finished": False}]
    other = [1, 2, 5, 6, 7, 8, 10, 15, 16, 17, 18, 20, 25, 26, 28]
    picks = {1: _picks(SQUAD_IDS), 2: _picks(FH_IDS, chip="freehit"),
             3: _picks(other, chip="freehit")}
    _install(monkeypatch, picks, completed=[1, 2], boot=boot)
    r = rt.resolve_squad_ex(boot, ENTRY, None, None, None, None)
    assert sorted(r["squad_ids"]) == sorted(SQUAD_IDS)
    assert r["freehit_reverted_from"] == 3


def test_edeltava_kierros_puuttuu_pitaa_fh_joukkueen_eika_vaita_palautusta(monkeypatch):
    _install(monkeypatch, {2: _picks(FH_IDS, chip="freehit", bank=3)}, completed=[1, 2])
    r = rt.resolve_squad_ex(BOOT, ENTRY, None, None, None, None)
    assert sorted(r["squad_ids"]) == sorted(FH_IDS)
    assert r["freehit_reverted_from"] is None


def test_tuntematon_tila_kaatuu_nimetysti():
    with pytest.raises(ValueError):
        rt.resolve_squad_ex(BOOT, ENTRY, None, None, None, None, freehit="maybe")


# --- B4 (julkaisutarkistaja k2): suunnittelupinnat kertovat palautuksen ------

def test_plannerin_squad_source_kertoo_palautuksen(monkeypatch):
    """Planneri suunnittelee palautuneesta rungosta, mutta sen stale-lause
    sanoi "This plan starts from your GW{gw} squad" -> epatosi. gw pysyy
    FH-kierroksena (FPL:n julkaisu), ja freehit_reverted_from kertoo syyn."""
    _install(monkeypatch, FH_GW2, completed=[1, 2])
    from src.models import fpl_planner
    out = fpl_planner.plan_transfers(entry=ENTRY, horizon=3)
    ss = out["meta"]["squad_source"]
    assert ss["gw"] == 2 and ss["stale"] is True
    assert ss["freehit_reverted_from"] == 2


def test_ilman_fh_squad_source_ei_vaita_palautusta(monkeypatch):
    _install(monkeypatch, {1: _picks(FH_IDS), 2: _picks(SQUAD_IDS)}, completed=[1, 2])
    from src.models import fpl_planner
    ss = fpl_planner.plan_transfers(entry=ENTRY, horizon=3)["meta"]["squad_source"]
    assert ss["freehit_reverted_from"] is None
