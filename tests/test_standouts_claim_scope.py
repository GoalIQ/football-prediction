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
    # 22.9 (kierros 2): jokainen omassa seurassaan. Yhteinen "TST" teki
    # seurakatolla poolista kolmen pelaajan (kuten Cityn 18.9) ja jatti
    # loput sivun tauluun - tasan se tila jonka superlatiivi kumosi.
    return {
        "id": pid, "web_name": name, "team_short": f"T{pid}", "team": f"T{pid}",
        "pos": "FWD",
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


def test_safest_vertailujoukko_on_se_minka_lukija_nakee() -> None:
    """22.9 (julkaisuportti, kierros 2) KUMOSI taman testin aiemman muodon.
    Se sanoi: "xP-rajan alle jaava pelaaja ei ole ehdokas, joten han ei saa
    kaataa superlatiivia". Mutta lukija ei nae GW-xP-rajaa (SAFE_MIN_XP)
    mistaan: kortti kertoo ehdokseen vain "at least a 60% chance of
    starting", ja #top-100-taulu nayttaa Blank- ja Start%-sarakkeet. Rivi
    joka tayttaa kortin ILMOITTAMAN ehdon ja blankkaa harvemmin kumoaa
    vaitteen lukijan silmissa, joten superlatiivi jatetaan pois."""
    nakyva = list(CLEAN) + [
        _player(9, "Bench", p90=3, p_haul=0.0, p_blank=0.01, gw_xp=1.0),
    ]
    html, _ = build_html(_data(nakyva), log=None)
    assert "lowest blank chance" not in _why(html, "Safest pick")
    # Negatiivinen kontrolli: sama rivi alle kortin oman ehdon (start 50 %).
    alle = dict(nakyva[-1], p_start=0.5)
    html, _ = build_html(_data(list(CLEAN) + [alle]), log=None)
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


def test_captain_superlative_goes_through_claim_scope():
    """10.9 (KORTIN-KAPTEENITIILI-CLAIM-SCOPE): kapteenin "top GW projection
    in the pool" ei ollut lukijan lapi. Tasapeli -> "joint top", parempi
    poolissa joka ei ole kortilla -> ei superlatiivia."""
    from scripts.render_standouts_card import claim_scope, scope_phrase
    a = {"id": 1, "web_name": "A", "gameweeks": [{"gw": 4, "xp": 5.5}]}
    b = {"id": 2, "web_name": "B", "gameweeks": [{"gw": 4, "xp": 5.5}]}
    c = {"id": 3, "web_name": "C", "gameweeks": [{"gw": 4, "xp": 6.0}]}
    val = lambda p: p["gameweeks"][0]["xp"]
    assert scope_phrase("top GW4 projection", claim_scope([a, b], a, val, True, {})) \
        == "joint top GW4 projection in the pool"
    assert scope_phrase("top GW4 projection", claim_scope([a, c], a, val, True, {})) == ""
    assert scope_phrase("top GW4 projection", claim_scope([a], a, val, True, {})) \
        == "top GW4 projection in the pool"


# ---------------------------------------------------------------------------
# 22.9 JULKAISUPORTTI, KIERROS 2: vertailujoukko = pooli ∪ lukijan nakemat rivit
# ---------------------------------------------------------------------------
# Tarkistaja ajoi 148 origin/mainin projektiocommitia (1.-22.9): safest olisi
# ollut EPATOSI 49:ssa. Esim. bcedc68ff ja 61d68d357 (18.9): kortti sanoi
# "lowest blank chance after our captain pick, blanks 20%", kun
# /fpl/expected-points#top-100 nayttaa Andersonin (MCI) blank 17 %, Start 97.
# Syy: kortin pooli soveltaa seurakattoa (max 3 per seura, `top_projected`),
# joten Anderson oli Cityn NELJAS eika poolissa - mutta sivun top-100-taulu
# ei sovella kattoa, ja siella lukija hanet nakee. Vertailu tehdaan nyt
# kortin tarkistusreitin riveja vastaan: captain -> #gw-xp (`free_rows`),
# ceiling ja safest -> #top-100 (`horizon_top_ids_actionable`), vain rivit
# jotka tayttavat kortin oman ehdon (p_start >= 0.6), ja NAYTETYILLA
# pyoristyksilla (sivu: round(p*100) %, GW-xP 1 desimaali).

def _pl(pid, name, club, xp, blank, p90=10, haul=0.15, pos="MID", p_start=0.95):
    return {"id": pid, "web_name": name, "team_short": club, "team": club,
            "pos": pos, "price": 6.0, "status": "a", "p_start": p_start,
            "xp_horizon_total": xp * 6, "xp_per_gw": xp,
            "gameweeks": [{"gw": 6, "xp": xp}],
            "xp_dist": {"gw": 6, "n": 2000, "mean": xp, "p_haul": haul,
                        "p_blank": blank, "p10": 1, "median": 4, "p90": p90,
                        "haul_pts": 10, "blank_pts": 2}}


def _data18(players):
    return {"meta": {"next_gameweek": 6, "deadline_gameweek": 6,
                     "available": True,
                     "deadline_utc": "2026-10-10T10:00:00+00:00",
                     "generated_at": "2026-09-18T03:59:51+00:00"},
            "players": players}


# 18.9:n rakenne: kolme Cityn pelaajaa tayttaa seurakaton, neljas (Anderson)
# blankkaa harvemmin kuin kortin "safest" ja nakyy sivun top-100:ssa.
MCI18 = [
    _pl(1, "Haaland", "MCI", 7.0, 0.05, p90=14, haul=0.30, pos="FWD"),
    _pl(2, "Guehi", "MCI", 6.0, 0.25, p90=11, pos="DEF"),
    _pl(3, "Foden", "MCI", 5.8, 0.30, p90=11),
    _pl(4, "Anderson", "MCI", 5.0, 0.17, p90=9, p_start=0.97),
    _pl(5, "Ceil", "ARS", 5.5, 0.35, p90=15, haul=0.25, pos="FWD"),
    _pl(6, "Safe", "LIV", 4.5, 0.20, p90=9),
    _pl(7, "Gamb", "CHE", 3.0, 0.45, p90=12, haul=0.20),
]


def test_18_9_neljas_seuran_pelaaja_taulussa_kaataa_safest_superlatiivin():
    html, s = build_html(_data18(MCI18), log=None)
    assert s["safest"]["web_name"] == "Safe"          # fikstuuri tekee mita vaittaa
    assert "Anderson" not in {(p or {}).get("web_name") for p in s.values()}
    why = _why(html, "Safest pick")
    assert "lowest blank chance" not in why, why[:200]
    assert "blanks 20%" in why, why[:200]


def test_18_9_negatiivinen_kontrolli_ilman_andersonia_superlatiivi_sailyy():
    html, _ = build_html(_data18([p for p in MCI18 if p["id"] != 4]), log=None)
    why = _why(html, "Safest pick")
    assert "lowest blank chance after our captain pick, blanks 20%" in why, why[:200]


def test_rivi_joka_ei_tayta_kortin_ehtoa_ei_kaada_superlatiivia():
    """Start alle 60 %: kortti sanoo itse ottavansa vain >= 60 %, joten rivi
    ei ole superlatiivin vertailujoukossa vaikka se nakyy taulussa."""
    muu = [dict(p) for p in MCI18]
    muu[3] = _pl(4, "Anderson", "MCI", 5.0, 0.17, p90=9, p_start=0.55)
    html, _ = build_html(_data18(muu), log=None)
    assert "lowest blank chance after our captain pick" in _why(html, "Safest pick")


def test_vertailu_naytetyilla_pyoristyksilla_tasatilanne_on_joint():
    """Anderson 0.204 ja Safe 0.200 nakyvat molemmat 20 %:na: kortti ei saa
    vaittaa yksin pieninta, vaan 'joint lowest'."""
    muu = [dict(p) for p in MCI18]
    muu[3] = _pl(4, "Anderson", "MCI", 5.0, 0.204, p90=9)
    html, _ = build_html(_data18(muu), log=None)
    why = _why(html, "Safest pick")
    assert "joint lowest blank chance after our captain pick" in why, why[:200]


def test_captain_vertailu_gw_xp_listaa_vastaan():
    """Kapteenin 'top GW6 projection' tarkistetaan #gw-xp-listalta: 4. MCI-
    pelaaja jolla parempi GW-xP kuin kapteenilla ei ole listalla (seurakatto
    on myos sivulla), joten se EI kaada superlatiivia - mutta listan pelaaja
    samalla 1 desimaalin luvulla tekee siita 'joint top'."""
    muu = [dict(p) for p in MCI18]
    muu.append(_pl(8, "Twin", "NEW", 7.04, 0.40, p90=8, p_start=0.9))
    html, _ = build_html(_data18(muu), log=None)
    assert "joint top GW6 projection" in _why(html, "Captain pick")
