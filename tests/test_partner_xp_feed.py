"""Portti: kumppanisyote /api/partner/xp (26.9.2026, FPL Demon).

Sovittu X DM:ssa: FPL id + seuraavat 5 kierrosta, EI minuutteja eika muita
mallin kenttia. Portti pitaa huolen etta
  (1) ilman ymparistoa reitti on pois paalta (403), vaaralla avaimella 401,
  (2) vastauksessa on VAIN sallitut kentat, mitattuna oikealla projektiolla,
  (3) kierrosta jonka deadline on mennyt ei tarjota (load_xp_actionable),
  (4) reitti on kytketty appiin ja lukee avaimen headerista, ei URL:sta.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from api import partner_feed as pf
from src.models import fpl_xp

ROOT = Path(__file__).resolve().parents[1]
KEY = "k" * 30
OTHER = "z" * 30


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("PARTNER_XP_KEYS", f"fpldemon:{KEY},other:{OTHER}")


def test_ilman_ymparistoa_reitti_on_pois_paalta(client, monkeypatch):
    monkeypatch.delenv("PARTNER_XP_KEYS", raising=False)
    r = client.get("/api/partner/xp", headers={"X-Partner-Key": KEY})
    assert r.status_code == 403


def test_liian_lyhyt_avain_ei_kelpaa_ymparistossa(client, monkeypatch):
    monkeypatch.setenv("PARTNER_XP_KEYS", "fpldemon:short")
    assert client.get("/api/partner/xp", headers={"X-Partner-Key": "short"}).status_code == 403


def test_vaara_tai_puuttuva_avain_on_401(client, keys):
    assert client.get("/api/partner/xp").status_code == 401
    assert client.get("/api/partner/xp", headers={"X-Partner-Key": "x" * 30}).status_code == 401
    # Avain URL:ssa ei kelpaa: se paatyisi lokeihin.
    assert client.get(f"/api/partner/xp?key={KEY}").status_code == 401


def test_oikea_avain_vain_sallitut_kentat(client, keys):
    r = client.get("/api/partner/xp", headers={"X-Partner-Key": KEY})
    assert r.status_code == 200, r.text
    d = r.json()
    assert set(d) == pf.TOP_FIELDS
    assert d["attribution"] == "Projected points powered by GoalIQ"
    assert d["link"] == ("https://pro.goaliq.app/players/player-xp"
                         "?utm_source=fpldemon&utm_medium=partner")
    assert 1 <= len(d["gameweeks"]) <= pf.PARTNER_XP_HORIZON
    assert d["players"], "syote tyhja vaikka projektio on committattu"
    for p in d["players"]:
        assert set(p) == pf.PLAYER_FIELDS, p
        assert isinstance(p["id"], int)
        assert set(p["xp"]) <= {str(g) for g in d["gameweeks"]}
        for v in p["xp"].values():
            assert isinstance(v, (int, float)) and round(v, 1) == v
    assert r.headers["cache-control"] == "private, max-age=300"
    # Toinen kumppani saa oman linkkinsa (attribuutio erottuu).
    r2 = client.get("/api/partner/xp", headers={"X-Partner-Key": OTHER})
    assert "utm_source=other" in r2.json()["link"]


def test_syotteessa_ei_ole_minuutteja_eika_mallin_kenttia():
    # Mitattu committatulla projektiolla: pelaajarivilla on kymmenia kenttia
    # (xmins, p_start, components ...). Mikaan niista ei saa paatya syotteeseen.
    data = fpl_xp.load_xp_actionable()
    raaka = set().union(*(set(p) for p in data["players"]))
    assert {"xmins", "p_start", "components"} <= raaka
    out = pf.build_partner_xp(data, "fpldemon")
    teksti = json.dumps(out["players"])
    for kentta in raaka - {"id"}:
        assert f'"{kentta}"' not in teksti, kentta


def _xp_file(tmp_path: Path, deadline_gw: int) -> Path:
    players = [{"id": i, "web_name": f"P{i}", "xmins": 80,
                "gameweeks": [{"gw": gw, "xp": 2.0 + gw / 100, "opponents": []}
                              for gw in range(6, 13)]}
               for i in (1, 2)]
    path = tmp_path / "xp.json"
    path.write_text(json.dumps({
        "meta": {"available": True, "generated_at": "2026-09-26T09:00:00+00:00",
                 "deadline_gameweek": deadline_gw, "next_gameweek": deadline_gw},
        "players": players}), encoding="utf-8")
    return path


@pytest.mark.parametrize("deadline_gw,odotus", [
    (6, [6, 7, 8, 9, 10]),     # ennen GW6:n deadlinea
    (7, [7, 8, 9, 10, 11]),    # GW6:n deadline mennyt, kierros kesken/pelattu
    (11, [11, 12]),            # kauden loppu: horisontti lyhenee, ei keksita
])
def test_mennytta_kierrosta_ei_tarjota_missaan_vaiheessa(tmp_path, deadline_gw, odotus):
    data = fpl_xp.load_xp_actionable(_xp_file(tmp_path, deadline_gw))
    out = pf.build_partner_xp(data, "fpldemon")
    assert out["gameweeks"] == odotus
    assert all(set(p["xp"]) == {str(g) for g in odotus} for p in out["players"])


def test_reitti_kayttaa_actionable_lukijaa(client, keys, monkeypatch, tmp_path):
    # Kutsupaikka, ei vain funktio: reitti lukee load_xp_actionablen kautta.
    path = _xp_file(tmp_path, 7)
    monkeypatch.setattr(pf, "load_xp_actionable",
                        lambda: fpl_xp.load_xp_actionable(path))
    d = client.get("/api/partner/xp", headers={"X-Partner-Key": KEY}).json()
    assert d["gameweeks"] == [7, 8, 9, 10, 11]
    src = (ROOT / "api/partner_feed.py").read_text(encoding="utf-8")
    assert "load_xp_actionable()" in src and "load_xp()" not in src


def test_projektio_puuttuu_503(client, keys, monkeypatch):
    monkeypatch.setattr(pf, "load_xp_actionable", lambda: fpl_xp.empty_xp())
    assert client.get("/api/partner/xp", headers={"X-Partner-Key": KEY}).status_code == 503
