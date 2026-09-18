# -*- coding: utf-8 -*-
"""PARIN-SUORITUSJARJESTYS (18.9.2026): juokseva pankki ei saa kayda
miinukselle yhdellakaan askeleella.

🔴 MIKSI TAMA TESTI ON OLEMASSA (adversariaalisen tarkistajan loydos 18.9).
`best_pair` jarjestaa parin niin etta rahaa vapauttava siirto on ensin. Sita
riviä vartioi 17.9 asti VAIN lahdekoodi-grep
(`test_moottorin_budjettiehdot_lukevat_sell_pricea`), joka kieltaa
merkkijonon `(o1["price"] - i1["price"])`. Rivin voi kirjoittaa ekvivalenttiin
muotoon
    if (i1["price"] - o1["price"]) > (i2["price"] - o2["price"]):
joka on TASAN vanha, nykyhintaan nojaava vertailu - ja grep ei nae sita.
Mitattu 18.9: mutaation kanssa koko ei-slow-suite oli vihrea (4320 passed),
koska LOPPUSALDO on molemmissa jarjestyksissa sama. Vain valisaldo eroaa:
oikea [8->91, 3->90] kavelee 2 -> 1, vaara [3->90, 8->91] kavelee -1 -> 1.

Portti ei ole vahti vaan mahdottomuus (CLAUDE.md 6a.1): `plan_gw` ajaa
siirrot `bank_walk`in lapi, joka NOSTAA `TransferPlanError`in negatiivisesta
valisaldosta. Vaara jarjestys ei siis paase jaadytettyyn artefaktiin
(`meta.transfers` + `out_selling_price`/`in_price`), joka on julkinen vaite
siirroista jotka FPL olisi hyvaksynyt.

Hermeettinen: synteettiset dictit, ei verkkoa, ei levya.
"""
from __future__ import annotations

import pytest

from src.models import fpl_transfers as tr


def _p(pid, pos, price, xp, club=None, **extra):
    row = {"id": pid, "web_name": f"P{pid}", "team_short": "T",
           "element_type": pos, "club": club if club is not None else pid,
           "price": price, "owned_pct": 1.0, "xp_per_gw": xp,
           "xp_horizon_total": xp, "status": "a", "chance_next": 100,
           "gameweeks": [{"gw": 2, "opponents": [], "xp": xp}]}
    row.update(extra)
    return row


def _runko(*, def3_price=60, def3_selling=40, mid8_selling=50):
    """2 GK / 5 DEF / 5 MID / 3 FWD, eri seurat. id 3 = DEF, id 8 = MID.

    DEF 3 on se jonka hinta on NOUSSUT (myynti 4.0 < hinta 6.0): siita
    saatava raha on pienempi kuin nykyhinta lupaa, joten sen siirto on
    rahaa KULUTTAVA vaikka nykyhinnalla se nayttaisi rahaa vapauttavalta.
    """
    squad, pid = [], 1
    for pos, n in ((1, 2), (2, 5), (3, 5), (4, 3)):
        for _ in range(n):
            squad.append(_p(pid, pos, 50, 5.0, selling_price=50))
            pid += 1
    for p in squad:
        if p["id"] == 3:
            p["price"], p["selling_price"] = def3_price, def3_selling
        elif p["id"] == 8:
            p["selling_price"] = mid8_selling
    return squad


def _pooli(squad):
    # DEF 4.1 (id 90) ja MID 4.8 (id 91), molemmat selvasti parempia.
    return squad + [_p(90, 2, 41, 12.0, club=90), _p(91, 3, 48, 12.0, club=91)]


# ---------------------------------------------------------------------------
# 1. Lukija itse: yksi paikka joka ei voi palauttaa vaaraa
# ---------------------------------------------------------------------------
def _m(out_id, out_price, out_selling, in_id, in_price):
    return {"out": _p(out_id, 2, out_price, 1.0, selling_price=out_selling),
            "in": _p(in_id, 2, in_price, 1.0)}


def test_bank_walk_palauttaa_saldon_joka_askeleelta():
    walk = tr.bank_walk(0, [_m(8, 50, 50, 91, 48), _m(3, 60, 40, 90, 41)])
    assert walk == [2, 1]


def test_bank_walk_nostaa_poikkeuksen_negatiivisesta_valisaldosta():
    """Loppusaldo on 1 eli positiivinen — silti kielletty, koska FPL tekee
    siirrot yksi kerrallaan eika salli valilla negatiivista pankkia."""
    vaara = [_m(3, 60, 40, 90, 41), _m(8, 50, 50, 91, 48)]
    with pytest.raises(tr.TransferPlanError, match="askeleella 1/2"):
        tr.bank_walk(0, vaara)


