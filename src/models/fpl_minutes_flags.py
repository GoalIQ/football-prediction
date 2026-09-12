# -*- coding: utf-8 -*-
"""Minuuttiperustan lippu: YKSI lukija sivulle, kortille ja kaikille pinnoille.

TAUSTA (12.9.2026). Ilmaissivu `/fpl/expected-points` merkitsee Isakin rivin
`!`-lipulla (694 minuuttia viime kaudella -> minuuttiarvio nojaa lyhyeen
otokseen), mutta `gen_share_card.py xp` -kortti EI merkinnyt. Sama pelaaja,
sama sija, kaksi eri lupausta varmuudesta - ja kortti on se joka leviaa ilman
sivua ymparillaan. Loydettiin GW4-deadlinekorttia tehdessa, ennen postausta.

Sama vikaluokka on osunut ennenkin: 25.8 GW2-kortin `COV*`-alaviite ja
`BASELINE-MERKINTA-VAIN-MOBIILISSA`. Aina kun lipun EHTO kirjoitetaan
uudelleen jokaiselle pinnalle, joku pinta unohtaa sen.

CLAUDE.md 6a, mekanismi 1: yksi lukija joka ei voi palauttaa vaaraa. Pinta saa
paattaa MITEN lippu piirretaan (HTML-span, PIL-laatikko, teksti), mutta EI
sita milloin se on olemassa.
"""
from __future__ import annotations

# Merkit ovat osa julkista copya: sivun selite sanoo ne aaneen.
NO_HISTORY = "?"
SHORT_BASIS = "!"


def flag_symbol(p: dict) -> str:
    """'' | '?' | '!' - pelaajan minuuttiperustan lippu.

    Jarjestys on merkitseva: `no_history` voittaa, koska silloin EI OLE
    otosta lainkaan (vahvempi varaus kuin lyhyt otos).
    """
    if p.get("data_basis") == "no_history":
        return NO_HISTORY
    if p.get("minutes_basis_flag") in ("short_season", "new_club"):
        return SHORT_BASIS
    return ""


def legend_parts(rows: list[dict]) -> list[str]:
    """Selitteen osat siina jarjestyksessa kuin sivu ne kirjoittaa.

    Palauttaa PUHTAAN tekstin ilman HTML-entiteetteja: kortti piirtaa
    fonttiin, sivu escapettaa itse.
    """
    symbolit = [flag_symbol(r) for r in rows]
    osat = []
    if SHORT_BASIS in symbolit:
        osat.append("! = last season's minutes do not describe this player's "
                    "role here, either a short season or a move to this club")
    if NO_HISTORY in symbolit:
        osat.append("? = no Premier League games yet, so the role comes from "
                    "price")
    return osat
