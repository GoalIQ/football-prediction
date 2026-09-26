"""Kumppanisyote: GoalIQ:n xP-projektiot kumppanin tyokaluun (26.9.2026).

Ensimmainen kumppani FPL Demon (fpldemon.com), ehdot sovittu X DM:ssa 26.9
(Villen GO): FPL-pelaaja-id + seuraavat 5 kierrosta, luvut vain plannerin ja
solverin sisalla, "Projected points powered by GoalIQ" + linkki. Minuutit ja
muut mallin kentat EIVAT kuulu syotteeseen.

TURVA (saanto 6a, "tee vaarasta vaihtoehdosta mahdoton"):
  - Vastaus rakennetaan SALLITTUJEN kenttien listasta (`TOP_FIELDS`,
    `PLAYER_FIELDS`), ei kopioimalla projektiota ja poistamalla. Uusi kentta
    projektiossa ei voi vuotaa syotteeseen; tests/test_partner_xp_feed.py
    kaatuu jos vastauksessa on yksikin kentta listan ulkopuolelta.
  - Lahde on `load_xp_actionable()`: kierrosta jonka deadline on mennyt ei
    tarjota.
  - Avaimet ymparistomuuttujassa PARTNER_XP_KEYS muodossa
    "nimi:avain,nimi2:avain2". Puuttuva tai tyhja -> 403 aina (reitti pois
    paalta, sama linja kuin require_admin). Vaara tai puuttuva avain -> 401.
    Avain perutaan poistamalla se muuttujasta (+ deploy, ks. muisti
    render-save-only-ei-ota-kayttoon).
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response

from src.models.fpl_xp import load_xp_actionable

router = APIRouter()
log = logging.getLogger("goaliq.partner")

#: Sovittu horisontti (X DM 26.9): seuraavat 5 kierrosta.
PARTNER_XP_HORIZON = 5

#: Vastauksen ainoat sallitut kentat. Lisays vaatii paatoksen, ei koodimuutosta
#: joka "vain lisaa yhden kentan": testi lukee nama samat joukot.
TOP_FIELDS = frozenset({"source", "attribution", "link", "generated_at",
                        "gameweeks", "note", "players"})
PLAYER_FIELDS = frozenset({"id", "xp"})

ATTRIBUTION = "Projected points powered by GoalIQ"
NOTE = ("Players not listed have no projection for these gameweeks. "
        "Numbers are for use inside the partner's tools only, as agreed.")
_LINK = "https://pro.goaliq.app/players/player-xp?utm_source={name}&utm_medium=partner"


def _partner_keys() -> dict[str, str]:
    """{avain: kumppanin nimi} ymparistosta. Virheellinen pari ohitetaan."""
    raw = (os.getenv("PARTNER_XP_KEYS") or "").strip()
    out: dict[str, str] = {}
    for part in raw.split(","):
        name, sep, key = part.strip().partition(":")
        name, key = name.strip(), key.strip()
        if sep and name and len(key) >= 24:
            out[key] = name
    return out


def require_partner(request: Request) -> str:
    """Palauttaa kumppanin nimen tai nostaa 403/401."""
    keys = _partner_keys()
    if not keys:
        raise HTTPException(status_code=403, detail="Partner feed is disabled.")
    provided = (request.headers.get("x-partner-key") or "").strip()
    if provided:
        for key, name in keys.items():
            # Vakioaikainen vertailu jokaista avainta vasten.
            if hmac.compare_digest(provided, key):
                return name
    raise HTTPException(status_code=401, detail="Invalid partner key.")


def build_partner_xp(data: dict, partner: str,
                     horizon: int = PARTNER_XP_HORIZON) -> Optional[dict]:
    """Syotteen runko sallituista kentista. None = projektiota ei ole."""
    meta = data.get("meta") or {}
    players = data.get("players") or []
    if not meta.get("available") or not players:
        return None
    all_gws = sorted({g["gw"] for p in players for g in (p.get("gameweeks") or [])
                      if isinstance(g.get("gw"), int)})
    gws = all_gws[:horizon]
    wanted = set(gws)
    rows = []
    for p in players:
        pid = p.get("id")
        if not isinstance(pid, int):
            continue
        xp = {str(g["gw"]): round(float(g["xp"]), 1)
              for g in (p.get("gameweeks") or [])
              if g.get("gw") in wanted and isinstance(g.get("xp"), (int, float))}
        if xp:
            rows.append({"id": pid, "xp": xp})
    return {
        "source": "GoalIQ",
        "attribution": ATTRIBUTION,
        "link": _LINK.format(name=partner),
        "generated_at": meta.get("generated_at"),
        "gameweeks": gws,
        "note": NOTE,
        "players": rows,
    }


@router.get("/api/partner/xp", include_in_schema=False)
def partner_xp(request: Request, response: Response):
    """Kumppanin xP-syote (X-Partner-Key-header)."""
    partner = require_partner(request)
    out = build_partner_xp(load_xp_actionable(), partner)
    if out is None:
        raise HTTPException(status_code=503,
                            detail="xP projections are not available yet.")
    # Kumppani hakee skriptilla (30 min valein); data paivittyy tunneissa.
    response.headers["Cache-Control"] = "private, max-age=300"
    log.info("partner xp feed: %s gws=%s players=%d generated_at=%s",
             partner, out["gameweeks"], len(out["players"]), out["generated_at"])
    return out
