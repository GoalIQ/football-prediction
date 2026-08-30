#!/usr/bin/env python
"""ILMAISIKKUNA-PORTTI: lupaus ilmaisesta Premiumista ei saa jaada elamaan.

TAUSTA (30.8.2026). "Premium is free on the web until the GW4 deadline on
12 September" oli kovakoodattuna vahintaan kahdeksaan paikkaan, joista vain
YKSI on generoitu. Loput ovat kasin yllapidettyja (faq.html 4 mainintaa,
creators.html, llms.txt, viisi SPA-komponenttia), eika mikaan poista niita.
12.9.2026 klo 12:30 UTC jokainen niista alkaa vaittaa Premiumin olevan
ilmainen kun se ei ole. Vaite koskee tulopuolta ja kytkeytyy paalle itsestaan.

Portti tekee kaksi asiaa:
  1. Ikkunan SULJETTUA: kaatuu jos yksikaan julkinen pinta yha lupaa ilmaista.
     Tama on se hetki jolloin kukaan ei muista katsoa.
  2. Ikkunan ollessa AUKI: tulostaa missa lupaus elaa, jotta blast radius on
     tiedossa ENNEN kuin ikkuna sulkeutuu.

Generoiduilla pinnoilla lause johdetaan `src.free_window`:sta ja katoaa
itsestaan; tama portti on kasin yllapidettyja pintoja varten, joita koodi ei
voi korjata puolestaan.

Kaytto:
    python scripts/check_free_window.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.free_window import day_label, is_open  # noqa: E402

#: Julkiset pinnat joilla lupaus voi elaa. Glob, ei kasin nimetty lista:
#: kasin nimetty lista vanhenee heti kun uusi pinta syntyy
#: (muisti: portin-sanalista-vanhenee).
SURFACE_GLOBS = ("*.html", "fpl/**/*.html", "llms.txt",
                 "web/pro-spa/src/**/*.svelte", "web/pro-spa/src/**/*.ts")

#: Lupaus tunnistetaan MERKITYKSESTA, ei yhdesta merkkijonosta: sama vaite on
#: kirjoitettu useassa sanamuodossa (muisti: sama-vaite-monessa-sanamuodossa).
CLAIM_RE = re.compile(
    r"(free on the web until|Premium is free until|"
    r"free until the GW4 deadline|nothing to pay for GW1)", re.I)


def surfaces() -> list[Path]:
    out: list[Path] = []
    for g in SURFACE_GLOBS:
        out.extend(sorted(ROOT.glob(g)))
    return [p for p in out if p.is_file()]


def hits(paths=None) -> list[tuple[str, int, str]]:
    found = []
    for p in (paths if paths is not None else surfaces()):
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in CLAIM_RE.finditer(txt):
            line = txt[:m.start()].count("\n") + 1
            found.append((str(p.relative_to(ROOT)), line, m.group(0)))
    return found


def main() -> int:
    paths = surfaces()
    if not paths:
        print("FAIL: yhtaan julkista pintaa ei loytynyt - porttia ei voi "
              "todentaa (fail-closed).")
        return 1
    found = hits(paths)
    if is_open():
        print(f"OK: ilmaisikkuna on auki {day_label()} asti. "
              f"Lupaus elaa {len(found)} kohdassa {len({f[0] for f in found})} "
              f"tiedostossa:")
        for f, ln, _ in found:
            print(f"     {f}:{ln}")
        print("     (generoidut pinnat siivoutuvat itse; kasin yllapidetyt "
              "eivat - tama portti kaatuu niista kun ikkuna sulkeutuu)")
        return 0
    if not found:
        print(f"OK: ilmaisikkuna on kiinni ({day_label()} mennyt) eika "
              f"yksikaan pinta lupaa ilmaista Premiumia.")
        return 0
    for f, ln, txt in found:
        print(f"FAIL: {f}:{ln} lupaa yha ilmaista Premiumia ({txt!r}), "
              f"mutta ikkuna sulkeutui {day_label()}.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
