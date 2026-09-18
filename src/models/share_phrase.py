"""Osuusluku -> luonnollisen kielen murto-osalause, johdettu MITTAUKSESTA.

MIKSI (18.9.2026, MINUUTTIPORTTI-TYYPILLINEN). tests/test_minutes_claim_matches_source.py
sitoi tekstin artefaktin PLAIN-lukuihin (keskiarvo, hännän raja), mutta portin
oma docstring nimesi tunnetun reiän: ehto etsi vain että hännän luku ("30") ON
LÄSNÄ tekstissä, ei että teksti kertoo TYYPILLISEN tapauksen (share_within_5,
share_over_30). Sanalista ("four in ten" kolmella kielellä) olisi vanhentunut
äänettömästi, jos mittaus muuttuisi eikä listaa muistettaisi päivittää.

Tämä moduuli tekee sanamuodosta LASKETUN funktion mittauksen omista luvuista,
ei ylläpidettyä listaa: CLAUDE.md 6a kohta 1 (yksi lukija joka ei voi palauttaa
väärää). Kun `share_within_5`/`share_over_30` muuttuu, odotettu lause muuttuu
saman tien — testi ei voi jäädä vihreäksi vanhalla sanamuodolla.
"""
from __future__ import annotations

_WORDS: dict[str, dict[int, str]] = {
    "en": {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
           7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven",
           12: "twelve", 15: "fifteen", 20: "twenty"},
    "es": {1: "uno", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis",
           7: "siete", 8: "ocho", 9: "nueve", 10: "diez", 11: "once",
           12: "doce", 15: "quince", 20: "veinte"},
    "pt": {1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco", 6: "seis",
           7: "sete", 8: "oito", 9: "nove", 10: "dez", 11: "onze",
           12: "doze", 15: "quinze", 20: "vinte"},
}

_IN_TEN = {"en": "{n} in ten", "es": "{n} de cada diez", "pt": "{n} em cada dez"}
_ONE_IN_N = {"en": "one in {n}", "es": "uno de cada {n}", "pt": "um em cada {n}"}

LANGS = tuple(_WORDS)


def _word(n: int, lang: str) -> str:
    """Numerosana kielellä `lang`, tai digitit jos taulukko ei kata lukua.

    Emme tiedä etukäteen kuinka pieneksi `share_over_30` voi pudota (isompi N),
    joten taulukon ulkopuolinen luku EI kaadu — se vain näkyy numerona sanan
    sijaan, ja seuraava kopion kirjoittaja huomaa sen tekstistä."""
    return _WORDS[lang].get(n, str(n))


def share_in_ten_phrase(share: float, lang: str) -> str:
    """`share` (0..1) pyöristettynä lähimpään kymmenesosaan: "four in ten" jne.

    Minimi 1: nollaa lähempänä oleva osuus ei saisi sanaa "zero in ten" (sitä
    ei tällä artefaktilla esiinny, mutta funktio ei silti palauta merkitystä
    vailla olevaa lausetta)."""
    if lang not in _WORDS:
        raise ValueError(f"tuntematon kieli: {lang!r}")
    n = max(1, min(10, round(share * 10)))
    return _IN_TEN[lang].format(n=_word(n, lang))


def one_in_n_phrase(share: float, lang: str) -> str:
    """Pieni osuus sanotaan "one in N" (N = round(1/share))."""
    if lang not in _WORDS:
        raise ValueError(f"tuntematon kieli: {lang!r}")
    if share <= 0:
        raise ValueError("one_in_n_phrase vaatii share > 0")
    n = max(2, round(1.0 / share))
    return _ONE_IN_N[lang].format(n=_word(n, lang))
