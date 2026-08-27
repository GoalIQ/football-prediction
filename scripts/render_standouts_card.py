"""STANDOUTS-CARD (27.8.2026): kierroskohtainen "standouts"-jakokortti.

MIKSI: kilpailijat (NextXI, Vollo) saavat ~25 k nayttoa per kierros
vakiomuodolla: 4-5 korttia (kapteeni, korkein katto, turvallisin, uhkapeli)
+ tuotekuva, joka kierros sama. Meilta puuttui toistuva muoto.

LAHDE: data/fpl_xp_projections.json, VAIN XP-DISTRIBUTION-kentat (xp_dist)
+ xp_per_gw. Ei keksittyja lukuja. Kortti EI nayta per-pelaaja-xP:ta
(Premium) vaan todennakoisyyksia ja prosentteja; erottaja alatunnisteessa:
mallin oma entry liigassa + "graded in public".

Valinnat (kaikki headline-GW:sta, vain pelaajat joilla p_start >= 0.6 ja
status a, jotta kortti ei nosta penkkilaista):
  CAPTAIN PICK   suurin xp_per_gw
  HIGHEST CEILING suurin p90 (tasapeli: p_haul)
  SAFEST PICK    pienin p_blank niista joiden xp_per_gw >= 4
  THE GAMBLE     suurin p_haul niista joiden p_blank >= 0.35

Tuloste: HTML + PNG (Chrome headless) kuten render_frozen_squad_card.
    python -m scripts.render_standouts_card --out outputs/cards
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

XP_PATH = config.DATA_DIR / "fpl_xp_projections.json"
MIN_P_START = 0.6
SAFE_MIN_XP = 4.0
GAMBLE_MIN_BLANK = 0.35

CSS = """
:root{--teal:#2ED6C2;--amber:#F5C542;--ink:#0B0A09;--ink2:#141311;
--cream:#F3F2F2;--muted:#A8A29A;--line:rgba(243,242,242,0.24);}
*{margin:0;padding:0;box-sizing:border-box;}
body{background:#000;}
.card{width:1200px;height:675px;background:
linear-gradient(160deg,var(--ink) 0%,var(--ink2) 70%,#101a17 100%);
font-family:'Segoe UI',system-ui,sans-serif;color:var(--cream);
padding:34px 44px 26px;display:flex;flex-direction:column;}
.hdr{display:flex;justify-content:space-between;align-items:baseline;}
.brand{color:var(--teal);font-weight:700;font-size:26px;letter-spacing:.5px;}
.title{font-size:22px;font-weight:600;}
.sub{color:var(--muted);font-size:15px;margin-top:4px;text-align:right;}
.tiles{display:flex;gap:18px;margin:26px 0 18px;flex:1;}
.tile{flex:1;border:1px solid var(--line);background:rgba(46,214,194,0.07);
padding:18px 18px 14px;display:flex;flex-direction:column;}
.tile .lbl{font-size:13px;letter-spacing:.12em;color:var(--amber);
text-transform:uppercase;font-weight:700;}
.tile .name{font-size:30px;font-weight:700;margin-top:10px;white-space:nowrap;
overflow:hidden;text-overflow:ellipsis;}
.tile .meta{color:var(--muted);font-size:15px;margin-top:2px;}
.tile .range{color:var(--muted);font-size:15px;margin-top:26px;}
.tile .range b{color:var(--cream);font-weight:600;}
.tile .big{font-size:54px;font-weight:700;color:var(--teal);margin-top:auto;
line-height:1;font-variant-numeric:tabular-nums;}
.tile .big small{font-size:18px;color:var(--muted);font-weight:500;margin-left:6px;}
.tile .why{color:var(--muted);font-size:14px;margin-top:8px;min-height:36px;}
.ftr{display:flex;justify-content:space-between;color:var(--muted);
font-size:14px;border-top:1px solid var(--line);padding-top:10px;}
.ftr b{color:var(--cream);}
"""


def _pool(players: list[dict]) -> list[dict]:
    return [p for p in players
            if p.get("xp_dist") and p.get("status", "a") == "a"
            and float(p.get("p_start") or 0) >= MIN_P_START]


def pick_standouts(players: list[dict]) -> dict:
    """Puhdas valintafunktio (testattava). Palauttaa avaimet
    captain/ceiling/safest/gamble -> pelaajarivi tai None."""
    pool = _pool(players)
    if not pool:
        return {"captain": None, "ceiling": None, "safest": None, "gamble": None}
    d = lambda p: p["xp_dist"]
    # Nelja ERI nimea: sama pelaaja ei ole seka katto etta uhkapeli (Isak oli
    # molemmat 27.8 ensimmaisella ajolla). Valinta jarjestyksessa, poissulku.
    taken: list = []
    def rest():
        return [p for p in pool if p["id"] not in taken] if all("id" in p for p in pool)             else [p for p in pool if p["web_name"] not in taken]
    def key(p):
        return p.get("id", p["web_name"])
    captain = max(pool, key=lambda p: (p["xp_per_gw"], d(p)["p_haul"]))
    taken.append(key(captain))
    ceiling = max(rest(), key=lambda p: (d(p)["p90"], d(p)["p_haul"])) if rest() else None
    if ceiling: taken.append(key(ceiling))
    safe_pool = [p for p in rest() if p["xp_per_gw"] >= SAFE_MIN_XP]
    safest = (min(safe_pool, key=lambda p: (d(p)["p_blank"], -p["xp_per_gw"]))
              if safe_pool else None)
    if safest: taken.append(key(safest))
    gamble_pool = [p for p in rest() if d(p)["p_blank"] >= GAMBLE_MIN_BLANK]
    gamble = (max(gamble_pool, key=lambda p: (d(p)["p_haul"], -d(p)["p_blank"]))
              if gamble_pool else None)
    return {"captain": captain, "ceiling": ceiling, "safest": safest,
            "gamble": gamble}


def _tile(lbl: str, p: dict | None, big: str, small: str, why: str) -> str:
    if p is None:
        return (f'<div class="tile"><div class="lbl">{escape(lbl)}</div>'
                '<div class="name">-</div><div class="meta">no pick this week</div>'
                '<div class="big">-</div></div>')
    return (f'<div class="tile"><div class="lbl">{escape(lbl)}</div>'
            f'<div class="name">{escape(p["web_name"])}</div>'
            f'<div class="meta">{escape(p["pos"])} · {escape(p["team_short"])}'
            f' · {float(p.get("price") or 0):.1f}m</div>'
            f'<div class="range">floor <b>{p["xp_dist"]["p10"]}</b> · median '
            f'<b>{p["xp_dist"]["median"]}</b> · ceiling <b>{p["xp_dist"]["p90"]}</b> pts</div>'
            f'<div class="big">{escape(big)}<small>{escape(small)}</small></div>'
            f'<div class="why">{escape(why)}</div></div>')


def build_html(data: dict) -> tuple[str, dict]:
    players = data.get("players") or []
    meta = data.get("meta") or {}
    gw = int(meta.get("next_gameweek") or 0)
    s = pick_standouts(players)
    pct = lambda x: f"{round(x * 100)}%"
    tiles = "".join([
        _tile("Captain pick", s["captain"],
              pct(s["captain"]["xp_dist"]["p_haul"]) if s["captain"] else "-",
              "10+ pts",
              (f"highest projection of the week, blanks {pct(s['captain']['xp_dist']['p_blank'])}"
               if s["captain"] else "")),
        _tile("Highest ceiling", s["ceiling"],
              str(s["ceiling"]["xp_dist"]["p90"]) if s["ceiling"] else "-",
              "pts, 1 week in 10",
              (f"10+ in {pct(s['ceiling']['xp_dist']['p_haul'])} of simulated weeks"
               if s["ceiling"] else "")),
        _tile("Safest pick", s["safest"],
              pct(s["safest"]["xp_dist"]["p_blank"]) if s["safest"] else "-",
              "blank chance",
              (f"floor {s['safest']['xp_dist']['p10']}, median {s['safest']['xp_dist']['median']} pts"
               if s["safest"] else "")),
        _tile("The gamble", s["gamble"],
              pct(s["gamble"]["xp_dist"]["p_haul"]) if s["gamble"] else "-",
              "10+ pts",
              (f"but blanks {pct(s['gamble']['xp_dist']['p_blank'])} of the time"
               if s["gamble"] else "")),
    ])
    n = (s["captain"] or {}).get("xp_dist", {}).get("n", 2000) if s["captain"] else 2000
    html = (
        "<!doctype html><meta charset='utf-8'>"
        f"<style>{CSS}</style>"
        '<div class="card">'
        '<div class="hdr"><div><span class="brand">GoalIQ</span></div>'
        f'<div><div class="title">GW{gw} standouts from {n:,} simulated gameweeks</div>'
        '<div class="sub">Same numbers as our xP, shown as chances instead of averages. '
        'Likely starters only.</div></div></div>'
        f'<div class="tiles">{tiles}</div>'
        '<div class="ftr"><span>The model plays too: <b>entry 116920</b>, '
        'graded in public every gameweek</span>'
        '<span>model projections, not betting advice</span>'
        '<span>goaliq.app/fpl</span></div>'
        "</div>")
    return html, s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(config.PROJECT_ROOT / "outputs" / "cards"))
    args = ap.parse_args()
    data = json.loads(XP_PATH.read_text(encoding="utf-8"))
    html, s = build_html(data)
    gw = int((data.get("meta") or {}).get("next_gameweek") or 0)
    out_dir = Path(args.out).resolve()  # file-URI vaatii absoluuttisen polun
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"goaliq_standouts_gw{gw}.html"
    html_path.write_text(html, encoding="utf-8")
    for k, p in s.items():
        print(f"  {k:8s} {p['web_name'] if p else '-'} "
              f"{p['xp_dist'] if p else ''}")
    print(f"HTML: {html_path}")
    candidates = [shutil.which(n) for n in
                  ("chrome", "google-chrome", "chromium", "msedge")]
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env)
        if base:
            candidates.append(str(Path(base) / "Google" / "Chrome" / "Application"
                                  / "chrome.exe"))
    for exe in candidates:
        if exe and Path(exe).exists():
            png = out_dir / f"goaliq_standouts_gw{gw}.png"
            subprocess.run([exe, "--headless=new", f"--screenshot={png}",
                            "--window-size=1200,675", "--hide-scrollbars",
                            html_path.as_uri()],
                           check=True, capture_output=True, timeout=60)
            print(f"PNG: {png}")
            break
    else:
        print("Chromea ei loytynyt - kaappaa HTML kasin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
