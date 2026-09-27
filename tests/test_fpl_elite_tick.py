# -*- coding: utf-8 -*-
"""EO-PUTKI-N200 (27.9.2026): elite ownership -ajurin paatos joka kauden
vaiheessa (saanto 6a kohta 3: invariantti mitataan synteettisilla vaiheilla,
ei vain nykyhetkessa).

Tausta: GW5:n EO menetettiin, koska sijoitusotos jai ottamatta GW4:n jalkeen.
Ajuri paattaa bootstrapin kierrostiloista itse, eika vaihe jaa muistin varaan.
"""
from __future__ import annotations

import datetime as dt

import pytest

from scripts.fpl_elite_tick import paatos

UTC = dt.timezone.utc


def _events(finished_upto: int, data_checked_upto: int, deadlines: dict[int, str]):
    return [{"id": g, "deadline_time": d,
             "finished": g <= finished_upto, "data_checked": g <= data_checked_upto}
            for g, d in deadlines.items()]


# Oikeat 26/27-deadlinet (bootstrap 27.9): GW5 18.9, GW6 10.10, GW7 17.10.
DL = {5: "2026-09-18T17:30:00Z", 6: "2026-10-10T10:00:00Z", 7: "2026-10-17T10:00:00Z"}


def t(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s).replace(tzinfo=UTC)


def test_vaihe_kierros_valmis_ennen_seuraavaa_deadlinea_ottaa_otoksen():
    """27.9: GW5 valmis + tarkistettu, GW6:n deadline 10.10 edessa."""
    ev = _events(5, 5, DL)
    assert paatos(ev, {"rank_after_gw": 3}, {"picks_gameweek": 4}, t("2026-09-27T14:00"))[:2] == ("snapshot", 5)


def test_vaihe_otos_otettu_odotetaan_deadlinea():
    ev = _events(5, 5, DL)
    toimi, gw, syy = paatos(ev, {"rank_after_gw": 5}, {"picks_gameweek": 4}, t("2026-10-01T12:00"))
    assert toimi is None and "ei tehtavaa" in syy


def test_vaihe_deadline_mennyt_hakee_valinnat():
    """10.10 deadlinen jalkeen: otos GW5:n jalkeen, EO GW4 -> GW6-pickit."""
    ev = _events(5, 5, DL)
    assert paatos(ev, {"rank_after_gw": 5}, {"picks_gameweek": 4}, t("2026-10-10T16:00"))[:2] == ("picks", 6)


def test_vaihe_kesken_kierroksen_valinnat_jo_haettu():
    ev = _events(5, 5, DL)
    toimi, _, _ = paatos(ev, {"rank_after_gw": 5}, {"picks_gameweek": 6}, t("2026-10-11T12:00"))
    assert toimi is None


def test_vaihe_kierros_valmis_mutta_data_tarkistamatta_ei_ota_otosta():
    """finished=True mutta data_checked=False: bonukset voivat viela muuttaa
    sijoituksia -> otos odottaa."""
    ev = _events(6, 5, DL)
    toimi, _, _ = paatos(ev, {"rank_after_gw": 5}, {"picks_gameweek": 6}, t("2026-10-13T08:00"))
    assert toimi is None


def test_vaihe_gradattu_ottaa_seuraavan_otoksen():
    ev = _events(6, 6, DL)
    assert paatos(ev, {"rank_after_gw": 5}, {"picks_gameweek": 6}, t("2026-10-14T08:00"))[:2] == ("snapshot", 6)


def test_myohassa_ei_oteta_kehapaatelmaa():
    """GW4:n jalkeen otos jai ottamatta ja GW5:n deadline meni (tasan 27.9:n
    tilanne GW5:lle): ajuri EI ota otosta vaan kertoo aaneen."""
    dl = {4: "2026-09-12T10:00:00Z", 5: "2026-09-18T17:30:00Z", 6: "2026-10-10T10:00:00Z"}
    ev = [{"id": 4, "deadline_time": dl[4], "finished": True, "data_checked": True},
          {"id": 5, "deadline_time": dl[5], "finished": False, "data_checked": False},
          {"id": 6, "deadline_time": dl[6], "finished": False, "data_checked": False}]
    toimi, _, syy = paatos(ev, {"rank_after_gw": 3}, {"picks_gameweek": 4}, t("2026-09-19T08:00"))
    assert toimi is None and syy.startswith("MYOHASSA")


def test_valinnat_ennen_otosta_eivat_ole_kehapaatelma():
    """Picks vaatii tasan otoksen N-1: vanhempi otos -> ei pickeja."""
    ev = _events(5, 5, DL)
    toimi, _, _ = paatos(ev, {"rank_after_gw": 4}, {"picks_gameweek": 4}, t("2026-10-10T16:00"))
    assert toimi != "picks"


@pytest.mark.parametrize("snap,own", [(None, None), ({}, {})])
def test_puuttuvat_artefaktit_eivat_kaada(snap, own):
    ev = _events(5, 5, DL)
    assert paatos(ev, snap, own, t("2026-09-27T14:00"))[:2] == ("snapshot", 5)


def test_kauden_viimeinen_kierros():
    ev = [{"id": 38, "deadline_time": "2027-05-23T14:00:00Z", "finished": True, "data_checked": True}]
    toimi, _, syy = paatos(ev, {"rank_after_gw": 37}, {"picks_gameweek": 38}, t("2027-05-25T08:00"))
    assert toimi is None and "viimeinen" in syy
