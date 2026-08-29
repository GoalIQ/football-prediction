"""Gradaa lokiin kirjatut kutsut FPL:n omilla pisteilla (GW-CALLS-LOKI, 28.8).

Kierros gradataan kun kaikki sen ottelut ovat finished_provisional, ja rivi
pysyy provisionaalisena kunnes data_checked (sama saanto kuin
grade_model_squad.py). Provisionaalinen rivi gradataan uudelleen joka ajolla,
lopullista ei kirjoiteta yli.

    python -m scripts.grade_gw_calls
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from src.data import fpl_api  # noqa: E402
from src.models.gw_calls import grade_entry, gw_status  # noqa: E402

LOG_PATH = config.DATA_DIR / "gw_calls.json"


def main() -> int:
    if not LOG_PATH.exists():
        print("Ei gw_calls.json-lokia - ei gradattavaa.")
        return 0
    log = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    todo = [r for r in log.get("gameweeks") or []
            if not r.get("graded") or r["graded"].get("provisional")]
    if not todo:
        print("Kaikki kutsut on gradattu lopullisesti.")
        return 0
    try:
        boot = fpl_api.fetch_bootstrap(force=True)
        fixtures = fpl_api.fetch_fixtures(force=True)
    except Exception as e:
        print(f"VIRHE: FPL-haku epaonnistui: {e!r}")
        return 1
    status = gw_status(boot, fixtures)
    now = _dt.datetime.now(_dt.timezone.utc)
    changed = 0
    for row in todo:
        gw = int(row["gw"])
        st = status.get(gw)
        if not st or not st["gradable"]:
            print(f"GW{gw}: ei viela pelattu loppuun - odotetaan.")
            continue
        try:
            live = fpl_api.fetch_event_live(gw, force=True)
        except Exception as e:
            print(f"VIRHE: event/{gw}/live epaonnistui: {e!r}")
            return 1
        points, minutes, starts = {}, {}, {}
        for el in live.get("elements") or []:
            s = el.get("stats") or {}
            points[int(el["id"])] = int(s.get("total_points") or 0)
            minutes[int(el["id"])] = int(s.get("minutes") or 0)
            # 29.8 (DEADLINE-SNAPSHOT, mittari M1): FPL:n live-stats `starts`
            # erottaa aloittajan vaihtopelaajasta; minuutit eivat riita.
            if "starts" in s:
                starts[int(el["id"])] = int(s.get("starts") or 0)
        grade_entry(row, points, minutes, st["provisional"], now,
                    starts=starts or None)
        changed += 1
        flag = " (provisionaalinen)" if st["provisional"] else ""
        print(f"OK: GW{gw} gradattu{flag}: " + ", ".join(
            f"{k} {v['points']}p" for k, v in row["graded"]["by_call"].items()))
    if changed:
        LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
