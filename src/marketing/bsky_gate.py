"""Bluesky-botin julkaisuportti (16.10.2026). Jokainen ulos lahteva teksti kulkee taman lapi.

Villen saanto 6b (julkaisuportti) automaatiossa: ihmisen julkaisutarkistaja hyvaksyy pohjat ja
ajonaikaisen agentin ohjeen, ja tama tiedosto tekee mekaanisen osan JOKA KERTA. Oletus on hylkays:
`check()` palauttaa ongelmat, ja tyhja lista on ainoa tapa paasta ulos.

Mita mitataan (kaikki kaatavat):
  1. luvut: jokainen numero tulee kaytettyjen moduuliavainten teksteista (ilmaissivu nayttaa saman),
     tai on kierrosnumero. "10+" vain p_10plus-avaimen kanssa.
  2. kielletyt merkit (em/en dash, kaarevat lainausmerkit, ellipsi, U+FFFD) ja hylatyt sanamuodot
     (data/rejected_phrases.json).
  3. pituus: 300 merkkia (Blueskyn raja on 300 grafeemia; merkkimaara on tiukempi tai sama).
  4. vastaus: ei linkkia eika tuotenimea (C1: vastaus antaa luvun, ei mainosta), kohdepostaus alle
     4 h vanha, kohdetili ei estolistalla, samaan ketjuun ei kahdesti, tekijalle tauko 48 h.
  5. toisto: ei lahes samaa tekstia kuin 40 viimeisessa (Blueskyn yhteisoohje 3.1: spammi).
  6. kiintiot: omia postauksia 3/vrk, vastauksia muiden postauksiin 4/vrk.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import config
from scripts.public_text import BANNED

MAX_CHARS = 300
POSTS_PER_DAY = 3
OUTBOUND_REPLIES_PER_DAY = 4
TARGET_MAX_AGE = timedelta(hours=4)
AUTHOR_COOLDOWN = timedelta(hours=48)
SIMILAR = 0.8

# Ei lookaheadia: "15.6m" ja "8.0xP" tarkistetaan myos (yksikko perassa ei vapauta lukua).
_NUM_RE = re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)?%?\+?")
_GW_RE = re.compile(r"\b(?:GW|Gameweek\s*)(\d{1,2})\b", re.I)
_URL_RE = re.compile(r"https?://\S+|\b[\w-]+\.(?:app|com|net|org|io|co|uk)\b\S*", re.I)


def rejected_phrases(path: Path | None = None) -> list[str]:
    p = path or (config.DATA_DIR / "rejected_phrases.json")
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [str(x.get("phrase")).lower() for x in d.get("phrases") or [] if x.get("phrase")]


def allowed_numbers(values: dict[str, dict]) -> set[str]:
    """`values`: {avain: moduulin arvo} vain julkisella reitilla (public_url) olevat."""
    out: set[str] = set()
    for key, v in values.items():
        if not v.get("public_url"):
            continue
        t = str(v.get("text") or "").strip()
        if t:
            out.add(t)
            out.add(t.rstrip("%"))
        if key.endswith("p_10plus"):
            out.add("10+")
    return out


def _words(t: str) -> set[str]:
    return set(re.findall(r"[a-z0-9.%]+", t.lower()))


def similar(a: str, b: str) -> bool:
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return False
    return len(wa & wb) / len(wa | wb) >= SIMILAR


def check(item: dict, *, values: dict[str, dict], gw: int | None, now: datetime,
          state: dict, blocklist: set[str], phrases: list[str]) -> list[str]:
    """Palauttaa ongelmat. `item`: {kind: post|reply|mention_reply, text, keys, target?}."""
    text = str(item.get("text") or "")
    kind = item.get("kind")
    probs: list[str] = []
    if not text.strip():
        return ["tyhja teksti"]
    if len(text) > MAX_CHARS:
        probs.append(f"pituus {len(text)} > {MAX_CHARS}")
    for ch, name in BANNED.items():
        if ch in text:
            probs.append(f"kielletty merkki: {name}")
    low = text.lower()
    for ph in phrases:
        if ph and ph in low:
            probs.append(f"hylatty sanamuoto: {ph!r}")

    used = {k: values[k] for k in item.get("keys") or [] if k in values}
    missing = [k for k in item.get("keys") or [] if k not in values]
    if missing:
        probs.append(f"avaimet eivat ole tuoreessa moduulissa: {missing[:5]}")
    ok_nums = allowed_numbers(used)
    gws = {str(gw)} if gw is not None else set()
    body = _URL_RE.sub(" ", text)
    for m in _GW_RE.finditer(body):
        if m.group(1) not in gws and m.group(1) not in {str(int(g) - 1) for g in gws}:
            probs.append(f"kierros GW{m.group(1)} ei ole moduulin kierros tai edellinen")
    body = _GW_RE.sub(" ", body)
    for m in _NUM_RE.finditer(body):
        n = m.group(0)
        if n not in ok_nums and n.rstrip("%") not in ok_nums:
            probs.append(f"luku {n!r} ei tule kaytetyista moduuliavaimista")

    if kind in ("reply", "mention_reply"):
        if _URL_RE.search(text):
            probs.append("vastauksessa linkki")
        if "goaliq" in low:
            probs.append("vastauksessa tuotenimi")
        tgt = item.get("target") or {}
        if not tgt.get("uri") or not tgt.get("cid"):
            probs.append("vastauksen kohde puuttuu")
        if tgt.get("uri") in set(state.get("replied_uris") or []):
            probs.append("tahan postaukseen on jo vastattu")
        if (tgt.get("root_uri") or tgt.get("uri")) in set(state.get("replied_roots") or []):
            probs.append("tahan ketjuun on jo vastattu")
    if kind == "reply":
        tgt = item.get("target") or {}
        handle = str(tgt.get("handle") or "").lower()
        if handle in blocklist:
            probs.append(f"kohdetili estolistalla: {handle}")
        try:
            created = datetime.fromisoformat(str(tgt.get("created_at")).replace("Z", "+00:00"))
            if now - created > TARGET_MAX_AGE:
                probs.append(f"kohdepostaus {int((now - created).total_seconds() // 3600)} h vanha (raja 4 h)")
        except ValueError:
            probs.append("kohdepostauksen aika puuttuu")
        last = (state.get("author_last_reply") or {}).get(handle)
        if last and now - datetime.fromisoformat(last) < AUTHOR_COOLDOWN:
            probs.append(f"tekijalle vastattu alle 48 h sitten: {handle}")

    day = now.date().isoformat()
    counts = (state.get("daily") or {}).get(day) or {}
    if kind == "post" and counts.get("post", 0) >= POSTS_PER_DAY:
        probs.append(f"omien postausten kiintio {POSTS_PER_DAY}/vrk taynna")
    if kind == "reply" and counts.get("reply", 0) >= OUTBOUND_REPLIES_PER_DAY:
        probs.append(f"vastauskiintio {OUTBOUND_REPLIES_PER_DAY}/vrk taynna")
    for prev in (state.get("recent_texts") or [])[-40:]:
        if similar(text, prev):
            probs.append("lahes sama teksti kuin aiempi postaus (toisto)")
            break
    return probs
