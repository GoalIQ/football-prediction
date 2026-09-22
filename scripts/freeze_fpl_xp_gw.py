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

22.9 (D5, track record vs FPL:n oma projektio): ep_next kirjataan
deadline-arvoksi VAIN kun se todistetusti on sitä (fpl_reference_gate):
  * hakuhetki (fpl_api.bootstrap_fetched_at, välimuistin mtime) on ennen
    deadlinea — fetch_bootstrap voi palauttaa tunnin vanhan välimuistin, joten
    kutsuhetki ei ole hakuhetki, ja
  * bootstrapin is_next-kierros on jäädytettävä kierros. ep_next viittaa aina
    FPL:n is_next-kierrokseen: deadlinen jälkeen se on jo SEURAAVAN kierroksen
    luku (ja ep_this on deadlinen jälkeen päivittyvä luku), joten kumpikaan
    ei ole kierroksen N deadline-arvo.
Jos portti ei aukea, xP jäädytetään silti (pääasia) mutta ep_next/form jäävät
pois ja meta.fpl_reference_status kertoo syyn. Gradaus lukee ep_next:n vain
src/models/fpl_xp_accuracy.frozen_players():n kautta, joka tarkistaa saman.
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from src.data import fpl_api
from src.models import fpl_xp_accuracy as xacc

XP_PATH = config.PROJECT_ROOT / "data" / "fpl_xp_projections.json"
FROZEN_DIR = config.PROJECT_ROOT / "data" / "fpl_xp_frozen"
FREEZE_WINDOW_H = 30   # päivittäinen cron ehtii aina väliin

_ISO = "%Y-%m-%dT%H:%M:%SZ"


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


def _deadline(ev: dict) -> _dt.datetime | None:
    try:
        return _dt.datetime.fromisoformat(
            str(ev.get("deadline_time", "")).replace("Z", "+00:00"))
    except ValueError:
        return None


def pick_freeze_target(events: list[dict], now: _dt.datetime,
                       window_h: float = FREEZE_WINDOW_H
                       ) -> tuple[int, _dt.datetime] | None:
    """Ensimmäinen ratkeamaton kierros jonka deadline on TULEVAISUUDESSA ja
    alle window_h:n päässä. Deadlinen jälkeen kierrosta ei valita koskaan:
    jäädytys ei voi kirjoittaa kierrokselle arvoa joka haettiin sen
    deadlinen jälkeen."""
    for ev in events or []:
        if ev.get("finished"):
            continue
        dl = _deadline(ev)
        if dl is None:
            continue
        if dl > now and (dl - now) <= _dt.timedelta(hours=window_h):
            return int(ev["id"]), dl
    return None


def ep_next_gw(events: list[dict]) -> int | None:
    """Kierros johon bootstrapin ep_next viittaa: FPL:n is_next-event."""
    for ev in events or []:
        if ev.get("is_next"):
            try:
                return int(ev["id"])
            except (KeyError, TypeError, ValueError):
                return None
    return None


def fpl_reference_gate(events: list[dict], gw: int, deadline: _dt.datetime,
                       fetched_at: _dt.datetime | None) -> str:
    """xacc.REF_OK vain kun bootstrapin ep_next on kierroksen gw
    deadline-arvo. Muuten syykoodi (xacc.REF_*), joka kirjataan metaan."""
    if fetched_at is None:
        return xacc.REF_FETCH_TIME_UNKNOWN
    if fetched_at >= deadline:
        return xacc.REF_FETCHED_AFTER_DEADLINE
    if ep_next_gw(events) != int(gw):
        return xacc.REF_OTHER_GW
    return xacc.REF_OK


