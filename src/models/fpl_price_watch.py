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
    "The percentages are FPL's own price projection, refreshed here every "
    "three hours. The day is their projection too, so a late rush of "
    "transfers still moves it.")
DISCLAIMER_ESTIMATE = (
    "Estimated from FPL net-transfer velocity, used only when the official "
    "projection is unavailable. Model estimate, not a guarantee.")
# Taaksepain-yhteensopivuus: mobiili ja vanhat pinnat lukevat taman nimen.
# 🔴 EI saa osoittaa DISCLAIMER_OFFICIALiin: `empty_price_watch()` kayttaa
# tata, ja silloin tyhja tila vaittaisi virallista lahdetta vaikka dataa ei
# ole lainkaan. Neutraali teksti on ainoa joka on tosi molemmissa tiloissa.
DISCLAIMER = ("Price change candidates. The source is named in the meta for "
              "each build.")


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


OWNED_NOTE = (
    "Owned counts how many of your 15 are on the risers and fallers lists. "
    "Tonight means FPL's own projection crosses the threshold at the next "
    "price update."
)


def annotate_owned(payload: dict, squad_ids: set[int]) -> dict:
    """MY-TEAM-CONTEXT (3.9): merkitse omistetut rivit ja tiivista `owned`-lohko.

    Ei muuta rivien jarjestysta eika poista mitaan: vain `owned: bool` joka
    riville ja `owned`-yhteenveto juureen. Ilman entrya tata ei kutsuta,
    joten vanha vastaus on tasmalleen entinen.
    """
    ids = set(squad_ids)

    def _mark(rows):
        out = []
        for r in rows or []:
            r2 = dict(r)
            r2["owned"] = r2.get("id") in ids
            out.append(r2)
        return out

    payload["risers"] = _mark(payload.get("risers"))
    payload["fallers"] = _mark(payload.get("fallers"))
    own_r = [r for r in payload["risers"] if r["owned"]]
    own_f = [r for r in payload["fallers"] if r["owned"]]
    tonight = [r for r in own_r + own_f if r.get("eta_days") == 0]
    payload["owned"] = {
        "squad_size": len(ids),
        "rising": [{"id": r["id"], "web_name": r["web_name"],
                    "status": r.get("status"), "eta_days": r.get("eta_days")}
                   for r in own_r],
        "falling": [{"id": r["id"], "web_name": r["web_name"],
                     "status": r.get("status"), "eta_days": r.get("eta_days")}
                    for r in own_f],
        "n_rising": len(own_r),
        "n_falling": len(own_f),
        "n_tonight": len(tonight),
        "note": OWNED_NOTE,
    }
    return payload


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
