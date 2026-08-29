"""xP-deadline-freeze (30.7, Villen GO): per-GW xP vs toteuma -putken osa 1.

Kun seuraavan GW:n deadline on alle FREEZE_WINDOW_H päässä, jäädytetään sen
kierroksen per-pelaaja-xP data/fpl_xp_frozen/gw{N}.json:iin. Gradaus (osa 2,
grade_fpl_xp_gw.py) vertaa jäädytettyä ennustetta toteumaan kun kierros on
ratkennut — ennuste on IMMUTABLE ennen kickoffia, sama periaate kuin
ottelulokissa ja Beat the modelissa.

Idempotentti: olemassa olevaa freezeä EI ylikirjoiteta (ennusteen vaihtaminen
jälkikäteen olisi tasan se vilppi jota koko putki torjuu).
Exit 0 myös kun ei jäädytettävää; tekninen virhe → 1.

29.8 (IDEA-2026-08-29-xp-graded-public): samaan riviin jäädytetään myös FPL:n
oma `ep_next` (bootstrap elements[].ep_next, live-only-kenttä jota API ei
arkistoi) ja FPL:n `form`-luku baselineksi. Bootstrap haetaan samalla
fetcherillä kuin projektio (src/data/fpl_api.fetch_bootstrap), joten ep_next
on samasta hetkestä kuin xP eikä toisesta hausta. Gradaus vertaa kolmea
lukua samalla rivijoukolla (grade_fpl_xp_gw + src/models/fpl_xp_accuracy).
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from src.data import fpl_api

XP_PATH = config.PROJECT_ROOT / "data" / "fpl_xp_projections.json"
FROZEN_DIR = config.PROJECT_ROOT / "data" / "fpl_xp_frozen"
FREEZE_WINDOW_H = 30   # päivittäinen cron ehtii aina väliin


def _num(v) -> float | None:
    """FPL antaa ep_next/form merkkijonoina ("4.5"). Puuttuva -> None, ei 0:
    gradaus ohittaa rivin vertailusta eikä väitä FPL:n ennustaneen nollaa."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fpl_reference_by_id(boot: dict) -> dict[int, dict]:
    """{element_id: {ep_next, form}} bootstrapista."""
    out = {}
    for el in (boot or {}).get("elements") or []:
        try:
            out[int(el["id"])] = {"ep_next": _num(el.get("ep_next")),
                                  "form": _num(el.get("form"))}
        except (KeyError, TypeError, ValueError):
            continue
    return out


def slim_rows(xp: dict, gw: int, ref: dict[int, dict] | None = None) -> list[dict]:
    """Puhdas ydin: projektiosta kierroksen {gw} slim-rivit.

    `ref` = fpl_reference_by_id(bootstrap): rivi saa ep_next + form samasta
    hetkestä. Ilman refiä (vanha kutsu) kentät jäävät pois eikä gradaus
    tee vertailua sille kierrokselle."""
    rows = []
    for p in xp.get("players") or []:
        g = next((x for x in p.get("gameweeks") or [] if x.get("gw") == gw), None)
        if g is None:
            continue
        row = {"id": p["id"], "web_name": p.get("web_name"),
               "team_short": p.get("team_short"), "pos": p.get("pos"),
               "price": p.get("price"), "xmins": p.get("xmins"),
               "xp": g.get("xp")}
        if ref is not None:
            r = ref.get(int(p["id"])) or {}
            row["ep_next"] = r.get("ep_next")
            row["form"] = r.get("form")
        rows.append(row)
    return rows


def main() -> int:
    try:
        boot = fpl_api.fetch_bootstrap()
        events = boot.get("events") or []
    except Exception as e:
        print(f"VIRHE: bootstrap-haku epäonnistui: {e!r}")
        return 1
    now = _dt.datetime.now(_dt.timezone.utc)
    nxt = None
    for ev in events:
        if ev.get("finished"):
            continue
        dl = _dt.datetime.fromisoformat(
            str(ev.get("deadline_time", "")).replace("Z", "+00:00"))
        if dl > now and (dl - now) <= _dt.timedelta(hours=FREEZE_WINDOW_H):
            nxt = (int(ev["id"]), dl)
            break
    if nxt is None:
        print("Ei deadlinea freeze-ikkunassa — ei jäädytettävää.")
        return 0
    gw, dl = nxt
    out = FROZEN_DIR / f"gw{gw}.json"
    if out.exists():
        print(f"GW{gw} on jo jäädytetty — ei ylikirjoiteta (immutable).")
        return 0
    if not XP_PATH.exists():
        print("VIRHE: xP-projektiota ei ole.")
        return 1
    xp = json.loads(XP_PATH.read_text(encoding="utf-8"))
    ref = fpl_reference_by_id(boot)
    rows = slim_rows(xp, gw, ref)
    if len(rows) < 200:
        print(f"VIRHE: vain {len(rows)} riviä GW{gw}:lle — ei jäädytetä.")
        return 1
    n_ep = sum(1 for r in rows if r.get("ep_next") is not None)
    if n_ep < len(rows) * 0.9:
        # ep_next puuttuu laajasti -> bootstrap on outo (kausi ei alkanut,
        # kenttä tyhjä). Freeze tehdään silti (xP on pääasia), mutta luku
        # näkyy lokissa eikä hiljaa "vertailu n=0":na.
        print(f"VAROITUS: ep_next vain {n_ep}/{len(rows)} riville.")
    FROZEN_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "meta": {"gw": gw, "deadline": dl.strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "frozen_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "projection_generated_at": xp.get("meta", {}).get("generated_at"),
                 "n_players": len(rows),
                 "n_ep_next": n_ep,
                 "fpl_reference": ("ep_next and form from the same FPL "
                                   "bootstrap-static as the projection, "
                                   "frozen at frozen_at")},
        "players": rows,
    }, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"OK: GW{gw} jäädytetty ({len(rows)} pelaajaa, deadline {dl}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
