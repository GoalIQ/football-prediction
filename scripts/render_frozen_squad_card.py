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

from src.brand import logo_svg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from scripts.build_fpl_longtail import _kit_defs, _kit_svg

FROZEN_DIR = config.PROJECT_ROOT / "data" / "model_squad_frozen"

CSS = """
:root{--amber:#F5C542;--ink:#0B0A09;--ink2:#141311;
--cream:#F3F2F2;--paper:#1F1D1A;--muted:#A8A29A;
--line:rgba(243,242,242,0.24);}
*{margin:0;padding:0;box-sizing:border-box;}
body{background:#000;}
.card{width:1200px;height:675px;background:
linear-gradient(160deg,var(--ink) 0%,var(--ink2) 70%,#101a17 100%);
font-family:'Segoe UI',system-ui,sans-serif;color:var(--cream);
padding:34px 44px 26px;display:flex;flex-direction:column;}
.hdr{display:flex;justify-content:space-between;align-items:baseline;}
.brand{display:inline-flex;align-items:center;gap:8px;font-family:"IBM Plex Mono",ui-monospace,Consolas,monospace;text-transform:uppercase;font-weight:800;font-size:24px;letter-spacing:.5px;color:var(--cream);}.brand b{font-weight:800;letter-spacing:.5px;}.brand i{font-style:normal;color:var(--amber);}
.title{font-size:21px;font-weight:600;}
.sub{color:var(--muted);font-size:15px;margin-top:4px;text-align:right;}
.pitch{background:rgba(46,214,194,0.13);border:1px solid var(--line);
padding:4px;margin:10px 0 6px;flex:1;display:flex;
flex-direction:column;justify-content:space-evenly;}
.xirow{display:flex;justify-content:space-evenly;}
.xip{width:124px;text-align:center;position:relative;}
.xip b{display:block;font-size:15px;font-weight:600;margin-top:2px;
white-space:nowrap;}
.xip span{display:block;font-size:13px;color:var(--muted);
font-variant-numeric:tabular-nums;}
.xip span.xp{color:var(--cream);font-size:14px;margin-top:3px;font-weight:600;}
.xip span.xp i{font-style:normal;color:var(--muted);font-weight:400;font-size:12px;}
.xip span.sim{color:var(--amber);font-size:11px;margin-top:1px;
white-space:nowrap;letter-spacing:-.1px;}
.badge{position:absolute;top:-4px;right:14px;background:var(--amber);
color:var(--ink);font-size:13px;font-weight:700;width:22px;height:22px;
border-radius:50%;line-height:22px;}
.badge.v{background:var(--cream);}
.badge.tc{width:32px;border-radius:11px;font-size:14px;font-weight:800;right:8px;}
.bench{display:flex;align-items:center;gap:18px;border-top:1px solid var(--line);
padding-top:10px;}
.bench .lbl{color:var(--muted);font-size:14px;width:60px;}
.bench .xip{width:96px;}
.bench .xip b{font-size:13px;}
.ftr{display:flex;justify-content:space-between;color:var(--muted);
font-size:14px;margin-top:6px;}
.ftr b{color:var(--cream);font-weight:600;}
svg.kit{display:block;margin:0 auto;}
"""


def xp_line(xp: float | None) -> str:
    """Kierroksen xP samasta artefaktista kuin jakauma.

    Tama on kortin ainoa piste-ennuste: `gameweeks[].xp` TALLE kierrokselle,
    ei `xp_per_gw` joka on horisontin summa jaettuna kierrosmaaralla (muisti:
    xp-per-gw-ei-ole-gw-xp). Sama luku kuin ilmaissivun GW-taulun xP-sarake.
    """
    if xp is None:
        return ""
    return f'<span class="xp">{xp:.1f} <i>xP</i></span>'


