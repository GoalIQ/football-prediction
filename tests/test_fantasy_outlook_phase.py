"""/api/fantasy teams[].fixtures alkaa kierroksesta johon voi viela vaikuttaa (2.11.2026).

Vika: rajaus oli vain ylhaalta (`gw <= gw_cut`). Kesken kierroksen
(next_gameweek 9, deadline_gameweek 10) sovelluksen ja webin "Clean sheet
outlook" alkoi GW9:sta ja naytti CS-%:n jo pelatuille otteluille. Loytyi kun
kauppakuvaa otettiin: ARS@LIV 38 % oli pelattu 1.11 (0-1).

Saanto 6a kohta 3: invariantti mitataan synteettisilla vaiheilla, ei vain
nykyhetkessa (ennen deadlinea, kesken kierroksen, gradauksen jalkeen).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import src.models.fpl_phase0 as phase0
from api.main import app

client = TestClient(app)


def _payload(meta: dict) -> dict:
    teams = [{"short": t, "fixtures": [{"gw": gw, "opp": "X", "cs_pct": 30.0}
                                      for gw in range(8, 20)]}
             for t in ("ARS", "LIV")]
    return {"meta": {"available": True, "horizon_max": 12, **meta}, "teams": teams}


VAIHEET = [
    # (nimi, meta, ensimmainen sallittu kierros)
    ("ennen deadlinea", {"next_gameweek": 10, "deadline_gameweek": 10}, 10),
    ("kesken kierroksen", {"next_gameweek": 9, "deadline_gameweek": 10}, 10),
    ("gradauksen jalkeen", {"next_gameweek": 10, "deadline_gameweek": 10,
                            "completed_gameweeks": list(range(1, 10))}, 10),
    ("vanha payload ilman deadline_gameweekia", {"next_gameweek": 9}, 9),
]


@pytest.mark.parametrize("nimi,meta,eka", VAIHEET, ids=[v[0] for v in VAIHEET])
@pytest.mark.parametrize("horizon", [None, "1", "all"])
def test_outlook_ei_sisalla_lukittuja_kierroksia(monkeypatch, nimi, meta, eka, horizon):
    monkeypatch.setattr(phase0, "load_phase0", lambda path=None: _payload(meta))
    r = client.get("/api/fantasy", params={"horizon": horizon} if horizon else {})
    assert r.status_code == 200, r.text
    gws = sorted({f["gw"] for t in r.json()["teams"] for f in t["fixtures"]})
    assert gws, f"{nimi}: vastaus tyhja, testi ei mittaisi mitaan"
    assert gws[0] == eka, f"{nimi}: outlook alkaa GW{gws[0]}, pitaisi GW{eka}"
    if horizon == "1":
        assert gws == [eka]
    # horizon_gw kertoo mita vastauksessa ON
    assert r.json()["meta"]["horizon_gw"] == len(gws)


def _tiered(meta: dict, near_from: int, near_n: int = 6) -> dict:
    """Kuten tuotannon artefakti: lahiraja (tier) on ankkuroitu next_gameweekiin,
    kaukokierroksilla ei ole cs_pct:ta."""
    def row(gw):
        near = near_from <= gw < near_from + near_n
        return {"gw": gw, "opp": "X", "tier": "near" if near else "far",
                **({"cs_pct": 30.0} if near else {})}
    teams = [{"short": t, "fixtures": [row(gw) for gw in range(near_from, 20)]}
             for t in ("ARS", "LIV")]
    return {"meta": {"available": True, "horizon_max": 12, "near_horizon_gw": near_n, **meta},
            "teams": teams}


@pytest.mark.parametrize("nimi,meta,near_from,odotus", [
    # 2.11 tuotanto: next 9, deadline 10 -> artefaktin lahi GW9-14, vastauksessa GW10-14
    ("kesken kierroksen", {"next_gameweek": 9, "deadline_gameweek": 10}, 9, 5),
    ("ennen deadlinea", {"next_gameweek": 10, "deadline_gameweek": 10}, 10, 6),
    ("gradauksen jalkeen", {"next_gameweek": 10, "deadline_gameweek": 10}, 10, 6),
])
def test_lahiraja_ei_lupaa_kaukokierrosta(monkeypatch, nimi, meta, near_from, odotus):
    """Sovellus laskee oletusvalin: gwFrom + near_horizon_gw - 1. Jos meta lupaa
    enemman lahikierroksia kuin vastauksessa on, oletusnakyma ottaa mukaan
    kaukokierroksen ilman CS-%:ia ('6 games, no clean sheet % yet')."""
    monkeypatch.setattr(phase0, "load_phase0", lambda path=None: _tiered(meta, near_from))
    d = client.get("/api/fantasy").json()
    near = d["meta"]["near_horizon_gw"]
    assert near == odotus, f"{nimi}: near_horizon_gw {near}, pitaisi {odotus}"
    eka = min(f["gw"] for t in d["teams"] for f in t["fixtures"])
    oletusvali = range(eka, eka + near)
    for t in d["teams"]:
        for f in t["fixtures"]:
            if f["gw"] in oletusvali:
                assert f["tier"] == "near" and "cs_pct" in f, (nimi, f)
