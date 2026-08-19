"""Validating the pre-season minutes prior ACROSS THE SUMMER BREAK.

The ship gate walk-forwards inside a single season, so it never touches the
pre-season path (`minutes_model(..., n_last=None)`) at all. That path is what
produces the GW1 numbers, and its damping constant (PRESEASON_HALFLIFE = 10)
was chosen on 2026-08-09 as a JUDGEMENT CALL: the within-season proxy argued
for 4, but the proxy cannot see the summer break, which is the whole reason the
mechanism exists. The judgement call was therefore never measured.

This script measures it on a real fold:
    prior from 24/25  ->  predict 25/26 GW1-6  ->  compare to what happened

Both ends are frozen data (no live API), so the run is reproducible.

The metric is MINUTES, not xP: the prior predicts minutes, and minutes error is
what breaks a GW1 projection (Palmer 43 vs 74 min). The reference points are the
whole half-life space plus flat weighting, which is the same thing as an
infinite half-life (0.5**(x/inf) = 1) and so needs no separate code path.

Output note: the run prints TWO result blocks. Block 1 is the prior on its own.
Block 2 re-runs the same comparison after the 1 keeper + 10 outfield
normalisation the builder applies in production. They are different numbers on
purpose; quote whichever one you mean.

Run:  python -m scripts.validate_preseason_prior
      python -m scripts.validate_preseason_prior --to-gw 3
      python -m scripts.validate_preseason_prior --all-folds
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

import config
from src.models import fpl_xp as xp

PREV_SEASON = "2425"
EVAL_SEASON = "2526"
BALANCED = 1e9          # aareton puoliintuma == tasapaino (pre-9.8. kaytos)
HALFLIVES = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 16.0, 24.0, BALANCED]
MIN_PREV_ROUNDS = 5     # alle taman priori on kohinaa, ei prioria

# Kolme itsenaista kesaa. Yksi fold ei riita paattamaan vakiosta: 9.8. valittu
# 10 on niin lahella optimia etta ero mahtuu yhden kesan kohinaan.
FOLDS = [("2223", "2324"), ("2324", "2425"), ("2425", "2526")]

# GATE: vaimennuksen on oltava perusteltu (parempi kuin tasapaino) JA vakion
# lahella optimia. Ei sovita vakiota dataan - todetaan ettei sita tarvitse
# siirtaa. Kynnys 0.30 min on suurempi kuin foldien valinen optimin heilunta
# (hl6 vs hl8), joten portti ei laukea kohinasta.
GATE_MAX_GAP_TO_BEST_MIN = 0.30


def _artifact(season: str) -> Path:
    return config.PROJECT_ROOT / "data" / f"fpl_prev_season_minutes_{season}.json"


def _load_prev(season: str = PREV_SEASON) -> dict:
    p = _artifact(season)
    if not p.exists():
        raise SystemExit(
            f"Puuttuu {p.name}. Aja ensin:\n"
            f"  python -m scripts.build_fpl_prev_season_minutes --season {season}")
    return json.loads(p.read_text(encoding="utf-8"))


def _load_actuals_from_artifact(season: str, to_gw: int) -> dict[int, float]:
    """Toteutuneet keskiminuutit GW1..to_gw jaadytetysta artefaktista.

    Kaytetaan kun arviointikausi ei ole 25/26 (jonka levyarkisto on eri
    muodossa). Sama code-avain, joten foldit ovat vertailukelpoisia.
    """
    doc = _load_prev(season)
    out: dict[int, float] = {}
    for code_s, p in doc["players"].items():
        mins = 0.0
        for k, v in p["rounds"].items():
            if 1 <= int(k) <= to_gw:
                mins += min(float(v[0]), 90.0)
        out[int(code_s)] = mins / to_gw
    return out


def _load_eval_actuals(to_gw: int) -> tuple[dict[int, float], dict[int, str]]:
    """{code: toteutuneet keskiminuutit GW1..to_gw} 25/26:n levyarkistosta.

    Avain on code EIKA id: FPL:n element-id:t nollautuvat kausittain, ja
    id-mappays olisi kadottanut osan pelaajista NAYTTAMATTA virhetta
    (todennettu 9.8.2026 toisessa yhteydessa: 269/400).
    """
    boot = json.loads((config.RAW_DATA_DIR / "fpl"
                       / f"bootstrap_static_{EVAL_SEASON}.archive.json")
                      .read_text(encoding="utf-8"))
    code_by_id = {e["id"]: e["code"] for e in boot["elements"]}
    name_by_code = {e["code"]: e["web_name"] for e in boot["elements"]}

    sdir = config.RAW_DATA_DIR / "fpl" / f"summary_{EVAL_SEASON}"
    actual: dict[int, float] = {}
    for f in sorted(sdir.glob("element_*.json")):
        eid = int(f.stem.split("_")[1])
        code = code_by_id.get(eid)
        if code is None:
            continue
        hist = json.loads(f.read_text(encoding="utf-8")).get("history") or []
        mins = 0.0
        for r in hist:
            if r.get("round") is not None and 1 <= r["round"] <= to_gw:
                mins += min(float(r.get("minutes") or 0), 90.0)
        actual[code] = mins / to_gw
    return actual, name_by_code


def _predict_mm(prev_players: dict, halflife: float) -> dict[int, dict]:
    """Koko minuuttiestimaatti per code annetulla puoliintumalla."""
    orig = xp.PRESEASON_HALFLIFE
    xp.PRESEASON_HALFLIFE = halflife
    try:
        out: dict[int, dict] = {}
        for code_s, p in prev_players.items():
            rr = {int(k): v for k, v in p["rounds"].items()}
            if len(rr) < MIN_PREV_ROUNDS:
                continue
            mins = {k: float(v[0]) for k, v in rr.items()}
            starts = {k: int(v[1]) for k, v in rr.items()}
            own_rounds = sorted(rr)
            out[int(code_s)] = xp.minutes_model(mins, starts, own_rounds,
                                                n_last=None)
        return out
    finally:
        xp.PRESEASON_HALFLIFE = orig


def _predict(prev_players: dict, halflife: float) -> dict[int, float]:
    return {c: mm["xmins"] for c, mm in _predict_mm(prev_players, halflife).items()}


def _apply_structural(mm_by_code: dict[int, dict], boot: dict) -> dict[int, dict]:
    """Tuotannon rakenteellinen joukkuerajoite (5.8): 1 vahti + 10 kenttaa.

    Replikoi build_fpl_xp.py:n passin: ylibuukattu ryhma leikataan p**k:lla,
    naulatut (raw >= NAILED_PROTECT_P_START) suojattuina; alibuukattu saa
    capatun noston.

    HUOM konservatiivisuus: ryhmassa ovat vain ne pelaajat joilla on 24/25-
    priori. Tuotannossa mukana ovat myos kesan tulokkaat, jotka kasvattavat
    Sigma p_startia ja saavat rajoitteen puremaan KOVEMMIN. Tama mittaus
    aliarvioi siis korjauksen voiman, ei yliarvioi.
    """
    mm = {c: dict(v) for c, v in mm_by_code.items()}
    by_team: dict[int, list[tuple[int, bool]]] = {}
    for e in boot["elements"]:
        code = e["code"]
        if code not in mm:
            continue
        by_team.setdefault(e["team"], []).append((code, e["element_type"] == 1))

    for members in by_team.values():
        for slots, is_gk in ((xp.TEAM_GK_SLOTS, True),
                             (xp.TEAM_OUTFIELD_SLOTS, False)):
            grp = [c for c, gk in members
                   if gk == is_gk and mm[c]["p_start_raw"] > 0]
            if not grp:
                continue
            tot = sum(mm[c]["p_start_raw"] for c in grp)
            if tot > slots:
                prot = [c for c in grp
                        if mm[c]["p_start_raw"] >= xp.NAILED_PROTECT_P_START]
                rest = [c for c in grp if c not in prot]
                prot_sum = sum(mm[c]["p_start_raw"] for c in prot)
                if prot_sum >= slots or not rest:
                    target, cut = grp, slots
                else:
                    target, cut = rest, slots - prot_sum
                k = xp.structural_exponent([mm[c]["p_start_raw"] for c in target],
                                           cut)
                if k > 1.0:
                    for c in target:
                        cur = mm[c]["p_start_raw"]
                        f = (cur ** k) / cur if cur > 0 else 1.0
                        mm[c] = xp.scale_p_start(mm[c], f)
            else:
                f = xp.depth_factor([mm[c]["p_start_raw"] for c in grp], slots)
                if f != 1.0:
                    for c in grp:
                        mm[c] = xp.scale_p_start(mm[c], f)
    return mm


def measure_fold(from_season: str, to_season: str, to_gw: int) -> dict:
    """Yksi kesatauko-fold: MAE per puoliintuma + odotettujen avaajien harha.

    Palauttaa pelkat luvut (ei tulostusta), jotta monifold-portti voi koota ne.
    """
    global PREV_SEASON, EVAL_SEASON
    PREV_SEASON, EVAL_SEASON = from_season, to_season
    prev = _load_prev(from_season)
    if to_season == "2526":
        actual, _ = _load_eval_actuals(to_gw)
    else:
        actual = _load_actuals_from_artifact(to_season, to_gw)

    live_pred = _predict(prev["players"], 10.0)
    codes = sorted(set(live_pred) & set(actual))
    if len(codes) < 50:
        raise SystemExit(f"Populaatio liian pieni (n={len(codes)}) fold "
                         f"{from_season}->{to_season} — code-mappays epaonnistui?")
    ys = np.array([actual[c] for c in codes])

    rows = []
    for hl in HALFLIVES:
        pred = _predict(prev["players"], hl)
        xs = np.array([pred[c] for c in codes])
        rows.append({"halflife": ("flat" if hl == BALANCED else hl),
                     "mae": float(np.mean(np.abs(xs - ys))),
                     "bias": float(np.mean(xs - ys))})

    live = next(r for r in rows if r["halflife"] == 10.0)
    best = min(rows, key=lambda r: r["mae"])
    balanced = next(r for r in rows if r["halflife"] == "flat")
    starters = [c for c in codes if live_pred[c] >= 60 and actual[c] > 0]
    sb = float(np.mean([live_pred[c] - actual[c] for c in starters]))

    return {
        "fold": f"{from_season}->{to_season}", "n": len(codes),
        "live_mae": live["mae"], "best_mae": best["mae"],
        "best_halflife": best["halflife"], "balanced_mae": balanced["mae"],
        "gap_to_best": live["mae"] - best["mae"],
        "starter_bias_min": sb, "n_starters": len(starters),
        "rows": rows,
    }


def run_all_folds(to_gw: int) -> int:
    """Monifold-portti: onko vaimennus perusteltu ja vakio lahella optimia."""
    res = [measure_fold(a, b, to_gw) for a, b in FOLDS]
    print("=" * 74)
    print(f"PRE-SEASON PRIOR: {len(FOLDS)} summer-break folds, "
          f"GW1-{to_gw}, live PRESEASON_HALFLIFE=10")
    print("=" * 74)
    print(f"  {'fold':>12} {'n':>5} {'live':>7} {'best':>7} {'(hl)':>6} "
          f"{'flat':>7} {'gap':>7} {'starter bias':>13}")
    print("  " + "-" * 68)
    for r in res:
        hl = r["best_halflife"]
        hls = hl if isinstance(hl, str) else f"{hl:g}"
        print(f"  {r['fold']:>12} {r['n']:>5} {r['live_mae']:7.3f} "
              f"{r['best_mae']:7.3f} {hls:>6} {r['balanced_mae']:7.3f} "
              f"{r['gap_to_best']:+7.3f} {r['starter_bias_min']:+9.2f} min")

    damping_ok = all(r["live_mae"] < r["balanced_mae"] for r in res)
    near_opt = all(r["gap_to_best"] <= GATE_MAX_GAP_TO_BEST_MIN for r in res)
    passed = damping_ok and near_opt
    print()
    print(f"  damping beats flat weighting in every fold : "
          f"{'YES' if damping_ok else 'NO'}")
    print(f"  live constant within {GATE_MAX_GAP_TO_BEST_MIN} min of best : "
          f"{'YES' if near_opt else 'NO'}")
    print(f"\n  GATE: {'PASS' if passed else 'FAIL'}")
    sb = [r["starter_bias_min"] for r in res]
    print(f"\n  KNOWN BIAS: players the prior expects to start (>=60 min) and who "
          f"did play\n  are projected {min(sb):+.1f} to {max(sb):+.1f} min "
          f"ABOVE what they actually played (mean {sum(sb)/len(sb):+.1f}).\n"
          f"  The direction is the same in all {len(res)} summers. The "
          f"structural squad\n  constraint does NOT correct it (protecting "
          f"nailed-on starters is deliberate),\n  and the availability flag "
          f"does not apply to a player who is fit and playing.")
    print("=" * 74)
    return 0 if passed else 2


def main() -> int:
    global PREV_SEASON, EVAL_SEASON
    ap = argparse.ArgumentParser()
    ap.add_argument("--all-folds", action="store_true",
                    help="aja kaikki kesatauko-foldit + portti (SUOSITUS)")
    ap.add_argument("--to-gw", type=int, default=6, choices=range(1, 11))
    ap.add_argument("--from-season", default=PREV_SEASON,
                    help="kausi josta priori rakennetaan")
    ap.add_argument("--to-season", default=EVAL_SEASON,
                    help="kausi jonka GW1-n vastaan mitataan")
    ap.add_argument("--json", action="store_true", help="tulosta raportti JSONina")
    args = ap.parse_args()

    if args.all_folds:
        return run_all_folds(args.to_gw)

    PREV_SEASON, EVAL_SEASON = args.from_season, args.to_season
    if PREV_SEASON == EVAL_SEASON:
        raise SystemExit("from-season ja to-season eivat voi olla sama kausi.")

    prev = _load_prev(PREV_SEASON)
    if EVAL_SEASON == "2526":
        actual, names = _load_eval_actuals(args.to_gw)
    else:
        actual = _load_actuals_from_artifact(EVAL_SEASON, args.to_gw)
        names = {}

    # Populaatio: pelaaja jolla on priori 24/25:sta JA joka on 25/26:n
    # rekisterissa. PL:sta lahtenyt ei ole priorin virhe.
    base_pred = _predict(prev["players"], xp.PRESEASON_HALFLIFE)
    codes = sorted(set(base_pred) & set(actual))
    if len(codes) < 50:
        raise SystemExit(f"Population too small (n={len(codes)}) - "
                         f"the code mapping most likely failed.")

    ys = np.array([actual[c] for c in codes])

    print("=" * 74)
    print(f"PRE-SEASON PRIOR ACROSS THE SUMMER BREAK: {PREV_SEASON} -> "
          f"{EVAL_SEASON} GW1-{args.to_gw}")
    print("=" * 74)
    print(f"  population: {len(codes)} players "
          f"(prior from >= {MIN_PREV_ROUNDS} rounds of 24/25 AND present in 25/26)")
    print(f"  coverage:   {len(codes)}/{len(base_pred)} players with a prior "
          f"were found in {EVAL_SEASON}")
    print(f"  actual:     mean minutes {ys.mean():.1f} (median "
          f"{np.median(ys):.1f})")
    print()
    print(f"  {'half-life':>14}  {'MAE min':>8}  {'bias':>7}  {'vs live':>8}")
    print("  " + "-" * 44)

    rows = []
    live_mae = None
    for hl in HALFLIVES:
        pred = _predict(prev["players"], hl)
        xs = np.array([pred[c] for c in codes])
        mae = float(np.mean(np.abs(xs - ys)))
        bias = float(np.mean(xs - ys))
        if hl == 10.0:
            live_mae = mae
        rows.append({"halflife": ("flat" if hl == BALANCED else hl),
                     "mae": mae, "bias": bias})

    for r in rows:
        label = r["halflife"] if isinstance(r["halflife"], str) else f"hl{r['halflife']:g}"
        tag = "  <- LIVE" if r["halflife"] == 10.0 else ""
        delta = (f"{r['mae'] - live_mae:+.3f}" if live_mae is not None else "-")
        print(f"  {label:>14}  {r['mae']:8.3f}  {r['bias']:+7.3f}  {delta:>8}{tag}")

    best = min(rows, key=lambda r: r["mae"])
    blabel = (best["halflife"] if isinstance(best["halflife"], str)
              else f"hl{best['halflife']:g}")
    print()
    print(f"  Best: {blabel} (MAE {best['mae']:.3f})")
    if live_mae is not None:
        print(f"  Live (hl10): MAE {live_mae:.3f}  "
              f"= {live_mae - best['mae']:+.3f} vs best")

    balanced = next(r for r in rows if r["halflife"] == "flat")
    print(f"  Flat weighting (behaviour before 2026-08-09): MAE {balanced['mae']:.3f}  "
          f"= {balanced['mae'] - live_mae:+.3f} vs live")

    # Harha ei ole tasaisesti jakautunut, ja se ratkaisee onko se korjattava.
    # Priori EI nae kesan siirtoja eika loukkaantumisia; tuotannossa niita
    # vaimentaa apply_availability (FPL:n saatavuuslippu), jota ei ole
    # historiallisena -> tama mittaus on ILMAN sita. Leikkaukset kertovat
    # kumpi on kyseessa: "ei pelannut lainkaan" vai "pelasi odotettua vahemman".
    print()
    print("  RESULTS BLOCK 1 - prior only "
          "(live hl10, bias = projected - actual):")
    live_pred = _predict(prev["players"], 10.0)
    slices = {
        "all": codes,
        "played >=1 min in GW1-6": [c for c in codes if actual[c] > 0],
        "no minutes at all": [c for c in codes if actual[c] == 0],
        "prior >=60 min (expected starters)": [c for c in codes
                                               if live_pred[c] >= 60],
        "prior >=60 AND played": [c for c in codes
                                  if live_pred[c] >= 60 and actual[c] > 0],
    }
    for label, sel in slices.items():
        if len(sel) < 10:
            print(f"      {label:<36} n={len(sel)} (too small)")
            continue
        xs = np.array([live_pred[c] for c in sel])
        yy = np.array([actual[c] for c in sel])
        print(f"      {label:<36} n={len(sel):>3}  "
              f"MAE {np.mean(np.abs(xs - yy)):6.2f}  "
              f"bias {np.mean(xs - yy):+6.2f}")

    # Absorboiko tuotannon rakenteellinen rajoite harhan? Pelkka priori EI ole
    # se mita kayttaja nakee: builder ajaa 1 vahti + 10 kenttaa -normalisoinnin
    # priorin paalle. Ilman tata mittausta "+16 min ylipredikointi" olisi vaite
    # tuotannosta jota ei ole tuotannosta mitattu.
    bootp = (config.RAW_DATA_DIR / "fpl"
             / f"bootstrap_static_{EVAL_SEASON}.archive.json")
    if not bootp.exists():
        print()
        print(f"  (structural constraint not run: "
              f"{bootp.name} missing -> no squad split for {EVAL_SEASON})")
    else:
        boot = json.loads(bootp.read_text(encoding="utf-8"))
        struct = _apply_structural(_predict_mm(prev["players"], 10.0), boot)
        print()
        print("  RESULTS BLOCK 2 - AFTER the structural squad constraint "
              "(1 keeper + 10 outfield):")
        for label, sel in slices.items():
            sel = [c for c in sel if c in struct]
            if len(sel) < 10:
                continue
            xs = np.array([struct[c]["xmins"] for c in sel])
            yy = np.array([actual[c] for c in sel])
            print(f"      {label:<36} n={len(sel):>3}  "
                  f"MAE {np.mean(np.abs(xs - yy)):6.2f}  "
                  f"bias {np.mean(xs - yy):+6.2f}")
    print("=" * 74)

    if args.json:
        print(json.dumps({"season_from": PREV_SEASON, "season_to": EVAL_SEASON,
                          "to_gw": args.to_gw, "n": len(codes), "rows": rows},
                         ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