def test_bank_walk_lukee_myyntihinnan_ei_nykyhintaa():
    """Sama siirto kahdella eri myyntihinnalla: nykyhinta 6.0 riittaisi
    5.5:n tulokkaaseen, myyntihinta 4.0 ei."""
    assert tr.bank_walk(0, [_m(3, 60, 60, 90, 55)]) == [5]
    with pytest.raises(tr.TransferPlanError):
        tr.bank_walk(0, [_m(3, 60, 40, 90, 55)])


def test_bank_walk_tyhjalla_listalla_on_tyhja_ei_virhe():
    assert tr.bank_walk(-0, []) == []


# ---------------------------------------------------------------------------
# 2. Kutsupaikka: plan_gw:n julkaisema jarjestys
# ---------------------------------------------------------------------------
def test_parin_jarjestys_ei_vie_valipankkia_miinukselle():
    """🔴 EROTTELEVA FIKSTUURI. Tama on se runko jolla `best_pair`in
    jarjestysrivin ekvivalentti uudelleenkirjoitus punastuu.

    Ilman `bank_walk`ia ja vaaralla jarjestyksella: moves [(3,90),(8,91)],
    valipankki -1 -> 1, loppupankki 1 — eli loppusaldoa mittaava testi
    lapaisee. Talla testilla plan_gw nostaa `TransferPlanError`in.
    """
    squad = _runko()
    step = tr.plan_gw(squad, _pooli(squad), 0, [2], 2)
    parit = [(m["out"]["id"], m["in"]["id"]) for m in step["moves"]]
    assert parit == [(8, 91), (3, 90)], parit
    assert step["bank_walk"] == [2, 1]
    assert step["bank_tenths"] == 1
    # Sama luku kahdesta suunnasta: artefaktiin kirjattavat rivit kavelevat
    # samaan saldoon kuin moottorin oma kirjanpito.
    assert tr.bank_walk(0, step["moves"]) == step["bank_walk"]


def test_plan_gw_kieltaytyy_jos_pari_annetaan_vaarassa_jarjestyksessa(monkeypatch):
    """MEKANISMITODISTUS, ei exit-koodi: pakotetaan `best_pair` palauttamaan
    parin vaarassa jarjestyksessa ja mitataan etta plan_gw KIELTAYTYY.

    Ilman `bank_walk`ia tama haara onnistuisi hiljaa ja kirjoittaisi
    artefaktiin siirtojarjestyksen jota FPL ei olisi hyvaksynyt.
    """
    oikea = tr.best_pair

    def kaannetty(*a, **kw):
        pr = oikea(*a, **kw)
        if pr is not None:
            pr = dict(pr, moves=list(reversed(pr["moves"])))
        return pr

    monkeypatch.setattr(tr, "best_pair", kaannetty)
    squad = _runko()
    with pytest.raises(tr.TransferPlanError, match="askeleella 1/2"):
        tr.plan_gw(squad, _pooli(squad), 0, [2], 2)


def test_yksittaiset_siirrot_kavelevat_myos():
    """Yksittaissiirtojen ketju kulkee saman lukijan lapi: `single_moves`in
    budjettiehto takaa ei-negatiivisen, ja `plan_gw` mittaa sen."""
    squad = _runko(def3_price=50, def3_selling=50, mid8_selling=50)
    step = tr.plan_gw(squad, _pooli(squad), 0, [2], 2)
    assert step["moves"], "fikstuurin pitaa tuottaa siirtoja"
    assert all(b >= 0 for b in step["bank_walk"])
    assert step["bank_walk"] == tr.bank_walk(0, step["moves"])


# ---------------------------------------------------------------------------
# 3. Invariantti mitataan JOKA VAIHEESSA (CLAUDE.md 6a.3)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("nimi,hinta,myynti", [
    ("hinta noussut (myynti < hinta)", 60, 40),
    ("hinta noussut vahan", 52, 51),
    ("hinta laskenut (myynti == hinta)", 45, 45),
    ("ei liiketta", 50, 50),
])
@pytest.mark.parametrize("pankki", [0, 3, 12])
@pytest.mark.parametrize("ft", [1, 2, 3])
def test_juokseva_pankki_ei_kay_miinukselle_missaan_vaiheessa(
        nimi, hinta, myynti, pankki, ft):
    """36 yhdistelmaa: hintaliike x pankkitila x FT-saldo. Testi joka on tosi
    vain TASSA vaiheessa (yksi pankki, yksi FT) on vihrea siihen asti kun se
    lakkaa olemasta tosi."""
    squad = _runko(def3_price=hinta, def3_selling=myynti)
    step = tr.plan_gw(squad, _pooli(squad), pankki, [2], ft)
    assert all(b >= 0 for b in step["bank_walk"]), (nimi, step["bank_walk"])
    assert len(step["bank_walk"]) == len(step["moves"])
    if step["moves"]:
        assert step["bank_walk"][-1] == step["bank_tenths"]
