#!/usr/bin/env python3
"""Automaattinen kierrosrecap /fpl/notes-sivulle (ylläpitäjän päätös 2026-10-17).

Lisää `data/fpl_notes.json`:iin yhden muistion kierrosta kohden samaan muotoon
kuin käsin kirjoitetut (slug, date, title, paragraphs, claims, check_url, cta).
`build_fpl_longtail.py` renderöi ne.

Luvut tulevat VAIN artefakteista: `data/gw_recap.json` (mallijoukkue vs FPL:n
keskiarvo, juokseva ero, kutsut) ja `data/fpl_xp_gw_accuracy.json` comparison
(GoalIQ xP vs FPL ep_next vs form). Mitään lukua ei arvata: jos lähde puuttuu,
muistiota ei synny. Tappiot kerrotaan samalla painolla kuin voitot.

Muistio syntyy vain kun kierros on lopullisesti gradattu (ei provisional) ja
täsmälleen kerran (slug recap-gwN, idempotentti). Pohjia on kolme ja ne
vaihtuvat kierrosnumeron mukaan, jottei sama runko toistu viikosta toiseen.

Aja: python scripts/build_fpl_recap_note.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECAP_PATH = ROOT / "data" / "gw_recap.json"
ACCURACY_PATH = ROOT / "data" / "fpl_xp_gw_accuracy.json"
NOTES_PATH = ROOT / "data" / "fpl_notes.json"

BASE = "https://goaliq.app"
CHECK_URL = f"{BASE}/fpl"
CTA = "The gameweek calls and the accuracy table, free, no sign-in"

CALL_LABEL = {
    "captain_pick": "captain pick",
    "gamble": "boom-or-bust pick",
    "safest": "safest pick",
    "ceiling": "ceiling pick",
    "model_captain": "model captain",
}


def slug_for(gw: int) -> str:
    return f"recap-gw{gw}"


def is_final(gw_entry: dict) -> bool:
    """Kierros on lopullisesti gradattu: squad pisteytetty, kutsut gradattu,
    mikään osa ei ole provisional."""
    if not gw_entry or gw_entry.get("provisional"):
        return False
    squad = gw_entry.get("squad") or {}
    calls = gw_entry.get("calls") or {}
    if squad.get("points") is None or squad.get("average") is None:
        return False
    if squad.get("provisional"):
        return False
    if not calls.get("graded") or calls.get("provisional"):
        return False
    return True


def _comparison(accuracy_doc: dict, gw: int) -> dict | None:
    for g in (accuracy_doc or {}).get("gameweeks") or []:
        if g.get("gw") == gw:
            comp = g.get("comparison")
            mae = (comp or {}).get("mae") or {}
            if all(mae.get(k) is not None
                   for k in ("goaliq", "fpl_ep_next", "form_baseline")):
                return comp
    return None


def _running(recap_doc: dict, gw: int) -> tuple[int, int, int] | None:
    """(kierroksia, juokseva ero, kierroksia keskiarvon yli) kierrokseen asti."""
    rows = [r for r in ((recap_doc.get("running") or {}).get("per_gw") or [])
            if r.get("gw") is not None and r["gw"] <= gw
            and r.get("diff") is not None]
    if not rows:
        return None
    return (len(rows), sum(r["diff"] for r in rows),
            sum(1 for r in rows if r["diff"] > 0))


def _gw_phrase(n: int) -> str:
    return "gameweek" if n == 1 else "gameweeks"


def _pts(n: int) -> str:
    return f"{n} point" if abs(n) == 1 else f"{n} points"


def _signed(n: int) -> str:
    return f"+{n}" if n > 0 else str(n)


def _calls_facts(calls: dict) -> tuple[list[str], list[str], list[str]]:
    """(osuneet, huteja, nimetyt luvut) vain kutsuista joilla on tulos."""
    hits, misses, nums = [], [], []
    for c in calls.get("calls") or []:
        if c.get("call") == "model_captain" or c.get("met") is None:
            continue
        label = CALL_LABEL.get(c.get("call"), str(c.get("call")))
        pts = c.get("points")
        if pts is None or not c.get("web_name"):
            continue
        text = f"{label} {c['web_name']} ({_pts(pts)})"
        (hits if c["met"] else misses).append(text)
        nums.append(str(pts))
    return hits, misses, nums


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _result_paragraph(gw: int, squad: dict, run: tuple[int, int, int] | None,
                      tone: int) -> tuple[str, list[str]]:
    pts, avg, diff = squad["points"], squad["average"], squad["points"] - squad["average"]
    claims = [str(pts), str(avg)]
    if diff > 0:
        verdict = f"{_pts(diff)} above"
    elif diff < 0:
        verdict = f"{_pts(-diff)} below"
    else:
        verdict = "level with"
    if tone == 0:
        text = (f"Our model squad scored {pts} points in gameweek {gw}. The FPL "
                f"average was {avg}, so we finished {verdict} it."
                if diff else
                f"Our model squad scored {pts} points in gameweek {gw}, level "
                f"with the FPL average of {avg}.")
    elif tone == 1:
        text = (f"Gameweek {gw}: {pts} for the model squad against an FPL average "
                f"of {avg}, which is {verdict} the average."
                if diff else
                f"Gameweek {gw}: {pts} for the model squad against an FPL "
                f"average of {avg}, level.")
    else:
        text = (f"The average manager got {avg} in gameweek {gw}. Our model "
                f"squad got {pts}, {verdict} that."
                if diff else
                f"The average manager got {avg} in gameweek {gw}. Our model "
                f"squad got the same, {pts}.")
    if run:
        n, total, beat = run
        claims += [_signed(total), str(n)]
        text += (f" Over {n} scored {_gw_phrase(n)} the running gap to the "
                 f"average is {_signed(total)} points. We were above it in "
                 f"{beat} of the {n}.")
    return text, claims


def _calls_paragraph(calls: dict, tone: int) -> tuple[str | None, list[str]]:
    hits, misses, nums = _calls_facts(calls)
    if not hits and not misses:
        return None, []
    total = len(hits) + len(misses)
    parts = []
    if hits:
        parts.append(f"Hit: {_join(hits)}.")
    if misses:
        parts.append(f"Missed: {_join(misses)}.")
    lead = {
        0: f"Of the {total} graded calls we made before the deadline, "
           f"{len(hits)} came off and {len(misses)} did not.",
        1: f"The calls table has {total} graded rows for this gameweek: "
           f"{len(hits)} hit, {len(misses)} missed.",
        2: f"Calls first, because they are logged before the deadline: "
           f"{len(hits)} of {total} landed.",
    }[tone]
    return lead + " " + " ".join(parts), nums


def _accuracy_paragraph(comp: dict | None, tone: int) -> tuple[str | None, list[str]]:
    if not comp:
        return None, []
    mae = comp["mae"]
    g, e, f = mae["goaliq"], mae["fpl_ep_next"], mae["form_baseline"]
    n = comp.get("n")
    claims = [_num(g), _num(e), _num(f)]
    if g < min(e, f):
        verdict = "we were closest of the three"
    elif g > max(e, f):
        verdict = "we were furthest off of the three"
    else:
        verdict = "we landed between the other two"
    size = f" across {n} players" if n else ""
    if n:
        claims.append(str(n))
    text = {
        0: f"On the xP accuracy table the average miss per player{size} was "
           f"{_num(g)} points for GoalIQ, {_num(e)} for FPL's ep_next and "
           f"{_num(f)} for plain form, so {verdict}.",
        1: f"Projection error, in points per player{size}: GoalIQ {_num(g)}, "
           f"FPL ep_next {_num(e)}, form {_num(f)}. By that measure {verdict}.",
        2: f"On the same players{size}, GoalIQ's xP missed by {_num(g)} "
           f"points on average, FPL's ep_next by {_num(e)} and form by "
           f"{_num(f)}. Short version: {verdict}.",
    }[tone]
    return text, claims


def _num(x: float) -> str:
    return f"{x:.3f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


def build_note(gw_entry: dict, recap_doc: dict, accuracy_doc: dict,
               today: date) -> dict | None:
    """Yksi muistio lopullisesti gradatusta kierroksesta, tai None."""
    if not is_final(gw_entry):
        return None
    gw = gw_entry["gw"]
    tone = gw % 3
    squad = gw_entry["squad"]
    claims: list[str] = []
    paragraphs: list[str] = []

    res, c = _result_paragraph(gw, squad, _running(recap_doc, gw), tone)
    calls_p, cc = _calls_paragraph(gw_entry["calls"], tone)
    acc_p, ac = _accuracy_paragraph(_comparison(accuracy_doc, gw), tone)
    order = [(res, c), (calls_p, cc), (acc_p, ac)]
    if tone == 2 and calls_p:  # pohja 3 aloittaa kutsuista
        order = [(calls_p, cc), (res, c), (acc_p, ac)]
    elif tone == 1 and acc_p:  # pohja 2 aloittaa tarkkuudesta
        order = [(acc_p, ac), (res, c), (calls_p, cc)]
    for text, cl in order:
        if text:
            paragraphs.append(text)
            claims += cl

    seen: set[str] = set()
    claims = [x for x in claims if not (x in seen or seen.add(x))]
    if len(claims) < 3:
        return None

    diff = squad["points"] - squad["average"]
    title = {
        0: f"Gameweek {gw}: the numbers, wins and misses together",
        1: f"Gameweek {gw} recap: {squad['points']} against an average of {squad['average']}",
        2: f"What we called before gameweek {gw} and what happened",
    }[tone]
    if diff and tone == 0:
        title = (f"Gameweek {gw}: {_pts(abs(diff))} "
                 f"{'above' if diff > 0 else 'below'} the FPL average")
    return {
        "slug": slug_for(gw),
        "date": (squad.get("graded_at") or "")[:10] or today.isoformat(),
        "title": title,
        "check_url": CHECK_URL,
        "cta": CTA,
        "claims": claims,
        "paragraphs": paragraphs,
    }


def add_recaps(notes_doc: dict, recap_doc: dict, accuracy_doc: dict,
               today: date) -> list[str]:
    """Lisää puuttuvat recap-muistiot notes_dociin. Palauttaa lisätyt sluget."""
    notes = notes_doc.setdefault("notes", [])
    have = {n.get("slug") for n in notes}
    added = []
    for g in sorted((recap_doc or {}).get("gameweeks") or [],
                    key=lambda x: x.get("gw") or 0):
        if not isinstance(g.get("gw"), int) or slug_for(g["gw"]) in have:
            continue
        note = build_note(g, recap_doc, accuracy_doc, today)
        if note:
            notes.insert(0, note)
            have.add(note["slug"])
            added.append(note["slug"])
    return added


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main() -> int:
    recap, acc, notes = _load(RECAP_PATH), _load(ACCURACY_PATH), _load(NOTES_PATH)
    if not recap or not notes:
        print("recap: lähde puuttuu, ei muutoksia")
        return 0
    added = add_recaps(notes, recap, acc, date.today())
    if added:
        NOTES_PATH.write_text(
            json.dumps(notes, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    print(f"recap: lisätty {added or 'ei mitään'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
