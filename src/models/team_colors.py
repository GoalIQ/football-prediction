"""Seuravarit jaettuna: sivut, kortit ja mika tahansa muu pinta.

17.8: varit asuivat `scripts/build_fpl_longtail.py`:ssa, ja jakokortti-
generaattori tarvitsi ne. Toinen kopio olisi tarkoittanut etta sivu ja kortti
voivat nayttaa saman seuran eri varisena - sama "kaksi totuutta" -vika joka on
kirjattu jo optimoijasta ja mallilupauksesta.

EI KRESTEJA EIKA SPONSOREITA. Vari + muoto riittaa tunnistamiseen, ja se on
ainoa muoto joka ei ole lisenssiriski. Sama linjaus kuin paitasiluetilla
sivuilla.
"""
from __future__ import annotations

import re

_TEAM_COLORS = {
    "ARS": ("#EF0107", "#FFFFFF"), "AVL": ("#670E36", "#FFFFFF"),
    "BOU": ("#DA291C", "#FFFFFF"), "BRE": ("#E30613", "#FFFFFF"),
    "BHA": ("#0057B8", "#FFFFFF"), "BUR": ("#6C1D45", "#FFFFFF"),
    "CHE": ("#034694", "#FFFFFF"), "COV": ("#009CD8", "#FFFFFF"),
    "CRY": ("#1B458F", "#FFFFFF"), "EVE": ("#003399", "#FFFFFF"),
    "FUL": ("#000000", "#FFFFFF"), "HUL": ("#F0A800", "#000000"),
    "IPS": ("#4172B5", "#FFFFFF"), "LEE": ("#FFCD00", "#1D428A"),
    "LEI": ("#003090", "#FFFFFF"), "LIV": ("#C8102E", "#FFFFFF"),
    "MCI": ("#6CABDD", "#FFFFFF"), "MUN": ("#DA291C", "#FFFFFF"),
    "NEW": ("#241F20", "#FFFFFF"), "NFO": ("#DD0000", "#FFFFFF"),
    "SHU": ("#EE2737", "#FFFFFF"), "SOU": ("#D71920", "#FFFFFF"),
    "SUN": ("#EB172B", "#FFFFFF"), "TOT": ("#132257", "#FFFFFF"),
    "WHU": ("#7A263A", "#FFFFFF"), "WOL": ("#FDB913", "#231F20"),
}

# Sama siluetti kuin TeamKit.svelte / TeamKit.tsx (1:1).
_JERSEY = ("M 33 15 L 43 9 C 46 15 54 15 57 9 L 67 15 L 84 27 L 76 42 L 67 36 "
           "L 67 86 Q 67 90 63 90 L 37 90 Q 33 90 33 86 L 33 36 L 24 42 L 16 27 Z")
_SLEEVE_L = "M 33 15 L 16 27 L 24 42 L 33 36 Z"
_SLEEVE_R = "M 67 15 L 84 27 L 76 42 L 67 36 Z"


def _hash_color(name: str) -> str:
    """Deterministinen fallback, peili teamColors.ts:n hashColorista."""
    h = 0
    for ch in name:
        h = (h * 31 + ord(ch)) & 0xFFFFFF
    return f"hsl({h % 360}, 45%, 32%)"


def _team_color(short: str) -> tuple[str, str]:
    hit = _TEAM_COLORS.get((short or "").upper())
    return hit if hit else (_hash_color(short or "?"), "#FFFFFF")


def _darken(hex_color: str, factor: float = 0.7) -> str:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", (hex_color or "").strip())
    if not m:
        return hex_color
    n = int(m.group(1), 16)
    parts = [max(0, round(((n >> s) & 0xFF) * factor)) for s in (16, 8, 0)]
    return "#{:02x}{:02x}{:02x}".format(*parts)
