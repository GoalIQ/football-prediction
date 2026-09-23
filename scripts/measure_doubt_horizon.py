"""XP-DOUBT-HORISONTTI: kestaako FPL:n d-lippu yli seuraavan kierroksen?

Tulos kirjattu `src/models/fpl_xp.py`:n `DOUBT_RECOVERY`-kommenttiin. Aja
uudelleen kun kautta on kulunut lisaa, ja paivita taulukko ja vakiot jos tasot
liikkuvat (otos 23.9: GW1-5, 56 d/75-lippua, 21 d/25-50-lippua).

Lahteet (ei johdettuja tiedostoja, saanto 0a):
  1. Taman repon paivittain commitoitu `data/fpl_xp_projections.json`
     (git-historia): FPL:n `status` ja `chance_next` jokaiselle pelaajalle
     (`players` + `excluded`). Jokaiselle deadlinelle viimeisin ajo ennen sita.
  2. FPL `/api/bootstrap-static/` (deadlinet).

Mittari: odotettu saatavuus FPL:n omana lukuna deadlinella n+k niille, joilla
oli d-lippu deadlinella n (a = 1, d = prosentti tai 0.5, i/s/u/n = 0), ja
vertailuna terveet (a) samoilla kierroksilla. Suhde epavarma / terve on se
taso jolla epavarman pelaajan xP:ta kerrotaan kierrokselle n+k.

    python -m scripts.measure_doubt_horizon
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTEFAKTI = "data/fpl_xp_projections.json"
UA = {"User-Agent": "Mozilla/5.0"}


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _git(*a: str) -> bytes:
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True,
                          check=True).stdout


def avail(status, chance) -> float | None:
    """FPL:n oma saatavuusluku. None = pelaaja ei ole ajossa (lahti liigasta)."""
    if status == "a":
        return 1.0
    if status == "d":
        return (chance if chance is not None else 50) / 100
    if status in ("i", "s", "u", "n"):
        return 0.0
    return None


def snapshots(ref: str = "origin/main") -> list[tuple[dt.datetime, str]]:
    out = []
    for line in _git("log", "--format=%H %cI", ref, "--", ARTEFAKTI).decode().splitlines():
        h, t = line.split()
        out.append((dt.datetime.fromisoformat(t).astimezone(dt.timezone.utc), h))
    return sorted(out)


def flags_at(sha: str) -> dict[int, tuple]:
    d = json.loads(_git("show", f"{sha}:{ARTEFAKTI}"))
    return {int(p["id"]): (p.get("status"), p.get("chance_next"))
            for p in (d.get("players") or []) + (d.get("excluded") or [])
            if p.get("id") is not None}


def deadline_flags(events: dict, snaps, now) -> dict[int, dict[int, tuple]]:
    """{gw: {pid: (status, chance)}} viimeisesta ajosta ennen kunkin deadlinea."""
    out = {}
    for n in sorted(events):
        dl = dt.datetime.fromisoformat(events[n]["deadline_time"].replace("Z", "+00:00"))
        if dl > now:
            break
        before = [s for s in snaps if s[0] < dl]
        if before:
            out[n] = flags_at(before[-1][1])
    return out


def recovery_table(flags: dict[int, dict[int, tuple]], ks=(1, 2, 3)) -> dict:
    """{(ryhma, k): (keskiarvo, n)} ryhmille d75, d25_50 ja a."""
    groups = {"d75": lambda s, c: s == "d" and c == 75,
              "d25_50": lambda s, c: s == "d" and c in (25, 50),
              "a": lambda s, c: s == "a"}
    table = {}
    for name, pick in groups.items():
        for k in ks:
            vals = []
            for n, f0 in flags.items():
                fk = flags.get(n + k)
                if fk is None:
                    continue
                for pid, (s, c) in f0.items():
                    if not pick(s, c):
                        continue
                    v = avail(*(fk.get(pid) or (None, None)))
                    if v is not None:
                        vals.append(v)
            if vals:
                table[(name, k)] = (sum(vals) / len(vals), len(vals))
    return table


def main() -> int:
    boot = _get("https://fantasy.premierleague.com/api/bootstrap-static/")
    events = {e["id"]: e for e in boot["events"]}
    now = dt.datetime.now(dt.timezone.utc)
    flags = deadline_flags(events, snapshots(), now)
    print(f"deadlinet joilla ajo ennen: GW{min(flags)}-GW{max(flags)}")
    t = recovery_table(flags)
    print(f"{'k':>3} {'d/75':>14} {'d/25+50':>14} {'a':>16} {'d75/a':>7}")
    for k in (1, 2, 3):
        d75, low, a = t.get(("d75", k)), t.get(("d25_50", k)), t.get(("a", k))
        fmt = lambda v: f"{v[0]:.3f} (n={v[1]})" if v else "-"  # noqa: E731
        rel = f"{d75[0] / a[0]:.2f}" if d75 and a else "-"
        print(f"{k:>3} {fmt(d75):>14} {fmt(low):>14} {fmt(a):>16} {rel:>7}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
