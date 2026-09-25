"""XP-KALIBROINTI-GW2-4: kaksi 28.8 oletuksena asetettua parametria mitattuna.

(1) MINUTES_PREV_BLEND (+ PREV_MINUTES_PRIOR_ROUNDS): sekoitetaanko viime
    kauden minuuttiarvio kuluvan kauden ikkunaan START_WINDOW:n aikana.
    Mitta: xMins MAE ja P(aloittaa) Brier kierroksella k, kun malli nakee vain
    kierrokset < k. Sekoitus vaikuttaa vain k = 2..4 (GW5:sta paino on 1.0).
(2) PREV_SEASON_CARRY: viime kauden paino per-90-vauhdeissa (xG, xA).
    Mitta: ennustettu xGI/90 vs kierroksen k toteutunut xGI/90 pelaajille
    joilla >= 45 min kierroksella k, minuuteilla painotettu MAE.

Walk-forward: kierroksen k ennuste kayttaa vain kierroksia < k (FPL
event/{gw}/live) + jaadytetyn viime kauden arkiston
(data/fpl_prev_baselines_2526.json). Sama ydinmalli kuin tuotannossa
(src/models/fpl_xp: minutes_model, blend_minutes, accumulate_history,
carry_prev_season, position_priors, player_rates). EI saatavuutta, syvyytta,
hintaprioria eika joukkuevoimaa: ne ovat samat kaikille varianteille, joten
ero mittaa vain parametria (sama rajaus kuin backtest_fpl_minutes.py).

Read-only. Ajo: python -m scripts.measure_xp_carry_blend [--to-gw 5]
"""
from __future__ import annotations

import argparse
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
PREV_PATH = ROOT / "data" / "fpl_prev_baselines_2526.json"
MIN_MINS_RATE = 45           # xGI/90-toteuma vain riittavan pitkasta nayteestä
CARRY_VALUES = (0.0, 0.3, 0.5, 0.7, 1.0)
BLEND_ROUNDS = (None, 0.5, 1.0, 2.0)   # None = sekoitus pois (tuotanto nyt)


def _get(path: str):
    r = requests.get(f"{FPL}{path}", headers=UA, timeout=60)
    r.raise_for_status()
    return r.json()


def load(to_gw: int):
    boot = _get("/bootstrap-static/")
    elems = {e["id"]: e for e in boot["elements"]}
    live: dict[int, dict[int, dict]] = {}
    for gw in range(1, to_gw + 1):
        d = _get(f"/event/{gw}/live/")
        live[gw] = {el["id"]: el.get("stats") or {} for el in d.get("elements", [])}
    prev = json.loads(PREV_PATH.read_text(encoding="utf-8")).get("players") or {}
    return elems, live, prev


def rows_for(pid: int, live: dict, before: int) -> list[dict]:
    """Pelaajan kierrosrivit < before element-summaryn muodossa. Kierros jolla
    pelaajalla ei ole riviä live-datassa jaa pois (sama kuin summaryssa)."""
    out = []
    for gw in range(1, before):
        s = live.get(gw, {}).get(pid)
        if s is None:
            continue
        out.append({"round": gw, "minutes": s.get("minutes", 0) or 0,
                    "starts": s.get("starts", 0) or 0,
                    "expected_goals": s.get("expected_goals"),
                    "expected_assists": s.get("expected_assists"),
                    "saves": s.get("saves", 0), "yellow_cards": s.get("yellow_cards", 0),
                    "bonus": s.get("bonus", 0)})
    return out


def minutes_variants(pid, rows, prev_b, blend_rounds):
    mr = {r["round"]: float(r["minutes"]) for r in rows}
    sr = {r["round"]: int(r["starts"]) for r in rows}
    mm = xp.minutes_model(mr, sr, sorted(mr), n_last=6)
    if blend_rounds is None or not prev_b or not prev_b.get("mins_by_round"):
        return mm
    pm = {int(k): float(v) for k, v in prev_b["mins_by_round"].items()}
    ps = {int(k): int(v) for k, v in prev_b["starts_by_round"].items()}
    mm_prev = xp.minutes_model(pm, ps, sorted(pm), n_last=None)
    n = len(mr)
    w = 1.0 if n >= xp.START_WINDOW else n / (n + blend_rounds)
    return xp.blend_minutes(mm, mm_prev, w)


