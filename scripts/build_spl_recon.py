"""SPL GW1 clean sheet -täsmäytys julkiselle pinnalle (QUEUE SPL-GW1-RECON).

Mitä tämä tekee: vertaa deadline-hetken julkaistut GW1 CS -ennusteet
toteumaan ja kirjoittaa tuloksen artefaktiksi jonka build_spl_phase0 liittää
metaan -> /api/fantasy?league=spl kantaa sen -> SPA renderöi. Jokainen sivun
luku tulee tästä artefaktista, ei käsin kirjoitetusta copysta (sama sääntö
kuin /fpl/minutes-accuracy 19.8: luku ja sivu samasta ajosta).

LÄHTEET, molemmat nimetty artefaktiin:
- Ennusteet: `data/spl_gw1_deadline_snapshot.json` — ote committista
  118c3957 (bottirefreshin snapshot 2026-08-13T18:53:59, viimeinen ennen
  GW1-otteluiden ratkeamista; ennusteet on fitattu vendoroituun historiaan
  joka päättyy 21.5.2026, joten kierroksen aloitus ei vuoda niihin).
  Ote luodaan `--extract`-ajolla ja committoidaan — git-historia ei ole
  ajonaikainen riippuvuus.
- Toteuma: RSL-fantasy-feedin finished-ottelut skoreineen (sama lähde ja
  sama SHORT_TO_MODEL-mappaus kuin build_spl_phase0:n inseason-fitissä).

NAIIVI VERTAILUTASO on nimettävä eikä arvattava: vakioennuste
p = clean sheet -osuus vendoroidussa kahden kauden historiassa
(spl_results.csv, sama ikkuna jolla malli fitataan). Brier lasketaan
molemmille samoista 18 joukkue-sivusta.

Ajo:
    .venv/Scripts/python.exe scripts/build_spl_recon.py --extract  # kerran
    .venv/Scripts/python.exe scripts/build_spl_recon.py
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402

# 🔴 Portin loydos 20.8: ensimmainen pinni (118c3957) syntyi 18:53:59 UTC,
# kun kierroksen ensimmainen ottelu alkoi 16:15 ja oli jo paattynyt. Luvut
# olivat identtiset, mutta "before the round kicked off" ei olisi ollut
# artefaktin tukema vaite. Tama build on 15:53:22 = 22 min ennen avauspotkua,
# ja GW1-rivit on verifioitu bittitarkasti samoiksi molemmissa commiteissa.
SNAPSHOT_COMMIT = "c7025ad1c6d94ea71938830ea125ee8d7d861368"
SNAPSHOT_PATH = config.PROJECT_ROOT / "data" / "spl_gw1_deadline_snapshot.json"
OUT_PATH = config.PROJECT_ROOT / "data" / "spl_gw1_recon.json"
RESULTS_CSV = config.PROJECT_ROOT / "data" / "spl_results.csv"
GW = 1


def extract_snapshot() -> None:
    """Poimi GW1-ennusteet snapshot-commitista ja vendoroi ote."""
    raw = subprocess.run(
        ["git", "show", f"{SNAPSHOT_COMMIT}:data/spl_projections_phase0.json"],
        cwd=config.PROJECT_ROOT, capture_output=True, check=True,
    ).stdout
    full = json.loads(raw)
    gw1 = [f for f in full["fixtures"] if f.get("gameweek") == GW]
    if len(gw1) != 9:
        raise SystemExit(f"VIRHE: odotettu 9 GW1-ottelua, snapshotissa {len(gw1)}")
    SNAPSHOT_PATH.write_text(json.dumps({
        "provenance": {
            "commit": SNAPSHOT_COMMIT,
            "generated_at": full["meta"]["generated_at"],
            # Julkiselle payloadille englanniksi — kielivahti
            # (test_public_payload_language) valvoo tata, ja se nappasi
            # ensimmaisen suomenkielisen version ennen pushia. Sisalto on
            # portin verifioima: c7025ad-metassa ei ole inseason-kenttaa
            # lainkaan (in-season-fitti shipattiin vasta 19.8), joten
            # "no 26/27 results in the fit" on todistettu eika arvattu.
            "note": (
                "Last build published before the round kicked off (first "
                "GW1 kickoff 13 Aug 2026, 16:15 UTC). Fitted on vendored "
                "history ending 21 May 2026, with no 26/27 results in "
                "the fit."
            ),
        },
        "gameweek": GW,
        "fixtures": [
            {k: f[k] for k in (
                "kickoff", "home", "away", "home_short", "away_short",
                "cs_home_pct", "cs_away_pct",
            )}
            for f in gw1
        ],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Kirjoitettu: {SNAPSHOT_PATH} ({len(gw1)} ottelua)")


def fetch_gw1_results() -> dict[tuple[str, str], tuple[int, int]]:
    """GW1-toteuma RSL-feedistä, avain (home, away) mallinimin."""
    from scripts.build_spl_phase0 import SPL_BASE, SPL_HEADERS, SHORT_TO_MODEL
    import requests

    boot = requests.get(f"{SPL_BASE}/bootstrap-static/", headers=SPL_HEADERS,
                        timeout=30)
    boot.raise_for_status()
    teams_by_id = {t["id"]: t for t in boot.json().get("teams", [])}
    r = requests.get(f"{SPL_BASE}/fixtures/", headers=SPL_HEADERS, timeout=30)
    r.raise_for_status()
    out: dict[tuple[str, str], tuple[int, int]] = {}
    for f in r.json():
        if f.get("event") != GW or not f.get("finished"):
            continue
        if f.get("team_h_score") is None or f.get("team_a_score") is None:
            continue
        th, ta = teams_by_id.get(f.get("team_h")), teams_by_id.get(f.get("team_a"))
        if not th or not ta:
            continue
        key = (SHORT_TO_MODEL[th["short_name"]], SHORT_TO_MODEL[ta["short_name"]])
        out[key] = (int(f["team_h_score"]), int(f["team_a_score"]))
    return out


def naive_cs_rate() -> float:
    """Vakioennusteen taso: CS-osuus vendoroidussa fittihistoriassa."""
    df = pd.read_csv(RESULTS_CSV, encoding="utf-8")
    sides = len(df) * 2
    cs = int((df["away_score"] == 0).sum() + (df["home_score"] == 0).sum())
    return cs / sides


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", action="store_true",
                    help="poimi GW1-ennusteet snapshot-commitista (kerta-ajo)")
    args = ap.parse_args()
    if args.extract:
        extract_snapshot()
        return 0

    if not SNAPSHOT_PATH.exists():
        raise SystemExit(f"{SNAPSHOT_PATH} puuttuu — aja ensin --extract")
    snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    results = fetch_gw1_results()
    if len(results) != len(snap["fixtures"]):
        raise SystemExit(
            f"VIRHE: feedissä {len(results)} ratkennutta GW1-ottelua, "
            f"snapshotissa {len(snap['fixtures'])} — ei kirjoiteta vajaata."
        )

    rows = []
    sides: list[tuple[float, bool]] = []  # (p_cs, toteutuiko)
    for f in snap["fixtures"]:
        key = (f["home"], f["away"])
        if key not in results:
            raise SystemExit(f"VIRHE: ottelulle {key} ei löydy tulosta feedistä.")
        hs, as_ = results[key]
        p_home_cs = f["cs_home_pct"] / 100.0
        p_away_cs = f["cs_away_pct"] / 100.0
        sides.append((p_home_cs, as_ == 0))
        sides.append((p_away_cs, hs == 0))
        rows.append({
            "home": f["home"], "away": f["away"],
            "home_short": f["home_short"], "away_short": f["away_short"],
            "score": f"{hs}-{as_}",
            "cs_home_pct": f["cs_home_pct"], "cs_away_pct": f["cs_away_pct"],
            "cs_home_kept": as_ == 0, "cs_away_kept": hs == 0,
        })

    expected = sum(p for p, _ in sides)
    actual = sum(1 for _, kept in sides if kept)
    brier = sum((p - float(kept)) ** 2 for p, kept in sides) / len(sides)
    naive_p = naive_cs_rate()
    naive_brier = sum((naive_p - float(kept)) ** 2 for _, kept in sides) / len(sides)

    top3 = sorted(
        ((f"{r['home']} (vs {r['away_short']})" if side == "home"
          else f"{r['away']} (at {r['home_short']})",
          r[f"cs_{side}_pct"], r[f"cs_{side}_kept"])
         for r in rows for side in ("home", "away")),
        key=lambda x: -x[1],
    )[:3]

    OUT_PATH.write_text(json.dumps({
        "gameweek": GW,
        "snapshot": snap["provenance"],
        "sides": len(sides),
        "expected_cs": round(expected, 2),
        "actual_cs": actual,
        "brier": round(brier, 4),
        "naive_brier": round(naive_brier, 4),
        "naive_p": round(naive_p, 4),
        "naive_note": (
            "Constant probability equal to the clean sheet share in the same "
            "two-season history the model is fitted on."
        ),
        "top3": [
            {"team": t, "cs_pct": p, "kept": kept} for t, p, kept in top3
        ],
        "fixtures": rows,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"GW{GW}: odotettu {expected:.2f} CS, toteutui {actual} · "
          f"Brier {brier:.4f} vs naiivi {naive_brier:.4f} (p={naive_p:.3f})")
    for t, p, kept in top3:
        print(f"  top3: {t} {p:.1f}% -> {'CS' if kept else 'ei CS'}")
    print(f"Kirjoitettu: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
