"""Portti: standouts-kortin tiili ei saa vaittaa superlatiivia jonka
viereinen tiili kumoaa.

MITATTU KAHDESTI SAMASTA KORTISTA (4.9.2026, julkaisuportti):

  k1  Ceiling-tiili sanoi "top ceiling in the pool". `pick_standouts()`
      valitsee ceilingin `rest()`-joukosta josta kapteeni on jo pudotettu,
      ja GW3:ssa kapteeni Haalandin katto oli 14, "ceilingin" Isakin 11 -
      ja Haalandin luku on VIEREISESSA tiilessa. Samassa lauseessa oli
      toinen vaite, "and he reaches it most often", jota mikaan kentta ei
      mittaa.

  k2  Korjaus koski vain ceiling-tiilta ja jatti SAMAN vian kahteen paikkaan:
        - Safest-tiili nimesi Andersonin (blank 17 %) turvallisimmaksi,
          vaikka Haaland (5 %) ja Isak (15 %) ovat samalla kortilla.
        - Ceiling-korjaus itse ohitti tasapelin: p90 on kokonaisluku, ja
          GW3:ssa katto 11 oli kolmella (Guehi, Foden, Isak), joten "top"
          ei ollut yksikasitteinen edes rajattuna. Ensimmaisen kierroksen
          portti ei nahnyt sita, koska kaikissa sen fikstuureissa ceilingin
          p90 oli uniikki.

Vaite johdetaan nyt yhdesta lukijasta (`claim_scope` + `scope_phrase`), ja
tama portti ajaa sen KAIKISSA vaiheissa (saanto 6a kohta 3): rajaus paalla
ja pois, tasapeli paalla ja pois, molemmat tiilet.
"""
from __future__ import annotations

import re

import pytest

from scripts.render_standouts_card import (build_html, claim_scope,
                                           scope_phrase)


def _player(pid: int, name: str, p90: int, p_haul: float, p_blank: float,
            price: int = 60, et: int = 4, gw_xp: float = 5.0) -> dict:
    return {
        "id": pid, "web_name": name, "team_short": "TST", "pos": "FWD",
        "element_type": et, "price": price, "now_cost": price,
        "status": "a", "chance_next": 100, "p_start": 0.9, "xmins": 85,
        "data_basis": "pl_history", "owned_pct": 5.0,
        "xp_horizon_total": 30.0, "xp_per_gw": 5.0,
        "gameweeks": [{"gw": 3, "xp": gw_xp}],
        "xp_dist": {"gw": 3, "n": 2000, "mean": 5.0, "p_haul": p_haul,
                    "p_blank": p_blank, "p10": 2, "median": 5, "p90": p90,
                    "haul_pts": 10, "blank_pts": 2},
    }


def _data(players: list[dict]) -> dict:
    return {"meta": {"next_gameweek": 3, "deadline_gameweek": 3,
                     "horizon_gw": 6, "generated_at": "2026-09-04T00:00:00Z"},
            "players": players}


def _why(html: str, tile: str) -> str:
    i = html.find(tile)
    assert i != -1, f"tiilta {tile!r} ei loydy kortilta"
    return re.sub(r"<[^>]+>", " ", html[i:i + 900])


# GW3:n oikea tilanne: kapteenilla korkein katto, ceiling-katto kolmen
# jakama, ja kaksi kortin pelaajaa blankkaa harvemmin kuin "safest".
GW3 = [
    _player(1, "Cap", p90=14, p_haul=0.31, p_blank=0.049, gw_xp=7.9),
    _player(2, "Ceil", p90=11, p_haul=0.213, p_blank=0.146, gw_xp=6.0),
    _player(3, "TieA", p90=11, p_haul=0.137, p_blank=0.30, gw_xp=5.0),
    _player(4, "TieB", p90=11, p_haul=0.135, p_blank=0.31, gw_xp=5.0),
    _player(5, "Safe", p90=8, p_haul=0.05, p_blank=0.17, price=64, et=3,
            gw_xp=4.7),
    _player(6, "Risk", p90=10, p_haul=0.11, p_blank=0.35, price=61, gw_xp=4.5),
]

# Sama kortti ilman tasapelia ja ilman rajausta.
CLEAN = [
    _player(1, "Cap", p90=9, p_haul=0.31, p_blank=0.20, gw_xp=7.9),
    _player(2, "Ceil", p90=15, p_haul=0.21, p_blank=0.25, gw_xp=6.0),
    _player(5, "Safe", p90=8, p_haul=0.05, p_blank=0.06, price=64, et=3,
            gw_xp=4.7),
    _player(6, "Risk", p90=10, p_haul=0.11, p_blank=0.35, price=61, gw_xp=4.5),
]


