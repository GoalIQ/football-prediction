# -*- coding: utf-8 -*-
"""Portti: kapteenin kerroin tulee TILIN chipista, ei vakiosta.

🔴 MITATTU TUOTANNOSTA 7.9.2026. `goaliq.app/fpl#gw-calls` tulosti GW3:sta
kaksi riviä peräkkäin, ja ne olivat keskenään ristiriidassa:

    "The squad played a Triple Captain in GW3."
    "Model squad captain | Haaland | captain, points doubled | 9 |
     18 as captain"

Oikea luku on 27. Kerroin oli kovakoodattu kahteen paikkaan: gradaajaan
(`gw_calls.grade`, `int(pts) * 2`) ja sivugeneraattoriin (`_call_said`
palautti merkkijonon "captain, points doubled").

VIKA EI OLLUT UUSI. Sama asia korjattiin 6.9 porttikierroksella löydöksenä
A2 - mutta vain `lib/gwReviewCard.ts`:aan, eli mobiiliin ja SPA:han. Web ja
gradaaja jäivät jälkeen (muisti: sama-vaite-monella-renderointipolulla).
Siksi tämä portti mittaa KAIKKI polut, ei sitä yhtä joka korjattiin.

Toinen puoli on tunnistus: kerroin koskee vain tapausta jossa kutsuttu
pelaaja oli myös tilin oikea kapteeni. GW2:ssa `model_captain` oli Guéhi
mutta tili kapteenoi B.Fernandesin, joten "4 as captain" olisi väite
tapahtumasta jota ei tapahtunut.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.models import gw_calls as gwc
from scripts import build_fpl_page as bp

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "data" / "gw_calls.json"


def _rivi(chip, entry_captain, call_pid=411, pts=9):
    return {
        "gw": 3,
        "entry_actual": {"chip": chip, "captain": entry_captain},
        "calls": [{"call": "model_captain", "player_id": call_pid,
                   "web_name": "Haaland", "team_short": "MCI",
                   "metric": "gw_xp", "value": 7.92}],
        "graded": {"provisional": False, "by_call": {
            "model_captain": {"points": pts, "minutes": 90, "met": None}}},
    }


# --------------------------------------------------------------- yksi lukija

@pytest.mark.parametrize("chip,odotettu", [
    ("3xc", 3),
    ("wildcard", 2),
    ("bboost", 2),
    ("freehit", 2),
    ("manager", 2),
    (None, 2),
    ("", 2),
    ("jokin_uusi_chip_2027", 2),   # tuntematon -> oletus, ei keksitty kerroin
])
def test_kerroin_tulee_chipista(chip, odotettu):
    rivi = _rivi(chip, 411)
    kerroin, oma = gwc.captain_multiplier(rivi, rivi["calls"][0])
    assert (kerroin, oma) == (odotettu, True), chip


def test_kutsuttu_pelaaja_ei_ollut_tilin_kapteeni():
    """GW2:n tosielaman tapaus: kutsu Guehi, tili kapteenoi B.Fernandesin."""
    rivi = _rivi("wildcard", entry_captain=426, call_pid=388, pts=2)
    kerroin, oma = gwc.captain_multiplier(rivi, rivi["calls"][0])
    assert oma is False
    assert kerroin == 2


def test_3xc_ei_kolminkertaista_vaaraa_pelaajaa():
    """NEGATIIVINEN KONTROLLI: chip ei riita, pelaajan on oltava sama.

    Ilman tata kerroin voisi kolminkertaistaa kutsun jota tili ei
    kapteenoinut, eli vaittaa pisteita joita kukaan ei saanut."""
    rivi = _rivi("3xc", entry_captain=999, call_pid=411)
    kerroin, oma = gwc.captain_multiplier(rivi, rivi["calls"][0])
    assert (kerroin, oma) == (2, False)


def test_entry_actual_puuttuu_kokonaan():
    """Puuttuva tieto ei saa tuottaa vaitetta. GW1:lla ei ole entry_actualia."""
    rivi = {"gw": 1, "calls": [{"call": "model_captain", "player_id": 411}]}
    kerroin, oma = gwc.captain_multiplier(rivi, rivi["calls"][0])
    assert (kerroin, oma) == (2, False)


# ------------------------------------------------------- kaikki pinnat samaa

@pytest.mark.parametrize("chip,sana,tulos", [
    ("3xc", "tripled", "27 as captain"),
    ("wildcard", "doubled", "18 as captain"),
])
def test_sivun_molemmat_solut_kertovat_saman_kertoimen(chip, sana, tulos):
    """"What it said" ja "Result" eivat saa olla eri mielta samalla rivilla."""
    rivi = _rivi(chip, 411)
    said = bp._call_said(rivi["calls"][0], rivi)
    pts, res = bp._call_result(rivi["calls"][0], rivi["graded"], rivi)
    assert sana in said, said
    assert res == tulos, res


def test_sivu_ei_vaita_kapteenointia_jota_ei_tapahtunut():
    rivi = _rivi("wildcard", entry_captain=426, call_pid=388, pts=2)
    said = bp._call_said(rivi["calls"][0], rivi)
    _, res = bp._call_result(rivi["calls"][0], rivi["graded"], rivi)
    assert "if captained" in said, said
    assert res == "4 if captained", res


def test_sivu_ei_lue_johdettua_kenttaa_artefaktista():
    """🔴 Sivu johtaa kertoimen chipista, EI lue `captain_total`ia.

    Gradaaja ei kirjoita lopullista rivia uudelleen, joten vanhalla
    kertoimella laskettu `captain_total` jaisi lokiin ikuisesti - ja jos
    sivu lukisi sen, se perisi virheen. Tama testi syottaa TAHALLAAN vaaran
    `captain_total`in ja vaatii etta sivu ohittaa sen.
    """
    rivi = _rivi("3xc", 411)
    rivi["graded"]["by_call"]["model_captain"]["captain_total"] = 18
    _, res = bp._call_result(rivi["calls"][0], rivi["graded"], rivi)
    assert res == "27 as captain", res


# ----------------------------------------------------- oikea loki, oikea data

def test_julkaistu_loki_on_linjassa_chippien_kanssa():
    """Portti oikeaa artefaktia vasten, ei vain fikstuuria.

    Tama on se testi joka olisi kaatanut 7.9:n vian: `captain_total` 18
    kierroksella jolla `entry_actual.chip` on `3xc`.
    """
    log = json.loads(LOG.read_text(encoding="utf-8"))
    virheet = []
    for rivi in log.get("gameweeks") or []:
        g = (rivi.get("graded") or {}).get("by_call", {}).get("model_captain")
        call = next((c for c in rivi.get("calls") or []
                     if c.get("call") == "model_captain"), None)
        if not g or not call or g.get("points") is None:
            continue
        kerroin, _ = gwc.captain_multiplier(rivi, call)
        odotettu = int(g["points"]) * kerroin
        if g.get("captain_total") != odotettu:
            virheet.append(
                f"GW{rivi.get('gw')}: captain_total {g.get('captain_total')}, "
                f"chip {(rivi.get('entry_actual') or {}).get('chip')!r} "
                f"-> odotettu {odotettu}")
    assert not virheet, "\n  ".join(virheet)


def test_kontrolli_loki_ei_ole_tyhja():
    """NEGATIIVINEN KONTROLLI: portti ylla lapaisisi tyhjalla lokilla
    (muisti: kontrolli-lapaisi-tyhjana)."""
    log = json.loads(LOG.read_text(encoding="utf-8"))
    gradatut = [r for r in log.get("gameweeks") or []
                if (r.get("graded") or {}).get("by_call", {})
                .get("model_captain", {}).get("points") is not None]
    assert len(gradatut) >= 2, len(gradatut)
    # ja ainakin yhdella on chip, muuten portti ei mittaa kertoimen haaraa
    assert any((r.get("entry_actual") or {}).get("chip") for r in gradatut)


def test_migraatio_on_idempotentti():
    """Korjaus lopulliselle riville ei saa ajautua joka ajossa uudelleen."""
    rivi = _rivi("3xc", 411)
    gwc._korjaa_kapteenin_kerroin(rivi)
    eka = json.dumps(rivi, sort_keys=True)
    gwc._korjaa_kapteenin_kerroin(rivi)
    assert json.dumps(rivi, sort_keys=True) == eka
    assert rivi["graded"]["by_call"]["model_captain"]["captain_total"] == 27


def test_migraatio_ei_koske_pisteisiin_eika_tulokseen():
    """Kapea migraatio: se saa taydentaa kertoimen eika mitaan muuta."""
    rivi = _rivi("3xc", 411)
    rivi["graded"]["by_call"]["model_captain"]["met"] = True
    rivi["graded"]["graded_at"] = "2026-09-07T13:28:52Z"
    gwc._korjaa_kapteenin_kerroin(rivi)
    g = rivi["graded"]
    assert g["by_call"]["model_captain"]["points"] == 9
    assert g["by_call"]["model_captain"]["met"] is True
    assert g["graded_at"] == "2026-09-07T13:28:52Z"
