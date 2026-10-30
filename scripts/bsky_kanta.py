"""Ylläpitäjän kanta Bluesky-botin raaka-aineeksi (23.10.2026, ylläpitäjän päätös).

`ask` avaa kerran kierroksessa noin 48 h ennen deadlinea issuen `Kanta GW<N>` ylläpitäjälle, `read` palauttaa
kuluvan kierroksen issuen ylläpitäjän kommentit ennen deadlinea. Botti ei voi keksiä kantaa: portti
(src/marketing/bsky_gate.py) hylkää `owner_take`-aiheen, jos tässä ei ole saman kierroksen vastausta.

24.10.2026: GW8:n issue avautui 38 min ennen deadlinea (ominaisuus mergettiin 16:39Z), ylläpitäjä vastasi
17:03Z, ja seuraava julkaisuajo oli 17:50Z eli deadlinen jälkeen: vastaus ei voinut ehtiä postaukseen, vaikka
sitä pyydettiin. Nyt issue avataan vain, kun vastaukselle jää aikaa (`MIN_ASK_LEAD`), se kertoo takarajan
(`ANSWER_LEAD` ennen deadlinea), ja tuore vastaus käynnistää aivot seuraavassa tuntiajossa (`new_take_since`).

30.10.2026: GW9:n vastaus (29.10 15:10Z) ei päässyt botille, koska `read` hyväksyi vain OWNER/MEMBER-
associationin. Ylläpitäjän jäsenyys orgissa on yksityinen, joten botin tokenilla sama kommentti on
CONTRIBUTOR, ja `current_takes` nieli tilanteen hiljaa. Sama vika korjattiin korjaus.py:ssä 21.10
kirjautumisnimellä, mutta tämä tiedosto kopioi vanhan säännön. Nyt kirjautumisnimet luetaan korjaus.py:stä
(yksi lähde, kieltoportin alla), ja jokainen luku kertoo stderriin, montako kommenttia hylättiin millä syyllä.
"""
from __future__ import annotations

import argparse
import functools
import importlib.util
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ISSUE_REPO = "GoalIQ/football-prediction"
ISSUE_ASSIGNEE = "Veikkoville"
ISSUE_LABEL = "kanta"
ASK_WINDOW = timedelta(hours=48)
# Vastaus tarvitsee tuntiajon (aivot + julkaisu, ~1 h 15 min) ja postausvälin (2 h 30 min) ennen deadlinea.
ANSWER_LEAD = timedelta(hours=3)
# Alle tämän ei kysytä lainkaan: ylläpitäjältä ei pyydetä vastausta, jota ei ehditä käyttää.
MIN_ASK_LEAD = timedelta(hours=12)
OWNER_ASSOCIATIONS = {"OWNER", "MEMBER"}     # sama sääntö kuin .github/auto-kehitys/korjaus.py
MAX_TAKE_CHARS = 1500
# Ylläpitäjän kirjautumisnimet tulevat tästä tiedostosta, ei kopiona. Se on kieltoportin alla (.github/*:
# vain ihminen), joten agentti ei voi lisätä joukkoon ketään, ja korjaus.py ajetaan sellaisenaan irrallisena
# kopiona ($RUNNER_TEMP/portit), joten se ei voi itse tuoda joukkoa muualta.
LOGIN_SOURCE = Path(__file__).resolve().parents[1] / ".github" / "auto-kehitys" / "korjaus.py"


