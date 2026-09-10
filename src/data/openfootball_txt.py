"""openfootball/champions-league (txt) — Europa League ja Conference League.

UCL-KATTAVUUS-ILMAISELLA-DATALLA (10.9.2026): football.json ei kanna EL/ECL:aa,
mutta GitHubin openfootball/champions-league-repo kantaa ne tekstimuodossa
(2024-25: el.txt 189 ottelua tuloksineen, conf.txt, elq.txt, confq.txt).
Tama lukija parsii sen samaan DataFrame-muotoon kuin `openfootball.py`.

Muoto (esimerkki):
    = UEFA Europa League 2024/25
    # Date       Wed Sep 25 2024 - Wed May 21 2025 (238d)
    ▪ League phase
      Wed Sep 25 2024
        18:45  AZ Alkmaar (NED)        v IF Elfsborg (SWE)        3-2 (1-1)
               FK Bodø/Glimt (NOR)     v FC Porto (POR)           3-2 (2-1)
      Thu Oct 3
        18:45  Slavia Praha (CZE)      v AFC Ajax (NED)           1-1 (0-1)
    ▪ Round of 16
               Rangers FC (SCO)        v Fenerbahçe (TUR)   3-2 pen. 0-2 a.e.t. (0-2, 0-1)

Pisteytys: 90 minuutin tulos. Jatkoajalla ratkenneissa se on sulkujen
ENSIMMAINEN luku ("(0-2, 0-1)" = 90 min, puoliaika), muuten luku ennen
sulkuja. Sama saanto kuin track recordissa (muisti: grading norm 90min).
Paivamaararivilla ilman vuotta vuosi paatellaan kaudesta: hei-jou =
ensimmainen vuosi, tam-kes = toinen.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import requests

import config

CACHE_DIR = config.RAW_DATA_DIR / "openfootball_txt"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
BASE = "https://raw.githubusercontent.com/openfootball/champions-league/master"

FILES = {
    "INT-Champions League": ("cl", "clq"),
    "INT-Europa League": ("el", "elq"),
    "INT-Conference League": ("conf", "confq"),
}
COLUMNS = ["date", "home_team", "away_team", "home_score", "away_score",
           "league", "season", "home_xg", "away_xg", "lahde"]

_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
_DATE_RE = re.compile(r"^\s{1,4}(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Z][a-z]{2})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$")
_MATCH_RE = re.compile(
    r"^\s+(?:\d{1,2}:\d{2}\s+)?(?P<home>.+?)\s+v\s+(?P<away>.+?)\s{2,}(?P<score>\d+-\d+.*)$")
_CC_RE = re.compile(r"\s*\([A-Z]{3}\)\s*$")
_SCORE_RE = re.compile(r"(\d+)-(\d+)")


def _season_url(kausi: str) -> str:
    return f"20{kausi[:2]}-{kausi[2:]}" if len(kausi) == 4 else kausi


def _year_for(month: int, kausi: str) -> int:
    first = 2000 + int(kausi[:2])
    return first if month >= 7 else first + 1


def parse_txt(text: str, liiga: str, kausi: str) -> pd.DataFrame:
    rows = []
    cur_date = None
    for line in text.splitlines():
        if line.startswith("#") or line.startswith("="):
            continue
        m = _DATE_RE.match(line)
        if m:
            mon = _MONTHS.get(m.group(1))
            if mon:
                year = int(m.group(3)) if m.group(3) else _year_for(mon, kausi)
                cur_date = pd.Timestamp(year=year, month=mon, day=int(m.group(2)))
            continue
        m = _MATCH_RE.match(line)
        if not m or cur_date is None:
            continue
        score_txt = m.group("score")
        if "a.e.t." in score_txt:
            paren = re.search(r"\(([^)]*)\)", score_txt)
            sm = _SCORE_RE.search(paren.group(1)) if paren else None
        else:
            sm = _SCORE_RE.match(score_txt)
        if not sm:
            continue
        rows.append({
            "date": cur_date,
            "home_team": _CC_RE.sub("", m.group("home")).strip(),
            "away_team": _CC_RE.sub("", m.group("away")).strip(),
            "home_score": int(sm.group(1)), "away_score": int(sm.group(2)),
            "league": liiga, "season": kausi,
            "home_xg": pd.NA, "away_xg": pd.NA, "lahde": "openfootball_txt",
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def _fetch(kausi: str, code: str) -> str | None:
    cache = CACHE_DIR / f"{code}_{_season_url(kausi)}.txt"
    if cache.exists() and cache.stat().st_size > 100:
        return cache.read_text(encoding="utf-8")
    try:
        r = requests.get(f"{BASE}/{_season_url(kausi)}/{code}.txt", timeout=20)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    cache.write_text(r.text, encoding="utf-8")
    return r.text


def lataa(liiga: str, kaudet: list[str], qualifiers: bool = False) -> pd.DataFrame:
    """Turnauksen ottelut (tulokselliset) annetuilta kausilta."""
    codes = FILES.get(liiga)
    if not codes:
        return pd.DataFrame(columns=COLUMNS)
    if not qualifiers:
        codes = codes[:1]
    parts = []
    for k in kaudet:
        for code in codes:
            txt = _fetch(k, code)
            if txt:
                d = parse_txt(txt, liiga, k)
                if not d.empty:
                    parts.append(d)
    if not parts:
        return pd.DataFrame(columns=COLUMNS)
    return pd.concat(parts, ignore_index=True)
