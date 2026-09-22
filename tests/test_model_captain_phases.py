# -*- coding: utf-8 -*-
"""MALLIN KAPTEENI KAUDEN VAIHEISSA (22.9.2026, julkaisutarkistaja web-IA k2).

VIKA JOTA TAMA VARTIOI. pro.goaliq.app:n This week -kortti nimesi "The
model's captain, GW{n}" rate-teamin kautta entryn 116920 JULKAISTUISTA
pickeista. Freezen (~T-29 h) ja deadlinen valilla ne ovat edellisen
kierroksen runko, kun taas goaliq.app/fpl nimeaa saman kierroksen "Model
squad captain" -rivin freezesta (gw_calls). Jos freezen siirto toi eri
kapteenin, kaksi julkista pintaa nimesi eri pelaajan.

SAANTO 6a KOHTA 3: sama lukija (`fpl_model_captain.model_captain`) ajetaan
synteettisissa vaiheissa, ei vain siina jossa kausi sattuu olemaan:

  a  before_freeze   deadline edessa, freezea ei ole       -> entry_picks
  b  frozen          freeze olemassa, deadline edessa      -> frozen
  c  after_deadline  GW6 kesken, GW7:n deadline edessa     -> entry_picks (GW6-pickit)
  c' lag             deadline mennyt, artefakti laahaa     -> frozen (lukittu GW6)
  d  break           maaottelutauko, GW8 kahden viikon paassa -> entry_picks
  d' season_end      kaikki deadlinet menneet              -> frozen (viimeinen lukittu)

EROTTELEVA FIKSTUURI: jaadytetyn rungon kapteeni (16) EI ole rungon
korkein GW-xP (25). Rate-teamin saanto nimeaisi siis eri pelaajan kuin
freeze, kuten tuotannossa silloin kun malli siirtaa tai vaihtaa kapteenin
freezessa. Ilman tata eroa testi olisi vihrea vaaraa lahdetta vasten
(muisti: exit-koodi-ei-ole-todiste-mekanismista).
"""
from __future__ import annotations

import copy
import datetime as dt
import json

import pytest

import src.models.fpl_model_captain as mc
import src.models.fpl_rate_team as rt
from src.models import gw_calls
from src.models.fpl_model_entry import ENTRY_ID
from tests.test_fpl_rate_team import POOL_BOOT, POOL_PLAYERS, SQUAD_IDS

UTC = dt.timezone.utc

DEADLINES = {
    5: "2026-09-18T17:30:00Z",
    6: "2026-09-26T10:00:00Z",
    7: "2026-10-03T10:00:00Z",
    8: "2026-10-17T10:00:00Z",   # maaottelutauko ennen GW8:aa
    9: "2026-10-24T10:00:00Z",
}

#: Entryn GW5-pickit = test_fpl_rate_team:n runko. Freeze GW6 tekee siirron
#: 27 -> 28 (FWD) ja lukitsee kapteeniksi 16:n (MID 5.2 xP), vaikka XI:n
#: korkein on 25 (FWD 5.8).
GW5_PICKS = list(SQUAD_IDS)
GW6_SQUAD = [x for x in SQUAD_IDS if x != 27] + [28]
FROZEN_CAPTAIN = 16
FROZEN_VICE = 15
TOP_XP_IN_SQUAD = 25

_BY_ID = {p["id"]: p for p in POOL_PLAYERS}
_BOOT_BY_ID = {e["id"]: e for e in POOL_BOOT}


def _players_all_gws():
    """Poolin rivit kierroksille 1-9; kapteenilla GW6-vastustaja."""
    out = []
    for p in POOL_PLAYERS:
        q = copy.deepcopy(p)
        q["gameweeks"] = [{"gw": g, "opponents": [{"opp": "OPP", "venue": "H"}],
                           "xp": p["xp_per_gw"]} for g in range(1, 10)]
        if q["id"] == FROZEN_CAPTAIN:
            q["gameweeks"][5]["opponents"] = [{"opp": "LIV", "venue": "A"}]
        out.append(q)
    return out


