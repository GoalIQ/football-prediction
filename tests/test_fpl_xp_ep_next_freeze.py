# -*- coding: utf-8 -*-
"""D5 (22.9.2026): GoalIQ xP vs FPL:n oma projektio (ep_next), molemmat
jaadytettyina ennen deadlinea, gradattuna toteumaa vasten.

Kolme asiaa lukitaan:
  1. VAIHEET (CLAUDE.md 6a kohta 3): freeze ajetaan synteettisilla hetkilla
     (ikkunan ulkopuolella, ikkunassa, deadlinen jalkeen, vanhentunut
     valimuisti). Deadlinen jalkeen haettu ep_next viittaa jo SEURAAVAAN
     kierrokseen, joten se ei saa koskaan paatya kierroksen N
     "deadline-arvoksi". Testit ajetaan myos main():n eli KUTSUPAIKAN kautta.
  2. YKSI LUKIJA: gradaus lukee ep_next:n vain fpl_xp_accuracy.frozen_players
     -funktion kautta, joka riisuu kentan jos meta ei todista sita
     deadline-arvoksi.
  3. GRADAUS tunnetulla MAE:lla: vs_fpl_ep_next kaikki / pelasi / ei pelannut.

Ei verkkoa: bootstrap, hakuhetki ja kello syotetaan kasin.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import freeze_fpl_xp_gw as fz  # noqa: E402
from scripts import grade_fpl_xp_gw as gr  # noqa: E402
from src.models import fpl_xp_accuracy as xacc  # noqa: E402
from src.models.fpl_xp_accuracy import PRED_EP_NEXT, PRED_GOALIQ  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc


def _t(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


GW6_DL = _t("2026-10-10T10:00:00Z")


def _events(is_next: int, gw5_finished=True, gw7_deadline="2026-10-17T10:00:00Z"):
    """GW5 pelattu, GW6 deadline 10.10 10:00, GW7 myohemmin. is_next kertoo
    mihin kierrokseen bootstrapin ep_next viittaa."""
    evs = [
        {"id": 5, "deadline_time": "2026-09-18T17:30:00Z", "finished": gw5_finished},
        {"id": 6, "deadline_time": "2026-10-10T10:00:00Z", "finished": False},
        {"id": 7, "deadline_time": gw7_deadline, "finished": False},
    ]
    for e in evs:
        e["is_next"] = e["id"] == is_next
    return evs


def _boot(is_next: int, **kw) -> dict:
    return {"events": _events(is_next, **kw),
            "elements": [
                {"id": 1, "ep_next": "4.5", "form": "4.5"},
                {"id": 2, "ep_next": "1.2", "form": "1.6"},
                # id 3 = uusi pelaaja: projektiossa mutta ei viela bootstrapissa
                {"id": 4, "ep_next": "", "form": "0.0"},   # tyhja ep_next
            ]}


def _xp_doc(n_extra: int = 0) -> dict:
    players = [
        {"id": 1, "web_name": "A", "pos": "MID",
         "gameweeks": [{"gw": 6, "xp": 5.0}, {"gw": 7, "xp": 4.0}]},
        {"id": 2, "web_name": "B", "pos": "DEF",
         "gameweeks": [{"gw": 6, "xp": 2.0}, {"gw": 7, "xp": 2.5}]},
        {"id": 3, "web_name": "C", "pos": "FWD",
         "gameweeks": [{"gw": 6, "xp": 1.0}, {"gw": 7, "xp": 1.0}]},
        {"id": 4, "web_name": "D", "pos": "GKP",
         "gameweeks": [{"gw": 6, "xp": 3.0}, {"gw": 7, "xp": 3.0}]},
    ]
    # main() vaatii >= 200 rivia; taytteet ilman bootstrap-rivia (ep_next None)
    for i in range(n_extra):
        players.append({"id": 1000 + i, "web_name": f"X{i}", "pos": "MID",
                        "gameweeks": [{"gw": 6, "xp": 0.5}, {"gw": 7, "xp": 0.5}]})
    return {"meta": {"generated_at": "2026-10-09T11:50:00+00:00"}, "players": players}


# ---------------------------------------------------------------------------
# 1a. Vaiheet puhtaalla ytimella
# ---------------------------------------------------------------------------
def test_ikkunassa_ennen_deadlinea_ep_next_jaadytetaan_hakuhetken_kanssa():
    now = _t("2026-10-09T12:00:00Z")              # T-22 h
    fetched = _t("2026-10-09T11:48:00Z")          # valimuisti 12 min vanha
    doc = fz.build_frozen(_xp_doc(), _boot(is_next=6), now, fetched)
    meta = doc["meta"]
    assert meta["gw"] == 6
    assert meta["deadline"] == "2026-10-10T10:00:00Z"
    assert meta["fpl_reference_status"] == xacc.REF_OK
    assert meta["fpl_reference_fetched_at"] == "2026-10-09T11:48:00Z"
    assert meta["frozen_at"] == "2026-10-09T12:00:00Z"
    assert meta["ep_next_gw"] == 6
    by_id = {p["id"]: p for p in doc["players"]}
    assert by_id[1]["ep_next"] == pytest.approx(4.5)
    assert by_id[2]["ep_next"] == pytest.approx(1.2)
    # Uusi pelaaja (ei bootstrapissa) ja tyhja ep_next -> None, ei 0.
    assert by_id[3]["ep_next"] is None
    assert by_id[4]["ep_next"] is None
    assert meta["n_ep_next"] == 2
    assert xacc.ep_next_is_deadline_value(meta)


def test_ikkunan_ulkopuolella_ei_jaadytysta():
    now = _t("2026-10-08T09:00:00Z")              # T-49 h
    assert fz.build_frozen(_xp_doc(), _boot(is_next=6), now, now) is None


def test_deadlinen_jalkeen_kierrosta_ei_jaadyteta_lainkaan():
    """10:30 GW6:n deadlinen jalkeen FPL on jo kaantanyt is_next -> GW7 ja
    ep_next on GW7:n luku. GW6:lle ei saa syntya mitaan, eika GW7:lle
    ennen sen omaa ikkunaa."""
    now = _t("2026-10-10T10:30:00Z")
    boot = _boot(is_next=7)
    boot["events"][1]["is_current"] = True
    assert fz.pick_freeze_target(boot["events"], now) is None
    assert fz.build_frozen(_xp_doc(), boot, now, now) is None


def test_deadlinen_jalkeen_seuraava_kierros_ikkunassa_saa_oman_arvonsa():
    """Tiivis ohjelma: GW7:n deadline on 23 h GW6:n jalkeen. Deadlinen
    jalkeinen ajo jaadyttaa GW7:n (is_next = 7), EI GW6:ta GW7:n ep_nextilla."""
    now = _t("2026-10-10T10:30:00Z")
    boot = _boot(is_next=7, gw7_deadline="2026-10-11T09:30:00Z")
    doc = fz.build_frozen(_xp_doc(), boot, now, now - dt.timedelta(minutes=5))
    assert doc["meta"]["gw"] == 7
    assert doc["meta"]["fpl_reference_status"] == xacc.REF_OK
    by_id = {p["id"]: p for p in doc["players"]}
    assert by_id[1]["xp"] == pytest.approx(4.0)   # GW7:n xP, ei GW6:n


def test_vanhentunut_valimuisti_edellisen_kierroksen_ep_next_ei_kelpaa():
    """Bootstrap haettu ennen GW5:n deadlinea (is_next = 5), luettu GW6:n
    ikkunassa. Hakuhetki on ennen GW6:n deadlinea, joten pelkka aikaehto
    paastaisi sen lapi; is_next-ehto ei."""
    now = _t("2026-10-09T12:00:00Z")
    stale = _boot(is_next=5, gw5_finished=False)
    doc = fz.build_frozen(_xp_doc(), stale, now, _t("2026-09-18T16:00:00Z"))
    meta = doc["meta"]
    assert meta["gw"] == 6
    assert meta["fpl_reference_status"] == xacc.REF_OTHER_GW
    assert meta["n_ep_next"] == 0
    assert all("ep_next" not in p for p in doc["players"])
    assert not xacc.ep_next_is_deadline_value(meta)


@pytest.mark.parametrize("fetched,status", [
    (GW6_DL, xacc.REF_FETCHED_AFTER_DEADLINE),                         # tasan deadline
    (GW6_DL + dt.timedelta(minutes=1), xacc.REF_FETCHED_AFTER_DEADLINE),
    (None, xacc.REF_FETCH_TIME_UNKNOWN),
])
def test_hakuhetki_deadlinella_tai_tuntematon_ei_kelpaa(fetched, status):
    """Kello voi olla ennen deadlinea vaikka data haettiin sen jalkeen (tai
    hakuhetkea ei tiedeta): portti katsoo hakuhetkea, ei ajon kelloa."""
    now = GW6_DL - dt.timedelta(hours=1)
    doc = fz.build_frozen(_xp_doc(), _boot(is_next=6), now, fetched)
    assert doc["meta"]["fpl_reference_status"] == status
    assert doc["meta"]["n_ep_next"] == 0
    assert all("ep_next" not in p for p in doc["players"])
    assert not xacc.ep_next_is_deadline_value(doc["meta"])


# ---------------------------------------------------------------------------
# 1b. Vaiheet KUTSUPAIKAN (main) kautta
# ---------------------------------------------------------------------------
@pytest.fixture
def freeze_env(tmp_path, monkeypatch):
    xp_path = tmp_path / "fpl_xp_projections.json"
    xp_path.write_text(json.dumps(_xp_doc(n_extra=210)), encoding="utf-8")
    frozen_dir = tmp_path / "frozen"
    monkeypatch.setattr(fz, "XP_PATH", xp_path)
    monkeypatch.setattr(fz, "FROZEN_DIR", frozen_dir)
    state = {"boot": _boot(is_next=6), "fetched": None}
    monkeypatch.setattr(fz.fpl_api, "fetch_bootstrap", lambda *a, **k: state["boot"])
    monkeypatch.setattr(fz.fpl_api, "bootstrap_fetched_at", lambda: state["fetched"])
    return frozen_dir, state


def test_main_ennen_deadlinea_kirjoittaa_ep_nextin(freeze_env):
    frozen_dir, state = freeze_env
    now = _t("2026-10-09T12:00:00Z")
    state["fetched"] = now - dt.timedelta(minutes=3)
    assert fz.main(now=now) == 0
    doc = json.loads((frozen_dir / "gw6.json").read_text(encoding="utf-8"))
    assert doc["meta"]["fpl_reference_status"] == xacc.REF_OK
    assert doc["meta"]["fpl_reference_fetched_at"] == "2026-10-09T11:57:00Z"
    assert doc["meta"]["n_ep_next"] == 2
    # Immutable: toinen ajo ei ylikirjoita vaikka ep_next olisi muuttunut.
    state["boot"]["elements"][0]["ep_next"] = "9.9"
    assert fz.main(now=now + dt.timedelta(hours=3)) == 0
    doc2 = json.loads((frozen_dir / "gw6.json").read_text(encoding="utf-8"))
    assert doc2 == doc


def test_main_deadlinen_jalkeen_ei_kirjoita_mitaan(freeze_env):
    frozen_dir, state = freeze_env
    now = _t("2026-10-10T10:30:00Z")
    state["boot"] = _boot(is_next=7)
    state["fetched"] = now
    assert fz.main(now=now) == 0
    assert not frozen_dir.exists() or not any(frozen_dir.iterdir())


def test_main_vanhentunut_bootstrap_jaadyttaa_xpn_ilman_ep_nextia(freeze_env):
    frozen_dir, state = freeze_env
    now = _t("2026-10-09T12:00:00Z")
    state["boot"] = _boot(is_next=5, gw5_finished=False)
    state["fetched"] = _t("2026-09-18T16:00:00Z")
    assert fz.main(now=now) == 0
    doc = json.loads((frozen_dir / "gw6.json").read_text(encoding="utf-8"))
    assert doc["meta"]["fpl_reference_status"] == xacc.REF_OTHER_GW
    assert all("ep_next" not in p for p in doc["players"])
    assert len(doc["players"]) >= 200                     # xP silti jaadytetty


def test_bootstrap_fetched_at_on_valimuistin_hakuhetki(tmp_path, monkeypatch):
    """Hakuhetki = valimuistitiedoston mtime, ei kutsuhetki: fetch_bootstrap
    voi palauttaa tunnin vanhan valimuistin."""
    import os
    from src.data import fpl_api
    monkeypatch.setattr(fpl_api, "CACHE_DIR", tmp_path)
    assert fpl_api.bootstrap_fetched_at() is None
    f = tmp_path / "bootstrap_static.json"
    f.write_text("{}", encoding="utf-8")
    t = _t("2026-10-09T11:02:03Z").timestamp()
    os.utime(f, (t, t))
    assert fpl_api.bootstrap_fetched_at() == _t("2026-10-09T11:02:03Z")


# ---------------------------------------------------------------------------
# 2. Yksi lukija
# ---------------------------------------------------------------------------
def _meta(**kw):
    m = {"gw": 6, "deadline": "2026-10-10T10:00:00Z", "frozen_at": "2026-10-09T12:00:00Z"}
    m.update(kw)
    return m


@pytest.mark.parametrize("meta,ok", [
    # 22.9-rakenne
    (_meta(fpl_reference_status="ok", ep_next_gw=6,
           fpl_reference_fetched_at="2026-10-09T11:50:00Z"), True),
    (_meta(fpl_reference_status="ok", ep_next_gw=7,
           fpl_reference_fetched_at="2026-10-09T11:50:00Z"), False),
    (_meta(fpl_reference_status="ok", ep_next_gw=6,
           fpl_reference_fetched_at="2026-10-10T10:00:00Z"), False),
    (_meta(fpl_reference_status="ok", ep_next_gw=6,
           fpl_reference_fetched_at=None), False),
    (_meta(fpl_reference_status=xacc.REF_OTHER_GW, ep_next_gw=6,
           fpl_reference_fetched_at="2026-10-09T11:50:00Z"), False),
    # 29.8-rakenne (GW3-GW5): fpl_reference + frozen_at ennen deadlinea
    (_meta(fpl_reference="ep_next and form ..."), True),
    (_meta(fpl_reference="ep_next and form ...", frozen_at="2026-10-10T10:05:00Z"), False),
    # GW1/GW2-rakenne: ei referenssia lainkaan
    (_meta(), False),
    ({"gw": 6}, False),
])
def test_lukija_hyvaksyy_vain_todistetun_deadline_arvon(meta, ok):
    assert xacc.ep_next_is_deadline_value(meta) is ok


def test_frozen_players_riisuu_todistamattoman_ep_nextin():
    players = [{"id": 1, "xp": 5.0, "ep_next": 4.0, "form": 4.0, "pos": "MID"}]
    good = {"meta": _meta(fpl_reference="x"), "players": players}
    bad = {"meta": _meta(fpl_reference="x", frozen_at="2026-10-10T11:00:00Z"),
           "players": players}
    assert xacc.frozen_players(good)[0]["ep_next"] == 4.0
    stripped = xacc.frozen_players(bad)[0]
    assert "ep_next" not in stripped and "form" not in stripped
    assert stripped["xp"] == 5.0
    assert players[0]["ep_next"] == 4.0          # alkuperainen ei muutu


def test_grade_gw_ei_vertaa_deadlinen_jalkeen_haettua_ep_nextia():
    """Kutsupaikka: grade_gw:n on kuljettava frozen_players():n kautta. Jos
    se lukisi players-listan suoraan, vertailu syntyisi."""
    players = [{"id": 1, "xp": 5.0, "ep_next": 4.0, "form": 4.0, "pos": "MID"}]
    actual = {1: (6.0, 90.0)}
    bad = {"meta": _meta(fpl_reference="x", frozen_at="2026-10-10T11:00:00Z"),
           "players": players}
    row = gr.grade_gw(bad, actual)
    assert row["n"] == 1 and row["mae"] == pytest.approx(1.0)   # xP gradataan silti
    assert row["comparison"] is None
    assert row["vs_fpl_ep_next"] is None
    old = {"gw": 6, "n": 1, "mae": 1.0, "bias": 1.0, "mae_by_pos": {}}
    gr.enrich_row(old, bad, actual)
    assert old["comparison"] is None and old["vs_fpl_ep_next"] is None


def test_jaadytetyt_tiedostot_joissa_ep_next_lapaisevat_lukijan():
    """Invariantti koko historialle: jos tiedostossa on ep_next-arvoja, meta
    todistaa ne deadline-arvoiksi (muuten gradaus pudottaisi vertailun
    hiljaa). Ilman ep_nextia (GW1, GW2) lukija ei keksi niita."""
    files = sorted((ROOT / "data" / "fpl_xp_frozen").glob("gw*.json"))
    if not files:
        pytest.skip("ei jaadytettyja kierroksia tassa tyopuussa")
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        has_ep = any(p.get("ep_next") is not None for p in doc.get("players") or [])
        if has_ep:
            assert xacc.ep_next_is_deadline_value(doc["meta"]), f.name
            assert doc["meta"]["frozen_at"] < doc["meta"]["deadline"], f.name
        else:
            assert all("ep_next" not in p or p["ep_next"] is None
                       for p in xacc.frozen_players(doc)), f.name


# ---------------------------------------------------------------------------
# 3. Gradaus tunnetulla MAE:lla
# ---------------------------------------------------------------------------
def _pl(pid, xp, ep=None):
    d = {"id": pid, "pos": "MID", "xp": xp}
    if ep is not None:
        d["ep_next"] = ep
    return d


def test_vs_fpl_ep_next_tunnettu_mae_ja_minuuttijako():
    players = [
        _pl(1, 5.0, 3.0),     # pelasi, 8 p:   |3| vs |5|
        _pl(2, 2.0, 4.0),     # pelasi, 2 p:   |0| vs |2|
        _pl(8, 2.0, 1.0),     # pelasi 1 min, 0 p: |2| vs |1|
        _pl(3, 1.0, 0.0),     # ei pelannut:   |1| vs |0|
        _pl(4, 3.0, 2.0),     # ei pelannut:   |3| vs |2|
        _pl(5, 4.0),          # ep_next puuttuu -> ei vertailuun, ei 0
        _pl(6, 2.0, 2.0),     # ei toteumaa -> ei vertailuun, ei 0 p / 0 min
        {"id": 7, "pos": "MID", "xp": None, "ep_next": 1.0},   # ei xP:ta
    ]
    actual = {1: (8.0, 90.0), 2: (2.0, 60.0), 8: (0.0, 1.0),
              3: (0.0, 0.0), 4: (0.0, 0.0), 5: (3.0, 90.0), 7: (1.0, 90.0)}
    vs = xacc.vs_fpl_ep_next(players, actual)
    assert vs["method_code"] == xacc.VS_FPL_METHOD_CODE
    assert vs["n_missing_ep_next"] == 1
    assert vs["n_missing_actual"] == 1
    pl, dnp, al = vs["played"], vs["did_not_play"], vs["all"]
    assert pl["n"] == 3 and dnp["n"] == 2 and al["n"] == 5
    assert pl["mae"][PRED_GOALIQ] == pytest.approx(5 / 3, abs=1e-3)
    assert pl["mae"][PRED_EP_NEXT] == pytest.approx(8 / 3, abs=1e-3)
    assert pl["goaliq_minus_fpl"] == pytest.approx(-1.0)
    assert dnp["mae"][PRED_GOALIQ] == pytest.approx(2.0)
    assert dnp["mae"][PRED_EP_NEXT] == pytest.approx(1.0)
    assert dnp["goaliq_minus_fpl"] == pytest.approx(1.0)
    assert al["mae"][PRED_GOALIQ] == pytest.approx(1.8)
    assert al["mae"][PRED_EP_NEXT] == pytest.approx(2.0)
    assert al["goaliq_minus_fpl"] == pytest.approx(-0.2)
    # n-painotettu poolaus antaa saman kuin koko joukko (pool_groups-yhteensopiva)
    pooled = xacc.pool_groups([pl, dnp])
    assert pooled["n"] == 5
    assert pooled["mae"][PRED_GOALIQ] == pytest.approx(1.8, abs=1e-3)


def test_ero_lasketaan_pyoristamattomista():
    """1/3 vs 2/3: pyoristettyjen erotus olisi -0.334, oikea -0.333."""
    players = [_pl(1, 1.0, 2.0), _pl(2, 0.0, 0.0), _pl(3, 0.0, 0.0)]
    actual = {1: (0.0, 90.0), 2: (0.0, 90.0), 3: (0.0, 90.0)}
    al = xacc.vs_fpl_ep_next(players, actual)["all"]
    assert al["mae"][PRED_GOALIQ] == 0.333 and al["mae"][PRED_EP_NEXT] == 0.667
    assert al["goaliq_minus_fpl"] == -0.333


def test_vs_fpl_ilman_ep_nextia_on_none_ja_tyhja_ryhma_ei_ole_nolla():
    assert xacc.vs_fpl_ep_next([_pl(1, 2.0)], {1: (2.0, 90.0)}) is None
    vs = xacc.vs_fpl_ep_next([_pl(1, 2.0, 1.0)], {1: (2.0, 90.0)})
    assert vs["did_not_play"] == {"n": 0, "mae": None, "goaliq_minus_fpl": None}


def test_freeze_ja_gradaus_paasta_paahan():
    """build_frozen -> tiedosto -> grade_gw: ep_next kulkee lukijan lapi ja
    vs-lohko on tunnettu. Uusi pelaaja (id 3) ja tyhja ep_next (id 4) jaavat
    vertailusta mutta gradataan GoalIQ:n omassa MAE:ssa."""
    now = _t("2026-10-09T12:00:00Z")
    doc = fz.build_frozen(_xp_doc(), _boot(is_next=6), now, now)
    doc = json.loads(json.dumps(doc))                 # levyn kautta kulkeva muoto
    actual = {1: (8.0, 90.0), 2: (1.0, 90.0), 3: (0.0, 0.0), 4: (2.0, 90.0)}
    row = gr.grade_gw(doc, actual)
    assert row["n"] == 4
    vs = row["vs_fpl_ep_next"]
    assert vs["n_missing_ep_next"] == 2
    # id1: |8-5|=3 vs |8-4.5|=3.5 ; id2: |1-2|=1 vs |1-1.2|=0.2
    assert vs["played"]["mae"][PRED_GOALIQ] == pytest.approx(2.0)
    assert vs["played"]["mae"][PRED_EP_NEXT] == pytest.approx(1.85)
    assert vs["played"]["goaliq_minus_fpl"] == pytest.approx(0.15)
    assert vs["did_not_play"]["n"] == 0


def test_taydennys_lisaa_vain_puuttuvan_lohkon():
    """Append-only: vanha comparison-lohko ei laskeudu uudelleen kun uusi
    vs_fpl_ep_next-avain taydennetaan (FPL voi korjata live-dataa)."""
    sentinel = {"n": 1, "mae": {"goaliq": 9.0}}
    row = {"gw": 6, "n": 1, "mae": 1.0, "bias": 1.0, "mae_by_pos": {},
           "by_class": {"x": 1}, "by_pos_stats": {"y": 1}, "comparison": sentinel}
    assert gr.needs_enrich(row)
    frozen = {"meta": _meta(fpl_reference="x"),
              "players": [{"id": 1, "xp": 5.0, "ep_next": 4.0, "form": 4.0, "pos": "MID"}]}
    gr.enrich_row(row, frozen, {1: (6.0, 90.0)})
    assert row["comparison"] is sentinel
    assert row["by_class"] == {"x": 1}
    assert row["vs_fpl_ep_next"]["all"]["goaliq_minus_fpl"] == pytest.approx(-1.0)
    assert not gr.needs_enrich(row)
