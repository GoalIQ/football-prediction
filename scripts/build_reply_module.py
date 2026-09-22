"""Rakenna GW-kohtainen X-reply-moduuli: data/reply_modules/gw{N}.json.

X-REPLY-MOOTTORI (Villen GO 22.9.2026). Suunnitelma:
goaliq-app/cos-reports/ux-uudistus-2026-09/c3-reply-valmius.md luku 2.

Ajo (repon juuressa):
    python -m scripts.build_reply_module            # kuluva vaikutettava kierros
    python -m scripts.build_reply_module --gw 6     # sama, tarkistettuna
    python -m scripts.build_reply_module --dry-run  # ei kirjoita

MITA TAMA TEKEE
1. Lukee paikalliset artefaktit (xP, phase0, gw_calls, accuracy, jaadytetyt)
   ja hakee kolme elavaa lahdetta: /api/fantasy/differentials (sama kuin
   /fpl/differentials-sivun lahde), FPL:n bootstrapin ja mallin entryn
   (116920) viimeisimman pelatun kierroksen.
2. Laskee osiot `src/marketing/reply_sections`in funktioilla (samat joita
   lukija ajaa tuoreusvertailussa).
3. Hakee julkiset sivut (goaliq.app/fpl, /fpl/expected-points,
   /fpl/differentials, 20 seurasivua, /fpl/points/gw{N}) ja todistaa etta
   jokainen luku jolle loytyy rivi nakyy siella SAMANA TEKSTINA.
   Eri teksti samalla rivilla -> exit 1, moduulia EI kirjoiteta.
   Luku jolle ei ole ilmaispintaa kirjataan `public_url: null`; fast-lane-
   portti ei hyvaksy sita julkiseen tekstiin.
4. Kirjaa jokaiselle luvulle value, generated_at, source (tiedosto@commit),
   public_url ja verified_at, seka nimettyjen pelaajien FPL-tilan lukijan
   muutostarkistusta varten.

Exit: 0 kirjoitettu, 1 ristiriita tai lahde puuttuu, 2 vaara kierros.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from src.marketing import public_surface as ps  # noqa: E402
from src.marketing import reply_module as rm  # noqa: E402
from src.marketing import reply_sections as rs  # noqa: E402

API = "https://api.goaliq.app"
FPL = "https://fantasy.premierleague.com/api"


def _git_commit(path: Path) -> str:
    """Viimeisin commit joka koski tiedostoa, + '-dirty' jos tyopuu eroaa."""
    rel = path.relative_to(ROOT).as_posix()
    try:
        c = subprocess.run(["git", "log", "-1", "--format=%h", "--", rel], cwd=ROOT,
                           capture_output=True, text=True, timeout=30).stdout.strip()
        dirty = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=ROOT,
                               timeout=30).returncode != 0
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return (c or "untracked") + ("-dirty" if dirty else "")


def _head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _get_json(url: str, timeout: int = 90) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": ps.UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _read(name: str) -> dict | None:
    p = config.DATA_DIR / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _src(file_label: str, path: Path | None, generated_at, stamp_name: str | None = None,
         **extra) -> dict:
    d = {"file": file_label, "commit": _git_commit(path) if path else extra.pop("commit", None),
         "generated_at": generated_at}
    if stamp_name:
        d["stamp"] = rm.source_stamp(stamp_name)
    d.update(extra)
    return d


def build(gw_arg: int | None, dry_run: bool, out_dir: Path | None = None) -> int:
    from scripts.publish_gate import load_blocklist
    from src.models.fpl_gameweek import actionable_gameweek
    from src.models.fpl_xp import attach_horizon_total_actionable, load_xp_actionable

    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    xp_path = config.DATA_DIR / "fpl_xp_projections.json"
    xp = attach_horizon_total_actionable(load_xp_actionable(xp_path))
    meta = xp.get("meta") or {}
    gw = actionable_gameweek(meta)
    if not isinstance(gw, int):
        print("VIRHE: kierrosta ei voi paatella projektiosta.")
        return 1
    if gw_arg is not None and gw_arg != gw:
        print(f"VIRHE: --gw {gw_arg}, mutta vaikutettava kierros on GW{gw}. Moduuli "
              f"rakennetaan vain kierrokselle johon voi viela vaikuttaa.")
        return 2
    deadline = meta.get("deadline_utc")
    print(f"[1/5] GW{gw}, deadline {deadline}")

    phase0 = _read("fpl_projections_phase0.json") or {}
    blocklist = load_blocklist()
    gw_calls = _read("gw_calls.json")
    acc = _read("accuracy.json")
    xp_acc = _read("fpl_xp_gw_accuracy.json")
    frozen_path = config.DATA_DIR / "model_squad_frozen" / f"gw{gw}.json"
    frozen = json.loads(frozen_path.read_text(encoding="utf-8")) if frozen_path.exists() else None
    fxp_path = config.DATA_DIR / "fpl_xp_frozen" / f"gw{gw}.json"
    frozen_xp = json.loads(fxp_path.read_text(encoding="utf-8")) if fxp_path.exists() else None
    elite = _read("fpl_elite_ownership.json")

    print("[2/5] Elavat lahteet: differentials-API, FPL bootstrap, mallin entry...")
    diff_url = f"{API}/api/fantasy/differentials?max_ownership={rs.DIFFERENTIAL_MAX_OWN:g}"
    try:
        diff_payload = _get_json(diff_url)
    except Exception as e:  # noqa: BLE001
        print(f"VIRHE: differentials-API ei vastannut: {e}")
        return 1
    boot = _get_json(f"{FPL}/bootstrap-static/")
    events = boot.get("events") or []
    done = [e for e in events if e.get("finished") and e.get("data_checked")
            and int(e["id"]) < gw]
    last = max((int(e["id"]) for e in done), default=None)
    entry_event = None
    live_points: dict = {}
    cap_mult = 2
    if last:
        entry_event = _get_json(f"{FPL}/entry/{rs.MODEL_ENTRY}/event/{last}/picks/")
        live = _get_json(f"{FPL}/event/{last}/live/")
        live_points = {int(e["id"]): int((e.get("stats") or {}).get("total_points") or 0)
                       for e in live.get("elements") or []}
        # Mallin jaadytetyn rungon kapteenikerroin: Triple Captain -> 3.
        fz = config.DATA_DIR / "model_squad_frozen" / f"gw{last}.json"
        if fz.exists():
            chip = (json.loads(fz.read_text(encoding="utf-8")).get("meta") or {}).get("chip")
            cap_mult = 3 if chip in ("3xc", "triple_captain") else 2

    print("[3/5] Osiot...")
    sections = {
        "captain_top5": rs.captain_top5(xp, gw, blocklist),
        "xp_top5": rs.xp_top5(xp, gw, blocklist),
        "cs_top": rs.cs_top(phase0, gw),
        "player_lookup": rs.player_lookup(xp, gw, blocklist),
        "differentials": rs.differentials(diff_payload, gw),
        "model_vs_template": rs.model_vs_template(frozen, elite, frozen_xp, gw),
        "last_gw": rs.last_gw(entry_event, events, gw_calls, gw, live_points, cap_mult),
        "track_record": rs.track_record(acc, xp_acc),
    }
    for n, s in sections.items():
        print(f"      {n}: {'ok' if s.get('available') else 'EI: ' + str(s.get('reason'))}")

    print("[4/5] Julkiset pinnat...")
    need = set(rm.ALL_SURFACES)
    if sections["model_vs_template"].get("available"):
        need.add("points_gw")
    pages, surf_meta, errs = rm.fetch_surfaces(need, gw)
    for name in ("gw_xp", "top100", "clean_sheets"):
        pg = (pages.get(name) or {}).get("gw")
        if pg is not None and pg != gw:
            print(f"      huom: {name} nayttaa GW{pg}, moduuli on GW{gw} -> ei reitti "
                  f"taman kierroksen luvuille")
    if errs:
        for e in errs:
            print(f"VIRHE: {e}")
        return 1
    le = sections["last_gw"]
    if le.get("available"):
        eh = (entry_event or {}).get("entry_history") or {}
        ev = next(e for e in events if int(e["id"]) == le["gw"])
        pages["fpl_entry"] = {"url": le["entry_url"], "points": str(int(eh["points"])),
                              "average": str(int(ev["average_entry_score"])),
                              "cost": str(int(eh.get("event_transfers_cost") or 0))}

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sources = {
        "xp": _src("data/fpl_xp_projections.json", xp_path, meta.get("generated_at"), "xp"),
        "phase0": _src("data/fpl_projections_phase0.json",
                       config.DATA_DIR / "fpl_projections_phase0.json",
                       (phase0.get("meta") or {}).get("generated_at"), "phase0"),
        "differentials": {"file": diff_url, "commit": "api",
                          "generated_at": (diff_payload.get("meta") or {}).get("generated_at"),
                          "fetched_at": now_iso},
        "gw_calls": _src("data/gw_calls.json", config.DATA_DIR / "gw_calls.json", None,
                         "gw_calls"),
        "accuracy": _src("data/accuracy.json", config.DATA_DIR / "accuracy.json",
                         (acc or {}).get("updated_at"), "accuracy"),
        "xp_accuracy": _src("data/fpl_xp_gw_accuracy.json",
                            config.DATA_DIR / "fpl_xp_gw_accuracy.json", None, "xp_accuracy"),
        "fpl_entry": {"file": f"{FPL}/entry/{rs.MODEL_ENTRY}/event/{last}/picks/",
                      "commit": "fpl-api", "generated_at": now_iso},
        "fpl_bootstrap": {"file": f"{FPL}/bootstrap-static/", "commit": "fpl-api",
                          "generated_at": now_iso},
        "fpl_live": {"file": f"{FPL}/event/{last}/live/", "commit": "fpl-api",
                     "generated_at": now_iso},
    }
    if frozen:
        sources["frozen"] = _src(f"data/model_squad_frozen/gw{gw}.json", frozen_path,
                                 (frozen.get("meta") or {}).get("frozen_at"))
    if frozen_xp:
        sources["frozen_xp"] = _src(f"data/fpl_xp_frozen/gw{gw}.json", fxp_path,
                                    (frozen_xp.get("meta") or {}).get("frozen_at"))
    if elite:
        sources["elite"] = _src("data/fpl_elite_ownership.json",
                                config.DATA_DIR / "fpl_elite_ownership.json",
                                (elite.get("meta") or {}).get("generated_at"))

    ok, none, bad = rm.resolve_routes(sections, pages, gw, now_iso, sources)
    # fpl_entry-luvut luetaan samasta API-vastauksesta jonka FPL:n entry-sivu
    # renderoi; reitin nimi kertoo sen.
    print(f"      varmennettu julkista pintaa vasten: {ok}, ilman ilmaisreittia: {none}")
    if bad:
        print(f"VIRHE: {len(bad)} lukua eroaa julkiselta pinnalta. Moduulia EI kirjoiteta.")
        for b in bad[:30]:
            print(f"   {b}")
        return 1

    named = {}
    by_id = {int(e["id"]): e for e in boot.get("elements") or []}
    for key, v, row, sname in rm.iter_values(sections):
        if sname in rm.PLAYER_SECTIONS and row and row.get("player_id") is not None:
            pid = int(row["player_id"])
            e = by_id.get(pid)
            if e and str(pid) not in named:
                named[str(pid)] = {"web_name": e.get("web_name"), "status": e.get("status"),
                                   "chance": e.get("chance_of_playing_next_round"),
                                   "news": e.get("news") or ""}

    module = {
        "schema": rm.SCHEMA,
        "gw": gw,
        "deadline_utc": deadline,
        "generated_at": now_iso,
        "generator": "scripts/build_reply_module.py",
        "fp_commit": _head(),
        "drift_rule": rm.DRIFT_RULE,
        "rules": {
            "use": ("A number may go into a public reply only if its public_url is set: "
                    "that is the free page where the reader sees the same text. "
                    "public_url null = not shown on any free page, do not use in "
                    "public text. Checked by scripts/check_reply_numbers.py."),
            "stale": ("load_reply_module refuses after the deadline, when a source was "
                      "regenerated and a selected number would now display differently, "
                      "or when a named player's FPL status, chance or news changed."),
        },
        "sources": sources,
        "surfaces": surf_meta,
        "counts": {"verified": ok, "no_free_route": none},
        "named_players": named,
        "sections": sections,
        "build_started_at": started,
    }
    path = rm.module_path(gw, out_dir)
    if dry_run:
        print(f"[5/5] --dry-run: ei kirjoitettu ({path})")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    # Kompakti: ~480 pelaajaa x 8 lukua, ja jokainen luku kantaa oman
    # lahteensa ja reittinsa (speksi). Sisennys lisaisi koon puolella.
    path.write_text(json.dumps(module, ensure_ascii=False, separators=(",", ":")) + "\n",
                    encoding="utf-8", newline="\n")
    print(f"[5/5] -> {path} ({path.stat().st_size // 1024} kt)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gw", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    return build(a.gw, a.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
