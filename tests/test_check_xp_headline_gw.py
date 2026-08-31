"""Portti otsikkokierrokselle (31.8.2026).

Portti ilman negatiivista kontrollia on sokea: se lapaisisi myos tyhjana tai
aina-vihreana. Nama testit ajavat molemmat suunnat.
"""
from __future__ import annotations

from scripts.check_xp_headline_gw import tarkista


def _payload(dl, dist_gw, comp_gw, horizon=(3, 4, 5), n=3):
    return {
        "meta": {"deadline_gameweek": dl},
        "players": [{
            "xp_dist": ({"gw": dist_gw} if dist_gw is not None else None),
            "components_gw": comp_gw,
            "gameweeks": [{"gw": g} for g in horizon],
        } for _ in range(n)],
    }


def test_oikea_kierros_lapaisee():
    assert tarkista(_payload(3, 3, 3)) == []


def test_31_8_tilanne_kaatuu():
    """deadline 3, jakauma ja komponentit 2 - tasmalleen livena mitattu tila."""
    v = tarkista(_payload(3, 2, 2))
    assert len(v) == 2
    assert "xp_dist.gw != deadline_gameweek (3)" in v[0] and "GW2 3 pelaajalla" in v[0]
    assert "components_gw" in v[1]


def test_pelkka_jakauma_vaarin_riittaa_kaatamaan():
    v = tarkista(_payload(3, 2, 3))
    assert len(v) == 1 and "xp_dist" in v[0]


def test_pelkat_komponentit_vaarin_riittavat_kaatamaan():
    v = tarkista(_payload(3, 3, 2))
    assert len(v) == 1 and "components_gw" in v[0]


def test_blank_gw_saa_olla_none():
    """xp_dist puuttuu kun otsikkokierros on blank - se ei ole vika."""
    assert tarkista(_payload(3, None, 3)) == []


def test_otsikko_horisontin_ulkopuolella_kaatuu():
    v = tarkista(_payload(9, 9, 9, horizon=(3, 4, 5)))
    assert any("ei ole horisontissa" in x for x in v)


# --- fail-closed: puuttuva tieto ei ole "kunnossa" ------------------------

def test_puuttuva_deadline_kaataa_ei_lapaise():
    """Hiljainen lapipaasto oli tasan se miten tama vika eli 519 pelaajalla."""
    v = tarkista({"meta": {}, "players": [{"xp_dist": {"gw": 2}}]})
    assert len(v) == 1 and "deadline_gameweek puuttuu" in v[0]


def test_tyhja_players_kaataa_ei_lapaise():
    """Kontrolli joka lapaisee tyhjana on sokea portti
    (muisti: kontrolli-lapaisi-tyhjana)."""
    v = tarkista({"meta": {"deadline_gameweek": 3}, "players": []})
    assert len(v) == 1 and "tyhja" in v[0]


def test_yksikin_vaara_pelaaja_riittaa():
    """Enemmisto oikein ei ole kunnossa: yksi rivi on yksi vaara vaite."""
    p = _payload(3, 3, 3, n=5)
    p["players"][2]["xp_dist"] = {"gw": 2}
    v = tarkista(p)
    assert len(v) == 1 and "GW2 1 pelaajalla" in v[0]
