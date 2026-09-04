"""Portti: benchmark ei saa havita kadella rakennetulle lailliselle rungolle.

🔴 MITATTU VIKA (4.9.2026, julkaisuportin loydos, vahvistettu itse).
`build_optimal_squad` palautti tuotannossa XI:n jonka horisontti-xP oli
**310.77**, mutta entryn 116920 OMA runko — taysin laillinen, 99.3m, max
3/seura, positiot 2/5/5/3 — antoi **322.42**. Vertailukohta ei siis ollut
ylaraja lainkaan:

    rating.beats_benchmark    True
    rating.percentile         100.0   (leikattu min(100, ...))
    rating.gap_to_optimal_xp  0.0

Kayttajalle nayttavassa copyssa se oli "100% of the best possible budget
squad" vertailukohdasta jonka sama data osoittaa voitetuksi — tasan se ontto
imartelu jota `fpl_rate_team.py:666` varoittaa (Hub 2,0★ oppi 4).

JUURISYY. Eksakti DP ratkaisee XI:n ILMAN 3/klubi-rajaa ja antaa todistetun
ylarajan (mitattu **327.38**). Jos sen ratkaisu rikkoo katon, KOKO ratkaisu
heitettiin pois ja pudottiin ahneeseen tayttoon + 1-swap-paikallishakuun.
Ahne lahtokohta jaa kauas eika 1-swap paase sielta pois.

KORJAUS. Rikkovat pelaajat SIIRRETAAN (`_repair_club_cap`) sen sijaan etta
ratkaisu heitettaisiin pois. Nolla lisa-DP-kutsua. Mitattu tuotannolla:
310.77 -> **325.71**; `beats_benchmark` True -> False, `percentile`
100.0 -> 99.0, `gap_to_optimal_xp` 0.0 -> 3.29.

FIKSTUURI EI OLE TUOTANTODATAA eika yksi kasin valittu tapaus. Ensimmainen
versio tasta testista kaytti yhta kasin rakennettua poolia, ja mittasin etta
ahne varapolku loysi siina SAMAN tuloksen (506.00 molemmilla) — negatiivinen
kontrolli olisi siis lapaissut vaikka korjausta ei olisi ajettu lainkaan
(muisti: kontrolli-lapaisi-tyhjana). Nyt pooli generoidaan siemenesta ja
testit ajetaan niilla siemenilla joilla polut MITATUSTI eroavat.
"""
from __future__ import annotations

import itertools
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import fpl_rate_team as rt


def _p(pid: int, pos: int, club: int, price: int, xp: float) -> dict:
    return {
        "id": pid,
        "web_name": "P%d" % pid,
        "element_type": pos,
        "club": club,
        "team_short": "T%02d" % club,
        "price": price,
        "xp_horizon_total": xp,
        "xp_per_gw": xp / 6.0,
        "xmins": 80.0,      # `_playable` vaatii oikeat minuutit
        "p_start": 0.9,
    }


def pooli(seed: int) -> list[dict]:
    """Pooli jossa yksi seura on selvasti paras JA kallis.

    Molemmat ehdot tarvitaan: kalleus kiristaa budjetin niin etta ahne tayttö
    tekee huonoja valintoja, ja paremmuus saa rajoitteettoman DP:n
    keskittamaan yli katon. Ilman kalleutta ahne loytaa saman tuloksen eika
    testi mittaa mitaan.
    """
    r = random.Random(seed)
    pid = itertools.count(1)
    out: list[dict] = []
    for pos, n in ((2, 4), (3, 4), (4, 3)):
        for _ in range(n):
            out.append(_p(next(pid), pos, 1, r.randint(95, 125),
                          r.uniform(52, 62)))
    for club in range(2, 16):
        for pos, n in ((1, 1), (2, 3), (3, 3), (4, 2)):
            for _ in range(n):
                out.append(_p(next(pid), pos, club, r.randint(40, 110),
                              r.uniform(8, 48)))
    for club in range(2, 6):
        out.append(_p(next(pid), 1, club, 40, r.uniform(14, 22)))
    return out


