"""Ylläpitäjän kanta Bluesky-botin raaka-aineeksi (23.10.2026, ylläpitäjän päätös).

`ask` avaa kerran kierroksessa noin 48 h ennen deadlinea issuen `Kanta GW<N>` ylläpitäjälle, `read` palauttaa
kuluvan kierroksen issuen OWNER/MEMBER-kommentit ennen deadlinea. Botti ei voi keksiä kantaa: portti
(src/marketing/bsky_gate.py) hylkää `owner_take`-aiheen, jos tässä ei ole saman kierroksen vastausta.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ISSUE_REPO = "GoalIQ/football-prediction"
ISSUE_ASSIGNEE = "Veikkoville"
ISSUE_LABEL = "kanta"
ASK_WINDOW = timedelta(hours=48)
OWNER_ASSOCIATIONS = {"OWNER", "MEMBER"}     # sama sääntö kuin .github/auto-kehitys/korjaus.py
MAX_TAKE_CHARS = 1500


def title(gw: int) -> str:
    return f"Kanta GW{gw}"


def body(gw: int) -> str:
    return (f"GW{gw}:n deadline lähestyy. Vastaa tähän sähköpostilla (vastaus tulee issueen kommenttina), "
            f"niin botti voi rakentaa yhden postauksen kantasi ympärille.\n\n"
            f"1. Kenet kapteenoit ja miksi?\n2. Missä olet eri mieltä mallin kanssa?\n"
            f"3. Mikä meni pieleen viime kierroksella?\n\n"
            f"Vain tämän kierroksen deadlinea edeltävät vastaukset otetaan mukaan.")


def hours_to_deadline(deadline: datetime, now: datetime) -> float:
    return (deadline - now).total_seconds() / 3600


def ask_due(deadline: datetime, now: datetime) -> bool:
    """Issue avataan vain, kun deadlineen on enintään 48 h eikä se ole jo mennyt."""
    return timedelta(0) < deadline - now <= ASK_WINDOW


def ask(gw: int, deadline: datetime, now: datetime, find, create) -> str:
    """`find(title)` -> olemassa oleva issue tai None; `create(payload)` -> url. Palauttaa tilan sanana."""
    if not ask_due(deadline, now):
        return "ei-aika"
    if find(title(gw)):
        return "jo-olemassa"
    create({"title": title(gw), "body": body(gw), "assignees": [ISSUE_ASSIGNEE], "labels": [ISSUE_LABEL]})
    return "luotu"


def read(gw: int, deadline: datetime, now: datetime, comments) -> list[dict]:
    """Kuluvan kierroksen ylläpitäjän kommentit. `comments`: GitHubin issue-kommenttilista (dict).
    Deadlinen jälkeen ei mitään: vanha kanta ei kuulu seuraavaan kierrokseen."""
    if now >= deadline:
        return []
    out = []
    for c in comments or []:
        if c.get("author_association") not in OWNER_ASSOCIATIONS:
            continue
        if (c.get("user") or {}).get("type") == "Bot":
            continue
        text = str(c.get("body") or "").strip()
        if not text:
            continue
        out.append({"gw": gw, "text": text[:MAX_TAKE_CHARS], "at": c.get("created_at")})
    return out


# ---------------------------------------------------------------- GitHub

def _req(url: str, token: str, data: dict | None = None):
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8") if data else None,
                                 method="POST" if data else "GET",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _find_issue(token: str, gw: int) -> dict | None:
    # Label ensin, sitten tuoreimmat ilman labelia: jos label puuttuu repossa tai pudotetaan, pelkka
    # label-haku ei loytaisi issueta ja `ask` avaisi uuden joka tunti koko 48 h ikkunan (CoS 23.10).
    for params in ({"labels": ISSUE_LABEL, "state": "all", "per_page": 30},
                   {"state": "all", "per_page": 100, "sort": "created", "direction": "desc"}):
        q = urllib.parse.urlencode(params)
        for i in _req(f"https://api.github.com/repos/{ISSUE_REPO}/issues?{q}", token):
            if i.get("title") == title(gw) and "pull_request" not in i:
                return i
    return None


def current_takes(gw: int, deadline: datetime, now: datetime, token: str | None = None) -> list[dict]:
    """Verkosta luettu kanta; virhe tai token puuttuu = ei kantaa (botti ei arvaa)."""
    token = token or os.environ.get("GH_TOKEN", "").strip()
    if not token or now >= deadline:
        return []
    try:
        issue = _find_issue(token, gw)
        if not issue:
            return []
        return read(gw, deadline, now, _req(f"{issue['comments_url']}?per_page=100", token))
    except Exception:  # noqa: BLE001
        return []


def cmd_ask(gw: int, deadline: datetime, now: datetime) -> int:
    token = os.environ.get("GH_TOKEN", "").strip()
    if not token:
        print("kanta ask: ei GH_TOKENia, ohitetaan")
        return 0
    url = f"https://api.github.com/repos/{ISSUE_REPO}/issues"
    tila = ask(gw, deadline, now, lambda t: _find_issue(token, gw),
               lambda p: _req(url, token, p))
    print(f"kanta ask GW{gw}: {tila}")
    return 0


def _module_gw_deadline() -> tuple[int, datetime]:
    import tempfile
    from pathlib import Path
    from scripts.bsky_bot import fresh_module
    mod, _values, err = fresh_module(Path(tempfile.mkdtemp(prefix="kanta_mod_")))
    if not mod:
        raise SystemExit(f"ei moduulia: {err}")
    return int(mod["gw"]), datetime.fromisoformat(str(mod["deadline_utc"]).replace("Z", "+00:00"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("ask", "read"))
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    gw, deadline = _module_gw_deadline()
    if a.cmd == "ask":
        return cmd_ask(gw, deadline, now)
    print(json.dumps(current_takes(gw, deadline, now), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
