"""Tekstin lukujen kateportti: onko jokainen virkkeen luku faktalohkossa.

MIKSI TAMA ON OMANA MODUULINAAN (17.8.2026). Logiikka asui
`scripts/build_fpl_why.py`:ssa, joka kutsui maksullista tekstirajapintaa.
Kun se ominaisuus poistettiin, tama olisi lahtenyt mukana - mutta
`build_gw_digest.py` kayttaa sita eika sen tekstissa ole mitaan
generoitua. Portti ei siis kuulunut sinne alun perinkaan: se tarkistaa
LUKUJA, ei sita kuka virkkeen kirjoitti.

Kaytto: `ungrounded_numbers(virke, faktat)` palauttaa listan virkkeen
luvuista joita faktalohko EI kanna. Tyhja lista = puhdas.
"""
from __future__ import annotations

import re

_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")

# "per 90" on jalkapallodatan vakioyksikko eika vaite, joten se on ainoa
# sallittu luku jota faktalohko ei kanna. Lista on tarkoituksella yhden
# mittainen: jokainen lisays tahan on reika portissa.
UNIT_NUMBERS = {"90"}


def _numeric_strings(value, out: set[str]) -> None:
    if isinstance(value, dict):
        for v in value.values():
            _numeric_strings(v, out)
        return
    if isinstance(value, (list, tuple)):
        for v in value:
            _numeric_strings(v, out)
        return
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        f = float(value)
        # 4.50 -> "4.5" ja "4.50" ovat sama luku lukijalle; molemmat sallitaan.
        # Kokonaisluvuksi pyoristaminen EI ole: 5.8 ei saa oikeuttaa "6":tta,
        # koska lukija tarkistaa luvun sivulta jossa lukee 5.8.
        out.add(f"{f:g}")
        out.add(f"{f:.1f}")
        out.add(f"{f:.2f}")
        if f == int(f):
            out.add(str(int(f)))
            out.add(f"{f:.0f}")
        return
    if isinstance(value, str):
        for m in _NUM_RE.findall(value):
            out.add(m.replace(",", "."))


def allowed_numbers(facts: dict) -> set[str]:
    out: set[str] = set()
    _numeric_strings(facts, out)
    return out


def ungrounded_numbers(sentence: str, facts: dict) -> list[str]:
    """Virkkeen luvut jotka EIVAT ole faktalohkossa. Tyhja = puhdas."""
    allowed = allowed_numbers(facts) | UNIT_NUMBERS
    bad = []
    for raw in _NUM_RE.findall(sentence or ""):
        token = raw.replace(",", ".")
        candidates = {token}
        # Perakkaiset nollat karsitaan VAIN desimaaliosasta ("4.50" -> "4.5").
        # Ilman tata ehtoa "90" typistyi "9":ksi ja lapaisi portin milla
        # tahansa pelaajalla jolla oli 9 maalia - portti oli sokea tasan
        # silla tavalla jota se oli rakennettu estamaan.
        if "." in token:
            candidates.add(token.rstrip("0").rstrip(".") or "0")
        try:
            f = float(token)
            candidates |= {f"{f:g}", f"{f:.1f}", f"{f:.2f}"}
            if f == int(f):
                candidates.add(str(int(f)))
        except ValueError:
            pass
        if not (candidates & allowed):
            bad.append(raw)
    return bad
