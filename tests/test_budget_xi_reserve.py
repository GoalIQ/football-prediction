"""PORTTI: ahne budjetti-XI varaa jaljella olevat paikat POSITIOKOHTAISESTI.

MITATTU VIKA 16.9.2026: `/api/fantasy/chip-ev` vastasi tuotannossa **503**
"Cannot build a model squad from the pool" ilman entrya (entry-moodi toimi,
joten vika oli nakymaton kaikille jotka testasivat omalla entryllaan).

Juurisyy: budjettivaraus oli `slots_left * min_price`, jossa `min_price` on
KOKO poolin halvin pelaaja. Se on aliarvio aina kun jokin pakollinen positio
on kalliimpi kuin poolin halvin. Tuotannon luvut sina paivana:

    halvin pelaaja           3,9 m (DEF)
    halvin maalivahti        4,0 m
    XI-budjetti             84,1 m
    ahne kaytti 10 kenttapelaajaan 76,3 m -> maalivahdille jai 3,9 m

Yhden kymmenyksen vaje kaatoi koko endpointin. Vika oli ollut olemassa niin
kauan kuin halvin maalivahti sattui olemaan poolin halvin pelaaja — eli
invariantti oli mitattu hetkella jolloin se sattui pitamaan (CLAUDE.md 6a).

Siksi tama testi EI aja tuotannon poolia vaan SYNTEETTISIA hintarakenteita:
hinnat ovat ulkoista tilaa joka vaihtuu koodin alla joka kerta kun FPL
hinnoittelee pelaajia uudelleen.
"""
from __future__ import annotations

import pytest

from api.fantasy_edge import BUDGET_TENTHS, _greedy_budget_xi
from src.models.fpl_rate_team import SQUAD_QUOTA, XI_MAX, XI_MIN

MAX_PER_CLUB = 3


def _pool(spec: dict[int, list[tuple[int, float]]]) -> list[dict]:
    """Pooli (hinta, xp) -pareista per positio. xp annetaan EKSPLISIITTISESTI,
    koska ahne kayttaa GLOBAALIA xp-jarjestysta positioiden yli — johdettu
    "listan jarjestys" ei riita kun tarkoitus on ohjata valintajarjestys
    tuotannon muotoon. Klubit kierratetaan, jotta klubikatto ei ole se mika
    kaataa (sita vahtii `_legal`)."""
    out, pid = [], 1
    for pos, rows in spec.items():
        for price, xp in rows:
            out.append({
                "id": pid, "web_name": f"P{pid}", "element_type": pos,
                "club": (pid % 20) + 1, "price": price,
                "xp_horizon_total": float(xp),
                "team_short": "TST", "owned_pct": 1.0, "gameweeks": [],
            })
            pid += 1
    return out


def _legal(xi: list[dict]) -> None:
    assert len(xi) == 11, f"XI jai {len(xi)}:aan"
    counts: dict[int, int] = {}
    clubs: dict[int, int] = {}
    for p in xi:
        counts[p["element_type"]] = counts.get(p["element_type"], 0) + 1
        clubs[p["club"]] = clubs.get(p["club"], 0) + 1
    for t in XI_MIN:
        assert XI_MIN[t] <= counts.get(t, 0) <= XI_MAX[t], (t, counts)
    assert max(clubs.values()) <= MAX_PER_CLUB, clubs


# Jokainen tapaus on hintarakenne jossa VAARA varaus (globaali minimi) ajaa
# ahneen umpikujaan. Kaikissa on varaa lailliseen XI:aan.
# TUOTANNON MUOTO 16.9, kymmenyksina. Luvut on valittu niin etta ahne kuluttaa
# budjetin kenttapelaajiin ja maalivahti jaa YHDEN kymmenyksen paahan — sama
# muoto joka kaatoi endpointin. `test_vaara_varaus_...` todistaa etta vanha
# varaus ei selvia tasta; ilman sita fikstuuri ei erottelisi mitaan.
TUOTANNON_MUOTO: dict[int, list[tuple[int, float]]] = {
    #    hinta  xp   (xp ohjaa valintajarjestyksen)
    1: [(40, 10), (45, 9), (50, 8), (55, 7)],
    2: [(80, 100), (80, 99), (80, 98), (80, 97), (80, 96),
        (39, 5), (39, 5), (39, 5), (39, 5)],
    3: [(90, 95), (90, 94), (90, 93), (90, 92),
        (44, 4), (44, 4), (44, 4), (44, 4), (44, 4)],
    4: [(44, 91), (45, 3), (45, 3), (45, 3)],
}

