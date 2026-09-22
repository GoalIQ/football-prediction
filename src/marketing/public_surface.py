"""Julkisten ilmaispintojen luku: mika luku NAKYY lukijalle tietyssa URL:ssa.

X-REPLY-MOOTTORI (22.9.2026). Reply-moduulin jokaisella luvulla on
`public_url`, ja generaattori todistaa etta sama luku on siella nakyvissa:
se hakee sivun ja vertaa. Tama moduuli on se "hakee ja lukee" -osa.

MIKSI TAULUKON SOLUN TEKSTI EIKA DATA-ATTRIBUUTTI
------------------------------------------------
Lukija ei nae `data-card-spec`ia eika JSON-LD:ta. Han nakee solun. Siksi
parseri lukee solun nakyvan tekstin ja ohittaa alarivit (`m-sub`), vain
kapealla naytolla nakyvat (`m-only`) ja minuuttiliput (`flag`): ne ovat
saman solun lisatekstia eivatka osa lukua. Muisti
tarkistusreitti-on-ihmisluettava: URL joka vastaa 200 ei viela ole reitti.

Kaikki parserit ovat puhtaita funktioita HTML-merkkijonosta, jotta ne voi
testata tallennetuilla sivuilla ilman verkkoa. Verkko on vain `fetch`issa.
"""
from __future__ import annotations

import re
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser

BASE = "https://goaliq.app"
UA = "Mozilla/5.0 (GoalIQ reply-module verifier; +https://goaliq.app)"

# `tflag` = seuran vieressa oleva lappu ("promoted", "turnover"). Se on
# nakyvaa tekstia, mutta ei osa seuran koodia: ilman ohitusta solu luki
# "COVpromoted" ja 33/100 top-100-rivia jai ilman reittia (mitattu 22.9).
SKIP_CLASSES = ("m-sub", "m-only", "flag", "tflag")


@dataclass
class Table:
    anchor: str | None
    headers: list[str] = field(default_factory=list)
    header_titles: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    caption: str = ""

    def col(self, name: str) -> int | None:
        for i, h in enumerate(self.headers):
            if h == name:
                return i
        return None


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[Table] = []
        self._anchor: str | None = None
        self._t: Table | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._cell_th = False
        self._title: str = ""
        self._spans: list[bool] = []
        self._caption = False

    def _skipping(self) -> bool:
        return any(self._spans)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id") and tag in ("h2", "h3", "details", "section"):
            self._anchor = a["id"]
        if tag == "table":
            self._t = Table(anchor=self._anchor)
        elif self._t is None:
            return
        elif tag == "caption":
            self._caption = True
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell, self._cell_th, self._title = [], tag == "th", ""
            self._spans = []
        elif tag == "span" and self._cell is not None:
            cls = (a.get("class") or "").split()
            self._spans.append(any(c in SKIP_CLASSES for c in cls))
        elif tag == "abbr" and self._cell is not None:
            self._title = a.get("title") or self._title
        elif tag == "br" and self._cell is not None and not self._skipping():
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if self._t is None:
            return
        if tag == "caption":
            self._caption = False
        elif tag == "span" and self._cell is not None and self._spans:
            self._spans.pop()
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            txt = re.sub(r"\s+", " ", "".join(self._cell)).strip()
            if self._cell_th and not self._t.rows and self._row is not None:
                self._t.headers.append(txt)
                self._t.header_titles.append(self._title)
            else:
                self._row.append(txt)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self._t.rows.append(self._row)
            self._row = None
        elif tag == "table":
            self.tables.append(self._t)
            self._t = None

    def handle_data(self, data):
        if self._t is None:
            return
        if self._caption:
            self._t.caption += data
            return
        if self._cell is not None and not self._skipping():
            self._cell.append(data)


def tables(html: str) -> list[Table]:
    p = _TableParser()
    p.feed(html)
    return p.tables


