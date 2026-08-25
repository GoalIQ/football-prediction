"""EO-BY-TIER: efektiivinen omistus sijoitustasoittain (25.8.2026).

MIKSI: rank-pelaajan kysymys ei ole "mita kaikki omistavat" vaan "mita KARKI
omistaa". FPL:n oma `selected_by_percent` on koko kentan omistus ja se on
dominoitu miljoonista passiivisista joukkueista.

MITTARI: EO = keskimaarainen multiplier x 100. FPL:n picks-vastaus antaa
`multiplier`-kentan suoraan: 0 = penkki, 1 = pelaava, 2 = kapteeni, 3 = triple
captain. EO on siis laskettu datasta eika tulkittu.

    owned_pct   = osuus jolla pelaaja on 15:ssa (penkki mukaan lukien)
    eo_pct      = 100 * sum(multiplier) / n_sampled
    captain_pct = osuus joka antoi kapteenin nauhan


🔴 KEHAPAATELMA JOKA MITATTIIN JA JOKA MAARAA TAMAN SKRIPTIN RAKENTEEN
=====================================================================
Ensimmainen versio otti sijoitusotoksen JA valinnat samalta kierrokselta.
Se on kehapaatelma: kierroksen N jalkeinen sijoitus on osittain seuraus siita
mita manageri omisti kierroksella N. "Karki omistaa De Cuyperin" oli tosi vain
koska De Cuyper teki 17 pistetta ja hanen omistajansa nousivat karkeen.

Mitattu 25.8 GW1:n jalkeen, Bench Boostin kaytto sijoitustasoittain:

    top1k     90,0 %        top100k   67,5 %        ~3M        8,3 %
    top10k    87,5 %        ~1M       27,1 %

Monotoninen gradientti 8 %:sta 90 %:iin. BB lisaa penkkipisteet -> korkeampi
pistemaara -> korkeampi sijoitus. Yhden kierroksen jalkeen "top 1k" on siis
paaosin otos chipin pelanneista, ei otos hyvista managereista. Sama valikoituma
varjaa JOKAISEN pelaajan EO-luvun samassa otoksessa.

RATKAISU: sijoitusotos otetaan kierrokselta N-1 ja valinnat kierrokselta N.
Silloin mitataan "mita hyvin sijoittuneet VALITSIVAT", ei "mita onnekkaat
omistivat". Tama vaatii kaksi vaihetta, koska FPL:n standings-API antaa vain
NYKYISET sijoitukset - historiallista ei ole:

    1) --snapshot         aja kierroksen N-1 jalkeen, ennen kierroksen N
                          deadlinea. Tallentaa tasojen entry-ID:t.
    2) --picks --gw N     aja kierroksen N deadlinen jalkeen. Lukee snapshotin
                          ja hakee NIIDEN samojen managerien kierroksen N
                          valinnat.

GW1:lle tata ei voi tehda: sita ennen ei ole sijoitusta. GW1:n EO-by-tier on
siis vaistamatta kehallinen eika sita julkaista lukuna.

🔴 TAMA ON OTOS, EI TASON TAYSI OMISTUS. Jokainen tason luku kantaa `n`:n
payloadissa, ja n on julkaistava aina luvun vieressa.

🔴 EI GH-RUNNERILTA (FPL-esto GitHubin IP-avaruudesta). Render tai paikallinen.

Ajo:
    python scripts/fpl_elite_ownership.py --snapshot --after-gw 1
    python scripts/fpl_elite_ownership.py --picks --gw 2
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

OUT_PATH = config.DATA_DIR / "fpl_elite_ownership.json"
SNAPSHOT_PATH = config.DATA_DIR / "fpl_rank_snapshot.json"

# Tasot: (nimi, viimeinen sivu, montako sivua otetaan, entryja per sivu).
# Sivu = 50 sijoitusta, joten sivu 200 = sijoitus 10 000.
#
# 🔴 Sivut poimitaan TASAVALEIN tason yli eika tason karjesta. top10k:n otos
# joka olisi vain sivut 1-20 olisi tosiasiassa top1k uudelleen, ja kaksi "eri"
# tasoa nayttaisi samat luvut. Se olisi mittausvirhe joka nayttaa loydokselta.
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


# ---------------------------------------------------------------------------
# Vaihe 1: sijoitusotos
# ---------------------------------------------------------------------------
def snapshot(after_gw: int, verbose: bool = True) -> dict:
    """Tallenna tasojen entry-ID:t sellaisina kuin sijoitukset ovat NYT.

    Ajetaan kierroksen `after_gw` jalkeen ja ENNEN seuraavan deadlinea.
    """
    tiers: dict[str, list[int]] = {}
    for name, last_page, n_pages, per_page in TIERS:
        entries: list[int] = []
        for pg in _sample_pages(last_page, n_pages):
            try:
                data = fpl_api.fetch_league_standings(pg, force=True)
            except Exception as e:
                if verbose:
                    print(f"      [{name}] sivu {pg} EPAONNISTUI: {e}")
                continue
            rows = (data.get("standings") or {}).get("results") or []
            if not rows:
                # 🔴 Tyhja sivu ei ole "ei manageria" vaan sivutuksen loppu tai
                # esto. Kirjataan aanekkaasti, ei ohiteta hiljaa.
                if verbose:
                    print(f"      [{name}] sivu {pg} palautti 0 rivia")
                continue
            entries.extend(r["entry"] for r in rows[:per_page])
        tiers[name] = entries
        if verbose:
            print(f"   [{name}] {len(entries)} entrya")

    return {
        "meta": {
            "rank_after_gw": after_gw,
            "taken_at": _dt.datetime.now(_dt.timezone.utc)
            .replace(microsecond=0).isoformat(),
            "note": ("Rank snapshot. Pair with picks from a LATER gameweek: "
                     "sampling rank and picks from the same gameweek is "
                     "circular."),
        },
        "tiers": tiers,
    }


# ---------------------------------------------------------------------------
# Vaihe 2: valinnat + EO
# ---------------------------------------------------------------------------
def collect_tier(name: str, entries: list[int], gw: int,
                 verbose: bool = True) -> dict:
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
            # 404 = ei rivia talle kierrokselle. 🔴 EI nolla vaan pois
            # otoksesta: nolla vaarantaisi jokaisen prosentin nimittajan.
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

    return {"n_sampled": n, "n_missing": missing, "chips": dict(chips),
            "_owned": dict(owned), "_mult": dict(mult_sum), "_cap": dict(captain)}


def build(gw: int, snap: dict, verbose: bool = True) -> dict:
    rank_gw = snap["meta"]["rank_after_gw"]
    circular = gw <= rank_gw

    boot = fpl_api.fetch_bootstrap()
    el = {e["id"]: e for e in boot["elements"]}
    teams = {t["id"]: t["short_name"] for t in boot["teams"]}
    pos = {t["id"]: t["singular_name_short"] for t in boot["element_types"]}

    tiers: dict[str, dict] = {}
    for name, entries in snap["tiers"].items():
        if verbose:
            print(f"   [{name}] haetaan GW{gw} valinnat...")
        tiers[name] = collect_tier(name, entries, gw, verbose)

    pids: set[int] = set()
    for t in tiers.values():
        pids |= set(t["_owned"])

    players = []
    for pid in pids:
        e = el.get(pid)
        if e is None:
            continue
        row = {
            "id": pid, "web_name": e["web_name"],
            "team": teams.get(e["team"], "?"),
            "pos": pos.get(e["element_type"], "?"),
            "price": e["now_cost"] / 10.0,
            # FPL:n oma luku = KOKO kentan omistus, vertailukohta.
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
            "picks_gameweek": gw,
            "rank_after_gw": rank_gw,
            # 🔴 Jos tama on True, luvut mittaavat lopputulosta eivat valintaa.
            # Kentta on payloadissa jotta pinta ei voi esittaa niita neutraalina.
            "circular": circular,
            "circular_note": (
                "Rank and picks come from the same gameweek, so the tiers are "
                "partly defined by the outcome they are being used to explain. "
                "Do not present these as what good managers choose."
            ) if circular else None,
            "generated_at": _dt.datetime.now(_dt.timezone.utc)
            .replace(microsecond=0).isoformat(),
            "source": "FPL overall league 314 standings + entry picks",
            "metric": ("EO = mean multiplier x 100 (bench 0, playing 1, "
                       "captain 2, triple captain 3), taken straight from the "
                       "official picks payload."),
            # 🔴 Otoskoko on osa lukua, ei alaviite.
            "sample": {k: {"n_sampled": v["n_sampled"],
                           "n_missing": v["n_missing"],
                           "chips": v["chips"]}
                       for k, v in tiers.items()},
            "caveat": ("Each tier is a sample of that rank range, not the full "
                       "tier. Always show n next to the percentage."),
        },
        "players": players,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", action="store_true",
                    help="tallenna sijoitusotos (aja kierroksen jalkeen)")
    ap.add_argument("--after-gw", type=int, help="snapshotin kierros")
    ap.add_argument("--picks", action="store_true",
                    help="hae valinnat ja laske EO")
    ap.add_argument("--gw", type=int, help="minka kierroksen valinnat")
    ap.add_argument("--allow-circular", action="store_true",
                    help="salli sama kierros molemmille (merkitaan payloadiin)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    verbose = not args.quiet

    if args.snapshot:
        if args.after_gw is None:
            ap.error("--snapshot vaatii --after-gw")
        snap = snapshot(args.after_gw, verbose)
        SNAPSHOT_PATH.write_text(json.dumps(snap, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
        n = sum(len(v) for v in snap["tiers"].values())
        print(f"[ok] {SNAPSHOT_PATH.name}: {n} entrya, sijoitus GW"
              f"{args.after_gw}:n jalkeen")
        return 0

    if args.picks:
        if args.gw is None:
            ap.error("--picks vaatii --gw")
        if not SNAPSHOT_PATH.exists():
            print(f"[virhe] {SNAPSHOT_PATH.name} puuttuu. Aja ensin "
                  f"--snapshot --after-gw <N>.", file=sys.stderr)
            return 2
        snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        rank_gw = snap["meta"]["rank_after_gw"]
        if args.gw <= rank_gw and not args.allow_circular:
            print(
                f"[virhe] KEHAPAATELMA: sijoitusotos on GW{rank_gw}:n jalkeen "
                f"ja pyydat GW{args.gw}:n valintoja. Talloin taso on osittain "
                f"maaritelty silla lopputuloksella jota ollaan selittamassa.\n"
                f"        Mitattu 25.8: Bench Boostin kaytto oli top1k:ssa "
                f"90 % ja sijoituksessa ~3M 8 % - gradientti on valikoitumaa, "
                f"ei strategiaa.\n"
                f"        Aja --picks --gw {rank_gw + 1} tai myohempi. "
                f"Pakota tarvittaessa --allow-circular.",
                file=sys.stderr)
            return 2
        out = build(args.gw, snap, verbose)
        OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                            encoding="utf-8")
        s = out["meta"]["sample"]
        flag = " 🔴 KEHALLINEN" if out["meta"]["circular"] else ""
        print(f"[ok] {OUT_PATH.name}: {len(out['players'])} pelaajaa, otos "
              + ", ".join(f"{k} n={v['n_sampled']}" for k, v in s.items())
              + flag)
        return 0

    ap.error("anna joko --snapshot tai --picks")


if __name__ == "__main__":
    raise SystemExit(main())
