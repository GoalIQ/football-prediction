"""EO-PUTKI-N200: elite ownership -putken ajuri CI:lle (27.9.2026).

MIKSI: `fpl_elite_ownership.py` on kaksivaiheinen (sijoitusotos kierroksen N-1
jalkeen, valinnat kierroksen N deadlinen jalkeen, ks. sen otsikko:
kehapaatelma). Vaiheet ajettiin kasin, ja GW5:n EO menetettiin: otos jai
ottamatta GW4:n jalkeen, eika sita voi enaa ottaa (FPL:n standings antaa vain
NYKYISET sijoitukset). Saanto 6a: tehdaan vaarasta vaihtoehdosta mahdoton.
Taman ajurin CI ajaa kuuden tunnin valein, ja se paattaa tilasta itse.

PAATOS (puhdas funktio `paatos`, testattu synteettisilla kauden vaiheilla):
  1. PICKS: kierroksen N deadline on mennyt, otos on kierroksen N-1 jalkeen
     ja EO-artefakti on vanhempi kuin N -> hae kierroksen N valinnat (+ elite
     managers samasta otoksesta).
  2. SNAPSHOT: kierros F on valmis JA FPL:n data tarkistettu, otos on
     vanhempi kuin F, ja kierroksen F+1 deadline on viela edessa -> ota otos.
     Jos F+1:n deadline on jo mennyt, otos olisi myohassa (kehapaatelma):
     EI oteta, vaan kerrotaan aaneen.
  3. Muuten ei tehtavaa.

Ajo: python -m scripts.fpl_elite_tick   (GITHUB_OUTPUT: action=snapshot|picks|none)
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402

SNAPSHOT_PATH = config.DATA_DIR / "fpl_rank_snapshot.json"
OWNERSHIP_PATH = config.DATA_DIR / "fpl_elite_ownership.json"


def _deadline(e: dict) -> _dt.datetime | None:
    s = e.get("deadline_time")
    if not s:
        return None
    return _dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def paatos(events: list[dict], snap_meta: dict | None, own_meta: dict | None,
           now: _dt.datetime) -> tuple[str | None, int | None, str]:
    """(toimenpide, kierros, perustelu). Toimenpide 'picks' | 'snapshot' | None."""
    dl = {int(e["id"]): _deadline(e) for e in events if e.get("id") is not None}
    alkaneet = [g for g, d in dl.items() if d is not None and d <= now]
    nykyinen = max(alkaneet) if alkaneet else None
    valmiit = [int(e["id"]) for e in events if e.get("finished") and e.get("data_checked")]
    valmis = max(valmiit) if valmiit else None
    snap_gw = (snap_meta or {}).get("rank_after_gw")
    picks_gw = (own_meta or {}).get("picks_gameweek")

    if nykyinen is not None and snap_gw == nykyinen - 1 and (picks_gw or 0) < nykyinen:
        return "picks", nykyinen, (
            f"GW{nykyinen}:n deadline mennyt, otos GW{snap_gw}:n jalkeen, EO GW{picks_gw}")
    if valmis is not None and (snap_gw or 0) < valmis:
        seuraava = dl.get(valmis + 1)
        if seuraava is not None and seuraava > now:
            return "snapshot", valmis, (
                f"GW{valmis} valmis ja tarkistettu, GW{valmis + 1}:n deadline {seuraava:%d.%m %H:%M} UTC edessa")
        if seuraava is None:
            return None, None, f"GW{valmis} on kauden viimeinen, ei seuraavaa kierrosta"
        return None, None, (
            f"MYOHASSA: GW{valmis} valmis mutta GW{valmis + 1}:n deadline on jo mennyt; "
            f"otos nyt olisi kehapaatelma, GW{valmis + 1}:n EO jaa tekematta")
    return None, None, (
        f"ei tehtavaa (nykyinen GW{nykyinen}, valmis GW{valmis}, otos GW{snap_gw}, EO GW{picks_gw})")


def _meta(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("meta")
    except (OSError, ValueError):
        return None


def _aja(*args: str) -> None:
    print("$", " ".join(args), flush=True)
    subprocess.run([sys.executable, *args], check=True)


def main() -> int:
    from src.data import fpl_api
    boot = fpl_api.fetch_bootstrap(force=True)
    now = _dt.datetime.now(_dt.timezone.utc)
    toimi, gw, syy = paatos(boot.get("events") or [], _meta(SNAPSHOT_PATH),
                            _meta(OWNERSHIP_PATH), now)
    print(f"[tick] {toimi or 'none'}: {syy}")
    if syy.startswith("MYOHASSA"):
        print(f"::warning::{syy}")
    if toimi == "snapshot":
        _aja("scripts/fpl_elite_ownership.py", "--snapshot", "--after-gw", str(gw), "--quiet")
    elif toimi == "picks":
        _aja("scripts/fpl_elite_ownership.py", "--picks", "--gw", str(gw), "--quiet")
        _aja("scripts/fpl_elite_managers.py", "--gw", str(gw), "--quiet")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"action={toimi or 'none'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
