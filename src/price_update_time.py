"""FPL:n hintapaivityksen hetki lukijalle, jonka aikavyohyketta palvelin ei tieda.

26.9.2026 (PRICE-ETA-PALVELINSIVUT, julkaisutarkistaja B1-B2): hubin
/fpl/price-changes ja GW review -lause sanoivat "tonight" / "within a day"
`eta_days`-offsetista. FPL paivittaa 23:00Z, joka on Aasiassa aamu, ja offset 1
on aina 24-48 h paassa. YKSI muotoilija molemmille pinnoille (saanto 6a):
absoluuttinen hetki `eta_at`:sta UK-aikana, ja mennyt tai puuttuva hetki ei
tuota aikalausetta lainkaan (sama saanto kuin SPA:n ja mobiilin lib/priceEta).
"""
from __future__ import annotations

from datetime import datetime, timezone


def _uk():
    # Ladataan vasta kutsussa: jos ymparistosta puuttuu tz-data, vain
    # aikalause jaa pois (fail-closed), eika koko moduuli tai API kaadu.
    from zoneinfo import ZoneInfo
    return ZoneInfo("Europe/London")


def price_update_parts(eta_at: object, now: datetime | None = None) -> tuple[str, str] | None:
    """("Sun 27 Sep", "00:00") UK-aikana, tai None jos hetki puuttuu, on
    virheellinen, ilman aikavyohyketta tai jo mennyt."""
    if not isinstance(eta_at, str) or not eta_at:
        return None
    try:
        t = datetime.fromisoformat(eta_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        return None
    if t <= (now or datetime.now(timezone.utc)):
        return None
    try:
        u = t.astimezone(_uk())
    except Exception:
        return None
    return f"{u:%a} {u.day} {u:%b}", f"{u:%H:%M}"
