"""Gradaa mallin oma FPL-rivi kierroksittain -> data/model_squad_gw_scores.json.

🔴 MIKSI TAMA ON OLEMASSA (loydos 25.8.2026)
`/api/fantasy/model-race` lukee tata tiedostoa, ja jonossa oli useita rivejä
joiden heratysehto oli "GW1 gradattu" / `model-race.meta.graded_gws >= 1`.
Mitattu 25.8: tiedostoa EI OLLUT OLEMASSA eika mikaan repossa kirjoittanut
sita. Este ei siis ollut FPL:n `finished`-lippu vaan puuttuva gradaaja.
Endpoint vastasi "First scores land once GW1 finishes" viela senkin jalkeen
kun GW1 oli pelattu, eli selite nimesi vaaran mekanismin.

LAHDE: mallin luvut otetaan FPL:n OMASTA vastauksesta (entry history + picks),
ei lasketa uudelleen. Rivin lukitus ennen deadlinea on todistettu erikseen
(`verify_model_entry_matches_freeze.py` + git-historia), joten tama skripti ei
vastaa siita - se vain lukee toteuman.

🔴 PROVISIONAALISUUS. FPL kaantaa `event.finished` ja `data_checked` vasta
tuntien viiveella viimeisen ottelun jalkeen (mitattu 25.8 klo 07 UTC: GW1
pelattu 21.-24.8, molemmat liput yha False, kaikki 10 ottelua
`finished_provisional: true`). Odottaminen `data_checked`:ia tarkoittaisi ettei
kierrosta nay tuotteessa vuorokauteen sen paattymisen jalkeen.

Ratkaisu: gradataan kun KAIKKI kierroksen ottelut ovat `finished_provisional`,
ja rivi merkitaan `"provisional": true` kunnes `data_checked` kaantyy. Seuraava
ajo gradaa rivin uudelleen ja poistaa lipun. Luku siis nakyy heti, mutta se ei
esiinny lopullisena. 🔴 Lippu on kannettava pintaan asti - provisionaalinen
luku esitettyna lopullisena on tasan se lupausrikko jota vastaan koko tuote
myydaan.

🔴 EI GH-RUNNERILTA (FPL-esto GitHubin IP-avaruudesta). Render tai paikallinen.

Ajo:
    python scripts/grade_model_squad.py            # kaikki gradattavat GW:t
    python scripts/grade_model_squad.py --gw 1     # vain yksi
    python scripts/grade_model_squad.py --dry-run  # ei kirjoita
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from src.data import fpl_api  # noqa: E402

# Sama lahde ja sama env-ohitus kuin verify_model_entry_matches_freeze.py:52,
# jotta mallin rivi ei voi olla eri kahdessa skriptissa.
ENTRY_ID = int(os.environ.get("FPL_MODEL_ENTRY_ID", "116920"))
OUT_PATH = config.DATA_DIR / "model_squad_gw_scores.json"


def _gw_status(boot: dict, fixtures: list[dict]) -> dict[int, dict]:
    """Per kierros: onko se gradattavissa ja onko luku viela provisionaalinen.

    `finished_provisional` per ottelu on tarkempi kuin `event.finished`, joka
    kaantyy vasta kun FPL on kayn ut bonukset lapi. Kierros on gradattavissa
    kun jokainen sen ottelu on pelattu.
    """
    by_gw: dict[int, list[dict]] = {}
    for f in fixtures:
        gw = f.get("event")
        if gw is not None:
            by_gw.setdefault(int(gw), []).append(f)

    out: dict[int, dict] = {}
    for ev in boot.get("events") or []:
        gw = int(ev["id"])
        fx = by_gw.get(gw) or []
        if not fx:
            continue
        all_played = all(f.get("finished_provisional") for f in fx)
        out[gw] = {
            "gradable": all_played,
            # data_checked = FPL on vahvistanut bonukset ja dubious goalsit
            "provisional": not bool(ev.get("data_checked")),
            "fpl_average": ev.get("average_entry_score"),
            "n_fixtures": len(fx),
        }
    return out


def _grade_gw(gw: int, history_by_gw: dict[int, dict], status: dict) -> dict:
    """Yhden kierroksen rivi. Kaikki luvut FPL:n omasta vastauksesta."""
    h = history_by_gw[gw]
    picks = fpl_api.fetch_entry_picks(ENTRY_ID, gw, force=status["provisional"])
    if picks is None:
        raise RuntimeError(
            f"entry {ENTRY_ID}: ei picks-rivia GW{gw}:lle. Malli ei ollut "
            f"mukana talla kierroksella, tai entry-ID on vaara."
        )

    captain_id = None
    captain_mult = 1
    for p in picks.get("picks") or []:
        if p.get("is_captain"):
            captain_id = p["element"]
            captain_mult = p.get("multiplier", 2)

    # Kapteenin TUOMA lisa = hanen pisteensa x (multiplier - 1). Elava
    # pistedata haetaan kierroksen live-vastauksesta.
    captain_added = None
    if captain_id is not None:
        try:
            live = fpl_api.fetch_event_live(gw, force=status["provisional"])
            pts = {e["id"]: (e.get("stats") or {}).get("total_points")
                   for e in live.get("elements") or []}
            base = pts.get(captain_id)
            if base is not None:
                captain_added = int(base) * (int(captain_mult) - 1)
        except Exception:
            # 🔴 Poikkeus -> None, EI nolla. Nolla vaittaisi etta kapteeni ei
            # tuonut mitaan; None sanoo ettemme tieda.
            captain_added = None

    return {
        "gw": gw,
        # FPL:n oma kierrospistemäärä, siirtokustannukset jo mukana.
        "points": h["points"],
        "bench_points": h["bench"],
        "transfer_cost": h["transfer_cost"],
        "fpl_average": status["fpl_average"],
        "captain_id": captain_id,
        "captain_points_added": captain_added,
        "active_chip": picks.get("active_chip"),
        "autosubs": [
            {"in": a.get("element_in"), "out": a.get("element_out")}
            for a in (picks.get("automatic_subs") or [])
        ],
        "provisional": status["provisional"],
        "graded_at": _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0).isoformat(),
    }


def build(only_gw: int | None = None, verbose: bool = True) -> dict:
    boot = fpl_api.fetch_bootstrap(max_age_s=600)
    fixtures = fpl_api.fetch_fixtures(max_age_s=600)
    status = _gw_status(boot, fixtures)

    history = fpl_api.fetch_entry_history(ENTRY_ID)
    history_by_gw = {
        int(r["event"]): {
            "points": int(r.get("points") or 0),
            "bench": int(r.get("points_on_bench") or 0),
            "transfer_cost": int(r.get("event_transfers_cost") or 0),
        }
        for r in (history.get("current") or [])
        if r.get("event") is not None
    }

    # Sailyta aiemmin gradatut rivit: lopullinen rivi ei saa muuttua takaisin
    # provisionaaliseksi jos FPL:n vastaus hetkellisesti puuttuu.
    existing: dict[int, dict] = {}
    if OUT_PATH.exists():
        try:
            prev = json.loads(OUT_PATH.read_text(encoding="utf-8"))
            existing = {int(r["gw"]): r for r in (prev.get("gameweeks") or [])}
        except (OSError, ValueError, KeyError):
            existing = {}

    rows: dict[int, dict] = dict(existing)
    for gw, st in sorted(status.items()):
        if only_gw is not None and gw != only_gw:
            continue
        if not st["gradable"]:
            continue
        if gw not in history_by_gw:
            if verbose:
                print(f"   GW{gw}: entrylla ei riviä, ohitetaan")
            continue
        # Jo lopullisesti gradattu -> ei haeta uudelleen.
        old = existing.get(gw)
        if old is not None and not old.get("provisional") and not st["provisional"]:
            if verbose:
                print(f"   GW{gw}: jo lopullinen, ohitetaan")
            continue
        rows[gw] = _grade_gw(gw, history_by_gw, st)
        if verbose:
            flag = " (PROVISIONAALINEN)" if st["provisional"] else ""
            print(f"   GW{gw}: {rows[gw]['points']} p, keskiarvo "
                  f"{st['fpl_average']}{flag}")

    ordered = [rows[g] for g in sorted(rows)]
    return {
        "meta": {
            "entry_id": ENTRY_ID,
            "source": "FPL entry history + picks (not recomputed)",
            "generated_at": _dt.datetime.now(_dt.timezone.utc)
            .replace(microsecond=0).isoformat(),
            "provisional_gws": [r["gw"] for r in ordered if r.get("provisional")],
        },
        "gameweeks": ordered,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gw", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    out = build(args.gw, verbose=not args.quiet)
    if args.dry_run:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    prov = out["meta"]["provisional_gws"]
    print(f"[ok] {OUT_PATH.name}: {len(out['gameweeks'])} kierrosta"
          + (f", provisionaalisia: {prov}" if prov else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