PLAYERS = _players_all_gws()


def _frozen_doc(gw: int, squad: list[int], captain: int, vice: int) -> dict:
    rows = [{"id": pid, "web_name": f"P{pid}", "team_short": _BY_ID[pid]["team_short"],
             "pos": _BOOT_BY_ID[pid]["element_type"], "club": _BOOT_BY_ID[pid]["team"],
             "price": _BOOT_BY_ID[pid]["now_cost"], "xp": 3.33}
            for pid in squad]
    by_pos = {k: [r for r in rows if r["pos"] == k] for k in (1, 2, 3, 4)}
    # Laillinen 4-4-2: GK + 4 DEF + 4 MID + 2 FWD, penkilla loput.
    take = {1: 1, 2: 4, 3: 4, 4: 2}
    xi = [r for k in (1, 2, 3, 4) for r in by_pos[k][:take[k]]]
    bench = [r for k in (1, 2, 3, 4) for r in by_pos[k][take[k]:]]
    return {
        "meta": {"gw": gw, "deadline": DEADLINES.get(gw, "2026-10-30T10:00:00Z"),
                 "frozen_at": f"2026-09-{min(28, 10 + gw):02d}T12:18:34Z",
                 "budget": 100.0, "cost": 99.0, "transfers": []},
        "captain": captain, "vice_captain": vice,
        "xi": xi, "bench": bench,
    }


# (nimi, now, is_current, is_next, xp next_gameweek, xp deadline_gameweek,
#  jaadytetyt kierrokset, julkaistu pickkikierros max,
#  odotettu source, odotettu gw, odotettu picks_gw, odotettu deadline_gameweek)
PHASES = [
    ("a_before_freeze", "2026-09-24T12:00:00Z", 5, 6, 6, 6, [5], 5,
     "entry_picks", 6, 5, 6),
    ("b_frozen", "2026-09-25T12:00:00Z", 5, 6, 6, 6, [5, 6], 5,
     "frozen", 6, None, 6),
    ("c_after_deadline", "2026-09-27T12:00:00Z", 6, 7, 6, 7, [5, 6], 6,
     "entry_picks", 7, 6, 7),
    ("c_lag", "2026-09-26T11:00:00Z", 6, 7, 6, 6, [5, 6], 6,
     "frozen", 6, None, 7),
    ("d_break", "2026-10-06T12:00:00Z", 7, 8, 8, 8, [5, 6, 7], 7,
     "entry_picks", 8, 7, 8),
    ("d_season_end", "2026-10-30T12:00:00Z", 9, None, 9, 9, [5, 6, 7, 8, 9], 9,
     "frozen", 9, None, None),
]


def _squad_for(gw: int) -> list[int]:
    return GW5_PICKS if gw <= 5 else GW6_SQUAD


