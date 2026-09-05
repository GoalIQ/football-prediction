# -*- coding: utf-8 -*-
"""Portti: paasivulla on oma jakokortti, ei yhteista.

TAUSTA (5.9.2026): `/`, `/fpl`, `/predictions` ja `/career` jakoivat saman
`goaliq-social-1200x630.png`:n, joten jokainen jako naytti feedissa
identtiselta vaikka sivut vastaavat eri kysymyksiin. Alasivut olivat saaneet
oman korttinsa 15.8 alkaen; nama neljä olivat jaaneet ilman, eika mikaan
huutanut siita.

MIKSI POIKKEUSLISTA EIKA PELKKA TARKISTUS: uusi sivu ei saa paasta listalle
vahingossa. Jos sivulla ei ole omaa korttia, testi kaatuu ja kirjoittaja
joutuu joko generoimaan kortin tai kirjaamaan MIKSI yhteinen riittaa —
unohduksesta syntyva vika muuttuu mahdottomaksi, tietoinen valinta jaa
diffiin nakyviin.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OG_DIR = ROOT / "assets" / "brand" / "og"
YHTEINEN = "goaliq-social-1200x630.png"

#: Sivut joilla ON oltava oma kortti: sivusto-tason laskeutumissivut, joita
#: jaetaan linkkina. Arvo on kortin slug.
OMA_KORTTI = {
    "index.html": "home",
    "fpl.html": "fpl",
    "predictions.html": "predictions",
    "career.html": "career",
}

#: Perusteltu poikkeuslista. Sivu saa kayttaa yhteista korttia VAIN jos syy
#: on kirjattu tahan.
YHTEINEN_SALLITTU = {
    "privacy.html": "Juridinen sivu, ei jaeta markkinoinnissa.",
    "faq.html": "Tukisivu; jaot ohjautuvat etusivulle tai /fpl:aan.",
    "spl.html": "Oma osio, ei viela omaa korttia; SPL:aa ei markkinoida jaoilla.",
    "creators.html": "Kutsusivu, jaetaan DM:ssa linkkina eika esikatselukorttina.",
    "delete-account.html": "Tilinhallinta, ei jaettava.",
    "reset-password.html": "Tilinhallinta, ei jaettava.",
    "subscription-managed.html": "Tilinhallinta, ei jaettava.",
    "404.html": "Virhesivu.",
}

OG_RE = re.compile(r'<meta\s+property="og:image"\s+content="([^"]+)"')
TW_RE = re.compile(r'<meta\s+name="twitter:image"\s+content="([^"]+)"')


def _juurisivut() -> list[Path]:
    # Vain repon juuren sivut. MM-sivut (world-cup-*) ovat generoituja ja
    # niita on 15; ne kayttavat yhteista korttia tarkoituksella.
    return sorted(
        p
        for p in ROOT.glob("*.html")
        if not p.name.startswith("world-cup-")
    )


@pytest.mark.parametrize("nimi,slug", sorted(OMA_KORTTI.items()))
def test_paasivulla_on_oma_kortti(nimi: str, slug: str) -> None:
    sivu = ROOT / nimi
    if not sivu.exists():  # pragma: no cover
        pytest.skip(f"{nimi} puuttuu")
    teksti = sivu.read_text(encoding="utf-8", errors="replace")

    kortti = OG_DIR / f"{slug}-1200x630.png"
    assert kortti.exists(), (
        f"{nimi} viittaa korttiin {kortti.name} jota ei ole. Generoi: "
        "python assets/brand/gen_og_cards.py (goaliq-app-repossa)."
    )

    for saanto, re_ in (("og:image", OG_RE), ("twitter:image", TW_RE)):
        osumat = re_.findall(teksti)
        assert osumat, f"{nimi}: {saanto} puuttuu kokonaan"
        for url in osumat:
            assert YHTEINEN not in url, (
                f"{nimi}: {saanto} osoittaa yhteiseen korttiin. "
                f"Odotettu: assets/brand/og/{slug}-1200x630.png"
            )
            assert f"og/{slug}-1200x630.png" in url, (
                f"{nimi}: {saanto} = {url}, odotettu og/{slug}-1200x630.png"
            )


def test_yhteista_korttia_kayttava_sivu_on_perusteltu() -> None:
    """Uusi juurisivu ei paase yhteiseen korttiin ilman kirjattua syyta."""
    puuttuvat = []
    for sivu in _juurisivut():
        if sivu.name in OMA_KORTTI or sivu.name in YHTEINEN_SALLITTU:
            continue
        teksti = sivu.read_text(encoding="utf-8", errors="replace")
        if any(YHTEINEN in u for u in OG_RE.findall(teksti)):
            puuttuvat.append(sivu.name)
    assert not puuttuvat, (
        "Nama sivut kayttavat yhteista jakokorttia ilman perustelua: "
        f"{puuttuvat}. Joko generoi oma kortti (gen_og_cards.py) ja lisaa "
        "sivu OMA_KORTTI-listaan, tai kirjaa syy YHTEINEN_SALLITTU-listaan."
    )


def test_negatiivinen_kontrolli_portti_huomaa_yhteisen_kortin() -> None:
    """Kontrolli: portti EI saa lapaista jos sivu palaisi yhteiseen korttiin.

    Ilman tata testi voisi olla vihreana siksi etta regex ei osu mihinkaan
    (`findall` palauttaisi tyhjan), eika siksi etta kortit ovat kunnossa.
    """
    vaarennos = (
        '<meta property="og:image" '
        f'content="https://goaliq.app/assets/brand/{YHTEINEN}">'
    )
    osumat = OG_RE.findall(vaarennos)
    assert osumat, "regex ei osu edes tunnettuun muotoon -> portti on inertti"
    assert any(YHTEINEN in u for u in osumat)