def visible_text(html: str) -> str:
    """Sivun luettava teksti yhtena rivina (ei skripteja, tyyleja, headia)."""
    body = re.sub(r"<script.*?</script>|<style.*?</style>|<head.*?</head>", " ",
                  html, flags=re.S | re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    import html as _h
    return re.sub(r"\s+", " ", _h.unescape(body)).strip()


# ---------------------------------------------------------------------------
# Sivukohtaiset lukijat. Jokainen palauttaa {avain: {sarake: teksti}} ja
# kierroksen jonka sivu itse sanoo (otsikosta), jotta vertailu voi kieltaytya
# kun sivu nayttaa eri kierrosta kuin moduuli.
# ---------------------------------------------------------------------------
def _gw_from(text: str) -> int | None:
    m = re.search(r"(?:gameweek|GW)\s*(\d{1,2})", text or "", re.I)
    return int(m.group(1)) if m else None


def gw_xp_table(html: str) -> tuple[int | None, dict]:
    """/fpl/expected-points#gw-xp: (kierros, {(nimi, seura): {...}})."""
    for t in tables(html):
        if t.anchor != "gw-xp":
            continue
        gw_col = next((i for i, h in enumerate(t.headers)
                       if re.fullmatch(r"GW\d+ xP", h)), None)
        if gw_col is None:
            continue
        gw = _gw_from(t.headers[gw_col])
        out = {}
        for r in t.rows:
            key = (r[t.col("Player")], r[t.col("Team")])
            out[key] = {"gw_xp": r[gw_col], "start_pct": r[t.col("Start%")],
                        "opponent": r[t.col("Opponent")], "price": r[t.col("Price")],
                        "rank": r[t.col("#")]}
        return gw, out
    return None, {}


def top100_table(html: str) -> tuple[int | None, dict]:
    """/fpl/expected-points (#top-100): (jakaumasarakkeiden kierros, rivit).

    Kierros luetaan `10+`-sarakkeen selitteesta ("Chance of 10 or more points
    in gameweek 6"), koska jakauma on YHDEN kierroksen luku samassa taulukossa
    jonka muut sarakkeet ovat kuuden kierroksen summia.
    """
    for t in tables(html):
        if t.col("6GW xP") is None or t.col("10+") is None:
            continue
        gw = _gw_from(t.header_titles[t.col("10+")])
        out = {}
        for r in t.rows:
            key = (r[t.col("Player")], r[t.col("Team")])
            out[key] = {"xp_6gw": r[t.col("6GW xP")], "p_10plus": r[t.col("10+")],
                        "p_blank": r[t.col("Blank")], "owned_pct": r[t.col("Own%")],
                        "start_pct": r[t.col("Start%")], "xmins": r[t.col("xMins")],
                        "xp_per_gw": r[t.col("xP/GW")], "price": r[t.col("Price")]}
        return gw, out
    return None, {}


def points_table(html: str) -> dict:
    """/fpl/points/gw{N}: jaadytetty xP ja toteutunut, {(nimi, seura): {...}}."""
    for t in tables(html):
        if t.col("xP") is None or t.col("Pts") is None:
            continue
        return {(r[t.col("Player")], r[t.col("Team")]): {"xp": r[t.col("xP")],
                                                         "pts": r[t.col("Pts")]}
                for r in t.rows}
    return {}


def clean_sheet_table(html: str) -> tuple[int | None, dict]:
    """goaliq.app/fpl#clean-sheets: (kierros captionista, {seura: {...}})."""
    for t in tables(html):
        if t.col("Clean sheet %") is None or t.col("Team") is None:
            continue
        gw = _gw_from(t.caption)
        out = {}
        for r in t.rows:
            out[r[t.col("Team")]] = {"cs_pct": r[t.col("Clean sheet %")],
                                     "opponent": r[t.col("Next opponent")]}
        return gw, out
    return None, {}


def differentials_table(html: str) -> dict:
    """/fpl/differentials: {(nimi, seura): {...}}."""
    for t in tables(html):
        if t.col("Owned") is None or t.col("xP/GW") is None:
            continue
        hz = next((i for i, h in enumerate(t.headers) if h.startswith("xP, ")), None)
        out = {}
        for r in t.rows:
            key = (r[t.col("Player")], r[t.col("Team")])
            out[key] = {"owned_pct": r[t.col("Owned")], "xp_per_gw": r[t.col("xP/GW")],
                        "xp_6gw": r[hz] if hz is not None else None,
                        "rank": r[0]}
        return out
    return {}


def club_table(html: str) -> dict:
    """/fpl/club/<slug>: {nimi: {...}} (seura on sivun oma)."""
    for t in tables(html):
        if t.col("6GW xP") is None or t.col("Owned") is None:
            continue
        return {r[t.col("Player")]: {"xp_6gw": r[t.col("6GW xP")],
                                     "owned_pct": r[t.col("Owned")],
                                     "price": r[t.col("Price")]}
                for r in t.rows}
    return {}


def gw_calls_table(html: str) -> dict:
    """goaliq.app/fpl#gw-calls: {(kierros, kutsu): {...}}."""
    for t in tables(html):
        if t.col("Call") is None or t.col("Points") is None:
            continue
        out = {}
        for r in t.rows:
            if len(r) < len(t.headers):
                continue  # seliterivi ("The squad played a Triple Captain")
            gw = _gw_from(r[t.col("GW")])
            res = r[t.col("Result")]
            m = re.match(r"(\d+) as captain", res or "")
            out[(gw, r[t.col("Call")])] = {
                "player": r[t.col("Player")], "points": r[t.col("Points")],
                "result": res, "said": r[t.col("What it said")],
                "return": m.group(1) if m else None}
        return out
    return {}


def xp_accuracy_table(html: str) -> dict:
    """goaliq.app/fpl#xp-accuracy: {kierros: {"players": .., "mae": ..}}."""
    for t in tables(html):
        if t.col("GoalIQ xP") is None or t.col("GW") is None:
            continue
        out = {}
        for r in t.rows:
            gw = _gw_from(r[t.col("GW")])
            if gw is not None:
                out[gw] = {"players": r[t.col("Players")], "mae": r[t.col("GoalIQ xP")]}
        return out
    return {}


def eo_table(html: str) -> tuple[int | None, dict]:
    """goaliq.app/fpl#eo-by-tier: (picks-kierros captionista, {nimi: {...}})."""
    for t in tables(html):
        if t.anchor != "eo-by-tier" or t.col("Player") is None:
            continue
        lead = next((i for i, h in enumerate(t.headers) if h.startswith("EO ")), None)
        if lead is None:
            continue
        gw = _gw_from(t.caption)
        return gw, {r[t.col("Player")]: {"eo_lead": r[lead],
                                         "lead_label": t.headers[lead]}
                    for r in t.rows}
    return None, {}


def track_record_sentence(html: str) -> dict | None:
    """/fpl#track-record: "Across the N completed matches, ... correctly in P of matches."""
    m = re.search(r"Across the (\d[\d,]*) completed matches, the model called the "
                  r"result correctly in ([\d.]+%) of matches", visible_text(html))
    if not m:
        return None
    return {"n": m.group(1).replace(",", ""), "pct_1x2": m.group(2)}


# ---------------------------------------------------------------------------
# Verkko
# ---------------------------------------------------------------------------
@dataclass
class Fetched:
    url: str
    status: int
    html: str
    fetched_at: str


def fetch(url: str, timeout: int = 60) -> Fetched:
    """Hae sivu. Ankkuri (#...) pudotetaan pyynnosta, ei URL:sta."""
    bare = url.split("#", 1)[0]
    req = urllib.request.Request(bare, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", "replace")
        status = getattr(r, "status", 200)
    return Fetched(url=bare, status=status, html=body,
                   fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
