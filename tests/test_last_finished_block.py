# -*- coding: utf-8 -*-
"""LUCK-PITCH: paattyneen kierroksen lohko (1.9.2026).

Miksi nama ovat testin arvoisia: jokainen naista epaonnistuu HILJAA.
Vaara kierros nayttaisi kesken olevan kierroksen lopullisena, kertoimeton
summa tekisi mallista systemaattisesti paremman nakoisen, ja vaillinainen
freeze antaisi erotuksen joka nayttaa oikealta muttei ole.
"""
import pytest

from src.models import fpl_rate_team as rt


def _bootstrap(events, elements=None):
    return {"events": events, "elements": elements or []}


def test_valitsee_suurimman_valmiin_ja_tarkistetun():
    bs = _bootstrap([
        {"id": 1, "finished": True, "data_checked": True},
        {"id": 2, "finished": True, "data_checked": True},
        {"id": 3, "finished": False, "data_checked": False},
    ])
    assert rt.last_finished_gameweek(bs) == 2


def test_finished_ilman_data_checkedia_ei_kelpaa():
    """NEGATIIVINEN KONTROLLI. Pisteet muuttuvat viela bonusten ja
    kurinpidon myota kunnes `data_checked` kaantyy, joten pelkka `finished`
    antaisi luvun joka vanhenee kadessa."""
    bs = _bootstrap([
        {"id": 1, "finished": True, "data_checked": True},
        {"id": 2, "finished": True, "data_checked": False},
    ])
    assert rt.last_finished_gameweek(bs) == 1


def test_ei_yhtaan_valmista_kierrosta():
    bs = _bootstrap([{"id": 1, "finished": False, "data_checked": False}])
    assert rt.last_finished_gameweek(bs) is None


# --- last_finished_block ---------------------------------------------------

PICKS = {
    "active_chip": None,
    "entry_history": {"points": 61, "event_transfers_cost": 4, "points_on_bench": 3},
    "picks": [
        {"element": 1, "multiplier": 2, "is_captain": True, "is_vice_captain": False},
        {"element": 2, "multiplier": 1, "is_captain": False, "is_vice_captain": True},
        {"element": 3, "multiplier": 0, "is_captain": False, "is_vice_captain": False},
    ],
}
ELEMENTS = [
    {"id": 1, "web_name": "Kapteeni", "element_type": 3},
    {"id": 2, "web_name": "Kentta", "element_type": 2},
    {"id": 3, "web_name": "Penkki", "element_type": 4},
]
BS = _bootstrap(
    [{"id": 2, "finished": True, "data_checked": True, "average_entry_score": 50}],
    ELEMENTS,
)


@pytest.fixture
def wired(monkeypatch):
    """Lahteet kiinnitetaan, jotta testi mittaa TATA logiikkaa eika verkkoa."""
    monkeypatch.setattr(rt, "get_entry_picks", lambda e, g: PICKS)
    monkeypatch.setattr(rt.fpl_actuals, "points_for", lambda g, s=None: {1: 23, 2: 4, 3: 9})
    monkeypatch.setattr(rt.fpl_actuals, "frozen_xp_for", lambda g: {1: 4.0, 2: 3.0, 3: 2.0})
    monkeypatch.setattr(rt.fpl_actuals, "frozen_meta", lambda g: {"frozen_at": "X", "deadline": "Y"})
    return None


def test_summa_kayttaa_kerrointa(wired):
    b = rt.last_finished_block(1, BS, {}, "2026/27")
    # 4.0*2 + 3.0*1 + 2.0*0 = 11.0 — penkki EI ole mukana.
    assert b["xp"] == 11.0
    assert b["complete"] is True


def test_penkki_ei_paase_summaan(wired, monkeypatch):
    """MUTAATIO: jos kerroin unohtuisi, penkin 2.0 nousisi summaan ja luku
    olisi 9.0 eli malli nayttaisi joka kierros paremmalta kuin se oli."""
    b = rt.last_finished_block(1, BS, {}, "2026/27")
    naive = 4.0 + 3.0 + 2.0
    assert b["xp"] != naive


def test_pistemaara_on_fpln_oma_luku(wired, monkeypatch):
    """Pisteet luetaan `entry_history`sta, EI summaamalla toteumia. Naissa
    on tarkoituksella eri luku: jos summaisimme, saisimme 23*2+4 = 50 emmeka
    FPL:n 61:ta, ja kayttajan oma FPL-tili nayttaisi eri lukua kuin me."""
    b = rt.last_finished_block(1, BS, {}, "2026/27")
    assert b["points"] == 61
    assert b["diff"] == round(61 - 11.0, 2)


def test_vaillinainen_freeze_pudottaa_erotuksen(wired, monkeypatch):
    """Pelanneelta puuttuva freeze tekisi summasta alakanttiin ja erotuksesta
    imartelevan. Silloin erotusta ei anneta lainkaan."""
    monkeypatch.setattr(rt.fpl_actuals, "frozen_xp_for", lambda g: {1: 4.0})
    b = rt.last_finished_block(1, BS, {}, "2026/27")
    assert b["complete"] is False
    assert b["xp"] is None and b["diff"] is None
    # Pistemaara sailyy: se on FPL:n oma eika riipu meidan freezestamme.
    assert b["points"] == 61


def test_ilman_toteumia_ei_lohkoa(wired, monkeypatch):
    monkeypatch.setattr(rt.fpl_actuals, "points_for", lambda g, s=None: {})
    assert rt.last_finished_block(1, BS, {}, "2026/27") is None


def test_ilman_freezea_ei_lohkoa(wired, monkeypatch):
    monkeypatch.setattr(rt.fpl_actuals, "frozen_xp_for", lambda g: {})
    assert rt.last_finished_block(1, BS, {}, "2026/27") is None


def test_entryn_puuttuvat_picksit_eivat_kaada_vastausta(wired, monkeypatch):
    def boom(e, g):
        raise rt.RateTeamError(404, "not public")
    monkeypatch.setattr(rt, "get_entry_picks", boom)
    assert rt.last_finished_block(1, BS, {}, "2026/27") is None


def test_manual_moodi_ei_saa_lohkoa(wired):
    assert rt.last_finished_block(None, BS, {}, "2026/27") is None


def test_nolla_pistetta_on_luku_eika_puuttuva(wired, monkeypatch):
    monkeypatch.setattr(rt.fpl_actuals, "points_for", lambda g, s=None: {1: 0, 2: 4, 3: 9})
    b = rt.last_finished_block(1, BS, {}, "2026/27")
    kapteeni = next(r for r in b["players"] if r["id"] == 1)
    assert kapteeni["points"] == 0, "nolla ei saa muuttua nulliksi"


def test_puuttuva_toteuma_on_null_eika_nolla(wired, monkeypatch):
    monkeypatch.setattr(rt.fpl_actuals, "points_for", lambda g, s=None: {2: 4, 3: 9})
    b = rt.last_finished_block(1, BS, {}, "2026/27")
    kapteeni = next(r for r in b["players"] if r["id"] == 1)
    assert kapteeni["points"] is None, "nolla olisi vaite, puuttuva on totuus"
