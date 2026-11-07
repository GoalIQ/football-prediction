"""Kierros kellon mukaan, vaikka builder on kaatunut (7.11.2026).

Mitattu tuotannosta paiva GW10:n deadlinen jalkeen: rate-team `captain_gw` 10 ja
siirtoikkuna GW10-14, `/api/fantasy` `next_gameweek` 9. Lukija ajetaan
synteettisilla vaiheilla (CLAUDE.md 6a kohta 3), koska tila syntyy vain katkossa.
"""
from __future__ import annotations

import ast
import datetime as dt
import inspect
import textwrap

import pytest

from src.models import fpl_gameweek, fpl_phase0, fpl_rate_team
from src.models.fpl_gameweek import meta_at_clock

UTC = dt.timezone.utc
DEADLINES = [
    {"gw": 10, "utc": "2026-11-06T18:30:00+00:00"},
    {"gw": 11, "utc": "2026-11-21T11:00:00+00:00"},
    {"gw": 12, "utc": "2026-11-27T18:30:00+00:00"},
]
STALE = {
    "deadline_gameweek": 10,
    "next_gameweek": 9,
    "deadline_utc": "2026-11-06T18:30:00+00:00",
    "completed_gameweeks": [1, 2, 3, 4, 5, 6, 7, 8],
    "generated_at": "2026-11-01T21:54:49+00:00",
}
BEFORE = dt.datetime(2026, 11, 6, 18, 0, tzinfo=UTC)
AT = dt.datetime(2026, 11, 6, 18, 30, tzinfo=UTC)
DURING = dt.datetime(2026, 11, 7, 9, 0, tzinfo=UTC)
PAST_TWO = dt.datetime(2026, 11, 22, 9, 0, tzinfo=UTC)
SEASON_OVER = dt.datetime(2026, 12, 1, 9, 0, tzinfo=UTC)


def test_terve_tila_palauttaa_saman_olion():
    assert meta_at_clock(STALE, deadlines=DEADLINES, now=BEFORE) is STALE


def test_deadlinen_hetkella_kierros_vaihtuu():
    assert meta_at_clock(STALE, deadlines=DEADLINES, now=AT)["deadline_gameweek"] == 11


def test_vanha_meta_siirtyy_kellon_mukaan():
    out = meta_at_clock(STALE, deadlines=DEADLINES, now=DURING)
    assert out["deadline_gameweek"] == 11
    assert out["deadline_utc"] == "2026-11-21T11:00:00+00:00"
    assert out["next_gameweek"] == 10
    assert out["clock_rolled_from"] == 10
    assert out["generated_at"] == STALE["generated_at"], "rakennushetki ei saa muuttua"


def test_syote_ei_muutu():
    before = dict(STALE)
    meta_at_clock(STALE, deadlines=DEADLINES, now=DURING)
    assert STALE == before


def test_valmis_kierros_ei_ole_kesken():
    out = meta_at_clock(STALE, deadlines=DEADLINES, done=[9, 10], now=DURING)
    assert out["next_gameweek"] == 11
    assert out["completed_gameweeks"] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


def test_kaksi_deadlinea_ohi():
    out = meta_at_clock(STALE, deadlines=DEADLINES, now=PAST_TWO)
    assert (out["deadline_gameweek"], out["next_gameweek"]) == (12, 11)


def test_iso_next_gameweek_sailyy():
    meta = {**STALE, "next_gameweek": 11}
    assert meta_at_clock(meta, deadlines=DEADLINES, now=DURING)["next_gameweek"] == 11


def test_idempotentti():
    once = meta_at_clock(STALE, deadlines=DEADLINES, now=DURING)
    assert meta_at_clock(once, deadlines=DEADLINES, now=DURING) is once


