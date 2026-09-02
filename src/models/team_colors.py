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
    # 21.8 kit-kuviot: FUL/LEE pelaavat valkoisessa (sama peruste kuin TOT).
    "FUL": ("#FFFFFF", "#000000"), "HUL": ("#F0A800", "#000000"),
    "IPS": ("#4172B5", "#FFFFFF"), "LEE": ("#FFFFFF", "#1D428A"),
    "LEI": ("#003090", "#FFFFFF"), "LIV": ("#C8102E", "#FFFFFF"),
    "MCI": ("#6CABDD", "#FFFFFF"), "MUN": ("#DA291C", "#FFFFFF"),
    "NEW": ("#241F20", "#FFFFFF"), "NFO": ("#DD0000", "#FFFFFF"),
    "SHU": ("#EE2737", "#FFFFFF"), "SOU": ("#D71920", "#FFFFFF"),
    # 31.7 (Villen havainto, teamColors.ts): Spursin identiteetti on VALKOINEN
    # paita, navy on detaljivari -- navy-paita luki "sininen joukkue". Tama
    # kopio jai navyksi 17.8-siirrossa asti = sivut ja SPA nayttivat Spursin
    # eri varisena, tasan se "kaksi totuutta" -vika jota docstring varoittaa.
    "SUN": ("#EB172B", "#FFFFFF"), "TOT": ("#FFFFFF", "#132257"),
    "WHU": ("#7A263A", "#FFFFFF"), "WOL": ("#FDB913", "#231F20"),
}

# Sama siluetti kuin TeamKit.svelte / TeamKit.tsx (1:1).
# 2.9 PAITAPAIVITYS (Villen tilaus): realistisempi siluetti — leveammat
# olkapaat, kapeneva runko, hihansuut omina paneeleina, syvempi kaulus.
# Rintaan GOALIQ-merkki sponsorin paikalle (renderoijat >= 40 px).
_JERSEY = ("M 31 14 L 40 10 C 44 20 56 20 60 10 L 69 14 L 88 26 L 82 44 L 69 39 "
           "L 70 88 Q 70 92 66 92 L 34 92 Q 30 92 30 88 L 31 39 L 18 44 L 12 26 Z")
_SLEEVE_L = "M 31 14 L 12 26 L 18 44 L 31 39 Z"
_SLEEVE_R = "M 69 14 L 88 26 L 82 44 L 69 39 Z"
_CUFF_L = "M 12 26 L 18 44 L 21.8 42.7 L 15.8 24.7 Z"
_CUFF_R = "M 88 26 L 82 44 L 78.2 42.7 L 84.2 24.7 Z"
# KIT-KUVIOT 21.8: kaulus (paantien kaari viivana) + kuratoitu kuviotaulu.
# PEILI jaetusta teamKits.ts:sta (goaliq-app lib/teamKits.ts = web/pro-spa/
# src/lib/teamKits.ts, sanatarkasti sama tiedosto molemmissa) — jos muutat
# jotain naista, muuta kaikki kolme samassa yhteydessa, muuten sama joukkue
# saa eri paidan eri pinnalta. IP-raja: EI kresteja/sponsoreita/valmistaja-
# logoja; kuviotyypit ovat paidan yleista muotokielta, eivat trade dressia.
_COLLAR = "M 40 10 C 44 20 56 20 60 10"

#: short -> (pattern, secondary). Puuttuva rivi = solid ilman kakkosvaria.
_KIT_BY_SHORT = {
    # Premier League
    "ARS": ("sleeves", "#FFFFFF"), "AVL": ("sleeves", "#94BEE5"),
    "BOU": ("stripes", "#000000"), "BRE": ("stripes", "#FFFFFF"),
    "BHA": ("stripes", "#FFFFFF"), "BUR": ("sleeves", "#99D6EA"),
    "CHE": ("solid", "#FFFFFF"), "COV": ("solid", "#FFFFFF"),
    "CRY": ("stripes", "#C4122E"), "EVE": ("solid", "#FFFFFF"),
    "FUL": ("solid", "#000000"), "HUL": ("stripes", "#000000"),
    "IPS": ("sleeves", "#FFFFFF"), "LEE": ("solid", "#1D428A"),
    "LIV": ("solid", "#FFFFFF"), "MCI": ("solid", "#1C2C5B"),
    "MUN": ("solid", "#FFFFFF"), "NFO": ("solid", "#FFFFFF"),
    "NEW": ("stripes", "#FFFFFF"), "SHU": ("stripes", "#FFFFFF"),
    "SOU": ("stripes", "#FFFFFF"), "SUN": ("stripes", "#FFFFFF"),
    "TOT": ("solid", "#132257"), "WHU": ("sleeves", "#7AC5E8"),
    "WOL": ("solid", "#231F20"),
    # La Liga
    "ATH": ("stripes", "#FFFFFF"), "ATM": ("stripes", "#FFFFFF"),
    "BAR": ("stripes", "#004D98"), "BET": ("stripes", "#FFFFFF"),
    "GIR": ("stripes", "#FFFFFF"), "RMA": ("solid", "#00529F"),
    "RSO": ("stripes", "#FFFFFF"),
    # Serie A
    "ATA": ("stripes", "#2E6BB0"), "BOL": ("stripes", "#1B2F5B"),
    "GEN": ("halves", "#002147"), "INT": ("stripes", "#000000"),
    "JUV": ("stripes", "#FFFFFF"), "MIL": ("stripes", "#000000"),
    "UDI": ("stripes", "#FFFFFF"),
    # Ligue 1
    "ASM": ("sash", "#FFFFFF"), "LEN": ("halves", "#A8123A"),
    "PSG": ("band", "#DA291C"),
}


def _kit_layers(pattern: str) -> list:
    """Kuvion muodot rungon sisalla — peili teamKits.ts:n kitLayersista.

    'sleeves' ei tuota runkomuotoja: se tarkoittaa etta hihat maalataan
    secondary-varilla tummennetun johdoksen sijaan (renderoija lukee itse).
    """
    if pattern == "stripes":
        return [("rect", x, 0, 5, 100) for x in (38, 48, 58)]
    if pattern == "hoops":
        return [("rect", 0, y, 100, 7) for y in (25, 45, 65)]
    if pattern == "halves":
        return [("rect", 50, 0, 50, 100)]
    if pattern == "band":
        return [("rect", 44, 0, 12, 100)]
    if pattern == "sash":
        return [("path", "M 85 0 L 100 15 L 15 100 L 0 85 Z")]
    return []


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


def _cuff_color(color: str, pattern: str, secondary) -> str:
    """Hihansuun vari: kontrastihihalla runkovari, muuten kakkosvari tai
    tummennettu runko. Sama saanto TeamKit.tsx / .svelte / shareCard.ts."""
    if pattern == "sleeves":
        return color
    return secondary or _darken(color, 0.55)
