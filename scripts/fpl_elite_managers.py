"""ELITE-MANAGERS: mita karki SIIRSI ja kenet se kapteenoi (25.8.2026).

Kilpailijalla (FPL Rogue) on tama; meilla ei ollut mitaan vastaavaa. Kysymys on
rank-pelaajan: ei "mita kaikki tekivat" vaan "mita KARKI teki".

Kaytaa SAMAA sijoitusotosta kuin `fpl_elite_ownership.py`
(`data/fpl_rank_snapshot.json`), joten tasot ovat vertailukelpoisia keskenaan
eivatka kaksi eri otosta anna kahta eri vastausta samaan kysymykseen.

🔴 SAMA KEHAPAATELMAVAHTI. Sijoitusotos kierrokselta N-1, siirrot kierrokselle
N. Siirrot TEHDAAN ennen kierroksen N deadlinea, joten sijoitus ei voi tuntea
niiden lopputulosta - mutta jos otos ja kierros ovat samat, taso on osittain
maaritelty silla mita se omisti, ja "karki siirsi X:n sisaan" muuttuu
havainnoksi "X pelasi hyvin".

Mitattu 25.8 GW1:n jalkeen, Bench Boostin kaytto sijoitustasoittain:
    top1k 90,0 % · top10k 87,5 % · top100k 67,5 % · ~1M 27,1 % · ~3M 8,3 %
Monotoninen gradientti 8 -> 90 %. Yhden kierroksen jalkeen "top 1k" on paaosin
otos chipin pelanneista, ei otos hyvista managereista.

🔴 TYHJA SIIRTOLISTA ON DATAA. Manageri joka piti joukkueensa ennallaan on
otoksessa mukana ja `hold`-lukuna nakyvissa - hold on myos valinta. Vain 404
(ei rivia talle kaudelle) pudottaa managerin otoksesta.

🔴 EI GH-RUNNERILTA (FPL-esto GitHubin IP-avaruudesta). Render tai paikallinen.

Ajo (sijoitusotos otetaan fpl_elite_ownership.py --snapshot:lla):
    python scripts/fpl_elite_managers.py --gw 2
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from collections import defaultdict
from pathlib import Path

if str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from src.data import fpl_api  # noqa: E402

OUT_PATH = config.DATA_DIR / "fpl_elite_managers.json"
SNAPSHOT_PATH = config.DATA_DIR / "fpl_rank_snapshot.json"


def collect_tier(name: str, entries: list[int], gw: int,
                 verbose: bool = True) -> dict:
    """Yhden tason siirrot + kapteenit yhdelle kierrokselle."""
    tulo: dict[int, int] = defaultdict(int)
    lahto: dict[int, int] = defaultdict(int)
    kapteeni: dict[int, int] = defaultdict(int)
    chips: dict[str, int] = defaultdict(int)
    n = 0
    missing = 0
    hold = 0
    hitit = 0
    siirtoja_yht = 0

    for i, e in enumerate(entries, 1):
        try:
            tr = fpl_api.fetch_entry_transfers(e)
            picks = fpl_api.fetch_entry_picks(e, gw)
        except Exception as ex:
            if verbose:
                print(f"      [{name}] entry {e} EPAONNISTUI: {ex}")
            missing += 1
            continue
        # 🔴 `tr is None` = 404 (ei rivia) -> pois otoksesta.
        #    `tr == []`   = ei siirtoja -> KUULUU otokseen.
        if tr is None or picks is None:
            missing += 1
            continue
        n += 1
        chips[picks.get("active_chip") or "none"] += 1

        gw_siirrot = [t for t in tr if t.get("event") == gw]
        if not gw_siirrot:
            hold += 1
        siirtoja_yht += len(gw_siirrot)
        for t in gw_siirrot:
            if t.get("element_in") is not None:
                tulo[t["element_in"]] += 1
            if t.get("element_out") is not None:
                lahto[t["element_out"]] += 1

        # Siirtokustannus tulle kierrokselta: FPL kertoo sen picks-vastauksen
        # entry_historyssa, ei siirtoriveilla.
        eh = picks.get("entry_history") or {}
        if (eh.get("event_transfers_cost") or 0) > 0:
            hitit += 1

        for p in picks.get("picks") or []:
            if p.get("is_captain"):
                kapteeni[p["element"]] += 1

        if verbose and i % 50 == 0:
            print(f"      [{name}] {i}/{len(entries)}")

    return {"n_sampled": n, "n_missing": missing, "hold": hold,
            "took_hit": hitit, "transfers_total": siirtoja_yht,
            "chips": dict(chips),
            "_in": dict(tulo), "_out": dict(lahto), "_cap": dict(kapteeni)}


def _rivit(el, teams, pos, laskuri: dict, n: int, top: int) -> list[dict]:
    out = []
    for pid, c in sorted(laskuri.items(), key=lambda x: -x[1])[:top]:
        e = el.get(pid)
        if e is None:
            continue
        out.append({
            "id": pid, "web_name": e["web_name"],
            "team": teams.get(e["team"], "?"),
            "pos": pos.get(e["element_type"], "?"),
            "price": e["now_cost"] / 10.0,
            "count": c,
            "pct": round(100.0 * c / n, 1) if n else None,
            # FPL:n oma koko kentan omistus vertailukohdaksi.
            "overall_pct": float(e.get("selected_by_percent") or 0.0),
        })
    return out


def build(gw: int, snap: dict, top: int = 15, verbose: bool = True) -> dict:
    rank_gw = snap["meta"]["rank_after_gw"]
    circular = gw <= rank_gw

    boot = fpl_api.fetch_bootstrap()
    el = {e["id"]: e for e in boot["elements"]}
    teams = {t["id"]: t["short_name"] for t in boot["teams"]}
    pos = {t["id"]: t["singular_name_short"] for t in boot["element_types"]}

    tiers: dict[str, dict] = {}
    for name, entries in snap["tiers"].items():
        if verbose:
            print(f"   [{name}] haetaan GW{gw} siirrot...")
        tiers[name] = collect_tier(name, entries, gw, verbose)

    out_tiers = {}
    for name, t in tiers.items():
        n = t["n_sampled"]
        out_tiers[name] = {
            "n_sampled": n,
            "n_missing": t["n_missing"],
            # 🔴 hold on TULOS eika puuttuva data: se kertoo kuinka moni
            # tason manageri piti joukkueensa ennallaan.
            "hold": t["hold"],
            "hold_pct": round(100.0 * t["hold"] / n, 1) if n else None,
            "took_hit": t["took_hit"],
            "took_hit_pct": round(100.0 * t["took_hit"] / n, 1) if n else None,
            "transfers_per_manager": (round(t["transfers_total"] / n, 2)
                                      if n else None),
            "chips": t["chips"],
            "transfers_in": _rivit(el, teams, pos, t["_in"], n, top),
            "transfers_out": _rivit(el, teams, pos, t["_out"], n, top),
            "captains": _rivit(el, teams, pos, t["_cap"], n, top),
        }

    return {
        "meta": {
            "gameweek": gw,
            "rank_after_gw": rank_gw,
            "circular": circular,
            "circular_note": (
                "Rank and transfers come from the same gameweek, so the tiers "
                "are partly defined by the outcome being explained. Do not "
                "present these as what good managers choose."
            ) if circular else None,
            "generated_at": _dt.datetime.now(_dt.timezone.utc)
            .replace(microsecond=0).isoformat(),
            "source": "FPL entry transfers + picks, sampled by rank tier",
            # 🔴 Otoskoko on osa lukua, ei alaviite.
            "caveat": ("Each tier is a sample of that rank range, not the full "
                       "tier. Always show n next to the percentage."),
        },
        "tiers": out_tiers,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gw", type=int, required=True)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--allow-circular", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    if not SNAPSHOT_PATH.exists():
        print(f"[virhe] {SNAPSHOT_PATH.name} puuttuu. Aja ensin "
              f"`fpl_elite_ownership.py --snapshot --after-gw <N>`.",
              file=sys.stderr)
        return 2
    snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    rank_gw = snap["meta"]["rank_after_gw"]
    if args.gw <= rank_gw and not args.allow_circular:
        print(
            f"[virhe] KEHAPAATELMA: sijoitusotos on GW{rank_gw}:n jalkeen ja "
            f"pyydat GW{args.gw}:n siirtoja. Taso olisi osittain maaritelty "
            f"silla mita se omisti, ja 'karki siirsi X:n sisaan' muuttuisi "
            f"havainnoksi 'X pelasi hyvin'.\n"
            f"        Aja --gw {rank_gw + 1} tai myohempi.",
            file=sys.stderr)
        return 2

    out = build(args.gw, snap, args.top, verbose=not args.quiet)

    # 🔴 TYHJA TULOS EI SAA NAYTTAA ONNISTUMISELTA. Kierroksen valinnat eivat
    # ole julkisia ennen sen deadlinea: jokainen `entry/{id}/event/{gw}/picks/`
    # vastaa 404 ja koko otos putoaa `missing`:iin. Ilman tata vartijaa ajo
    # kirjoittaisi tyhjan tiedoston, poistuisi nollalla ja nayttaisi
    # tulokselta. Vrt. kontrolli-lapaisi-tyhjana.
    tyhjat = [k for k, v in out["tiers"].items() if not v["n_sampled"]]
    if len(tyhjat) == len(out["tiers"]):
        print(
            f"[virhe] Yksikaan taso ei tuottanut otosta GW{args.gw}:lle. "
            f"Todennakoisin syy: kierroksen deadline ei ole viela mennyt, "
            f"jolloin valinnat eivat ole julkisia. EI kirjoitettu "
            f"{OUT_PATH.name}:aa.",
            file=sys.stderr)
        return 2
    if tyhjat:
        print(f"[varoitus] tasot ilman otosta: {tyhjat}", file=sys.stderr)

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    s = out["tiers"]
    print(f"[ok] {OUT_PATH.name}: "
          + ", ".join(f"{k} n={v['n_sampled']} hold={v['hold_pct']}%"
                      for k, v in s.items())
          + (" 🔴 KEHALLINEN" if out["meta"]["circular"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