@pytest.mark.parametrize(
    "meta, deadlines, now",
    [
        (STALE, DEADLINES, SEASON_OVER),  # kausi ohi: kierrosta ei keksita
        (STALE, [], DURING),  # lista tyhja
        (STALE, [{"gw": "x", "utc": "rikki"}], DURING),
        ({**STALE, "deadline_gameweek": None}, DEADLINES, DURING),
        ({**STALE, "deadline_gameweek": True}, DEADLINES, DURING),
    ],
)
def test_ilman_perustetta_meta_ei_liiku(meta, deadlines, now):
    assert meta_at_clock(meta, deadlines=deadlines, now=now) is meta


def test_oletuslista_on_metan_oma():
    meta = {**STALE, "deadlines": DEADLINES}
    assert meta_at_clock(meta, now=DURING)["deadline_gameweek"] == 11


def test_oma_deadline_listan_ulkopuolelta():
    rows = [d for d in DEADLINES if d["gw"] != 10]
    assert meta_at_clock(STALE, deadlines=rows, now=DURING)["deadline_gameweek"] == 11


def test_ei_meta_dictia():
    assert meta_at_clock(None, deadlines=DEADLINES, now=DURING) is None


def test_open_gameweek_ennallaan_refaktoroinnin_jalkeen():
    meta = {**STALE, "deadlines": DEADLINES}
    assert fpl_gameweek.open_gameweek(meta, DURING) == 11
    assert fpl_gameweek.open_gameweek(meta, SEASON_OVER) is None


# --- rate-team ja planner: kaikki saavat kierroksen samasta kohdasta ---------

def _pool_rows():
    return [
        {
            "id": i,
            "gameweeks": [{"gw": g, "xp": 2.0, "opponents": []} for g in range(9, 15)],
            "xp_horizon_total": 12.0,
        }
        for i in range(1, 4)
    ]


def _xp():
    return {"meta": {**STALE, "available": True, "horizon_gw": 6}, "players": _pool_rows()}


def _bootstrap():
    return {
        "elements": [],
        "events": [
            {"id": 9, "deadline_time": "2026-10-30T18:30:00Z", "finished": True},
            {"id": 10, "deadline_time": "2026-11-06T18:30:00Z", "finished": False},
            {"id": 11, "deadline_time": "2099-11-21T11:00:00Z", "finished": False},
        ],
    }


@pytest.fixture
def ctx(monkeypatch):
    monkeypatch.setattr(fpl_rate_team, "load_xp", _xp)
    monkeypatch.setattr(fpl_rate_team, "get_bootstrap", _bootstrap)
    monkeypatch.setattr(fpl_rate_team, "projection_bootstrap", lambda _x: _bootstrap())
    monkeypatch.setattr(fpl_rate_team, "_projection_pool", lambda x, _p: x["players"])
    return fpl_rate_team.build_context


def test_build_context_siirtaa_kierroksen(ctx):
    xp, _b, pool, _by = ctx()
    assert xp["meta"]["deadline_gameweek"] == 11
    assert xp["meta"]["next_gameweek"] == 10
    assert xp["meta"]["horizon_total_from"] == 11
    assert xp["meta"]["horizon_total_gw"] == 4, "GW11-14, lukittu GW10 ei ole summassa"


def test_vaiheet_rate_teamin_lukijoille(ctx):
    xp, _b, pool, _by = ctx()
    assert fpl_rate_team.gw_in_progress(10, xp) is True
    assert fpl_rate_team.actionable_captain_gw(10, pool, xp) == 11
    assert fpl_rate_team.transfer_horizon_gws(pool, xp, 10) == [11, 12, 13, 14]
    assert fpl_rate_team.picks_outdated(10, xp["meta"]["deadline_gameweek"]) is True


def test_staattinen_polku_ei_riipu_kellosta(ctx):
    xp, _b, _p, _by = ctx(as_of_projection=True)
    assert xp["meta"]["deadline_gameweek"] == 10
    assert "clock_rolled_from" not in xp["meta"]


# --- /api/fantasy ja /api/fantasy/xp ----------------------------------------

FAR = [
    {"gw": 10, "utc": "2020-11-06T18:30:00+00:00"},
    {"gw": 11, "utc": "2099-11-21T11:00:00+00:00"},
]


def _kickoff(year: int) -> int:
    return int(dt.datetime(year, 1, 1, tzinfo=UTC).timestamp() * 1000)


