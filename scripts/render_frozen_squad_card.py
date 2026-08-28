"""Jakokortti mallin JAADYTETYSTA GW-rungosta (21.8.2026).

MIKSI OMA RENDERI: /fpl/model-xi rakennetaan paivittain uusiksi projektioista,
ja jo samana iltana sen penkki erosi freezesta (Mykolenko puuttui sivulta).
Postattava kuva on lupaus "entered as-is", joten sen AINOA sallittu lahde on
data/model_squad_frozen/gw{n}.json — sama artefakti jota
verify_model_entry_matches_freeze vertaa FPL-tiliin.

Kortilla EI ole xP-lukuja: kaikki kortin tiedot (rivi, kapteenit, hinnat,
kokonaishinta) ovat FPL:n julkisella entry-sivulla deadlinen jalkeen.

Tuloste: HTML scratchpadiin + PNG samaan hakemistoon jos Chrome loytyy.
    python -m scripts.render_frozen_squad_card --gw 1 --out <hakemisto>
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from scripts.build_fpl_longtail import _kit_defs, _kit_svg

FROZEN_DIR = config.PROJECT_ROOT / "data" / "model_squad_frozen"

CSS = """
:root{--teal:#2ED6C2;--amber:#F5C542;--ink:#0B0A09;--ink2:#141311;
--cream:#F3F2F2;--paper:#1F1D1A;--muted:#A8A29A;
--line:rgba(243,242,242,0.24);}
*{margin:0;padding:0;box-sizing:border-box;}
body{background:#000;}
.card{width:1200px;height:675px;background:
linear-gradient(160deg,var(--ink) 0%,var(--ink2) 70%,#101a17 100%);
font-family:'Segoe UI',system-ui,sans-serif;color:var(--cream);
padding:34px 44px 26px;display:flex;flex-direction:column;}
.hdr{display:flex;justify-content:space-between;align-items:baseline;}
.brand{color:var(--teal);font-weight:700;font-size:26px;letter-spacing:.5px;}
.title{font-size:21px;font-weight:600;}
.sub{color:var(--muted);font-size:15px;margin-top:4px;text-align:right;}
.pitch{background:rgba(46,214,194,0.13);border:1px solid var(--line);
padding:6px 4px;margin:16px 0 10px;flex:1;display:flex;
flex-direction:column;justify-content:space-evenly;}
.xirow{display:flex;justify-content:space-evenly;}
.xip{width:104px;text-align:center;position:relative;}
.xip b{display:block;font-size:15px;font-weight:600;margin-top:2px;
white-space:nowrap;}
.xip span{display:block;font-size:13px;color:var(--muted);
font-variant-numeric:tabular-nums;}
.badge{position:absolute;top:-4px;right:14px;background:var(--amber);
color:var(--ink);font-size:13px;font-weight:700;width:22px;height:22px;
border-radius:50%;line-height:22px;}
.badge.v{background:var(--cream);}
.bench{display:flex;align-items:center;gap:18px;border-top:1px solid var(--line);
padding-top:10px;}
.bench .lbl{color:var(--muted);font-size:14px;width:60px;}
.bench .xip{width:96px;}
.bench .xip b{font-size:13px;}
.ftr{display:flex;justify-content:space-between;color:var(--muted);
font-size:14px;margin-top:10px;}
.ftr b{color:var(--cream);font-weight:600;}
svg.kit{display:block;margin:0 auto;}
"""


def cell(p: dict, cap: int, vice: int, size: int = 54) -> str:
    badge = ""
    if p["id"] == cap:
        badge = '<span class="badge">C</span>'
    elif p["id"] == vice:
        badge = '<span class="badge v">V</span>'
    return ('<div class="xip">' + badge + _kit_svg(p["team_short"], size=size)
            + f'<b>{p["web_name"]}</b>'
            + f'<span>{p["team_short"]} · {p["price"] / 10:.1f}m</span></div>')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gw", type=int, default=1)
    ap.add_argument("--out", default=str(config.PROJECT_ROOT / "outputs"))
    ap.add_argument("--hide-bench", action="store_true",
                    help="jata penkkirivi pois (promopinnan nimiesto, esim. Thiaw)")
    args = ap.parse_args()

    frozen = json.loads(
        (FROZEN_DIR / f"gw{args.gw}.json").read_text(encoding="utf-8"))
    xi, bench = frozen["xi"], frozen["bench"]
    cap, vice = frozen["captain"], frozen["vice_captain"]
    total = sum(p["price"] for p in xi + bench) / 10.0
    import datetime as _dt
    raw = str(frozen.get("meta", {}).get("frozen_at", ""))[:10]
    frozen_at = _dt.date.fromisoformat(raw).strftime("%d %b").lstrip("0") if raw else ""

    rows = {t: [p for p in xi if p["pos"] == t] for t in (1, 2, 3, 4)}
    shape = "-".join(str(len(rows[t])) for t in (2, 3, 4))
    pitch = "".join(
        '<div class="xirow">' + "".join(cell(p, cap, vice) for p in rows[t])
        + "</div>" for t in (1, 2, 3, 4))
    bench_html = "".join(cell(p, cap=-1, vice=-1, size=42) for p in bench)
    shorts = [p["team_short"] for p in xi + bench]

    html = (
        "<!doctype html><meta charset='utf-8'>"
        f"<style>{CSS}</style>"
        f'<svg width="0" height="0" style="position:absolute">{_kit_defs(shorts)}</svg>'
        '<div class="card">'
        '<div class="hdr"><div><span class="brand">GoalIQ</span></div>'
        f'<div><div class="title">The model&#39;s own FPL squad, GW{args.gw} ({shape})</div>'
        f'<div class="sub">Picked by the optimiser, frozen {frozen_at}, entered as-is</div></div></div>'
        f'<div class="pitch">{pitch}</div>'
        ("" if args.hide_bench else f'<div class="bench"><span class="lbl">Bench</span>{bench_html}</div>')
        f'<div class="ftr"><span><b>{total:.1f}m</b> spent</span>'
        # 21.8 portti B1: EI linkkiä /fpl/model-xi-sivulle — se regeneroituu
        # päivittäin ja sen 15 voi erota freezestä (erosi jo samana iltana).
        "<span>entry 116920 · public on fantasy.premierleague.com</span>"
        "<span>goaliq.app</span></div>"
        "</div>")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"model-squad-gw{args.gw}.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"HTML: {html_path}")

    # 22.8: ei kovakoodattua C:\-polkua (test_no_machine_specific_paths) —
    # PATH ensin, sitten Windowsin ohjelmakansiot env-muuttujien kautta.
    candidates = [shutil.which(n) for n in
                  ("chrome", "google-chrome", "chromium", "msedge")]
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env)
        if base:
            candidates.append(
                str(Path(base) / "Google" / "Chrome" / "Application"
                    / "chrome.exe"))
    for exe in candidates:
        if exe and Path(exe).exists():
            png = out_dir / f"model-squad-gw{args.gw}.png"
            subprocess.run(
                [exe, "--headless=new", f"--screenshot={png}",
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