# Siemenet joilla korjauspolku MITATUSTI parantaa tulosta (skannattu 0-39,
# 14 osumaa 40:sta). Jokainen `build_optimal_squad`-kutsu ajaa eksaktin DP:n
# (~1-2 s), joten koko lista ajetaan vain HALVOISSA testeissa; raskaat
# kayttavat otosta. Ilman tata rajausta koko sarja hidastui 38 s -> 6 min 47 s,
# ja hidas portti on portti joka ohitetaan.
EROTTAVAT = [1, 4, 8, 10, 11, 15, 19, 20, 21, 26, 27, 28, 33, 36]
OTOS = EROTTAVAT[:4]


def _laillinen(squad: list[dict]) -> bool:
    if len(squad) != 15 or len({p["id"] for p in squad}) != 15:
        return False
    if rt._shape_of(squad) != rt.SQUAD_QUOTA:
        return False
    if any(n > rt.MAX_PER_CLUB for n in rt._club_counts(squad).values()):
        return False
    return sum(p["price"] for p in squad) <= rt.BUDGET_TENTHS


def _kasin_rakennettu(pool: list[dict]) -> list[dict] | None:
    """Ahne laillinen 15 ILMAN optimoijaa. Tarkoituksella tyhma: jos tama
    voittaa optimoijan, optimoija on rikki. Tasan nain kavi tuotannossa.

    BUDJETTITIETOINEN. Ensimmainen versio otti vain parhaat xP:n mukaan ja
    ylitti budjetin kalliilla fikstuurilla, jolloin funktio palautti None ja
    KOKO testi skippasi — 14 skippia 14:sta. Kontrolli joka ei aja on sama
    kuin ei kontrollia.
    """
    # 1. HALVIN LAILLINEN 15. Tama mahtuu aina jos pooli riittaa, joten
    #    kontrolli ei voi palauttaa None:a budjetin takia.
    #
    #    Ensimmainen versio meni toisin pain (paras xP ensin, varaus poolin
    #    halvimmasta per positio) ja loppui kesken kaikilla siemenilla: kun
    #    halvimmat on jo otettu, jaljella olevat ovat kalliimpia ja varaus
    #    aliarvioi. Se on TASAN sama vikaluokka jonka optimoija itse
    #    dokumentoi ("globaali minimi aliarvioi", korjaus b 14.8) — ja
    #    seurauksena 14 testia 14:sta skippasi eli kontrolli ei ajanut.
    squad: list[dict] = []
    klubit: dict = {}
    for pos, maara in sorted(rt.SQUAD_QUOTA.items()):
        otettu = 0
        for p in sorted((q for q in pool if q["element_type"] == pos),
                        key=lambda q: (q["price"], -q["xp_horizon_total"])):
            if otettu == maara:
                break
            if klubit.get(p["club"], 0) >= rt.MAX_PER_CLUB:
                continue
            squad.append(p)
            klubit[p["club"]] = klubit.get(p["club"], 0) + 1
            otettu += 1
        if otettu != maara:
            return None
    kaytetty = sum(p["price"] for p in squad)
    if kaytetty > rt.BUDGET_TENTHS:
        return None

    # 2. Ahne paivitys: vaihda huonoin parempaan niin kauan kuin raha ja
    #    seurakatto sallivat. Tyhma mutta laillinen — ja jos tama voittaa
    #    optimoijan, optimoija on rikki.
    idt = {p["id"] for p in squad}
    parani = True
    while parani:
        parani = False
        for i, out in enumerate(sorted(
                squad, key=lambda q: q["xp_horizon_total"])):
            j = next(k for k, q in enumerate(squad) if q["id"] == out["id"])
            ilman = squad[:j] + squad[j + 1:]
            raha = rt.BUDGET_TENTHS - sum(p["price"] for p in ilman)
            kk = rt._club_counts(ilman)
            ehdokkaat = [q for q in pool
                         if q["element_type"] == out["element_type"]
                         and q["id"] not in idt
                         and q["price"] <= raha
                         and kk.get(q["club"], 0) < rt.MAX_PER_CLUB
                         and q["xp_horizon_total"] > out["xp_horizon_total"]]
            if not ehdokkaat:
                continue
            tilalle = max(ehdokkaat, key=lambda q: q["xp_horizon_total"])
            idt.discard(out["id"])
            idt.add(tilalle["id"])
            squad = ilman + [tilalle]
            parani = True
            break
    return squad


