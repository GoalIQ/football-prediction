"""Mittaa DefCon-rivin haarojen laukeamisosuudet ENNEN kuin niille kirjoitetaan copy.

Miksi tama ajetaan ennen koodia: muisti `syyn-haara-joka-ei-laukea-on-copyn-lupaus`
— haara jota ei koskaan laukea on lupaus jota tuote ei pida. DefCon-rivi
muutetaan numeroseinasta muotoon "kategoria + lause + toiminto", ja jokaiselle
kategorialle on osoitettava etta se todella esiintyy pelatulla aineistolla.

Aineisto: `data/fpl_defcon_gw.json` (332 pelaajaa, per-GW-rivit muodossa
[gw, opp, venue, minutes, dc, start], kausi 2025/26).

Kaksi mittausta:

1. **Loppitila** (todellinen data, ei oletuksia): jokainen pelaaja-GW jossa
   minuutteja > 0 -> osui / jai vajaaksi, ja vajaaksi jaaneista kuinka moni
   oli <= 2 pisteen paassa.

2. **Kesken ottelun** (oletus merkitty): live-haarat ("2 puuttuu, peli kesken")
   voivat laueta vain ottelun aikana, eika sellaista tilannekuvaa ole
   tallennettuna. Siksi kertyma arvioidaan LINEAARISENA minuuttien suhteen:
   dc(t) = round(dc_loppu * t / minuutit). Tama on karkea approksimaatio eika
   sita saa julkaista lukuna — se vastaa vain kysymykseen "laukeaako haara
   koskaan", joka on DoD:n vaatimus.

Aja: python scripts/measure_defcon_rows.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "fpl_defcon_gw.json"

# Rivin sarakkeet per_gw-taulukossa.
GW, OPP, VENUE, MINUTES, DC, START = range(6)

SNAPSHOTS = (45, 60, 75)


def end_state(dc: int, threshold: int) -> str:
    if dc >= threshold:
        return "SCORED"
    return "CLOSE_AT_END" if threshold - dc <= 2 else "MISSED"


def in_play_state(dc_now: int, threshold: int) -> str:
    if dc_now >= threshold:
        return "SCORED"
    return "CLOSE" if threshold - dc_now <= 2 else "NEEDS_MORE"


def main() -> None:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    players = payload["players"]
    thresholds = payload["meta"]["thresholds"]

    end = Counter()
    live = {snap: Counter() for snap in SNAPSHOTS}
    rows = 0

    for p in players:
        thr = p.get("threshold")
        if not thr:
            continue  # maalivahdit
        for row in p.get("per_gw") or []:
            minutes = int(row[MINUTES] or 0)
            if minutes <= 0:
                continue
            dc = int(row[DC] or 0)
            rows += 1
            end[end_state(dc, thr)] += 1
            for snap in SNAPSHOTS:
                if minutes < snap:
                    continue
                dc_now = round(dc * snap / minutes)
                live[snap][in_play_state(dc_now, thr)] += 1

    print(f"Pelaaja-GW-rivit joissa minuutteja > 0: {rows}\n")
    print("LOPPUTILA (todellinen data)")
    for k, n in end.most_common():
        print(f"  {k:14s} {n:6d}  {n / rows:6.1%}")

    print("\nKESKEN OTTELUN (OLETUS: lineaarinen kertyma, ei julkaistava luku)")
    for snap in SNAPSHOTS:
        c = live[snap]
        total = sum(c.values())
        if not total:
            continue
        parts = "  ".join(f"{k} {n / total:5.1%}" for k, n in c.most_common())
        print(f"  {snap}' (n={total}): {parts}")

    print("\nJohtopaatos: haara laukeaa kun sen osuus on > 0 %. Nolla tarkoittaa")
    print("etta kategorialle EI kirjoiteta tekstia.")


if __name__ == "__main__":
    main()
