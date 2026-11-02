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
