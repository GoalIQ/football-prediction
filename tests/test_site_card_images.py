"""Portti: sivun kuvaviittaukset osoittavat olemassa oleviin, tuoreisiin kuviin.

🔴 TAUSTA (4.9.2026, Villen tilaus). Laskeutumissivulla oli **0 kuvaa** ja
2 559 sanaa proosaa, jossa kavijaa pyydetaan kuvittelemaan tyokalut joita
myymme. Kortit ovat olleet olemassa koko ajan, mutta ne kirjoitetaan
`outputs/`-kansioon joka on gitignoressa.

Kaksi asiaa voi mennä hiljaa rikki, ja tama portti estaa molemmat:

1. **Rikkinainen viittaus.** Sivu osoittaa tiedostoon jota ei ole. Tumma
   sivupohja piilottaa puuttuvan kuvan lahes taysin - kavija nakee tyhjan
   laatikon eika mikaan huuda.
2. **Vanhentunut kuva.** Nimi on tarkoituksella vakio
   (`gameweek-card.webp`), jotta sivun ei tarvitse tietaa kierrosnumeroa.
   Sama vakionimi tarkoittaa etta VANHA kortti nayttaa tuoreelta:
   GW3:n kortti GW7:n aikana on nakymatta vaara. Sama vikaluokka kuin
   "Live model projections · GW1-6" joka oli kovakoodattu GEN-markerien
   ulkopuolelle ja jota mikaan ei paivittanyt.
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
SIVUT = ["index.html", "fpl.html", "career.html", "faq.html", "creators.html"]

# Vakionimet joita sivut kayttavat. Uusi kortti lisataan tanne KASIN, jotta
# rikkinainen viittaus loytyy ennen julkaisua.
ODOTETUT = {"gameweek-card.webp", "projected-xi-card.webp"}

# Kuinka vanha julkaistu kortti saa olla. Kierros kestaa viikon; kaksi
# viikkoa antaa tilaa maaotteluetauolle ilman etta vanhentunut kortti jaa
# sivulle koko kaudeksi.
MAX_IKA_VRK = 16

RE_SRC = re.compile(r'src="(/assets/cards/[^"]+)"')


def _viittaukset() -> set[str]:
    ulos = set()
    for nimi in SIVUT:
        p = ROOT / nimi
        if not p.exists():
            continue
        ulos |= set(RE_SRC.findall(p.read_text(encoding="utf-8")))
    return ulos


def test_sivut_viittaavat_kortteihin():
    """Tyhjyyskontrolli: jos yksikaan sivu ei viittaa korttiin, koko portti
    mittaa tyhjaa ja kuvat ovat kadonneet huomaamatta."""
    v = _viittaukset()
    assert v, "yksikaan sivu ei viittaa /assets/cards/-kuvaan"
    nimet = {Path(x).name for x in v}
    assert nimet == ODOTETUT, (nimet, ODOTETUT)


def test_jokainen_viittaus_osoittaa_olemassa_olevaan_tiedostoon():
    puuttuu = []
    for src in _viittaukset():
        p = ROOT / src.lstrip("/")
        if not p.exists() or p.stat().st_size == 0:
            puuttuu.append(src)
    assert not puuttuu, (
        "sivu viittaa kuvaan jota ei ole; tumma pohja piilottaa taman "
        "kavijalta: %s" % puuttuu)


@pytest.mark.parametrize("nimi", sorted(ODOTETUT))
def test_kortti_ei_ole_vanhentunut(nimi):
    p = ROOT / "assets" / "cards" / nimi
    if not p.exists():
        pytest.fail("%s puuttuu kokonaan" % nimi)
    ika = dt.datetime.now() - dt.datetime.fromtimestamp(p.stat().st_mtime)
    assert ika.days <= MAX_IKA_VRK, (
        "%s on %d vrk vanha (raja %d). Vakionimi saa vanhan kortin nayttamaan "
        "tuoreelta. Aja `python -m scripts.publish_cards_to_site` tai tarkista "
        "miksi fpl-data-refresh ei aja sita." % (nimi, ika.days, MAX_IKA_VRK))


def test_kortit_ovat_webpia_eivat_pngta():
    """Mitattu 4.9: sama kortti on PNG:na 192 kB ja WebP:na 32 kB, ja
    laskeutumissivu on pakattuna 26 kB. Kaksi PNG:ta olisi
    kuusinkertaistanut sivun painon."""
    for src in _viittaukset():
        assert src.endswith(".webp"), src


@pytest.mark.parametrize("nimi", sorted(ODOTETUT))
def test_kortti_on_kohtuullisen_kokoinen(nimi):
    p = ROOT / "assets" / "cards" / nimi
    if not p.exists():
        pytest.skip("%s puuttuu" % nimi)
    kb = p.stat().st_size / 1024
    assert kb < 120, "%s on %.0f kB, liikaa laskeutumissivulle" % (nimi, kb)


def test_kuvilla_on_mitat_ja_alt():
    """Ilman width/height sivu hyppaa kun kuva latautuu (CLS); ilman altia
    kuva ei ole olemassa ruudunlukijalle."""
    puutteet = []
    for nimi in SIVUT:
        p = ROOT / nimi
        if not p.exists():
            continue
        teksti = p.read_text(encoding="utf-8")
        for tagi in re.findall(r"<img[^>]*/assets/cards/[^>]*>", teksti):
            if 'width="' not in tagi or 'height="' not in tagi:
                puutteet.append(("mitat", nimi, tagi[:70]))
            if not re.search(r'alt="[^"]{15,}"', tagi):
                puutteet.append(("alt", nimi, tagi[:70]))
    assert not puutteet, puutteet


def test_julkaisuskripti_ei_kovakoodaa_kierrosta():
    """Skriptin on poimittava uusin kierros, ei osoitettava tiettyyn.

    Mitataan VAIN `re.compile(r"...")`-kuvioista. Ensimmainen versio luki
    koko tiedoston ja osui omaan docstringiinsa ("gw10:n ennen gw9:aa") -
    kolmas kerta samana paivana kun portti mittasi selittavaa tekstiaan
    koodin sijaan.
    """
    src = (ROOT / "scripts" / "publish_cards_to_site.py").read_text(
        encoding="utf-8")
    kuviot = re.findall(r're\.compile\(r"([^"]+)"\)', src)
    assert kuviot, "yhtaan re.compile-kuviota ei loytynyt"
    for k in kuviot:
        assert r"gw(\d+)" in k, k
        assert not re.search(r"gw\d", k.replace(r"gw(\d+)", "")), k
