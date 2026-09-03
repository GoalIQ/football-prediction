"""Entryn julkisesta historiasta johdetut tilat (3.9.2026, CHIP-EV-BUDGET).

Lahde: FPL `entry/{id}/history/` -> `current` [{event, event_transfers,
event_transfers_cost, bank, value, ...}] ja `chips` [{name, event}].
Molemmat ovat julkisia ilman kirjautumista. Kaksi johdettua lukua:

  team_value_tenths(history): kauden viimeisin `value` (FPL:n oma joukkueen
    arvo, bank mukana). Se on se raha jolla Free Hit / Wildcard -runko oikeasti
    rakennetaan - ei 100,0 m. Mitattu 3.9: entry 116920 value 999 = 99,9 m.

  infer_free_transfers(history): vapaiden siirtojen saldo seuraavalle
    kierrokselle. FPL ei julkaise saldoa, mutta se seuraa saannosta:
    kausi alkaa 1 FT:lla, joka kierroksen jalkeen +1, katto 5, tehdyt siirrot
    kuluttavat saldoa (hitit eivat vie miinukselle), ja wildcard/free hit
    -kierroksella siirrot eivat kuluta (saldo sailyy ja kertyy). Tama on
    PAATELMA julkisesta datasta, ei pelin oma luku -> vastaus merkitsee sen
    `ft_source = "inferred_from_history"`.
"""
from __future__ import annotations

FT_MAX = 5
FT_START = 1


def team_value_tenths(history: dict | None) -> int | None:
    rows = [r for r in ((history or {}).get("current") or [])
            if isinstance(r.get("value"), int) and r["value"] > 0]
    if not rows:
        return None
    return int(max(rows, key=lambda r: int(r.get("event") or 0))["value"])


def infer_free_transfers(history: dict | None) -> int | None:
    """FT-saldo seuraavalle pelaamattomalle kierrokselle, tai None jos
    historiaa ei ole."""
    rows = sorted((r for r in ((history or {}).get("current") or [])
                   if isinstance(r.get("event"), int)),
                  key=lambda r: r["event"])
    if not rows:
        return None
    chip_gws = {int(c.get("event")) for c in ((history or {}).get("chips") or [])
                if str(c.get("name")) in ("wildcard", "freehit")
                and isinstance(c.get("event"), int)}
    ft = FT_START
    for r in rows:
        made = int(r.get("event_transfers") or 0)
        if r["event"] not in chip_gws:
            ft = max(ft - made, 0)
        ft = min(FT_MAX, ft + 1)
    return ft