def measure(to_gw: int) -> dict:
    elems, live, prev = load(to_gw)
    tulos = {"minutes": {}, "carry": {}, "n": {}}
    for k in range(2, to_gw + 1):
        # --- (1) minuutit: pooli = pelaaja jolla on viime kauden arkisto ja rivi kierroksella k
        err = defaultdict(list)
        brier = defaultdict(list)
        err_gw1_miss = defaultdict(list)
        err_vakio = defaultdict(list)
        for pid, e in elems.items():
            prev_b = prev.get(str(e.get("code")))
            act = live.get(k, {}).get(pid)
            if act is None or not prev_b:
                continue
            rows = rows_for(pid, live, k)
            actual_min = min(90.0, float(act.get("minutes", 0) or 0))
            actual_start = 1.0 if (act.get("starts", 0) or 0) >= 1 else 0.0
            vain_nolla = rows and all((r["minutes"] or 0) == 0 for r in rows)
            # Sekoituksen suunniteltu tapaus (Watkins 28.8): viime kauden
            # vakiopelaaja (>= 1500 min) jolla kuluvalla kaudella vain nollia.
            vakio_pois = vain_nolla and float((prev_b.get("acc") or {}).get("mins") or 0) >= 1500
            for br in BLEND_ROUNDS:
                mm = minutes_variants(pid, rows, prev_b, br)
                err[br].append(abs(mm["xmins"] - actual_min))
                brier[br].append((mm["p_start"] - actual_start) ** 2)
                if vain_nolla:
                    err_gw1_miss[br].append(abs(mm["xmins"] - actual_min))
                if vakio_pois:
                    err_vakio[br].append(abs(mm["xmins"] - actual_min))
        tulos["minutes"][k] = {
            str(br): {"mae": round(sum(v) / len(v), 3), "brier": round(sum(brier[br]) / len(brier[br]), 4),
                      "mae_kaikki_nollat_ennen": (round(sum(err_gw1_miss[br]) / len(err_gw1_miss[br]), 2)
                                                   if err_gw1_miss[br] else None),
                      "n_nollat": len(err_gw1_miss[br]),
                      "mae_vakio_poissa": (round(sum(err_vakio[br]) / len(err_vakio[br]), 2)
                                           if err_vakio[br] else None),
                      "n_vakio_poissa": len(err_vakio[br])}
            for br, v in err.items()}
        tulos["n"][k] = len(err[None])

        # --- (2) carry: priorit ja vauhdit kierroksia < k vasten
        for c in CARRY_VALUES:
            acc_by, pos_by = {}, {}
            for pid, e in elems.items():
                acc = xp.accumulate_history(rows_for(pid, live, k))
                prev_b = prev.get(str(e.get("code")))
                acc = xp.carry_prev_season(acc, (prev_b or {}).get("acc"), carry=c)
                acc_by[pid], pos_by[pid] = acc, e["element_type"]
            priors = xp.position_priors(acc_by, pos_by)
            num = den = 0.0
            for pid, e in elems.items():
                act = live.get(k, {}).get(pid)
                if not act or (act.get("minutes", 0) or 0) < MIN_MINS_RATE:
                    continue
                if e["element_type"] == 1:
                    continue
                m = float(act["minutes"])
                toteuma = 90.0 * (float(act.get("expected_goals") or 0)
                                  + float(act.get("expected_assists") or 0)) / m
                r = xp.player_rates(acc_by[pid], e["element_type"], priors)
                num += m * abs((r["xg90"] + r["xa90"]) - toteuma)
                den += m
            tulos["carry"].setdefault(k, {})[str(c)] = round(num / den, 4) if den else None
    return tulos


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--to-gw", type=int, default=5)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    t = measure(a.to_gw)
    print("MINUUTIT (xMins MAE / P(start) Brier), rivi per kohdekierros; 'None' = sekoitus pois")
    for k, v in t["minutes"].items():
        print(f"  GW{k} n={t['n'][k]}: " + " | ".join(
            f"{br}: {x['mae']:.2f} / {x['brier']:.4f}"
            + (f" (nollat ennen n={x['n_nollat']}: {x['mae_kaikki_nollat_ennen']})" if x['n_nollat'] else "")
            + (f" [vakio poissa n={x['n_vakio_poissa']}: {x['mae_vakio_poissa']}]" if x['n_vakio_poissa'] else "")
            for br, x in v.items()))
    print("CARRY (xGI/90 MAE, minuuteilla painotettu, ulkopelaajat >= 45 min)")
    for k, v in t["carry"].items():
        print(f"  GW{k}: " + " | ".join(f"{c}: {m:.4f}" for c, m in v.items()))
    if a.json:
        a.json.write_text(json.dumps(t, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