RAKENTEET: dict[int, list[tuple[int, float]]] = {
    "tuotannon_muoto_16_9": TUOTANNON_MUOTO,
    # Karjistetty: maalivahdit selvasti kalliimpia, aliarvio on iso.
    "gk_selvasti_kallein_positio": {
        1: [(70, 10), (75, 9), (80, 8), (85, 7)],
        2: [(39, 100), (40, 99), (41, 98), (42, 97), (43, 96),
            (80, 20), (90, 19), (100, 18), (110, 17)],
        3: [(40, 95), (41, 94), (42, 93), (95, 30), (105, 29),
            (115, 28), (125, 27), (130, 26), (135, 25)],
        4: [(40, 92), (41, 91), (90, 22), (100, 21), (110, 20), (120, 19)],
    },
    # Hyokkaajat kalleimpia: XI_MIN[4] = 1 on se vaje joka jaa varaamatta.
    "fwd_kallein_pakollinen": {
        1: [(40, 10), (41, 9), (42, 8), (43, 7)],
        2: [(39, 100), (40, 99), (41, 98), (42, 97), (43, 96),
            (44, 95), (45, 94), (46, 93), (47, 92)],
        3: [(39, 90), (40, 89), (41, 88), (42, 87), (43, 86),
            (44, 85), (45, 84), (46, 83), (47, 82)],
        4: [(95, 80), (100, 79), (110, 78), (120, 77), (130, 76), (140, 75)],
    },
    # Tasainen pohja: vanha varaus riittaisi. Korjaus ei saa muuttaa
    # kayttaytymista siella missa se oli jo oikein.
    "tasainen_pohja": {
        1: [(40, 10), (41, 9), (42, 8), (43, 7)],
        2: [(40, 100), (41, 99), (42, 98), (43, 97), (44, 96),
            (45, 95), (46, 94), (47, 93), (48, 92)],
        3: [(40, 90), (41, 89), (42, 88), (43, 87), (44, 86),
            (45, 85), (46, 84), (47, 83), (48, 82)],
        4: [(40, 80), (41, 79), (42, 78), (43, 77), (44, 76), (45, 75)],
    },
}


@pytest.mark.parametrize("nimi", sorted(RAKENTEET))
def test_laillinen_xi_syntyy_jokaisella_hintarakenteella(nimi: str) -> None:
    pool = _pool(RAKENTEET[nimi])
    assert all(len([p for p in pool if p["element_type"] == t]) >= n
               for t, n in SQUAD_QUOTA.items()), "fikstuuri itse on rikki"
    xi = _greedy_budget_xi(pool, key=lambda p: p["xp_horizon_total"])
    _legal(xi)


@pytest.mark.parametrize("nimi", sorted(RAKENTEET))
def test_xi_mahtuu_budjettiin_penkkivaraus_mukaan(nimi: str) -> None:
    """XI:n hinta + halvin laillinen penkki ei saa ylittaa budjettia —
    muuten 'laillinen XI' olisi sellainen jota ei voi ostaa."""
    pool = _pool(RAKENTEET[nimi])
    xi = _greedy_budget_xi(pool, key=lambda p: p["xp_horizon_total"])
    by_pos: dict[int, list[int]] = {}
    for p in pool:
        by_pos.setdefault(p["element_type"], []).append(p["price"])
    bench = min(by_pos[1]) + sum(sorted(
        pr for t in (2, 3, 4) for pr in by_pos[t])[:3])
    assert sum(p["price"] for p in xi) + bench <= BUDGET_TENTHS


def test_liian_pieni_budjetti_palauttaa_tyhjan_eika_laitonta() -> None:
    """Aukko ei saa levita: kun XI:aan EI ole varaa, vastaus on tyhja lista
    (kutsuja nostaa 503:n), ei vajaa tai laiton XI."""
    kallis = {1: [(400, 10), (410, 9), (420, 8), (430, 7)],
              2: [(400, 5)] * 9, 3: [(400, 4)] * 9, 4: [(400, 3)] * 6}
    xi = _greedy_budget_xi(_pool(kallis), key=lambda p: p["xp_horizon_total"])
    assert xi == []


def test_vaara_varaus_kaataisi_tuotannon_muodon() -> None:
    """EROTTELEVA: sama pooli vanhalla varauksella (globaali minimi) jaa
    vajaaksi. Ilman tata testi menisi lapi myos rikkinaisella toteutuksella,
    koska ahne voi onnistua monella hintarakenteella sattumalta."""
    pool = _pool(TUOTANNON_MUOTO)
    by_pos: dict[int, list[dict]] = {1: [], 2: [], 3: [], 4: []}
    for p in pool:
        by_pos[p["element_type"]].append(p)
    xi_budget = BUDGET_TENTHS - (
        min(p["price"] for p in by_pos[1])
        + sum(sorted(p["price"] for t in (2, 3, 4) for p in by_pos[t])[:3]))
    min_price = min(p["price"] for p in pool)

    vanha: list[dict] = []
    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    clubs: dict[int, int] = {}
    cost = 0
    for p in sorted(pool, key=lambda q: q["xp_horizon_total"], reverse=True):
        if len(vanha) == 11:
            break
        t = p["element_type"]
        if counts[t] >= XI_MAX[t] or clubs.get(p["club"], 0) >= MAX_PER_CLUB:
            continue
        need_min = sum(max(0, XI_MIN[q] - counts[q] - (1 if q == t else 0))
                       for q in XI_MIN)
        slots_left = 11 - len(vanha) - 1
        if need_min > slots_left:
            continue
        if cost + p["price"] + slots_left * min_price > xi_budget:
            continue
        vanha.append(p)
        counts[t] += 1
        clubs[p["club"]] = clubs.get(p["club"], 0) + 1
        cost += p["price"]
    assert len(vanha) < 11, (
        "vanha varaus selviaa tasta fikstuurista -> fikstuuri ei erottele "
        "korjausta rikkinaisesta toteutuksesta")
    assert counts[1] == 0, "vian muoto oli nimenomaan varaamatta jaanyt maalivahti"