def _setup(monkeypatch, tmp_path, phase):
    (_name, now, cur, nxt, xp_next, xp_dl, frozen_gws, picks_max,
     *_expected) = phase
    events = [{"id": g, "deadline_time": DEADLINES.get(g, f"2026-08-{10 + g:02d}T10:00:00Z"),
               "is_current": g == cur, "is_next": g == nxt,
               "finished": False, "data_checked": False}
              for g in range(1, 10)]
    boot = {"events": events, "elements": POOL_BOOT,
            "teams": [{"id": i} for i in range(1, 11)]}
    xp = {"meta": {"available": True, "season": "test-phases",
                   "generated_at": "2026-09-22T09:55:36+00:00",
                   "next_gameweek": xp_next, "deadline_gameweek": xp_dl,
                   "horizon_gw": 6},
          "players": copy.deepcopy(PLAYERS)}

    def fake_fetch(path):
        if path == "/bootstrap-static/":
            return boot
        if path == f"/entry/{ENTRY_ID}/":
            return {"id": ENTRY_ID}
        if path == f"/entry/{ENTRY_ID}/history/":
            return {"chips": [], "current": [], "past": []}
        pre = f"/entry/{ENTRY_ID}/event/"
        if path.startswith(pre) and path.endswith("/picks/"):
            gw = int(path[len(pre):-len("/picks/")])
            if gw <= picks_max:
                # FPL julkaisee pickit deadlinella: GW6:n pickit = GW6-freeze,
                # kapteeni kuten freezessa (Ville syottaa rivin entryyn).
                ids = _squad_for(gw)
                return {"picks": [{"element": e, "is_captain": e == FROZEN_CAPTAIN,
                                   "is_vice_captain": e == FROZEN_VICE} for e in ids],
                        "entry_history": {"bank": 10}}
        raise rt.RateTeamError(404, "Not found on the FPL API.")

    monkeypatch.setattr(rt, "_fetch_fpl", fake_fetch)
    monkeypatch.setattr(rt, "load_xp", lambda: copy.deepcopy(xp))
    rt._OPTIMAL_XP_CACHE.clear()
    rt._FPL_CACHE.clear()

    fdir = tmp_path / "model_squad_frozen"
    fdir.mkdir()
    for g in frozen_gws:
        doc = _frozen_doc(g, _squad_for(g), FROZEN_CAPTAIN, FROZEN_VICE)
        (fdir / f"gw{g}.json").write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(mc, "FROZEN_DIR", fdir)
    t = gw_calls.parse_utc(now)
    monkeypatch.setattr(mc, "_now", lambda: t)
    return fdir, t


@pytest.fixture(autouse=True)
def _clean_caches():
    yield
    rt._OPTIMAL_XP_CACHE.clear()
    rt._FPL_CACHE.clear()


@pytest.mark.parametrize("phase", PHASES, ids=[p[0] for p in PHASES])
def test_source_and_gameweek_per_phase(monkeypatch, tmp_path, phase):
    _setup(monkeypatch, tmp_path, phase)
    exp_source, exp_gw, exp_picks_gw, exp_dl = phase[-4:]
    out = mc.model_captain()
    m = out["meta"]
    assert m["source"] == exp_source, (phase[0], m)
    assert m["gw"] == exp_gw, (phase[0], m)
    assert m["picks_gw"] == exp_picks_gw, (phase[0], m)
    assert m["deadline_gameweek"] == exp_dl, (phase[0], m)
    assert m["entry_id"] == ENTRY_ID
    if exp_source == "frozen":
        assert m["frozen_at"], phase[0]
        assert m["route"]["kind"] == "gw_calls"
        assert out["alternative"] is None
    else:
        assert m["frozen_at"] is None
        assert m["route"]["url"].endswith(f"/entry/{ENTRY_ID}/event/{exp_picks_gw}")


@pytest.mark.parametrize("phase", PHASES, ids=[p[0] for p in PHASES])
def test_captain_is_the_frozen_one_whenever_a_freeze_exists(monkeypatch, tmp_path, phase):
    """INVARIANTTI: jos kortin kierrokselle on freeze, kapteeni == freezen
    kapteeni == gw_calls-lokin `model_captain`. Muuten kapteeni on rate-teamin
    nimeama (sama saanto kuin ennen tata muutosta)."""
    fdir, now = _setup(monkeypatch, tmp_path, phase)
    out = mc.model_captain()
    gw = out["meta"]["gw"]
    path = fdir / f"gw{gw}.json"
    if path.exists():
        frozen = json.loads(path.read_text(encoding="utf-8"))
        # gw_calls-lokin rivi samasta freezesta, ENNEN sen deadlinea
        before = gw_calls.parse_utc(frozen["meta"]["deadline"]) - dt.timedelta(hours=2)
        log_row = gw_calls.build_entry(frozen, {}, {}, before, None)
        log_cap = [c for c in log_row["calls"] if c["call"] == "model_captain"]
        assert len(log_cap) == 1
        assert out["captain"]["id"] == frozen["captain"] == log_cap[0]["player_id"], phase[0]
        assert out["meta"]["source"] == "frozen"
        # Erotteleva kontrolli: rate-teamin saanto samalle rungolle nimeaisi
        # eri pelaajan, eli testi ei ole vihrea sattumalta.
        ids = [p["id"] for p in frozen["xi"] + frozen["bench"]]
        suggestion = rt.rate_team(players=ids, bank=0.0)["captain"]["pick"]["id"]
        assert suggestion != out["captain"]["id"], phase[0]
    else:
        assert out["meta"]["source"] == "entry_picks"
        expected = rt.rate_team(entry=ENTRY_ID)["captain"]["pick"]["id"]
        assert out["captain"]["id"] == expected, phase[0]


