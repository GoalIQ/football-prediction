"""SPL clean sheet -tasmaytys julkiselle pinnalle, KAIKKI ratkenneet kierrokset.

Mita tama tekee: vertaa jokaisen kierroksen deadline-hetkella julkaistut CS-
ennusteet toteumaan ja kirjoittaa tuloksen artefaktiksi jonka
build_spl_phase0 liittaa metaan -> /api/fantasy?league=spl -> SPA renderoi.
Jokainen sivun luku tulee tasta artefaktista, ei kasin kirjoitetusta copysta.

MIKSI TAMA KIRJOITETTIIN UUDELLEEN 3.9.2026 (Villen havainto).
Ensimmainen versio oli KERTA-AJO: `GW = 1` moduulivakiona ja yksi kasin
pinnattu snapshot-commit. Se oli oikein sina paivana kun se kirjoitettiin.
3.9 SPL oli kierroksessa 5, nelja kierrosta oli ratkennut, ja sivu tarjosi yha
otsikkoa "How our GW1 clean sheet calls went". Track record naytti kauden
avauksesta eika kaudesta. Vika ei ollut siina etta joku unohti ajaa skriptin —
skripti EI VOINUT tuottaa muuta kuin GW1:n.

Suunnittelu niin ettei vikaa voi syntya (CLAUDE.md saanto 6a):
  (1) YKSI LUKIJA JOKA EI VOI PALAUTTAA VAARAA: `build_all()` lukee
      snapshot-hakemiston ja feedin, ja `latest` on aina uusin RATKENNUT
      kierros. Kierrosta ei anneta parametrina eika vakiona.
  (2) POIKKEUSLISTA JOSSA ON PERUSTELU: GW1:n snapshot on kasin pinnattu
      commitiin c7025ad (22 min ennen avauspotkua, rivit verifioitu
      bittitarkasti). Se on `PINNED_SNAPSHOTS`issa perusteluineen; kaikki muut
      resolvoidaan koneellisesti, eika uusi kierros paase listalle vahingossa.
  (3) INVARIANTTI MITATAAN JOKA VAIHEESSA: `tests/test_spl_recon_rolls.py`
      ajaa saman koodin synteettisilla kausivaiheilla (kierros kesken, kierros
      juuri ratkennut, kaksi kierrosta ratkennut) — ei siina vaiheessa jossa
      kausi sattuu nyt olemaan.

LAHTEET, molemmat nimetty artefaktiin:
- Ennusteet: viimeinen `data/spl_projections_phase0.json` joka on committoitu
  ENNEN kierroksen ensimmaista avauspotkua. Ote vendoroidaan hakemistoon
  `data/spl_deadline_snapshots/` ja committoidaan — git-historia ei ole
  ajonaikainen riippuvuus.
- Toteuma: RSL-fantasy-feedin finished-ottelut skoreineen (sama lahde ja sama
  SHORT_TO_MODEL-mappaus kuin build_spl_phase0:n inseason-fitissa).

NAIIVI VERTAILUTASO on nimettava eika arvattava: vakioennuste
p = clean sheet -osuus vendoroidussa kahden kauden historiassa
(spl_results.csv, kaudet 2425 + 2526). 🔴 EI "sama ikkuna jolla malli
fitataan": malli fitataan niiden PAALLE taman kauden otteluilla
(19.8 alkaen), joten se lause oli tosi vain GW1:ssa.

Ajo:
    .venv/Scripts/python.exe -m scripts.build_spl_recon --extract   # uudet GW:t
    .venv/Scripts/python.exe -m scripts.build_spl_recon
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402

SNAPSHOT_DIR = config.PROJECT_ROOT / "data" / "spl_deadline_snapshots"
OUT_PATH = config.PROJECT_ROOT / "data" / "spl_recon.json"
RESULTS_CSV = config.PROJECT_ROOT / "data" / "spl_results.csv"
ARTEFACT = "data/spl_projections_phase0.json"

# POIKKEUSLISTA PERUSTELUINEEN (mekanismi 2). Automaattinen resolveri ottaa
# viimeisen committin ennen avauspotkua; naille kierroksille commit on valittu
# kasin ja verifioitu erikseen. Uusi kierros EI paase tanne vahingossa: rivi on
# kirjoitettava ja perusteltava.
PINNED_SNAPSHOTS = {
    1: (
        "c7025ad1c6d94ea71938830ea125ee8d7d861368",
        "Last build published before the round kicked off (first GW1 kickoff "
        "13 Aug 2026, 16:15 UTC; this build is 15:53:22, 22 min earlier). "
        "Fitted on vendored history ending 21 May 2026, with no 26/27 results "
        "in the fit.",
    ),
}

SNAP_FIELDS = ("kickoff", "home", "away", "home_short", "away_short",
               "cs_home_pct", "cs_away_pct")


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------

def fetch_feed() -> list[dict]:
    """RSL-feedin ottelut mallinimin. Yksi kutsu, kaikki kierrokset."""
    from scripts.build_spl_phase0 import SPL_BASE, SPL_HEADERS, SHORT_TO_MODEL
    import requests

    boot = requests.get(f"{SPL_BASE}/bootstrap-static/", headers=SPL_HEADERS,
                        timeout=30)
    boot.raise_for_status()
    teams_by_id = {t["id"]: t for t in boot.json().get("teams", [])}
    r = requests.get(f"{SPL_BASE}/fixtures/", headers=SPL_HEADERS, timeout=30)
    r.raise_for_status()
    out = []
    for f in r.json():
        gw = f.get("event")
        th, ta = teams_by_id.get(f.get("team_h")), teams_by_id.get(f.get("team_a"))
        if gw is None or not th or not ta:
            continue
        out.append({
            "gw": int(gw),
            "kickoff": f.get("kickoff_time"),
            "finished": bool(f.get("finished")),
            "home": SHORT_TO_MODEL[th["short_name"]],
            "away": SHORT_TO_MODEL[ta["short_name"]],
            "home_score": f.get("team_h_score"),
            "away_score": f.get("team_a_score"),
        })
    return out


def settled_gameweeks(feed: list[dict]) -> list[int]:
    """Kierrokset joiden JOKAINEN ottelu on paattynyt ja skoorattu.

    Osittain pelattua kierrosta ei oteta: puolikas kierros nayttaisi mallin
    tarkkuuden otoksesta jota ei valittu, vaan joka sattui olemaan valmis kun
    skripti ajettiin."""
    by_gw: dict[int, list[dict]] = {}
    for f in feed:
        by_gw.setdefault(f["gw"], []).append(f)
    done = []
    for gw, rows in sorted(by_gw.items()):
        if all(r["finished"] and r["home_score"] is not None
               and r["away_score"] is not None for r in rows):
            done.append(gw)
    return done


def first_kickoff(feed: list[dict], gw: int) -> str:
    ks = [f["kickoff"] for f in feed if f["gw"] == gw and f["kickoff"]]
    if not ks:
        raise SystemExit(f"VIRHE: GW{gw}:lle ei ole avauspotkua feedissa.")
    return min(ks)


# ---------------------------------------------------------------------------
# Snapshotit
# ---------------------------------------------------------------------------

def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=config.PROJECT_ROOT,
                          capture_output=True, check=True).stdout.decode("utf-8")


def resolve_commit(gw: int, kickoff_iso: str) -> tuple[str, str]:
    """Viimeinen artefaktin commit ENNEN kierroksen avauspotkua.

    Palauttaa (sha, perustelu). Kasin pinnatut ohittavat resolverin."""
    if gw in PINNED_SNAPSHOTS:
        return PINNED_SNAPSHOTS[gw]
    kickoff = datetime.fromisoformat(kickoff_iso.replace("Z", "+00:00"))
    log = _git("log", "--format=%H %cI", "--", ARTEFACT).splitlines()
    for line in log:  # uusin ensin
        sha, iso = line.split(" ", 1)
        when = datetime.fromisoformat(iso.strip())
        if when < kickoff:
            mins = int((kickoff - when).total_seconds() // 60)
            return sha, (
                f"Last build committed before the round kicked off "
                f"({mins} min before the first GW{gw} kickoff).")
    raise SystemExit(
        f"VIRHE: GW{gw}:lle ei loydy artefaktin committia ennen "
        f"{kickoff_iso} — snapshottia ei voi tehda jalkikateen.")


def extract_snapshot(gw: int, feed: list[dict]) -> Path:
    """Poimi kierroksen ennusteet oikeasta commitista ja vendoroi ote."""
    kickoff = first_kickoff(feed, gw)
    sha, why = resolve_commit(gw, kickoff)
    raw = _git("show", f"{sha}:{ARTEFACT}")
    full = json.loads(raw)
    rows = [f for f in full["fixtures"] if f.get("gameweek") == gw]
    n_feed = sum(1 for f in feed if f["gw"] == gw)
    if len(rows) != n_feed:
        raise SystemExit(
            f"VIRHE: GW{gw}: feedissa {n_feed} ottelua, commitin "
            f"{sha[:9]} artefaktissa {len(rows)} — ei kirjoiteta vajaata.")
    meta = full.get("meta", {})
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"gw{gw}.json"
    path.write_text(json.dumps({
        "provenance": {
            "commit": sha,
            "generated_at": meta.get("generated_at"),
            "kickoff_utc": kickoff,
            # Julkiselle payloadille englanniksi — kielivahti
            # (test_public_payload_language) valvoo tata.
            "note": why,
            # Mita malli oli NAHNYT kun se teki nama luvut. GW1:n sanamuoto
            # ("no 26/27 results in the fit") ei kelpaa myohemmille
            # kierroksille: inseason-fitti shipattiin 19.8.
            "inseason_matches_in_fit": meta.get("inseason_matches_in_fit", 0),
        },
        "gameweek": gw,
        "fixtures": [{k: f[k] for k in SNAP_FIELDS} for f in rows],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_snapshots() -> dict[int, dict]:
    if not SNAPSHOT_DIR.exists():
        return {}
    out = {}
    for p in sorted(SNAPSHOT_DIR.glob("gw*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        out[int(d["gameweek"])] = d
    return out


# ---------------------------------------------------------------------------
# Laskenta
# ---------------------------------------------------------------------------

def naive_cs_rate() -> float:
    """Vakioennusteen taso: CS-osuus vendoroidussa fittihistoriassa."""
    df = pd.read_csv(RESULTS_CSV, encoding="utf-8")
    sides = len(df) * 2
    cs = int((df["away_score"] == 0).sum() + (df["home_score"] == 0).sum())
    return cs / sides


def _sides_for(snapshot: dict, results: dict[tuple[str, str], tuple[int, int]]
               ) -> tuple[list[dict], list[tuple[float, bool]]]:
    rows, sides = [], []
    for f in snapshot["fixtures"]:
        key = (f["home"], f["away"])
        if key not in results:
            raise SystemExit(
                f"VIRHE: GW{snapshot['gameweek']}: ottelulle {key} ei loydy "
                f"tulosta feedista.")
        hs, as_ = results[key]
        sides.append((f["cs_home_pct"] / 100.0, as_ == 0))
        sides.append((f["cs_away_pct"] / 100.0, hs == 0))
        rows.append({
            "home": f["home"], "away": f["away"],
            "home_short": f["home_short"], "away_short": f["away_short"],
            "score": f"{hs}-{as_}",
            "cs_home_pct": f["cs_home_pct"], "cs_away_pct": f["cs_away_pct"],
            "cs_home_kept": as_ == 0, "cs_away_kept": hs == 0,
        })
    return rows, sides


def _scores(sides: list[tuple[float, bool]], naive_p: float) -> dict:
    n = len(sides)
    return {
        "sides": n,
        "expected_cs": round(sum(p for p, _ in sides), 2),
        "actual_cs": sum(1 for _, kept in sides if kept),
        "brier": round(sum((p - float(k)) ** 2 for p, k in sides) / n, 4),
        "naive_brier": round(
            sum((naive_p - float(k)) ** 2 for _, k in sides) / n, 4),
    }


def build_all(snapshots: dict[int, dict], feed: list[dict],
              naive_p: float | None = None) -> dict:
    """Yksi lukija: uusin RATKENNUT kierros + kausi tahan asti.

    Kierros ei ole parametri. Uusin kierros on aina se jonka jokainen ottelu
    on paattynyt ja jolle on deadline-snapshot — ei se joka sattui olemaan
    viimeisin kun joku ajoi skriptin viimeksi."""
    if naive_p is None:
        naive_p = naive_cs_rate()
    # 🔴 Portin loydos 3.9: tama sanoi "the same two-season history the model
    # is fitted on". Se oli tosi GW1:ssa (inseason_matches_in_fit = 0) ja
    # muuttui epatodeksi HILJAA kun inseason-fitti shipattiin 19.8 (9 -> 18 ->
    # 26 ottelua snapshoteissa). Naiivi taso lasketaan `spl_results.csv`:sta
    # (kaudet 2425 + 2526, 612 ottelua); malli fitataan niiden PAALLE taman
    # kauden otteluilla. Kaksi eri ikkunaa oli kirjoitettu yhdeksi.
    naive_note = ("Constant probability equal to the clean sheet share in the "
                  "two completed seasons before this one. The model is fitted "
                  "on those plus the matches played so far this season.")
    settled = settled_gameweeks(feed)
    # Ratkennut kierros ilman snapshottia ei saa jaada HILJAA pois: silloin
    # `latest` jaatyisi vanhaan kierrokseen eika mikaan huutaisi. Tama on se
    # vika joka 3.9 nakyi sivulla neljä kierrosta.
    missing = [gw for gw in settled if gw not in snapshots]
    if missing:
        raise SystemExit(
            f"VIRHE: ratkenneilta kierroksilta {missing} puuttuu "
            f"deadline-snapshot — aja `--extract` ennen buildia. Kausi ei saa "
            f"julkaista osittaista track recordia.")
    done = list(settled)
    if not done:
        raise SystemExit(
            "VIRHE: yhtaan ratkennutta kierrosta — ei mitaan tasmaytettavaa.")
    results_by_gw: dict[int, dict[tuple[str, str], tuple[int, int]]] = {}
    for f in feed:
        if f["finished"] and f["home_score"] is not None:
            results_by_gw.setdefault(f["gw"], {})[(f["home"], f["away"])] = (
                int(f["home_score"]), int(f["away_score"]))

    per_gw: list[dict] = []
    all_sides: list[tuple[float, bool]] = []
    latest_rows: list[dict] = []
    latest_sides: list[tuple[float, bool]] = []
    for gw in done:
        rows, sides = _sides_for(snapshots[gw], results_by_gw.get(gw, {}))
        all_sides.extend(sides)
        block = {"gameweek": gw, "snapshot": snapshots[gw]["provenance"]}
        block.update(_scores(sides, naive_p))
        per_gw.append(block)
        if gw == done[-1]:
            latest_rows, latest_sides = rows, sides

    latest_gw = done[-1]
    top3 = sorted(
        ((f"{r['home']} (vs {r['away_short']})" if side == "home"
          else f"{r['away']} (at {r['home_short']})",
          r[f"cs_{side}_pct"], r[f"cs_{side}_kept"])
         for r in latest_rows for side in ("home", "away")),
        key=lambda x: -x[1],
    )[:3]

    out = {
        # Taaksepain yhteensopivat avaimet = UUSIN ratkennut kierros. SPA:n
        # otsikko lukee naita, ja se on nyt kauden viimeisin eika kauden
        # ensimmainen.
        "gameweek": latest_gw,
        "snapshot": snapshots[latest_gw]["provenance"],
        "naive_p": round(naive_p, 4),
        "naive_note": naive_note,
        "top3": [{"team": t, "cs_pct": p, "kept": k} for t, p, k in top3],
        "fixtures": latest_rows,
        # Uudet avaimet: koko kausi.
        "gameweeks": per_gw,
        "season_to_date": {
            "gameweeks": done,
            "matches": sum(len(snapshots[gw]["fixtures"]) for gw in done),
            "naive_p": round(naive_p, 4),
            **_scores(all_sides, naive_p),
        },
    }
    out.update(_scores(latest_sides, naive_p))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", action="store_true",
                    help="vendoroi puuttuvat deadline-snapshotit git-historiasta")
    args = ap.parse_args()
    feed = fetch_feed()

    if args.extract:
        have = set(load_snapshots())
        made = 0
        for gw in settled_gameweeks(feed):
            if gw in have:
                continue
            print(f"GW{gw}: {extract_snapshot(gw, feed)}")
            made += 1
        print(f"Uusia snapshotteja: {made}")
        return 0

    doc = build_all(load_snapshots(), feed)
    doc["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    OUT_PATH.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    s = doc["season_to_date"]
    print(f"Uusin ratkennut: GW{doc['gameweek']} — odotettu "
          f"{doc['expected_cs']:.2f} CS, toteutui {doc['actual_cs']} · "
          f"Brier {doc['brier']:.4f} vs naiivi {doc['naive_brier']:.4f}")
    print(f"Kausi GW{s['gameweeks'][0]}-GW{s['gameweeks'][-1]}: {s['sides']} "
          f"joukkue-sivua, odotettu {s['expected_cs']:.2f}, toteutui "
          f"{s['actual_cs']} · Brier {s['brier']:.4f} vs {s['naive_brier']:.4f}")
    print(f"Kirjoitettu: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