@functools.lru_cache(maxsize=1)
def maintainer_logins() -> frozenset[str]:
    spec = importlib.util.spec_from_file_location("_korjaus_yllapitaja", LOGIN_SOURCE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return frozenset(mod.YLLAPITAJAN_LOGINIT)


def title(gw: int) -> str:
    return f"Kanta GW{gw}"


WEEKDAYS_FI = ("ma", "ti", "ke", "to", "pe", "la", "su")


def answer_by(deadline: datetime) -> datetime:
    return deadline - ANSWER_LEAD


def finnish_time(t: datetime) -> str:
    """'pe 30.10. klo 10.00 Suomen aikaa'; ilman aikavyöhyketietoa UTC (ei arvata kesäaikaa)."""
    try:
        from zoneinfo import ZoneInfo
        local, zone = t.astimezone(ZoneInfo("Europe/Helsinki")), "Suomen aikaa"
    except Exception:  # noqa: BLE001 - Windowsilla ilman tzdataa
        local, zone = t.astimezone(timezone.utc), "UTC"
    return f"{WEEKDAYS_FI[local.weekday()]} {local.day}.{local.month}. klo {local:%H.%M} {zone}"


def body(gw: int, deadline: datetime) -> str:
    return (f"GW{gw}:n deadline on {finnish_time(deadline)}. Vastaa tähän sähköpostilla (vastaus tulee issueen "
            f"kommenttina) viimeistään {finnish_time(answer_by(deadline))}, niin botti rakentaa yhden "
            f"postauksen kantasi ympärille ennen deadlinea. Vastaus käynnistää botin seuraavassa tuntiajossa.\n\n"
            f"1. Kenet kapteenoit ja miksi?\n2. Missä olet eri mieltä mallin kanssa?\n"
            f"3. Mikä meni pieleen viime kierroksella?")


def hours_to_deadline(deadline: datetime, now: datetime) -> float:
    return (deadline - now).total_seconds() / 3600


def ask_due(deadline: datetime, now: datetime) -> bool:
    """Issue avataan, kun deadlineen on enintään 48 h mutta vähintään `MIN_ASK_LEAD`: myöhemmin avattu issue
    pyytäisi vastausta, joka ei ehdi postaukseen (GW8 24.10)."""
    return MIN_ASK_LEAD <= deadline - now <= ASK_WINDOW


def ask(gw: int, deadline: datetime, now: datetime, find, create) -> str:
    """`find(title)` -> olemassa oleva issue tai None; `create(payload)` -> url. Palauttaa tilan sanana."""
    if not ask_due(deadline, now):
        return "ei-aika"
    if find(title(gw)):
        return "jo-olemassa"
    create({"title": title(gw), "body": body(gw, deadline), "assignees": [ISSUE_ASSIGNEE],
            "labels": [ISSUE_LABEL]})
    return "luotu"


def rejection(c: dict) -> str | None:
    """Miksi kommentti ei ole ylläpitäjän kanta; None = kelpaa. Ylläpitäjä tunnistetaan kirjautumisnimestä
    tai OWNER/MEMBER-associationista (sama sääntö kuin korjaus.py:n poimi_ohjeet)."""
    user = c.get("user") or {}
    if user.get("type") == "Bot":
        return "botti"
    if str(user.get("login", "")) not in maintainer_logins() \
            and c.get("author_association") not in OWNER_ASSOCIATIONS:
        return f"kirjoittaja {c.get('author_association')}"
    if not str(c.get("body") or "").strip():
        return "tyhjä"
    return None


def read(gw: int, deadline: datetime, now: datetime, comments, rejected: Counter | None = None) -> list[dict]:
    """Kuluvan kierroksen ylläpitäjän kommentit. `comments`: GitHubin issue-kommenttilista (dict).
    Deadlinen jälkeen ei mitään: vanha kanta ei kuulu seuraavaan kierrokseen. `rejected` kerää hylkäyssyyt."""
    rejected = Counter() if rejected is None else rejected
    if now >= deadline:
        rejected["deadline ohi"] += len(comments or [])
        return []
    out = []
    for c in comments or []:
        syy = rejection(c)
        if syy:
            rejected[syy] += 1
            continue
        text = str(c.get("body") or "").strip()
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
    """Verkosta luettu kanta; virhe tai token puuttuu = ei kantaa (botti ei arvaa). Tulos ja syy stderriin:
    stdoutissa voi olla JSONia (`read`), ja hiljainen tyhjä lista piilotti GW9:n vastauksen vuorokauden."""
    token = token or os.environ.get("GH_TOKEN", "").strip()
    if not token:
        return _report(gw, "ei GH_TOKENia")
    if now >= deadline:
        return _report(gw, "deadline ohi")
    try:
        issue = _find_issue(token, gw)
        if not issue:
            return _report(gw, f"issueta {title(gw)!r} ei löydy")
        comments = _req(f"{issue['comments_url']}?per_page=100", token)
        rejected: Counter = Counter()
        takes = read(gw, deadline, now, comments, rejected)
        return _report(gw, f"kommentteja {len(comments or [])}, hyväksytty {len(takes)}, "
                           f"hylätty {dict(rejected) or 0}", takes)
    except Exception as e:  # noqa: BLE001
        return _report(gw, f"virhe {e!r}"[:300])


def _report(gw: int, msg: str, takes: list[dict] | None = None) -> list[dict]:
    print(f"kanta GW{gw}: {msg}", file=sys.stderr)
    return takes or []


def new_take_since(takes: list[dict], last_think: str | None) -> bool:
    """Onko kannassa kommentti, jota aivot eivät ole vielä nähneet (kirjoitettu viimeisen aivoajon jälkeen).
    `takes` tulee `read`istä, joten deadlinen jälkeen lista on tyhjä eikä mikään käynnistä aivoja."""
    if not takes:
        return False
    if not last_think:
        return True
    seen = datetime.fromisoformat(last_think.replace("Z", "+00:00"))
    for t in takes:
        try:
            if datetime.fromisoformat(str(t.get("at")).replace("Z", "+00:00")) > seen:
                return True
        except ValueError:
            return True   # aika puuttuu: aivot ajetaan (varovainen suunta, kanta ei jää käyttämättä)
    return False


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