def test_ceiling_sanoo_rajauksen_kun_kapteenilla_on_korkeampi_katto() -> None:
    html, s = build_html(_data(GW3), log=None)
    why = _why(html, "Ceiling")
    assert "after our captain pick" in why, why[:200]
    assert "in the pool" not in why, why[:200]


def test_ceiling_sanoo_tasapelin() -> None:
    """p90 on kokonaisluku: sama katto voi olla usealla, ja kaikki kolme
    ovat samalla ilmaissivulla johon kortti linkkaa."""
    html, _ = build_html(_data(GW3), log=None)
    assert "joint top ceiling" in _why(html, "Ceiling")


def test_ceiling_ilman_rajausta_ja_tasapelia_saa_sanoa_poolin() -> None:
    """Negatiivinen kontrolli: kumpikaan varaus ei saa jaada paalle aina."""
    html, _ = build_html(_data(CLEAN), log=None)
    why = _why(html, "Ceiling")
    assert "top ceiling in the pool" in why, why[:200]
    assert "joint" not in why, why[:200]
    assert "after our" not in why, why[:200]


def test_ceiling_luku_on_sama_kuin_tiilen_oma_jakauma() -> None:
    html, s = build_html(_data(GW3), log=None)
    assert str(s["ceiling"]["xp_dist"]["p90"]) in _why(html, "Ceiling")


def test_safest_nimeaa_molemmat_edellaan_olevat_tiilet() -> None:
    """Kortin oma teksti kertoo etta kaksi turvallisempaa on samalla
    kortilla - muuten lukija laskee sen itse ja kortti on vaarassa."""
    html, s = build_html(_data(GW3), log=None)
    why = _why(html, "Safest pick")
    assert ("lowest blank chance after our captain pick and our ceiling pick"
            in why), why[:200]


def test_safest_ilman_rajausta_saa_sanoa_poolin() -> None:
    """Negatiivinen kontrolli: kun safest on oikeasti pienin, rajausta ei
    saa sanoa."""
    html, _ = build_html(_data(CLEAN), log=None)
    why = _why(html, "Safest pick")
    assert "lowest blank chance in the pool" in why, why[:200]
    assert "after our" not in why, why[:200]


def test_safest_vertailujoukko_on_sama_kuin_valinnassa() -> None:
    """xP-rajan alle jaava pelaaja ei ole ehdokas, joten han ei saa
    myoskaan kaataa superlatiivia. Muuten kortti varoisi sanomasta mitaan."""
    players = list(CLEAN) + [
        _player(9, "Bench", p90=3, p_haul=0.0, p_blank=0.01, gw_xp=1.0),
    ]
    html, _ = build_html(_data(players), log=None)
    assert "lowest blank chance in the pool" in _why(html, "Safest pick")


@pytest.mark.parametrize("kielletty", ["reaches it most often", "most often",
                                       "scored in public"])
def test_hylatyt_sanamuodot_eivat_palaa(kielletty: str) -> None:
    html, _ = build_html(_data(GW3), log=None)
    assert kielletty not in html, kielletty


def test_scope_ei_vaita_mitaan_jos_parempi_ei_ole_kortilla() -> None:
    """Fail-closed: jos joku parempi ei ole kortilla, lukijalla ei ole
    naytettavaa perustelua, joten superlatiivia ei sanota lainkaan."""
    pool = [_player(1, "A", p90=14, p_haul=0.3, p_blank=0.1),
            _player(2, "B", p90=11, p_haul=0.2, p_blank=0.2)]
    sc = claim_scope(pool, pool[1], lambda p: p["xp_dist"]["p90"], True,
                     {"captain": None})
    assert sc["on_card"] is False
    assert scope_phrase("top ceiling", sc) == ""


def test_scope_negatiivinen_kontrolli_tasapeli_katoaa() -> None:
    """Ilman tasapelia sama lukija palauttaa 'top', ei 'joint top'."""
    pool = [_player(1, "A", p90=14, p_haul=0.3, p_blank=0.1),
            _player(2, "B", p90=11, p_haul=0.2, p_blank=0.2)]
    sc = claim_scope(pool, pool[0], lambda p: p["xp_dist"]["p90"], True, {})
    assert scope_phrase("top ceiling", sc) == "top ceiling in the pool"
