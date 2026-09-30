"""Portti: kumppanisyote /api/partner/xp (26.9.2026, FPL Demon).

Sovittu X DM:ssa: FPL id + seuraavat 5 kierrosta, ei muita mallin kenttia.
Minuutit lisattiin 29.9 (Demonin pyynto, Villen DM "Yes on minutes"): `xmins`
per kierros samoille kierroksille kuin `xp`. Portti pitaa huolen etta
  (1) ilman ymparistoa reitti on pois paalta (403), vaaralla avaimella 401,
  (2) vastauksessa on VAIN sallitut kentat, mitattuna oikealla projektiolla,
  (3) kierrosta jonka deadline on mennyt ei tarjota (load_xp_actionable),
  (4) reitti on kytketty appiin ja lukee avaimen headerista, ei URL:sta,
  (5) minuutit ovat kierroksen omat (builderin xm_g, sama jolla xp laskettiin),
      eivat rivin otsikkominuutit kopioituna jokaiselle kierrokselle.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from api import partner_feed as pf
from src.models import fpl_xp

ROOT = Path(__file__).resolve().parents[1]
ROW_XMINS = 80.0  # rivin otsikkominuutit fikstuurissa: ei saa esiintya kierrosarvona
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
        # Minuutit: vain samoilta kierroksilta kuin xp (tyhja kun committattu
        # projektio on vanhempi kuin kentta).
        assert isinstance(p["xmins"], dict) and set(p["xmins"]) <= set(p["xp"])
        for v in p["xmins"].values():
            assert isinstance(v, (int, float)) and round(v, 1) == v and 0 <= v <= 180
    assert r.headers["cache-control"] == "private, max-age=300"
    # Toinen kumppani saa oman linkkinsa (attribuutio erottuu).
    r2 = client.get("/api/partner/xp", headers={"X-Partner-Key": OTHER})
    assert "utm_source=other" in r2.json()["link"]


def test_syotteessa_ei_muita_mallin_kenttia():
    # Mitattu committatulla projektiolla: pelaajarivilla on kymmenia kenttia
    # (p_start, components ...). Mikaan niista ei saa paatya syotteeseen.
    # `xmins` on sovittu 29.9, mutta kierroskohtaisena dictina, ei rivin
    # skalaarina (se testataan alla fikstuurilla).
    data = fpl_xp.load_xp_actionable()
    raaka = set().union(*(set(p) for p in data["players"]))
    assert {"xmins", "p_start", "components"} <= raaka
    out = pf.build_partner_xp(data, "fpldemon")
    teksti = json.dumps(out["players"])
    for kentta in raaka - {"id", "xmins"}:
        assert f'"{kentta}"' not in teksti, kentta
    assert all(isinstance(p["xmins"], dict) for p in out["players"])


def _gw_row(gw: int) -> dict:
    """GW9 = blank (ei ottelua), GW10 = tupla. Muut yksi ottelu."""
    if gw == 9:
        return {"gw": gw, "xp": 0.0, "xmins": 0.0, "opponents": []}
    if gw == 10:
        return {"gw": gw, "xp": 7.1, "xmins": 170.04, "opponents": ["A", "B"]}
    return {"gw": gw, "xp": 2.0 + gw / 100, "xmins": 70.0 + gw + 0.26,
            "opponents": ["A"]}


def _xp_file(tmp_path: Path, deadline_gw: int, with_xmins: bool = True) -> Path:
    def row(gw):
        r = _gw_row(gw)
        if not with_xmins:
            r.pop("xmins")
        return r
    players = [{"id": i, "web_name": f"P{i}", "xmins": ROW_XMINS,
                "gameweeks": [row(gw) for gw in range(6, 13)]}
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


@pytest.mark.parametrize("deadline_gw", [6, 7, 11])
def test_minuutit_ovat_kierroksen_omat_joka_vaiheessa(tmp_path, deadline_gw):
    data = fpl_xp.load_xp_actionable(_xp_file(tmp_path, deadline_gw))
    out = pf.build_partner_xp(data, "fpldemon")
    for p in out["players"]:
        assert set(p["xmins"]) == set(p["xp"])
        for gw, v in p["xmins"].items():
            assert v == round(_gw_row(int(gw))["xmins"], 1)
        assert ROW_XMINS not in p["xmins"].values()
    first = out["players"][0]["xmins"]
    if deadline_gw <= 9:
        assert first["9"] == 0.0      # blank: ei ottelua
    if deadline_gw <= 10:
        assert first["10"] == 170.0   # tupla: kahden ottelun summa


def test_vanha_projektio_ilman_kierrosminuutteja_antaa_tyhjan(tmp_path):
    # Ei arvausta: rivin otsikkominuutteja ei kopioida kierroksille.
    data = fpl_xp.load_xp_actionable(_xp_file(tmp_path, 6, with_xmins=False))
    out = pf.build_partner_xp(data, "fpldemon")
    assert out["players"] and all(p["xmins"] == {} for p in out["players"])


def _horizon_loop() -> ast.For:
    tree = ast.parse((ROOT / "scripts" / "build_fpl_xp.py").read_text(encoding="utf-8"))
    # Silmukka joka laskee kierroksen xP:n (for g in horizon + xp_components).
    loops = [n for n in ast.walk(tree) if isinstance(n, ast.For)
             and isinstance(n.target, ast.Name) and n.target.id == "g"
             and isinstance(n.iter, ast.Name) and n.iter.id == "horizon"
             and any(isinstance(c, ast.Attribute) and c.attr == "xp_components"
                     for c in ast.walk(n))]
    assert len(loops) == 1, "builderin xP-horisonttisilmukka muuttui"
    return loops[0]


def test_builder_emittoi_minuutit_samasta_xm_g_sta_kuin_xp():
    """Kutsupaikka: kierroksen minuutit tulevat samasta `xm_g`:sta jolla
    `xp_components` laskee kierroksen xP:n, kerrottuna otteluiden maaralla.
    Rivin `xmins` (otsikkokierros) tai `mm_r` ilman kerrointa antaisi
    kumppanille minuutit jotka eivat vastaa xP:ta."""
    loop = _horizon_loop()
    comps = [n for n in ast.walk(loop) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "xp_components"]
    assert comps and all(isinstance(c.args[2], ast.Name) and c.args[2].id == "xm_g"
                         for c in comps)
    appends = [n for n in ast.walk(loop) if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Attribute) and n.func.attr == "append"
               and isinstance(n.func.value, ast.Name) and n.func.value.id == "gws"]
    assert len(appends) == 1
    row = appends[0].args[0]
    keys = [k.value for k in row.keys]
    assert "xmins" in keys, "gameweeks[].xmins puuttuu builderista"
    val = row.values[keys.index("xmins")]
    names = {n.id for n in ast.walk(val) if isinstance(n, ast.Name)}
    assert names == {"round", "xm_g", "len", "ctxs"}, ast.unparse(val)


def test_reitti_kayttaa_actionable_lukijaa(client, keys, monkeypatch, tmp_path):
    # Kutsupaikka, ei vain funktio: reitti lukee load_xp_actionablen kautta.
    path = _xp_file(tmp_path, 7)
    monkeypatch.setattr(pf, "load_xp_actionable",
                        lambda: fpl_xp.load_xp_actionable(path))
    d = client.get("/api/partner/xp", headers={"X-Partner-Key": KEY}).json()
    assert d["gameweeks"] == [7, 8, 9, 10, 11]
    assert d["players"][0]["xmins"]["10"] == 170.0
    src = (ROOT / "api/partner_feed.py").read_text(encoding="utf-8")
    assert "load_xp_actionable()" in src and "load_xp()" not in src


def test_projektio_puuttuu_503(client, keys, monkeypatch):
    monkeypatch.setattr(pf, "load_xp_actionable", lambda: fpl_xp.empty_xp())
    assert client.get("/api/partner/xp", headers={"X-Partner-Key": KEY}).status_code == 503
