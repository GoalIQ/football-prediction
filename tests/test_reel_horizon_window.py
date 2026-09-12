# -*- coding: utf-8 -*-
"""Portti: gen_reel.py:n ikkunateksti seuraa oikeaa kierrosta (REEL-HORISONTTI-IKKUNA, 12.9.2026).

`card_cs()`:n "Gameweek 1" ja `card_value()`:n "First six gameweeks" olivat
kovakoodattuja merkkijonoja. Ne olivat oikein vain siihen asti kun kauden oma
GW1 oli viela edessa - heti kun horisontti liukuu pelatun kierroksen ohi
(esim. deadline_gameweek=12 mutta artefaktissa on yha GW10-11 mukana), teksti
vaittaa vaaraa kierrosta. Sama bugiluokka kuin jakokortin ikkunakorjaus
(`fpl_gameweek.window_label`, ks. `tests/test_transfer_horizon_parity.py`).

Negatiivinen kontrolli tassa on `test_menneet_kierrokset_eivat_paase_ikkunaan`:
syotedatassa ON menneita kierroksia (GW10-11 deadlinen 12 alla), ja testi
kaatuisi jos joku palauttaisi ikkunan raa'an listan min/max-arvoista sen
sijaan etta suodattaisi `actionable_gameweeks`-lukijalla.
"""
from __future__ import annotations

import json

import pytest

from scripts import gen_reel


def test_gameweek_yksikko_kun_yksi_kierros_jaljella():
    meta = {"deadline_gameweek": 12}
    assert gen_reel._window_phrase(meta, [12]) == "Gameweek 12"


def test_gameweeks_vali_kun_useampi_kierros():
    meta = {"deadline_gameweek": 12}
    assert gen_reel._window_phrase(meta, [12, 13, 14, 15, 16, 17]) == "Gameweeks 12-17"


def test_menneet_kierrokset_eivat_paase_ikkunaan():
    """Negatiivinen kontrolli: GW10-11 ovat lukittuja (deadline 12 on jo ohi
    niiden omien deadlinejen), mutta artefaktissa ne ovat viela listalla.
    Naiivi min/max raakalistasta sanoisi 'Gameweeks 10-17'; oikea vastaus
    suodattaa ne pois."""
    meta = {"deadline_gameweek": 12}
    raw_including_past = [10, 11, 12, 13, 14, 15, 16, 17]
    assert gen_reel._window_phrase(meta, raw_including_past) == "Gameweeks 12-17"


def test_ei_kierroksia_ei_kaadu():
    assert gen_reel._window_phrase({"deadline_gameweek": 12}, []) == "the next gameweeks"


def _phase0_fixture(deadline_gw: int, gws: list[int]) -> dict:
    fixtures = [{"gw": g, "venue": "H", "opponent": "OPP", "cs_pct": 50.0 + g}
                for g in gws]
    return {
        "meta": {"deadline_gameweek": deadline_gw, "generated_at": "2026-09-12T00:00:00Z"},
        "teams": [{"name": "Test FC", "fixtures": fixtures}],
    }


def _xp_fixture(deadline_gw: int, gws: list[int], n_players: int = 5) -> dict:
    players = []
    for i in range(n_players):
        players.append({
            "web_name": f"Player{i}",
            "team_short": "TFC",
            "price": 5.0 + i,
            "xmins": 80,
            "status": "a",
            "xp_horizon_total": 20.0 - i,
            "gameweeks": [{"gw": g} for g in gws],
        })
    return {
        "meta": {"deadline_gameweek": deadline_gw, "generated_at": "2026-09-12T00:00:00Z"},
        "players": players,
    }


def test_card_cs_kaytta_todellista_kierrosta_ei_kovakoodattua_ykkosta(tmp_path, monkeypatch):
    # Tuotannon phase0-artefaktin joukkuekohtainen fixtures[] alkaa jo
    # deadline_gameweekista (mitattu 12.9: GW4 seka meta.deadline_gameweek
    # etta fixtures[0].gw), joten fixture tassa jaljittelee sita eika keksi
    # uutta muotoa. Deadline on GW12, EI GW1 - vanha kovakoodattu "Gameweek 1"
    # olisi tassa yhta vaarin kuin tuotannossa nyt (GW4, ei GW1).
    doc = _phase0_fixture(12, [12, 13, 14, 15, 16, 17])
    p = tmp_path / "phase0.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(gen_reel, "PHASE0", p)

    card = gen_reel.card_cs()
    assert card["sub1"] == "Gameweek 12"
    assert card["sub1"] != "Gameweek 1"
    assert "Gameweeks 12-17" in card["point"]
    assert "first six" not in card["point"].lower()


def test_card_value_kaytta_todellista_ikkunaa_ei_kovakoodattua_tekstia(tmp_path, monkeypatch):
    doc = _xp_fixture(12, [12, 13, 14, 15, 16, 17])
    p = tmp_path / "xp.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(gen_reel, "XP", p)

    card = gen_reel.card_value()
    assert card["sub1"] == "Gameweeks 12-17"
    assert card["sub1"] != "First six gameweeks"


def test_card_value_yhden_kierroksen_ikkuna_on_yksikossa(tmp_path, monkeypatch):
    """Kauden viimeinen kierros: ikkunassa on vain yksi GW, ei valia."""
    doc = _xp_fixture(38, [38])
    p = tmp_path / "xp.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(gen_reel, "XP", p)

    card = gen_reel.card_value()
    assert card["sub1"] == "Gameweek 38"
