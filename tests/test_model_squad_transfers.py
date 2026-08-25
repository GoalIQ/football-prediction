"""Mallin runko peritaan ja siirrot tehdaan FPL:n saannoilla (25.8.2026).

🔴 TAUSTA. `freeze_model_squad_gw.py` kutsui `free_optimum()`:ia ILMAN
viittausta edelliseen runkoon: ei siirtorajaa, ei hit-kustannusta. Mitattu 25.8
GW1 -> GW2: 7 pelaajaa 15:sta olisi vaihtunut. Ihminen saa YHDEN ilmaisen
siirron; seitseman maksaisi -24 pistetta. Malli ei maksanut mitaan.

Ja kayttajalle nakyi samaan aikaan lause "The model's squad is locked before
every deadline and plays no chips." Teknisesti tosi (FPL-chippia ei aktivoida)
mutta se antaa ymmartaa etta malli pelaa samoilla saannoilla kuin lukija. Alusta
rakentaminen on VAHVEMPI kuin wildcard, jonka ihminen saa kerran tai kaksi
kaudessa.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "freeze_model_squad_gw", ROOT / "scripts" / "freeze_model_squad_gw.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _p(pid, pos=3, price=50, club=1, xp=5.0):
    return {"id": pid, "element_type": pos, "price": price, "club": club,
            "web_name": f"P{pid}", "team_short": "AAA",
            "xp_horizon_total": xp, "gameweeks": [{"gw": 2, "xp": xp / 6}]}


def _freeze(ids, meta=None):
    rivit = [{"id": i, "web_name": f"P{i}", "pos": 3, "price": 50, "club": 1}
             for i in ids]
    return {"meta": meta or {}, "xi": rivit[:11], "bench": rivit[11:]}


# ---------------------------------------------------------------------------
# FT-saldo
# ---------------------------------------------------------------------------
def test_ilman_rullausta_yksi_ilmainen_siirto():
    m = _load()
    assert m._ft_available({}) == 1
    assert m._ft_available({"ft_left": 0}) == 1


def test_kayttamaton_siirto_rullaa_kattoon_asti():
    m = _load()
    assert m._ft_available({"ft_left": 1}) == 2
    # 🔴 Katto: rullaus ei kerry rajatta. Ilman kattoa malli saisi kauden
    # lopussa kaytannossa wildcardin ilmaiseksi.
    assert m._ft_available({"ft_left": 5}) == m.FT_MAX
    assert m.FT_MAX == 2


def test_vanha_freeze_ilman_kenttaa_on_konservatiivinen():
    """Puuttuva `ft_left` -> ei rullausta. Epavarmuudessa malli rajoitetaan
    tiukemmin, koska virhe ei silloin imartele sita."""
    m = _load()
    assert m._ft_available({"gw": 1, "cost": 100.0}) == 1


# ---------------------------------------------------------------------------
# Edellisen freezen loytaminen
# ---------------------------------------------------------------------------
def test_perii_lahimmasta_aiemmasta_eika_oleta_gw_miinus_yksi(tmp_path, monkeypatch):
    """Kierros voi jaada valiin (ajo kaatui, kausitauko). Runko peritaan silti
    viimeisimmasta joka on olemassa."""
    m = _load()
    monkeypatch.setattr(m, "FROZEN_DIR", tmp_path)
    (tmp_path / "gw1.json").write_text(json.dumps(_freeze([1])), encoding="utf-8")
    (tmp_path / "gw3.json").write_text(json.dumps(_freeze([2])), encoding="utf-8")
    n, _ = m._prev_freeze(5)
    assert n == 3, "lahin AIEMPI, ei gw-1"


def test_ei_aiempaa_freezea_palauttaa_none(tmp_path, monkeypatch):
    """Kauden ensimmainen kierros: vapaa valinta, kuten ihmisellakin."""
    m = _load()
    monkeypatch.setattr(m, "FROZEN_DIR", tmp_path)
    assert m._prev_freeze(1) is None


def test_myohempi_freeze_ei_kelpaa_lahteeksi(tmp_path, monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "FROZEN_DIR", tmp_path)
    (tmp_path / "gw7.json").write_text(json.dumps(_freeze([1])), encoding="utf-8")
    assert m._prev_freeze(3) is None, "tulevaa kierrosta ei saa peria"


# ---------------------------------------------------------------------------
# Siirtorajoite
# ---------------------------------------------------------------------------
def test_ilman_ilmaisia_siirtoja_hitti_vaatii_hyodyn_yli_neljan(monkeypatch):
    """🔴 Hitti otetaan VAIN kun horisontti-hyoty ylittaa sen hinnan. Sama
    kynnys jolla tuote kehottaa kayttajaa ottamaan hitin."""
    m = _load()
    pool = [_p(1), _p(2, xp=9.0)]
    kutsut = {"n": 0}

    def fake(squad, p, bank):
        kutsut["n"] += 1
        # Ensimmainen ehdotus +3,0 (alle 4) -> hitti EI kannata
        return {"hold": False, "suggestions": [
            {"out": {"id": 1}, "in": {"id": 2}, "delta_xp_horizon": 3.0}]}

    monkeypatch.setattr("src.models.fpl_rate_team.transfer_suggestions", fake)
    prev = _freeze(list(range(1, 16)), {"budget": 100.0})
    pool = [_p(i) for i in range(1, 16)] + [_p(99, xp=9.0)]
    out = m._constrained_from_prev(prev, pool, 2, ft=0)
    assert out["transfers"] == [], "3,0 < 4,0 -> ei hittia"
    assert out["hits"] == 0


def test_ilmainen_siirto_kaytetaan_pienellakin_hyodyllä(monkeypatch):
    m = _load()

    def fake(squad, p, bank):
        return {"hold": False, "suggestions": [
            {"out": {"id": 1}, "in": {"id": 99}, "delta_xp_horizon": 0.5}]}

    monkeypatch.setattr("src.models.fpl_rate_team.transfer_suggestions", fake)
    prev = _freeze(list(range(1, 16)), {"budget": 100.0})
    pool = [_p(i) for i in range(1, 16)] + [_p(99, xp=9.0)]
    out = m._constrained_from_prev(prev, pool, 2, ft=1)
    assert len(out["transfers"]) == 1
    assert out["hits"] == 0
    assert out["transfers"][0]["hit"] is False


def test_hold_pysayttaa_siirrot(monkeypatch):
    m = _load()
    monkeypatch.setattr("src.models.fpl_rate_team.transfer_suggestions",
                        lambda s, p, b: {"hold": True, "suggestions": [
                            {"out": {"id": 1}, "in": {"id": 99},
                             "delta_xp_horizon": 99.0}]})
    prev = _freeze(list(range(1, 16)), {"budget": 100.0})
    pool = [_p(i) for i in range(1, 16)] + [_p(99)]
    out = m._constrained_from_prev(prev, pool, 2, ft=2)
    assert out["transfers"] == [], "hold on tulos, ei ohitettava"


def test_pelaaja_poissa_poolista_estaa_perimisen():
    """🔴 Runkoa ei voi peria rehellisesti jos pelaaja on poistunut liigasta.
    Palautetaan None, jolloin kutsuja putoaa vapaaseen optimiin JA kertoo sen
    metassa - ei vaieta."""
    m = _load()
    prev = _freeze(list(range(1, 16)), {"budget": 100.0})
    pool = [_p(i) for i in range(1, 15)]        # yksi puuttuu
    assert m._constrained_from_prev(prev, pool, 2, ft=1) is None


def test_ft_left_kertoo_kayttamattomat(monkeypatch):
    m = _load()
    monkeypatch.setattr("src.models.fpl_rate_team.transfer_suggestions",
                        lambda s, p, b: {"hold": True, "suggestions": []})
    prev = _freeze(list(range(1, 16)), {"budget": 100.0})
    pool = [_p(i) for i in range(1, 16)]
    out = m._constrained_from_prev(prev, pool, 2, ft=2)
    assert out["ft_left"] == 2, "kayttamattomat rullaavat eteenpain"
