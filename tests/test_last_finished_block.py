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

# --- ottelutulostaulu (1.9) -------------------------------------------------

def test_vs_model_lasketaan_molemmista(wired, monkeypatch):
    monkeypatch.setattr(rt, "model_squad_gw",
                        lambda g: {"entry_id": 999, "points": 50, "fpl_average": 50,
                                   "provisional": False})
    monkeypatch.setattr(rt, "_entry_identity", lambda e, g: {
        "manager_name": "Testi Nimi", "team_name": "Testi FC",
        "overall_rank": 1000, "rank_change": 250})
    b = rt.last_finished_block(1, BS, {}, "2026/27")
    assert b["model_points"] == 50
    assert b["vs_model"] == 61 - 50
    assert b["manager_name"] == "Testi Nimi"
    assert b["overall_rank"] == 1000
    assert b["rank_change"] == 250


def test_oma_rivi_ei_pelaa_itseaan_vastaan(wired, monkeypatch):
    """Jos katsottava entry ON mallin rivi, ottelua ei ole. "108 vs 108,
    voitit 0:lla" olisi holynpolya joka nayttaisi rikkinaiselta."""
    monkeypatch.setattr(rt, "model_squad_gw",
                        lambda g: {"entry_id": 1, "points": 61, "fpl_average": 50,
                                   "provisional": False})
    monkeypatch.setattr(rt, "_entry_identity", lambda e, g: {
        "manager_name": None, "team_name": None,
        "overall_rank": None, "rank_change": None})
    b = rt.last_finished_block(1, BS, {}, "2026/27")
    assert b["model_points"] is None
    assert b["vs_model"] is None


def test_puuttuva_mallirivi_pudottaa_vain_vertailun(wired, monkeypatch):
    """NEGATIIVINEN KONTROLLI: puolikas ottelu ei ole ottelu, mutta se ei saa
    pudottaa koko lohkoa - pistemaara ja kentta ovat yha oikein."""
    monkeypatch.setattr(rt, "model_squad_gw", lambda g: None)
    monkeypatch.setattr(rt, "_entry_identity", lambda e, g: {
        "manager_name": None, "team_name": None,
        "overall_rank": None, "rank_change": None})
    b = rt.last_finished_block(1, BS, {}, "2026/27")
    assert b["model_points"] is None and b["vs_model"] is None
    assert b["points"] == 61
    assert len(b["players"]) == 3


def test_identiteetin_kaatuminen_ei_kaada_lohkoa(wired, monkeypatch):
    """Nimi ja sijoitus ovat vapaaehtoisia: FPL:n entry- tai history-kutsun
    kaatuminen saa viedä ne kentat, ei koko kierroksen tulosta."""
    def boom(path):
        raise rt.RateTeamError(503, "upstream down")
    monkeypatch.setattr(rt, "_fetch_fpl", boom)
    monkeypatch.setattr(rt, "model_squad_gw", lambda g: None)
    b = rt.last_finished_block(1, BS, {}, "2026/27")
    assert b is not None
    assert b["manager_name"] is None and b["overall_rank"] is None
    assert b["points"] == 61


def test_sijoitusmuutos_on_positiivinen_kun_noustiin(monkeypatch):
    """FPL:n sijoitusluku PIENENEE kun nousee. Kentta kaantaa merkin, jotta
    kayttoliittyman ei tarvitse muistaa sita - jos merkki kaantyisi vain
    UI:ssa, toinen pinta piirtaisi nuolen vaarin paain."""
    hist = {"current": [{"event": 1, "overall_rank": 500_000},
                        {"event": 2, "overall_rank": 120_000}]}
    def fake(path):
        if path.endswith("/history/"):
            return hist
        return {"player_first_name": "A", "player_last_name": "B", "name": "T"}
    monkeypatch.setattr(rt, "_fetch_fpl", fake)
    out = rt._entry_identity(1, 2)
    assert out["overall_rank"] == 120_000
    assert out["rank_change"] == 380_000, "nousu on positiivinen luku"


