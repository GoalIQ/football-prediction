"""Tuoko PR uusia punaisia testejä? (18.10.2026, automergen testiportti)

Mainissa voi olla ennestään punaisia testejä (esim. live-FPL:n 503 deadlinen aikana). Jos automerge
vaatisi koko sarjan vihreäksi, se ei mergeäisi koskaan; jos se ei katsoisi testejä lainkaan, se voisi
rikkoa mainin. Siksi vertailu: PR:n punaiset ajetaan uudelleen mainissa, ja vain ne, jotka ovat
punaisia PR:ssä mutta eivät mainissa, ovat PR:n tuomia.

  tiedostot  --junit pr.xml          -> punaisten testien tiedostot (ajetaan mainissa uudelleen)
  vertaa     --pr pr.xml --main m.xml -> exit 0 jos uusia punaisia ei ole, 1 jos on (ja lista)

Puuttuva tai rikkinäinen junit-tiedosto on virhe (exit 1), ei "ei punaisia": tyhjä ei ole vihreä.
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def punaiset(polku: str) -> set[tuple[str, str]]:
    juuri = ET.parse(polku).getroot()
    out = set()
    for tc in juuri.iter("testcase"):
        if tc.find("failure") is not None or tc.find("error") is not None:
            out.add((tc.get("classname", ""), tc.get("name", "")))
    return out


def testien_maara(polku: str) -> int:
    return sum(1 for _ in ET.parse(polku).getroot().iter("testcase"))


def tiedostoksi(classname: str) -> str:
    """tests.test_x tai tests.test_x.TestY -> tests/test_x.py"""
    osat = classname.split(".")
    while osat and not osat[-1].startswith("test_"):
        osat.pop()
    return "/".join(osat) + ".py" if osat else ""


def uudet_punaiset(pr: set[tuple[str, str]], main: set[tuple[str, str]]) -> list[tuple[str, str]]:
    return sorted(pr - main)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="komento", required=True)
    t = sub.add_parser("tiedostot")
    t.add_argument("--junit", required=True)
    v = sub.add_parser("vertaa")
    v.add_argument("--pr", required=True)
    v.add_argument("--main")
    a = ap.parse_args(argv)
    try:
        if a.komento == "tiedostot":
            for f in sorted({tiedostoksi(c) for c, _ in punaiset(a.junit)} - {""}):
                if Path(f).is_file():
                    print(f)
            return 0
        if testien_maara(a.pr) == 0:
            print("::error::PR:n junit-tiedostossa ei ole yhtään testiä: tyhjä ei ole vihreä")
            return 1
        pr = punaiset(a.pr)
        mainin = punaiset(a.main) if a.main and Path(a.main).is_file() else set()
        uudet = uudet_punaiset(pr, mainin)
    except (ET.ParseError, FileNotFoundError) as e:
        print(f"::error::junit-tiedostoa ei voitu lukea: {e}")
        return 1
    print(f"PR:ssä punaisia {len(pr)}, joista mainissa ennestään {len(pr & mainin)}, uusia {len(uudet)}.")
    for c, n in uudet:
        print(f"  UUSI PUNAINEN: {c}::{n}")
    return 1 if uudet else 0


if __name__ == "__main__":
    sys.exit(main())