def build_frozen(xp: dict, boot: dict, now: _dt.datetime,
                 fetched_at: _dt.datetime | None) -> dict | None:
    """Puhdas ydin: jäädytettävä dokumentti tai None jos ikkunassa ei ole
    kierrosta. Ei IO:ta; main() hoitaa haun, idempotenssin ja kirjoituksen."""
    events = (boot or {}).get("events") or []
    target = pick_freeze_target(events, now)
    if target is None:
        return None
    gw, dl = target
    status = fpl_reference_gate(events, gw, dl, fetched_at)
    ref = fpl_reference_by_id(boot) if status == xacc.REF_OK else None
    rows = slim_rows(xp, gw, ref)
    fetched_txt = (fetched_at.astimezone(_dt.timezone.utc).strftime(_ISO)
                   if fetched_at else None)
    meta = {"gw": gw, "deadline": dl.strftime(_ISO),
            "frozen_at": now.strftime(_ISO),
            "projection_generated_at": xp.get("meta", {}).get("generated_at"),
            "n_players": len(rows),
            "n_ep_next": sum(1 for r in rows if r.get("ep_next") is not None),
            "fpl_reference_status": status,
            "fpl_reference_fetched_at": fetched_txt,
            "ep_next_gw": ep_next_gw(events)}
    if status == xacc.REF_OK:
        meta["fpl_reference"] = ("ep_next and form from the same FPL "
                                 "bootstrap-static as the projection, "
                                 "fetched at fpl_reference_fetched_at")
    return {"meta": meta, "players": rows}


def main(now: _dt.datetime | None = None) -> int:
    """`now` vain testeille (vaihetestit kutsupaikan kautta); ajossa None."""
    try:
        boot = fpl_api.fetch_bootstrap()
        fetched_at = fpl_api.bootstrap_fetched_at()
    except Exception as e:
        print(f"VIRHE: bootstrap-haku epäonnistui: {e!r}")
        return 1
    if now is None:
        now = _dt.datetime.now(_dt.timezone.utc)
    target = pick_freeze_target(boot.get("events") or [], now)
    if target is None:
        print("Ei deadlinea freeze-ikkunassa — ei jäädytettävää.")
        return 0
    gw, dl = target
    out = FROZEN_DIR / f"gw{gw}.json"
    if out.exists():
        print(f"GW{gw} on jo jäädytetty — ei ylikirjoiteta (immutable).")
        return 0
    if not XP_PATH.exists():
        print("VIRHE: xP-projektiota ei ole.")
        return 1
    xp = json.loads(XP_PATH.read_text(encoding="utf-8"))
    doc = build_frozen(xp, boot, now, fetched_at)
    if doc is None:   # sama target kuin yllä; ei hiljaista None-kirjoitusta
        print("Ei deadlinea freeze-ikkunassa — ei jäädytettävää.")
        return 0
    meta, rows = doc["meta"], doc["players"]
    if len(rows) < 200:
        print(f"VIRHE: vain {len(rows)} riviä GW{gw}:lle — ei jäädytetä.")
        return 1
    if meta["fpl_reference_status"] != xacc.REF_OK:
        # xP jäädytetään silti (pääasia), mutta FPL-vertailu jää tältä
        # kierrokselta pois ja syy näkyy lokissa ja metassa.
        print(f"VAROITUS: ep_next ei ole GW{gw}:n deadline-arvo "
              f"({meta['fpl_reference_status']}, haettu "
              f"{meta['fpl_reference_fetched_at']}, is_next "
              f"{meta['ep_next_gw']}) — jäädytetään ilman FPL-referenssiä.")
    elif meta["n_ep_next"] < len(rows) * 0.9:
        # ep_next puuttuu laajasti -> bootstrap on outo (kausi ei alkanut,
        # kenttä tyhjä). Freeze tehdään silti (xP on pääasia), mutta luku
        # näkyy lokissa eikä hiljaa "vertailu n=0":na.
        print(f"VAROITUS: ep_next vain {meta['n_ep_next']}/{len(rows)} riville.")
    FROZEN_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n",
                   encoding="utf-8")
    print(f"OK: GW{gw} jäädytetty ({len(rows)} pelaajaa, deadline {dl}, "
          f"ep_next {meta['n_ep_next']} riviä, haettu "
          f"{meta['fpl_reference_fetched_at']}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
