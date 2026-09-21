# -*- coding: utf-8 -*-
"""Portti: kalenteri ja sivu eivat voi sanoa eri aikaa, eika kalenteriin
kirjoiteta mennytta tai vyohykkeetonta hetkea.

MITATTU 20.9.2026: web-kavijoista 1 520 / 1 540 kavi tasan yhtena paivana.
Kalenterimuistutus on paluusyy jota meidan ei tarvitse operoida - mutta se on
myos PYSYVA merkinta lukijan omassa kalenterissa, kuten jakokortti on pysyva
kuva. Vaara aika ei ole korjattavissa jalkikateen, joten se vartioidaan.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import pytest

from src.deadline_calendar import ics

ROOT = Path(__file__).resolve().parents[1]
PHASE0 = ROOT / "data" / "fpl_projections_phase0.json"
ICS = ROOT / "fpl" / "deadlines.ics"
SIVU = ROOT / "fpl.html"
NOW = dt.datetime(2026, 9, 20, 12, 0, tzinfo=dt.timezone.utc)


def _meta() -> dict:
    return json.loads(PHASE0.read_text(encoding="utf-8")).get("meta", {})


# --- 1. puhdas funktio: aika, menneet, rikkinaiset ------------------------

def test_ajat_ovat_utc_ja_paattyvat_zhen():
    teksti = ics([{"gw": 6, "utc": "2026-10-10T10:00:00+00:00"}], NOW)
    assert "DTSTART:20261010T100000Z" in teksti
    for rivi in teksti.splitlines():
        if rivi.startswith(("DTSTART:", "DTEND:", "DTSTAMP:")):
            assert rivi.endswith("Z"), f"{rivi}: vyohykkeeton aika kalenterissa"


def test_vyohykkeeton_syote_tulkitaan_utcksi_ei_paikalliseksi():
    """FPL julkaisee UTC:na. Jos naiivi aika tulkittaisiin koneen
    vyohykkeessa, muistutus siirtyisi buildikoneen mukaan."""
    a = ics([{"gw": 6, "utc": "2026-10-10T10:00:00"}], NOW)
    b = ics([{"gw": 6, "utc": "2026-10-10T10:00:00+00:00"}], NOW)
    assert "DTSTART:20261010T100000Z" in a
    assert re.search(r"DTSTART:\S+", a).group() == re.search(r"DTSTART:\S+", b).group()


def test_mennytta_deadlinea_ei_kirjoiteta():
    teksti = ics([{"gw": 5, "utc": "2026-09-18T17:30:00+00:00"},
                  {"gw": 6, "utc": "2026-10-10T10:00:00+00:00"}], NOW)
    assert "gw5" not in teksti and "GW5" not in teksti
    assert teksti.count("BEGIN:VEVENT") == 1


@pytest.mark.parametrize("syote", [
    None, [], [{}], [{"gw": None, "utc": "2026-10-10T10:00:00+00:00"}],
    [{"gw": 6, "utc": None}], [{"gw": 6, "utc": "ei-aikaa"}],
    [{"gw": "6", "utc": "2026-10-10T10:00:00+00:00"}],
])
def test_rikkinainen_syote_tuottaa_tyhjan_eika_vaaraa(syote):
    """Tyhja = kalenteria ei tarjota. Se on parempi kuin merkinta jonka
    aikaa ei tiedeta: sivun rivi jaa silloin myos pois."""
    assert ics(syote, NOW) == ""


def test_muistutus_on_mukana_ja_kaksi_tuntia():
    teksti = ics([{"gw": 6, "utc": "2026-10-10T10:00:00+00:00"}], NOW)
    assert "BEGIN:VALARM" in teksti and "TRIGGER:-PT120M" in teksti


def test_rivinvaihto_on_crlf():
    """RFC 5545. Pelkka LF rikkoo osan kalenteriohjelmista."""
    teksti = ics([{"gw": 6, "utc": "2026-10-10T10:00:00+00:00"}], NOW)
    assert "\r\n" in teksti and "\n\n" not in teksti.replace("\r\n", "\n\n").replace("\n\n", "\r\n")


# --- 2. julkaistu tiedosto vastaa artefaktia ja sivua ---------------------

@pytest.mark.skipif(not ICS.exists(), reason="deadlines.ics ei viela generoitu")
def test_julkaistu_ics_vastaa_artefaktia():
    dls = _meta().get("deadlines") or []
    assert dls, "artefaktissa ei ole deadlineja -> sivu ja kalenteri ovat sokeita"
    teksti = ICS.read_text(encoding="utf-8")
    odotetut = {f"UID:fpl-gw{d['gw']}-deadline@goaliq.app" for d in dls}
    loydetyt = set(re.findall(r"UID:\S+", teksti))
    assert loydetyt == odotetut, (
        "kalenteri ja artefakti eri mielta kierroksista: "
        f"vain kalenterissa {sorted(loydetyt - odotetut)}, "
        f"vain artefaktissa {sorted(odotetut - loydetyt)}")


@pytest.mark.skipif(not ICS.exists(), reason="deadlines.ics ei viela generoitu")
def test_sivu_ja_kalenteri_sanovat_saman_seuraavan_deadlinen():
    """Muisti `jakopinta-lukee-eri-tiedostoa-kuin-sivu`: kaksi pintaa samasta
    luvusta on kaksi tilaisuutta olla eri mielta."""
    dls = _meta().get("deadlines") or []
    eka = dt.datetime.fromisoformat(dls[0]["utc"]).astimezone(dt.timezone.utc)
    html = SIVU.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"Next deadline: Gameweek (\d+), (\d+ \w+) at (\d{2}:\d{2}) UTC", html)
    assert m, "fpl.html ei kerro seuraavaa deadlinea -> paluusyy katosi sivulta"
    assert int(m.group(1)) == dls[0]["gw"]
    assert m.group(3) == eka.strftime("%H:%M")
    ensimmainen_ics = re.search(r"DTSTART:(\S+)", ICS.read_text(encoding="utf-8")).group(1)
    assert ensimmainen_ics == eka.strftime("%Y%m%dT%H%M%SZ")


@pytest.mark.skipif(not ICS.exists(), reason="deadlines.ics ei viela generoitu")
def test_julkaistussa_tiedostossa_on_crlf():
    """RFC 5545 vaatii CRLF:n, ja `.gitattributes` sanoo `* text=auto eol=lf`.

    MITATTU 20.9: ensimmainen commit meni repoon LF:lla, eli julkaistu
    kalenteri olisi rikkonut tiukat kalenteriohjelmat. Korjaus on
    `*.ics -text`, ja tama testi lukee TAVUT levylta - jos joku poistaa
    saannon, se nakyy tassa eika kayttajan kalenterissa.
    """
    CRLF, LF = bytes([13, 10]), bytes([10])
    tavut = ICS.read_bytes()
    assert CRLF in tavut, "julkaistu .ics on LF-muodossa (RFC 5545 vaatii CRLF)"
    assert LF not in tavut.replace(CRLF, b""), "sekamuotoisia rivinvaihtoja"


@pytest.mark.skipif(not ICS.exists(), reason="deadlines.ics ei viela generoitu")
def test_sivulla_on_latauslinkki():
    html = SIVU.read_text(encoding="utf-8", errors="replace")
    assert 'href="/fpl/deadlines.ics"' in html, (
        "kalenteri on olemassa mutta sivulla ei ole linkkia siihen")


def test_sama_syote_tuottaa_saman_tiedoston():
    """21.9: rakennushetki DTSTAMPissa teki jokaisesta rakennuksesta eri
    tiedoston, ja rinnakkaiset builderit konfliktoivat pushissa (data-refresh
    35558945289 heitti rakennuksensa pois). Kaksi eri hetkea ennen samoja
    deadlineja -> tavulleen sama teksti."""
    dls = [{"gw": 6, "utc": "2026-10-10T10:00:00+00:00"},
           {"gw": 7, "utc": "2026-10-17T10:00:00+00:00"}]
    aamu = dt.datetime(2026, 9, 21, 0, 36, 14, tzinfo=dt.timezone.utc)
    ilta = dt.datetime(2026, 9, 21, 3, 55, 30, tzinfo=dt.timezone.utc)
    assert ics(dls, aamu) == ics(dls, ilta)


def test_kiintea_leima_on_menneisyydessa_kaikkiin_tapahtumiin_nahden():
    """Negatiivinen kontrolli: kiintea DTSTAMP ei saa olla tapahtuman jalkeen
    (luotu ennen kuin se on olemassa). Vartioi vakion arvoa, ei vain sen
    olemassaoloa."""
    from src.deadline_calendar import DTSTAMP_KIINTEA
    leima = dt.datetime.strptime(DTSTAMP_KIINTEA, "%Y%m%dT%H%M%SZ").replace(
        tzinfo=dt.timezone.utc)
    for d in _meta().get("deadlines") or []:
        assert leima < dt.datetime.fromisoformat(d["utc"]).astimezone(
            dt.timezone.utc)
