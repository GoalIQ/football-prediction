"""Nousijan koti-avaus: onko buusti oikea ja kuuluuko se ennustepolkuun?

TAUSTA (22.8.2026, Villen havainto). `PROMOTED_HOME_OPENER_ATT_BOOST = 1.30`
elaa `src/models/fpl_context.py`:ssa ja sita kutsuu VAIN FPL-putki
(`build_fpl_xp`, `build_fpl_phase0`). Ottelu-ennustepolku (`api/main.py`) ei
importoi moduulia lainkaan. GW1 2026/27 nayttai mita se maksaa: Hull 2-0
Man Utd (annoimme Hullille 13 %) ja Ipswich 2-1 Sunderland (21 %) — liigan
ainoat nousijakotipelit, molemmat ensimmaisia kotipeleja, molemmat hutteja.

MIKSI TAMA SKRIPTI EIKA SUORA KYTKENTA. Alkuperainen kalibrointi on
**n=3 koti-avausta** (25/26 walk-forward). Kolme ottelua ei riita
mallimuutoksen perusteeksi, ja tama talo on juuri tanaan mitannut toisen
"ilmeisen" korjauksen (BSA-tasapelit) pois olemassaolosta. Kysymykset:

  1. Onko ilmio olemassa isommalla otoksella?
  2. **Onko se NOUSIJA-ilmio vai KAUDEN-AVAUS-ilmio?** Jos jokainen joukkue
     ylisuorittaa ensimmaisessa kotipelissaan, "promoted" on vaara selittaja
     ja buusti kohdistuu vaaraan joukkoon. Tata kontrollia ei ollut
     alkuperaisessa kalibroinnissa.
  3. Jos ilmio on olemassa, mika kerroin minimoi 1X2-log lossin — ja onko
     ero kohinaa?

MENETELMA. Walk-forward: jokaiselle mitattavalle ottelulle sovitetaan malli
VAIN sita edeltavalla datalla (tuotannon parametrit), ennustetaan lambda/mu ja
1X2, ja verrataan toteumaan. Nousijaksi lasketaan joukkue joka on talla
kaudella muttei edellisella. Otos: viisi monikautista liigaa + PL.

AJO:
    .venv/Scripts/python.exe scripts/backtest_promoted_home_opener.py
    .venv/Scripts/python.exe scripts/backtest_promoted_home_opener.py --from-season 2018
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

from src.models.dixon_coles import DixonColesModel  # noqa: E402

RAW = ROOT / "data" / "raw" / "footballdata"

# Tuotannon fit-parametrit (api/main.py oletukset).
PROD_DECAY = 0.0035
PROD_L2 = 2.0

# Monikautiset tiedostot: yksi tiedosto, sarake Season.
MULTI = [
    ("BRA Serie A", "BRA_Serie_A_all.csv"),
    ("SWE Allsvenskan", "SWE_Allsvenskan_all.csv"),
    ("NOR Eliteserien", "NOR_Eliteserien_all.csv"),
    ("DEN Superliga", "DEN_Superliga_all.csv"),
    ("FIN Veikkausliiga", "FIN_Veikkausliiga_all.csv"),
]
# Kausikohtaiset PL-tiedostot (eri sarakenimet).
PL_FILES = [
    ("2022/23", "ENG_Premier_League_2223.csv"),
    ("2023/24", "ENG_Premier_League_2324.csv"),
    ("2024/25", "ENG_Premier_League_2425.csv"),
    ("2025/26", "ENG_Premier_League_2526.csv"),
]


def _norm(df: pd.DataFrame, cols: dict, season=None) -> pd.DataFrame:
    out = pd.DataFrame({
        "season": df[cols["season"]] if season is None else season,
        "date": pd.to_datetime(df[cols["date"]], format="%d/%m/%Y",
                               errors="coerce"),
        "home_team": df[cols["home"]].astype(str).str.strip(),
        "away_team": df[cols["away"]].astype(str).str.strip(),
        "home_score": pd.to_numeric(df[cols["hg"]], errors="coerce"),
        "away_score": pd.to_numeric(df[cols["ag"]], errors="coerce"),
    })
    return out.dropna(subset=["date", "home_score", "away_score"])


def lataa() -> dict[str, pd.DataFrame]:
    ligat: dict[str, pd.DataFrame] = {}
    for nimi, tiedosto in MULTI:
        p = RAW / tiedosto
        if not p.exists():
            continue
        ligat[nimi] = _norm(pd.read_csv(p), {
            "season": "Season", "date": "Date", "home": "Home",
            "away": "Away", "hg": "HG", "ag": "AG"})
    osat = []
    for season, tiedosto in PL_FILES:
        p = RAW / tiedosto
        if not p.exists():
            continue
        osat.append(_norm(pd.read_csv(p), {
            "date": "Date", "home": "HomeTeam", "away": "AwayTeam",
            "hg": "FTHG", "ag": "FTAG"}, season=season))
    if osat:
        ligat["ENG Premier League"] = pd.concat(osat, ignore_index=True)
    for k in ligat:
        ligat[k] = ligat[k].sort_values("date").reset_index(drop=True)
    return ligat


def kausijarjestys(df: pd.DataFrame) -> list:
    """Kaudet aikajarjestyksessa (merkkijonokaudet eivat lajitellu oikein
    pelkkana tekstina kaikissa formaateissa, joten kaytetaan alkupaivaa)."""
    alku = df.groupby("season")["date"].min().sort_values()
    return list(alku.index)


def kohteet(df: pd.DataFrame, from_season_year: int) -> list[dict]:
    """Mitattavat ottelut: JOKAISEN joukkueen ensimmainen kotipeli kaudella,
    liputettuna nousijaksi tai ei. Nousija = talla kaudella, ei edellisella.

    Molemmat ryhmat kerataan samalla logiikalla, jotta kontrolli ei eroa
    kohteesta millaan muulla kuin nousijastatuksella.
    """
    kaudet = kausijarjestys(df)
    joukkueet = {s: set(g["home_team"]) | set(g["away_team"])
                 for s, g in df.groupby("season")}
    out = []
    for i, s in enumerate(kaudet):
        if i == 0:
            continue  # ei edellista kautta -> nousijastatusta ei voi paatella
        g = df[df["season"] == s]
        if g["date"].min().year < from_season_year:
            continue
        nousijat = joukkueet[s] - joukkueet[kaudet[i - 1]]
        for team in sorted(joukkueet[s]):
            koti = g[g["home_team"] == team]
            if koti.empty:
                continue
            eka = koti.iloc[0]
            out.append({
                "season": s, "date": eka["date"], "team": team,
                "home_team": eka["home_team"], "away_team": eka["away_team"],
                "home_score": int(eka["home_score"]),
                "away_score": int(eka["away_score"]),
                "promoted": team in nousijat,
            })
    return out


def aja_liiga(nimi: str, df: pd.DataFrame, from_season_year: int,
              boosts: list[float]) -> list[dict]:
    rivit = []
    khs = kohteet(df, from_season_year)
    for k in khs:
        train = df[df["date"] < k["date"]]
        if len(train) < 300:
            continue
        malli = DixonColesModel().fit(
            train, decay=PROD_DECAY, date_col="date",
            l2_attack_defence=PROD_L2)
        try:
            lam, mu = malli.expected_goals(k["home_team"], k["away_team"])
        except ValueError:
            continue  # joukkuetta ei ole fitissa (esim. aivan uusi seura)
        rivi = dict(k)
        rivi["league"] = nimi
        rivi["lam"] = float(lam)
        rivi["mu"] = float(mu)
        rivi["converged"] = bool(getattr(malli, "fit_success_", True))
        for b in boosts:
            adj = {"home_factor": b, "away_factor": 1.0}
            p = malli.predict_1x2(k["home_team"], k["away_team"],
                                  adjustments=adj)
            rivi[f"p_home_{b}"] = p["home"]
            rivi[f"p_draw_{b}"] = p["draw"]
            rivi[f"p_away_{b}"] = p["away"]
        rivit.append(rivi)
    return rivit


def log_loss(rows: pd.DataFrame, b: float) -> float:
    eps = 1e-12
    p = np.where(rows["home_score"] > rows["away_score"], rows[f"p_home_{b}"],
                 np.where(rows["home_score"] == rows["away_score"],
                          rows[f"p_draw_{b}"], rows[f"p_away_{b}"]))
    return float(-np.log(np.clip(p, eps, 1)).mean())


def osumat(rows: pd.DataFrame, b: float) -> float:
    pick = np.argmax(rows[[f"p_home_{b}", f"p_draw_{b}", f"p_away_{b}"]].values,
                     axis=1)
    tod = np.where(rows["home_score"] > rows["away_score"], 0,
                   np.where(rows["home_score"] == rows["away_score"], 1, 2))
    return float((pick == tod).mean())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-season", type=int, default=2015)
    ap.add_argument("--boosts", nargs="*", type=float,
                    default=[1.0, 1.1, 1.2, 1.3, 1.4])
    args = ap.parse_args()
    boosts = args.boosts

    ligat = lataa()
    print(f"Liigoja: {len(ligat)} — " + ", ".join(
        f"{k} ({len(v)})" for k, v in ligat.items()))
    print(f"Mitattavat: jokaisen joukkueen 1. kotipeli kaudella "
          f"{args.from_season}->, nousijalippu erikseen.\n")

    kaikki = []
    for nimi, df in ligat.items():
        rivit = aja_liiga(nimi, df, args.from_season, boosts)
        n_prom = sum(1 for r in rivit if r["promoted"])
        print(f"  {nimi:<22} {len(rivit):4d} avausta, joista nousijoita {n_prom}")
        kaikki.extend(rivit)

    if not kaikki:
        print("ei rivejä")
        return 1
    d = pd.DataFrame(kaikki)
    hajonneet = int((~d["converged"]).sum())
    if hajonneet:
        print(f"\nvaroitus: {hajonneet} riviä hajonneesta sovituksesta")

    # --- 1. EFEKTIN KOKO: toteuma / odotus kotimaaleissa -------------------
    print("\n1) KOTIJOUKKUEEN MAALIT, toteuma / mallin odotus (1. kotipeli)")
    print(f"   {'ryhma':<26} {'n':>4} {'toteuma':>8} {'odotus':>8} "
          f"{'suhde':>7} {'95% CI':>16}")
    for label, sub in (("NOUSIJA", d[d["promoted"]]),
                       ("ei-nousija (kontrolli)", d[~d["promoted"]])):
        n = len(sub)
        if n == 0:
            continue
        tot = float(sub["home_score"].mean())
        odo = float(sub["lam"].mean())
        # Bootstrap-CI suhteelle (maalit ovat laskureita, ei normaaleja).
        rng = np.random.default_rng(20260822)
        idx = rng.integers(0, n, size=(4000, n))
        suhteet = (sub["home_score"].values[idx].mean(axis=1)
                   / sub["lam"].values[idx].mean(axis=1))
        lo, hi = np.percentile(suhteet, [2.5, 97.5])
        print(f"   {label:<26} {n:4d} {tot:8.2f} {odo:8.2f} "
              f"{tot / odo:7.2f} {f'[{lo:.2f}, {hi:.2f}]':>16}")

    # Nousijan VIERAS-avaus kontrollina: alkuperainen kalibrointi sanoi 0,84
    # eli ei buustia vieraisiin. Tassa se on suoraan mitattavissa.
    print("\n   (nousijan koti-avaus vs sama joukkue muualla: ks. raportti)")

    # --- 2. KUULUUKO BUUSTI ENNUSTEPOLKUUN: 1X2-log loss ------------------
    prom = d[d["promoted"]].reset_index(drop=True)
    print(f"\n2) 1X2 NOUSIJAN KOTI-AVAUKSISSA (n={len(prom)})")
    print(f"   {'kerroin':>8} {'log loss':>10} {'osumat':>8}")
    tulokset = {}
    for b in boosts:
        ll = log_loss(prom, b)
        acc = osumat(prom, b)
        tulokset[b] = ll
        print(f"   {b:8.2f} {ll:10.4f} {acc:7.1%}")
    paras = min(tulokset, key=tulokset.get)
    print(f"   -> paras kerroin otoksessa: {paras} "
          f"(delta vs 1.00: {tulokset[paras] - tulokset[1.0]:+.4f})")

    # Parittainen t-testi rivikohtaisille log lossin eroille: onko ero
    # kohinaa? Keskiarvon paraneminen yksin ei kerro sita.
    if paras != 1.0:
        eps = 1e-12
        def per_row(b):
            p = np.where(prom["home_score"] > prom["away_score"], prom[f"p_home_{b}"],
                         np.where(prom["home_score"] == prom["away_score"],
                                  prom[f"p_draw_{b}"], prom[f"p_away_{b}"]))
            return -np.log(np.clip(p, eps, 1))
        erot = per_row(1.0) - per_row(paras)
        t = float(erot.mean() / (erot.std(ddof=1) / math.sqrt(len(erot))))
        print(f"   parittainen t (1.00 vs {paras}): t={t:+.2f}, n={len(erot)}")

    # --- 3. SAMA KERROIN KONTROLLIRYHMASSA (ei saa auttaa) ----------------
    ctrl = d[~d["promoted"]].reset_index(drop=True)
    if len(ctrl) > 0:
        print(f"\n3) NEGATIIVINEN KONTROLLI: sama kerroin ei-nousijoiden "
              f"1. kotipeleissa (n={len(ctrl)})")
        print(f"   {'kerroin':>8} {'log loss':>10}")
        for b in boosts:
            print(f"   {b:8.2f} {log_loss(ctrl, b):10.4f}")
        print("   Jos kerroin parantaa TATAKIN ryhmaa, kyse ei ole "
              "nousijailmiosta vaan kotiedun aliarviosta avauksissa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
