"""Puolustusprofiilin (/fpl/defence + jakokortti) YKSI LUKIJA (5.10.2026).

Villen havainto 5.10: GW5:n jalkeen /fpl/defence nayttaa yha 2025/26-kauden
laukausdataa ("This season's matches are not in this table for anyone yet"),
vaikka kuluvan kauden data on Understatissa. Sivu ja jakokortti lukivat
kumpikin kovakoodattua `understat_team_defence_2526.json`-tiedostoa.

Saanto: kuluva kausi kun JOKAISELLA rivilla on vahintaan MIN_CURRENT_GAMES
ottelua (sama raja kuin Leaders-sivulla ja kortin xGI:lla), muuten edellinen
kausi. Puuttuva tai vajaa kuluvan kauden artefakti EI voi tyhjentaa sivua:
lukija putoaa edelliseen kauteen, ja sivun copy kertoo kumpi on kyseessa
(`meta.complete`).
"""
from __future__ import annotations

import json
from pathlib import Path

import config
from src.models.fpl_leaders import MIN_CURRENT_GAMES


def defence_path(season: str, data_dir: Path | None = None) -> Path:
    """'2627' -> data/understat_team_defence_2627.json."""
    return (data_dir or config.DATA_DIR) / f"understat_team_defence_{season}.json"


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def current_is_usable(doc: dict | None) -> bool:
    """Kelpaako kuluvan kauden artefakti sivulle."""
    meta = (doc or {}).get("meta") or {}
    rows = (doc or {}).get("teams") or []
    if not meta.get("available") or not rows:
        return False
    # Nousija ilman dataa tarkoittaisi etta kuluvan kauden taulukosta puuttuu
    # seura jonka lukija olettaa olevan mukana.
    if meta.get("promoted_no_data"):
        return False
    return min(int(r.get("matches") or 0) for r in rows) >= MIN_CURRENT_GAMES


def load_defence(current: str | None = None,
                 data_dir: Path | None = None) -> dict | None:
    """Sivun ja kortin puolustusdata: kuluva kausi tai edellinen kausi."""
    cur_season = current or config.current_season()
    cur = _read(defence_path(cur_season, data_dir))
    if current_is_usable(cur):
        return cur
    prev_season = f"{int(cur_season[:2]) - 1:02d}{cur_season[:2]}"
    return _read(defence_path(prev_season, data_dir))


def is_season_so_far(doc: dict | None) -> bool:
    """True kun data on kesken olevalta kaudelta (copy: "so far")."""
    return ((doc or {}).get("meta") or {}).get("complete") is False