def _ilman_korjausta(pool: list[dict], monkeypatch) -> float:
    monkeypatch.setattr(rt, "_repair_club_cap", lambda *a, **k: None)
    rt._OPTIMAL_XP_CACHE.clear()
    res = rt.build_optimal_squad(pool)
    monkeypatch.undo()
    rt._OPTIMAL_XP_CACHE.clear()
    return res["xi_xp"] if res["xi"] else -1.0


# --- fikstuurin oma kontrolli ----------------------------------------------

@pytest.mark.parametrize("seed", OTOS)
def test_fikstuuri_pakottaa_korjauspolun(seed):
    """Tyhjyyskontrolli: jos rajoitteeton optimi EI riko kattoa, testi
    mittaisi eri koodipolkua kuin se jota varten se on kirjoitettu."""
    P = pooli(seed)
    ex, _tot = rt._unconstrained_optimum(
        P, rt.BUDGET_TENTHS - 150, [], bench_pool=P)
    assert ex, seed
    assert not rt._squad_clubs_ok(ex), (
        "siemen %d ei riko klubikattoa" % seed)


# --- itse invariantti -------------------------------------------------------

@pytest.mark.parametrize("seed", OTOS)
def test_benchmark_ei_havia_kadella_rakennetulle(seed):
    """🔴 TAMA ON SE VIKA. Vertailukohdan on oltava vahintaan yhta hyva kuin
    mika tahansa laillinen runko jonka voimme rakentaa suoraan."""
    P = pooli(seed)
    rt._OPTIMAL_XP_CACHE.clear()
    res = rt.build_optimal_squad(P)
    assert res["xi"], seed
    kasin = _kasin_rakennettu(P)
    assert kasin is not None, (
        "siemenesta %d ei saatu kasin laillista runkoa - kontrolli ei aja"
        % seed)
    assert _laillinen(kasin), seed
    kasin_xp = sum(p["xp_horizon_total"] for p in rt.optimal_xi(kasin))
    assert res["xi_xp"] >= kasin_xp - 1e-6, (
        "siemen %d: benchmark %.2f havisi kasin rakennetulle %.2f"
        % (seed, res["xi_xp"], kasin_xp))


@pytest.mark.parametrize("seed", OTOS)
def test_palautettu_runko_on_laillinen(seed):
    rt._OPTIMAL_XP_CACHE.clear()
    res = rt.build_optimal_squad(pooli(seed))
    assert res["xi"], seed
    assert _laillinen(res["xi"] + res["bench"]), seed


@pytest.mark.parametrize("seed", OTOS)
def test_ei_ylita_todistettua_ylarajaa(seed):
    """Korjaus ei saa keksia pisteita: ylaraja patee mille tahansa
    lailliselle rungolle."""
    P = pooli(seed)
    rt._OPTIMAL_XP_CACHE.clear()
    res = rt.build_optimal_squad(P)
    _ex, ylaraja = rt._unconstrained_optimum(
        P, rt.BUDGET_TENTHS - 150, [], bench_pool=P)
    assert ylaraja != rt._NEG
    assert res["xi_xp"] <= ylaraja + 1e-6, (
        "siemen %d: %.2f > ylaraja %.2f" % (seed, res["xi_xp"], ylaraja))


# --- negatiivinen kontrolli: korjaus oikeasti tekee tyon --------------------

