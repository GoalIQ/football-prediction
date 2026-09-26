"""Jaetut muotoilijat: sama luku renderoityy samana joka pinnalla.

10.9.2026 (portti, XP-AJURIT k3): /fpl tulosti nollapelin `fmt_pct`:lla
(38.6%) ja ilmaissivun todiste `round()`:lla (39%) - sama kentta, kaksi
muotoilijaa, 14/18 seuralla eri merkkijono. Yksi funktio, ei kopiota.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def fmt_pct(x: float, decimals: int = 1) -> str:
    """51.0 -> "51%", 38.6 -> "38.6%". Ei pankkiiripyoristysta kokonaisluvuksi."""
    # 26.9 (julkaisutarkistaja E3): f-string pyoristaa tasapisteet parilliseen
    # (48.25 -> "48.2"), JS:n toFixed ylospain ("48.3"). SPA:n fmtPct ja sivu
    # nayttaisivat silloin eri luvun. Decimal(x) on floatin tarkka arvo, joten
    # ROUND_HALF_UP antaa saman tuloksen kuin toFixed.
    s = str(Decimal(x).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP))
    # 26.9: rstrip("0") ilman desimaalipistetta sei kokonaisluvun nollat
    # (50 -> "5%" kun decimals=0). Vain desimaaliosan nollat pois.
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s + "%"
