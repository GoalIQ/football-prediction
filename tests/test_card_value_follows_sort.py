"""PORTTI: jaettu kortti nayttaa SEN luvun jolla lista on lajiteltu.

MITATTU VIKA 16.9: `XpTable.svelte`:n jakokortti tulosti aina
`xp_horizon_total` ja nimilapun `xP`, vaikka lista oli lajiteltu
haul-todennakoisyydella ("Chance of 10+ points"), blank-riskilla tai
Start-prosentilla. Kayttaja siis jakoi kuvan joka VAITTI olevansa xP-lista
kun se oli jarjestetty jollain muulla.

Kuva on se mika elaa ilman sivua: vastaanottaja ei nae sorttivalitsinta,
vain otsikon ja luvut. Sama luokka kuin `kaavio-on-vaite` ja
`jakopinta-lukee-eri-tiedostoa-kuin-sivu`.

Portti lukee LAHTEEN eika renderoi korttia: jokaiselle sortille jonka
`SORTS`-taulukko tuntee on oltava haara seka `cardValue`ssa etta
`cardValueLabel`issa. Uusi sortti ilman haaraa = kaatuu, ja kirjoittaja
joutuu paattamaan mita kortti nayttaa.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
XPTABLE = ROOT / "web" / "pro-spa" / "src" / "lib" / "components" / "XpTable.svelte"

# Sortit jotka nayttavat KOKONAIS-xP:n: niille ei tarvita omaa haaraa, koska
# kortin oletusarvo on juuri se. Perustelu per avain, ei pelkka lista.
OLETUS_XP = {
    "total": "kortin oletusarvo on horisontin xP",
    "pos": "jarjestys on positio, mutta arvo on yha xP",
    "team": "jarjestys on seura, mutta arvo on yha xP",
    "name": "jarjestys on nimi, mutta arvo on yha xP",
    "perGw": "xP per GW on sama suure eri jakajalla; kortti nayttaa summan",
    "price": "hinta on jo kortin PRICE-sarakkeessa (midLabel)",
}


def _lahde() -> str:
    if not XPTABLE.exists():
        pytest.skip("XpTable.svelte puuttuu")
    return XPTABLE.read_text(encoding="utf-8")


def _sort_avaimet(src: str) -> list[str]:
    """`SORTS`-olion avaimet. Luetaan lahteesta, jotta uusi sortti tulee
    porttiin mukaan ilman etta taman testin listaa muistetaan paivittaa."""
    alku = src.index("const SORTS = {")
    loppu = src.index("} as const;", alku)
    lohko = src[alku:loppu]
    # ylimman tason avaimet: rivin alussa kaksi tabia + nimi + kaksoispiste
    return re.findall(r"^\t\t(\w+):\s*\{", lohko, flags=re.M)


def test_sorttilista_loytyi() -> None:
    """Tyhja lista tekisi portista aanettoman."""
    avaimet = _sort_avaimet(_lahde())
    assert len(avaimet) >= 8, avaimet
    assert "total" in avaimet and "haul" in avaimet


def test_jokaisella_sortilla_on_kortin_arvo_ja_nimilappu() -> None:
    src = _lahde()
    arvo_alku = src.index("function cardValue(")
    arvo = src[arvo_alku:src.index("let cardValueLabel", arvo_alku)]
    lappu_alku = src.index("let cardValueLabel")
    lappu = src[lappu_alku:src.index("});", lappu_alku)]

    puuttuu = []
    for key in _sort_avaimet(src):
        if key in OLETUS_XP:
            continue
        if f"sortBy === '{key}'" not in arvo:
            puuttuu.append(f"cardValue: {key}")
        if f"sortBy === '{key}'" not in lappu:
            puuttuu.append(f"cardValueLabel: {key}")
    assert not puuttuu, (
        "sortti ilman kortin haaraa -> jaettu kuva vaittaisi olevansa xP-lista. "
        "Lisaa haara tai kirjaa avain OLETUS_XP:hen PERUSTELUN kanssa: "
        + ", ".join(puuttuu))


def test_oletuslistalla_on_perustelu() -> None:
    """Poikkeuslistalle ei paase vahingossa (saanto 6a kohta 2)."""
    avaimet = set(_sort_avaimet(_lahde()))
    for key, syy in OLETUS_XP.items():
        assert syy.strip(), key
        assert key in avaimet, f"{key}: poikkeus osoittaa sorttiin jota ei ole"


def test_kortti_ei_kovakoodaa_xp_nimilappua() -> None:
    """EROTTELEVA: vanha toteutus paatti nimilapun paikan paalla kolmella
    ehdolla ja putosi muuten merkkijonoon 'xP'. Jos tama palaa, kortti voi
    taas vaittaa vaarin."""
    src = _lahde()
    assert "valueLabel: cardValueLabel," in src, (
        "kortin nimilappu ei tule yhdesta lukijasta")
    assert "value: cardValue(p)" in src, (
        "kortin arvo ei tule yhdesta lukijasta")