def test_frozen_phase_fixes_the_bug_that_was_published(monkeypatch, tmp_path):
    """Vaihe b tasmalleen: rate-team entrylle nimeaa GW5-pickien kapteenin,
    freeze nimeaa toisen. Kortin on nimettava freezen."""
    _setup(monkeypatch, tmp_path, PHASES[1])
    old_path = rt.rate_team(entry=ENTRY_ID)
    assert old_path["meta"]["picks_gw"] == 5
    assert old_path["captain"]["pick"]["id"] == TOP_XP_IN_SQUAD
    out = mc.model_captain()
    assert out["captain"]["id"] == FROZEN_CAPTAIN != TOP_XP_IN_SQUAD
    assert out["captain"]["opponents"] == [{"opp": "LIV", "venue": "A"}]
    assert out["captain"]["gw_xp"] == round(_BY_ID[FROZEN_CAPTAIN]["xp_per_gw"], 2)
    assert out["captain"]["gw_xp_basis"] == "projection"
    assert out["captain"]["gw_xp_frozen"] == 3.33
    assert out["vice_captain"]["id"] == FROZEN_VICE
    assert out["meta"]["frozen_deadline"] == DEADLINES[6]


def test_frozen_phase_does_not_read_the_entry_picks_at_all(monkeypatch, tmp_path):
    """Freezen ja deadlinen valissa FPL:n entry-pickit ovat edellisen
    kierroksen runko. Freeze-tila ei saa nojata niihin lainkaan: jos FPL:n
    entry-rajapinta on alhaalla, kortti vastaa silti freezesta. (Mutaatio
    M2: ilman deadline-kierroksen freeze-tarkistusta lukija kavisi
    rate-teamin kautta ja kaatuisi tahan.)"""
    _setup(monkeypatch, tmp_path, PHASES[1])
    real = rt._fetch_fpl

    def entry_down(path):
        if path.startswith("/entry/"):
            raise rt.RateTeamError(503, "FPL entry API down")
        return real(path)

    monkeypatch.setattr(rt, "_fetch_fpl", entry_down)
    rt._FPL_CACHE.clear()
    out = mc.model_captain()
    assert out["meta"]["source"] == "frozen"
    assert out["captain"]["id"] == FROZEN_CAPTAIN


def test_frozen_captain_missing_from_projection_falls_back_to_frozen_xp(
        monkeypatch, tmp_path):
    """Sama arvosaanto kuin gw_calls-lokissa: tuore projektio jos on, muuten
    freezen luku, ja pinta kertoo kumpi (`gw_xp_basis`)."""
    _setup(monkeypatch, tmp_path, PHASES[1])
    xp = rt.load_xp()
    xp["players"] = [p for p in xp["players"] if p["id"] != FROZEN_CAPTAIN]
    monkeypatch.setattr(rt, "load_xp", lambda: copy.deepcopy(xp))
    out = mc.model_captain()
    assert out["captain"]["id"] == FROZEN_CAPTAIN
    assert out["captain"]["gw_xp"] == 3.33
    assert out["captain"]["gw_xp_basis"] == "frozen"
    assert out["captain"]["opponents"] is None


