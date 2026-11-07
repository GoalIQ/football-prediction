"""FPL Phase 0 — staattisen projektio-JSON:n loader (#FPL-P0).

`/api/fantasy` tarjoilee ajastetun refresh-jobin (scripts/build_fpl_phase0.py)
tuottaman `data/fpl_projections_phase0.json`:n. Tämä moduuli vain lukee
tiedoston — EI laskentaa pyynnössä (Render 0.5 vCPU -budjettisääntö,
FPL-speksi luku 2). Peili: src/models/accuracy.py::load_aggregate.
"""
from __future__ import annotations

import json
from pathlib import Path

import config

PHASE0_PATH = config.DATA_DIR / "fpl_projections_phase0.json"

# SPL-fantasy (7.8): sama skeema, eri liiga — /api/fantasy?league=spl.
# Builderi: scripts/build_spl_phase0.py. Tuntematon liiga-avain EI osu tähän
# mappiin ja endpoint palauttaa 404:n (ei hiljaista fallbackia FPL-dataan —
# väärän liigan data näyttäisi oikealta ja menisi portteista läpi).
SPL_PHASE0_PATH = config.DATA_DIR / "spl_projections_phase0.json"
PHASE0_PATHS = {"fpl": PHASE0_PATH, "spl": SPL_PHASE0_PATH}


def empty_phase0() -> dict:
    """Runko kun projektiota ei ole vielä committattu — appi näyttää
    tyhjän tilan (available=False), ei kaadu."""
    return {
        "meta": {
            "product": "GoalIQ Fantasy Phase 0 - clean sheet % + model FDR",
            "available": False,
            "season": None,
            "generated_at": None,
            "next_gameweek": None,
            "horizon_gw": 0,
        },
        "teams": [],
        "fixtures": [],
    }


def meta_at_clock_phase0(meta: dict, phase0: dict | None = None) -> dict:
    """`fpl_gameweek.meta_at_clock` phase0:n deadlineilla ja kickoff-ajoilla.

    Ei verkkokutsua: `/api/fantasy` ja `/api/fantasy/xp` eivat saa riippua
    FPL:n saatavuudesta. Phase0:ssa lista on, xP-artefaktissa ei.
    """
    from src.models.fpl_gameweek import completed_gameweeks, meta_at_clock
    src = load_phase0() if phase0 is None else phase0
    return meta_at_clock(
        meta,
        deadlines=(src.get("meta") or {}).get("deadlines") or [],
        done=completed_gameweeks(src.get("fixtures")),
    )


def load_phase0(path: Path = PHASE0_PATH) -> dict:
    if not path.exists():
        return empty_phase0()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return empty_phase0()
    if not isinstance(data, dict) or "teams" not in data or "fixtures" not in data:
        return empty_phase0()
    return data
