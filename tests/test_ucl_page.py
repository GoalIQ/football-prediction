# -*- coding: utf-8 -*-
"""Portit /ucl-osion sivuille."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UCL = ROOT / "ucl"
SIVUT = ("index.html", "prices.html", "team-news.html")


def _html(nimi: str) -> str:
    p = UCL / nimi
    if not p.exists():
        pytest.skip(f"{nimi} ei ole viela generoitu")
    return p.read_text(encoding="utf-8")


@pytest.mark.parametrize("nimi", SIVUT)
def test_sivun_luokat_ovat_olemassa_tyyliarkissa(nimi):
    """🔴 TAMA VIKA TEHTIIN JA MITATTIIN RENDEROIDYSTA KUVASTA 7.9.2026.

    Ensimmainen versio kirjoitti `<div class="tablewrap">` ja
    `<table class="sortable">`. Kumpaakaan luokkaa ei ole olemassa - oikeat
    ovat `tblwrap` ja `lb`. Yhden kirjaimen ero maksoi KOLME asiaa
    kerralla, eika mikaan huutanut:

        - taulukon tyylit (padding, erotinviivat, otsikkorivi)
        - lajittelu       (`scripts/table_tools.py` sitoo sen `table.lb`:hen)
        - positiosuodatin (sama tiedosto, sama valitsin)

    Keksitty luokkanimi on validia HTML:aa. Ainoa tapa havaita se on
    verrata sivun luokkia siihen CSS:aan joka sivulla oikeasti on.
    """
    h = _html(nimi)
    tyyli = "\n".join(re.findall(r"<style>(.*?)</style>", h, re.S))
    assert len(tyyli) > 2000, "sivulla ei ole tyyliarkkia"

    # CSS:ssa maaritellyt luokat + JS:n lisaamat (ne eivat ole HTML:ssa).
    maaritellyt = set(re.findall(r"\.([a-zA-Z][\w-]*)", tyyli))
    kaytetyt = set()
    for m in re.findall(r'class="([^"]+)"', h):
        kaytetyt.update(m.split())

    puuttuvat = sorted(kaytetyt - maaritellyt)
    assert not puuttuvat, (
        f"{nimi}: luokkia joita tyyliarkissa EI OLE: {puuttuvat}. "
        "Keksitty luokkanimi on validia HTML:aa ja saa nolla tyylia - "
        "tarkista oikea nimi lahteesta, ala arvaa.")


@pytest.mark.parametrize("nimi", SIVUT)
def test_taulukko_saa_lajittelun_ja_suodattimen(nimi):
    """`table_tools.js` sitoo molemmat valitsimeen `table.lb`. Muu luokka
    tuottaa taulukon joka nayttaa oikealta eika reagoi klikkiin."""
    h = _html(nimi)
    assert '<table class="lb">' in h, (
        f"{nimi}: taulukko ei ole luokkaa `lb`, joten lajittelu ja "
        "suodatin eivat kytkeydy")


@pytest.mark.parametrize("nimi", SIVUT)
def test_sivulla_on_kaavio(nimi):
    """Villen kysymys 7.9: 'Grafiikoita?'. Mitattu vastaus oli silloin: ei
    yhtaan kaaviota koko sivustolla."""
    h = _html(nimi)
    kaaviot = re.findall(r'<svg viewBox="0 0 \d+ \d+"', h)
    assert kaaviot, f"{nimi}: ei yhtaan kaaviota"
    assert 'class="chart-scroll"' in h, f"{nimi}: kaavio ilman vieritinta"


def test_hub_kaaviot_ovat_kaikki_kolme():
    h = _html("index.html")
    for otsikko in ("Ownership by price", "Price range by position",
                    "Players unavailable by club"):
        assert f'aria-label="{otsikko}' in h, f"puuttuu kaavio: {otsikko}"


@pytest.mark.parametrize("nimi", SIVUT)
def test_pistesarake_kertoo_kaudesta_jos_luvut_ovat_viime_kaudelta(nimi):
    """Sarakeotsikko ja kentta tulevat `ucl_phase.pistekentta()`sta samasta
    kutsusta. Jos artefaktissa ei ole `points`-kenttaa, otsikon ON
    sanottava 'last season'."""
    import json
    from src.models import ucl_phase as up
    d = ROOT / "data" / "ucl_fantasy.json"
    if not d.exists():
        pytest.skip("artefaktia ei ole")
    doc = json.loads(d.read_text(encoding="utf-8"))
    kentta, otsikko = up.pistekentta(doc)
    h = _html(nimi)
    if kentta == "prev_season_points":
        assert "Pts (last season)" in h, (
            f"{nimi}: luvut ovat viime kaudelta mutta sarake ei sano sita")
        assert "xP" not in h, (
            f"{nimi}: sivulla on xP-sarake vaikka kautta ei ole pelattu")


def test_hub_ei_lupaa_taman_kauden_lukuja_esikaudella():
    """Muisti: honest-data-labels. Copy ei saa luvata dataa jota ei ole."""
    import json
    from src.models import ucl_phase as up
    d = ROOT / "data" / "ucl_fantasy.json"
    if not d.exists():
        pytest.skip("artefaktia ei ole")
    doc = json.loads(d.read_text(encoding="utf-8"))
    if up.vaihe(doc) != up.ESIKAUSI:
        pytest.skip("kausi on alkanut")
    h = _html("index.html")
    assert "No matchday of this season has been played yet" in h, (
        "hub ei sano etta kautta ei ole pelattu")


def test_saatavuuskaavion_jarjestys_vastaa_copyn_lupausta():
    """🔴 MITATTU KUVASTA. Ensimmainen versio lajitteli poissaolojen
    SUMMALLA, jolloin karkeen nousi klubi jolla oli eniten rekisteroimatta
    jatettyja pelaajia - ei eniten loukkaantumisia. Copy sanoi 'clubs with
    the most', ja lukija luki sen loukkaantumisiksi.

    Jarjestys ja naytetty luku vastaavat samaan kysymykseen (muisti:
    uusi-sorttiulottuvuus-muuttaa-sarakkeen).
    """
    import json
    from collections import Counter, defaultdict
    d = ROOT / "data" / "ucl_fantasy.json"
    if not d.exists():
        pytest.skip("artefaktia ei ole")
    doc = json.loads(d.read_text(encoding="utf-8"))

    per_klubi = defaultdict(Counter)
    for p in doc["players"]:
        if p["status"] in ("injured", "suspended", "doubtful", "not_in_squad"):
            per_klubi[p["team_code"]][p["status"]] += 1

    h = _html("index.html")
    # Kaavion rivijarjestys: klubikoodit y-jarjestyksessa.
    # HUOM: aria-label esiintyy KAHDESTI (figure-kaarija + svg), joten
    # `split(...)[1]` osui 117 merkin valifragmenttiin ja loysi 0 klubia.
    # Luetaan svg-elementti eksplisiittisesti.
    m = re.search(r'<svg [^>]*aria-label="Players unavailable by club"'
                  r'[^>]*>(.*?)</svg>', h, re.S)
    assert m, "saatavuuskaaviota ei loytynyt sivulta"
    lohko = m.group(1)
    koodit = re.findall(r'text-anchor="end">([A-Z]{2,4})</text>', lohko)
    assert len(koodit) >= 8, f"kaaviossa vain {len(koodit)} klubia"

    def toimittava(k: str) -> int:
        c = per_klubi[k]
        return c["injured"] + c["suspended"] + c["doubtful"]

    arvot = [toimittava(k) for k in koodit]
    assert arvot == sorted(arvot, reverse=True), (
        f"kaavio ei ole jarjestetty toimittavien poissaolojen mukaan: "
        f"{list(zip(koodit, arvot))}")
    assert all(v > 0 for v in arvot), (
        "kaaviossa on klubi jolla ei ole yhtaan loukkaantunutta, "
        "pelikieltoa tai kyseenalaista - se on rekisterointikirjanpitoa")

    assert "ordered by injuries, suspensions and doubts" in h, (
        "copy ei kerro mika jarjestys on")


@pytest.mark.parametrize("nimi", SIVUT)
def test_ei_em_dashia(nimi):
    """Muisti: em-dash-ja-pinta-pariteetti."""
    h = _html(nimi)
    runko = h.split("<body>", 1)[-1]
    assert "—" not in runko, f"{nimi}: em dash julkisessa tekstissa"


@pytest.mark.parametrize("nimi", SIVUT)
def test_sivu_sanoo_ettei_ole_uefan(nimi):
    """Virallisen syotteen kayttaminen ei tee meista virallista lahdetta."""
    h = _html(nimi)
    assert "not affiliated" in h or "GoalIQ is an independent" in h or \
        "statistical estimates" in h, f"{nimi}: ei erottautumislausetta"
