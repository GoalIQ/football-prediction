# -*- coding: utf-8 -*-
"""Portti tapaukselle "ajoi, ei tehnyt mitaan" (PLAYER-GW-STALE-GUARD).

MIKSI (23.8.2026, Villen havainto): `fpl/player-gw.json` oli tuotannossa
**25 tuntia vanha ja 31 pelaajassa** samalla kun `fpl-data-refresh` ajoi
**vihreana joka 3. tunti**. Builderi tulosti "SKIP" ja palautti 0, koska
jaadytetylle kaudelle kirjoitettu ehto osui kausivaihdoksen jalkeen elavaan
kauteen. Workflow'n health-steppi tarkistaa `outcome == failure` — se EI nae
tapausta jossa steppi ajoi, palautti nollan eika tuottanut mitaan. Eika sita
nae kukaan muukaan: mitaan ei committoida, joten diffiakaan ei synny.

Tama portti mittaa TUOTOSTA eika exit-koodia. Kaksi vaitetta:

  1. TUOREUS  — elavalla basis-kaudella outputin `generated_at` saa olla
     korkeintaan MAX_AGE_H tuntia vanha.
  2. KATE     — `n_players` ei saa romahtaa suhteessa lahteeseen
     (`data/fpl_player_stats.json`). Raja on MIN_COVERAGE.

Jaadytetylla basis-kaudella kumpikaan ei pade: silloin SKIP on oikea tulos ja
output saa olla kuinka vanha tahansa. Portti tunnistaa tilanteen samasta
taulusta kuin builderi (`SEASON_KEYS`), ei omasta kopiosta.

AJO:  python -m scripts.check_player_gw_freshness
      exit 0 = kunnossa, exit 1 = jaassa tai vajaa.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_fpl_player_gw import OUT, SEASON_KEYS, STATS  # noqa: E402

# 3 h cron -> 12 h antaa kolme peraakkaista valiin jaanytta ajoa ennen kuin
# portti huutaa. Kapeampi ikkuna kolahtaisi normaalista GitHub-driftista
# (workflow'n oma kommentti: ajot driftaavat ja jaavat valiin kuormassa).
MAX_AGE_H = 12
# Builderin oma sanity vaatii TAYDEN katteen, joten tama on vain romahdusvahti
# sille tapaukselle etta output on vanhalta ajolta pienemmalla pelaajajoukolla.
MIN_COVERAGE = 0.9


def _lue(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def tarkista(now: datetime | None = None) -> list[str]:
    """Palauttaa listan vikoja. Tyhja lista = kunnossa."""
    now = now or datetime.now()
    viat: list[str] = []

    stats = _lue(STATS)
    if stats is None:
        return [f"{STATS.name} ei ole luettavissa — lahdetta ei ole, "
                f"builderin tulosta ei voi arvioida."]
    basis = (stats.get("meta") or {}).get("basis_season")
    if basis not in SEASON_KEYS:
        print(f"basis {basis!r} on jaadytetty kausi — tuoreusvaatimusta ei ole. OK.")
        return []

    out = _lue(OUT)
    if out is None:
        return [f"{OUT.name} puuttuu tai on rikki, vaikka basis ({basis}) on "
                f"elava kausi."]
    meta = out.get("meta") or {}

    gen = meta.get("generated_at")
    try:
        t = datetime.fromisoformat(str(gen))
    except (TypeError, ValueError):
        viat.append(f"generated_at ei ole luettava aikaleima: {gen!r}")
    else:
        ika = now - t
        if ika > timedelta(hours=MAX_AGE_H):
            viat.append(
                f"output on {ika.total_seconds() / 3600:.1f} h vanha "
                f"(generated_at {gen}, raja {MAX_AGE_H} h) vaikka basis "
                f"({basis}) on elava kausi — builderi ei ole tuottanut mitaan.")

    want = len(stats.get("players") or [])
    got = int(meta.get("n_players") or 0)
    if want and got < want * MIN_COVERAGE:
        viat.append(
            f"kate {got}/{want} pelaajaa (< {MIN_COVERAGE:.0%}) — output on "
            f"todennakoisesti vanhalta ajolta pienemmalla joukolla.")
    return viat


def main() -> int:
    viat = tarkista()
    if not viat:
        out = _lue(OUT) or {}
        meta = out.get("meta") or {}
        print(f"player-gw tuore: {meta.get('n_players')} pelaajaa, "
              f"generated_at {meta.get('generated_at')}.")
        return 0
    print("PLAYER-GW-STALE-GUARD FAIL:")
    for v in viat:
        print("  " + v)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