@pytest.mark.parametrize("seed", OTOS[:2])
def test_negatiivinen_kontrolli_ilman_korjausta_huononee(seed, monkeypatch):
    """Mutaatio: kytke korjaus pois ja varmista etta tulos HUONONEE. Ilman
    tata testi lapaisisi vaikka korjausta ei ajettaisi lainkaan — ja
    ensimmainen versio tasta testista teki tasan sen."""
    P = pooli(seed)
    rt._OPTIMAL_XP_CACHE.clear()
    kanssa = rt.build_optimal_squad(P)["xi_xp"]
    ilman = _ilman_korjausta(P, monkeypatch)
    assert kanssa > ilman + 0.5, (
        "siemen %d: korjaus ei paranna (%.2f vs %.2f)" % (seed, kanssa, ilman))


# --- _repair_club_cap suoraan -----------------------------------------------

def test_korjaus_poistaa_ylityksen():
    xi = [_p(900 + i, 2, 1, 50, 60.0) for i in range(4)] + \
         [_p(910 + i, 3, 2 + i, 50, 40.0) for i in range(7)]
    pool = xi + [_p(950, 2, 9, 50, 55.0), _p(951, 2, 9, 50, 10.0)]
    korjattu = rt._repair_club_cap(xi, pool, rt.BUDGET_TENTHS)
    assert korjattu is not None
    assert all(n <= rt.MAX_PER_CLUB
               for n in rt._club_counts(korjattu).values())
    # paras korvaaja valitaan, ei ensimmainen
    assert any(p["id"] == 950 for p in korjattu)
    assert not any(p["id"] == 951 for p in korjattu)


def test_korjaus_ei_vaihda_lukittuja():
    """Fit checker lukitsee pelaajia; korjaus ei saa pudottaa niita."""
    xi = [_p(900 + i, 2, 1, 50, 60.0 - i) for i in range(4)] + \
         [_p(910 + i, 3, 2 + i, 50, 40.0) for i in range(7)]
    pool = xi + [_p(950, 2, 9, 50, 55.0)]
    assert rt._repair_club_cap(
        xi, pool, rt.BUDGET_TENTHS, {900, 901, 902, 903}) is None


def test_korjaus_kunnioittaa_budjettia():
    xi = [_p(900 + i, 2, 1, 50, 60.0) for i in range(4)] + \
         [_p(910 + i, 3, 2 + i, 50, 40.0) for i in range(7)]
    pool = xi + [_p(950, 2, 9, 999, 55.0)]   # ainoa korvaaja liian kallis
    assert rt._repair_club_cap(
        xi, pool, sum(p["price"] for p in xi), set()) is None


def test_jo_laillinen_palautuu_sellaisenaan():
    xi = [_p(900 + i, 2, 1 + i, 50, 60.0) for i in range(4)] + \
         [_p(910 + i, 3, 5 + i, 50, 40.0) for i in range(7)]
    korjattu = rt._repair_club_cap(xi, list(xi), rt.BUDGET_TENTHS)
    assert korjattu is not None
    assert {p["id"] for p in korjattu} == {p["id"] for p in xi}


@pytest.mark.parametrize("per_seura", [4, 5, 6])
def test_kierrokset_johdetaan_ylityksesta(per_seura):
    """🔴 Kierrosmaara oli aluksi VAKIO 3, jolloin useamman seuran ylitys
    palautti None:n eli jatti korjauksen tekematta hiljaa."""
    xi = [_p(900 + i, 2, 1, 50, 60.0 - i) for i in range(per_seura)]
    xi += [_p(920 + i, 3, 2, 50, 50.0 - i) for i in range(11 - len(xi))]
    pool = list(xi)
    for i in range(10):
        pool.append(_p(960 + i, 2, 10 + i, 50, 55.0 - i))
        pool.append(_p(980 + i, 3, 10 + i, 50, 45.0 - i))
    korjattu = rt._repair_club_cap(xi, pool, rt.BUDGET_TENTHS)
    assert korjattu is not None, per_seura
    assert len(korjattu) == 11
    assert all(n <= rt.MAX_PER_CLUB
               for n in rt._club_counts(korjattu).values())
