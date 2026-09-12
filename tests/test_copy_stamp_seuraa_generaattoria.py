# -*- coding: utf-8 -*-
"""Tuoreusleima ei voi jaada jalkeen GENERAATTORIN tekemasta muutoksesta.

🔴 MITATTU 12.9.2026. `tests/test_faq_freshness.py` vartioi etta faq.html:n
"Last updated" -leima vastaa sivun copya. Se oletti — sanomatta sita — etta
copyn muuttaa ihminen joka paivittaa leiman samalla.

Ilmaisikkunan sulkeutuminen klo 12:30 UTC poisti lupauslauseen faq.html:sta
koneellisesti (`check_free_window.fix()` -> `strip_claim` -> `write_text`).
Leima jai `834e4eca8357` / "7 September 2026" kun sisalto sanoi
`6a25db3a1dbb`, ja `tests.yml` oli punainen ilman etta kukaan oli koskenut
sivuun. Vaarin punainen portti on huonompi kuin puuttuva portti: se opettaa
ohittamaan.

Invariantti: jos koodipolku kirjoittaa sivun nakyvaa copya, sen on
paivitettava saman sivun leima samassa kirjoituksessa.
"""
from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

import pytest

from src.copy_stamp import (HASH_RE, LEIMA_RE, copy_tiiviste, paivita_leima,
                            paivita_tiedoston_leima)

ROOT = Path(__file__).resolve().parents[1]
NOW = _dt.datetime(2026, 9, 12, 13, 0, tzinfo=_dt.timezone.utc)

SIVU = (
    "<html><body>\n"
    '<p>Premium is free on the web until the GW4 deadline on 12 September.</p>\n'
    '<p class="updated" data-copy-hash="000000000000">Last updated: '
    "1 January 2026</p>\n"
    "</body></html>"
)


def test_leima_paivittyy_kun_copy_muuttuu():
    uusi, muuttui = paivita_leima(SIVU, now=NOW)
    assert muuttui
    m = LEIMA_RE.search(uusi)
    assert m and m.group("pvm") == "12 September 2026"
    assert HASH_RE.search(m.group("attrs")).group(1) == copy_tiiviste(uusi)


def test_ajan_tasalla_oleva_leima_on_no_op():
    """Negatiivinen kontrolli: ilman tata joka ajo tuottaisi tyhjan commitin
    pelkan paivan vaihtumisen takia."""
    kertaalleen, _ = paivita_leima(SIVU, now=NOW)
    uudelleen, muuttui = paivita_leima(
        kertaalleen, now=NOW + _dt.timedelta(days=5))
    assert muuttui is False and uudelleen == kertaalleen


def test_sivu_ilman_leimaa_jaa_koskematta():
    teksti = "<html><body><p>ei leimaa</p></body></html>"
    uusi, muuttui = paivita_leima(teksti, now=NOW)
    assert muuttui is False and uusi == teksti


