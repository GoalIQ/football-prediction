"""UEFA Nations League -malli offline -> data/unl_model.json (23.9.2026).

Sama syy kuin build_wc_model.py: Render Starter ei jaksa fitata kaikkien
maiden mallia ajossa. Aja datan virkistyksen jalkeen:

    python -m scripts.update_international_results
    python -m scripts.build_unl_model

Asetukset ja niiden perustelu: src/data/nations_league.py (takatesti UNL
2022/23 + 2024/25, raportti cos-reports/cc-reports/2026-09-23-unl.md).
"""
from __future__ import annotations

import datetime as dt
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from src.data.nations_league import (
    UNL_FIT_BAYES, UNL_FIT_DECAY, UNL_INCLUDE, UNL_MODEL_PATH, UNL_TEAMS,
    UNL_WINDOW_YEARS, fit_unl_model, save_unl_model, window_start,
)


def main() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    start = window_start(now)
    t0 = time.time()
    dc, df = fit_unl_model(start)
    el = time.time() - t0
    puuttuu = [t for t in UNL_TEAMS if t not in dc.attack]
    if puuttuu:
        print(f"VIRHE: UNL-maita puuttuu mallista: {puuttuu}")
        return 1
    meta = {
        "source": "martj42/international_results (CC0)",
        "competition": "UEFA Nations League 2026/27",
        "window_start": start,
        "window_years": UNL_WINDOW_YEARS,
        "include": UNL_INCLUDE,
        "decay": UNL_FIT_DECAY,
        "bayes_shrinkage": UNL_FIT_BAYES,
        "elo_prior": None,
        "home_advantage_kept": True,
        "n_train_matches": len(df),
        "last_train_match": str(df["date"].max())[:10],
        "n_teams": len(dc.teams_),
        "built_at": now.isoformat(timespec="seconds"),
        "fit_seconds": round(el, 2),
    }
    save_unl_model(dc, meta)
    print(f"Fit {el:.1f}s -> {UNL_MODEL_PATH}")
    print(f"meta: {meta}")
    for h, a in [("Portugal", "Wales"), ("Netherlands", "Germany"),
                 ("Andorra", "Malta"), ("Spain", "San Marino")]:
        p = dc.predict_1x2(h, a)
        print(f"  {h} v {a}: 1={p['home']:.2f} X={p['draw']:.2f} 2={p['away']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
