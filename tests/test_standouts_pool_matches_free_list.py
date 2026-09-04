"""Portti: standouts-kortin pooli on ilmaispinnan GW-listan osajoukko.

VILLEN HUOMIO 4.9.2026: kortti nimesi Andersonin "safest pickiksi", mutta
hanta ei ollut ilmaissivun GW3-listalla eika projected-XI-kortilla. Syy oli
kaksi listaa kahdella saannolla: `src/models/fpl_gw_xp.top_projected()`
soveltaa `MAX_PER_CLUB`ia (Villen paatos 30.8: ilman kattoa GW3:n top 20 oli
10/20 Man City), ja kortti rakensi oman poolinsa omalla silmukallaan ilman
kattoa. Cityn kolme parasta olivat Haaland, Guehi ja Foden - Anderson oli
neljas, eli kortin lukija ei loytanyt hanta mistaan muualta meidan
pinnoiltamme.

Poolin PITAA olla osajoukko, ei sama joukko: kortti suodattaa lisaksi
`p_start >= MIN_P_START`, koska penkkilainen ei ole "pick".
"""
from __future__ import annotations

from scripts.render_standouts_card import MIN_P_START, _pool, pick_standouts
from src.models.fpl_gw_xp import club_of, top_projected


def _p(pid: int, name: str, club: str, xp: float, p_start: float = 0.9,
       gw: int = 3, status: str = "a") -> dict:
    return {"id": pid, "web_name": name, "team": club, "team_short": club,
            "pos": "MID", "element_type": 3, "price": 60, "status": status,
            "p_start": p_start, "xmins": 80,
            "gameweeks": [{"gw": gw, "xp": xp}],
            "xp_dist": {"gw": gw, "n": 2000, "mean": xp, "p_haul": 0.1,
                        "p_blank": 0.2, "p10": 2, "median": 4, "p90": 9,
                        "haul_pts": 10, "blank_pts": 2}}


# Viisi saman seuran pelaajaa, laskeva xP: vain kolme parasta saa lapaista.
FIVE = [_p(1, "A", "MCI", 8.0), _p(2, "B", "MCI", 7.0), _p(3, "C", "MCI", 6.0),
        _p(4, "D", "MCI", 5.0), _p(5, "E", "MCI", 4.5),
        _p(6, "F", "LIV", 6.5), _p(7, "G", "MUN", 6.2), _p(8, "H", "ARS", 5.9)]


def test_seurakatto_patee_kortin_pooliin() -> None:
    nimet = [p["web_name"] for p in _pool(FIVE) if p["team_short"] == "MCI"]
    assert nimet == ["A", "B", "C"], nimet


def test_neljas_saman_seuran_ei_paase_valinnaksi() -> None:
    """Tasmalleen Andersonin tapaus: neljas Cityn pelaaja ei saa olla tiili."""
    s = pick_standouts(FIVE)
    valitut = {v["web_name"] for v in s.values() if v}
    assert "D" not in valitut and "E" not in valitut, valitut


def test_pooli_on_sivun_listan_osajoukko() -> None:
    """Yleinen invariantti: mita tahansa kortti nostaa, sen on oltava
    joukossa jonka sivun lukija olisi kelpuuttanut."""
    sivu = {p["id"] for p in top_projected(FIVE, 3, len(FIVE))}
    kortti = {p["id"] for p in _pool(FIVE)}
    assert kortti <= sivu, kortti - sivu


def test_p_start_raja_on_yha_voimassa() -> None:
    """Negatiivinen kontrolli: katto ei saa korvata p_start-rajaa."""
    penkki = FIVE + [_p(9, "Bench", "TOT", 9.9, p_start=0.2)]
    assert "Bench" not in {p["web_name"] for p in _pool(penkki)}
    assert "Bench" in {p["web_name"] for p in top_projected(penkki, 3, 99)}


def test_estolista_tulee_samalta_lukijalta() -> None:
    """Thiaw-esto ei ole enaa taman tiedoston oma kopio."""
    ps = FIVE + [_p(10, "M.Thiaw", "NEW", 9.9)]
    assert "M.Thiaw" not in {p["web_name"] for p in _pool(ps)}


def test_status_suodattuu() -> None:
    ps = FIVE + [_p(11, "Injured", "EVE", 9.9, status="i")]
    assert "Injured" not in {p["web_name"] for p in _pool(ps)}


def test_pooli_tyhjenee_hallitusti_jos_kierrosta_ei_voi_paatella() -> None:
    """Kaksi eri xp_dist-kierrosta: kortti ei saa arvata kumpi on oikea."""
    sekava = [_p(1, "A", "MCI", 8.0, gw=3), _p(2, "B", "LIV", 7.0, gw=4)]
    assert _pool(sekava) == []
