# -*- coding: utf-8 -*-
"""Render-deploy heti kun mallin freeze on mainissa mutta API ei viela nae sita.

MALLIN-KAPTEENI-FREEZE-IKKUNA (22.9.2026). `GET /api/fantasy/model-captain`
lukee `data/model_squad_frozen/gw{N}.json`:n RENDERIN deploysta. fpl-data-refresh
committaa freezen noin 29 h ennen deadlinea, mutta Render saa datan vain
render-daily-deployn mukana (04:45 ja 16:45 UTC). Valiin jaa jopa ~12 h, jolloin
goaliq.app/fpl (hub-deploy, 34 s) nimeaa jaadytetyn rungon kapteenin ja
pro.goaliq.app + mobiili (API) viela entryn edellisen kierroksen kapteenin.
Kaksi julkista pintaa, kaksi eri pelaajaa.

MITATAAN, EI OLETETA. Paatos ei nojaa siihen kirjoittiko TAMA ajo freezen
(se voi olla edellisen ajon, jonka dispatch kaatui) vaan kahteen mittaukseen:

  1. mika on mainissa: `git ls-tree origin/main data/model_squad_frozen/`
     (ei runnerin levy: push voi olla kaatunut, jolloin Renderille ei ole
     mitaan deployattavaa)
  2. mita live-API sanoo: `meta.source`, `meta.gw`, `meta.deadline_gameweek`

Jos mainissa on seuraavan deadlinen freeze ja API sanoo muuta, dispatchataan
render-daily-deploy. Jos edellinen deploy-ajo alkoi alle ODOTUS_MIN sitten, se
on todennakoisesti viela kesken: ei tuplabuildia (500 min/kk kiintio).

Tuntematon tila (API ei vastaa, meta puuttuu) ei dispatchaa eika kaada: se
tulostaa ::warning::n. Deployn laukaisu arvauksen perusteella polttaisi
kiintiota joka tunti niin kauan kuin API on alhaalla.

    python -m scripts.render_deploy_after_freeze          # mittaa + dispatch
    python -m scripts.render_deploy_after_freeze --dry-run
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import urllib.request

API_URL = "https://api.goaliq.app/api/fantasy/model-captain"
WORKFLOW = "render-daily-deploy.yml"
FROZEN_PREFIX = "data/model_squad_frozen/"
ODOTUS_MIN = 45

_GW_RE = re.compile(r"^gw(\d+)\.json$")


def frozen_gws(ls_tree_lines: list[str]) -> set[int]:
    """`git ls-tree --name-only` -rivit -> jaadytetyt kierrokset."""
    out: set[int] = set()
    for line in ls_tree_lines:
        name = line.strip().replace("\\", "/").rsplit("/", 1)[-1]
        m = _GW_RE.match(name)
        if m:
            out.add(int(m.group(1)))
    return out


def paatos(main_gws: set[int], live_meta: dict | None,
           minuutit_edellisesta: float | None) -> tuple[str, str]:
    """-> (toiminto, syy). toiminto: dispatch | ok | odota | tuntematon."""
    if not isinstance(live_meta, dict):
        return "tuntematon", "live-API ei vastannut tai meta puuttuu"
    gw = live_meta.get("deadline_gameweek")
    if not isinstance(gw, int) or isinstance(gw, bool):
        return "ok", "ei seuraavaa deadlinea (kausi paattynyt tai tauko ilman kierrosta)"
    if gw not in main_gws:
        return "ok", f"GW{gw}:n freezea ei ole viela mainissa"
    if live_meta.get("source") == "frozen" and live_meta.get("gw") == gw:
        return "ok", f"API lukee jo GW{gw}:n freezen"
    if minuutit_edellisesta is not None and minuutit_edellisesta < ODOTUS_MIN:
        return "odota", (f"GW{gw}:n freeze on mainissa, API ei nae sita, mutta "
                         f"edellinen {WORKFLOW} alkoi {minuutit_edellisesta:.0f} min "
                         f"sitten (raja {ODOTUS_MIN})")
    return "dispatch", (f"GW{gw}:n freeze on mainissa, API sanoo source="
                        f"{live_meta.get('source')!r} gw={live_meta.get('gw')!r}")


def _main_gws() -> set[int]:
    subprocess.run(["git", "fetch", "origin", "main", "--quiet"], check=False)
    r = subprocess.run(["git", "ls-tree", "--name-only", "origin/main", FROZEN_PREFIX],
                       capture_output=True, text=True, check=True)
    return frozen_gws(r.stdout.splitlines())


def _live_meta() -> dict | None:
    req = urllib.request.Request(API_URL, headers={"User-Agent": "goaliq-ci/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            doc = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 - kaikki verkkovirheet = tuntematon
        print(f"live-API: {type(e).__name__}: {e}")
        return None
    meta = doc.get("meta") if isinstance(doc, dict) else None
    return meta if isinstance(meta, dict) else None


def _minuutit_edellisesta(now: dt.datetime) -> float | None:
    r = subprocess.run(["gh", "run", "list", "--workflow", WORKFLOW, "--limit", "1",
                        "--json", "createdAt"], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"gh run list: {r.stderr.strip()}")
        return None
    try:
        runs = json.loads(r.stdout or "[]")
        if not runs:
            return None
        t = dt.datetime.fromisoformat(runs[0]["createdAt"].replace("Z", "+00:00"))
    except (ValueError, KeyError, TypeError):
        return None
    return (now - t).total_seconds() / 60


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    now = dt.datetime.now(dt.timezone.utc)
    toiminto, syy = paatos(_main_gws(), _live_meta(), _minuutit_edellisesta(now))
    print(f"{toiminto}: {syy}")
    if toiminto == "tuntematon":
        print(f"::warning::freezen Render-deploy jai mittaamatta: {syy}")
        return 0
    if toiminto != "dispatch" or args.dry_run:
        return 0
    r = subprocess.run(["gh", "workflow", "run", WORKFLOW, "--ref", "main"])
    if r.returncode != 0:
        print(f"::error::{WORKFLOW} dispatch kaatui: API nayttaa vanhaa kapteenia "
              "seuraavaan ajastettuun deployhin asti. Tarkista 'permissions: actions: write'.")
        return 1
    print(f"Dispatchattu {WORKFLOW}: API lukee freezen noin 3-5 min kuluttua.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
