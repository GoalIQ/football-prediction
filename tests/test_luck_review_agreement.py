# -*- coding: utf-8 -*-
"""Sama vaite kahdesta lahteesta: `last_finished` ja `gw-review` (1.9.2026).

MIKSI TAMA ON OLEMASSA: 1.9 rakennettiin `last_finished`-lohko pitch-nakymalle
tarkistamatta ensin, etta "This week" -valilehdella oli JO `gw-review`-kortti
joka nayttaa saman vaitteen ("108 scored against 50.9 projected +57.1").
Molemmat jaivat, koska ne vastaavat eri kysymykseen:

  gw-review        yksi kortti, rivit KERTOIMELLISINA (projected/actual on jo
                   kerrottu) -> paras ja huonoin kutsu luetaan suoraan
  last_finished    kentta ja jakokortti, rivit KERTOIMETTOMINA + erillinen
                   `multiplier` -> tuomiomerkki lasketaan pelaajan omasta
                   suorituksesta, ei kapteeninauhasta

Muoto EROAA tarkoituksella. SUMMAT EIVAT SAA EROTA. Tama testi ajaa molemmat
samoilla syotteilla ja kaatuu jos ne erkanevat - se on ainoa asia joka estaa
kahta pintaa vaittamasta eri lukua samasta kierroksesta.

🔴 Lisaksi ne laskevat pistemaaran ERI TAVALLA, ja se on tarkoitus:
  gw-review     summaa omat rivinsa
  last_finished lukee FPL:n oman `entry_history.points`in
Jos ne eroavat, FPL on eri mielta kuin me - juuri sellainen ero halutaan nahda.
"""
import pytest

from src.models import fpl_gw_review as review
from src.models import fpl_rate_team as rt

# XI: 1 kapteeni (x2) + 2 kenttapelaajaa. Penkki: 1 pelaaja joka PELASI
# (kerroin 0 -> ei saa nakya kummankaan summassa) ja 1 joka ei pelannut.
PICKS = {
    "active_chip": None,
    "entry_history": {"points": 61, "event_transfers_cost": 0, "points_on_bench": 9},
    "picks": [
        {"element": 1, "multiplier": 2, "is_captain": True, "is_vice_captain": False},
        {"element": 2, "multiplier": 1, "is_captain": False, "is_vice_captain": True},
        {"element": 3, "multiplier": 1, "is_captain": False, "is_vice_captain": False},
        {"element": 4, "multiplier": 0, "is_captain": False, "is_vice_captain": False},
        {"element": 5, "multiplier": 0, "is_captain": False, "is_vice_captain": False},
    ],
}
FROZEN = {1: 4.0, 2: 3.0, 3: 6.5, 4: 2.0}          # 5 puuttuu: ei freezea
POINTS = {1: 23, 2: 4, 3: 1, 4: 9}                  # 5 puuttuu: ei pelannut
INFO = {i: {"web_name": f"P{i}", "team_short": "XXX", "pos": "MID"} for i in range(1, 6)}

BOOTSTRAP = {
    "events": [{"id": 2, "finished": True, "data_checked": True,
                "average_entry_score": 50}],
    "elements": [{"id": i, "web_name": f"P{i}", "element_type": 3} for i in range(1, 6)],
}


@pytest.fixture
def wired(monkeypatch):
    monkeypatch.setattr(rt, "get_entry_picks", lambda e, g: PICKS)
    monkeypatch.setattr(rt.fpl_actuals, "points_for", lambda g, s=None: POINTS)
    monkeypatch.setattr(rt.fpl_actuals, "frozen_xp_for", lambda g: FROZEN)
    monkeypatch.setattr(rt.fpl_actuals, "frozen_meta", lambda g: {})
    return None


def _both(wired_):
    lf = rt.last_finished_block(1, BOOTSTRAP, {}, "2026/27")
    rv = review.build_review(2, PICKS, FROZEN, POINTS, INFO)
    return lf, rv["review"]


def test_projisoitu_summa_on_sama(wired):
    lf, rv = _both(wired)
    # 4.0*2 + 3.0 + 6.5 = 17.5. Penkki (kerroin 0) ei ole mukana kummassakaan.
    assert lf["xp"] == pytest.approx(17.5)
    assert rv["projected"] == pytest.approx(lf["xp"]), (
        "pitch ja gw-review vaittavat eri projisoitua summaa samasta kierroksesta"
    )


def test_penkki_ei_ole_kummassakaan_summassa(wired):
    """MUTAATIO: pelaaja 4 on penkilla mutta PELASI (9 pistetta, 2.0 xP).
    Jos kerroin unohtuisi kummassa tahansa, summat eroaisivat tassa."""
    lf, rv = _both(wired)
    ilman_kerrointa = 4.0 + 3.0 + 6.5 + 2.0
    assert lf["xp"] != pytest.approx(ilman_kerrointa)
    assert rv["projected"] != pytest.approx(ilman_kerrointa)


def test_pistemaarat_eroavat_vain_odotetulla_tavalla(wired):
    """gw-review summaa omat rivinsa (23*2 + 4 + 1 = 51), last_finished lukee
    FPL:n luvun (61). Ero on TARKOITUKSELLINEN ja se on syy pitaa molemmat:
    FPL:n luku kantaa autosubit ja bonukset, meidan summamme ei.

    Testi ei vaadi niiden olevan samat - se vaatii etta kumpikin on se mika
    lupaa olevansa, jotta ero on luettavissa eika vahinko."""
    lf, rv = _both(wired)
    assert rv["actual"] == 23 * 2 + 4 + 1
    assert lf["points"] == PICKS["entry_history"]["points"]
    assert lf["points_source"] == "FPL entry history"


def test_vertailtavien_maara_ei_ole_sama_kuin_complete(wired):
    """1.9 luulin naiden olevan ristiriidassa. Ne vastaavat eri kysymykseen:

      gw-review `players_compared`  montako RUNGON pelaajaa saatiin verrattua
      last_finished `complete`      onko jokaisella PELANNEELLA freeze

    Pelaaja 5 ei pelannut, joten vertailtavia on 4/5 mutta summa on silti
    kokonainen. Ilman tata testia joku korjaa "vian" jota ei ole."""
    lf, rv = _both(wired)
    full = review.build_review(2, PICKS, FROZEN, POINTS, INFO)
    assert full["meta"]["players_compared"] == 4
    assert len(lf["players"]) == 5
    assert lf["complete"] is True