def test_ensimmaisella_kierroksella_ei_ole_muutosta(monkeypatch):
    def fake(path):
        if path.endswith("/history/"):
            return {"current": [{"event": 1, "overall_rank": 500_000}]}
        return {}
    monkeypatch.setattr(rt, "_fetch_fpl", fake)
    out = rt._entry_identity(1, 1)
    assert out["overall_rank"] == 500_000
    assert out["rank_change"] is None


def test_isoin_heilahdus_nimetaan_kun_yksi_selittaa_neljasosan(wired):
    """GW2:sta mitattu: kapteeni vei 67 % koko erosta. Ilman tata rivia
    "+57 yli mallin" on mystinen luku."""
    b = rt.last_finished_block(1, BS, {}, "2026/27")
    # xp 11.0, points 61 -> diff 50.0. Kapteeni: (23-4.0)*2 = 38.0 = 76 %.
    assert b["biggest_swing"] == {"web_name": "Kapteeni", "contribution": 38.0}


def test_penkkipelaaja_ei_voi_olla_heilahdus(wired, monkeypatch):
    """Kerroin 0 = ei vaikuta summaan, joten se ei voi selittaa eroa vaikka
    olisi tehnyt eniten pisteita."""
    monkeypatch.setattr(rt.fpl_actuals, "points_for", lambda g, s=None: {1: 4, 2: 4, 3: 60})
    b = rt.last_finished_block(1, BS, {}, "2026/27")
    assert b["biggest_swing"] is None or b["biggest_swing"]["web_name"] != "Penkki"


def test_tasaisesti_jakautunut_ero_ei_saa_nimea(wired, monkeypatch):
    """NEGATIIVINEN KONTROLLI: jos mikaan yksittainen pelaaja ei selita
    neljasosaa, "suurin naista" olisi mielivaltainen eika havainto."""
    monkeypatch.setattr(rt.fpl_actuals, "points_for", lambda g, s=None: {1: 5, 2: 5, 3: 5})
    monkeypatch.setattr(rt.fpl_actuals, "frozen_xp_for", lambda g: {1: 4.5, 2: 4.5, 3: 4.5})
    b = rt.last_finished_block(1, BS, {}, "2026/27")
    assert b["biggest_swing"] is None


def test_vaillinainen_freeze_pudottaa_myos_heilahduksen(wired, monkeypatch):
    """Jos erotusta ei anneta, ei anneta senkaan selitysta."""
    monkeypatch.setattr(rt.fpl_actuals, "frozen_xp_for", lambda g: {1: 4.0})
    b = rt.last_finished_block(1, BS, {}, "2026/27")
    assert b["complete"] is False and b["biggest_swing"] is None



# --- model_entry_id (portti 2.9 k3) ----------------------------------------
# Kortin "Model 108" tarvitsee reitin: mallin FPL-entry on julkinen ja sen
# id kulkee mallin luvun mukana. Ilman mallirivia id on None, jotta kortti
# pudottaa mallisolut eika nayta lukua ilman reittia.

def test_model_entry_id_kulkee_mallin_luvun_mukana(wired, monkeypatch):
    monkeypatch.setattr(rt, "model_squad_gw", lambda g: {
        "entry_id": 116920, "points": 108, "fpl_average": 81, "provisional": False,
        "chip": "wildcard",
    })
    b = rt.last_finished_block(1, BS, {}, "2026/27")
    assert b["model_points"] == 108
    assert b["model_entry_id"] == 116920
    assert b["model_chip"] == "wildcard"


def test_provisional_mallirivi_ei_paase_kortille(wired, monkeypatch):
    monkeypatch.setattr(rt, "model_squad_gw", lambda g: {
        "entry_id": 116920, "points": 99, "fpl_average": 81, "provisional": True,
        "chip": None,
    })
    b = rt.last_finished_block(1, BS, {}, "2026/27")
    assert b["model_points"] is None
    assert b["model_entry_id"] is None
    assert b["model_chip"] is None


def test_model_entry_id_puuttuu_ilman_mallirivia(wired, monkeypatch):
    monkeypatch.setattr(rt, "model_squad_gw", lambda g: None)
    b = rt.last_finished_block(1, BS, {}, "2026/27")
    assert b["model_points"] is None
    assert b["model_entry_id"] is None