def test_phase0_lukija_kierros_kesken_kun_ottelu_on_edessa():
    src = {"meta": {"deadlines": FAR}, "fixtures": [{"gameweek": 10, "kickoff_ms": _kickoff(2099)}]}
    out = fpl_phase0.meta_at_clock_phase0(STALE, src)
    assert (out["deadline_gameweek"], out["next_gameweek"]) == (11, 10)


def test_phase0_lukija_kierros_valmis_kun_kaikki_ottelut_alkoivat():
    src = {"meta": {"deadlines": FAR}, "fixtures": [{"gameweek": 10, "kickoff_ms": _kickoff(2020)}]}
    out = fpl_phase0.meta_at_clock_phase0(STALE, src)
    assert (out["deadline_gameweek"], out["next_gameweek"]) == (11, 11)


def test_phase0_lukija_ilman_listaa_ei_liiku():
    assert fpl_phase0.meta_at_clock_phase0(STALE, {"meta": {}, "fixtures": []}) is STALE


def _kutsut(func) -> list[str]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    return [
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    ]


@pytest.mark.parametrize("name", ["fantasy_phase0", "fantasy_xp"])
def test_tarjoilupinnat_kayttavat_lukijaa(name):
    from api import main

    assert "meta_at_clock_phase0" in _kutsut(inspect.unwrap(getattr(main, name)))


def test_rate_team_kertoo_rakennushetken():
    assert '"generated_at"' in inspect.getsource(fpl_rate_team.rate_team)


def test_optimin_avain_seuraa_ikkunaa(ctx):
    """k3 K1: sama `generated_at`, kierros siirtyy kellolla. Vanha avain antoi
    optimin vanhasta ikkunasta: ero -58,5 oikean -4,9:n sijaan."""
    xp = ctx()[0]
    ennen = {"meta": {"generated_at": xp["meta"]["generated_at"], "horizon_total_from": 10}}
    assert fpl_rate_team.free_optimum_key(ennen) != fpl_rate_team.free_optimum_key(xp)
    assert fpl_rate_team.free_optimum_key(xp) == fpl_rate_team.free_optimum_key(ctx()[0])


def _push_rt(**meta):
    built = dt.datetime.now(UTC).isoformat()
    return {
        "meta": {
            "captain_gw": 11,
            "picks_gw": 10,
            "picks_outdated": True,
            "generated_at": built,
            **meta,
        },
        "transfers": {
            "hold": True,
            "hold_verdict": {"gw_from": 11, "gw_to": 14, "verdict": "hold"},
            "suggestions": [],
        },
        "captain": {"pick": {"web_name": "Gabriel"}},
    }


def test_push_pysyy_yleisena_vanhalla_rakennuksella():
    """Sivu nayttaa rakennuspaivan, push ei voi."""
    from scripts.push_dispatch import personal_body

    assert personal_body(_push_rt(), 11, True, True) is not None
    vanha = (dt.datetime.now(UTC) - dt.timedelta(hours=25)).isoformat()
    assert personal_body(_push_rt(generated_at=vanha), 11, True, True) is None
    assert personal_body(_push_rt(generated_at=None), 11, True, True) is None


def test_katko_ennen_deadlinea_ei_paasta_numeroita():
    """k3: kierros ei siirry, mutta luvut ovat vanhoja."""
    from scripts.push_dispatch import model_is_fresh

    now = dt.datetime(2026, 11, 20, 12, tzinfo=UTC)
    assert model_is_fresh({"generated_at": "2026-11-20T00:00:00+00:00"}, now) is True
    assert model_is_fresh({"generated_at": "2026-11-18T00:00:00+00:00"}, now) is False
    assert model_is_fresh({}, now) is False


def test_botin_lukija_ei_siirry():
    """Reply-moduuli vaikenee deadlinen jalkeen, ja sen pitaa saada vaieta."""
    from src.models import fpl_xp

    src = inspect.getsource(fpl_xp.load_xp_actionable)
    assert "meta_at_clock" not in src
