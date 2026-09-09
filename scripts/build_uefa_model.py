# -*- coding: utf-8 -*-
"""Bake: UEFA-yhteismalli levylle (data/uefa_joint_model.json).

Ajetaan ucl-refresh.yml:ssa 6 h valein. Kutsuu TASAN samaa fittipolkua
kuin API (`api.main._fit_uefa_yhteismalli`), jotta artefakti ja live-fitti
eivat voi erota: eri kutsuja, sama funktio. Ks. src/models/uefa_prebuilt.py.

AJO:  python -m scripts.build_uefa_model
Exit 0 = kirjoitettu. Exit 1 = fitti epaonnistui (artefaktia EI kosketa;
API fittaa livena kunnes seuraava ajo onnistuu).
"""
from __future__ import annotations

import sys
import time

import config
from src.models import uefa_prebuilt

TOURNAMENT = "INT-Champions League"


def main() -> int:
    from api.main import _UEFA_SEASONS, _fit_uefa_yhteismalli, uefa_prebuilt_decay

    t0 = time.time()
    pari = list(config.current_season_pair())
    decay = uefa_prebuilt_decay()
    try:
        dc = _fit_uefa_yhteismalli((TOURNAMENT,), tuple(_UEFA_SEASONS), decay,
                                   allow_prebuilt=False)
    except Exception as e:  # HTTPException tai datavirhe
        print(f"VIRHE: yhteisfitti epaonnistui: {type(e).__name__}: {e}")
        return 1
    meta = uefa_prebuilt.save(dc, tournament=TOURNAMENT, season_pair=pari,
                              decay=decay,
                              extra={"fit_seconds": round(time.time() - t0, 1)})
    print(f"UEFA-malli kirjoitettu: {meta['n_clubs']} seuraa, {meta['built_at']}, "
          f"fitti {meta['fit_seconds']} s -> {uefa_prebuilt.PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
