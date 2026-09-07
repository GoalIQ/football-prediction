# -*- coding: utf-8 -*-
"""Portit inline-SVG-kaavioille.

Kaavio on julkinen vaite siina missa lause. Se voi valehdella tavoilla
joita copy-portit eivat nae, koska mikaan sana ei ole vaarin. Naista
kolme on portitettu:

  1. piste joka ei mahdu domainiin KATOAA hiljaa
  2. pylvasakseli joka ei ala nollasta LIIOITTELEE eroa
  3. tyhja kaavio nayttaa NOLLALTA vaikka kyse on puuttuvasta tiedosta

Jokaisella on negatiivinen kontrolli: testi ajaa myos sen syotteen jonka
PITAA menna lapi. Ilman sita portti voisi olla vihrea siksi etta se
hylkaa kaiken (muisti: kontrolli-lapaisi-tyhjana).
"""
from __future__ import annotations

import re

import pytest

from src.viz import svg_charts as sc


def _pisteet(*xy):
    return [{"nimi": "a", "vari": sc.TEAL,
             "pisteet": [(x, y, f"{x}/{y}") for x, y in xy]}]


# --- 1. piste ei saa kadota ------------------------------------------------

def test_domainin_ulkopuolinen_piste_nostaa():
    """🔴 TAMA ON SE VIKA JOTA VASTAAN MODUULI ON RAKENNETTU. SVG piirtaa
    plottialueen ulkopuolisen ympyran ilman valitusta, ja se leikkautuu
    pois. Kaavio nayttaa taydelliselta."""
    with pytest.raises(sc.KaavioVirhe, match="ulkopuolella"):
        sc.scatter(sarjat=_pisteet((5, 10), (99, 10)),
                   x_domain=(4, 11), y_domain=(0, 20),
                   x_label="x", y_label="y", otsikko="t")


def test_kontrolli_mahtuva_piste_ei_nosta():
    """NEGATIIVINEN KONTROLLI: ilman tata edellinen testi lapaisisi myos
    silloin kun `scatter` nostaa aina."""
    svg = sc.scatter(sarjat=_pisteet((5, 10), (10.9, 19)),
                     x_domain=(4, 11), y_domain=(0, 20),
                     x_label="x", y_label="y", otsikko="t")
    assert svg.count("<circle") == 2


def test_ilman_annettua_domainia_kaikki_pisteet_mahtuvat():
    """Automaattinen domain lasketaan datasta, joten pudotus on
    mahdotonta. Mitattu UCL-datalla: Mbappe 61 % on ainoa piste yli
    50 %:n, ja se on nimenomaan se havainto jonka lukija haluaa."""
    svg = sc.scatter(sarjat=_pisteet((4, 1), (11, 61)),
                     x_label="x", y_label="y", otsikko="t")
    assert svg.count("<circle") == 2


def test_piste_piirtyy_plottialueen_sisaan():
    """Ei riita etta nosto on olemassa - koordinaatin on oltava jarkeva.
    Portti joka etsii merkkijonoa ei mittaa arvoa (muisti)."""
    svg = sc.scatter(sarjat=_pisteet((4, 0), (11, 61)),
                     x_label="x", y_label="y", otsikko="t",
                     leveys=720, korkeus=360)
    cx = [float(m) for m in re.findall(r'<circle cx="([0-9.]+)"', svg)]
    cy = [float(m) for m in re.findall(r'cy="([0-9.]+)" r="4"', svg)]
    assert cx and cy
    assert all(52 <= x <= 704 for x in cx), cx
    assert all(16 <= y <= 316 for y in cy), cy


# --- 2. pylvas alkaa nollasta ---------------------------------------------

def test_pylvasta_ei_voi_katkaista():
    """Domain-parametria EI OLE. Vaara vaihtoehto ei ole tarjolla, joten
    sita ei voi valita vahingossa (saanto 6a kohta 1)."""
    import inspect
    allekirjoitus = inspect.signature(sc.stacked_bars).parameters
    assert not any("domain" in p for p in allekirjoitus), (
        "stacked_bars ottaa domainin parametrina - katkaistu akseli on "
        "taas mahdollinen")


def test_pylvaan_pituus_on_suhteessa_arvoon():
    """Mittaa LUVUN, ei merkkijonon: kaksinkertainen arvo = kaksinkertainen
    pylvas, koska nollasta lahtevalla akselilla se on totta."""
    svg = sc.stacked_bars(
        rivit=[("A", {"n": 2}), ("B", {"n": 4})],
        sarjat=[("n", sc.TEAL, "kpl")], otsikko="t", x_label="kpl")
    w = [float(m) for m in re.findall(r'<rect x="[0-9.]+" y="[0-9]+" '
                                      r'width="([0-9.]+)"', svg)]
    assert len(w) == 2, w
    assert abs(w[1] / w[0] - 2.0) < 0.02, w


# --- 3. tyhja ei saa nayttaa nollalta -------------------------------------

