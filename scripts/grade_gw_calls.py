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
from src.models.gw_calls import (entry_actual, entry_transfers_made,  # noqa: E402
                                 grade_entry, gw_status)

import os
ENTRY_ID = int(os.environ.get("FPL_MODEL_ENTRY_ID", "116920"))
LOG_PATH = config.DATA_DIR / "gw_calls.json"


def fill_made(rows: list[dict], fetch) -> int:
    """Taydenna `entry_actual.made` riveille joilta se puuttuu (MODEL-TRANSFERS-RIVI 28.9).

    Ajetaan myos lopullisesti gradatuille riveille: siirrot ovat lukittuja
    deadlinen jalkeen, joten kentan voi lisata jalkikateen, ja GW2-GW5
    gradattiin ennen kuin kentta oli olemassa. Yksi haku kattaa koko kauden.
    Fail-open: jos FPL ei vastaa, kentta jaa puuttumaan ja sivu ei sano
    mitaan (renderoija vaatii kentan)."""
    puuttuvat = [r for r in rows
                 if isinstance(r.get("entry_actual"), dict) and "made" not in r["entry_actual"]]
    if not puuttuvat:
        return 0
    try:
        kaikki = fetch()
    except Exception as e:
        print(f"HUOM: entry/{ENTRY_ID}/transfers ei luettavissa: {e!r}")
        return 0
    if kaikki is None:
        print(f"HUOM: entry/{ENTRY_ID}/transfers 404 - made jaa taydentamatta.")
        return 0
    for r in puuttuvat:
        r["entry_actual"]["made"] = entry_transfers_made(kaikki, int(r["gw"]))
        print(f"OK: GW{r['gw']} entry_actual.made = {len(r['entry_actual']['made'])} siirtoa")
    return len(puuttuvat)


def main() -> int:
    if not LOG_PATH.exists():
        print("Ei gw_calls.json-lokia - ei gradattavaa.")
        return 0
    log = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    rows = log.get("gameweeks") or []
    todo = [r for r in rows
            if not r.get("graded") or r["graded"].get("provisional")]
    changed = 0
    if todo:
        rc = _grade(todo)
        if rc is None:
            return 1
        changed += rc
    else:
        print("Kaikki kutsut on gradattu lopullisesti.")
    changed += fill_made(rows, lambda: fpl_api.fetch_entry_transfers(ENTRY_ID, force=True))
    if changed:
        LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
    return 0


def _grade(todo: list[dict]) -> int | None:
    """Gradaa rivit; palauttaa muuttuneiden maaran, None jos FPL-haku kaatui."""
    try:
        boot = fpl_api.fetch_bootstrap(force=True)
        fixtures = fpl_api.fetch_fixtures(force=True)
    except Exception as e:
        print(f"VIRHE: FPL-haku epaonnistui: {e!r}")
        return None
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
            return None
        points, minutes, starts = {}, {}, {}
        for el in live.get("elements") or []:
            s = el.get("stats") or {}
            points[int(el["id"])] = int(s.get("total_points") or 0)
            minutes[int(el["id"])] = int(s.get("minutes") or 0)
            # 29.8 (DEADLINE-SNAPSHOT, mittari M1): FPL:n live-stats `starts`
            # erottaa aloittajan vaihtopelaajasta; minuutit eivat riita.
            if "starts" in s:
                starts[int(el["id"])] = int(s.get("starts") or 0)
        # 29.8: mita TILI teki (chip, siirrot, hitit). Ilman tata
        # `model_transfers` on ainoa siirtoluku lokissa, ja se on mallin
        # aikomus - GW2:ssa ne erosivat (freeze 3 siirtoa / 2 hittia,
        # entry wildcard / 0 / 0). Fail-open: jos FPL ei vastaa, kentta
        # jaa entiselleen eika gradaus kaadu.
        if not row.get("entry_actual"):
            try:
                hist = fpl_api.fetch_entry_history(ENTRY_ID, force=True)
                hrow = next((h for h in (hist.get("current") or [])
                             if int(h.get("event") or 0) == gw), None)
                picks = fpl_api.fetch_entry_picks(ENTRY_ID, gw, force=True)
                row["entry_actual"] = entry_actual(hrow, picks)
            except Exception as e:
                print(f"HUOM: entry_actual GW{gw} ei luettavissa: {e!r}")
        grade_entry(row, points, minutes, st["provisional"], now,
                    starts=starts or None)
        changed += 1
        flag = " (provisionaalinen)" if st["provisional"] else ""
        print(f"OK: GW{gw} gradattu{flag}: " + ", ".join(
            f"{k} {v['points']}p" for k, v in row["graded"]["by_call"].items()))
    return changed


if __name__ == "__main__":
    sys.exit(main())
