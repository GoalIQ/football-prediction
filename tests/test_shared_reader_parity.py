# -*- coding: utf-8 -*-
"""Portti: "yksi lukija" kahtena kopiona ei saa erkaantua hiljaa.

TAUSTA (7.9.2026, julkaisutarkistaja). Sama lukija on kirjoitettu kahdesti,
kerran mobiiliin (`goaliq-app/lib/*.ts`) ja kerran SPA:han
(`web/pro-spa/src/lib/*.ts`), ja molempien otsikko lupaa "sama tiedosto".
Portti huomautti: mikaan ei estanyt niiden erkanemista huomenna, ja juuri se
on koko mekanismin lupaus. Kaksi kopiota jotka VOIVAT erota eivat ole yksi
lukija vaan kaksi lukijaa joilla on sama nimi.

MIKSI SKIP CI:SSA: `goaliq-app` on eri (privaatti) repo eika sita checkouteta
missaan workflow'ssa. Sama ratkaisu kuin `test_optimality_claim_family.py`:ssa
— tarkistus ajaa siella missa molemmat repot ovat, eli kehityskoneella
jokaisella `pytest`-ajolla, ja se on tasan se hetki jolloin kopiot erkanevat.
Punainen CI vaarasta syysta olisi huonompi kuin paikallinen portti.

VAIN ENSIMMAINEN RIVI SAA EROTA: se nimeaa toisen kopion polun.
"""
from __future__ import annotations

from pathlib import Path

import pytest

FP = Path(__file__).resolve().parents[1]
APP = FP.parent / "goaliq-app"
SPA_LIB = FP / "web" / "pro-spa" / "src" / "lib"

# Tiedostot joiden otsikko lupaa "sama tiedosto" molemmilla pinnoilla.
PEILATUT = ("gwReviewCard.ts", "seasonObjective.ts")


def _rivit(p: Path) -> list[str]:
    # Rivinvaihdot normalisoidaan: repot ovat eri autocrlf-asetuksilla, ja
    # CRLF-ero ei ole sisaltoero (muisti: portti-linuxilla-mittaa-rivinvaihtoja).
    return p.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")


@pytest.mark.parametrize("nimi", PEILATUT)
def test_mirrored_reader_is_identical_apart_from_its_own_path_line(nimi):
    spa = SPA_LIB / nimi
    app = APP / "lib" / nimi
    assert spa.exists(), f"SPA-kopio puuttuu: {spa}"
    if not app.exists():
        pytest.skip("goaliq-app ei ole checkoutattu, peilausta ei voi verrata")

    a, b = _rivit(spa), _rivit(app)
    assert len(a) == len(b), (
        f"{nimi}: kopioissa on eri maara riveja ({len(a)} SPA / {len(b)} app) "
        "- 'yksi lukija' on erkaantunut")

    erot = [(i + 1, x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y]
    # Otsikkorivi saa erota: se nimeaa TOISEN kopion polun.
    sallitut = [e for e in erot
                if "on sama tiedosto" in e[1] and "on sama tiedosto" in e[2]]
    kielletyt = [e for e in erot if e not in sallitut]
    assert not kielletyt, (
        f"{nimi}: kopiot eroavat muualta kuin polkurivilta:\n  " +
        "\n  ".join(f"rivi {i}:\n    SPA: {x}\n    app: {y}"
                    for i, x, y in kielletyt[:5]))
    assert len(sallitut) <= 1, f"{nimi}: polkurivi esiintyy {len(sallitut)} kertaa"


def test_the_parity_check_would_actually_notice_a_difference():
    """NEGATIIVINEN KONTROLLI VERTAILULLE ITSELLEEN.

    Ilman tata portti voisi olla vihrea siksi etta se vertaa tyhjaa tyhjaan
    (muisti: kontrolli-lapaisi-tyhjana). Mutatoidaan yksi rivi muistissa ja
    varmistetaan etta ero loytyy.
    """
    spa = SPA_LIB / PEILATUT[0]
    a = _rivit(spa)
    assert len(a) > 20, "peilattu tiedosto on epailyttavan lyhyt"
    b = list(a)
    b[-2] = b[-2] + " // mutaatio"
    erot = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    assert erot, "vertailu ei huomaa muutettua rivia"