def test_tyhja_sarja_nostaa():
    with pytest.raises(sc.KaavioVirhe, match="ei yhtaan pistetta"):
        sc.scatter(sarjat=[{"nimi": "a", "vari": sc.TEAL, "pisteet": []}],
                   x_label="x", y_label="y", otsikko="t")


def test_pelkat_nollat_nostavat():
    """Muisti: nolla-ei-ole-sama-kuin-ei-tietoa. Pylvaikko jossa jokainen
    summa on 0 on tyhja ruudukko - lukija paattelee siita rikkinaisen
    sivun, ei nollan."""
    with pytest.raises(sc.KaavioVirhe, match="summa on 0"):
        sc.stacked_bars(rivit=[("A", {"n": 0})],
                        sarjat=[("n", sc.TEAL, "kpl")],
                        otsikko="t", x_label="kpl")


# --- yleiset ---------------------------------------------------------------

def test_svg_on_saavutettava_ja_selitteet_mukana():
    svg = sc.scatter(sarjat=_pisteet((5, 10)), x_label="Price",
                     y_label="Owned", otsikko="Owned by price")
    assert 'role="img"' in svg and 'aria-label="Owned by price"' in svg
    assert "<title>" in svg, "pisteilla ei ole selitetta"


def test_kaavio_ei_tuo_omaa_palettia():
    """Sivustolla on yksi paletti. Kaavio joka keksii omansa tekee
    sivustosta kokoelman eri nakoisia sivuja."""
    lahde = (sc.__file__)
    teksti = open(lahde, encoding="utf-8").read()
    varit = set(re.findall(r"#[0-9A-Fa-f]{6}", teksti))
    sallitut = {sc.INK, sc.CREAM, sc.MUTED, sc.FAINT, sc.AMBER, sc.TEAL,
                sc.CORAL, sc.PAPER}
    assert varit <= sallitut, f"tuntemattomia vareja: {varit - sallitut}"


def test_teksti_escapataan():
    svg = sc.scatter(
        sarjat=[{"nimi": "a", "vari": sc.TEAL,
                 "pisteet": [(1, 1, '<script>alert("x")</script>')]}],
        x_label="x", y_label="y", otsikko="t")
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg


def test_mobiili_ei_kutista_tekstia():
    """Kaarija vierittaa; se EI skaalaa svg:ta 100 %:iin leveydesta.
    360 px:n puhelimella 720 px viewBox skaalattuna olisi 0.5x, eli
    11 px teksti 5.5 px (muisti:
    headless-chrome-ilman-emulaatiota-nayttaa-ylivuotoa)."""
    svg = sc.scatter(sarjat=_pisteet((5, 10)), x_label="x", y_label="y",
                     otsikko="t")
    assert "chart-scroll" in svg
    assert "--chart-min:720px" in svg
    assert "overflow-x:auto" in sc.CHART_CSS
    assert "min-width:var(--chart-min" in sc.CHART_CSS


def test_pylvas_ja_akseli_ovat_samassa_mittakaavassa():
    """🔴 TAMA REIKA MITATTIIN MUTAATIOLLA. Suhdetesti yllapaa lapaisee
    myos silloin kun MOLEMMAT pylvaat skaalataan vaaralla kertoimella:
    suhde sailyy, mutta pylvaat eivat enaa vastaa akselin lukuja. Lukija
    lukee pituuden akselista, joten se on se vertailu joka on tehtava.

    Mitataan: arvoon v paattyvan pylvaan oikea reuna == v:n tickin x.
    """
    svg = sc.stacked_bars(
        rivit=[("A", {"n": 4}), ("B", {"n": 2})],
        sarjat=[("n", sc.TEAL, "kpl")], otsikko="t", x_label="kpl")

    # Tickit: (x, luku) ruudukkoviivoista + niiden teksteista.
    tickit = {}
    for m in re.finditer(r'<line x1="([0-9.]+)" y1="\d+" x2="[0-9.]+"', svg):
        tickit[round(float(m.group(1)), 1)] = None
    tekstit = [(round(float(x), 1), float(t)) for x, t in
               re.findall(r'<text x="([0-9.]+)" y="\d+" fill="[^"]+" '
                          r'font-family="[^"]+" font-size="11"[^>]*>'
                          r'([0-9.]+)</text>', svg)]
    kartta = {luku: x for x, luku in tekstit}
    assert 4.0 in kartta, f"akselilla ei ole tickia arvolle 4: {kartta}"

    palkit = [(float(a), float(w)) for a, w in re.findall(
        r'<rect x="([0-9.]+)" y="\d+" width="([0-9.]+)"', svg)]
    assert palkit, svg[:400]
    oikea_reuna = palkit[0][0] + palkit[0][1]     # rivi A, arvo 4
    assert abs(oikea_reuna - kartta[4.0]) < 1.0, (
        f"pylvaan reuna {oikea_reuna} ei osu akselin tickiin "
        f"{kartta[4.0]} - pylvas ja akseli ovat eri mittakaavassa")
