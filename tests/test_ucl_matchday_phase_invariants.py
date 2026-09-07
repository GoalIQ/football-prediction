# -*- coding: utf-8 -*-
"""Invariantti mitataan JOKA VAIHEESSA, ei nykyhetkessa (CLAUDE.md 6a, 3).

🔴 MIKSI TAMA TIEDOSTO ON OLEMASSA. `/ucl`-osio shipattiin 7.9.2026 ja se
oli mitattuna moitteeton - siina kauden vaiheessa. Samana iltana mitattiin
UEFAn syotteesta:

    players_90_en_1.json -> 200, 3 654 799 tavua
    players_90_en_2.json -> 403
    players_90_en_3.json -> 403

`build()` valitsee pelaajatiedoston sen kierroksen mukaan jonka deadline on
seuraavana. MD1:n deadline oli 8.9.2026 18:45 UTC. Klo 18:46 valinta olisi
kaantynyt MD2:een, jonka tiedostoa ei ole viela olemassa, ja koko ajo olisi
kuollut `SystemExit`iin: artefakti ja kolme julkista sivua olisivat
jaatyneet tasan silla hetkella kun MD1:n liikenne saapuu - ja jaatyminen
olisi nakynyt lukijalle vanhentuvana leimana, ei virheena.

Yksikaan olemassa oleva testi ei olisi voinut loytaa sita, koska ne kaikki
ajavat NYKYHETKEN kellolla. Tama tiedosto ajaa saman funktion synteettisilla
kauden vaiheilla: ennen ensimmaista deadlinea, sen jalkeen, kesken kauden,
ja viimeisen kierroksen jalkeen.

Vrt. muistit `ehto-ei-vanhene-teksti-vanhenee` ja
`ulkoinen-data-kausivaihdos-sokeus`.
"""
from __future__ import annotations

import datetime as dt

import pytest

from scripts import ingest_ucl as iu

KAUSI = 90
# MD1 8.9.2026 18:45 UTC, MD8 27.1.2027 - kuten mitattu syotteesta 7.9.
DEADLINET = [
    "09/08/26 06:45:00 PM", "10/13/26 06:45:00 PM", "10/20/26 06:45:00 PM",
    "11/03/26 06:45:00 PM", "11/24/26 06:45:00 PM", "12/08/26 06:45:00 PM",
    "01/20/27 06:45:00 PM", "01/27/27 06:45:00 PM",
]

VAIHEET = [
    ("ennen MD1:n deadlinea",
     dt.datetime(2026, 9, 7, 15, 0, tzinfo=dt.timezone.utc), 1),
    ("minuutti MD1:n deadlinen jalkeen",
     dt.datetime(2026, 9, 8, 18, 46, tzinfo=dt.timezone.utc), 2),
    ("MD1:n ja MD2:n valissa",
     dt.datetime(2026, 9, 25, 12, 0, tzinfo=dt.timezone.utc), 2),
    ("kesken kauden",
     dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.timezone.utc), 5),
    ("viimeisen kierroksen jalkeen",
     dt.datetime(2027, 2, 1, 12, 0, tzinfo=dt.timezone.utc), 1),
]


def _fx() -> dict:
    return {"data": {"value": [
        {"mdId": i + 1, "gameday": 1, "gdIsCurrent": 0, "gdIsLocked": 0,
         "deadline": dl, "matches": []}
        for i, dl in enumerate(DEADLINET)]}}


def _pelaajat_doc(nyt: dt.datetime) -> dict:
    """Syote jonka oma aikaleima on annettu hetki."""
    return {
        "meta": {"timestamp": {"utcTime": nyt.strftime("%m/%d/%Y %I:%M:%S %p")}},
        "data": {"value": {"playerList": [
            {"id": i, "pDName": "P%d" % i, "tId": 1 + i % 36, "tName": "Club",
             "skill": 1 + i % 4, "value": 5.0, "selPer": 1.0, "totPts": 0,
             "minsPlyd": 0, "teamPlayed": 0, "pStatus": ""}
            for i in range(1, 1163)]}},
    }


def _md_polusta(polku: str) -> int:
    return int(polku.rsplit("_", 1)[1].split(".")[0])


def _asenna_syote(monkeypatch, nyt: dt.datetime, saatavilla: set) -> list:
    """UEFA-korvike jossa VAIN `saatavilla`-kierrosten tiedostot vastaavat."""
    kutsutut = []

    def _hae(polku: str):
        kutsutut.append(polku)
        if polku.startswith("fixtures/"):
            return _fx()
        if polku.startswith("teams/"):
            return {"data": {"value": []}}
        if polku.startswith("players/"):
            return (_pelaajat_doc(nyt) if _md_polusta(polku) in saatavilla
                    else None)          # None = UEFAn 403
        return None

    monkeypatch.setattr(iu, "_hae", _hae)
    monkeypatch.setattr(iu, "loyda_kausi", lambda nyt_: (KAUSI, _fx()))
    return kutsutut


