"""xP vs toteuma -gradaus (30.7, Villen GO): putken osa 2.

Kun jäädytetty GW on ratkennut (bootstrap: finished + data_checked), haetaan
toteutuneet pisteet /event/{gw}/live/ ja gradataan jäädytetty ennuste.
Append-only-loki data/fpl_xp_gw_accuracy.json — MAE + bias kokonaisuutena ja
positioittain, EI cherry-pickausta: kaikki jäädytetyt pelaajat mukana, myös
ne joiden xmins petti (0 minuuttia pelannut projisoitu pelaaja on aito miss).

Idempotentti per GW. Exit 0 kun ei gradattavaa; tekninen virhe → 1.

29.8 (IDEA-2026-08-29-xp-graded-public): GW-riviin tulee lisäksi `by_class`
(DNP / blank / ticker / haul toteuman mukaan) ja `comparison` (GoalIQ vs FPL
ep_next vs FPL form samalla rivijoukolla; None jos freeze ei sisällä
ep_next:iä, kuten GW1 ja GW2). Logiikka on src/models/fpl_xp_accuracy.py.
Jo gradattu rivi jolta lohkot puuttuvat täydennetään paikallaan: mae/bias/n
eivät muutu (sama syöte), vain uudet avaimet lisätään, `enriched_at` kertoo
milloin. Toteuma haetaan fpl_api.fetch_event_live:lla (ei suoraa raw-lukua).
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from src.data import fpl_api
from src.models import fpl_xp_accuracy as xacc

FROZEN_DIR = config.PROJECT_ROOT / "data" / "fpl_xp_frozen"
LOG_PATH = config.PROJECT_ROOT / "data" / "fpl_xp_gw_accuracy.json"
ENRICH_KEYS = ("by_class", "by_pos_stats", "comparison")


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def actual_from_live(live: dict) -> dict[int, tuple[float, float]]:
    """event/{gw}/live -> {id: (total_points, minutes)}."""
    out = {}
    for el in live.get("elements") or []:
        st = el.get("stats") or {}
        out[int(el["id"])] = (float(st.get("total_points") or 0),
                              float(st.get("minutes") or 0))
    return out


def grade_gw(frozen: dict, actual: dict[int, tuple[float, float]]) -> dict:
    """Puhdas ydin: jäädytetty ennuste + toteuma {id: (pts, min)} → GW-rivi."""
    g = xacc.grade_players(frozen.get("players") or [], actual)
    return {
        "gw": frozen.get("meta", {}).get("gw"),
        "graded_at": _now(),
        "frozen_at": frozen.get("meta", {}).get("frozen_at"),
        "n": g["n"],
        "mae": g["mae"],
        "bias": g["bias"],
        "mae_by_pos": g["mae_by_pos"],
        "by_class": g["by_class"],
        "by_pos_stats": g["by_pos_stats"],
        "comparison": g["comparison"],
    }


def enrich_row(row: dict, frozen: dict, actual: dict[int, tuple[float, float]]) -> dict:
    """Vanha GW-rivi ilman luokka-/vertailulohkoja: lisää ne, älä koske
    olemassa oleviin lukuihin (append-only-henki: mae/bias/n pysyvät)."""
    g = xacc.grade_players(frozen.get("players") or [], actual)
    for k in ENRICH_KEYS:
        row[k] = g[k]
    row["enriched_at"] = _now()
    return row


def needs_enrich(row: dict) -> bool:
    return any(k not in row for k in ENRICH_KEYS)


def main() -> int:
    if not FROZEN_DIR.exists():
        print("Ei jäädytettyjä kierroksia — ei gradattavaa.")
        return 0
    log = (json.loads(LOG_PATH.read_text(encoding="utf-8"))
           if LOG_PATH.exists() else {"meta": {
               "product": "GoalIQ per-GW xP accuracy log",
               "rules": ("Projection frozen before the deadline (immutable), "
                         "graded once the gameweek finishes. All frozen "
                         "players graded, including those who did not play. "
                         "Append-only."),
           }, "gameweeks": []})
    log["meta"]["comparison_method_code"] = xacc.METHOD_CODE
    log["meta"]["comparison_method"] = xacc.METHOD
    log["meta"]["classes"] = dict(xacc.CLASS_LABELS)
    rows_by_gw = {g.get("gw"): g for g in log["gameweeks"]}
    pending = []   # (gw, frozen, existing_row_or_None)
    for f in sorted(FROZEN_DIR.glob("gw*.json")):
        frozen = json.loads(f.read_text(encoding="utf-8"))
        gw = frozen.get("meta", {}).get("gw")
        if gw is None:
            continue
        row = rows_by_gw.get(gw)
        if row is None or needs_enrich(row):
            pending.append((gw, frozen, row))
    if not pending:
        print("Kaikki jäädytetyt kierrokset on jo gradattu.")
        return 0
    try:
        boot = fpl_api.fetch_bootstrap()
        events = {int(e["id"]): e for e in boot.get("events") or []}
    except Exception as e:
        print(f"VIRHE: bootstrap-haku epäonnistui: {e!r}")
        return 1
    graded = 0
    for gw, frozen, row in pending:
        ev = events.get(int(gw))
        if not ev or not (ev.get("finished") and ev.get("data_checked")):
            print(f"GW{gw}: ei vielä ratkennut (finished+data_checked) — odotetaan.")
            continue
        try:
            live = fpl_api.fetch_event_live(int(gw))
        except Exception as e:
            print(f"VIRHE: event/{gw}/live-haku epäonnistui: {e!r}")
            return 1
        actual = actual_from_live(live)
        if row is None:
            row = grade_gw(frozen, actual)
            log["gameweeks"].append(row)
            verb = "gradattu"
        else:
            enrich_row(row, frozen, actual)
            verb = "täydennetty (by_class + comparison)"
        graded += 1
        cmp_ = row.get("comparison")
        cmp_txt = (f"vertailu n={cmp_['n']} MAE {cmp_['mae']}" if cmp_
                   else "ei vertailua (ep_next ei jäädytetty)")
        print(f"OK: GW{gw} {verb} — n={row['n']}, MAE {row['mae']}, "
              f"bias {row['bias']}, per pos {row['mae_by_pos']}, {cmp_txt}.")
    if graded:
        LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
