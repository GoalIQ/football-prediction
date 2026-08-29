#!/usr/bin/env python
"""LLMS-TXT-SYNC-PORTTI: jokainen /fpl-sivun sisaltolohko on kuvattava llms.txt:ssa.

TAUSTA (29.8.2026): llms.txt kuvasi /fpl-sivua yha pelkalla lauseella "clean
sheet probability and fixture difficulty", vaikka sivulle oli 28.-29.8 lisatty
gw-calls-loki, EO-by-tier ja xP-tarkkuuslohko. Tama on tunnettu sokea piste:
copy-sync-tarkistukset kaydaan sivuilta ja SPA:sta, ja llms.txt jaa valiin
koska se ei nayta sivulta. Sama unohdus on toistunut aiemminkin.

MIKSI ANKKURI EIKA SANALISTA: sanalistaportti vanhenee (uusi lohko keksii uudet
sanat, portti pysyy vihreana) ja substring-osuma on sokea. Tama portti vertaa
generoidun fpl.html:n ANKKURI-ID:ita llms.txt:n syvalinkkeihin
(https://goaliq.app/fpl#<ankkuri>). Uusi lohko tuo uuden ankkurin, ja portti
kaatuu kunnes joku joko kuvaa sen llms.txt:ssa tai lisaa sen alla olevaan
EXEMPT-listaan perusteluineen. Fail-closed: uusi lohko ei voi liukua ohi
hiljaisuudella.

Kaytto:
    python -m scripts.check_llms_txt_sync
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "fpl.html"
LLMS = ROOT / "llms.txt"

#: Ankkurit joita EI vaadita llms.txt:hen, jokainen perusteluineen. Lisays
#: tanne on tietoinen paatos, ei oletus.
EXEMPT: dict[str, str] = {
    "about": "yritysesittely, ei sivun omaa sisaltoa",
    "faq": "toistaa muiden lohkojen vaitteet, ei uutta dataa",
    "methodology": "kuvattu llms.txt:n omassa metodologia-osiossa",
    "creators": "yhteydenottokehote, ei dataa",
    "tools": "linkkilista muihin sivuihin jotka llms.txt kuvaa erikseen",
    "pro": "Premium-myyntilohko, ei ilmaispinnan dataa",
    "elite-transfers": "eo-by-tier-lohkon alaotsikko, kuvataan samassa rivissa",
}

ANCHOR_RE = re.compile(r'id="([a-z0-9][a-z0-9-]*)"')
LINK_RE = re.compile(r"goaliq\.app/fpl#([a-z0-9][a-z0-9-]*)")


def page_anchors(html: str) -> set[str]:
    return set(ANCHOR_RE.findall(html))


def llms_anchors(text: str) -> set[str]:
    return set(LINK_RE.findall(text))


def missing_anchors(html: str, llms: str, exempt: dict[str, str] | None = None) -> list[str]:
    """Ankkurit jotka sivulla on mutta joita llms.txt ei kuvaa."""
    ex = EXEMPT if exempt is None else exempt
    return sorted(page_anchors(html) - llms_anchors(llms) - set(ex))


def stale_anchors(html: str, llms: str) -> list[str]:
    """llms.txt:n syvalinkit jotka eivat enaa osoita mihinkaan sivulla.

    Sama vikaluokka toiseen suuntaan: lohko poistetaan sivulta, llms.txt jaa
    lupaamaan sita LLM-lukijoille.
    """
    return sorted(llms_anchors(llms) - page_anchors(html))


def main() -> int:
    if not PAGE.exists():
        print(f"FAIL: {PAGE} puuttuu - porttia ei voi todentaa (fail-closed).")
        return 1
    if not LLMS.exists():
        print(f"FAIL: {LLMS} puuttuu - porttia ei voi todentaa (fail-closed).")
        return 1

    html = PAGE.read_text(encoding="utf-8")
    llms = LLMS.read_text(encoding="utf-8")

    missing = missing_anchors(html, llms)
    stale = stale_anchors(html, llms)

    if not missing and not stale:
        described = sorted(page_anchors(html) - set(EXEMPT))
        print(f"OK: llms.txt kuvaa kaikki {len(described)} /fpl-sisaltolohkoa.")
        return 0

    for a in missing:
        print(
            f"FAIL: /fpl-sivulla on lohko #{a} jota llms.txt ei kuvaa. "
            f"Lisaa rivi joka linkittaa https://goaliq.app/fpl#{a}, "
            f"tai lisaa ankkuri EXEMPT-listaan perusteluineen."
        )
    for a in stale:
        print(
            f"FAIL: llms.txt linkittaa /fpl#{a}, mutta sivulla ei ole sita ankkuria. "
            f"Poista tai korjaa rivi."
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
