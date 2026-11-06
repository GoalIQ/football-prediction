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

def _uid(gw: int) -> str:
    return f"UID:fpl-gw{gw}-deadline@goaliq.app"


def ics_ristiriidat(dls: list[dict], loydetyt: set[str], now: dt.datetime) -> list[str]:
    """Kalenterin invariantti, joka pitaa kierroksen joka vaiheessa.

    6.11.2026: testi vertasi kalenteria artefaktin KOKO listaan. Kun phase0 jaa
    vanhaksi (Understat-katko) ja deadline menee, kalenteri pudottaa menneen
    kierroksen oikein, mutta artefakti pitaa sen listalla: testi oli punainen
    koko katkon ajan, vaikka sivu ja kalenteri olivat oikein. Mennyt kierros
    saa siis puuttua. Tuleva ei saa, eika artefaktin ulkopuolista saa olla.
    """
    kaikki = {_uid(d["gw"]) for d in dls}
    tulevat = {_uid(d["gw"]) for d in dls
               if dt.datetime.fromisoformat(d["utc"]).astimezone(dt.timezone.utc) > now}
    viat = [f"tuleva kierros puuttuu: {u}" for u in sorted(tulevat - loydetyt)]
    viat += [f"artefaktin ulkopuolella: {u}" for u in sorted(loydetyt - kaikki)]
    return viat


@pytest.mark.skipif(not ICS.exists(), reason="deadlines.ics ei viela generoitu")
def test_julkaistu_ics_vastaa_artefaktia():
    dls = _meta().get("deadlines") or []
    assert dls, "artefaktissa ei ole deadlineja -> sivu ja kalenteri ovat sokeita"
    loydetyt = set(re.findall(r"UID:\S+", ICS.read_text(encoding="utf-8")))
    assert loydetyt, "kalenteri on tyhja"
    viat = ics_ristiriidat(dls, loydetyt, dt.datetime.now(dt.timezone.utc))
    assert not viat, viat


_DLS = [{"gw": 10, "utc": "2026-11-06T18:30:00+00:00"},
        {"gw": 11, "utc": "2026-11-20T18:30:00+00:00"}]
_ENNEN = dt.datetime(2026, 11, 6, 12, 0, tzinfo=dt.timezone.utc)
_JALKEEN = dt.datetime(2026, 11, 6, 19, 0, tzinfo=dt.timezone.utc)


@pytest.mark.parametrize("now,loydetyt,ok", [
    (_ENNEN, {_uid(10), _uid(11)}, True),      # ennen deadlinea, kaikki mukana
    (_JALKEEN, {_uid(11)}, True),              # deadlinen jalkeen, mennyt pudotettu
    (_JALKEEN, {_uid(10), _uid(11)}, True),    # deadlinen jalkeen, ei viela rakennettu
    (_ENNEN, {_uid(11)}, False),               # tuleva puuttuu
    (_JALKEEN, {_uid(10)}, False),             # seuraava puuttuu
    (_JALKEEN, {_uid(11), _uid(12)}, False),   # artefaktin ulkopuolinen kierros
])
def test_kalenterin_invariantti_joka_vaiheessa(now, loydetyt, ok):
    assert (not ics_ristiriidat(_DLS, loydetyt, now)) is ok


@pytest.mark.skipif(not ICS.exists(), reason="deadlines.ics ei viela generoitu")
def test_sivu_ja_kalenteri_sanovat_saman_seuraavan_deadlinen():
    """Muisti `jakopinta-lukee-eri-tiedostoa-kuin-sivu`: kaksi pintaa samasta
    luvusta on kaksi tilaisuutta olla eri mielta."""
    dls = _meta().get("deadlines") or []
    html = SIVU.read_text(encoding="utf-8", errors="replace")
    # WP2 (1.11.2026): UTC-teksti on <time datetime>-elementissa, jonka selain
    # lokalisoi (src/local_time.py); staattinen teksti ja hetki ovat samat.
    m = re.search(r"Next deadline: Gameweek (\d+), (?:<time [^>]*>)?(\d+ \w+) at "
                  r"(\d{2}:\d{2}) UTC", html)
    assert m, "fpl.html ei kerro seuraavaa deadlinea -> paluusyy katosi sivulta"
    # Sivu lukee kellosta seuraavan kierroksen; artefaktin ensimmainen rivi voi
    # olla mennyt, kun phase0 on vanha. Haetaan siksi sivun nimeama kierros.
    rivi = next((d for d in dls if d["gw"] == int(m.group(1))), None)
    assert rivi, f"sivun kierros GW{m.group(1)} puuttuu artefaktista"
    eka = dt.datetime.fromisoformat(rivi["utc"]).astimezone(dt.timezone.utc)
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
