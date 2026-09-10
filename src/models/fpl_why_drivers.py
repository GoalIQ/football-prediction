"""Pisteiden todiste ilmaispinnalle: yksi lukija, yksi luku per rivi.

XP-AJURIT-ILMAISPINNALLE (Villen paatos 9.9.2026). Ensimmainen versio
julkaisi `fpl_why.json`-artefaktin ajurikategoriat ("goals & assists + set
pieces"). Portti 10.9 blokkasi sen kolmesta syysta: (1) "low ownership" ei
ole pisteiden lahde, (2) "set pieces" oli tosi vain artefaktin loysalla
kynnyksella (kolmas nimi listalla) ja 7/100 rivilla Premium-lukija
`driver_facts` kielsi sen, (3) "goals & assists" laukesi 0,15 xGI/90:sta
keskuspuolustajalle. Kategoria oli vaite ilman reittia.

Toinen versio julkaisi `driver_facts`-todisteen. Portin kierros 2 loysi
etta pelaajan "nollapeli-%" oli pistekomponentista johdettu luku
(minuuttiodotus mukana) joka poikkesi omasta /fpl-sivustamme 24/47 rivilla,
ja etta "last season" xGI:lla ei ollut ilmaista reittia.

Nyt: TODISTE JOLLA ON REITTI.
- Set piece -vastuu: `driver_facts` (1. tai 2. ottaja, sama kynnys kuin
  kortin merkeissa). Reitti: FPL:n oma pelaajasivu.
- Nollapeli: SEURAN GW-luku samasta kentasta jonka goaliq.app/fpl renderoi
  (`fpl_projections_phase0.json` teams[].fixtures[gw].cs_pct) ja SAMALLA
  muotoilijalla (`fmt.fmt_pct`: "38.6%", ei "39%"), solussa seuran lyhenne:
  "ARS 51% clean sheet chance". Vain GKP/DEF.
- xGI/90 viime kaudelta, kausi nimettyna ("0.57 xGI/90 in 2025/26"), sama
  lattia kuin why-selitteella (XGI_MIN). Reitti: FPL:n pelaajahistoria
  (history_past kantaa expected_goal_involvements + minutes). Vain MID/FWD.
- Ei koskaan: minutes (xMins on jo rivilla), fixtures, bonus, price,
  differential. Yksi todiste per rivi; jos mitaan ei ole, rivi on tyhja.

Sivu ja kortti kutsuvat tata moduulia (tests/test_card_matches_public_page.py).
"""
from __future__ import annotations

import json
from pathlib import Path

from src.models.fmt import fmt_pct
from src.models.fpl_gameweek import actionable_gameweek
from src.models.fpl_xp import driver_facts

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PHASE0_PATH = PROJECT_ROOT / "data" / "fpl_projections_phase0.json"

#: Sama kynnys jolla oma why-selitteemme suostuu siteeraamaan xGI:ta
#: (scripts/build_fpl_why.py importtaa taman). Alle: ei todistetta.
XGI_MIN = 0.15

PUBLISHABLE = ("set_pieces", "clean_sheets", "attacking_output")
NEVER = ("minutes", "fixtures", "bonus", "price", "differential")

PAGE_LEGEND = ("Under each name: the one number the projection leans on. "
               "Clean sheet chance is his club's for this gameweek, the same "
               "number as on goaliq.app/fpl#clean-sheets. Set-piece order (first "
               "or second taker only) and last season's xGI come from FPL's own "
               "player pages.")


def load_team_cs(gw: int | None, path: Path = PHASE0_PATH) -> dict[str, float]:
    """seuran lyhenne -> nollapeli-% kierrokselle `gw`, SAMASTA kentasta jota
    /fpl renderoi. Tuplakierros (kaksi ottelua) tai puuttuva data -> ei
    arvoa -> ei todistetta. Puuttuva tiedosto -> tyhja."""
    if gw is None:
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, float] = {}
    for t in doc.get("teams") or []:
        fx = [f for f in (t.get("fixtures") or [])
              if f.get("gw") == gw and f.get("cs_pct") is not None]
        if len(fx) == 1 and t.get("short"):
            out[str(t["short"])] = float(fx[0]["cs_pct"])
    return out


def previous_season_label(meta: dict | None) -> str | None:
    """'2026/27' -> '2025/26'. None jos kautta ei voi johtaa (ei arvausta)."""
    s = str((meta or {}).get("season") or "")
    if len(s) == 7 and s[4] == "/" and s[:4].isdigit():
        y = int(s[:4])
        return f"{y - 1}/{str(y)[2:]}"
    return None


def fact_text(player: dict, team_cs: dict[str, float] | None = None,
              prev_season: str | None = None) -> str:
    """Yhden rivin todiste tai tyhja.

    "on penalties, corners" | "ARS 51% clean sheet chance" |
    "0.57 xGI/90 in 2025/26".
    """
    if not isinstance(player, dict):
        return ""
    facts = driver_facts(player)
    sp = facts.get("set_pieces")
    if sp:
        return "on " + str(sp).lower()
    pos = str(player.get("pos") or "").upper()
    if pos in ("GKP", "DEF"):
        short = str(player.get("team_short") or "")
        cs = (team_cs or {}).get(short)
        if cs is not None:
            # Sama muotoilija kuin /fpl#clean-sheets-taulukossa: "38.6%", ei "39%".
            return f"{short} {fmt_pct(cs)} clean sheet chance"
        return ""
    if pos in ("MID", "FWD") and prev_season:
        xgi = ((player.get("last_season") or {}).get("per90") or {}).get("xgi")
        if isinstance(xgi, (int, float)) and xgi >= XGI_MIN:
            return f"{float(xgi):.2f} xGI/90 in {prev_season}"
    return ""


def fact_context(xp_doc: dict) -> dict:
    """Sivun ja kortin yhteinen konteksti yhdesta xP-artefaktista."""
    meta = xp_doc.get("meta") or {}
    # Kierros samalta lukijalta kuin jakopinnat (fpl_gameweek): mihin voi
    # viela vaikuttaa, ei metan raaka kierroskentta.
    return {"team_cs": load_team_cs(actionable_gameweek(meta)),
            "prev_season": previous_season_label(meta)}


def card_sub(player: dict, ctx: dict) -> str | None:
    """Kortin alarivi: "88 xMins  ·  on penalties". Sama todiste kuin sivulla."""
    osat = []
    xm = player.get("xmins")
    if isinstance(xm, (int, float)):
        osat.append(f"{xm:.0f} xMins")
    t = fact_text(player, ctx.get("team_cs"), ctx.get("prev_season"))
    if t:
        osat.append(t)
    return "  ·  ".join(osat) if osat else None
