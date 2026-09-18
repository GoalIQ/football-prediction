# -*- coding: utf-8 -*-
"""XP-HORIZON-ALKANUT-KIERROS (17.9.2026): `xp_horizon_total` ei saa sisaltaa
kierrosta johon lukija ei voi enaa vaikuttaa.

MITATTU LIVENA 12.9: kierros kesken, `next_gameweek` 4, `deadline_gameweek`
5. Haaland `xp_horizon_total` 38.06 = GW4-9, mutta pelattavien GW5-9 summa
oli 32.65. Luku nakyi XpTablessa, mobiilin xP-listassa, ProductIntrossa ja
jakokorteissa otsikon "next 6 GW" alla: viisi kayttokelpoista kierrosta
kuudeksi merkittyna.

MIKSI EI `load_xp_actionable` KAIKKIALLE: 13.9 todettiin etta lukijan vaihto
on ristiriidassa `tests/test_xp_reader_discipline.py`:n RAW_ALLOWED
`api/main.py` -poikkeuksen kanssa — ilmaispinnan xP-endpointit palauttavat
koko horisontin tarkoituksella, koska sivu nayttaa gradatun kierroksen
tuloksen elavan projektion vieressa. Rivit pysyvat; SUMMA rajataan.

SOPIMUS (SPA ja mobiili rakentavat taman varaan samaan aikaan):
  meta.horizon_gw            ennallaan = GW-sarakkeiden maara riveissa
  meta.horizon_total_from    UUSI int  = ensimmainen summattu kierros
  meta.horizon_total_gw      UUSI int  = montako kierrosta summattiin
  players[].xp_horizon_total nimi ennallaan, summa vain >= horizon_total_from,
                             laskettu SERVE-TIMESSA
  players[].gameweeks[]      ennallaan

KOLME MEKANISMIA (CLAUDE.md 6a):
  (1) yksi lukija: `fpl_xp.horizon_total_actionable` + payload-kaare
      `attach_horizon_total_actionable`. Jokainen serve-polku kutsuu sita.
  (2) kutsupaikkaportti: `CALL_SITES` lukee lahdetiedoston AST:n ja vaatii
      etta nimetty funktio kutsuu lukijaa — ja /api/fantasy/xp:ssa ENNEN
      maskia, koska maski valitsee ilmaisen kymmenikon tasta kentasta.
  (3) vaiheinvariantti: sama funktio ajetaan synteettisilla vaiheilla
      (ennen deadlinea / kesken kierroksen / gradauksen jalkeen). Alkanut
      kierros on riveilla mutta EI summassa. Testi kaatuu jos se paatyy
      summaan — ja negatiivinen kontrolli todistaa etta vanha kaytos
      (summa koko listasta) todella kaatuisi sen.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.models import fpl_xp
from src.models.fpl_xp import (attach_horizon_total_actionable,
                               horizon_total_actionable)

ROOT = Path(__file__).resolve().parents[1]

HORIZON = [3, 4, 5, 6, 7, 8]

# (vaihe, meta.next_gameweek, meta.deadline_gameweek, odotettu summan alku)
#   before  GW3:n deadline edessa           -> summa alkaa GW3:sta
#   live    GW3 kesken, deadline on GW4:n   -> GW3 riveilla, EI summassa
#   after   GW3 gradattu, GW4 auki          -> summa alkaa GW4:sta
PHASES = [
    ("before", 3, 3, 3),
    ("live", 3, 4, 4),
    ("after", 4, 4, 4),
]

# Kaksi profiilia joiden JARJESTYS vaihtuu kun alkanut kierros putoaa pois:
#   A: iso luku alkaneessa kierroksessa, pieni sen jalkeen (raaka 20.0,
#      vaikutettava GW4:sta 10.0)
#   B: pieni luku alkaneessa, tasainen sen jalkeen (raaka 16.0,
#      vaikutettava GW4:sta 15.0)
# Raaka summa sanoo A > B, vaikutettava sanoo B > A. Vanha koodi (summa
# koko listasta) tuottaa siis VAARAN jarjestyksen eika vain vaaran luvun,
# joten fikstuuri erottaa mekanismit eika vain exit-koodia.
A_XP = {3: 10.0, 4: 2.0, 5: 2.0, 6: 2.0, 7: 2.0, 8: 2.0}
B_XP = {3: 1.0, 4: 3.0, 5: 3.0, 6: 3.0, 7: 3.0, 8: 3.0}


def _rows(xp_by_gw: dict[int, float]) -> list[dict]:
    return [{"gw": g, "opponents": [{"opp": "OPP", "venue": "H"}], "xp": x}
            for g, x in xp_by_gw.items()]


def _player(pid: int, name: str, xp_by_gw: dict[int, float]) -> dict:
    rows = _rows(xp_by_gw)
    return {"id": pid, "web_name": name, "full_name": name, "team": "Test",
            "team_short": "TST", "pos": "MID", "price": 6.0, "owned_pct": 5.0,
            "status": "a", "news": "", "xmins": 90.0, "data_basis": "pl_history",
            "minutes_confidence": "high",
            "xp_per_gw": round(sum(xp_by_gw.values()) / len(xp_by_gw), 2),
            # putken luku: koko listan summa (tasan se mika oli vaarin)
            "xp_horizon_total": round(sum(xp_by_gw.values()), 2),
            "gameweeks": rows}


def _payload(next_gw: int, deadline_gw: int, tag: str = "") -> dict:
    return {"meta": {"product": "test", "available": True, "phase": 1,
                     "season": "2026/27",
                     "generated_at": f"2026-09-17T00:00:00+00:00{tag}",
                     "next_gameweek": next_gw, "deadline_gameweek": deadline_gw,
                     "horizon_gw": len(HORIZON)},
            "players": [_player(1, "A", A_XP), _player(2, "B", B_XP)],
            "excluded": []}


def _expected(xp_by_gw: dict[int, float], frm: int) -> float:
    return round(sum(x for g, x in xp_by_gw.items() if g >= frm), 2)


# ---------------------------------------------------------------------------
# (3) VAIHEINVARIANTTI: yksi lukija, kolme vaihetta
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("phase,next_gw,dl_gw,frm", PHASES)
def test_started_gameweek_stays_on_the_row_but_never_in_the_sum(
        phase, next_gw, dl_gw, frm):
    data = attach_horizon_total_actionable(_payload(next_gw, dl_gw))
    a, b = data["players"]
    assert a["xp_horizon_total"] == _expected(A_XP, frm), phase
    assert b["xp_horizon_total"] == _expected(B_XP, frm), phase
    # rivit ENNALLAAN: alkanut kierros pysyy listalla (sivun tarkistusreitti)
    assert [g["gw"] for g in a["gameweeks"]] == HORIZON, phase
    assert [g["xp"] for g in a["gameweeks"]] == list(A_XP.values()), phase
    # meta-sopimus
    assert data["meta"]["horizon_gw"] == len(HORIZON), phase
    assert data["meta"]["horizon_total_from"] == frm, phase
    assert data["meta"]["horizon_total_gw"] == len([g for g in HORIZON if g >= frm]), phase
    if phase == "live":
        # alkanut kierros EI ole summassa: A:n 10 pistetta GW3:sta puuttuu
        assert a["xp_horizon_total"] == 10.0
        assert data["meta"]["horizon_total_gw"] == 5


@pytest.mark.parametrize("phase,next_gw,dl_gw,frm", PHASES)
def test_per_gw_average_uses_the_same_sum_and_the_same_window(
        phase, next_gw, dl_gw, frm):
    """`xp_per_gw` ON SUMMAN JOHDOS, EI ERI IKKUNA (18.9).

    Putki kirjoittaa sen kaavalla `total / len(horizon)` eli KOKO
    horisontin keskiarvona. Kentat tarjoillaan vierekkain ja
    /fpl/differentials selittaa niiden suhteen auki ("xP/GW is the
    N-gameweek projection divided by N"), joten kesken kierroksen sivu
    sanoi itseaan vastaan: sarake 6.41, summa 31.97, sivun oma lasku
    31.97/6 = 5.33 (mitattu tuotantoartefaktilla synteettisella
    deadline_gameweek=6, Haaland).
    """
    raw = _payload(next_gw, dl_gw)
    putken = {p["id"]: p["xp_per_gw"] for p in raw["players"]}
    data = attach_horizon_total_actionable(raw)
    n = data["meta"]["horizon_total_gw"]
    for p in data["players"]:
        assert p["xp_per_gw"] == round(p["xp_horizon_total"] / n, 2), (phase, p)
    if phase == "live":
        # A: putken ka. 20.0/6 = 3.33, rajattu 10.0/5 = 2.0
        # B: putken ka. 16.0/6 = 2.67, rajattu 15.0/5 = 3.0
        a, b = data["players"]
        assert (a["xp_per_gw"], b["xp_per_gw"]) == (2.0, 3.0), (a, b)
        assert putken[1] == 3.33 and putken[2] == 2.67
        # ...ja JARJESTYS kaantyy myos keskiarvolla (SPA sorttaa 'xP per GW'),
        # joten portti erottaa mekanismit eika vain lukua.
        assert putken[1] > putken[2] and a["xp_per_gw"] < b["xp_per_gw"]
    elif phase == "before":
        # ennen deadlinea KAIKKI kierrokset ovat summassa, joten luku on
        # bittitarkasti entinen — muutos ei saa liikuttaa mitaan turhaan
        assert all(p["xp_per_gw"] == putken[p["id"]] for p in data["players"]), phase
    else:
        # gradauksen jalkeen (GW3 pelattu, GW4 auki) ikkuna on sama 5
        # kierrosta kuin livena: luku on rajattu, ei putken
        assert n == 5 and data["players"][0]["xp_per_gw"] == 2.0, phase
        assert all(p["xp_per_gw"] != putken[p["id"]] for p in data["players"]), phase


def test_per_gw_does_not_trust_the_pipeline_field():
    """Payloadin oma `xp_per_gw` ei jaa voimaan: se johdetaan riveista."""
    data = _payload(3, 4)
    data["players"][0]["xp_per_gw"] = 99.9
    out = attach_horizon_total_actionable(data)
    assert out["players"][0]["xp_per_gw"] == 2.0


def test_per_gw_is_zero_when_no_gameweek_is_actionable():
    """Kausi ohi: summa on 0.0, joten keskiarvo ei saa jaada putken lukuun
    joka lukisi 'tuottaa yha pisteita'."""
    data = _payload(9, 9)          # kaikki HORIZON-kierrokset (3-8) menneita
    out = attach_horizon_total_actionable(data)
    assert out["meta"]["horizon_total_gw"] == 0
    for p in out["players"]:
        assert p["xp_horizon_total"] == 0.0 and p["xp_per_gw"] == 0.0


def test_the_guard_would_fail_on_the_old_behaviour():
    """NEGATIIVINEN KONTROLLI. Vanha koodi summasi koko listan; kesken
    kierroksen se tuottaa eri luvun JA eri jarjestyksen kuin vaadittu, joten
    ylla oleva testi ei voi olla vihrea vanhalla kaytoksella."""
    raw_a = round(sum(A_XP.values()), 2)
    raw_b = round(sum(B_XP.values()), 2)
    assert raw_a != _expected(A_XP, 4) and raw_b != _expected(B_XP, 4)
    assert raw_a > raw_b                       # raaka jarjestys: A ennen B
    assert _expected(B_XP, 4) > _expected(A_XP, 4)   # vaikutettava: B ennen A
    # ja lukija ilman kierrosta ON tasan vanha kaytos (vanha payload)
    assert horizon_total_actionable(_rows(A_XP), None) == raw_a


def test_reader_ignores_rows_without_a_number_and_keeps_rows_without_a_gw():
    rows = [{"gw": 3, "xp": 1.0}, {"gw": 4, "xp": None}, {"gw": 5, "xp": True},
            {"gw": 6, "xp": 2.005}, {"gw": "x", "xp": 0.5}, "roska",
            {"gw": 7}]
    # gw 3 putoaa (alle 4), None/bool ohitetaan, ei-kokonaisluku-gw sailyy
    # kuten load_xp_actionable sailyttaa sen; pyoristys kahteen desimaaliin
    assert horizon_total_actionable(rows, 4) == round(2.005 + 0.5, 2)
    assert horizon_total_actionable([], 4) == 0.0
    assert horizon_total_actionable(None, 4) == 0.0


def test_attach_is_idempotent_and_leaves_rows_without_gameweeks_alone():
    data = _payload(3, 4)
    data["players"].append({"id": 9, "web_name": "NoRows",
                            "xp_horizon_total": 7.7})
    once = attach_horizon_total_actionable(data)
    a1 = once["players"][0]["xp_horizon_total"]
    twice = attach_horizon_total_actionable(once)
    assert twice["players"][0]["xp_horizon_total"] == a1 == 10.0
    assert twice["meta"]["horizon_total_from"] == 4
    assert twice["players"][2]["xp_horizon_total"] == 7.7


def test_old_payload_without_gameweek_fields_sums_everything_and_says_so():
    """Puuttuva tieto ei ole todiste siita etta deadline olisi mennyt."""
    data = _payload(3, 4)
    data["meta"].pop("deadline_gameweek")
    data["meta"]["next_gameweek"] = None
    out = attach_horizon_total_actionable(data)
    assert out["players"][0]["xp_horizon_total"] == round(sum(A_XP.values()), 2)
    assert out["meta"]["horizon_total_from"] == HORIZON[0]
    assert out["meta"]["horizon_total_gw"] == len(HORIZON)


def test_empty_payload_carries_the_same_meta_keys():
    meta = fpl_xp.empty_xp()["meta"]
    assert meta["horizon_total_from"] is None and meta["horizon_total_gw"] == 0
    out = attach_horizon_total_actionable(fpl_xp.empty_xp())
    assert out["meta"]["horizon_total_from"] is None
    assert out["meta"]["horizon_total_gw"] == 0


@pytest.mark.parametrize("phase,next_gw,dl_gw,frm", PHASES)
def test_actionable_reader_field_agrees_with_its_own_rows(
        tmp_path, phase, next_gw, dl_gw, frm):
    """`load_xp_actionable` rajasi rivit mutta jatti putken summan voimaan:
    rajattu lukija palautti kentan joka ei vastannut omia rivejaan."""
    p = tmp_path / "xp.json"
    p.write_text(json.dumps(_payload(next_gw, dl_gw)), encoding="utf-8")
    out = fpl_xp.load_xp_actionable(p)
    a = out["players"][0]
    assert a["xp_horizon_total"] == round(sum(g["xp"] for g in a["gameweeks"]), 2)
    assert a["xp_horizon_total"] == _expected(A_XP, frm), phase
    assert out["meta"]["horizon_total_from"] == out["meta"]["trimmed_from"] == frm


# ---------------------------------------------------------------------------
# /api/fantasy/xp: serve-polku, maski, jarjestys, ETag
# ---------------------------------------------------------------------------

@pytest.fixture
def xp_client(monkeypatch, tmp_path):
    """TestClient jonka /api/fantasy/xp lukee synteettisen artefaktin."""
    import api.main as m

    def _serve(next_gw: int, deadline_gw: int, tag: str = "") -> TestClient:
        p = tmp_path / f"xp_{next_gw}_{deadline_gw}.json"
        p.write_text(json.dumps(_payload(next_gw, deadline_gw, tag)),
                     encoding="utf-8")
        monkeypatch.setitem(fpl_xp.XP_PATHS, "fpl", p)
        return TestClient(m.app)
    return _serve


@pytest.mark.parametrize("phase,next_gw,dl_gw,frm", PHASES)
def test_endpoint_serves_the_actionable_sum_and_the_meta_contract(
        xp_client, phase, next_gw, dl_gw, frm):
    r = xp_client(next_gw, dl_gw).get("/api/fantasy/xp")
    assert r.status_code == 200
    data = r.json()
    by = {p["web_name"]: p for p in data["players"]}
    assert by["A"]["xp_horizon_total"] == _expected(A_XP, frm), phase
    assert by["B"]["xp_horizon_total"] == _expected(B_XP, frm), phase
    assert [g["gw"] for g in by["A"]["gameweeks"]] == HORIZON, phase
    assert data["meta"]["horizon_gw"] == len(HORIZON)
    assert data["meta"]["horizon_total_from"] == frm, phase
    assert data["meta"]["horizon_total_gw"] == len([g for g in HORIZON if g >= frm])
    # jarjestys seuraa UUTTA arvoa: kesken kierroksen B ennen A:ta, muuten A
    names = [p["web_name"] for p in data["players"]]
    assert names == (["B", "A"] if frm > HORIZON[0] else ["A", "B"]), phase


def test_endpoint_etag_carries_schema_s9(xp_client):
    """Semantiikka vaihtui ilman uutta projektiota: `generated_at` on sama,
    joten vain skeemaversio erottaa vanhan valimuistivastauksen uudesta."""
    r = xp_client(3, 4).get("/api/fantasy/xp")
    assert "-s9" in r.headers["etag"], r.headers["etag"]
    assert "-s8" not in r.headers["etag"]


def test_free_teaser_is_picked_by_the_actionable_sum(xp_client, monkeypatch):
    """Maski valitsee ilmaisen kymmenikon `xp_horizon_total`illa. Jos summa
    laskettaisiin maskin JALKEEN, ilmainen lista olisi eri kuin premiumin
    jarjestys — ja ProductIntro (5.9 portti) nayttaisi listan jota ei ole
    millaan ilmaispinnalla."""
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    r = xp_client(3, 4, tag="-masked").get("/api/fantasy/xp")
    assert r.status_code == 200
    data = r.json()
    assert data["meta"]["masked"] is True
    assert [p["web_name"] for p in data["players"]] == ["B", "A"]
    assert data["players"][0]["xp_horizon_total"] == 15.0
    assert data["meta"]["horizon_total_from"] == 4


# ---------------------------------------------------------------------------
# Muut serve-polut: CSV, pooli (rate-team-perhe), player-stats, jakokortti
# ---------------------------------------------------------------------------

def test_csv_export_column_and_order_use_the_actionable_sum(monkeypatch):
    import api.fantasy_edge as fe
    import api.main as m

    monkeypatch.setattr(fe, "load_xp", lambda: _payload(3, 4, tag="-csv"))
    monkeypatch.setattr(fe, "get_bootstrap", lambda: {"elements": []})
    r = TestClient(m.app).get("/api/fantasy/xp.csv")
    assert r.status_code == 200
    lines = r.text.lstrip("﻿").splitlines()
    assert lines[0].startswith("sep=")
    header = lines[1].split(",")
    col = header.index("xp_horizon_total")
    name = header.index("web_name")
    rows = [ln.split(",") for ln in lines[2:] if ln.strip()]
    got = {r_[name]: float(r_[col]) for r_ in rows}
    assert got == {"A": 10.0, "B": 15.0}
    assert [r_[name] for r_ in rows] == ["B", "A"]


def test_projection_pool_carries_the_actionable_sum(monkeypatch):
    """rate-team, fit, model-squad, planner, captain, differentials,
    replacements, value, compare, edge, chip-ev, wildcard-plan, plan-chains,
    rival, h2h ja league saavat poolinsa `build_context`ista — yksi paikka."""
    from src.models import fpl_rate_team as rt

    boot = {"elements": [
        {"id": 1, "now_cost": 60, "team": 1, "element_type": 3,
         "web_name": "A", "status": "a", "selected_by_percent": "5.0"},
        {"id": 2, "now_cost": 60, "team": 2, "element_type": 3,
         "web_name": "B", "status": "a", "selected_by_percent": "5.0"},
    ]}
    monkeypatch.setattr(rt, "load_xp", lambda: _payload(3, 4, tag="-pool"))
    monkeypatch.setattr(rt, "get_bootstrap", lambda: boot)
    xp_data, _b, pool, by_id = rt.build_context()
    assert by_id[1]["xp_horizon_total"] == 10.0
    assert by_id[2]["xp_horizon_total"] == 15.0
    assert xp_data["meta"]["horizon_total_from"] == 4
    # rivit raakana poolissa: rate-teamin kuluvan kierroksen luku sailyy
    assert [g["gw"] for g in by_id[1]["gameweeks"]] == HORIZON


@pytest.mark.parametrize("phase,next_gw,dl_gw,frm", PHASES)
def test_player_stats_live_fields_bound_the_sum_even_on_raw_rows(
        phase, next_gw, dl_gw, frm):
    """Tuotannossa rivit tulevat jo rajattuina (`load_xp_actionable`), mutta
    summa ei saa nojata siihen: sama funktio rajaa myos raakalistan."""
    from src.models.fpl_player_stats import _live_fields
    nxt, horizon = _live_fields(_player(1, "A", A_XP), frm)
    assert horizon == _expected(A_XP, frm), phase
    assert nxt == A_XP[frm], phase
    assert _live_fields({"gameweeks": [{"gw": 4, "xp": None}]}, 4) == (None, None)


def test_share_card_reads_the_same_sum_and_names_the_window(monkeypatch, tmp_path):
    """Kortti on julkinen kuva ja lukee artefaktia suoraan, ei API:a."""
    from scripts import gen_share_card as gsc

    (tmp_path / "fpl_xp_projections.json").write_text(
        json.dumps(_payload(3, 4)), encoding="utf-8")
    monkeypatch.setattr(gsc, "DATA", tmp_path)
    data = gsc._xp_payload()
    by = {p["web_name"]: p for p in data["players"]}
    assert by["A"]["xp_horizon_total"] == 10.0 and by["B"]["xp_horizon_total"] == 15.0
    assert gsc._horizon_n(data) == 5          # ei len(gameweeks) == 6
    spec = gsc.card_value(SimpleNamespace(top=10, min_mins=60))
    assert spec["title"] == "BEST VALUE, NEXT 5 GW"
    assert [r["name"] for r in spec["rows"]] == ["B", "A"]
    assert spec["rows"][0]["mid"].endswith("15.0 xP")
    # vanha payload ilman meta-kenttaa putoaa entiseen laskutapaan
    assert gsc._horizon_n({"players": [{"gameweeks": [1, 2, 3]}]}) == 3


# ---------------------------------------------------------------------------
# (2) KUTSUPAIKKAPORTTI: lahdetiedosto, ei ajonaikainen exit-koodi
# ---------------------------------------------------------------------------

# (tiedosto, funktio, vaadittu kutsu, kutsu jota ENNEN sen on oltava)
CALL_SITES = [
    ("api/main.py", "fantasy_xp",
     "attach_horizon_total_actionable", "mask_xp_payload"),
    ("api/fantasy_edge.py", "fantasy_xp_csv",
     "attach_horizon_total_actionable", "sorted"),
    ("src/models/fpl_rate_team.py", "build_context",
     "attach_horizon_total_actionable", "_projection_pool"),
    ("src/models/fpl_player_stats.py", "_live_fields",
     "horizon_total_actionable", None),
    ("src/models/fpl_xp.py", "load_xp_actionable",
     "attach_horizon_total_actionable", None),
    ("scripts/gen_share_card.py", "_xp_payload",
     "attach_horizon_total_actionable", None),
    # 17.9 (lisays raportin jalkeen): artefaktista rakennetut JULKISET
    # sivut ja reel. Ilman naita club-best-sivu olisi kesken kierroksen
    # kokonaisen kierroksen verran eri lukua kuin kortti jonka alatunniste
    # ohjaa sinne. Lukija ajetaan latauspisteessa ENNEN ensimmaista
    # renderia, jotta yksikaan sivu ei voi lukea putken summaa.
    ("scripts/build_fpl_longtail.py", "main",
     "attach_horizon_total_actionable", "render_captain"),
    ("scripts/build_fpl_page.py", "main",
     "attach_horizon_total_actionable", "render_page"),
    ("scripts/gen_reel.py", "card_value",
     "attach_horizon_total_actionable", "sorted"),
    # 18.9 (adversariaalinen tarkistus): selitysten VALINTA. Maksumuuri
    # lupaa "top 150 by Total xP", ja valinta tehtiin raa'asta artefaktin
    # summasta samalla kun nakyva jarjestys tulee rajatusta summasta.
    # Lukija on `select_players`in sisalla ENNEN lajittelua, jotta
    # yksikaan kutsupaikka (eika testi) voi valita raa'alla luvulla.
    ("scripts/build_fpl_why.py", "select_players",
     "attach_horizon_total_actionable", "sort"),
    ("scripts/build_fpl_why.py", "main",
     "attach_horizon_total_actionable", "select_players"),
]


def _calls_in(path: str, func: str) -> dict[str, int]:
    """{kutsutun nimi: ensimmainen rivi} nimetyn moduulitason funktion sisalla."""
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    fn = next((n for n in tree.body
               if isinstance(n, ast.FunctionDef) and n.name == func), None)
    assert fn is not None, f"{path}: funktiota {func} ei loydy"
    out: dict[str, int] = {}
    for n in ast.walk(fn):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        name = f.id if isinstance(f, ast.Name) else (
            f.attr if isinstance(f, ast.Attribute) else None)
        if name and name not in out:
            out[name] = n.lineno
    return out


@pytest.mark.parametrize("path,func,needed,before", CALL_SITES)
def test_every_serve_path_calls_the_one_reader(path, func, needed, before):
    calls = _calls_in(path, func)
    assert needed in calls, (
        f"{path}:{func} ei kutsu {needed}() — se palauttaisi putken summan "
        "joka sisaltaa jo alkaneen kierroksen")
    if before is not None:
        assert before in calls, (path, func, before)
        assert calls[needed] < calls[before], (
            f"{path}:{func}: {needed}() on kutsuttava ENNEN {before}()a "
            f"(rivit {calls[needed]} vs {calls[before]})")


def test_xp_endpoint_applies_the_reader_after_loading_and_before_masking():
    calls = _calls_in("api/main.py", "fantasy_xp")
    assert calls["load_xp"] < calls["attach_horizon_total_actionable"] < calls["mask_xp_payload"]


def test_share_card_applies_the_reader_on_both_source_paths():
    """`_xp_payload` lukee artefaktin TAI API:n. Kumpikin polku on
    kaytava lukijan lapi: API voi olla vanha versio, ja artefakti on aina
    putken raaka summa."""
    tree = ast.parse((ROOT / "scripts" / "gen_share_card.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "_xp_payload")
    n_calls = sum(1 for n in ast.walk(fn)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == "attach_horizon_total_actionable")
    assert n_calls >= 2, n_calls


def test_call_site_scanner_sees_through_a_dummy():
    """Negatiivinen kontrolli skannerille: ilman tata portti voisi olla
    vihrea siksi ettei se loyda kutsuja lainkaan."""
    src = "def f():\n    x = load_xp()\n    return mask_xp_payload(x)\n"
    tree = ast.parse(src)
    fn = tree.body[0]
    names = {n.func.id for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert names == {"load_xp", "mask_xp_payload"}
    assert "attach_horizon_total_actionable" not in names


# ---------------------------------------------------------------------------
# KIRJOITTAJA KAYTTAA LUKIJAN MAARITELMAA (17.9, mitattu)
# ---------------------------------------------------------------------------
#
# Putki kirjoitti `xp_horizon_total = round(total, 2)` = PYORISTAMATTOMIEN
# per-GW-lukujen summa, ja lukija summaa JULKAISTUT (pyoristetyt) rivit.
# Mitattu 17.9 artefaktista jossa ei ollut yhtaan alkanutta kierrosta
# (next_gameweek == deadline_gameweek == 5): 234/482 rivia erosi (max 0.02),
# 28 rivia yhden desimaalin tarkkuudella, API:n uudelleenlajittelu siirsi
# rivin 50, ja club-best-kortti sanoi kahdeksalla rivilla eri eron kuin sivu
# jolle sen alatunniste ohjaa. Eli API, CSV ja kortti olisivat sanoneet eri
# luvun kuin artefaktista rakennetut sivut JO ENNEN DEADLINEA.
#
# Korjaus on yksi maaritelma: putki kutsuu samaa funktiota. Portti lukee
# kirjoittajan LAHTEEN (dict-literaalin arvon), ei artefaktia — artefakti
# paivittyy vasta seuraavassa CI-ajossa, ja dataan sidottu testi olisi
# punainen siihen asti ilman etta mikaan on rikki.

WRITERS = [
    ("scripts/build_fpl_xp.py", "main"),
    ("scripts/build_spl_xp.py", "main"),
]


def _horizon_total_writes(tree_or_path, func: str | None) -> list:
    """Dict-literaalien `"xp_horizon_total"`-avainten ARVOSOLMUT nimetyn
    funktion sisalla (tai koko puussa kun func on None)."""
    if isinstance(tree_or_path, str):
        tree = ast.parse((ROOT / tree_or_path).read_text(encoding="utf-8"))
        scope = next((n for n in tree.body
                      if isinstance(n, ast.FunctionDef) and n.name == func), None)
        assert scope is not None, (tree_or_path, func)
    else:
        scope = tree_or_path
    out = []
    for n in ast.walk(scope):
        if not isinstance(n, ast.Dict):
            continue
        for k, v in zip(n.keys, n.values):
            if isinstance(k, ast.Constant) and k.value == "xp_horizon_total":
                out.append(v)
    return out


def _is_reader_call(v) -> bool:
    if not isinstance(v, ast.Call):
        return False
    f = v.func
    name = f.id if isinstance(f, ast.Name) else (
        f.attr if isinstance(f, ast.Attribute) else None)
    return name == "horizon_total_actionable"


@pytest.mark.parametrize("path,func", WRITERS)
def test_the_writer_uses_the_readers_definition(path, func):
    writes = _horizon_total_writes(path, func)
    assert writes, f"{path}:{func} ei kirjoita xp_horizon_totalia dict-literaalina"
    for v in writes:
        assert _is_reader_call(v), (
            f"{path}:{func}: xp_horizon_total = {ast.unparse(v)} — putken on "
            "kutsuttava horizon_total_actionable(rows, None), muuten artefaktin "
            "summa eroaa API:n, CSV:n ja kortin rivisummasta jo ennen deadlinea")
        # Koko listan summa (`None`): artefakti kantaa tarkoituksella myos
        # alkaneen kierroksen, rajaus tehdaan serve-timessa.
        assert len(v.args) == 2 and isinstance(v.args[1], ast.Constant) \
            and v.args[1].value is None, ast.unparse(v)


def test_writer_scanner_flags_the_old_formula():
    """Negatiivinen kontrolli: vanha `round(total, 2)` EI lapaise."""
    tree = ast.parse('row = {"xp_horizon_total": round(total, 2), "gameweeks": gws}')
    writes = _horizon_total_writes(tree, None)
    assert len(writes) == 1 and not _is_reader_call(writes[0])
    tree2 = ast.parse('row = {"xp_horizon_total": xp.horizon_total_actionable(gws, None)}')
    assert _is_reader_call(_horizon_total_writes(tree2, None)[0])


def test_definition_is_the_sum_of_the_published_rows_not_of_the_raw_values():
    """Erotteleva fikstuuri: vanha kaava ja lukija antavat ERI luvun samasta
    datasta, joten sopimus "sama funktio" ei ole pelkka exit-koodi."""
    raw = [1.004, 1.004, 1.004]                     # putken sisaiset luvut
    rows = [{"gw": 5 + i, "xp": round(x, 2)} for i, x in enumerate(raw)]
    assert round(sum(raw), 2) == 3.01               # vanha kirjoittaja
    assert horizon_total_actionable(rows, None) == 3.0   # julkaistut rivit
    assert horizon_total_actionable(rows, None) != round(sum(raw), 2)


# ---------------------------------------------------------------------------
# Artefaktista rakennetut julkiset pinnat: etusivun taulukko, reel
# ---------------------------------------------------------------------------

def test_front_page_table_footer_counts_the_summed_rounds():
    """"next N gameweeks" = summassa olevien kierrosten maara, ei sarakkeiden.
    Vanha payload ilman `horizon_total_gw`:ta putoaa `horizon_gw`:hen."""
    from scripts.build_fpl_page import xp_table_rows
    p = _player(1, "A", A_XP)
    html = xp_table_rows({"meta": {"horizon_gw": 6, "horizon_total_gw": 5},
                          "players": [p]}, n=1)
    assert "next 5 gameweeks" in html and "next 6 gameweeks" not in html
    html2 = xp_table_rows({"meta": {"horizon_gw": 6}, "players": [p]}, n=1)
    assert "next 6 gameweeks" in html2


def test_reel_value_card_reads_the_same_sum(monkeypatch, tmp_path):
    """Reel on julkinen video ja lukee artefaktia suoraan."""
    from scripts import gen_reel as gr
    data = _payload(3, 4)
    # tayte, jotta `card_value` ei kaadu liian pieneen avaajapooliin
    data["players"] += [_player(100 + i, f"P{i}", {g: 1.0 for g in HORIZON})
                        for i in range(gr.N_ROWS)]
    (tmp_path / "xp.json").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(gr, "XP", tmp_path / "xp.json")
    spec = gr.card_value()
    names = [r["name"] for r in spec["rows"]]
    # Vaikutettava summa: B 15.0/6.0 = 2.50 ennen A:ta 10.0/6.0 = 1.67.
    # Raaka summa olisi antanut A:n (20.0/6.0 = 3.33) ennen B:ta (16.0/6.0 =
    # 2.67) — eri karki JA eri luku, joten vanha koodi ei lapaise tata.
    assert names[:2] == ["B", "A"], names
    assert spec["rows"][0]["val"] == f"{15.0 / 6.0:.2f}", spec["rows"][0]
    assert spec["rows"][1]["val"] == f"{10.0 / 6.0:.2f}", spec["rows"][1]
    assert f"{20.0 / 6.0:.2f}" not in {r["val"] for r in spec["rows"]}
