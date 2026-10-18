"""Agenttiajon tulosportti: vihreä ajo ilman tulosta on punainen (18.10.2026, Villen GO).

Tausta: viikossa kaksi hiljaista nollaa. Bluesky-aivot ajoivat vihreänä 17.10 mutta jonoa ei
syntynyt (0 postausta), ja auto-kehitys päätti ajon vihreänä ilman haaraa, kun avoimia PR:iä oli.
Kumpikaan ei näkynyt autopilotin S1:ssä, koska S1 lukee vain ajon värin.

Sääntö: jokainen Claude-askel ilmoittaa tuloksensa. Hyväksyttyjä tuloksia on kaksi:
  1. odotettu tuotos on olemassa (tiedosto, jossa on vaadittu rivi, tai haara, jolla on commit), tai
  2. perusteltu nolla: agentti kirjoitti ohitustiedostoon syyn (vähintään 15 merkkiä).
Kaikki muu kaataa ajon, jolloin S1 näkee sen. Portti tests/test_auto_kehitys_tulos.py vaatii,
että jokaisen claude-code-action-askeleen jälkeen samassa työssä ajetaan tämä tiedosto.

Käyttö:
  python tulos.py --nimi auto-kehitys --haara auto/ --ohitus /tmp/ohitus.txt
  python tulos.py --nimi julkaisutarkistus --tiedosto /tmp/jt/verdikti.md --rivi '^VERDIKTI: '
Exit 0 = tulos tai perusteltu nolla, 1 = ei tulosta.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

OHITUKSEN_MIN = 15


def _git(*args: str) -> str:
    r = subprocess.run(("git",) + args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip() if r.returncode == 0 else ""


def tiedoston_tulos(polku: str, rivi: str | None) -> str | None:
    p = Path(polku)
    if not p.is_file():
        return None
    teksti = p.read_text(encoding="utf-8", errors="replace")
    if not teksti.strip():
        return None
    if rivi and not re.search(rivi, teksti, re.MULTILINE):
        return None
    return f"tiedosto {polku} ({len(teksti)} merkkiä)"


def haaran_tulos(etuliite: str, pohja: str = "origin/main") -> str | None:
    haara = _git("rev-parse", "--abbrev-ref", "HEAD")
    if not haara.startswith(etuliite):
        return None
    maara = _git("rev-list", "--count", f"{pohja}..HEAD")
    if not maara.isdigit() or int(maara) == 0:
        return None
    return f"haara {haara} ({maara} committia)"


def ohituksen_syy(polku: str | None) -> str | None:
    if not polku or not Path(polku).is_file():
        return None
    syy = " ".join(Path(polku).read_text(encoding="utf-8", errors="replace").split())
    return syy if len(syy) >= OHITUKSEN_MIN else None


def paata(tulos: str | None, syy: str | None) -> tuple[int, str]:
    if tulos:
        return 0, f"Tulos: {tulos}"
    if syy:
        return 0, f"Perusteltu nolla: {syy[:300]}"
    return 1, ("EI TULOSTA: agentti ei tuottanut odotettua tuotosta eikä kirjoittanut ohitukselle syytä. "
               "Vihreä ajo ilman tulosta on vika (katso agentin loki).")


def _yhteenveto(nimi: str, viesti: str) -> None:
    polku = os.environ.get("GITHUB_STEP_SUMMARY")
    if polku:
        with open(polku, "a", encoding="utf-8") as f:
            f.write(f"### {nimi}\n\n{viesti}\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nimi", required=True)
    ap.add_argument("--tiedosto")
    ap.add_argument("--rivi", help="regex, jonka tiedostossa pitää osua")
    ap.add_argument("--haara", help="haaran etuliite, esim. auto/")
    ap.add_argument("--pohja", default="origin/main")
    ap.add_argument("--ohitus", help="tiedosto, johon agentti kirjoittaa perustellun nollan syyn")
    a = ap.parse_args(argv)
    if not a.tiedosto and not a.haara:
        ap.error("anna --tiedosto tai --haara")
    tulos = tiedoston_tulos(a.tiedosto, a.rivi) if a.tiedosto else haaran_tulos(a.haara, a.pohja)
    koodi, viesti = paata(tulos, ohituksen_syy(a.ohitus))
    print(("::error::" if koodi else "") + f"{a.nimi}: {viesti}")
    _yhteenveto(a.nimi, viesti)
    return koodi


if __name__ == "__main__":
    sys.exit(main())
