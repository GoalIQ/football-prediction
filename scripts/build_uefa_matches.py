# -*- coding: utf-8 -*-
"""Vendoroi UEFAn paattyneet kaudet repoon (data/uefa_matches/).

AJO:  python -m scripts.build_uefa_matches 2324 2425 2526

Ajetaan kasin kun kausi paattyy (kesalla). Kuluvaa kautta EI vendoroida:
se haetaan livena (src/data/uefa_matches.py). Ks. moduulin docstring.
"""
from __future__ import annotations

import sys

from src.data import uefa_matches


def main(argv: list[str]) -> int:
    kaudet = argv or ["2324", "2425", "2526"]
    for p in uefa_matches.rakenna_vendor(kaudet):
        d = uefa_matches._lue_csv(p)
        print(f"{p.name}: {len(d)} ottelua, {d['date'].min().date()} - {d['date'].max().date()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
