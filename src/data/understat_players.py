# -*- coding: utf-8 -*-
"""Understatin pelaaja- ja joukkuekertymat viidelle paasarjalle (XHR).

Understatin HTML on kuori (muisti understat-js-kuori-kaikille-kausille),
mutta sivun oma XHR `getLeagueData/<liiga>/<vuosi>` palauttaa datan kun
pyynnossa on `X-Requested-With: XMLHttpRequest`. Vastaus on gzip-pakattu.
Mitattu 21.9.2026: 2025 (= kausi 25/26) ja 2026 (= 26/27) vastaavat kaikille
viidelle liigalle, 367-600 pelaajaa per liiga.

Kaytto: UCL Fantasyn xP (src/models/ucl_xp.py) tarvitsee pelaajan OSUUDEN
oman joukkueensa maaleista ja syotoista seka minuuttiosuuden. Osuus on
kotiliigasta, maaliodotus CL-mallista - nain osuus siirtyy kilpailutasolta
toiselle ilman etta kotiliigan taso vaaristaa sita.
"""
from __future__ import annotations

import gzip
import json
import time
import urllib.request
from pathlib import Path

import config

LIIGAT = {
    "ENG": "EPL",
    "ESP": "La_liga",
    "GER": "Bundesliga",
    "ITA": "Serie_A",
    "FRA": "Ligue_1",
}
"""UEFAn maakoodi -> Understatin liiga-avain."""

CACHE_DIR = config.RAW_DATA_DIR / "understat_players"
TTL_SEC = 12 * 3600


def _hae(liiga: str, vuosi: int) -> dict:
    url = f"https://understat.com/getLeagueData/{liiga}/{vuosi}"
    req = urllib.request.Request(url, headers={
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://understat.com/league/{liiga}/{vuosi}",
        "Accept-Encoding": "gzip",
    })
    with urllib.request.urlopen(req, timeout=40) as r:
        raaka = r.read()
        if r.headers.get("Content-Encoding") == "gzip" or raaka[:2] == b"\x1f\x8b":
            raaka = gzip.decompress(raaka)
    d = json.loads(raaka.decode("utf-8"))
    if not isinstance(d, dict) or "players" not in d or "teams" not in d:
        raise ValueError(f"odottamaton vastaus: {list(d)[:5] if isinstance(d, dict) else type(d)}")
    return d


def lataa(maa: str, vuosi: int, *, verkko: bool = True) -> dict | None:
    """{'players': [...], 'teams': {...}} tai None. Levyvalimuisti TTL 12 h;
    jos haku epaonnistuu, vanha levyversio (syy lokitetaan)."""
    liiga = LIIGAT[maa]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = CACHE_DIR / f"{liiga}_{vuosi}.json"
    if p.exists() and (not verkko or time.time() - p.stat().st_mtime < TTL_SEC):
        return json.loads(p.read_text(encoding="utf-8"))
    if not verkko:
        return None
    try:
        d = _hae(liiga, vuosi)
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        return d
    except Exception as e:
        if p.exists():
            print(f"[understat_players] {liiga} {vuosi}: {type(e).__name__}: {e} -> levyn versio")
            return json.loads(p.read_text(encoding="utf-8"))
        print(f"[understat_players] {liiga} {vuosi}: {type(e).__name__}: {e} -> ei dataa")
        return None


def joukkueet(d: dict, ennen: str | None = None) -> dict[str, dict]:
    """Joukkue -> {'ottelut', 'xg', 'npxg'} (valinnaisesti vain ennen paivaa)."""
    out = {}
    for t in (d.get("teams") or {}).values():
        hist = [h for h in t.get("history", []) if ennen is None or h["date"][:10] < ennen]
        out[t["title"]] = {
            "ottelut": len(hist),
            "xg": sum(float(h["xG"]) for h in hist),
            "npxg": sum(float(h["npxG"]) for h in hist),
        }
    return out


def pelaajat(d: dict) -> list[dict]:
    """Pelaajarivit numeroina. Pelaaja joka vaihtoi seuraa kauden aikana on
    Understatissa muodossa 'Seura A,Seura B'; sailytetaan viimeinen."""
    out = []
    for p in d.get("players") or []:
        seura = str(p.get("team_title", "")).split(",")[-1].strip()
        out.append({
            "id": str(p["id"]), "nimi": p["player_name"], "seura": seura,
            "ottelut": int(p["games"]), "min": float(p["time"]),
            "g": float(p["goals"]), "xg": float(p["xG"]), "npxg": float(p["npxG"]),
            "a": float(p["assists"]), "xa": float(p["xA"]),
            "yc": float(p["yellow_cards"]), "rc": float(p["red_cards"]),
            "pos": p.get("position", ""),
        })
    return out
