"""XP-LOUKKAANTUMINEN-PALUU: osuuko FPL:n "Expected back <paiva>" -paiva?

Lahteet (saanto 0a): fp:n commitoitu data/fpl_xp_projections.json (git-historia,
players + excluded: status, chance_next, news) ja FPL:n bootstrap + fixtures +
element-summary. Mittarit paluupaivan jalkeiselle ensimmaiselle joukkueen
ottelulle ("paluuottelu"):
  A = FPL:n oma saatavuus paluuottelun kierroksen deadlinella (a=1, d=chance, muut 0)
  B = pelasiko (minuutit > 0) paluuottelussa
  C = pelasiko jossain kahdesta ensimmaisesta ottelusta paluupaivan jalkeen
Vertailu: pelikiellot (5/5 pelikelpoisia paluupaivana).

Tulos 24.9.2026 (GW1-5, n = 22 tapausta / ~16 pelaajaa): A 0.386, B 27 %, C 36 %;
k = 0/1/2 kierrosta paluukierroksesta A = 0.386 (n 22) / 0.45 (n 15) / 0.50 (n 11),
terveet 0.944 / 0.883 / 0.830 (measure_doubt_horizon). Paiva ei ole luotettava
kuten pelikiellon paiva. Aja uudelleen kun GW10 on pelattu (~10.11):
    python -m scripts.measure_injury_return
"""
import datetime as dt
import json
import re
import subprocess
import time
import urllib.request

from pathlib import Path
FP = str(Path(__file__).resolve().parents[1])
UA = {"User-Agent": "Mozilla/5.0"}
RE = re.compile(r"Expected back (\d{1,2}) ([A-Za-z]{3})")
KK = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def get(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read())


def git(*a):
    return subprocess.run(["git", "-C", FP, *a], capture_output=True, check=True).stdout


boot = get("https://fantasy.premierleague.com/api/bootstrap-static/")
fx = get("https://fantasy.premierleague.com/api/fixtures/")
deadlines = {e["id"]: dt.datetime.fromisoformat(e["deadline_time"].replace("Z", "+00:00")) for e in boot["events"]}
team_of = {e["id"]: e["team"] for e in boot["elements"]}
today = dt.datetime.now(dt.timezone.utc)

log = [l.split() for l in git("log", "--format=%H %cI", "--since=2026-07-25", "origin/main", "--", "data/fpl_xp_projections.json").decode().splitlines() if l.strip()]
log = sorted(((dt.datetime.fromisoformat(t).astimezone(dt.timezone.utc), h) for h, t in log))
snaps = []
step = max(1, len(log) // 120)
for t, h in log[::step]:
    try:
        d = json.loads(git("show", f"{h}:data/fpl_xp_projections.json"))
    except Exception:
        continue
    rows = {p["id"]: (p.get("status"), p.get("chance_next"), p.get("news") or "") for p in (d.get("players") or []) + (d.get("excluded") or [])}
    snaps.append((t, rows))
print("snapshots", len(snaps))


def status_at(pid, when):
    """Viimeisin snapshot ennen hetkea."""
    best = None
    for t, rows in snaps:
        if t <= when and pid in rows:
            best = rows[pid]
    return best


def avail(st):
    if not st:
        return None
    s, c, _ = st
    if s == "a":
        return 1.0
    if s == "d":
        return (c if c is not None else 50) / 100
    return 0.0


cases = {}
for t, rows in snaps:
    for pid, (s, c, n) in rows.items():
        if s not in ("i", "d"):
            continue
        m = RE.search(n)
        if not m or m.group(2).lower() not in KK:
            continue
        try:
            rd = dt.date(t.year, KK[m.group(2).lower()], int(m.group(1)))
        except ValueError:
            continue
        if rd < t.date() - dt.timedelta(days=60):
            rd = dt.date(t.year + 1, rd.month, rd.day)
        key = (pid, rd)
        if key not in cases:
            cases[key] = {"pid": pid, "status": s, "news": n, "first_seen": t, "return": rd}

rows_out = []
es_cache = {}
for (pid, rd), c in sorted(cases.items(), key=lambda x: x[1]["first_seen"]):
    tm = team_of.get(pid)
    games = sorted((dt.datetime.fromisoformat(f["kickoff_time"].replace("Z", "+00:00")), f["event"], f["id"])
                   for f in fx if f.get("kickoff_time") and f["event"] and tm in (f["team_h"], f["team_a"]))
    after = [g for g in games if g[0].date() >= rd]
    if not after or after[0][0] > today:
        continue  # paluuottelua ei ole viela pelattu
    k0, gw0, fid0 = after[0]
    if pid not in es_cache:
        try:
            es_cache[pid] = get(f"https://fantasy.premierleague.com/api/element-summary/{pid}/")["history"]
            time.sleep(0.25)
        except Exception:
            es_cache[pid] = []
    hist = {h["fixture"]: h["minutes"] for h in es_cache[pid]}
    b = hist.get(fid0)
    c2 = [hist.get(g[2]) for g in after[:2] if g[0] <= today]
    a = avail(status_at(pid, deadlines[gw0]))
    lead = (rd - c["first_seen"].date()).days
    rows_out.append({"pid": pid, "name": next((e["web_name"] for e in boot["elements"] if e["id"] == pid), pid),
                     "flag": c["status"], "news": c["news"][:60], "return": rd.isoformat(), "lead_days": lead,
                     "gw": gw0, "A_avail": a, "B_played": (b or 0) > 0 if b is not None else None,
                     "C_played2": any((x or 0) > 0 for x in c2) if c2 else None})

print("tapauksia (paluuottelu pelattu):", len(rows_out))
def mean(xs):
    xs = [x for x in xs if x is not None]
    return (round(sum(xs) / len(xs), 3), len(xs)) if xs else (None, 0)
for flag in ("i", "d"):
    r = [x for x in rows_out if x["flag"] == flag]
    print(flag, "n", len(r), "A", mean([x["A_avail"] for x in r]), "B", mean([1.0 if x["B_played"] else 0.0 for x in r if x["B_played"] is not None]),
          "C", mean([1.0 if x["C_played2"] else 0.0 for x in r if x["C_played2"] is not None]))
for lo, hi in ((0, 7), (8, 21), (22, 400)):
    r = [x for x in rows_out if x["flag"] == "i" and lo <= x["lead_days"] <= hi]
    print(f"i lead {lo}-{hi} d: n {len(r)} A {mean([x['A_avail'] for x in r])} B {mean([1.0 if x['B_played'] else 0.0 for x in r if x['B_played'] is not None])}")
for x in rows_out[:40]:
    print(x["name"], x["flag"], x["return"], "lead", x["lead_days"], "GW", x["gw"], "A", x["A_avail"], "B", x["B_played"], "C", x["C_played2"], "|", x["news"])

# k kierrosta paluukierroksen jalkeen: FPL:n saatavuus deadlinella (vain menneet deadlinet)
print("--- k-kehitys (i, paiva annettu); terveet: scripts/measure_doubt_horizon ---")
for k in (0, 1, 2):
    vals = []
    for x in rows_out:
        g = x["gw"] + k
        if g not in deadlines or deadlines[g] > today:
            continue
        v = avail(status_at(x["pid"], deadlines[g]))
        if v is not None:
            vals.append(v)
    print("k", k, "i-paivalla", mean(vals))
