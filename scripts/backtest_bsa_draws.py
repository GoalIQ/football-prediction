"""Tasapelikalibrointi Brasileirassa (BSA-DRAW-CALIBRATION, 22.8).

TAUSTA. Villen havainto 22.8 ("malli ei ennusta yhtaan tasapelia") johti
mittaukseen 137 gradatusta ennusteesta: BSA:ssa ennustettiin 24,3 %
tasapeleja ja toteutui 43,5 % (20/46), z = +3,04. Muut liigat olivat kohinan
sisalla.

MIKSI TAMA SKRIPTI ON OLEMASSA. 46 ottelua on liian pieni otos siihen etta
19 prosenttiyksikon eroa voisi lukea mallin virheeksi. Kysymys jakautuu
kahteen osaan jotka on erotettava ennen kuin mallia kosketaan:

  1. Mika on BSA:n TODELLINEN tasapelitaso? (base rate, ei tama otos)
  2. Kuinka paljon mallin oma ennuste poikkeaa siita? (kalibrointi)

Vasta (2) on korjattavissa. (1):n hajonta on satunnaisuutta jota vastaan
kalibroiminen olisi ylisovitusta — ja juuri sita GO tekisi jos se ajettaisiin
20/46:n perusteella.

AJO:
    .venv/Scripts/python.exe scripts/backtest_bsa_draws.py
    .venv/Scripts/python.exe scripts/backtest_bsa_draws.py --seasons 2021 2026

Tuloste on tarkoituksella ihmisluettava: jokainen luku on se jonka paalle
mahdollinen mallimuutos perustellaan.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models.backtest import walk_forward_dixon_coles  # noqa: E402

CSV = ROOT / "data" / "raw" / "footballdata" / "BRA_Serie_A_all.csv"

# Tuotannon fit-parametrit (api/main.py oletukset) — backtestin on mitattava
# samaa mallia kuin mita shipataan, ei viereista konfiguraatiota.
PROD_DECAY = 0.0035
PROD_L2 = 2.0
PROD_PER_TEAM_HOME_ADV = True
PROD_SHRINK_DEFENCE = False


def lataa(seasons: tuple[int, int]) -> pd.DataFrame:
    df = pd.read_csv(CSV)
    df = df.dropna(subset=["HG", "AG", "Res"])
    df = df[(df["Season"] >= seasons[0]) & (df["Season"] <= seasons[1])]
    out = pd.DataFrame({
        "date": pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce"),
        "home_team": df["Home"].astype(str),
        "away_team": df["Away"].astype(str),
        "home_score": df["HG"].astype(int),
        "away_score": df["AG"].astype(int),
        # Pinnaclen sulkuhinnat: markkinan oma tasapelitodennakoisyys samalle
        # ottelulle. Tama on VERTAILUKOHTA jonka varianssi on murto-osa
        # binaarisen lopputuloksen varianssista.
        "psc_h": pd.to_numeric(df["PSCH"], errors="coerce"),
        "psc_d": pd.to_numeric(df["PSCD"], errors="coerce"),
        "psc_a": pd.to_numeric(df["PSCA"], errors="coerce"),
    })
    return out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def devig(h: float, d: float, a: float) -> float | None:
    """Markkinan de-vigattu P(tasapeli) (proportionaalinen normalisointi)."""
    if not all(np.isfinite([h, d, a])) or min(h, d, a) <= 1.0:
        return None
    inv = np.array([1.0 / h, 1.0 / d, 1.0 / a])
    return float(inv[1] / inv.sum())


def z_score(actual: int, probs: np.ndarray) -> float:
    exp = probs.sum()
    var = float((probs * (1.0 - probs)).sum())
    return (actual - exp) / math.sqrt(var) if var > 0 else float("nan")


def raportoi(nimi: str, p_draw: np.ndarray, toteutui: np.ndarray) -> dict:
    n = len(p_draw)
    act = int(toteutui.sum())
    exp = float(p_draw.sum())
    z = z_score(act, p_draw)
    brier = float(((p_draw - toteutui) ** 2).mean())
    # Kiintea baseline: sama luku joka ottelulle = otoksen oma tasapelitaso.
    # Jos malli ei paihita tata, se ei tuo tasapeleista mitaan tietoa.
    base = float(toteutui.mean())
    brier_base = float(((base - toteutui) ** 2).mean())
    print(
        f"{nimi:<28} n={n:4d}  ennuste {100 * exp / n:5.1f}%  "
        f"toteutui {100 * act / n:5.1f}%  z={z:+5.2f}  "
        f"Brier {brier:.4f} (kiintea {brier_base:.4f})"
    )
    return {"n": n, "pred": exp / n, "actual": act / n, "z": z,
            "brier": brier, "brier_base": brier_base}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs=2, type=int, default=[2021, 2026])
    ap.add_argument("--min-train", type=int, default=380,
                    help="Yksi kokonainen kausi ennen ensimmaista ennustetta")
    ap.add_argument("--refit-days", type=int, default=7)
    args = ap.parse_args()

    df = lataa((args.seasons[0], args.seasons[1]))
    print(f"BSA {args.seasons[0]}-{args.seasons[1]}: {len(df)} ottelua, "
          f"{df['date'].min().date()} - {df['date'].max().date()}")

    # --- 1. TODELLINEN TASO (ei mallia, ei otosta) --------------------------
    toteutuneet = (df["home_score"] == df["away_score"]).to_numpy()
    print(f"\n1) BSA:n oma tasapelitaso tassa aineistossa: "
          f"{100 * toteutuneet.mean():.1f}% ({int(toteutuneet.sum())}/{len(df)})")
    per_season = df.assign(draw=toteutuneet).groupby(df["date"].dt.year)["draw"].agg(["mean", "size"])
    print("   kausittain: " + ", ".join(
        f"{int(y)} {100 * r['mean']:.1f}%" for y, r in per_season.iterrows()))

    mkt = df.apply(lambda r: devig(r["psc_h"], r["psc_d"], r["psc_a"]), axis=1)
    mkt_ok = mkt.dropna()
    if len(mkt_ok) > 0:
        print(f"   markkinan de-vig P(tasapeli): {100 * mkt_ok.mean():.1f}% "
              f"(n={len(mkt_ok)}) — riippumaton vertailukohta")

    # --- 2. MALLIN KALIBROINTI (walk-forward, tuotannon parametrit) ---------
    print(f"\n2) Walk-forward (decay={PROD_DECAY}, l2={PROD_L2}, "
          f"refit {args.refit_days} vrk, min_train={args.min_train})...")
    bt = walk_forward_dixon_coles(
        df,
        min_train_size=args.min_train,
        refit_every_days=args.refit_days,
        decay=PROD_DECAY,
        l2_attack_defence=PROD_L2,
        per_team_home_adv=PROD_PER_TEAM_HOME_ADV,
        shrink_defence_to_mean=PROD_SHRINK_DEFENCE,
    )
    if len(bt) == 0:
        print("   ei yhtaan ennustetta — tarkista min_train_size")
        return 1

    hajonneet = int((~bt["fit_converged"]).sum())
    if hajonneet:
        print(f"   varoitus: {hajonneet} riviä hajonneesta sovituksesta")

    p = bt["p_draw"].to_numpy()
    y = (bt["actual_1x2"] == 1).to_numpy().astype(float)
    print()
    tulos = raportoi("malli (walk-forward)", p, y)

    # Markkinavertailu samoille otteluille (jos hinnat ovat olemassa).
    avain = df.set_index(["date", "home_team", "away_team"])
    mkt_p, mkt_y = [], []
    for _, r in bt.iterrows():
        try:
            rivi = avain.loc[(r["date"], r["home_team"], r["away_team"])]
        except KeyError:
            continue
        if isinstance(rivi, pd.DataFrame):
            rivi = rivi.iloc[0]
        m = devig(rivi["psc_h"], rivi["psc_d"], rivi["psc_a"])
        if m is None:
            continue
        mkt_p.append(m)
        mkt_y.append(1.0 if r["actual_1x2"] == 1 else 0.0)
    if mkt_p:
        raportoi("markkina (samat ottelut)", np.array(mkt_p), np.array(mkt_y))
        print(f"\n   mallin ja markkinan ero keskimaarin: "
              f"{100 * (tulos['pred'] - float(np.mean(mkt_p))):+.1f} pp")

    # --- 2b. VILLEN ALKUPERAINEN HAVAINTO ISOLLA OTOKSELLA -------------------
    # "Malli ei ennusta yhtaan tasapelia" = tasapeli ei ole KOSKAAN korkein
    # kolmesta. Se on eri vaite kuin "tasapeleja on liian vahan", ja se voi
    # olla tosi vaikka kalibrointi olisi taydellinen: tasapelin massa jakautuu
    # 0-0/1-1/2-2 kesken kun taas kotivoitto kerää kaikki 1-0/2-0/2-1/3-1...
    argmax_draw = int(((bt["p_draw"] >= bt["p_home"]) & (bt["p_draw"] >= bt["p_away"])).sum())
    print()
    print(f"2b) Tasapeli korkeimpana todennakoisyytena: {argmax_draw}/{len(bt)} "
          f"({100 * argmax_draw / len(bt):.1f}%)")
    print(f"    P(tasapeli): max {bt['p_draw'].max():.3f}, "
          f"mediaani {bt['p_draw'].median():.3f}, min {bt['p_draw'].min():.3f}")
    # Kuinka usein tasapeli TOTEUTUI kun se oli mallin mielesta lahinta
    # (ylin desiili)? Jos malli ei erottele lainkaan, tama on sama kuin taso.
    ylin = bt.nlargest(max(1, len(bt) // 10), "p_draw")
    alin = bt.nsmallest(max(1, len(bt) // 10), "p_draw")
    print(f"    ylin desiili P(D)={ylin['p_draw'].mean():.3f} -> toteutui "
          f"{100 * (ylin['actual_1x2'] == 1).mean():.1f}%  |  "
          f"alin desiili P(D)={alin['p_draw'].mean():.3f} -> toteutui "
          f"{100 * (alin['actual_1x2'] == 1).mean():.1f}%")

    # --- 3. MITA 46 OTTELUN OTOS OLISI VOINUT NAYTTAA -----------------------
    # Sama kysymys kuin lokista mitattu z=+3,04: kuinka usein 46 ottelun otos
    # antaa >= 20 tasapelia kun todellinen taso on talla tasolla? Ilman tata
    # lukua z=+3,04 luetaan mallin virheeksi vaikka se olisi otoskohinaa.
    rng = np.random.default_rng(20260822)
    taso = float(toteutuneet.mean())
    otokset = rng.binomial(46, taso, size=200_000)
    print(f"\n3) Otoskohina: jos todellinen taso on {100 * taso:.1f}%, "
          f"46 ottelun otoksessa on >= 20 tasapelia "
          f"{100 * (otokset >= 20).mean():.2f} %:ssa tapauksista "
          f"(keskiarvo {otokset.mean():.1f}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
