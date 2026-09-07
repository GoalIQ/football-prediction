# -*- coding: utf-8 -*-
"""Portti: sisainen linkki ei saa osoittaa uudelleenohjaukseen.

🔴 MITATTU TUOTANNOSTA 7.9.2026. Kavelin jokaisen sisaisen linkin lapi
kymmeneltä hub-sivulta ja `fpl/*.html`:sta (134 uniikkia URLia) ja mittasin
statuskoodin. Tulos:

    404  /fpl/points/gw1 .. gw3     (arkistosivut puuttuivat)
    308  66 ottelusivulinkkia       (.html -> paatteeton)
    308  /faq.html /privacy.html /fpl.html   (career.html, creators.html)

Cloudflare Pages ohjaa `.html`-URLit 308:lla paatteettomaan muotoon, ja se
paatteeton muoto on myos sivun oma `rel=canonical`. Linkki paatteelliseen
muotoon on siis aina yksi ylimaarainen hyppy kohteeseen joka on TASAN sama
sivu - ja se on hyppy jonka jokainen kavija ja jokainen crawler maksaa.

Vika ei nay mistaan: 308 ei ole virhe, sivu aukeaa, mikaan ei kaadu. Sen
naki vain kavelemalla linkit lapi ja katsomalla koodia, ei sisaltoa
(muisti: `uusi-sivu-ei-nay-hubissa`, `renderoimaton-kentta-todistetaan-vain-
kaikilta-pinnoilta`).

Tama portti mittaa levylla olevat sivut, joten se ei tarvitse verkkoa eika
voi olla vihrea siksi etta pyynto epaonnistui.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Sivut joilta linkit luetaan. Glob eika kasin nimetty lista: kasin nimetty
#: lista vanhenee heti kun uusi sivu syntyy (muisti: portin-sanalista-vanhenee).
SIVU_GLOBIT = ("*.html", "fpl/*.html", "fpl/club/*.html", "fpl/note/*.html",
               "ucl/*.html")

#: Poikkeuslista JOSSA ON PERUSTELU (CLAUDE.md 6a, mekanismi 2). Uusi
#: paatteellinen linkki ei paase tanne vahingossa: testi kaatuu ja kirjoittaja
#: joutuu kirjoittamaan miksi.
SALLITUT = {
    # Hakemistoindeksit tarjoillaan kauttaviivalla, eivat ole .html-linkkeja.
}


def _sivut() -> list[Path]:
    ulos: list[Path] = []
    for g in SIVU_GLOBIT:
        ulos.extend(sorted(ROOT.glob(g)))
    return [p for p in ulos if p.is_file()]


def _sisaiset_html_linkit(teksti: str) -> set[str]:
    """Sisaiset linkit jotka paattyvat .html:aan."""
    ulos = set()
    for h in re.findall(r'href="([^"]+)"', teksti):
        if h.startswith(("http://", "https://", "#", "mailto:", "tel:")):
            continue
        polku = h.split("#", 1)[0].split("?", 1)[0]
        if polku.endswith(".html"):
            ulos.add(polku)
    return ulos


def test_yksikaan_sisainen_linkki_ei_paaty_htmliin():
    """Paatteellinen linkki = 308-hyppy sivulle joka on sama sivu."""
    osumat = []
    for p in _sivut():
        try:
            t = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for h in sorted(_sisaiset_html_linkit(t)):
            if h in SALLITUT:
                continue
            osumat.append(f"{p.relative_to(ROOT)} -> {h}")
    assert not osumat, (
        "sisainen linkki .html-muodossa (Cloudflare ohjaa 308:lla samaan "
        "sivuun paatteettomana, joka on myos sen canonical). Poista pääte "
        "tai lisaa SALLITUT-listaan perusteluineen:\n  "
        + "\n  ".join(osumat))


def test_kontrolli_lukija_loytaa_linkkeja():
    """NEGATIIVINEN KONTROLLI: portti ei saa olla vihrea tyhjana.

    Ilman tata `_sivut()` tai `_sisaiset_html_linkit()` voisi palauttaa aina
    tyhjan (glob rikki, regex rikki) ja portti nayttaisi silti toimivalta
    (muisti: kontrolli-lapaisi-tyhjana).
    """
    sivut = _sivut()
    assert len(sivut) > 30, f"vain {len(sivut)} sivua - onko glob rikki?"
    linkkeja = 0
    for p in sivut:
        try:
            linkkeja += len(re.findall(r'href="/[^"]+"', p.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    assert linkkeja > 200, f"vain {linkkeja} sisaista linkkia - onko regex rikki?"


def test_kontrolli_lukija_tunnistaa_paatteellisen_linkin():
    """MUTAATIO: keksitty .html-linkki EI saa mennä lapi."""
    assert _sisaiset_html_linkit('<a href="/faq.html">FAQ</a>') == {"/faq.html"}
    assert _sisaiset_html_linkit('<a href="/faq.html#pricing">FAQ</a>') == {"/faq.html"}
    # ja paatteeton tai ulkoinen ei osu
    assert not _sisaiset_html_linkit('<a href="/faq">FAQ</a>')
    assert not _sisaiset_html_linkit('<a href="https://x.com/a.html">x</a>')


@pytest.mark.parametrize("nimi", ["career.html", "creators.html"])
def test_kasin_yllapidetyt_alatunnisteet_ovat_paatteettomia(nimi):
    """Nama kaksi sivua eivat ole generoituja, joten mikaan builderi ei
    korjaa niita puolestamme. Ne olivat 7.9 ainoat kolme ei-ottelulinkkia
    jotka ohjautuivat."""
    p = ROOT / nimi
    if not p.exists():
        pytest.skip(f"{nimi} ei ole")
    t = p.read_text(encoding="utf-8")
    for paha in ('href="/fpl.html"', 'href="/faq.html"', 'href="/privacy.html"'):
        assert paha not in t, f"{nimi}: {paha}"
