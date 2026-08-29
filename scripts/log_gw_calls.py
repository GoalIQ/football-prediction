"""Kirjaa GW:n julkiset kutsut lokiin ENNEN deadlinea (GW-CALLS-LOKI, 28.8).

Lahteet: data/model_squad_frozen/gw{N}.json (kapteeni, siirrot) +
data/fpl_xp_projections.json (standouts-kortin nelja valintaa samalla
pick_standouts()-funktiolla kuin kortti, joten loki ja PNG eivat voi erota).

Ajo (CI: fpl-data-refresh, freezen jalkeen; kasin ennen kortin postausta):
    python -m scripts.log_gw_calls            # seuraava GW jos freeze on
    python -m scripts.log_gw_calls --gw 2

DEADLINE-SNAPSHOT (29.8): sama skripti ajetaan uudelleen T-2 h -ikkunassa
(workflow'n tuntiajo + scripts/deadline_snapshot_guard.py), jolloin rivi
kirjoitetaan uudelleen tuoreella projektiolla. `logged_at` sailyy
ensimmaisesta kirjauksesta, `updated_at` on viimeisin, ja kortin projected_xi-
kutsu sailyy rivilla (src/models/gw_calls.upsert).

Exit 0: kirjattu tai ei mitaan kirjattavaa (ei freezea / deadline ohi ja rivi
on jo lokissa). Exit 1: deadline ohi eika rivia ole (kutsu jai kirjaamatta,
se on virhe joka kuuluu nakya), tai tekninen virhe.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from scripts.render_standouts_card import pick_standouts  # noqa: E402
from src.models.gw_calls import (NEW_LOG, DeadlinePassed,  # noqa: E402
                                 build_entry, upsert)
from src.models.fpl_gameweek import actionable_gameweek  # noqa: E402  portti: ei next_gameweek suoraan

FROZEN_DIR = config.PROJECT_ROOT / "data" / "model_squad_frozen"
XP_PATH = config.DATA_DIR / "fpl_xp_projections.json"
LOG_PATH = config.DATA_DIR / "gw_calls.json"


def load_log() -> dict:
    if LOG_PATH.exists():
        log = json.loads(LOG_PATH.read_text(encoding="utf-8"))
        # Saantoteksti seuraa koodia (29.8: kaksi aikaleimaa). Versio pysyy.
        log.setdefault("meta", {})["rules"] = NEW_LOG["meta"]["rules"]
        return log
    return json.loads(json.dumps(NEW_LOG))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gw", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    xp = json.loads(XP_PATH.read_text(encoding="utf-8"))
    meta = xp.get("meta") or {}
    gw = args.gw or int(actionable_gameweek(meta) or 0)
    frozen_path = FROZEN_DIR / f"gw{gw}.json"
    if not gw or not frozen_path.exists():
        print(f"GW{gw}: ei freezea ({frozen_path.name}) - ei kirjattavaa.")
        return 0
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    players = xp.get("players") or []
    by_id = {int(p["id"]): p for p in players if "id" in p}
    standouts = pick_standouts(players)
    now = _dt.datetime.now(_dt.timezone.utc)
    log = load_log()
    try:
        entry = build_entry(frozen, standouts, meta, now, by_id)
        upsert(log, entry, now)
    except DeadlinePassed as e:
        have = any(int(r.get("gw", -1)) == gw
                   for r in log.get("gameweeks") or [])
        tail = (" Rivi on lokissa ennen deadlinea kirjattuna." if have
                else " GW:n kutsuja EI ole lokissa.")
        print(("OK: " if have else "VIRHE: ") + str(e) + tail)
        return 0 if have else 1
    for c in entry["calls"]:
        print(f"  {c['call']:14s} {str(c['web_name']):16s} "
              f"{c['metric']}={c['value']}")
    if args.dry_run:
        print("dry-run: ei kirjoitettu.")
        return 0
    LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    print(f"OK: GW{gw} kutsut kirjattu: ensimmainen {entry['logged_at']}, "
          f"viimeisin {entry['updated_at']} (deadline {entry['deadline_utc']}, "
          f"projektio {entry['source'].get('projection_generated_at')}) "
          f"-> {LOG_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
