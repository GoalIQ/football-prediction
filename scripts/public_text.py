"""Portti artefaktikentille jotka renderoityvat sellaisenaan julkiselle sivulle.

TAUSTA (julkaisuportti 29.8.2026, EO-BY-TIER): `meta.metric` pumpataan
`build_fpl_page.py`:ssa suoraan sivucopyksi (`escape(metric)`). Kentta tulee
data-ajosta, ei sivupohjasta, joten mikaan copy-portti ei katso sita. Jos
tulevassa ajossa siihen paatyisi suomenkielinen selitys tai em dash, se
renderoituisi englanninkieliselle sivulle ilman etta yksikaan portti huomaisi.

Sama vikaluokka on aiemmin tullut ulos toista reittia: `/fpl/stats`-sivun
basis-label naytti U+FFFD:n, koska kirjoituspolun encoding oli vaara.

PORTIN RAJA, KIRJATTU: tama mittaa MERKKEJA, ei kielta. Puhtaasti ASCII-merkeilla
kirjoitettu suomenkielinen lause ("Kapteeni lasketaan kahdesti.") menee lapi.
Kielivahti on eri portti; alä oleta taman kattavan sita.

TAMA EI KOSKE PELAAJANIMIA. Guehi, Odegaard ja Sangare ovat oikeaa dataa ja
saavat renderoitya aksentteineen. Portti koskee KOPIOKENTTIA: valmiita
englanninkielisia lauseita joita artefakti kuljettaa sivulle.
"""

from __future__ import annotations

#: Merkit jotka ovat kiellettyja myos ASCII-ulkopuolisuudesta riippumatta.
#: Em dash on talon vakiintunut kielto (28.7 portti); kaarevat lainausmerkit
#: ja ellipsi ovat AI-tunnusmerkkeja joita sivupohjissa ei kayteta.
BANNED = {
    "—": "em dash",
    "–": "en dash",
    "‘": "kaareva heittomerkki",
    "’": "kaareva heittomerkki",
    "“": "kaarevat lainausmerkit",
    "”": "kaarevat lainausmerkit",
    "…": "ellipsimerkki",
    "�": "U+FFFD (rikkinainen encoding)",
}


def public_copy_problems(value: str, field: str) -> list[str]:
    """Palauttaa loydokset. Tyhja lista = kentta kelpaa sivulle."""
    problems: list[str] = []
    for ch, name in BANNED.items():
        if ch in value:
            problems.append(f"{field}: sisaltaa merkin {name} ({ch!r})")
    non_ascii = sorted({c for c in value if ord(c) > 127} - set(BANNED))
    if non_ascii:
        shown = ", ".join(f"{c!r} (U+{ord(c):04X})" for c in non_ascii[:5])
        problems.append(
            f"{field}: sisaltaa ei-ASCII-merkkeja ({shown}). "
            "Kopiokentta renderoityy englanninkieliselle sivulle sellaisenaan."
        )
    return problems


def assert_public_copy(value, field: str) -> str:
    """Palauttaa kentan siivottuna tai kaataa buildin.

    Fail-closed tarkoituksella: punainen build on parempi kuin suomenkielinen
    lause englanninkielisella sivulla. Tyhja arvo kelpaa (lohko jaa pois).
    """
    text = str(value or "").strip()
    if not text:
        return ""
    problems = public_copy_problems(text, field)
    if problems:
        raise ValueError(
            "Julkiselle sivulle menevä artefaktikenttä ei kelpaa:\n  "
            + "\n  ".join(problems)
        )
    return text