@pytest.mark.parametrize("breakage", ["json", "gw_mismatch", "captain_not_in_squad"])
def test_broken_freeze_fails_closed(monkeypatch, tmp_path, breakage):
    """Rikkinainen freeze EI pudota hiljaa rate-teamin arvaukseen."""
    fdir, _now = _setup(monkeypatch, tmp_path, PHASES[1])
    p = fdir / "gw6.json"
    if breakage == "json":
        p.write_text("{not json", encoding="utf-8")
    else:
        doc = json.loads(p.read_text(encoding="utf-8"))
        if breakage == "gw_mismatch":
            doc["meta"]["gw"] = 5
        else:
            doc["captain"] = 999
        p.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(mc.ModelCaptainError) as ei:
        mc.model_captain()
    assert ei.value.status_code == 503


def test_next_deadline_boundary():
    events = [{"id": 5, "deadline_time": DEADLINES[5]},
              {"id": 6, "deadline_time": DEADLINES[6]},
              {"id": 7, "deadline_time": DEADLINES[7]}]
    at = gw_calls.parse_utc(DEADLINES[6])
    # Tasan deadlinella kierros on lukittu: seuraava on GW7.
    assert mc.next_deadline(events, at)[0] == 7
    assert mc.next_deadline(events, at - dt.timedelta(seconds=1))[0] == 6
    assert mc.next_deadline(events, gw_calls.parse_utc("2027-01-01T00:00:00Z")) is None
    # Jarjestys ei riipu listan jarjestyksesta.
    assert mc.next_deadline(list(reversed(events)), at - dt.timedelta(days=30))[0] == 5


# ---------------------------------------------------------------------------
# Endpoint: kutsupaikka + response_model (muisti: testi kutsuu funktiota,
# ei kutsupaikkaa - endpoint mitataan HTTP:n yli)
# ---------------------------------------------------------------------------

ALLOWED_TOP = {"meta", "captain", "vice_captain", "alternative"}


@pytest.mark.parametrize("phase", [PHASES[0], PHASES[1]], ids=["a", "b"])
def test_endpoint_serves_the_one_reader(client, monkeypatch, tmp_path, phase):
    _setup(monkeypatch, tmp_path, phase)
    r = client.get("/api/fantasy/model-captain")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == ALLOWED_TOP
    assert r.headers.get("cache-control") == "no-store"
    assert body["meta"]["source"] == phase[-4]
    if phase[-4] == "frozen":
        assert body["captain"]["id"] == FROZEN_CAPTAIN
        assert body["captain"]["opponents"] == [{"opp": "LIV", "venue": "A"}]
    else:
        assert body["captain"]["id"] == TOP_XP_IN_SQUAD
        assert body["meta"]["picks_gw"] == 5


def test_endpoint_broken_freeze_is_503(client, monkeypatch, tmp_path):
    fdir, _t = _setup(monkeypatch, tmp_path, PHASES[1])
    (fdir / "gw6.json").write_text("{", encoding="utf-8")
    r = client.get("/api/fantasy/model-captain")
    assert r.status_code == 503


def test_endpoint_carries_no_premium_fields(client, monkeypatch, tmp_path):
    """Ilmaista dataa: ei siirtoehdotuksia, ei rate-teamin muita lohkoja.
    response_model rajaa kentat, joten lahteen muutos ei voi vuotaa."""
    _setup(monkeypatch, tmp_path, PHASES[0])
    body = client.get("/api/fantasy/model-captain").json()
    flat = json.dumps(body)
    for forbidden in ("suggestions", "transfers", "hold_verdict", "rating",
                      "team_xp", "last_finished"):
        assert forbidden not in flat, forbidden


def test_openapi_documents_the_route(client):
    spec = client.get("/openapi.json").json()
    op = spec["paths"]["/api/fantasy/model-captain"]["get"]
    ref = op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/ModelCaptainResponse")
    meta = spec["components"]["schemas"]["ModelCaptainMeta"]["properties"]
    assert set(meta["source"]["enum"]) == {"frozen", "entry_picks"}
