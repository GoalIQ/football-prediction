"""Jaetut muotoilijat: sama luku renderoityy samana joka pinnalla.

10.9.2026 (portti, XP-AJURIT k3): /fpl tulosti nollapelin `fmt_pct`:lla
(38.6%) ja ilmaissivun todiste `round()`:lla (39%) - sama kentta, kaksi
muotoilijaa, 14/18 seuralla eri merkkijono. Yksi funktio, ei kopiota.
"""
from __future__ import annotations


def fmt_pct(x: float, decimals: int = 1) -> str:
    """51.0 -> "51%", 38.6 -> "38.6%". Ei pankkiiripyoristysta kokonaisluvuksi."""
    return f"{x:.{decimals}f}".rstrip("0").rstrip(".") + "%"
