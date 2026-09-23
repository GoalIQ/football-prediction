"""Jakokortti mallin JAADYTETYSTA GW-rungosta (21.8.2026).

MIKSI OMA RENDERI: /fpl/model-xi rakennetaan paivittain uusiksi projektioista,
ja jo samana iltana sen penkki erosi freezesta (Mykolenko puuttui sivulta).
Postattava kuva on lupaus "we score it exactly as frozen" (21.9: aiempi
"entered as-is" poistettu, koska FPL-entry 116920 saa poiketa rungosta ja
mallin luku lasketaan jaadytetysta rungosta), joten sen AINOA sallittu lahde on
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
import sys
from pathlib import Path

from src.brand import logo_svg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from scripts.build_fpl_longtail import _kit_defs, _kit_svg
from scripts.card_shot import (CardLayoutError, find_chrome, render_card,
                               with_fonts)

FROZEN_DIR = config.PROJECT_ROOT / "data" / "model_squad_frozen"

CSS = """
:root{--amber:#F5C542;--ink:#0B0A09;--ink2:#141311;
--cream:#F3F2F2;--paper:#1F1D1A;--muted:#A8A29A;
--line:rgba(243,242,242,0.24);}
*{margin:0;padding:0;box-sizing:border-box;}
body{background:#000;}
.card{width:1200px;height:675px;background:
linear-gradient(160deg,var(--ink) 0%,var(--ink2) 70%,#101a17 100%);
font-family:'IBM Plex Sans',sans-serif;color:var(--cream);
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
font-variant-numeric:tabular-nums;white-space:nowrap;}
.xip span.xp{color:var(--cream);font-size:14px;margin-top:3px;font-weight:600;}
.xip span.xp i{font-style:normal;color:var(--muted);font-weight:400;font-size:12px;}
.xip span.sim{color:var(--amber);font-size:11px;margin-top:1px;
white-space:nowrap;letter-spacing:-.1px;}
.badge{position:absolute;top:0;right:14px;background:var(--amber);
color:var(--ink);font-size:13px;font-weight:700;width:22px;height:22px;
border-radius:50%;line-height:22px;}
.badge.v{background:var(--cream);}
.badge.tc{width:32px;border-radius:11px;font-size:14px;font-weight:800;right:8px;}
.bench{display:flex;align-items:center;gap:18px;border-top:1px solid var(--line);
padding-top:10px;}
.bench .lbl{color:var(--muted);font-size:14px;width:60px;}
.bench .xip{width:124px;}
.bench .xip b{font-size:13px;}
.ftr{display:flex;justify-content:space-between;color:var(--muted);
font-size:14px;margin-top:6px;}
.ftr b{color:var(--cream);font-weight:600;}
svg.kit{display:block;margin:0 auto;}
.xip span em.flag{font-style:normal;font-weight:700;color:var(--ink);
padding:0 4px;border-radius:3px;}
.xip span em.flag.d{background:#F5A142;}
.xip span em.flag.out{background:#FF6B6B;}
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


def availability_mark(p: dict) -> str:
    """FPL:n saatavuusmerkki jaadytetysta rivista, tai tyhja jos pelaaja on `a`.

    🔴 KORTTI-PENKIN-SAATAVUUSMERKKI (23.9, julkaisutarkistajan loydos 18.9):
    GW5-kortissa Oliver Dovin nakyi tavallisena penkkilaisena hintaan 4.0m,
    vaikka FPL sanoi `status u` (laina Leyton Orientiin). Kortti on pysyva
    kuva, ja jos se jaetaan ilman saatetta, merkki puuttuu. Status tulee
    freezesta (`slim`, kirjattu jaadytyshetkella), koska kortin AINOA lahde on
    freeze.

    Merkki on hintarivin jatkona (" · 75%" / " · out"), ei kuvan paalla: 23.9
    renderoinnissa kulmamerkki peitti paidan. d = FPL:n oma prosentti
    (chance_of_playing_next_round), muut = out.
    Fail-closed: rivi ilman `status`-avainta (jaadytetty ennen 23.9) tai
    `status: None` (bootstrap ei tuntenut pelaajaa) kaataa ajon, koska
    merkitsematon pelaaja on juuri se vaite jota kortti ei saa tehda.
    """
    if p.get("status") is None:
        raise SystemExit(
            f"{p.get('web_name')} (id {p.get('id')}): freeze ei kanna FPL:n "
            "saatavuutta (status puuttuu). Kortti ei voi merkita pelaajaa, joten "
            "sita ei renderoida (KORTTI-PENKIN-SAATAVUUSMERKKI). Jaadyta "
            "kierros uudelleen tai renderoi ilman korttia.")
    status = p["status"]
    chance = p.get("chance")
    # Prosentti ensin (julkaisutarkistaja 23.9): jos FPL antaa luvun 1-99,
    # kortti nayttaa sen statuksesta riippumatta, eika voi olla ristiriidassa
    # FPL:n oman luvun kanssa.
    if isinstance(chance, int) and 1 <= chance <= 99:
        return f' · <em class="flag d">{chance}%</em>'
    if status == "a" or (status == "d" and chance == 100):
        return ""
    if status == "d" and chance is None:
        return ' · <em class="flag d">doubt</em>'
    return ' · <em class="flag out">out</em>'


FLAGS_CLAUSE = "FPL flags too"


def subtitle(players: list[dict], frozen_at: str, override: str | None) -> str:
    """Alaotsikko. Kun kortilla on yksikin saatavuusmerkki, lause kertoo
    etta myos FPL:n liput ovat jaadytyshetkelta.

    🔴 Julkaisutarkistaja 23.9 (BLOKATTU k1): "frozen 17 Sep" paivasi
    pelaajavalinnan, ei lippua, ja lukija tarkistaa lipun FPL:sta joka
    nayttaa vain nykytilan. Mitattu GW5-ikkunasta: freezen (17.9 12:18) ja
    deadlinen valilla merkki olisi muuttunut 23/198 liputetulla pelaajalla.
    Muisti lippu-ilman-kierrosta-on-vaite.

    `--subtitle`-ohitus ei saa pudottaa lausetta hiljaa (deadline-paivan
    uudelleenrakennus): jos merkkeja on eika ohitus nimea FPL:n lippuja,
    ajo kaatuu.
    """
    marked = any(availability_mark(p) for p in players)
    if override is not None:
        if marked and "flags" not in override:
            raise SystemExit(
                "--subtitle ei kerro etta FPL:n liput ovat jaadytyshetkelta, "
                "mutta kortilla on saatavuusmerkki. Lisaa esim. "
                f"'{FLAGS_CLAUSE}' ohitukseen.")
        return override
    if marked:
        return (f"Picked by the optimiser and frozen {frozen_at}, {FLAGS_CLAUSE}. "
                "We score it exactly as frozen.")
    return f"Picked by the optimiser and frozen {frozen_at}. We score it exactly as frozen."


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
            + f'<span>{p["team_short"]} · {p["price"] / 10:.1f}m'
            + availability_mark(p) + '</span>'
            + xp_line(xp)
            + sim_line(p, dict(dist, _gkp=(p.get("pos") == 1))
                       if dist else None) + '</div>')


def money_line(meta: dict) -> str:
    """Kortin raharivi FPL:n omista luvuista freezen metasta.

    🔴 FROZEN-KORTTI-RAHALUKU-VAARIN (22.9, mitattu 18.9): kortti tulosti
    "<nykyhintojen summa>m spent" aina kun `meta.squad_value_m` puuttui, ja
    freeze ei ole koskaan kirjoittanut sita kenttaa, eli haara laukesi joka
    kerta. 4.9:n portti oli jo tuominnut sanamuodon: ostohinnat eivat ole
    julkisia, eika nykyhintojen summa ole rungon raha (GW5: 99.8m "spent" kun
    myyntiarvo oli 99.1m). Freeze kirjoittaa 17.9 alkaen
    `selling_value_tenths` (se raha jonka rungosta oikeasti saa) ja
    `bank_tenths` (FPL:n `bank`), `attach_entry_state` ainoana kirjoittajana.

    Fail-closed: puuttuva myyntiarvo kaataa ajon. Varalaskentaa nykyhinnoista
    EI ole, koska se on juuri se vaara luku jota kortti ei saa vaittaa.
    """
    sv = meta.get("selling_value_tenths")
    if not isinstance(sv, int):
        raise SystemExit(
            "meta.selling_value_tenths puuttuu freezesta: kortti ei laske "
            "rahalukua nykyhinnoista (FROZEN-KORTTI-RAHALUKU-VAARIN). "
            "Jaadyta kierros attach_entry_statella tai renderoi ilman korttia.")
    line = f"<b>{sv / 10:.1f}m</b> selling value"
    bank = meta.get("bank_tenths")
    if isinstance(bank, int):
        line += f" · {bank / 10:.1f}m in the bank"
    return line


# Paidan koko kentalla ja penkilla. Sims-tilassa jokaisella aloittajalla on
# kaksi rivia enemman (xP + jakauma), ja 46 px:n paidoilla nelja kentan rivia
# vievat penkin ja alatunnisteen kuvan alapuolelle (KORTTI-SIMS-YLIVUOTO 23.9:
# GitHub-reitti eli kortin tarkistusreitti leikkautui pois). Pienempi paita on
# ainoa korkeus joka ei ole tietoa.
KIT = {False: (46, 42), True: (34, 30)}


def build_html(frozen: dict, gw: int, *, sims: bool = False,
               dists: dict | None = None, xps: dict | None = None,
               hide_bench: bool = False,
               subtitle_override: str | None = None) -> str:
    """Kortin HTML ilman fontteja (ne lisataan vasta kuvattavaan tiedostoon,
    `card_shot.with_fonts`). Erotettu mainista 23.9, jotta asettelu voidaan
    mitata testissa samalla pohjalla joka julkaistaan."""
    import datetime as _dt
    dists, xps = dists or {}, xps or {}
    xi, bench = frozen["xi"], frozen["bench"]
    cap, vice = frozen["captain"], frozen["vice_captain"]
    meta_val = frozen.get("meta") or {}
    money = money_line(meta_val)
    raw = str(meta_val.get("frozen_at", ""))[:10]
    frozen_at = _dt.date.fromisoformat(raw).strftime("%d %b").lstrip("0") if raw else ""

    rows = {t: [p for p in xi if p["pos"] == t] for t in (1, 2, 3, 4)}
    shape = "-".join(str(len(rows[t])) for t in (2, 3, 4))
    kit_xi, kit_bench = KIT[sims]
    pitch = "".join(
        '<div class="xirow">'
        + "".join(cell(p, cap, vice, size=kit_xi, dist=dists.get(int(p["id"])),
                       chip=meta_val.get("chip"),
                       xp=xps.get(int(p["id"])))
                  for p in rows[t])
        + "</div>" for t in (1, 2, 3, 4))
    bench_html = "".join(cell(p, cap=-1, vice=-1, size=kit_bench) for p in bench)
    shorts = [p["team_short"] for p in xi + bench]

    bench_block = ("" if hide_bench
                   else f'<div class="bench"><span class="lbl">Bench</span>{bench_html}</div>')
    return (
        "<!doctype html><meta charset='utf-8'>"
        f"<style>{CSS}</style>"
        f'<svg width="0" height="0" style="position:absolute">{_kit_defs(shorts)}</svg>'
        + ('<div class="card sims">' if sims else '<div class="card">')
        + '<div class="hdr"><div><span class="brand">'
        # 30.8: merkki src/brand.py:sta (Villen 1.8 paatos).
        + logo_svg(28) + '<b>Goal<i>IQ</i></b></span></div>'
        f'<div><div class="title">The model&#39;s own FPL squad, GW{gw} ({shape})'
        + ('' if not sims else ', 2,000 simulated gameweeks each')
        + '</div>'
        f'<div class="sub">{subtitle(xi + ([] if hide_bench else bench), frozen_at, subtitle_override)}</div></div></div>'
        f'<div class="pitch">{pitch}</div>'
        f'{bench_block}'
        # 🔴 4.9 PORTTI: "spent" laskettiin NYKYHINNOISTA, mutta se ei ole
        # kumpikaan oikea luku: ostohinnat eivat ole julkisia, ja FPL:n oma
        # sivu nayttaa rungon myyntiarvon + pankin. Kun runko tulee entrysta,
        # kaytetaan FPL:n omia lukuja ja oikeaa sanaa.
        + f'<div class="ftr"><span>{money}</span>'
        # 21.8 portti B1: EI linkkiä /fpl/model-xi-sivulle — se regeneroituu
        # päivittäin ja sen 15 voi erota freezestä (erosi jo samana iltana).
        # 21.9: reitti on jaadytetty runko julkisessa repossa, ei entry
        # (entry saa poiketa rungosta, mallin luku lasketaan rungosta).
        + f"<span>github.com/GoalIQ/football-prediction · data/model_squad_frozen/gw{gw}.json</span>"
        + ('<span>goaliq.app/fpl/expected-points#top-100</span></div>'
           if sims else '<span>goaliq.app</span></div>')
        + "</div>")


def load_sims(gw: int) -> tuple[dict, dict]:
    """Jakaumat ja kierroksen xP samasta artefaktista kuin ilmaissivu."""
    xp = json.loads((config.DATA_DIR / "fpl_xp_projections.json")
                    .read_text(encoding="utf-8"))
    gws = {(pp.get("xp_dist") or {}).get("gw") for pp in xp.get("players") or []
           if pp.get("xp_dist")}
    gws.discard(None)
    # 🔴 Kortin otsikko sanoo GW:n, luvut tulevat `xp_dist`:sta. Jos ne
    # ovat eri kierrokselta, kortti julkaisisi vaaran kierroksen luvut
    # oikean kierroksen nimella (sama vika mitattiin standouts-kortista
    # 30.8). Fail-closed.
    if gws != {gw}:
        raise SystemExit(
            f"SIMULAATIOT ERI KIERROKSELTA: kortti on GW{gw} mutta "
            f"xp_dist on kierrokselta {sorted(gws)}. Aja projektio "
            "uudelleen ennen kuin julkaiset kortin.")
    dists = {int(pp["id"]): pp["xp_dist"] for pp in xp["players"]
             if pp.get("xp_dist") and pp.get("id") is not None}
    xps: dict = {}
    for pp in xp["players"]:
        for g in pp.get("gameweeks") or []:
            if g.get("gw") == gw and pp.get("id") is not None:
                xps[int(pp["id"])] = float(g.get("xp") or 0.0)
    return dists, xps


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
    # 5.9 KORTTI-PROVENIENSSI-PORTTI: otsikko lupaa entryn rungon, joten
    # generaattori vaatii todisteen (verifioitu / entryn pickeista / ketju
    # verifioidusta). Fail-closed: 4.9 kortti olisi kaatunut tassa.
    from src.models.fpl_model_entry import require_entry_provenance
    peruste = require_entry_provenance(frozen, FROZEN_DIR)
    print(f"provenienssi: {peruste}")
    dists, xps = load_sims(args.gw) if args.sims else ({}, {})
    html = build_html(frozen, args.gw, sims=args.sims, dists=dists, xps=xps,
                      hide_bench=args.hide_bench,
                      subtitle_override=args.subtitle)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"model-squad-gw{args.gw}.html"
    # 23.9: fontit upotetaan vasta kuvattavaan tiedostoon (scripts/card_shot.py),
    # jolloin asettelu ei riipu koneen fonteista.
    html_path.write_text(with_fonts(html), encoding="utf-8")
    print(f"HTML: {html_path}")

    exe = find_chrome()
    if exe is None:
        print("Chromea ei loytynyt - kaappaa HTML kasin.")
        return 0
    png = out_dir / f"model-squad-gw{args.gw}.png"
    try:
        # 🔴 KORTTI-SIMS-YLIVUOTO (23.9): kortti kuvattiin suoraan Chromella,
        # joten ylivuoto paatyi PNG:hen hiljaa (penkki ja tarkistusreitti
        # leikkautuivat pois). render_card mittaa asettelun ensin ja
        # kieltaytyy kirjoittamasta kuvaa.
        render_card(exe, html_path, png)
    except CardLayoutError as e:
        print(f"::error::{e}")
        return 1
    print(f"PNG: {png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
