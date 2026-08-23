"""/fpl/points: toteutuneet pisteet vs deadlinella JÄÄDYTETTY ennuste.

Sivun koko arvo on siinä, että xP-sarake on se luku joka julkaistiin ENNEN
kierrosta. Elävä xP liikkuu kesken ja jälkeen kierroksen kohti toteumaa
(mitattu 22.8: Gabriel 5.78 -> 5.14), joten elävän vertaaminen toteumaan
näyttäisi mallin tarkempana kuin se oli. Nämä testit vartioivat tasan sitä.
"""
from __future__ import annotations

import re
from datetime import datetime

import pytest

import scripts.build_fpl_longtail as bl


NYT = datetime(2026, 8, 23, 12, 0)

COLS = ["gw", "pts", "g", "a", "dc", "cs", "bps", "bonus", "mins", "xg", "xa"]


def _player_gw(rows: dict[str, list[list]]) -> dict:
    return {"meta": {"cols": COLS, "max_gw": 1, "basis_season": "2026/27"},
            "players": rows}


def _rivi(gw=1, pts=6, g=1, a=0, dc=3, cs=1, bps=25, bonus=1, mins=90,
          xg=0.4, xa=0.1):
    return [gw, pts, g, a, dc, cs, bps, bonus, mins, xg, xa]


def _frozen(players: list[dict]) -> dict:
    return {"meta": {"gw": 1, "deadline": "2026-08-21T17:30:00Z",
                     "frozen_at": "2026-08-20T12:33:43Z"},
            "players": players}


@pytest.fixture
def frozen_stub(monkeypatch):
    """Ohjaa jäädytetyn lumikuvan lukemisen ilman levyä."""
    doc: dict = {}

    def fake(gw):
        return doc.get("d")

    monkeypatch.setattr(bl, "_latest_frozen_gw", fake)
    return doc


def _teksti(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def test_xp_sarake_tulee_jaadytetysta_lumikuvasta(frozen_stub):
    """Jos xP tulisi muualta, tämä luku ei täsmäisi."""
    frozen_stub["d"] = _frozen([
        {"id": 1, "web_name": "Gabriel", "team_short": "ARS", "pos": "DEF",
         "price": 6.1, "xp": 5.78},
    ])
    html = bl.render_points(_player_gw({"1": [_rivi(pts=5)]}), NYT)
    assert html is not None
    assert "5.78" in html          # jäädytetty arvo sellaisenaan
    assert "-0.78" in html         # 5 - 5.78, ei pyöristetty pois
    assert "5.14" not in html      # elävä arvo EI saa esiintyä


def test_pelaamaton_ei_saa_rivia(frozen_stub):
    """Puuttuva rivi on totuus; nolla olisi väite."""
    frozen_stub["d"] = _frozen([
        {"id": 1, "web_name": "Pelasi", "team_short": "ARS", "pos": "MID",
         "price": 5.0, "xp": 3.0},
        {"id": 2, "web_name": "Haaland", "team_short": "MCI", "pos": "FWD",
         "price": 15.0, "xp": 7.5},
    ])
    # id 2 ei ole player-gw:ssä lainkaan -> ei ole pelannut
    html = bl.render_points(_player_gw({"1": [_rivi()]}), NYT)
    assert "Pelasi" in html
    assert "Haaland" not in html


def test_ilman_jaadytettya_ennustetta_pudotetaan_mutta_sanotaan_aaneen(frozen_stub):
    """Hiljainen pudotus tekisi taulusta vajaan ilman että kukaan näkee."""
    frozen_stub["d"] = _frozen([
        {"id": 1, "web_name": "Mukana", "team_short": "ARS", "pos": "MID",
         "price": 5.0, "xp": 3.0},
    ])
    html = bl.render_points(
        _player_gw({"1": [_rivi()], "99": [_rivi(pts=9)]}), NYT)
    assert "Mukana" in html
    t = _teksti(html)
    assert "1 player who did play is also left out" in t


def test_mae_lasketaan_riveista_eika_kovakoodata(frozen_stub):
    frozen_stub["d"] = _frozen([
        {"id": 1, "web_name": "A", "team_short": "ARS", "pos": "MID",
         "price": 5.0, "xp": 2.0},
        {"id": 2, "web_name": "B", "team_short": "CHE", "pos": "MID",
         "price": 5.0, "xp": 4.0},
    ])
    # toteumat 6 ja 4 -> virheet 4.0 ja 0.0 -> MAE 2.0
    html = bl.render_points(
        _player_gw({"1": [_rivi(pts=6)], "2": [_rivi(pts=4)]}), NYT)
    t = _teksti(html)
    assert "2.0 points" in t
    assert "too low on 1 of them and too high on 1" in t


def test_defcon_ja_muut_sarakkeet_ovat_mukana(frozen_stub):
    frozen_stub["d"] = _frozen([
        {"id": 1, "web_name": "A", "team_short": "ARS", "pos": "DEF",
         "price": 5.0, "xp": 3.0},
    ])
    html = bl.render_points(_player_gw({"1": [_rivi(dc=7, bps=31)]}), NYT)
    for otsikko in ("DC", "BPS", "xG", "xA", "Bonus" if False else "B"):
        assert f'>{otsikko}<' in html, otsikko
    assert "DefCon" in html      # selitetään lyhenne, ei jätetä arvattavaksi


def test_tyhja_syote_ei_tuota_sivua(frozen_stub):
    frozen_stub["d"] = _frozen([])
    assert bl.render_points(_player_gw({}), NYT) is None
    assert bl.render_points({"meta": {}, "players": {}}, NYT) is None


def test_jarjestys_on_toteutuneet_pisteet_laskevasti(frozen_stub):
    frozen_stub["d"] = _frozen([
        {"id": 1, "web_name": "Vahan", "team_short": "ARS", "pos": "MID",
         "price": 5.0, "xp": 8.0},
        {"id": 2, "web_name": "Paljon", "team_short": "CHE", "pos": "MID",
         "price": 5.0, "xp": 1.0},
    ])
    html = bl.render_points(
        _player_gw({"1": [_rivi(pts=2)], "2": [_rivi(pts=12)]}), NYT)
    assert html.index("Paljon") < html.index("Vahan")
