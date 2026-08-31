# -*- coding: utf-8 -*-
"""Portti: xP-projektion OTSIKKOKIERROS on se johon voi viela vaikuttaa.

MIKSI (31.8.2026). `data/fpl_xp_projections.json` oli tuotannossa tilassa
`meta.deadline_gameweek = 3` mutta `xp_dist.gw = 2` **kaikilla 519
pelaajalla**, ja `components_gw = 2`. Jakauma ja komponentit kuvasivat siis
kierrosta jonka deadline oli mennyt. Kolme pintaa naytti sen: ilmaissivun
`10+` / `Blank` / `Ceiling` -sarakkeet, standouts-kortti ja SPA:n XpTable.

Juurisyy on aina sama: `next_gw = min(pelaamaton fixture)` on KESKEN oleva
kierros niin kauan kuin sen viimeinen ottelu on pelaamatta, eli horisontin
ensimmainen kierros EI ole otsikkokierros. `src/models/fpl_gameweek.py`
dokumentoi taman vikaluokan neljasti; 30.8 se loytyi viidennen ja kuudennen
kerran, ja tama oli seitsemas ja kahdeksas.

Mikaan aiempi portti ei nappaa tata: ne vertaavat LUKUJA, ja nama luvut ovat
oikein - vaarasta kierroksesta.

Kolme vaitetta:
  1. `xp_dist.gw` == `meta.deadline_gameweek` jokaisella pelaajalla jolla
     lohko on (None on sallittu: blank GW).
  2. `components_gw` sama.
  3. Otsikkokierros on horisontissa (`gameweeks[].gw`), muuten komponentit
     olisivat tyhjat.

AJO:  python -m scripts.check_xp_headline_gw
      exit 0 = kunnossa, exit 1 = otsikko vaarassa kierroksessa.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XP_PATH = ROOT / "data" / "fpl_xp_projections.json"


def tarkista(payload: dict) -> list[str]:
    """Palauttaa virheet listana. Tyhja lista = kunnossa."""
    virheet: list[str] = []
    meta = payload.get("meta") or {}
    dl = meta.get("deadline_gameweek")
    if not isinstance(dl, int):
        # Ei tietoa != kunnossa. Ilman deadlinea koko vaite on mittaamaton,
        # ja hiljainen lapipaasto oli tasan se miten tama vika eli.
        return ["meta.deadline_gameweek puuttuu tai ei ole kokonaisluku: "
                "otsikkokierrosta ei voi tarkistaa"]

    players = payload.get("players") or []
    if not players:
        return ["players on tyhja: ei mitaan tarkistettavaa (ei sama kuin kunnossa)"]

    dist_vaarin: dict[int, int] = {}
    comp_vaarin: dict[int, int] = {}
    ei_horisontissa = 0
    for p in players:
        d = p.get("xp_dist")
        if isinstance(d, dict) and isinstance(d.get("gw"), int) and d["gw"] != dl:
            dist_vaarin[d["gw"]] = dist_vaarin.get(d["gw"], 0) + 1
        c = p.get("components_gw")
        if isinstance(c, int) and c != dl:
            comp_vaarin[c] = comp_vaarin.get(c, 0) + 1
        gws = {g.get("gw") for g in (p.get("gameweeks") or [])}
        if gws and dl not in gws:
            ei_horisontissa += 1

    if dist_vaarin:
        virheet.append(
            f"xp_dist.gw != deadline_gameweek ({dl}): "
            + ", ".join(f"GW{g} {n} pelaajalla" for g, n in sorted(dist_vaarin.items())))
    if comp_vaarin:
        virheet.append(
            f"components_gw != deadline_gameweek ({dl}): "
            + ", ".join(f"GW{g} {n} pelaajalla" for g, n in sorted(comp_vaarin.items())))
    if ei_horisontissa:
        virheet.append(f"otsikkokierros GW{dl} ei ole horisontissa "
                       f"{ei_horisontissa} pelaajalla")
    return virheet


def main() -> int:
    if not XP_PATH.exists():
        print(f"::warning::{XP_PATH.name} puuttuu - ohitetaan.")
        return 0
    payload = json.loads(XP_PATH.read_text(encoding="utf-8"))
    virheet = tarkista(payload)
    if virheet:
        for v in virheet:
            print(f"::error::xP-otsikkokierros: {v}")
        print("Otsikkokierros on se johon lukija voi VIELA vaikuttaa "
              "(meta.deadline_gameweek), ei horisontin ensimmainen kierros.")
        return 1
    dl = (payload.get("meta") or {}).get("deadline_gameweek")
    print(f"xP-otsikkokierros OK: GW{dl} kaikilla "
          f"{len(payload.get('players') or [])} pelaajalla.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