@pytest.mark.parametrize("nimi,nyt,odotettu_md", VAIHEET)
def test_build_ei_kaadu_missaan_kauden_vaiheessa(monkeypatch, nimi, nyt,
                                                 odotettu_md):
    """Vain MD1:n tiedosto on olemassa - kuten oikeasti oli 7.9.2026."""
    _asenna_syote(monkeypatch, nyt, saatavilla={1})
    doc = iu.build(nyt)
    m = doc["meta"]
    assert m["matchday"] == odotettu_md, nimi + ": vaara seuraava kierros"
    assert m["players_matchday"] == 1, nimi + ": piti pudota MD1:een"
    assert m["players_matchday_is_fallback"] is (odotettu_md != 1), nimi
    assert m["players"] == 1162, nimi


@pytest.mark.parametrize("nimi,nyt,odotettu_md", VAIHEET)
def test_kun_oma_kierros_on_julkaistu_fallbackia_ei_kayteta(
        monkeypatch, nimi, nyt, odotettu_md):
    """POSITIIVINEN KONTROLLI. Ilman tata testi ylla lapaisisi myos jos
    `hae_pelaajat` palauttaisi AINA MD1:n (muisti:
    kontrolli-lapaisi-tyhjana)."""
    _asenna_syote(monkeypatch, nyt, saatavilla=set(range(1, 9)))
    doc = iu.build(nyt)
    assert doc["meta"]["players_matchday"] == odotettu_md, nimi
    assert doc["meta"]["players_matchday_is_fallback"] is False, nimi


def test_yksikaan_kierros_ei_vastaa_kaataa_ajon(monkeypatch):
    """FAIL-CLOSED. Alaspain kavely ei saa muuttua hiljaiseksi tyhjaksi."""
    nyt = dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.timezone.utc)
    _asenna_syote(monkeypatch, nyt, saatavilla=set())
    with pytest.raises(SystemExit) as e:
        iu.build(nyt)
    assert "pelaajasyotetta ei saatu" in str(e.value)


def test_haku_kavelee_alaspain_eika_ylospain(monkeypatch):
    """Fallback saa lukea VAIN olemassa olevaa dataa samalta kaudelta.

    Ylospain kavely olisi arvaus tulevasta kierroksesta; alaspain kavely on
    kierros joka on oikeasti lukittu tai pelattu.
    """
    nyt = dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.timezone.utc)
    kutsutut = _asenna_syote(monkeypatch, nyt, saatavilla={3})
    doc = iu.build(nyt)
    assert doc["meta"]["matchday"] == 5
    assert doc["meta"]["players_matchday"] == 3
    pyydetyt = [_md_polusta(p) for p in kutsutut if p.startswith("players/")]
    assert pyydetyt == [5, 4, 3], pyydetyt
    assert max(pyydetyt) <= 5, "haku ei saa kysya tulevaa kierrosta"


def test_tuoreusportti_ei_kaada_ajoa_kun_tarjoillaan_aiempaa_kierrosta(
        monkeypatch):
    """Lukitun kierroksen tiedosto EI paivity, ja se on odotettu tila.

    72 h:n tuoreusportti on olemassa siksi etta huomaisimme UEFAn lopettaneen
    paivittamisen tai meidan lukevan vaaraa resurssia. Kumpikaan ei ole totta
    kun tarjoilemme tietoisesti aiempaa kierrosta, joten portti ei saa kaataa
    ajoa siina tilassa - se muuttaisi tunnetun tilan katkokseksi.
    """
    nyt = dt.datetime(2026, 10, 5, 12, 0, tzinfo=dt.timezone.utc)
    vanha = dt.datetime(2026, 9, 8, 18, 0, tzinfo=dt.timezone.utc)   # 27 vrk
    _asenna_syote(monkeypatch, vanha, saatavilla={1})
    doc = iu.build(nyt)
    assert doc["meta"]["players_matchday_is_fallback"] is True
    assert doc["meta"]["players_matchday"] == 1


def test_tuoreusportti_kaataa_yha_kun_ELAVA_kierros_on_jaatynyt(monkeypatch):
    """NEGATIIVINEN KONTROLLI edelliselle: portti ei saa muuttua fail-openiksi.

    Kun tarjoiltu kierros ON se jonka deadline on seuraavana, jaatynyt
    aikaleima tarkoittaa yha ettei artefaktia kirjoiteta jaatyneen paalle.
    """
    nyt = dt.datetime(2026, 10, 5, 12, 0, tzinfo=dt.timezone.utc)
    vanha = dt.datetime(2026, 9, 8, 18, 0, tzinfo=dt.timezone.utc)
    _asenna_syote(monkeypatch, vanha, saatavilla=set(range(1, 9)))
    with pytest.raises(SystemExit) as e:
        iu.build(nyt)
    assert "aikaleima" in str(e.value)
