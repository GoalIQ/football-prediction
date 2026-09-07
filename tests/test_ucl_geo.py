# -*- coding: utf-8 -*-
"""PORTIT /ucl-osion KONELUETTAVILLE PINNOILLE (SEO/GEO-auditointi 7.9.2026).

🔴 MITA TAMA KORJAA

Osiolla oli 23 testia, ja jokainen niista mittasi ihmiselle nakyvaa pintaa:
copyn, kaaviot, tuoreusleiman, em dashin. Yksikaan ei lukenut
`application/ld+json`-lohkoa, `llms.txt`:aa eika sitemapin `lastmod`ia.
Auditointi mittasi lopputuloksen:

  - JSON-LD oli yksi `WebPage` ilman `dateModified`ia, ilman
    `BreadcrumbList`ia ja ilman `Dataset`ia, vaikka `/ucl/prices` on 1 163
    rivin julkinen datataulukko. `publisher` oli inline-objekti ilman
    `@id`:ta, eli sivut eivat liittyneet sivuston entiteettigraafiin.
  - `llms.txt`:n UCL-osiossa ei ollut YHTAAN lukua, vaikka artefaktissa on
    pelaajamaara, klubimaara ja liputettujen maara.
  - `sitemap-core.xml`:n kolme UCL-rivia oli lisatty kasin, mikaan ei
    paivittanyt niita, ja `changefreq: daily` lupasi mita `lastmod` ei
    tukenut.

MEKANISMI, EI TAPAUS (CLAUDE.md 6a). Nama testit lukevat sivulistan
GLOBISTA eivatka vakiosta, ja vertaavat pinnan arvoa ARTEFAKTIIN eivatka
kovakoodattuun lukuun. Nelja UCL-sivu ei siis voi syntya ilman Datasetia,
eika mikaan luku voi jaataa ilman etta portti punastuu.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import build_ucl_page as bp  # noqa: E402

UCL = ROOT / "ucl"
DATA = ROOT / "data" / "ucl_fantasy.json"
LLMS = ROOT / "llms.txt"
SITEMAP = ROOT / "sitemap-core.xml"

LD_RE = re.compile(
    r'<script type="application/ld\+json">\s*(.*?)\s*</script>', re.S)


def _doc() -> dict:
    if not DATA.exists():  # pragma: no cover
        pytest.skip("data/ucl_fantasy.json puuttuu")
    return json.loads(DATA.read_text(encoding="utf-8"))


# 🔴 SIVULISTA GLOBISTA. Vakiolista olisi vihrea uudelle sivulle joka ei
# ole listalla, ja juuri uusi pinta on se jolta rakenne unohtuu (muisti:
# vieras-tiedosto-glob-kansiossa).
SIVUT = [p.name for p in sorted(UCL.glob("*.html"))]


def _html(nimi: str) -> str:
    p = UCL / nimi
    if not p.exists():  # pragma: no cover
        pytest.skip(f"{nimi} ei ole generoitu")
    return p.read_text(encoding="utf-8")


def _ld(nimi: str) -> dict[str, dict]:
    """Sivun JSON-LD-lohkot tyypin mukaan. Rikkinainen JSON kaataa tassa."""
    ulos = {}
    for raw in LD_RE.findall(_html(nimi)):
        b = json.loads(raw)
        ulos[b["@type"]] = b
    return ulos


def test_sivuja_loytyi():
    """KONTROLLI: tyhja glob tekisi jokaisesta alla olevasta testista
    vihrean mittaamatta mitaan (muisti: kontrolli-lapaisi-tyhjana)."""
    assert len(SIVUT) >= 3, f"vain {len(SIVUT)} UCL-sivua"


# ---------------------------------------------------------------------------
# 1. JSON-LD:n rakenne
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("nimi", SIVUT)
def test_sivulla_on_webpage_breadcrumb_ja_dataset(nimi):
    lohkot = _ld(nimi)
    for tyyppi in ("WebPage", "BreadcrumbList", "Dataset"):
        assert tyyppi in lohkot, (
            f"{nimi}: JSON-LD:sta puuttuu {tyyppi}. Taulukkosivu ilman "
            "Datasetia on AI-hauille pelkka WebPage.")


@pytest.mark.parametrize("nimi", SIVUT)
def test_julkaisija_on_sivuston_entiteettigraafissa(nimi):
    """Inline-`Organization` ilman `@id`:ta on crawlerille ERI entiteetti
    kuin `index.html`:n julistama `.../#organization`."""
    for tyyppi, lohko in _ld(nimi).items():
        for kentta in ("publisher", "creator"):
            arvo = lohko.get(kentta)
            if not isinstance(arvo, dict):
                continue
            assert arvo.get("@id") == bp.ORG_ID, (
                f"{nimi}/{tyyppi}: {kentta} ei viittaa {bp.ORG_ID}:hen "
                f"vaan on {arvo}")


@pytest.mark.parametrize("nimi", SIVUT)
def test_datemodified_on_datan_ika_ei_ajohetki(nimi):
    """🔴 LEIMA DATASTA, EI KELLOSTA. Ajohetkesta johdettu `dateModified`
    vaittaa tuoreutta myos silloin kun UEFAlta ei tullut uutta tiedostoa,
    ja tasan se vika mitattiin 22.8 cron-katkossa alasivuilla (muisti:
    rakennusaika-artefaktissa)."""
    odotettu = bp._feed_iso(_doc())
    assert odotettu, "artefaktissa ei ole feed_updated_utc-leimaa"
    for tyyppi, lohko in _ld(nimi).items():
        if "dateModified" in lohko:
            assert lohko["dateModified"] == odotettu, (
                f"{nimi}/{tyyppi}: dateModified {lohko['dateModified']} != "
                f"syotteen leima {odotettu}")
    assert "dateModified" in _ld(nimi)["WebPage"], f"{nimi}: ei dateModifiedia"


@pytest.mark.parametrize("nimi", SIVUT)
def test_variablemeasured_vastaa_sivun_taulukkoa(nimi):
    """🔴 KAKSI LISTAA SAMASTA ASIASTA AJAUTUU ERILLEEN. Pistesarakkeen
    otsikko vaihtuu kauden alkaessa (`ucl_phase.pistekentta`), joten kasin
    kirjoitettu `variableMeasured` jaisi lupaamaan viime kauden saraketta
    sivulla joka nayttaa taman kauden lukuja (muisti: kaksi-listaa-kaksi-
    saantoa)."""
    h = _html(nimi)
    m = re.search(r"<thead><tr>(.*?)</tr></thead>", h, re.S)
    assert m, f"{nimi}: taulukon otsikkorivia ei loytynyt"
    otsikot = re.findall(r"<th>(.*?)</th>", m.group(1))
    mitattu = [v["name"] for v in _ld(nimi)["Dataset"]["variableMeasured"]]
    assert mitattu == otsikot, (
        f"{nimi}: Dataset lupaa sarakkeet {mitattu}, taulukossa {otsikot}")


@pytest.mark.parametrize("nimi", SIVUT)
def test_murupolku_paattyy_taman_sivun_canonicaliin(nimi):
    h = _html(nimi)
    kanoninen = re.search(r'<link rel="canonical" href="([^"]+)"', h).group(1)
    polut = _ld(nimi)["BreadcrumbList"]["itemListElement"]
    assert polut[0]["item"] == bp.BASE
    assert polut[1]["item"] == f"{bp.BASE}/ucl/"
    assert polut[-1]["item"] == kanoninen, (
        f"{nimi}: murupolun viimeinen askel {polut[-1]['item']} ei ole sivun "
        f"canonical {kanoninen}")


# ---------------------------------------------------------------------------
# 2. FAQ: koneluettava ei saa luvata enempaa kuin nakyva
# ---------------------------------------------------------------------------
def test_hubin_faq_on_myos_nakyvassa_tekstissa():
    """🔴 JSON-LD ON JULKISEMPI PINTA KUIN RUNKO. FAQPage jonka vastauksia
    ei ole sivulla on vaite jota lukija ei voi tarkistaa, ja tassa osiossa
    on jo kerran kaynyt niin etta korjattu vaite jai elamaan JSON-LD:hen
    (muisti: hedge-vain-nakyvassa-copyssa)."""
    faq = _ld("index.html").get("FAQPage")
    assert faq, "hubilla ei ole FAQPagea"
    nakyva = re.sub(r"<[^>]+>", " ", _html("index.html").split("<body>", 1)[1])
    nakyva = re.sub(r"\s+", " ", nakyva)
    for q in faq["mainEntity"]:
        for teksti in (q["name"], q["acceptedAnswer"]["text"]):
            siisti = re.sub(r"\s+", " ", teksti)
            assert siisti in nakyva, (
                "FAQPage lupaa tekstia jota sivulla ei ole: "
                f"{siisti[:90]!r}")


def test_faq_luvut_ovat_artefaktista():
    """Kovakoodattu luku vanhenee hiljaa: FAQ:n pelaajamaaran on oltava
    sama kuin artefaktin, ei sama kuin kirjoitushetkella."""
    doc = _doc()
    faq = dict(bp._faq(doc, dt.datetime.now(dt.timezone.utc)))
    vastaus = faq["How many players are in UCL Fantasy?"]
    assert str(len(doc["players"])) in vastaus
    assert str(len(doc["teams"])) in vastaus


def test_kontrolli_faq_havaitsee_vanhentuneen_luvun():
    """NEGATIIVINEN KONTROLLI: yllaoleva voisi olla vihrea siksi etta luku
    esiintyy vastauksessa sattumalta."""
    doc = _doc()
    vaarennos = {**doc, "players": doc["players"][:5]}
    faq = dict(bp._faq(vaarennos, dt.datetime.now(dt.timezone.utc)))
    assert str(len(doc["players"])) not in \
        faq["How many players are in UCL Fantasy?"]


# ---------------------------------------------------------------------------
# 3. llms.txt ja sitemap: sivun ULKOPUOLISET pinnat
# ---------------------------------------------------------------------------
def test_llms_txt_ucl_lohko_on_generoitu_ja_ajan_tasalla():
    """🔴 KASIN KIRJOITETTU RIVI EI VANHENE VAAN JAATYY. Rivit 79-83 oli
    kirjoitettu kasin ja niissa ei ollut yhtaan lukua: kysymykseen "how
    many players are in UCL Fantasy" lahdeluettelo ei vastannut, vaikka
    lahde oli kadessa. Nyt lohko generoidaan, ja tama portti kaatuu jos
    levylla oleva lohko on jaanyt artefaktista jalkeen."""
    teksti = LLMS.read_text(encoding="utf-8")
    m = re.search(r"<!-- GEN:UCL-START -->(.*?)<!-- GEN:UCL-END -->",
                  teksti, re.S)
    assert m, "llms.txt:sta puuttuu GEN:UCL-markkeripari"
    assert m.group(1) == bp.llms_lohko(_doc()), (
        "llms.txt:n UCL-lohko on jaanyt artefaktista jalkeen. Aja "
        "`python -m scripts.build_ucl_page`.")


def test_llms_txt_kattaa_jokaisen_ucl_sivun():
    """Vastine `test_fpl_team_news_page.test_jokainen_fpl_sivu_on_llms_txt_ssa`
    lle: neljas UCL-sivu ei saa syntya lahdeluettelon ohi."""
    teksti = LLMS.read_text(encoding="utf-8")
    puuttuvat = [
        n for n in SIVUT
        if ("/ucl/" if n == "index.html" else f"/ucl/{n[:-5]}") not in teksti]
    assert not puuttuvat, f"llms.txt:sta puuttuu: {puuttuvat}"


def test_sitemapin_lastmod_seuraa_syotteen_ikaa():
    """`changefreq: daily` + jaatynyt `lastmod` on ristiriita joka opettaa
    crawlerin olemaan palaamatta. Kolme UCL-rivia oli lisatty kasin eika
    mikaan upsertannut niita."""
    xml = SITEMAP.read_text(encoding="utf-8")
    odotettu = bp._feed_pvm(_doc())
    assert odotettu
    for loc, _cf, _pri in bp.SITEMAP_RIVIT:
        m = re.search(
            r"<loc>" + re.escape(loc) + r"</loc>\s*<lastmod>([^<]+)</lastmod>",
            xml)
        assert m, f"sitemap-core.xml: {loc} puuttuu"
        assert m.group(1) == odotettu, (
            f"{loc}: lastmod {m.group(1)} != syotteen paiva {odotettu}")


def test_kontrolli_sitemap_upsert_muuttaa_arvoa():
    """NEGATIIVINEN KONTROLLI: yllaoleva olisi vihrea myos silloin jos
    upsert ei tekisi mitaan ja paivamaara sattuisi olemaan oikea."""
    from scripts.build_fpl_page import _upsert_sitemap_entry
    xml = SITEMAP.read_text(encoding="utf-8")
    loc = bp.SITEMAP_RIVIT[0][0]
    uusi = _upsert_sitemap_entry(xml, loc, "1999-01-01", "daily", "0.8")
    assert "1999-01-01" in uusi and uusi != xml
