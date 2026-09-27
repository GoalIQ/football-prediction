# -*- coding: utf-8 -*-
"""TC-TARGET-PLAYER (27.9.2026): Triple Captain -rivi nimeaa kenen luvusta se
syntyy, ja pelaajavalitsin antaa rungon jokaiselle pelaajalle oman parhaan
TC-kierroksen.

TAUSTA (Villen havainto 2.9): kapteenin vaihto kentalla Fernandesista
Haalandiin ei muuttanut TC-ehdotusta (GW7 +9.3) mitenkaan. Laskenta oli
suunniteltu niin (tc_ev = XI:n paras GW-xP, ei oma kapteeni), mutta ruutu ei
sanonut sita, joten kayttaja luki sen rikkinaiseksi.

Invariantit:
  - pelaajatason rivin tc_ev == tc_playerin saman kierroksen xP (nimi ja
    luku samasta lahteesta, ei kahta erillista laskentaa)
  - joukkuetason (skaalattu) rivi ei nimea ketaan: se ei ole kenenkaan luku
  - best.tc.player on parhaan rivin pelaaja
  - valitsin ei tarjoa kierrosta jolla TC:ta ei voi pelata
  - ilmaispinta ei saa nimea eika valitsinta (mallin kapteenivalinta)
"""
from __future__ import annotations

from fastapi.testclient import TestClient

import api.fantasy_edge as fe
import api.main as m
from src.models.fpl_chips import chip_state

client = TestClient(m.app)


def _payload(premium: bool = True) -> dict:
    orig = fe.is_premium_request
    fe.is_premium_request = lambda r: premium
    try:
        r = client.get("/api/fantasy/chip-ev")
    finally:
        fe.is_premium_request = orig
    assert r.status_code == 200, r.text
    return r.json()


def test_tc_rivin_luku_on_nimetyn_pelaajan_luku():
    d = _payload()
    tarkat = [w for w in d["windows"] if w["basis"] == "player_xp"]
    if not tarkat:
        return  # esikausi / data puuttuu
    by_id = {c["id"]: {r["gw"]: r["xp"] for r in c["by_gw"]} for c in d["tc_candidates"]}
    tarkistettu = 0
    for w in tarkat:
        p = w["tc_player"]
        assert p and p.get("web_name"), w
        assert p["id"] in by_id, f"TC-pelaaja {p} ei ole rungossa"
        if w["gw"] in by_id[p["id"]]:
            assert abs(by_id[p["id"]][w["gw"]] - w["tc_ev"]) < 0.011, (w, p)
            tarkistettu += 1
    # Kontrolli: vertailu ei saa olla vihrea siksi etta yhtaan kierrosta ei verrattu.
    assert tarkistettu > 0 or not d["tc_candidates"]


def test_skaalattu_rivi_ei_nimea_ketaan():
    for w in _payload()["windows"]:
        if w["basis"] != "player_xp":
            assert w["tc_player"] is None, w


def test_paras_tc_nimeaa_parhaan_rivin_pelaajan():
    d = _payload()
    b = (d.get("best") or {}).get("tc")
    if not b:
        return
    rivi = next(w for w in d["windows"] if w["gw"] == b["gw"] and w["basis"] == "player_xp")
    assert b["player"] == rivi["tc_player"]


def test_valitsin_jarjestyksessa_ja_paras_on_maksimi():
    c = _payload()["tc_candidates"]
    if not c:
        return
    assert [r["best_xp"] for r in c] == sorted((r["best_xp"] for r in c), reverse=True)
    for r in c:
        top = max(r["by_gw"], key=lambda x: x["xp"])
        assert r["best_xp"] == top["xp"] and r["best_gw"] == top["gw"], r
        assert r["pos"] in {"GKP", "DEF", "MID", "FWD"}


def test_ilmaispinta_ei_saa_nimea_eika_valitsinta():
    d = _payload(premium=False)
    assert d["meta"].get("masked") is True
    assert all(w.get("tc_player") is None for w in d["windows"])
    assert d["tc_candidates"] == []
    # Kontrolli: premium saa ne (muuten testi olisi vihrea tyhjalla).
    p = _payload()
    if any(w["basis"] == "player_xp" for w in p["windows"]):
        assert any(w.get("tc_player") for w in p["windows"])


BOOT = {"chips": [
    {"name": "3xc", "start_event": 1, "stop_event": 19},
    {"name": "3xc", "start_event": 20, "stop_event": 38},
]}


def _pelaaja(pid, name, xps):
    return {"id": pid, "web_name": name, "team_short": "ABC", "element_type": 4,
            "gameweeks": [{"gw": g, "xp": x} for g, x in xps.items()]}


def test_valitsin_ei_tarjoa_kierrosta_jolla_tc_on_jo_pelattu():
    squad = [_pelaaja(1, "Haaland", {18: 9.0, 19: 5.0, 20: 6.0}),
             _pelaaja(2, "Watkins", {18: 4.0, 19: 7.0, 20: 3.0})]
    # TC pelattu GW3:ssa: ensimmainen puolikas (GW1-19) on kaytetty.
    st = chip_state(BOOT, {"chips": [{"name": "3xc", "event": 3}]}, 18)
    out = fe._tc_candidates(squad, [18, 19, 20], st)
    assert {r["gw"] for c in out for r in c["by_gw"]} == {20}
    assert out[0]["web_name"] == "Haaland" and out[0]["best_gw"] == 20
    # Negatiivinen kontrolli: ilman pelattua TC:ta paras on GW18.
    st2 = chip_state(BOOT, {"chips": []}, 18)
    out2 = fe._tc_candidates(squad, [18, 19, 20], st2)
    assert out2[0]["best_gw"] == 18 and out2[0]["best_xp"] == 9.0
    assert [c["web_name"] for c in out2] == ["Haaland", "Watkins"]
