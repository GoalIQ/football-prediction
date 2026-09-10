"""UCL-KATTAVUUS-ILMAISELLA-DATALLA: montako siltaottelua liigat saisivat jos
silta laskettaisiin myos EL/ECL-otteluista (openfootball txt) ja Kreikan/Turkin
kotiliigat luettaisiin football.jsonista.

MITTAUS, EI MALLIMUUTOS. Tulostaa per liiga: CL-sillat (nykyinen), +EL/ECL,
ja mitka taman kauden CL-osallistujat siirtyisivat kynnyksen (25) yli.

    python -m scripts.measure_uefa_bridges
"""
from __future__ import annotations

import collections
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from src.data import openfootball, openfootball_txt  # noqa: E402
from src.data.loader import lataa_otteludata  # noqa: E402
from src.models.uefa_joint import MIN_BRIDGE_MATCHES, SUPPORT_LEAGUES, canonical_name  # noqa: E402

CL = "INT-Champions League"
EXTRA_DOMESTIC = {"GRE-Super League": "gr.1", "TUR-Super Lig": "tr.1"}


def _domestic_json(liiga: str, code: str, kaudet: list[str]) -> pd.DataFrame:
    parts = []
    for k in kaudet:
        url = (f"https://raw.githubusercontent.com/openfootball/football.json/master/"
               f"{openfootball._kausi_to_url(k)}/{code}.json")
        data = openfootball._hae_json(url, openfootball.CACHE_DIR / f"{code}_{openfootball._kausi_to_url(k)}.json")
        if data:
            d = openfootball._parse_data(data, liiga, k)
            if not d.empty:
                parts.append(d)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def main() -> int:
    pari = tuple(config.current_season_pair())
    cl_kaudet = ["2324", "2425", "2526", pari[-1]]
    dom = lataa_otteludata(list(SUPPORT_LEAGUES), pari)
    extra = pd.concat([_domestic_json(L, c, list(pari)) for L, c in EXTRA_DOMESTIC.items()],
                      ignore_index=True)
    cl = lataa_otteludata([CL], cl_kaudet)
    el = openfootball_txt.lataa("INT-Europa League", cl_kaudet, qualifiers=True)
    ecl = openfootball_txt.lataa("INT-Conference League", cl_kaudet, qualifiers=True)
    print(f"dom {len(dom)}  extra(gr/tr) {len(extra)}  CL {len(cl)}  EL {len(el)}  ECL {len(ecl)}")

    def club_league(frames) -> dict[str, str]:
        out: dict[str, str] = {}
        for f in frames:
            if f.empty:
                continue
            for r in f.itertuples(index=False):
                out.setdefault(canonical_name(r.home_team), r.league)
                out.setdefault(canonical_name(r.away_team), r.league)
        return out

    def bridges(tour: pd.DataFrame, cl_map: dict[str, str]) -> collections.Counter:
        c: collections.Counter = collections.Counter()
        if tour.empty:
            return c
        scored = tour.dropna(subset=["home_score", "away_score"])
        for r in scored.itertuples(index=False):
            for club in (r.home_team, r.away_team):
                L = cl_map.get(canonical_name(club))
                if L:
                    c[L] += 1
        return c

    base_map = club_league([dom])
    ext_map = club_league([dom, extra])
    b_cl = bridges(cl, base_map)
    b_all_base = b_cl + bridges(el, base_map) + bridges(ecl, base_map)
    b_all_ext = bridges(cl, ext_map) + bridges(el, ext_map) + bridges(ecl, ext_map)

    print(f"\n{'liiga':<22}{'CL':>6}{'CL+EL+ECL':>11}{'+gr/tr':>8}  kynnys {MIN_BRIDGE_MATCHES}")
    for L in sorted(set(b_cl) | set(b_all_base) | set(b_all_ext)):
        flag = "OK" if b_cl[L] >= MIN_BRIDGE_MATCHES else ("->OK" if b_all_ext[L] >= MIN_BRIDGE_MATCHES else "")
        print(f"{L:<22}{b_cl[L]:>6}{b_all_base[L]:>11}{b_all_ext[L]:>8}  {flag}")

    # taman kauden CL-osallistujat: kenen liiga ylittaa kynnyksen kussakin
    cur = cl[cl["season"].astype(str) == pari[-1]]
    clubs = sorted({*cur["home_team"], *cur["away_team"]})
    print(f"\nCL {pari[-1]}: {len(clubs)} seuraa")
    rows = []
    for c in clubs:
        L = ext_map.get(canonical_name(c))
        rows.append((c, L or "-", b_cl.get(L, 0) if L else 0, b_all_ext.get(L, 0) if L else 0))
    now_ok = sum(1 for _, L, a, _ in rows if L != "-" and a >= MIN_BRIDGE_MATCHES)
    ext_ok = sum(1 for _, L, _, b in rows if L != "-" and b >= MIN_BRIDGE_MATCHES)
    print(f"kynnyksen yli: nyt {now_ok}/{len(clubs)}, EL/ECL+gr/tr kanssa {ext_ok}/{len(clubs)}")
    for c, L, a, b in rows:
        if L == "-" or (a < MIN_BRIDGE_MATCHES):
            print(f"  {c:<32}{L:<22} CL {a:>3}  laaj. {b:>3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
