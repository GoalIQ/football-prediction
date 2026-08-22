"""Mittaa kannattaako ohuen otoksen nousija-blend PL-fittiin (walk-forward).

Tausta (QUEUE FPL-THIN-BLEND, 19.8.2026): heti kun nousijalla on YKSI pelattu
ottelu, se on `dc.attack`issa fitin jäljiltä ja promoted-baseline ohittaa sen.
Yhden ottelun estimaatti L2-kutistuu sarjan keskitasoon, joka on nousijalle
liian antelias — SPL:ssä mitattu vaikutus GW2:n CS-lukuihin oli +12,4 %-yks
(Al Diriyah). Sama artefakti osuu PL:ään heti kun GW1-tulokset tulevat
football-datasta (~24.8). Korjausehdokas on jo olemassa ja SPL käyttää sitä:
`promoted_baseline.blend_thin_toward_baseline` (w = n/n_min, n_min=6).

Tämä skripti mittaa ehdokkaan HISTORIALLA ennen kuin sitä kytketään PL:ään.

Menetelmä
---------
- Per liiga, per testikausi S: nousijat = kauden S joukkueet joita ei ole
  kaudessa S-1; viiteryhmä = kauden S-1 joukkueet joita ei ole kaudessa S-2.
  Molemmat johdetaan DATASTA, ei muistista — siksi testikausi kelpaa vain jos
  myös S-2:n joukkuelista on saatavilla (puuttuvat kirjataan näkyviin, ei
  hiljaista pudotusta).
- Arviointijoukko = kauden S ottelut joissa vähintään toisella osapuolella on
  nousijastatus JA 1..n_min-1 kauden ottelua fitissä. Vain nämä ottelut voivat
  erota varianttien välillä, joten fitti ajetaan KERRAN per ottelu ja siitä
  luetaan molemmat ennusteet — vertailu on täsmälleen parittainen.
- Treeni = kausi S-1 kokonaan + kauden S ottelut ennen arviointiottelua
  (sama kahden kauden ikkuna kuin tuotannon /api/predict).
- Fit-parametrit = TUOTANNON parametrit: decay 0.0035, l2 2.0,
  per_team_home_adv True, shrink_defence_to_mean False, xg_weight 0.5
  (config.DIXON_COLES_XG_WEIGHT; Understat-liigoilla xG on datassa).
- Variantti A (nykytuotanto): fitti + add_promoted_baseline fitistä
  puuttuville nousijoille (0 ottelua). Variantti B (ehdokas): sama +
  blend_thin_toward_baseline. Molemmat samasta fitistä.
- Metriikat: parittainen 1X2 log loss / Brier / osumatarkkuus, ja clean sheet
  -Brier (kummankin osapuolen CS binäärinä) koska SPL-artefakti näkyi juuri
  CS-luvuissa.

Kontrollit (portin vaatimus, ks. muisti gate-substring-osuma-on-sokea):
- Jokaisessa arviointiottelussa blendin on KOSKETTAVA vähintään yhtä
  osapuolta (telemetria tyhjä -> ajo kaatuu, ei hiljaista no-opia).
- Negatiivinen kontrolli: blendin jälkeen kahden vakiintuneen joukkueen
  keskinäinen ennuste on bittitarkasti sama kuin ennen blendiä.
- fit_success_ kirjataan per rivi (hajonnut sovitus ei piiloudu keskiarvoon).

Ajo:
    .venv/Scripts/python.exe scripts/backtest_thin_blend.py
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from src.data.loader import lataa_otteludata  # noqa: E402
from src.models.dixon_coles import DixonColesModel  # noqa: E402
from src.models.promoted_baseline import (  # noqa: E402
    add_promoted_baseline,
    blend_thin_toward_baseline,
)

LEAGUES = [
    "ENG-Premier League",
    "ESP-La Liga",
    "GER-Bundesliga",
    "ITA-Serie A",
    "FRA-Ligue 1",
]
# Kausikolmikot (S-2, S-1, S): S on testikausi. Kolmikko kelpaa vain jos
# KAIKKI kolme kautta löytyvät liigan datasta — S-2 tarvitaan vain
# joukkuelistana (viiteryhmän johtamiseen), S-1 ja S fittiin.
SEASON_TRIPLES = [
    ("2122", "2223", "2324"),
    ("2223", "2324", "2425"),
    ("2324", "2425", "2526"),
]
N_MIN = 6

# Tuotannon fit-parametrit (api/main.py defaultit + config).
PROD_DECAY = 0.0035
PROD_L2 = 2.0
PROD_PER_TEAM_HOME_ADV = True
PROD_SHRINK_DEFENCE = False
PROD_XG_WEIGHT = config.DIXON_COLES_XG_WEIGHT

OUT_PATH = config.PROJECT_ROOT / "logs" / "thin_blend_backtest.json"


def _fit(train: pd.DataFrame) -> DixonColesModel:
    return DixonColesModel(per_team_home_adv=PROD_PER_TEAM_HOME_ADV).fit(
        train,
        home_team_col="home_team",
        away_team_col="away_team",
        home_goals_col="home_score",
        away_goals_col="away_score",
        decay=PROD_DECAY,
        date_col="date",
        l2_attack_defence=PROD_L2,
        shrink_defence_to_mean=PROD_SHRINK_DEFENCE,
        home_xg_col="home_xg",
        away_xg_col="away_xg",
        xg_weight=PROD_XG_WEIGHT,
    )


def _cs_probs(dc: DixonColesModel, home: str, away: str) -> tuple[float, float]:
    """(P(koti pitää nollan), P(vieras pitää nollan)) score-matriisista.

    Rivit = kotijoukkueen maalit (sama konventio kuin predict_1x2:n tril/triu):
    kodin CS = P(vieras 0) = sarake 0, vieraan CS = P(koti 0) = rivi 0.
    """
    m = dc.score_matrix(home, away)
    return float(m[:, 0].sum()), float(m[0, :].sum())


def _predict_both(dc: DixonColesModel, home: str, away: str) -> dict:
    p = dc.predict_1x2(home, away)
    cs_h, cs_a = _cs_probs(dc, home, away)
    return {"p_home": p["home"], "p_draw": p["draw"], "p_away": p["away"],
            "cs_home": cs_h, "cs_away": cs_a}


def aja_liigakausi(
    df_league: pd.DataFrame,
    prevprev: str,
    prev: str,
    test: str,
) -> tuple[pd.DataFrame, dict] | None:
    """Arviointiottelut yhdelle (liiga, testikausi) -parille.

    Palauttaa (rivit, meta) tai None jos kausikolmikko ei ole datassa.
    """
    seasons_present = set(df_league["season"].astype(str))
    if not {prevprev, prev, test} <= seasons_present:
        return None

    teams = {
        s: set(df_league.loc[df_league["season"].astype(str) == s, "home_team"])
        | set(df_league.loc[df_league["season"].astype(str) == s, "away_team"])
        for s in (prevprev, prev, test)
    }
    promoted = sorted(teams[test] - teams[prev])
    reference = tuple(sorted(teams[prev] - teams[prevprev]))
    if not promoted or not reference:
        # Ei nousijoita tai ei viiteryhmää -> ei mitattavaa. Kirjataan silti.
        return pd.DataFrame(), {
            "promoted": promoted, "reference": list(reference), "n_eval": 0,
            "syy": "ei nousijoita tai viiteryhmää datassa",
        }

    ikkuna = df_league[df_league["season"].astype(str).isin([prev, test])].copy()
    ikkuna = ikkuna.sort_values("date").reset_index(drop=True)
    test_mask = ikkuna["season"].astype(str) == test

    rivit = []
    counts: dict[str, int] = {t: 0 for t in promoted}
    neg_kontrolli_ok = 0
    for i in range(len(ikkuna)):
        ottelu = ikkuna.iloc[i]
        if not test_mask.iloc[i]:
            continue
        home, away = ottelu["home_team"], ottelu["away_team"]
        thin = [t for t in (home, away)
                if t in counts and 1 <= counts[t] < N_MIN]
        if thin:
            train = ikkuna.iloc[:i]
            dc = _fit(train)
            # Nykytuotannon polku: fitistä kokonaan puuttuvat nousijat saavat
            # baselinen (koskee mm. nousija vs nousija -ottelun 0 ottelun
            # osapuolta). Sama molemmissa varianteissa.
            add_promoted_baseline(
                dc, [t for t in promoted if t not in dc.attack],
                reference=reference, allow_frozen=False,
            )
            ennen = _predict_both(dc, home, away)

            # Negatiivinen kontrolli: blend ei saa liikuttaa vakiintuneiden
            # joukkueiden keskinäistä ennustetta. Valitaan pari fitistä.
            vakiintuneet = [t for t in sorted(dc.attack)
                            if t not in promoted][:2]
            kontrolli_ennen = (
                dc.predict_1x2(*vakiintuneet) if len(vakiintuneet) == 2 else None
            )

            blend = blend_thin_toward_baseline(
                dc, counts, promoted, reference=reference,
                n_min=N_MIN, allow_frozen=False,
            )
            # Fail-closed: arviointiotteluun valikoitunut ohut nousija ON
            # blendattava. Tyhjä telemetria = valinta ja blend erimielisiä.
            if not all(t in blend["blended"] for t in thin):
                raise SystemExit(
                    f"VIRHE: blend ei koskettanut {thin} ottelussa "
                    f"{home}-{away} ({ottelu['date']}) — telemetria: {blend}"
                )
            if kontrolli_ennen is not None:
                kontrolli_jalkeen = dc.predict_1x2(*vakiintuneet)
                if kontrolli_ennen != kontrolli_jalkeen:
                    raise SystemExit(
                        f"VIRHE: blend liikutti vakiintuneiden paria "
                        f"{vakiintuneet}: {kontrolli_ennen} -> {kontrolli_jalkeen}"
                    )
                neg_kontrolli_ok += 1

            jalkeen = _predict_both(dc, home, away)

            h_g, a_g = int(ottelu["home_score"]), int(ottelu["away_score"])
            rivit.append({
                "date": str(ottelu["date"]),
                "season": test,
                "home_team": home,
                "away_team": away,
                "home_score": h_g,
                "away_score": a_g,
                "actual_1x2": 0 if h_g > a_g else (1 if h_g == a_g else 2),
                "thin_teams": thin,
                "thin_n": {t: counts[t] for t in thin},
                "fit_converged": bool(getattr(dc, "fit_success_", True)),
                **{f"{k}_a": v for k, v in ennen.items()},
                **{f"{k}_b": v for k, v in jalkeen.items()},
            })
        for t in (home, away):
            if t in counts:
                counts[t] += 1

    meta = {
        "promoted": promoted,
        "reference": list(reference),
        "n_eval": len(rivit),
        "neg_kontrolli_ajoja": neg_kontrolli_ok,
    }
    return pd.DataFrame(rivit), meta


def metriikat(bt: pd.DataFrame) -> dict:
    """Parittaiset metriikat: variantti A (nykytila) vs B (blend)."""
    if bt.empty:
        return {"n": 0}
    y = bt["actual_1x2"].values
    out: dict = {"n": int(len(bt))}
    for tag in ("a", "b"):
        p = np.clip(
            bt[[f"p_home_{tag}", f"p_draw_{tag}", f"p_away_{tag}"]].values,
            1e-10, 1 - 1e-10,
        )
        ll = -np.log(p[np.arange(len(y)), y])
        one_hot = np.eye(3)[y]
        # CS binäärinä molemmille osapuolille poolattuna.
        cs_p = np.concatenate([bt[f"cs_home_{tag}"], bt[f"cs_away_{tag}"]])
        cs_y = np.concatenate([
            (bt["away_score"] == 0).astype(float),
            (bt["home_score"] == 0).astype(float),
        ])
        out[tag] = {
            "log_loss": float(ll.mean()),
            "brier": float(np.mean(np.sum((p - one_hot) ** 2, axis=1))),
            "accuracy": float((p.argmax(axis=1) == y).mean()),
            "cs_brier": float(np.mean((cs_p - cs_y) ** 2)),
        }
    # Parittainen delta (B - A): negatiivinen log loss -delta = blend parempi.
    pa = np.clip(bt[["p_home_a", "p_draw_a", "p_away_a"]].values, 1e-10, 1)
    pb = np.clip(bt[["p_home_b", "p_draw_b", "p_away_b"]].values, 1e-10, 1)
    d = (-np.log(pb[np.arange(len(y)), y])) - (-np.log(pa[np.arange(len(y)), y]))
    se = d.std(ddof=1) / np.sqrt(len(d)) if len(d) > 1 else float("nan")
    out["delta_log_loss"] = float(d.mean())
    out["delta_se"] = float(se)
    out["delta_t"] = float(d.mean() / se) if se and se > 0 else float("nan")
    out["blend_parempi"] = bool(d.mean() < 0)
    out["ei_konvergoituneita"] = int((~bt["fit_converged"]).sum())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", nargs="*", default=LEAGUES)
    ap.add_argument("--out", default=str(OUT_PATH))
    args = ap.parse_args()

    logging.disable(logging.INFO)
    kaikki_kaudet = sorted({s for tri in SEASON_TRIPLES for s in tri})
    print(f"Haetaan data: {len(args.leagues)} liigaa, kaudet {kaikki_kaudet}")
    df = lataa_otteludata(args.leagues, kaikki_kaudet)
    df = df[df["home_score"].notna() & df["away_score"].notna()].copy()
    df["date"] = pd.to_datetime(df["date"])
    print(f"  {len(df)} pelattua ottelua")

    palat: list[pd.DataFrame] = []
    metat: dict[str, dict] = {}
    ohitetut: list[str] = []
    t0 = time.time()
    for liiga in args.leagues:
        osa = df[df["league"] == liiga]
        for prevprev, prev, test in SEASON_TRIPLES:
            tulos = aja_liigakausi(osa, prevprev, prev, test)
            avain = f"{liiga}/{test}"
            if tulos is None:
                # Ei hiljaista pudotusta: puuttuva kausikolmikko kirjataan.
                ohitetut.append(f"{avain} (kaudet {prevprev}/{prev} eivät datassa)")
                continue
            bt, meta = tulos
            metat[avain] = meta
            if not bt.empty:
                bt["league"] = liiga
                palat.append(bt)
            print(f"  {avain}: nousijat {meta['promoted']} "
                  f"viite {meta['reference']} -> {meta['n_eval']} arviointiottelua")

    if ohitetut:
        print("Ohitetut (ei kausikolmikkoa datassa):")
        for o in ohitetut:
            print(f"  - {o}")

    if not palat:
        print("VIRHE: ei yhtään arviointiottelua.")
        return 1
    bt = pd.concat(palat, ignore_index=True)

    tulokset = {"poolattu": metriikat(bt)}
    for liiga in sorted(bt["league"].unique()):
        tulokset[liiga] = metriikat(bt[bt["league"] == liiga])
    kesto = time.time() - t0

    p = tulokset["poolattu"]
    print(f"\nArviointiotteluita {p['n']} ({kesto:.0f} s)")
    print(f"  A (nykytila): log_loss {p['a']['log_loss']:.5f}  "
          f"brier {p['a']['brier']:.5f}  acc {p['a']['accuracy']:.4f}  "
          f"cs_brier {p['a']['cs_brier']:.5f}")
    print(f"  B (blend):    log_loss {p['b']['log_loss']:.5f}  "
          f"brier {p['b']['brier']:.5f}  acc {p['b']['accuracy']:.4f}  "
          f"cs_brier {p['b']['cs_brier']:.5f}")
    print(f"  delta log_loss (B-A) {p['delta_log_loss']:+.5f} "
          f"(se {p['delta_se']:.5f}, t {p['delta_t']:+.2f}) -> "
          f"{'BLEND PAREMPI' if p['blend_parempi'] else 'NYKYTILA PAREMPI'}")
    if p["ei_konvergoituneita"]:
        print(f"  [EI-KONVERGOITUNEITA FITTEJÄ: {p['ei_konvergoituneita']}]")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "menetelma": "fitti per arviointiottelu, parittainen A/B samasta fitistä",
        "n_min": N_MIN,
        "fit": {
            "decay": PROD_DECAY,
            "l2_attack_defence": PROD_L2,
            "per_team_home_adv": PROD_PER_TEAM_HOME_ADV,
            "shrink_defence_to_mean": PROD_SHRINK_DEFENCE,
            "xg_weight": PROD_XG_WEIGHT,
        },
        "liigakaudet": metat,
        "ohitetut": ohitetut,
        "tulokset": tulokset,
        "rivit": bt.to_dict(orient="records"),
    }, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nKirjoitettu: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
