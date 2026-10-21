#!/usr/bin/env python3
"""Automaattinen kierrosrecap /fpl/notes-sivulle (ylläpitäjän päätös 2026-10-17).

Lisää `data/fpl_notes.json`:iin yhden muistion kierrosta kohden samaan muotoon
kuin käsin kirjoitetut (slug, date, title, paragraphs, claims, check_url, cta).
`build_fpl_longtail.py` renderöi ne.

Luvut tulevat VAIN artefakteista ja vain sellaisina kuin ne näkyvät ilmaisella
/fpl-sivulla: `data/gw_recap.json` (kutsut) ja `data/fpl_xp_gw_accuracy.json` comparison
(GoalIQ xP vs FPL ep_next vs form). Mitään lukua ei arvata: jos lähde puuttuu,
muistiota ei synny. Tappiot kerrotaan samalla painolla kuin voitot.

Muistio syntyy vain kun kierros on lopullisesti gradattu (ei provisional),
täsmälleen kerran (slug recap-gwN, idempotentti) ja vain kierroksesta
ENSIMMAINEN_RECAP_GW alkaen. Pohjia on kolme ja ne
vaihtuvat kierrosnumeron mukaan, jottei sama runko toistu viikosta toiseen.

Aja: python scripts/build_fpl_recap_note.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import publish_gate  # noqa: E402
from src.models.fpl_gw_xp import excluded  # noqa: E402

RECAP_PATH = ROOT / "data" / "gw_recap.json"
ACCURACY_PATH = ROOT / "data" / "fpl_xp_gw_accuracy.json"
NOTES_PATH = ROOT / "data" / "fpl_notes.json"

BASE = "https://goaliq.app"
CHECK_URL = f"{BASE}/fpl"
CTA = "The gameweek calls and the accuracy table, free, no sign-in"

#: Ei takautuvia muistioita (ylläpitäjän ohje 21.10): ensimmäinen ajo lisäisi muuten
#: viisi samanrunkoista muistiota kerralla (GW2-GW7), ja uudelleengradattu GW2 saisi
#: päiväyksen 21.9. Recap alkaa kierroksesta, joka oli uusin gradattu käyttöönotossa.
ENSIMMAINEN_RECAP_GW = 7

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


def _pts(n: int) -> str:
    return f"{n} point" if abs(n) == 1 else f"{n} points"


_COUNT = {0: "none", 1: "one", 2: "two", 3: "three", 4: "four"}

#: Sarakkeiden nimet kuten /fpl#xp-accuracy-taulukon otsikoissa, jotta lukija
#: löytää jokaisen termin taulukosta.
EP_NEXT, FORM = "FPL ep_next", "FPL form"


def _count(n: int) -> str:
    return _COUNT.get(n, str(n))


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


#: Weekly standouts card -nostot. Muut rivit (model_captain, projected_xi,
#: tulevat lajit) eivät kuulu laskuriin.
STANDOUT = ("captain_pick", "ceiling", "safest", "gamble")


def _calls_facts(calls: dict) -> tuple[list[tuple[str, str, int]],
                                       list[tuple[str, str, int]], list[str], bool]:
    """(osuneet, huteja, nimetyt luvut, vajaa) standout-nostoista.
    Rivi = (nimilappu, pelaaja, pisteet); muotoilu tehdään pohjakohtaisesti,
    jottei sama 'Hit: ... Missed: ...' -runko toistu joka muistiossa.
    vajaa = jokin standout-rivi on taulukossa ilman tulosta, jolloin tekstin
    lukumäärä ei täsmäisi taulukon rivien kanssa."""
    hits, misses, nums, vajaa = [], [], [], False
    for c in calls.get("calls") or []:
        if c.get("call") not in STANDOUT:
            continue
        pts = c.get("points")
        if c.get("met") is None or pts is None or not c.get("web_name"):
            vajaa = True
            continue
        label = CALL_LABEL[c["call"]]
        (hits if c["met"] else misses).append((label, c["web_name"], pts))
        nums.append(str(pts))
    return hits, misses, nums, vajaa


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _items(rows: list[tuple[str, str, int]], tone: int) -> str:
    out = []
    for i, (label, name, pts) in enumerate(rows):
        if tone == 0:
            out.append(f"{label} {name} ({_pts(pts)})")
        elif tone == 1:
            out.append(f"{label} {name} on {pts}")
        else:
            out.append(f"{label} {name} with {_pts(pts) if i == 0 else pts}")
    return _join(out)


def _calls_paragraph(calls: dict, tone: int) -> tuple[str | None, list[str]]:
    """Osumat ja hudit samalla painolla. Lukumäärät sanoina; kaikki osuivat /
    kaikki hutivat saavat oman lauseen ("4 of our 4" ja "0 didn't" eivät synny).
    Alle kaksi pisteytettyä nostoa -> ei kappaletta.

    Nimiesto fail-closed: loki (gw_calls) ei suodata nimiä tarkoituksella, mutta
    muistio on julkaisu kuten X-ketju, joten sama estolista kuin korteilla
    (EXCLUDED_NAMES + scripts/publish_blocklist.json). Estetty nimi -> ei
    kutsukappaletta lainkaan, jottei luku "four" ja nimetyt nostot eroa."""
    hits, misses, nums, vajaa = _calls_facts(calls)
    if vajaa or len(hits) + len(misses) < 2:
        return None, []
    estolista = publish_gate.load_blocklist()
    if any(excluded(name, estolista) for _, name, _ in hits + misses):
        return None, []
    t, h, m = _count(len(hits) + len(misses)), _count(len(hits)), _count(len(misses))
    hs, ms = _items(hits, tone), _items(misses, tone)
    if tone == 0:
        picks = "standout picks we made before the deadline"
        if not misses:
            return f"All {t} {picks} came off: {hs}.", nums
        if not hits:
            return f"None of the {t} {picks} came off: {ms}.", nums
        return (f"Of the {t} {picks}, {h} came off and {m} didn't. "
                f"Hit: {hs}. Missed: {ms}."), nums
    if tone == 1:
        lead = f"The calls table scores our {t} standout picks for this gameweek."
        if not misses:
            return f"{lead} All {t} hit: {hs}.", nums
        if not hits:
            return f"{lead} All {t} missed: {ms}.", nums
        return f"{lead} {_cap(ms)} missed. {_cap(hs)} hit.", nums
    if not misses:
        return f"All {t} of our standout picks landed: {hs}.", nums
    if not hits:
        return f"None of our {t} standout picks landed: {ms}.", nums
    return f"{_cap(h)} of our {t} standout picks landed: {hs}. {_cap(ms)} didn't.", nums


def _accuracy_paragraph(comp: dict | None, tone: int) -> tuple[str | None, list[str]]:
    """Luvut kahdella desimaalilla kuten julkinen taulukko; verdikti lasketaan
    samoista pyöristetyistä luvuista, jotta teksti ei ole ristiriidassa taulukon kanssa.
    Verdikti on pohjakohtainen ja nimeää tasapelin vastapuolen."""
    if not comp:
        return None, []
    mae = comp["mae"]
    g, e, f = (_num(mae[k]) for k in ("goaliq", "fpl_ep_next", "form_baseline"))
    gv, ev, fv = float(g), float(e), float(f)
    claims = [g, e, f]
    tied = better = worse = ""
    if gv < min(ev, fv):
        kind = "closest"
    elif gv > max(ev, fv):
        kind = "furthest"
    elif gv == ev == fv:
        kind = "level"
    elif gv in (ev, fv):
        tied = EP_NEXT if gv == ev else FORM
        kind = "tie_best" if gv < (fv if gv == ev else ev) else "tie_worst"
    else:
        kind = "between"
        better, worse = (EP_NEXT, FORM) if ev < fv else (FORM, EP_NEXT)
    verdict = {
        0: {"closest": "we were closest of the three",
            "furthest": "we were furthest off of the three",
            "level": "all three were level",
            "tie_best": f"we tied with {tied} for closest",
            "tie_worst": f"we tied with {tied} for furthest off",
            "between": f"{better} beat us and we beat {worse}"},
        1: {"closest": "We beat both FPL columns on projection error",
            "furthest": "Both FPL columns beat us on projection error",
            "level": "All three columns were level on projection error",
            "tie_best": f"We tied with {tied} for the smallest projection error",
            "tie_worst": f"We tied with {tied} for the biggest projection error",
            "between": f"{better} beat us on projection error and we beat {worse}"},
        2: {"closest": "ours was the smallest miss",
            "furthest": "ours was the biggest miss",
            "level": "all three missed by the same",
            "tie_best": f"we shared the smallest miss with {tied}",
            "tie_worst": f"we shared the biggest miss with {tied}",
            "between": f"we came in behind {better} and ahead of {worse}"},
    }[tone][kind]
    text = {
        0: f"On the xP accuracy table the average miss per player was {g} "
           f"points for GoalIQ, {e} for {EP_NEXT} and {f} for {FORM}, "
           f"so {verdict}.",
        1: f"{verdict}: GoalIQ {g} points per player, {EP_NEXT} {e}, {FORM} {f}.",
        2: f"Our xP was off by {g} points per player on average, against {e} "
           f"for {EP_NEXT} and {f} for {FORM}, so {verdict}.",
    }[tone]
    return text, claims


def _num(x: float) -> str:
    return f"{float(x):.2f}"


def build_note(gw_entry: dict, recap_doc: dict, accuracy_doc: dict,
               today: date) -> dict | None:
    """Yksi muistio lopullisesti gradatusta kierroksesta, tai None."""
    if not is_final(gw_entry):
        return None
    gw = gw_entry["gw"]
    tone = gw % 3
    claims: list[str] = []
    paragraphs: list[str] = []

    calls_p, cc = _calls_paragraph(gw_entry["calls"], tone)
    if calls_p is None:
        return None  # kaikki kolme otsikkoa lupaavat kutsut
    acc_p, ac = _accuracy_paragraph(_comparison(accuracy_doc, gw), tone)
    order = [(calls_p, cc), (acc_p, ac)]
    if tone == 1:  # pohja 2 aloittaa tarkkuudesta
        order = [(acc_p, ac), (calls_p, cc)]
    for text, cl in order:
        if text:
            paragraphs.append(text)
            claims += cl

    seen: set[str] = set()
    claims = [x for x in claims if not (x in seen or seen.add(x))]
    if len(claims) < 3:
        return None

    title = {
        0: f"Gameweek {gw}: how our calls held up",
        1: f"Gameweek {gw} recap: our calls against what happened",
        2: f"What we called before gameweek {gw} and what happened",
    }[tone]
    return {
        "slug": slug_for(gw),
        "date": ((gw_entry.get("squad") or {}).get("graded_at") or "")[:10] or today.isoformat(),
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
        if g["gw"] < ENSIMMAINEN_RECAP_GW:
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
