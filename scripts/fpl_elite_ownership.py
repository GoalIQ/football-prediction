"""EO-BY-TIER: efektiivinen omistus sijoitustasoittain (25.8.2026).

MIKSI: rank-pelaajan kysymys ei ole "mita kaikki omistavat" vaan "mita KARKI
omistaa". FPL:n oma `selected_by_percent` on koko kentan omistus ja se on
dominoitu miljoonista passiivisista joukkueista. Kilpailijalla (FPL Rogue) on
tama, meilla ei ollut mitaan vastaavaa.

MITTARI: EO = keskimaarainen multiplier x 100. FPL:n picks-vastaus antaa
`multiplier`-kentan suoraan: 0 = penkki, 1 = pelaava, 2 = kapteeni, 3 = triple
captain. Nain EO on laskettu datasta eika tulkittu - emme keksi omaa kaavaa
jota lukija ei voi tarkistaa.

    owned_pct   = osuus jolla pelaaja on 15:ssa (penkki mukaan lukien)
    eo_pct      = 100 * sum(multiplier) / n_sampled
    captain_pct = osuus joka antoi kapteenin nauhan

🔴 TAMA ON OTOS, EI TASON TAYSI OMISTUS. Jokainen tason luku kantaa `n`:n
payloadissa, ja n on julkaistava aina luvun vieressa. Ilman sita "karki omistaa
62 %" lukee kokonaislaskentana. Vrt. honest-data-labels.

🔴 EI GH-RUNNERILTA. FPL-suuntaiset kutsut on estetty GitHubin IP-avaruudesta
(kirjattu tapaus). Aja Renderista tai paikallisesti.

🔴 EI ENNEN KIERROKSEN DEADLINEA. Mitattu 15.8: standings palautti 0 rivia ja
picks vastasi "Not found". Mitattu uudelleen 25.8 GW1:n jalkeen: molemmat
vastaavat normaalisti.

Ajo:
    python scripts/fpl_elite_ownership.py --gw 1
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from collections import defaultdict
from pathlib import Path

# Repon juuri sys.pathiin: skripti ajetaan `python scripts/<nimi>.py`, jolloin
# sys.path[0] on scripts/ eika juuri, eika `config` resolvoidu. Sama kaava kuin
# build_fpl_xp.py:34 ja build_fpl_page.py:39.
if str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from src.data import fpl_api  # noqa: E402

OUT_PATH = config.DATA_DIR / "fpl_elite_ownership.json"

# Tasot: (nimi, viimeinen sivu, montako sivua otetaan, entryja per sivu).
# Sivu = 50 sijoitusta, joten sivu 200 = sijoitus 10 000.
#
# 🔴 Sivut poimitaan TASAVALEIN tason yli eika tason karjesta. top10k:n otos
# joka olisi vain sivut 1-20 olisi tosiasiassa top1k uudelleen, ja kaksi
# "eri" tasoa nayttaisi samat luvut. Se olisi mittausvirhe joka nayttaa
# loydokselta ("karjen tasot ovat yksimielisia").
TIERS = [
    ("top1k", 20, 20, 10),
    ("top10k", 200, 20, 10),
    ("top100k", 2000, 20, 10),
]


def _sample_pages(last_page: int, n_pages: int) -> list[int]:
    """Tasavalein poimitut sivunumerot 1..last_page (molemmat mukaan lukien)."""
    if n_pages >= last_page:
        return list(range(1, last_page + 1))
    step = last_page / n_pages
    return sorted({max(1, round(1 + i * step)) for i in range(n_pages)})


def collect_tier(name: str, last_page: int, n_pages: int, per_page: int,
                 gw: int, verbose: bool = True) -> dict:
    """Hae yhden tason otos ja laske raakasummat."""
    pages = _sample_pages(last_page, n_pages)
    entries: list[int] = []
    for pg in pages:
        try:
            data = fpl_api.fetch_league_standings(pg)
        except Exception as e:  # verkkovirhe yhdella sivulla ei kaada ajoa
            if verbose:
                print(f"      [{name}] sivu {pg} EPAONNISTUI: {e}")
            continue
        rows = (data.get("standings") or {}).get("results") or []
        if not rows:
            # 🔴 Tyhja sivu ei ole "ei manageria" vaan yleensa sivutuksen loppu
            # tai esto. Kirjataan aanekkaasti, ei ohiteta hiljaa.
            if verbose:
                print(f"      [{name}] sivu {pg} palautti 0 rivia")
            continue
        entries.extend(r["entry"] for r in rows[:per_page])

    mult_sum: dict[int, int] = defaultdict(int)
    owned: dict[int, int] = defaultdict(int)
    captain: dict[int, int] = defaultdict(int)
    chips: dict[str, int] = defaultdict(int)
    n = 0
    missing = 0
    for i, e in enumerate(entries, 1):
        try:
            picks = fpl_api.fetch_entry_picks(e, gw)
        except Exception as ex:
            if verbose:
                print(f"      [{name}] entry {e} EPAONNISTUI: {ex}")
            missing += 1
            continue
        if picks is None:
            # 404 = ei rivia talle kierrokselle (manageri liittyi myohemmin).
            # 🔴 EI nolla vaan pois otoksesta: nolla vaarantaisi jokaisen
            # prosentin nimittajan. Vrt. nolla-ei-ole-sama-kuin-ei-tietoa.
            missing += 1
            continue
        n += 1
        chips[picks.get("active_chip") or "none"] += 1
        for p in picks.get("picks") or []:
            pid = p["element"]
            owned[pid] += 1
            mult_sum[pid] += p.get("multiplier", 0)
            if p.get("is_captain"):
                captain[pid] += 1
        if verbose and i % 50 == 0:
            print(f"      [{name}] {i}/{len(entries)}")

    return {
        "n_sampled": n,
        "n_missing": missing,
        "pages_used": len(pages),
        "chips": dict(chips),
        "_owned": dict(owned),
        "_mult": dict(mult_sum),
        "_cap": dict(captain),
    }


def build(gw: int, verbose: bool = True) -> dict:
    boot = fpl_api.fetch_bootstrap()
    el = {e["id"]: e for e in boot["elements"]}
    teams = {t["id"]: t["short_name"] for t in boot["teams"]}
    pos = {t["id"]: t["singular_name_short"] for t in boot["element_types"]}

    tiers: dict[str, dict] = {}
    for name, last_page, n_pages, per_page in TIERS:
        if verbose:
            print(f"   [{name}] haetaan...")
        tiers[name] = collect_tier(name, last_page, n_pages, per_page, gw,
                                   verbose)

    pids: set[int] = set()
    for t in tiers.values():
        pids |= set(t["_owned"])

    players = []
    for pid in pids:
        e = el.get(pid)
        if e is None:
            continue
        row = {
            "id": pid,
            "web_name": e["web_name"],
            "team": teams.get(e["team"], "?"),
            "pos": pos.get(e["element_type"], "?"),
            "price": e["now_cost"] / 10.0,
            # FPL:n oma luku = KOKO kentan omistus. Tama on se vertailukohta
            # jota vastaan "karki omistaa eri tavalla" mitataan.
            "overall_pct": float(e.get("selected_by_percent") or 0.0),
            "tiers": {},
        }
        for name, t in tiers.items():
            n = t["n_sampled"]
            if not n:
                continue
            row["tiers"][name] = {
                "owned_pct": round(100.0 * t["_owned"].get(pid, 0) / n, 1),
                "eo_pct": round(100.0 * t["_mult"].get(pid, 0) / n, 1),
                "captain_pct": round(100.0 * t["_cap"].get(pid, 0) / n, 1),
            }
        players.append(row)

    players.sort(key=lambda r: -(r["tiers"].get("top1k", {}).get("eo_pct") or 0.0))

    return {
        "meta": {
            "gameweek": gw,
            "generated_at": _dt.datetime.now(_dt.timezone.utc)
            .replace(microsecond=0).isoformat(),
            "source": "FPL overall league 314 standings + entry picks",
            "metric": ("EO = mean multiplier x 100 (bench 0, playing 1, "
                       "captain 2, triple captain 3), taken straight from the "
                       "official picks payload."),
            # 🔴 Otoskoko on osa lukua, ei alaviite.
            "sample": {k: {"n_sampled": v["n_sampled"],
                           "n_missing": v["n_missing"],
                           "pages_used": v["pages_used"],
                           "chips": v["chips"]}
                       for k, v in tiers.items()},
            "caveat": ("Each tier is a sample of that rank range, not the full "
                       "tier. Always show n next to the percentage."),
        },
        "players": players,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gw", type=int, required=True)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    out = build(args.gw, verbose=not args.quiet)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    s = out["meta"]["sample"]
    print(f"[ok] {OUT_PATH.name}: {len(out['players'])} pelaajaa, otos "
          + ", ".join(f"{k} n={v['n_sampled']}" for k, v in s.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
