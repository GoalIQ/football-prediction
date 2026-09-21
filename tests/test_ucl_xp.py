"""Portti: UCL Fantasyn xP (src/models/ucl_xp.py + scripts/build_ucl_xp.py).

Tausta 21.9.2026: saannot JOHDETTU UEFAn syotteen omista pisteista (557/557
pelannutta MD1:ssa selittyy kokonaislukukertoimilla). Jos UEFA muuttaa
saantoja, `tarkista_saannot` kaataa buildin - tama tiedosto varmistaa etta
tarkistus oikeasti huomaa muutoksen.

Minuuttimalli: MD1-takatestissa joukkueen aloitustodennakoisyydet
summautuivat 6,2-11,7:aan, vaikka avauksessa on tasan 11 -> `tayta`.
"""
from __future__ import annotations

import pytest

from src.models import ucl_xp as X
from src.models.dixon_coles import DixonColesModel


def _rivi(skill, mins, totPts, **k):  # noqa: E302
    base = {"skill": skill, "minsPlyd": mins, "totPts": totPts, "gS": 0, "assist": 0,
            "cS": 0, "gC": 0, "yC": 0, "rC": 0, "oG": 0, "pS": 0, "pC": 0, "pE": 0,
            "saves": 0, "pM": 0, "bR": 0, "gOB": 0, "mOM": 0, "pDName": "x"}
    base.update(k)
    return base


# MD1 26/27: UEFAn syotteen AIDOT rivit (players_90_en_2.json, haettu 21.9.2026).
# Kattavat jokaisen saantotyypin: nollapeli, torjunnat, paastetyt, riistot,
# kaukaa-maali, alle 60 min, ansaittu rangaistus, oma maali, punainen.
MD1_RIVIT = [
    {"skill": 4, "minsPlyd": 90, "totPts": 12, "gS": 2, "assist": 0, "cS": 0, "gC": 0, "yC": 1, "rC": 0, "oG": 0, "pS": 0, "pC": 0, "pE": 0, "saves": 0, "pM": 0, "bR": 0, "gOB": 0, "mOM": 1, "pDName": "E. Haaland"},
    {"skill": 1, "minsPlyd": 90, "totPts": 7, "gS": 0, "assist": 0, "cS": 1, "gC": 0, "yC": 0, "rC": 0, "oG": 0, "pS": 0, "pC": 0, "pE": 0, "saves": 3, "pM": 0, "bR": 0, "gOB": 0, "mOM": 0, "pDName": "D. Raya"},
    {"skill": 1, "minsPlyd": 90, "totPts": 2, "gS": 0, "assist": 0, "cS": 0, "gC": 2, "yC": 0, "rC": 0, "oG": 0, "pS": 0, "pC": 0, "pE": 0, "saves": 3, "pM": 0, "bR": 0, "gOB": 0, "mOM": 0, "pDName": "J. Oblak"},
    {"skill": 2, "minsPlyd": 80, "totPts": 14, "gS": 1, "assist": 0, "cS": 1, "gC": 0, "yC": 0, "rC": 0, "oG": 0, "pS": 0, "pC": 0, "pE": 0, "saves": 0, "pM": 0, "bR": 5, "gOB": 1, "mOM": 0, "pDName": "A. Davies"},
    {"skill": 2, "minsPlyd": 90, "totPts": 8, "gS": 0, "assist": 0, "cS": 1, "gC": 0, "yC": 0, "rC": 0, "oG": 0, "pS": 0, "pC": 0, "pE": 0, "saves": 0, "pM": 0, "bR": 7, "gOB": 0, "mOM": 0, "pDName": "Gabriel"},
    {"skill": 3, "minsPlyd": 25, "totPts": 4, "gS": 0, "assist": 1, "cS": 0, "gC": 0, "yC": 0, "rC": 0, "oG": 0, "pS": 0, "pC": 0, "pE": 0, "saves": 0, "pM": 0, "bR": 0, "gOB": 0, "mOM": 0, "pDName": "C. Tzolis"},
    {"skill": 3, "minsPlyd": 90, "totPts": 15, "gS": 1, "assist": 2, "cS": 0, "gC": 0, "yC": 0, "rC": 0, "oG": 0, "pS": 0, "pC": 0, "pE": 0, "saves": 0, "pM": 0, "bR": 3, "gOB": 1, "mOM": 0, "pDName": "L. Yamal"},
    {"skill": 4, "minsPlyd": 90, "totPts": 13, "gS": 2, "assist": 0, "cS": 0, "gC": 0, "yC": 0, "rC": 0, "oG": 1, "pS": 0, "pC": 0, "pE": 1, "saves": 0, "pM": 0, "bR": 0, "gOB": 0, "mOM": 1, "pDName": "S. Guirassy"},
    {"skill": 2, "minsPlyd": 87, "totPts": -1, "gS": 0, "assist": 0, "cS": 0, "gC": 5, "yC": 0, "rC": 1, "oG": 0, "pS": 0, "pC": 0, "pE": 0, "saves": 0, "pM": 0, "bR": 6, "gOB": 0, "mOM": 0, "pDName": "O. Bjørtuft"},
    {"skill": 3, "minsPlyd": 0, "totPts": 0, "gS": 0, "assist": 0, "cS": 0, "gC": 0, "yC": 0, "rC": 0, "oG": 0, "pS": 0, "pC": 0, "pE": 0, "saves": 0, "pM": 0, "bR": 0, "gOB": 0, "mOM": 0, "pDName": "ei pelannut"},
]


def test_saannot_selittavat_md1_rivit():
    ok, n, huonot = X.tarkista_saannot(MD1_RIVIT)
    assert (ok, n) == (9, 9), huonot