def sim_line(p: dict, dist: dict | None) -> str:
    """Pelaajan jakaumarivi kortille, tai tyhja jos jakaumaa ei ole.

    Luvut tulevat samasta artefaktista kuin ilmaissivun 10+- ja
    Blank-sarakkeet (`data/fpl_xp_projections.json`, `xp_dist`), jotta
    kortin ja tarkistusreitin luku on sama. Puuttuva jakauma jattaa rivin
    pois - se ei ole nolla (muisti: nolla-ei-ole-sama-kuin-ei-tietoa).
    """
    if not dist:
        return ""
    blank = f'blank {round(dist["p_blank"] * 100)}%'
    # Maalivahdin "10+ 0%" lukee rikkinaiselta, vaikka se on tosi: kymmenen
    # pistetta vaatii maalivahdilta nollapelin JA kolme torjuntaa JA bonusta.
    # Nayta hanelta vain blank, alaka nollaa.
    if str(dist.get("pos") or "") == "GKP" or dist.get("_gkp"):
        return f'<span class="sim">{blank}</span>'
    return (f'<span class="sim">10+ {round(dist["p_haul"] * 100)}% '
            f'· {blank}</span>')


def cell(p: dict, cap: int, vice: int, size: int = 46,
         dist: dict | None = None, chip: str | None = None,
         xp: float | None = None) -> str:
    badge = ""
    if p["id"] == cap:
        # Triple captain nakyy kortilla: kolminkertainen kapteeni on eri
        # veto kuin kaksinkertainen, eika lukija voi paatella sita mistaan
        # muualta ennen kuin pickit avautuvat deadlinella.
        badge = ('<span class="badge tc">TC</span>' if chip == "3xc"
                 else '<span class="badge">C</span>')
    elif p["id"] == vice:
        badge = '<span class="badge v">V</span>'
    return ('<div class="xip">' + badge + _kit_svg(p["team_short"], size=size)
            + f'<b>{p["web_name"]}</b>'
            + f'<span>{p["team_short"]} · {p["price"] / 10:.1f}m</span>'
            + xp_line(xp)
            + sim_line(p, dict(dist, _gkp=(p.get("pos") == 1))
                       if dist else None) + '</div>')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gw", type=int, default=1)
    ap.add_argument("--out", default=str(config.PROJECT_ROOT / "outputs"))
    ap.add_argument("--squad-file", default=None,
                    help="lue runko tasta JSONista freeze-hakemiston sijaan")
    ap.add_argument("--subtitle", default=None,
                    help="korvaa alaotsikko (esim. deadline-paivan uudelleenrakennus)")
    ap.add_argument("--sims", action="store_true",
                    help="nayta jokaisen aloittajan 10+- ja blank-%% "
                         "(sama xp_dist kuin ilmaissivun sarakkeet)")
    ap.add_argument("--hide-bench", action="store_true",
                    help="jata penkkirivi pois (promopinnan nimiesto, esim. Thiaw)")
    args = ap.parse_args()

    frozen = json.loads(
        (Path(args.squad_file) if args.squad_file else FROZEN_DIR / f"gw{args.gw}.json").read_text(encoding="utf-8"))
    xi, bench = frozen["xi"], frozen["bench"]
    cap, vice = frozen["captain"], frozen["vice_captain"]
    total = sum(p["price"] for p in xi + bench) / 10.0
    meta_val = frozen.get("meta") or {}
    import datetime as _dt
    raw = str(frozen.get("meta", {}).get("frozen_at", ""))[:10]
    frozen_at = _dt.date.fromisoformat(raw).strftime("%d %b").lstrip("0") if raw else ""

    rows = {t: [p for p in xi if p["pos"] == t] for t in (1, 2, 3, 4)}
    shape = "-".join(str(len(rows[t])) for t in (2, 3, 4))
    dists: dict = {}
    xps: dict = {}
    if args.sims:
        xp = json.loads((config.DATA_DIR / "fpl_xp_projections.json")
                        .read_text(encoding="utf-8"))
        gws = {(pp.get("xp_dist") or {}).get("gw") for pp in xp.get("players") or []
               if pp.get("xp_dist")}
        gws.discard(None)
        # 🔴 Kortin otsikko sanoo GW:n, luvut tulevat `xp_dist`:sta. Jos ne
        # ovat eri kierrokselta, kortti julkaisisi vaaran kierroksen luvut
        # oikean kierroksen nimella (sama vika mitattiin standouts-kortista
        # 30.8). Fail-closed.
        if gws != {args.gw}:
            raise SystemExit(
                f"SIMULAATIOT ERI KIERROKSELTA: kortti on GW{args.gw} mutta "
                f"xp_dist on kierrokselta {sorted(gws)}. Aja projektio "
                "uudelleen ennen kuin julkaiset kortin.")
        dists = {int(pp["id"]): pp["xp_dist"] for pp in xp["players"]
                 if pp.get("xp_dist") and pp.get("id") is not None}
        for pp in xp["players"]:
            for g in pp.get("gameweeks") or []:
                if g.get("gw") == args.gw and pp.get("id") is not None:
                    xps[int(pp["id"])] = float(g.get("xp") or 0.0)
    pitch = "".join(
        '<div class="xirow">'
        + "".join(cell(p, cap, vice, dist=dists.get(int(p["id"])),
                       chip=(frozen.get("meta") or {}).get("chip"),
                       xp=xps.get(int(p["id"])))
                  for p in rows[t])
        + "</div>" for t in (1, 2, 3, 4))
    bench_html = "".join(cell(p, cap=-1, vice=-1, size=42) for p in bench)
    shorts = [p["team_short"] for p in xi + bench]

    bench_block = ("" if args.hide_bench
                   else f'<div class="bench"><span class="lbl">Bench</span>{bench_html}</div>')
    html = (
        "<!doctype html><meta charset='utf-8'>"
        f"<style>{CSS}</style>"
        f'<svg width="0" height="0" style="position:absolute">{_kit_defs(shorts)}</svg>'
        '<div class="card">'
        '<div class="hdr"><div><span class="brand">'
        # 30.8: merkki src/brand.py:sta (Villen 1.8 paatos).
        + logo_svg(28) + '<b>Goal<i>IQ</i></b></span></div>'
        f'<div><div class="title">The model&#39;s own FPL squad, GW{args.gw} ({shape})'
        + ('' if not args.sims else ', 2,000 simulated gameweeks each')
        + '</div>'
        f'<div class="sub">{args.subtitle or f"Picked by the optimiser, frozen {frozen_at}, entered as-is"}</div></div></div>'
        f'<div class="pitch">{pitch}</div>'
        f'{bench_block}'
        # 🔴 4.9 PORTTI: "spent" laskettiin NYKYHINNOISTA, mutta se ei ole
        # kumpikaan oikea luku: ostohinnat eivat ole julkisia, ja FPL:n oma
        # sivu nayttaa rungon myyntiarvon + pankin. Kun runko tulee entrysta,
        # kaytetaan FPL:n omia lukuja ja oikeaa sanaa.
        + (f'<div class="ftr"><span><b>{meta_val["squad_value_m"]:.1f}m</b> squad'
           + (f' · {meta_val["bank_m"]:.1f}m in the bank' if meta_val.get("bank_m") is not None else '')
           + '</span>'
           if meta_val.get("squad_value_m") is not None
           else f'<div class="ftr"><span><b>{total:.1f}m</b> spent</span>')
        # 21.8 portti B1: EI linkkiä /fpl/model-xi-sivulle — se regeneroituu
        # päivittäin ja sen 15 voi erota freezestä (erosi jo samana iltana).
        + "<span>entry 116920 · public on fantasy.premierleague.com</span>"
        + ('<span>goaliq.app/fpl/expected-points#top-100</span></div>'
           if args.sims else '<span>goaliq.app</span></div>')
        + "</div>")

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
