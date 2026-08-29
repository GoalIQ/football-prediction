"""DEADLINE-SNAPSHOT (29.8.2026): kutsujen snapshot T-2 h -ikkunassa,
erillaan siirtofreezesta (T-24 h).

Portit:
1. paivitys ennen deadlinea sallittu ja korvaa arvot; logged_at sailyy,
   updated_at paivittyy, projected_xi-kutsu ei putoa
2. deadlinen jalkeen: exit 1 ja tiedosto koskematon (negatiivinen kontrolli
   skriptitasolla, ei vain funktiotasolla)
3. guard-ikkuna on leveampi kuin cron-cadenssi + drift (muisti
   "cron-ikkuna kapeampi kuin cadenssi")
4. workflow-rakenne: tuntiajo on schedulessa ja guard kutsuu skriptia
5. mittari M1 (start-osuus) lasketaan lokista gradauksen `started`-lipusta
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

import pytest
import yaml

from scripts import deadline_snapshot_guard as guard
from src.models.gw_calls import (NEW_LOG, build_entry, grade_entry,
                                 start_share, upsert, upsert_call)

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "fpl-data-refresh.yml"
SNAPSHOT_CRON = "40 7-18 * * *"

DL = "2026-08-28T17:30:00Z"
T0 = _dt.datetime(2026, 8, 27, 17, 4, tzinfo=_dt.timezone.utc)   # freeze T-24 h
T1 = _dt.datetime(2026, 8, 28, 16, 0, tzinfo=_dt.timezone.utc)   # snapshot T-90
AFTER = _dt.datetime(2026, 8, 28, 17, 30, tzinfo=_dt.timezone.utc)


def _p(pid, name, p_haul=0.1, gw_xp=4.5):
    return {"id": pid, "web_name": name, "team_short": "XXX", "pos": "MID",
            "gameweeks": [{"gw": 2, "xp": gw_xp}],
            "xp_dist": {"gw": 2, "n": 2000, "p_haul": p_haul, "p_blank": 0.3,
                        "p10": 1, "median": 4, "p90": 10, "haul_pts": 10,
                        "blank_pts": 2}}


def _frozen():
    return {"meta": {"gw": 2, "deadline": DL,
                     "frozen_at": "2026-08-27T17:04:43Z", "transfers": []},
            "captain": 388, "vice_captain": 115,
            "xi": [{"id": 388, "web_name": "Guehi", "team_short": "MCI",
                    "pos": 2, "xp": 4.76},
                   {"id": 115, "web_name": "De Cuyper", "team_short": "BHA",
                    "pos": 2, "xp": 4.6}],
            "bench": []}


def _standouts(cap_name="Cap", p_haul=0.11):
    return {"captain": _p(1, cap_name, p_haul=p_haul), "ceiling": _p(2, "Ceil"),
            "safest": _p(3, "Safe"), "gamble": _p(4, "Gamb")}


# --------------------------------------------------------------- 1. paivitys
def test_snapshot_paivittaa_arvot_ja_sailyttaa_ensimmaisen_aikaleiman():
    log = json.loads(json.dumps(NEW_LOG))
    e0 = build_entry(_frozen(), _standouts(), {"generated_at": "A"}, T0)
    upsert(log, e0, T0)
    # kortti kirjaa projected_xi:n valissa
    upsert_call(log, 2, DL, {"call": "projected_xi", "player_id": 388,
                             "web_name": "3-4-3 XI", "value": 60.0},
                T0 + _dt.timedelta(hours=2))
    # T-90: tuore projektio, kapteenin xP muuttui, kortin kapteeni vaihtui
    by_id = {388: {"id": 388, "gameweeks": [{"gw": 2, "xp": 5.9}]}}
    e1 = build_entry(_frozen(), _standouts("NewCap", 0.2),
                     {"generated_at": "B"}, T1, by_id)
    upsert(log, e1, T1)

    assert len(log["gameweeks"]) == 1
    row = log["gameweeks"][0]
    calls = {c["call"]: c for c in row["calls"]}
    assert calls["captain_pick"]["web_name"] == "NewCap"
    assert calls["captain_pick"]["value"] == pytest.approx(0.2)
    assert calls["model_captain"]["web_name"] == "Guehi", "henkilo freezesta"
    assert calls["model_captain"]["value"] == pytest.approx(5.9), "arvo tuore"
    assert calls["model_captain"]["frozen_value"] == pytest.approx(4.76)
    assert "projected_xi" in calls, "kortin kutsu ei saa pudota paivityksessa"
    assert row["logged_at"] == "2026-08-27T17:04:00Z"
    assert row["updated_at"] == "2026-08-28T16:00:00Z"
    assert row["source"]["projection_generated_at"] == "B"
    assert row["source"]["freeze_frozen_at"] == "2026-08-27T17:04:43Z"


def test_ensimmainen_kirjaus_saa_molemmat_aikaleimat_samaksi():
    log = json.loads(json.dumps(NEW_LOG))
    upsert(log, build_entry(_frozen(), _standouts(), {}, T0), T0)
    row = log["gameweeks"][0]
    assert row["logged_at"] == row["updated_at"] == "2026-08-27T17:04:00Z"


# ----------------------------------------------- 2. skripti: fail-closed
@pytest.fixture
def paths(tmp_path, monkeypatch):
    from scripts import log_gw_calls as mod
    frozen_dir = tmp_path / "frozen"
    frozen_dir.mkdir()
    (frozen_dir / "gw2.json").write_text(json.dumps(_frozen()), encoding="utf-8")
    xp = {"meta": {"generated_at": "2026-08-28T15:55:00", "deadline_gameweek": 2},
          "players": [_p(1, "Cap", p_haul=0.7, gw_xp=8.0),
                      _p(2, "Ceil", gw_xp=7.0), _p(3, "Safe", gw_xp=6.0),
                      _p(4, "Gamb", p_haul=0.3, gw_xp=5.0)]}
    xp_path = tmp_path / "xp.json"
    xp_path.write_text(json.dumps(xp), encoding="utf-8")
    log_path = tmp_path / "gw_calls.json"
    monkeypatch.setattr(mod, "FROZEN_DIR", frozen_dir)
    monkeypatch.setattr(mod, "XP_PATH", xp_path)
    monkeypatch.setattr(mod, "LOG_PATH", log_path)
    return mod, log_path


def _freeze_clock(monkeypatch, mod, when):
    class _Clock(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return when if tz else when.replace(tzinfo=None)
    monkeypatch.setattr(mod._dt, "datetime", _Clock)


def _seed_log(log_path):
    log = json.loads(json.dumps(NEW_LOG))
    upsert(log, build_entry(_frozen(), _standouts(), {"generated_at": "A"}, T0), T0)
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    return log_path.read_bytes()


def test_skripti_paivittaa_rivin_ennen_deadlinea(paths, monkeypatch, capsys):
    mod, log_path = paths
    _seed_log(log_path)
    _freeze_clock(monkeypatch, mod, T1)
    assert mod.main([]) == 0
    row = json.loads(log_path.read_text(encoding="utf-8"))["gameweeks"][0]
    assert row["logged_at"] == "2026-08-27T17:04:00Z"
    assert row["updated_at"] == "2026-08-28T16:00:00Z"
    assert row["source"]["projection_generated_at"] == "2026-08-28T15:55:00"
    out = capsys.readouterr().out
    assert "ensimmainen 2026-08-27T17:04:00Z" in out
    assert "viimeisin 2026-08-28T16:00:00Z" in out


def test_skripti_deadlinen_jalkeen_exit_1_ja_tiedostoa_ei_synny(paths, monkeypatch):
    """Negatiivinen kontrolli: rivia ei ole, deadline ohi -> exit 1, ei tiedostoa."""
    mod, log_path = paths
    _freeze_clock(monkeypatch, mod, AFTER)
    assert mod.main([]) == 1
    assert not log_path.exists()


def test_skripti_deadlinen_jalkeen_ei_koske_olemassa_olevaan_riviin(paths, monkeypatch):
    """Rivi on lokissa ennen deadlinea -> exit 0 (kutsu on kirjattu), mutta
    tiedosto on tavulleen sama: paivitys deadlinen jalkeen olisi jalkiviisaus."""
    mod, log_path = paths
    before = _seed_log(log_path)
    _freeze_clock(monkeypatch, mod, AFTER)
    assert mod.main([]) == 0
    assert log_path.read_bytes() == before


def test_upsertin_vahti_yksin_riittaa_deadlinen_jalkeen(paths, monkeypatch):
    """Skriptin polulla on KAKSI vahtia (build_entry ja upsert) ja molemmat
    nostavat DeadlinePassedin. Mitattu 29.8: upsertin vahdin poisto ei kaada
    yhtaakaan skriptitason testia, koska build_entry ehtii ensin (muisti:
    "kaksi vahtia yhdessa testissa"). Tama testi ohittaa build_entryn vahdin
    ja mittaa upsertin omana porttinaan: tiedoston pitaa jaada koskematta."""
    mod, log_path = paths
    before = _seed_log(log_path)
    real = mod.build_entry
    monkeypatch.setattr(mod, "build_entry",
                        lambda *a, **kw: real(*a[:3], T1, *a[4:], **kw))
    _freeze_clock(monkeypatch, mod, AFTER)
    assert mod.main([]) == 0
    assert log_path.read_bytes() == before


# ------------------------------------------------------ 3. guard-ikkuna
def _events(deadline: str):
    return [{"id": 2, "deadline_time": deadline},
            {"id": 3, "deadline_time": "2026-09-13T10:00:00Z"}]


def test_guard_ikkuna_on_leveampi_kuin_cadenssi_ja_drift():
    lo, hi = guard.SNAPSHOT_WINDOW_MIN
    assert hi - lo > guard.CRON_CADENCE_MIN + guard.CRON_DRIFT_ALLOWANCE_MIN


def test_guard_osuu_ikkunaan_ja_ohittaa_sen_ulkopuolella():
    ev = _events(DL)
    lo, hi = guard.SNAPSHOT_WINDOW_MIN
    dl = guard._parse(DL)
    hit = guard.snapshot_gw(ev, dl - _dt.timedelta(minutes=110))
    assert hit and hit["gw"] == 2 and hit["minutes_ahead"] == 110
    assert guard.snapshot_gw(ev, dl - _dt.timedelta(minutes=lo)) is not None
    assert guard.snapshot_gw(ev, dl - _dt.timedelta(minutes=hi)) is not None
    assert guard.snapshot_gw(ev, dl - _dt.timedelta(minutes=hi + 1)) is None
    assert guard.snapshot_gw(ev, dl - _dt.timedelta(minutes=lo - 1)) is None
    assert guard.snapshot_gw(ev, dl + _dt.timedelta(minutes=5)) is None
    assert guard.snapshot_gw([], dl) is None


def _run_guard(monkeypatch, capsys, events, now, boom=False):
    """Aja guard.main() ilman verkkoa; palauta stdout (= GITHUB_OUTPUT-rivi)."""
    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    def _fake(url, timeout=None):
        if boom:
            raise OSError("bootstrap alhaalla")
        return _Resp()
    monkeypatch.setattr(guard.urllib.request, "urlopen", _fake)
    monkeypatch.setattr(guard.json, "load", lambda r: {"events": events})
    class _Clock(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz else now.replace(tzinfo=None)
    monkeypatch.setattr(guard._dt, "datetime", _Clock)
    assert guard.main() == 0
    return capsys.readouterr().out.strip()


def test_guard_main_tulostaa_proceed_ikkunan_mukaan(monkeypatch, capsys):
    dl = guard._parse(DL)
    assert _run_guard(monkeypatch, capsys, _events(DL),
                      dl - _dt.timedelta(minutes=90)) == "proceed=true"
    assert _run_guard(monkeypatch, capsys, _events(DL),
                      dl - _dt.timedelta(hours=20)) == "proceed=false"


def test_guard_on_fail_closed_kun_bootstrap_kaatuu(monkeypatch, capsys):
    """Tuntiajo laukeaa 12 kertaa paivassa: fail-open ajaisi taydet builderit
    joka tunti FPL-katkon ajan ja jattaisi putken pysyvasti punaiseksi.
    Ohitettu ajo yritetaan uudelleen tunnin paasta, ikkunaan mahtuu kaksi."""
    dl = guard._parse(DL)
    out = _run_guard(monkeypatch, capsys, _events(DL),
                     dl - _dt.timedelta(minutes=90), boom=True)
    assert out == "proceed=false"


@pytest.mark.parametrize("deadline", ["2026-09-12T10:00:00Z",   # la
                                      "2026-09-12T11:30:00Z",   # la, myohainen
                                      "2026-08-28T17:30:00Z",   # pe
                                      "2026-09-15T18:30:00Z"])  # ti
def test_tuntiajo_osuu_ikkunaan_jokaisella_deadline_tyypilla(deadline):
    """Simuloi cronin `40 7-18` laukeamiset drift 0 ja drift 50 min -> ainakin
    yksi ajo osuu ikkunaan ja ehtii valmistua (10 min) ennen deadlinea."""
    ev = _events(deadline)
    dl = guard._parse(deadline)
    for drift in (0, 50):
        hits = []
        for hour in range(7, 19):
            for day_off in (-1, 0):
                fire = (dl.replace(hour=hour, minute=40, second=0)
                        + _dt.timedelta(days=day_off, minutes=drift))
                if guard.snapshot_gw(ev, fire):
                    hits.append(fire)
        assert hits, f"drift {drift}: ei yhtaan ajoa ikkunassa"
        assert all(h + _dt.timedelta(minutes=10) < dl for h in hits)


# ------------------------------------------------------ 4. workflow-rakenne
def _doc():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_workflow_schedule_sisaltaa_tuntiajon():
    doc = _doc()
    # PyYAML lukee avaimen `on` booleanina True.
    on = doc.get("on") or doc.get(True)
    crons = [s["cron"] for s in on["schedule"]]
    assert SNAPSHOT_CRON in crons
    assert "0 */3 * * *" in crons and "15 9 * * *" in crons, "vanhat ajot sailyvat"


def test_workflow_guard_kutsuu_snapshot_skriptia_vain_tuntiajolle():
    steps = _doc()["jobs"]["build-and-commit"]["steps"]
    g = next(s for s in steps if s.get("id") == "guard")
    run = g["run"]
    assert SNAPSHOT_CRON in run
    assert "python3 scripts/deadline_snapshot_guard.py" in run
    # skripti tulostaa proceed=... GITHUB_OUTPUTiin, jota muut askeleet lukevat
    m = re.search(r"deadline_snapshot_guard\.py\s*>>\s*\"\$GITHUB_OUTPUT\"", run)
    assert m, "guardin tuloste ei mene GITHUB_OUTPUTiin"
    # 09:15-haara sailyy
    assert "15 9 * * *" in run
    log_step = next(s for s in steps
                    if s.get("name") == "Log gameweek calls before the deadline")
    assert log_step["if"] == "steps.guard.outputs.proceed == 'true'"


def test_guard_skripti_on_stdlib_only():
    src = (ROOT / "scripts" / "deadline_snapshot_guard.py").read_text(encoding="utf-8")
    imports = re.findall(r"^(?:from|import)\s+([A-Za-z_][\w.]*)", src, re.M)
    assert not any(i.startswith(("config", "src", "scripts", "requests", "pandas"))
                   for i in imports), imports


# ------------------------------------------------------ 5. mittari M1
def test_start_share_lasketaan_gradauksen_started_lipusta():
    log = json.loads(json.dumps(NEW_LOG))
    for gw, t in ((1, T0 - _dt.timedelta(days=7)), (2, T0)):
        fr = _frozen()
        fr["meta"]["gw"] = gw
        fr["meta"]["deadline"] = (guard._parse(DL) - _dt.timedelta(days=7 * (2 - gw))
                                  ).strftime("%Y-%m-%dT%H:%M:%SZ")
        st = _standouts()
        for p in st.values():
            p["gameweeks"][0]["gw"] = gw
        upsert(log, build_entry(fr, st, {}, t), t)
    pts = {388: 6, 1: 12, 2: 9, 3: 2, 4: 10}
    mins = {388: 90, 1: 90, 2: 20, 3: 0, 4: 90}
    starts = {388: 1, 1: 1, 2: 0, 3: 0, 4: 1}
    for row in log["gameweeks"]:
        grade_entry(row, pts, mins, provisional=False, now=AFTER, starts=starts)
    g = log["gameweeks"][0]["graded"]["by_call"]
    assert g["ceiling"]["started"] is False and g["ceiling"]["minutes"] == 20
    assert g["captain_pick"]["started"] is True
    m = start_share(log, [1, 2])
    assert m == {"gws": [1, 2], "calls": 10, "started": 6, "share": 0.6}
    assert start_share(log, [3, 4])["share"] is None, "ei dataa -> None, ei 0"
    # ilman starts-dataa lippu on None eika rivi laske mukaan
    log2 = json.loads(json.dumps(NEW_LOG))
    upsert(log2, build_entry(_frozen(), _standouts(), {}, T0), T0)
    grade_entry(log2["gameweeks"][0], pts, mins, provisional=False, now=AFTER)
    assert start_share(log2, [2])["calls"] == 0