def test_saantomuutos_huomataan():
    """Jos UEFA nostaisi hyokkaajan maalin 5 pisteeseen, rivi ei enaa selity."""
    muutettu = [dict(MD1_RIVIT[0], totPts=14)]
    ok, n, huonot = X.tarkista_saannot(muutettu)
    assert (ok, n) == (0, 1) and huonot


def test_tayta_summa_ja_katto():
    arvot = {"a": 0.9, "b": 0.8, "c": 0.4, "d": 0.1, "e": 0.0}
    out = X.tayta(arvot, 2.8, 0.95)
    assert abs(sum(out.values()) - 2.8) < 1e-9
    assert max(out.values()) <= 0.95 + 1e-12
    assert out["e"] == 0.0, "nollasta ei synny aloittajaa"
    assert out["c"] > out["d"] * 3.9, "suhteet sailyvat katon alapuolella"


def test_tayta_ei_ylita_kun_mahdotonta():
    out = X.tayta({"a": 0.5, "b": 0.5}, 11.0, 0.95)
    assert all(v <= 0.95 + 1e-12 for v in out.values())


@pytest.mark.parametrize("minuutit,esiintymiset,odotus", [
    (450, 5, (5.0, 0.0)),      # taysi aloittaja
    (90, 5, (0.0, 5.0)),       # pelkka vaihtaja (5 x 18)
    (0, 0, (0.0, 0.0)),
])
def test_aloitukset_minuuteista(minuutit, esiintymiset, odotus):
    a, v = X.aloitukset_minuuteista(minuutit, esiintymiset)
    assert (round(a, 6), round(v, 6)) == odotus


def test_minuuttiarvio_johdonmukainen():
    m = X.minuuttiarvio(0.8, 0.1, 1.0)
    assert m["p60"] <= m["p_aloitus"]
    assert abs(m["min"] - (0.8 * X.MIN_ALOITUS + 0.1 * X.MIN_VAIHTO)) < 1e-9
    nolla = X.minuuttiarvio(0.8, 0.1, 0.0)
    assert nolla["min"] == 0 and nolla["p60"] == 0 and nolla["p1_59"] == 0


def _dc():
    t = ["A", "B"]
    return DixonColesModel(attack={"A": 0.3, "B": -0.2}, defence={"A": -0.1, "B": 0.2},
                           home_advantage=0.25, home_advantage_per_team={k: 0.0 for k in t},
                           rho=-0.05, teams_=t, per_team_home_adv=False, model_type_="dc")


def test_joukkue_odotus_todennakoisyydet():
    r = X.joukkue_odotus(_dc(), "A", "B")
    assert 0 < r["A"]["cs"] < 1 and 0 < r["B"]["cs"] < 1
    assert r["A"]["xg"] == pytest.approx(r["B"]["xga"])
    assert r["A"]["cs"] > r["B"]["cs"], "vahvempi kotijoukkue pitaa nollan useammin"
    assert r["A"]["gc2"] >= 0


def test_pelipaikan_saannot_komponenteissa():
    jo = X.joukkue_odotus(_dc(), "A", "B")["A"]
    mins = X.minuuttiarvio(0.9, 0.0, 1.0)
    kw = dict(joukkue=jo, minuutit=mins, g90=0.2, a90=0.1, yc90=0.1, riisto3_90=0.3,
              kaukaa_osuus=0.1, torjunnat_per_paastetty=2.5, p_mom=0.0)
    fwd = X.xp_pelaajalle("FWD", **kw)
    gk = X.xp_pelaajalle("GK", **kw)
    assert fwd["komponentit"]["nollapeli"] == 0, "hyokkaaja ei saa nollapelipisteita"
    assert gk["komponentit"]["torjunnat"] > 0
    assert gk["komponentit"]["maalit"] == 0, "GK:n maalisaantoa ei ole havaittu -> 0"
    nolla = X.xp_pelaajalle("MID", **{**kw, "minuutit": X.minuuttiarvio(0.9, 0.0, 0.0)})
    assert nolla["xp"] == 0


def test_understat_seurat_osuvat():
    """CL 26/27:n 21 paasarjaseuraa: fd.org-nimi -> Understatin nimi.
    Understat-nimet mitattu 21.9 getLeagueData-vastauksista."""
    from scripts.build_ucl_xp import understat_seura
    parit = {
        ("Manchester City FC", "ENG"): "Manchester City",
        ("FC Internazionale Milano", "ITA"): "Inter",
        ("FC Bayern München", "GER"): "Bayern Munich",
        ("RB Leipzig", "GER"): "RasenBallsport Leipzig",
        ("Real Betis Balompié", "ESP"): "Real Betis",
        ("Lille OSC", "FRA"): "Lille",
        ("Racing Club de Lens", "FRA"): "Lens",
        ("Paris Saint-Germain FC", "FRA"): "Paris Saint Germain",
        ("Club Atlético de Madrid", "ESP"): "Atletico Madrid",
        ("Como 1907", "ITA"): "Como",
    }
    liigan_seurat = {
        "ENG": ["Manchester City", "Manchester United", "Arsenal", "Aston Villa", "Liverpool"],
        "ITA": ["Inter", "AC Milan", "Como", "Napoli", "Roma"],
        "GER": ["Bayern Munich", "RasenBallsport Leipzig", "Borussia Dortmund", "VfB Stuttgart"],
        "ESP": ["Real Betis", "Atletico Madrid", "Real Madrid", "Barcelona", "Villarreal"],
        "FRA": ["Lille", "Lens", "Paris Saint Germain", "Marseille"],
    }
    for (fd, maa), us in parit.items():
        assert understat_seura(fd, maa, liigan_seurat[maa]) == us, fd
