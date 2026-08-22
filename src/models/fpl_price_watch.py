"""#43 FPL price watch — committatun hinnanmuutosennusteen lataus.

`/api/fantasy/price-watch` lukee `data/fpl_price_watch.json`:n jonka
`scripts/build_fpl_price_watch.py` tuottaa (päivittäinen fpl-data-refresh-cron).
Sama pattern kuin fpl_phase0/fpl_xp: endpoint EI laske mitään pyynnössä.
"""
from __future__ import annotations

import json
from pathlib import Path

import config

PW_PATH = config.DATA_DIR / "fpl_price_watch.json"

# 22.8.2026: FPL alkoi 26/27-kaudella julkaista hinnanmuutosdatan itse
# (bootstrapin price_change_percent / price_change_projections). Vanha
# varaus - "FPL's exact price thresholds are not public" - EI OLE ENAA TOSI,
# ja se oli sivun nakyvin lause. Kaksi eri tekstia, koska kaksi eri lahdetta:
# vaara varaus on pahempi kuin puuttuva.
DISCLAIMER_OFFICIAL = (
    "Straight from the official FPL price projection, updated hourly. A change "
    "lands when the projection reaches 100 percent, and very late transfers "
    "can still move it.")
DISCLAIMER_ESTIMATE = (
    "Estimated from FPL net-transfer velocity, used only when the official "
    "projection is unavailable. Model estimate, not a guarantee.")
# Taaksepain-yhteensopivuus: mobiili ja vanhat pinnat lukevat taman nimen.
DISCLAIMER = DISCLAIMER_OFFICIAL


def empty_price_watch() -> dict:
    """Runko kun tiedostoa ei ole committattu — appi näyttää tyhjän tilan."""
    return {
        "meta": {
            "product": "GoalIQ Fantasy - price watch",
            "available": False,
            "generated_at": None,
            "disclaimer": DISCLAIMER,
        },
        "risers": [],
        "fallers": [],
    }


def load_price_watch(path: Path = PW_PATH) -> dict:
    if not path.exists():
        return empty_price_watch()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return empty_price_watch()
    if not isinstance(data, dict) or "meta" not in data:
        return empty_price_watch()
    data.setdefault("risers", [])
    data.setdefault("fallers", [])
    return data
