"""Hakutuloksen otsikko ja kuvaus mahtuvat rajoihin (LOYDETTAVYYS-5, 3.11.2026).

TAUSTA. Mitattu 3.11: julkaistavista sivuista 2 789 / 3 315 kuvausta oli yli
160 merkkia ja 1 274 otsikkoa yli 60. Yli menevan osan Google katkaisee
hakutuloksessa, ja katkaisukohta osui usein juuri varaukseen ("Updated until
kick-off, and the last version is graded ..."), eli lukija ei nahnyt sita.
Pohjat kirjoitettiin kasin yksi kerrallaan, ja raja muistettiin vain osassa
(points-sivun kuvaus oli tasan 160 kierroksilla 1-9 ja 161 kierroksesta 10).

KAKSI MEKANISMIA (CLAUDE.md saanto 6a):

1. `fit(ehdokkaat, raja)`: pohja antaa kokonaiset vaihtoehdot pisimmasta
   lyhimpaan, ja ensimmainen joka mahtuu valitaan. Mitaan ei katkaista
   kesken sanan, ja jokainen vaihtoehto on kokonainen teksti, jonka
   julkaisutarkistaja voi lukea sellaisenaan.
2. `check(title, desc, where)`: jokaisen builderin `_page()` kutsuu taman.
   Yli rajan menevaa sivua ei kirjoiteta, vaan build kaatuu ja kertoo mika
   pohja ja mika sivu.

POIKKEUS VAIN PERUSTELLUSTA SYYSTA. Jos lyhinkaan vaihtoehto ei mahdu (esim.
kahden pitkan virallisen seuranimen ottelu), `fit` palauttaa sen vain kun
kutsuja nimeaa `POIKKEUKSET`-listan avaimen. Lista vaatii perustelun: tyhja
perustelu tai tuntematon avain kaataa saman tien. Poikkeuksen saa vain `fit`,
eli vain lyhin mahdollinen muoto voi ylittaa rajan, ei mika tahansa teksti.

Portti: tests/test_seo_meta_lengths.py ajaa builderit oikealla datalla
hiekkalaatikkoon ja mittaa jokaisen kirjoitetun sivun.
"""
from __future__ import annotations

from typing import Iterable

TITLE_MAX = 60
DESC_MAX = 160

#: Poikkeusavain -> perustelu. Tyhja perustelu ei vapauta (fail-closed).
POIKKEUKSET: dict[str, str] = {
    "joukkuenimet": (
        "Ottelusivun lyhin otsikko on '<koti> vs <vieras> Prediction' ja lyhin "
        "kuvaus nimeaa ottelun ja kirjauksen varauksen. Kun pelkat viralliset "
        "seuranimet vievat rajan (3.11: Sporting Clube de Portugal vs "
        "Manchester United FC), nimea ei katkaista eika vaihdeta: URL, H1, "
        "JSON-LD ja otsikko lukevat saman nimen "
        "(build_prediction_pages._apply_display_names)."
    ),
    "artikkelin-otsikko": (
        "Muistion otsikko on toimituksellinen ja julkaisutarkistajan "
        "hyvaksyma. Brandi ja loppulauseet pudotetaan, mutta yksittaista "
        "lausetta ei katkaista kesken eika kirjoiteta uutta otsikkoa "
        "koneellisesti."
    ),
}


class MetaTooLong(ValueError):
    """Otsikko tai kuvaus ylittaa rajan ilman perusteltua poikkeusta."""


class Poikkeus(str):
    """Merkkijono jonka `fit` palautti perustellun poikkeuksen nojalla.

    Vain `fit` luo naita, ja vain kun lyhinkaan ehdokas ei mahtunut.
    `check` hyvaksyy yli rajan menevan arvon vain talla tyypilla."""

    syy: str

    def __new__(cls, value: str, syy: str) -> "Poikkeus":
        obj = super().__new__(cls, value)
        obj.syy = syy
        return obj


def _perustelu(syy: str) -> str:
    perustelu = (POIKKEUKSET.get(syy) or "").strip()
    if not perustelu:
        raise MetaTooLong(
            f"poikkeus '{syy}' ei ole POIKKEUKSET-listalla perustelun kanssa "
            "(scripts/seo_meta.py)")
    return perustelu


def fit(ehdokkaat: Iterable[str], raja: int, poikkeus: str | None = None) -> str:
    """Ensimmainen ehdokas joka mahtuu `raja`an.

    Ehdokkaat annetaan pisimmasta (= alkuperainen) lyhimpaan. Jos mikaan ei
    mahdu: perustellulla poikkeuksella palautetaan LYHIN ehdokas
    `Poikkeus`-tyyppisena, muuten MetaTooLong."""
    lista = [str(e) for e in ehdokkaat]
    if not lista:
        raise ValueError("fit: ei ehdokkaita")
    for e in lista:
        if len(e) <= raja:
            return e
    lyhin = min(lista, key=len)
    if poikkeus is None:
        raise MetaTooLong(
            f"lyhinkin ehdokas on {len(lyhin)} merkkia (raja {raja}): {lyhin!r}")
    _perustelu(poikkeus)
    return Poikkeus(lyhin, poikkeus)


def problems(title: str, desc: str) -> list[str]:
    """Rajat ylittavat kentat ilman perusteltua poikkeusta. Tyhja = kelpaa."""
    out = []
    for kentta, arvo, raja in (("title", title, TITLE_MAX),
                               ("description", desc, DESC_MAX)):
        if len(arvo) <= raja:
            continue
        if isinstance(arvo, Poikkeus):
            _perustelu(arvo.syy)
            continue
        out.append(f"{kentta} {len(arvo)} merkkia (raja {raja}): {arvo!r}")
    return out


def check(title: str, desc: str, where: str) -> None:
    """Kaada build jos sivun otsikko tai kuvaus ylittaa rajan."""
    loydot = problems(title, desc)
    if loydot:
        raise MetaTooLong(f"{where}: " + "; ".join(loydot))
