"""PELIKIELTO-IKKUNA (22.10.2026): poistetaanko istuttu pelikielto minuutti-ikkunasta.

Mittaa `fpl_xp.served_ban_rounds` / `window_minutes` -varianttien vaikutuksen
minuuttimallin ennusteeseen walk-forwardina: kierroksen k ennuste kayttaa vain
pelaajan omia kierroksia < k (n_last=6, sama kuin live-kausi), toteuma on
kierroksen k minuutit (cap 90) ja aloitus.

Variantit:
  nyt          raaka summaus (tuotanto ennen tata)
  pun1..pun3   kieltokierrokset pois, punaisen katto 1..3, keltaisten rajat paalla
  pun3-ei-kelt punaisen katto 3, keltaisten rajat pois
  *-T          lisaksi laukaisijakierros (katkaistu aloitus) pois

Pooli = aktiivinen pelaaja (>= 1 min omassa 6 kierroksen ikkunassa ennen k:ta),
kuten scripts/backtest_fpl_minutes.py. Kohdekierros jaa pois, jos se on itse
varma kieltokierros (ensimmainen 0 min -kierros laukaisijan jalkeen): tuotannossa
sen hoitaa status `s`, ei minuuttimalli. "Muuttuneet" = otos jossa ikkuna eroaa
nykyisesta jossain variantissa; vain siella variantit voivat erota.

Data: FPL-kausiarkistot data/raw/fpl/season_2223..2425 (gw*.csv),
summary_2526 (element-summaryt) ja kuluva kausi FPL:n event/{gw}/live -rajapinnasta.
Read-only. Ajo: python -m scripts.measure_xp_ban_rounds [--raw <polku>] [--json <polku>]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import requests

from src.models import fpl_xp as xp

FPL = "https://fantasy.premierleague.com/api"
UA = {"User-Agent": "Mozilla/5.0 (GoalIQ calibration)"}
CSV_SEASONS = ("2223", "2324", "2425")
N_LAST = 6

VARIANTS: dict[str, dict | None] = {"nyt": None}
for _cap in (1, 2, 3):
    VARIANTS[f"pun{_cap}"] = {"red_max": _cap, "drop_trigger": False}
    VARIANTS[f"pun{_cap}-T"] = {"red_max": _cap, "drop_trigger": True}
VARIANTS["pun3-ei-kelt"] = {"red_max": 3, "drop_trigger": False, "yellow_rules": ()}


def _int(x) -> int:
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def _row(rnd, minutes, starts, red, yc) -> dict:
    return {"round": _int(rnd), "minutes": _int(minutes), "starts": _int(starts),
            "red_cards": _int(red), "yellow_cards": _int(yc)}


def load_csv_season(raw: Path, season: str) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = defaultdict(list)
    sdir = raw / f"season_{season}"
    for f in sorted(sdir.glob("gw*.csv")):
        with f.open(encoding="utf-8", errors="replace", newline="") as fh:
            for r in csv.DictReader(fh):
                out[_int(r["element"])].append(_row(
                    r["round"], r["minutes"], r.get("starts"), r.get("red_cards"),
                    r.get("yellow_cards")))
    return out


def load_summary_season(raw: Path, season: str) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for f in sorted((raw / f"summary_{season}").glob("element_*.json")):
        hist = json.loads(f.read_text(encoding="utf-8")).get("history") or []
        if hist:
            out[_int(f.stem.split("_")[1])] = [
                _row(h.get("round"), h.get("minutes"), h.get("starts"),
                     h.get("red_cards"), h.get("yellow_cards")) for h in hist]
    return out


def load_live_season() -> dict[int, list[dict]]:
    boot = requests.get(f"{FPL}/bootstrap-static/", headers=UA, timeout=60).json()
    done = [ev["id"] for ev in boot["events"] if ev.get("finished")]
    out: dict[int, list[dict]] = defaultdict(list)
    for gw in done:
        d = requests.get(f"{FPL}/event/{gw}/live/", headers=UA, timeout=60).json()
        for el in d.get("elements", []):
            s = el.get("stats") or {}
            # event/live antaa rivin myos pelaajalle jonka joukkue ei pelannut;
            # explain-lista on tyhja silloin (blank). Blankit eivat ole valintoja.
            if not el.get("explain"):
                continue
            out[el["id"]].append(_row(gw, s.get("minutes"), s.get("starts"),
                                      s.get("red_cards"), s.get("yellow_cards")))
    return out


def plain_round_minutes(rows: list[dict]) -> tuple[dict, dict]:
    mr: dict[int, float] = defaultdict(float)
    sr: dict[int, int] = defaultdict(int)
    for r in rows:
        mr[r["round"]] += r["minutes"]
        sr[r["round"]] += r["starts"]
    return dict(mr), dict(sr)


def measure_season(players: dict[int, list[dict]], exclude_cap: int = 1) -> dict:
    err = {v: [] for v in VARIANTS}
    brier = {v: [] for v in VARIANTS}
    err_m = {v: [] for v in VARIANTS}
    brier_m = {v: [] for v in VARIANTS}
    n_excluded = 0
    for _pid, rows in players.items():
        rows = sorted(rows, key=lambda r: r["round"])
        own = sorted({r["round"] for r in rows})
        for i, k in enumerate(own):
            if i == 0:
                continue
            before = [r for r in rows if r["round"] < k]
            window = own[:i][-N_LAST:]
            if sum(r["minutes"] for r in before if r["round"] in window) <= 0:
                continue
            upto = [r for r in rows if r["round"] <= k]
            if k in xp.served_ban_rounds(upto, red_max=exclude_cap, drop_trigger=False):
                n_excluded += 1
                continue
            at_k = [r for r in rows if r["round"] == k]
            actual_min = min(90.0, float(sum(r["minutes"] for r in at_k)))
            actual_start = 1.0 if sum(r["starts"] for r in at_k) >= 1 else 0.0
            preds = {}
            windows = {}
            for name, kw in VARIANTS.items():
                mr, sr = (plain_round_minutes(before) if kw is None
                          else xp.window_minutes(before, **kw))
                mm = xp.minutes_model(mr, sr, sorted(mr), n_last=N_LAST)
                preds[name] = mm
                windows[name] = tuple(sorted(mr)[-N_LAST:])
            changed = any(w != windows["nyt"] for w in windows.values())
            for name, mm in preds.items():
                e = abs(mm["xmins"] - actual_min)
                b = (mm["p_start"] - actual_start) ** 2
                err[name].append(e)
                brier[name].append(b)
                if changed:
                    err_m[name].append(e)
                    brier_m[name].append(b)

    def avg(xs):
        return round(sum(xs) / len(xs), 4) if xs else None

    return {
        "n": len(err["nyt"]), "n_muuttuneet": len(err_m["nyt"]),
        "n_kohde_kieltokierros_pois": n_excluded,
        "mae": {v: avg(x) for v, x in err.items()},
        "brier": {v: avg(x) for v, x in brier.items()},
        "mae_muuttuneet": {v: avg(x) for v, x in err_m.items()},
        "brier_muuttuneet": {v: avg(x) for v, x in brier_m.items()},
        "_sum": {v: (sum(err[v]), sum(brier[v]), sum(err_m[v]), sum(brier_m[v]))
                 for v in VARIANTS},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=ROOT / "data" / "raw" / "fpl")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--ilman-kuluvaa", action="store_true")
    # Kohdekierroksen rajaus: 1 = vain varma ensimmainen kieltokierros,
    # 3 = koko mahdollinen punaisen kielto (tuotannossa status s rajaa sen).
    ap.add_argument("--rajaus", type=int, default=1)
    a = ap.parse_args(argv)
    seasons: dict[str, dict[int, list[dict]]] = {}
    for s in CSV_SEASONS:
        seasons[s] = load_csv_season(a.raw, s)
    seasons["2526"] = load_summary_season(a.raw, "2526")
    if not a.ilman_kuluvaa:
        seasons["2627"] = load_live_season()
    tulos = {}
    tot = {v: [0.0, 0.0, 0.0, 0.0] for v in VARIANTS}
    n_tot = n_m_tot = 0
    for s, players in seasons.items():
        t = measure_season(players, exclude_cap=a.rajaus)
        tulos[s] = {k: v for k, v in t.items() if k != "_sum"}
        n_tot += t["n"]
        n_m_tot += t["n_muuttuneet"]
        for v in VARIANTS:
            for j in range(4):
                tot[v][j] += t["_sum"][v][j]
        print(f"KAUSI {s}: n={t['n']} muuttuneet={t['n_muuttuneet']} "
              f"(kohde = kieltokierros, pois: {t['n_kohde_kieltokierros_pois']})")
        for v in VARIANTS:
            print(f"  {v:13s} MAE {t['mae'][v]:.3f}  Brier {t['brier'][v]:.4f}  |  "
                  f"muuttuneet MAE {t['mae_muuttuneet'][v] or 0:.2f}  "
                  f"Brier {t['brier_muuttuneet'][v] or 0:.4f}")
    print(f"KAIKKI KAUDET: n={n_tot} muuttuneet={n_m_tot}")
    tulos["kaikki"] = {"n": n_tot, "n_muuttuneet": n_m_tot, "variantit": {}}
    for v in VARIANTS:
        mae, br, mae_m, br_m = (tot[v][0] / n_tot, tot[v][1] / n_tot,
                                tot[v][2] / max(n_m_tot, 1), tot[v][3] / max(n_m_tot, 1))
        tulos["kaikki"]["variantit"][v] = {"mae": round(mae, 4), "brier": round(br, 5),
                                           "mae_muuttuneet": round(mae_m, 3),
                                           "brier_muuttuneet": round(br_m, 4)}
        print(f"  {v:13s} MAE {mae:.4f}  Brier {br:.5f}  |  muuttuneet MAE {mae_m:.3f}  "
              f"Brier {br_m:.4f}")
    if a.json:
        a.json.write_text(json.dumps(tulos, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
