"""Rakenna vendoroitu varasnapshot football-data.co.uk -liigoille.

Aja kun lahde on PYSTYSSA, commitoi tulos:

    python scripts/build_fd_fallback.py
    git add data/fd_fallback && git commit

Taustaa: 8.9.2026 football-data.co.uk oli kokonaan alhaalla (503 myos sivun
juuresta) ja nelja liigaa oli kuollut tuotannossa. Renderin levy on efemeeri,
joten levycache ei auta kylmakaynnistyksessa — vain repoon vendoroitu tiedosto
selviaa. Ks. `src/data/fd_fallback.py`.

Oletuksena skripti kayttaa PAIKALLISTA cachea (ei verkkoa), jotta snapshot voi
syntya myos katkoksen aikana jos kehittajan koneella on tuoretta dataa.
`--force` hakee upstreamista.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

import config  # noqa: E402
from src.data.fd_fallback import (  # noqa: E402
    FALLBACK_DIR,
    SNAPSHOT_COLS,
    VENDORED_LEAGUES,
    polku,
)
from src.data.footballdata import lataa  # noqa: E402


def kaudet_liigalle(liiga: str) -> list[str]:
    """Snapshotiin otettavat kaudet.

    UEFA-ikkunan levyinen (4 kautta) myos domestic-liigoille: snapshot on
    varapolku, ja liian kapea vara olisi sama vika pienempana — kauden alussa
    aktiivisessa kaudessa on nolla ottelua.
    """
    kaudet = config.uefa_season_window()
    if liiga in ("BRA-Serie A",):
        # Kalenterivuosiliiga: 'new'-tiedosto kantaa kaikki kaudet, ja
        # `lataa_new` suodattaa itse. Annetaan kalenterivuodet.
        vuodet = sorted({int("20" + k[:2]) for k in kaudet} | {int("20" + k[2:]) for k in kaudet})
        return [str(v) for v in vuodet]
    return kaudet


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="hae upstreamista vaikka levycache olisi olemassa")
    args = ap.parse_args()

    FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
    rc = 0
    for liiga in VENDORED_LEAGUES:
        kaudet = kaudet_liigalle(liiga)
        df = lataa(liiga, kaudet, force=args.force)
        if df.empty:
            print(f"!! {liiga}: EI DATAA kausille {kaudet} — snapshot ENNALLAAN")
            rc = 1
            continue
        puuttuvat = [c for c in SNAPSHOT_COLS if c not in df.columns]
        if puuttuvat:
            print(f"!! {liiga}: sarakkeita puuttuu {puuttuvat} — ohitetaan")
            rc = 1
            continue
        out = df[list(SNAPSHOT_COLS)].copy()
        # Vain PELATUT ottelut: tulokseton rivi ei opeta mallille mitaan ja
        # tekisi snapshotista aikataulun, ei tulosdataa.
        out = out.dropna(subset=["home_score", "away_score"])
        out = out.sort_values(["date", "home_team"]).reset_index(drop=True)
        out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
        p = polku(liiga)
        out.to_csv(p, index=False, encoding="utf-8")
        koko = p.stat().st_size
        print(
            f"OK {liiga:20s} {len(out):5d} ottelua  "
            f"{out['season'].nunique()} kautta  {koko/1024:.0f} kB  -> {p.name}"
        )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
