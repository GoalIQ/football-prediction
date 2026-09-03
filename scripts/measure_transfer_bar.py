"""Siirtokynnyksen pyyhkaisy usealle rungolle ja ft-arvolle.

MIKSI (3.9.2026, Villen GO). `cos-reports/siirtomoottorin-paatoskynnykset.md`
mittasi kynnyksen YHDELLE rungolle (entry 116920) ja YHDELLA ft-arvolla (1).
Kohta 6 tekee siita ehdon eika varausta: yhden rungon optimi voi olla sen
rungon ominaisuus. Tama skripti ajaa saman pyyhkaisyn usealle entrylle ja
ft-arvolle, ja raportoi moottorin OMAN mittarin (painottamaton nettohyoty
suhteessa ei-siirtoja-baselineen) seka churnin (ostettu ja myyty saman
suunnitelman sisalla).

AJO:
    .venv/Scripts/python.exe -m scripts.measure_transfer_bar
    .venv/Scripts/python.exe -m scripts.measure_transfer_bar --entries 116920,1
"""
from __future__ import annotations

import argparse
import json
import urllib.request

from src.models import fpl_transfers as engine
from src.models.fpl_planner import plan_transfers

BARS = [0.5, 0.75, 1.0, 1.5, 2.0]
FTS = [0, 1, 3, 5]
OVERALL_LEAGUE = 314


def top_entries(n: int) -> list[int]:
    """Yleisliigan karki: julkisia entry-ID:ita joilla runko on oikea."""
    url = (f"https://fantasy.premierleague.com/api/leagues-classic/"
           f"{OVERALL_LEAGUE}/standings/")
    req = urllib.request.Request(url, headers={"User-Agent": "goaliq/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    return [row["entry"] for row in data["standings"]["results"][:n]]


def churn(plan: list[dict]) -> int:
    """Montako pelaajaa ostetaan ja myydaan saman suunnitelman sisalla."""
    bought: set[int] = set()
    n = 0
    for gw in plan:
        for t in gw["transfers"]:
            if t["out"]["id"] in bought:
                n += 1
            bought.add(t["in"]["id"])
    return n


def run(entries: list[int]) -> None:
    original = engine.MIN_GAIN_PER_TRANSFER
    print(f"{'entry':>9} {'ft':>3} {'bar':>5} {'moves':>6} {'hits':>5} "
          f"{'net xP':>8} {'churn':>6}")
    totals: dict[tuple[float], list[float]] = {}
    for entry in entries:
        for ft in FTS:
            for bar in BARS:
                engine.MIN_GAIN_PER_TRANSFER = bar
                try:
                    r = plan_transfers(entry=entry, horizon=6, ft=ft)
                except Exception as exc:                      # noqa: BLE001
                    print(f"{entry:>9} {ft:>3} {bar:>5}  VIRHE: {exc}")
                    continue
                hv = r["hold_verdict"]
                moves = hv["transfers_planned"]
                net = hv["best_move_gain_xp"] or 0.0
                c = churn(r["plan"])
                print(f"{entry:>9} {ft:>3} {bar:>5} {moves:>6} "
                      f"{hv['hits_taken']:>5} {net:>8.2f} {c:>6}")
                totals.setdefault((bar,), []).append(net)
    engine.MIN_GAIN_PER_TRANSFER = original
    print("\nYHTEENVETO (painottamaton nettohyoty, keskiarvo yli entryjen ja ft:n)")
    for (bar,), vals in sorted(totals.items()):
        print(f"  bar {bar:<5} n={len(vals):<3} keskiarvo {sum(vals)/len(vals):+.2f} "
              f"summa {sum(vals):+.2f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entries", default="")
    ap.add_argument("--top", type=int, default=3)
    args = ap.parse_args()
    if args.entries:
        entries = [int(x) for x in args.entries.split(",") if x.strip()]
    else:
        entries = [116920] + top_entries(args.top)
    run(entries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
