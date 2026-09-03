"""FPL-chippien saatavuus (3.9.2026, CHIP-EV-CHIPS-USED).

Kaksi faktaa joita chip-EV ja wildcard-plan eivat aiemmin tienneet:
  1. Kaudella 2026/27 jokainen chip on kaytettavissa KAHDESTI, kerran per
     kauden puolikas. Lahde: bootstrap-static `chips` (3.9: wildcard/freehit
     start 2 stop 19 ja 20-38; bboost/3xc 1-19 ja 20-38). Ikkunat luetaan
     bootstrapista, ei kovakoodata - FPL voi muuttaa rajaa.
  2. Entryn jo pelaamat chipit ovat `entry/{id}/history/` -> `chips`
     [{name, event}]. Pelattu chip ei ole enaa tarjolla samalla puolikkaalla.
     Mitattu 3.9: entry 116920 pelasi wildcardin GW2:ssa ja chip-EV ehdotti
     silti wildcard-ikkunaa GW3:lle.

Puhtaita funktioita, ei verkkoa. Nimikartta FPL -> API-avain:
  wildcard->wc, freehit->fh, bboost->bb, 3xc->tc.
"""
from __future__ import annotations

CHIP_KEY = {"wildcard": "wc", "freehit": "fh", "bboost": "bb", "3xc": "tc"}
CHIP_LABEL = {"wc": "Wildcard", "fh": "Free Hit", "bb": "Bench Boost",
              "tc": "Triple Captain"}
# Fallback vain jos bootstrapissa ei ole `chips`-listaa (vanha cache):
# yksi ikkuna koko kaudelle = vanha kaytos.
_FALLBACK_WINDOWS = [(1, 38)]


def chip_windows(bootstrap: dict | None) -> dict[str, list[tuple[int, int]]]:
    """{chip_key: [(start_gw, stop_gw), ...]} bootstrapin `chips`-listasta,
    ikkunat nousevassa jarjestyksessa. Tuntemattomat nimet ohitetaan."""
    out: dict[str, list[tuple[int, int]]] = {}
    for c in ((bootstrap or {}).get("chips") or []):
        key = CHIP_KEY.get(str(c.get("name") or ""))
        if key is None:
            continue
        try:
            start, stop = int(c.get("start_event")), int(c.get("stop_event"))
        except (TypeError, ValueError):
            continue
        out.setdefault(key, []).append((start, stop))
    for key in CHIP_KEY.values():
        out.setdefault(key, list(_FALLBACK_WINDOWS))
        out[key].sort()
    return out


def played_chips(history: dict | None) -> dict[str, list[int]]:
    """{chip_key: [gw, ...]} entryn history.chips-listasta."""
    out: dict[str, list[int]] = {}
    for c in ((history or {}).get("chips") or []):
        key = CHIP_KEY.get(str(c.get("name") or ""))
        try:
            gw = int(c.get("event"))
        except (TypeError, ValueError):
            continue
        if key is not None:
            out.setdefault(key, []).append(gw)
    return out


def chip_state(bootstrap: dict | None, history: dict | None,
               current_gw: int) -> dict[str, dict]:
    """Per chip: ikkunat, mika niista on pelattu, ja mitka GW:t ovat viela
    tarjolla. `current_gw` = seuraava pelattava kierros (actionable)."""
    windows = chip_windows(bootstrap)
    played = played_chips(history)
    state: dict[str, dict] = {}
    for key, wins in windows.items():
        rows = []
        for i, (start, stop) in enumerate(wins, start=1):
            used = [g for g in played.get(key, []) if start <= g <= stop]
            rows.append({
                "half": i, "start_gw": start, "stop_gw": stop,
                "played_gw": used[0] if used else None,
                # tarjolla jos ei pelattu JA ikkuna ei ole jo kokonaan takana
                "available": not used and stop >= current_gw,
            })
        state[key] = {
            "label": CHIP_LABEL[key],
            "windows": rows,
            "played_gws": sorted(played.get(key, [])),
            "available_now": any(
                r["available"] and r["start_gw"] <= current_gw <= r["stop_gw"]
                for r in rows),
        }
    return state


def gw_allowed(state: dict[str, dict], key: str, gw: int) -> bool:
    """Saako chipin `key` pelata kierroksella `gw` taman entryn tilassa."""
    for r in (state.get(key) or {}).get("windows") or []:
        if r["start_gw"] <= gw <= r["stop_gw"]:
            return bool(r["available"])
    return False


def next_available_window(state: dict[str, dict], key: str,
                          current_gw: int) -> dict | None:
    for r in (state.get(key) or {}).get("windows") or []:
        if r["available"] and r["stop_gw"] >= current_gw:
            return r
    return None