def test_generaattori_paivittaa_leiman_samassa_kirjoituksessa(tmp_path,
                                                              monkeypatch):
    """🔴 Ydintesti: sama polku joka poisti lauseen 12.9 klo 12:30.

    Ajetaan `fix()` tmp-tiedostolla ja vaaditaan etta lauseen poiston
    JALKEEN leima tasmaa uuteen sisaltoon. Ilman kytkentaa
    `check_free_window.py`:ssa tama kaatuu.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "check_free_window", ROOT / "scripts" / "check_free_window.py")
    cfw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfw)

    p = tmp_path / "faq.html"
    p.write_text(SIVU, encoding="utf-8")
    monkeypatch.setattr(cfw, "ROOT", tmp_path)

    kiinni = _dt.datetime(2026, 9, 13, tzinfo=_dt.timezone.utc)
    assert cfw.is_open(kiinni) is False, "testi vaatii suljetun ikkunan"
    muutetut = cfw.fix([p], now=kiinni)
    assert muutetut, "lauseen poisto ei tapahtunut — testi ei mittaa mitaan"

    teksti = p.read_text(encoding="utf-8")
    assert not cfw.CLAIM_RE.search(teksti), "lupaus jai sivulle"
    m = LEIMA_RE.search(teksti)
    assert m, "leima katosi"
    tallennettu = HASH_RE.search(m.group("attrs"))
    assert tallennettu and tallennettu.group(1) == copy_tiiviste(teksti), (
        "leima jai jalkeen generaattorin tekemasta copy-muutoksesta")


def test_faq_leima_on_tasmaava_repossa():
    """Ja lopputila levylla: sama vaite kuin test_faq_freshness, mutta tama
    kaatuu myos jos leima puuttuu kokonaan."""
    faq = ROOT / "faq.html"
    if not faq.exists():
        pytest.skip("faq.html puuttuu")
    teksti = faq.read_text(encoding="utf-8")
    m = LEIMA_RE.search(teksti)
    assert m, "faq.html: leimaa ei loydy"
    h = HASH_RE.search(m.group("attrs"))
    assert h, "faq.html: leimalta puuttuu data-copy-hash"
    assert h.group(1) == copy_tiiviste(teksti)


def test_apufunktio_kirjoittaa_levylle(tmp_path):
    p = tmp_path / "sivu.html"
    p.write_text(SIVU, encoding="utf-8")
    assert paivita_tiedoston_leima(p, now=NOW) is True
    assert paivita_tiedoston_leima(p, now=NOW) is False, "toinen ajo on no-op"


def test_pvm_muoto_on_sama_kuin_sivuilla():
    """Muoto '12 September 2026' — ei ISO, ei '12.9.2026'. Portti lukee
    LEIMA_RE:lla, ja vaara muoto tekisi leimasta lukukelvottoman."""
    uusi, _ = paivita_leima(SIVU, now=NOW)
    pvm = LEIMA_RE.search(uusi).group("pvm")
    assert re.fullmatch(r"\d{1,2} [A-Z][a-z]+ \d{4}", pvm), pvm


def test_leima_sailyttaa_muut_attribuutit():
    """🔴 Tarkistuksen loydos 12.9: ensimmainen versio rakensi tagin uudelleen
    kiintealla merkkijonolla ja pudotti kaiken paitsi hashin."""
    sivu = SIVU.replace('<p class="updated" data-copy-hash="000000000000">',
                        '<p class="updated" id="stamp" lang="en" '
                        'data-copy-hash="000000000000">')
    uusi, muuttui = paivita_leima(sivu, now=NOW)
    assert muuttui
    attrs = LEIMA_RE.search(uusi).group("attrs")
    assert 'id="stamp"' in attrs and 'lang="en"' in attrs
    assert HASH_RE.search(attrs).group(1) == copy_tiiviste(uusi)


def test_leimatut_sivut_ovat_tiedossa():
    """Kate nakyviin: mitka sivut kantavat leimaa ja mitka niista on
    vartioitu hashilla. Ilman tata uusi leimattu sivu jaa hiljaa katteen
    ulkopuolelle (muisti: `uusi-sivu-ei-nay-hubissa`)."""
    leimatut, hashilla = [], []
    for p in sorted(ROOT.glob("*.html")):
        t = p.read_text(encoding="utf-8", errors="ignore")
        m = LEIMA_RE.search(t)
        if not m:
            continue
        leimatut.append(p.name)
        if HASH_RE.search(m.group("attrs") or ""):
            hashilla.append(p.name)
    assert "faq.html" in hashilla, "faq.html:n leima on menettanyt hashinsa"
    # Tiedostetut ilman hashia. Lista on katteen mittari, ei hyvaksynta:
    # kun sivu lisataan tanne, se on nakyva valinta eika unohdus.
    ILMAN_HASHIA_TIEDOSSA = {"privacy.html", "delete-account.html"}
    yllattavat = set(leimatut) - set(hashilla) - ILMAN_HASHIA_TIEDOSSA
    assert not yllattavat, (
        f"uusi leimattu sivu ilman copy-hashia: {sorted(yllattavat)}. "
        f"Lisaa hash tai kirjaa sivu listalle perusteluineen.")
