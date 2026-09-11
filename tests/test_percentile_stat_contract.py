# -*- coding: utf-8 -*-
"""PLAYER-PERCENTILES-VS-POSITION: palkkien kentat ovat olemassa payloadissa.

🔴 MIKSI TAMA PORTTI ON (CLAUDE.md 6a mekanismi 1 ja 2). Prosenttiilipalkit
lukevat `/api/fantasy/player-stats` -vastauksen `fpl`-lohkoa nimella. Nimi joka
ei ole `fpl_player_stats._SUM_COLS`-kartassa ei kaada mitaan: `field()`
palauttaa `undefined`, `percentileOf` palauttaa `null` ja palkki jaa
renderoimatta. Vika ei siis nay virheena vaan PUUTTUVANA RIVINA, jota kukaan ei
etsi. Sama luokka kuin `maski-katkaisee-ilmaispinnan-hiljaa`.

Kaksi vaitetta:
  1. Jokainen `STATS_BY_POS`-kentta on olemassa palvelimen kartassa.
  2. Kaanteiset tilastot (paastetyt maalit, kortit) EIVAT ole listalla.
     Palkki jossa pitka on hyva valehtelisi niista, ja kaannetty palkki
     vaatisi oman selityksensa jokaiselle riville.

Molemmille negatiivinen kontrolli, jottei portti voi lapaista tyhjana
(muisti: kontrolli-lapaisi-tyhjana).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TS = ROOT / "web" / "pro-spa" / "src" / "lib" / "percentiles.ts"

# Suuremmalla luvulla on huonompi merkitys: nama eivat kuulu palkkeihin.
KAANTEISET = {"gc", "xgc", "yc", "rc"}


def _ts() -> str:
    assert TS.exists(), f"{TS} puuttuu"
    return TS.read_text(encoding="utf-8")


def palkkikentat(text: str) -> set[str]:
    """`STATS_BY_POS`-lohkon `key: '...'` -arvot."""
    i = text.find("STATS_BY_POS")
    assert i != -1, "STATS_BY_POS puuttuu - portti mittaisi tyhjaa"
    j = text.find("export function statsFor", i)
    lohko = text[i : j if j != -1 else len(text)]
    return set(re.findall(r"key:\s*'([^']+)'", lohko))


def palvelimen_kentat() -> set[str]:
    from src.models.fpl_player_stats import _SUM_COLS

    # `games` ja `ppg` lisataan riville erikseen aggregaatissa.
    return set(_SUM_COLS) | {"games", "ppg"}


def test_portti_ei_mittaa_tyhjaa() -> None:
    kentat = palkkikentat(_ts())
    assert len(kentat) >= 6, kentat
    assert len(palvelimen_kentat()) >= 20


def test_jokainen_palkkikentta_on_payloadissa() -> None:
    puuttuu = sorted(palkkikentat(_ts()) - palvelimen_kentat())
    assert not puuttuu, (
        f"prosenttiilipalkki lukee kenttaa jota vastaus ei kanna: {puuttuu}. "
        "Palkki ei kaadu vaan katoaa hiljaa - lisaa kentta "
        "src/models/fpl_player_stats.py:n _SUM_COLS-karttaan tai poista rivi."
    )


def test_kaanteisia_tilastoja_ei_nayteta_palkkina() -> None:
    osuu = sorted(palkkikentat(_ts()) & KAANTEISET)
    assert not osuu, (
        f"kaanteinen tilasto palkkina: {osuu}. Pitka palkki lukee hyvana, "
        "mutta naissa suurempi luku on huonompi."
    )


def test_negatiivinen_kontrolli_keksitty_kentta_kaataa() -> None:
    """Ilman tata edellinen testi menisi lapi myos rikkinaisella jasentimella."""
    rikottu = _ts().replace("key: 'mins'", "key: 'ei_ole_olemassa'", 1)
    assert "ei_ole_olemassa" in palkkikentat(rikottu)
    assert palkkikentat(rikottu) - palvelimen_kentat() == {"ei_ole_olemassa"}


def test_negatiivinen_kontrolli_kaanteinen_kentta_kaataa() -> None:
    rikottu = _ts().replace("key: 'saves'", "key: 'gc'", 1)
    assert palkkikentat(rikottu) & KAANTEISET == {"gc"}


def test_populaatiosaanto_on_kirjattu_moduuliin() -> None:
    """Otoslabel ja luku tulevat samasta kutsusta: saanto lukee koodissa.

    Ei tyylitesti: jos joku vaihtaa populaation (esim. kaikki pelaajat eika
    vain pelanneet), labelin "who have played" pitaa muuttua samalla. Tama
    kaataa hiljaisen muutoksen."""
    t = _ts()
    assert "minuutteja yli nollan" in t
    assert "hasPlayed" in t and "r.pos === pos" in t


@pytest.mark.parametrize("nimi", ["percentileOf", "ordinal", "positionWord", "statsFor"])
def test_lukija_on_yksi_moduuli(nimi: str) -> None:
    assert f"export function {nimi}" in _ts()
