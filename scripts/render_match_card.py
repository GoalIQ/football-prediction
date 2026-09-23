# -*- coding: utf-8 -*-
"""Ottelun 1X2-kortti nykyisella brandilla (23.9.2026).

Villen palaute 23.9: "mita noi kuvat nyt on, vanhat logot". outputs/gen_card.py
on kesakuun violetti pohja; nykyinen ilme on sama kuin gen_share_card.py:n
korteissa: muste (INK), amber, IBM Plex Mono ja teletext-sanamerkki. Tama
renderoija kayttaa NIITA vakioita suoraan (ei kopioita), jotta ilme ei voi
eriytya.

Vain 1X2 (julkaisutarkistaja 23.9): xG ja todennakoisin tulos ovat appissa
Premium-lukossa, joten julkinen kortti ei kanna niita.

Luvut ja suosikki luetaan AINA tuotannon API:sta (sama POST /api/predict-wc
jota appi kayttaa), ei kasin syotetyista prosenteista (saanto 6a, julkaisu-
tarkistaja 23.9). Korostus seuraa palvelimen `call`-kenttaa: kun ero on
mitatun marginaalin sisalla (too_close), mitaan ei korosteta.

AJO:
    python -m scripts.render_match_card --home Netherlands --away Germany
        --league "INT-Nations League" --tag MD1 --when "THU 24 SEP  ·  LEAGUE A"
        --stamp "as of 23 Sep" --out outputs/cards/unl_ned_ger.png
"""
from __future__ import annotations

import argparse
import math
import os
import re
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw

from scripts.gen_share_card import (AMBER, CREAM, FONT_BOLD, FONT_MED, INK, INK2,
                                    MUTED, _font)
from src.brand import WORDMARK_PNG

W, H, MX = 1200, 675, 60
PANEL_BG = (24, 23, 21)
BAR_REST = (60, 58, 54)
APP_DIR = Path(os.environ.get("GOALIQ_APP_DIR")
               or Path(__file__).resolve().parents[2] / "goaliq-app")


def pct_100(ps) -> list[int]:
    """Kokonaisluvut suurimman jaannoksen saannolla: summa on aina 100."""
    raw = [p * 100 for p in ps]
    fl = [math.floor(x) for x in raw]
    for i in sorted(range(3), key=lambda i: raw[i] - fl[i], reverse=True)[:100 - sum(fl)]:
        fl[i] += 1
    return fl


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def _iso(name: str) -> str | None:
    """Maan ISO appin lib/flags.ts:sta (sama lahde kuin appin liput)."""
    ts = (APP_DIR / "lib" / "flags.ts").read_text(encoding="utf-8")
    blk = ts[ts.index("NAME_TO_ISO_RAW"):ts.index("};", ts.index("NAME_TO_ISO_RAW"))]
    for m in re.finditer(r"^\s+'?([^':\n]+?)'?: '([a-z-]+)',", blk, re.M):
        if _norm(m.group(1)) == _norm(name):
            return m.group(2)
    return None


def _flag(canvas: Image.Image, name: str, cx: int, top: int, w: int = 132, h: int = 88):
    iso = _iso(name)
    p = APP_DIR / "assets" / "flags" / f"{iso}.png" if iso else None
    if not p or not p.exists():
        return
    fl = Image.open(p).convert("RGBA")
    # Litistys: rajaa lippu 3:2-laatikkoon (leveat liput leikataan keskelta).
    r = w / h
    if fl.width / fl.height > r:
        nw = int(fl.height * r)
        fl = fl.crop(((fl.width - nw) // 2, 0, (fl.width - nw) // 2 + nw, fl.height))
    else:
        nh = int(fl.width / r)
        fl = fl.crop((0, (fl.height - nh) // 2, fl.width, (fl.height - nh) // 2 + nh))
    fl = fl.resize((w, h), Image.LANCZOS)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=10, fill=255)
    canvas.paste(fl, (cx - w // 2, top), mask)


API = "https://api.goaliq.app/api/predict-wc"


def fetch_prediction(home: str, away: str, league: str) -> dict:
    import json
    import urllib.request
    req = urllib.request.Request(
        API, data=json.dumps({"home_team": home, "away_team": away,
                              "leagues": [league]}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "goaliq-card"})
    return json.load(urllib.request.urlopen(req, timeout=60))


def unl_league_letter(home: str) -> str | None:
    """UNL-lohkon liigakirjain ('Group A2' -> 'A') tuotannon taulukosta,
    ei kasin (23.9: testikortti sai vaaran 'LEAGUE A' Kosovo-Irlannille)."""
    import json
    import urllib.parse
    import urllib.request
    url = ("https://api.goaliq.app/api/standings?"
           + urllib.parse.urlencode({"league": "INT-Nations League"}))
    d = json.load(urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "goaliq-card"}), timeout=60))
    for g in d.get("groups") or []:
        if any(r.get("team_name") == home for r in g.get("rows") or []):
            m = re.match(r"Group ([A-D])\d", g.get("group") or "")
            return m.group(1) if m else None
    return None


def favourite_index(call: dict | None) -> int | None:
    """Palvelimen `call` -> korostettava sarake (0 koti, 2 vieras) tai None.
    Tasapelia ei koskaan korosteta suosikkina, eika mitaan kun too_close."""
    if not call or call.get("too_close"):
        return None
    return {"home": 0, "away": 2}.get(call.get("favourite"))


def render(home: str, away: str, pred: dict, title: str, tag: str, when: str,
           stamp: str, out: Path) -> Path:
    h_p, d_p, a_p = pct_100((pred["p_home_win"], pred["p_draw"], pred["p_away_win"]))
    fav = favourite_index(pred.get("call"))

    grad = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        grad.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(INK, INK2)))
    c = grad.resize((W, H)).convert("RGBA")
    d = ImageDraw.Draw(c)

    if WORDMARK_PNG.exists():
        wm = Image.open(WORDMARK_PNG).convert("RGBA")
        wm = wm.resize((int(wm.width * 56 / wm.height), 56), Image.LANCZOS)
        c.alpha_composite(wm, (W - MX - wm.width, 48))

    f_t = _font(FONT_BOLD, 46)
    d.text((MX, 44), title, font=f_t, fill=CREAM)
    d.text((MX + d.textlength(title + " ", font=f_t), 44), tag, font=f_t, fill=AMBER)
    d.text((MX, 104), f"{when}  ·  Dixon-Coles match model  ·  {stamp}",
           font=_font(FONT_MED, 20), fill=MUTED)

    top, bottom = 164, 560
    d.rounded_rectangle([MX, top, W - MX, bottom], radius=16, fill=PANEL_BG)
    cols = [MX + (W - 2 * MX) * k // 6 for k in (1, 3, 5)]
    f_name = _font(FONT_BOLD, 30)
    f_lbl = _font(FONT_MED, 18)
    for i, (cx, name, p) in enumerate(zip(cols, (home, "DRAW", away), (h_p, d_p, a_p))):
        if i == 1:
            f_draw = _font(FONT_BOLD, 30)
            d.text((cx - d.textlength("DRAW", font=f_draw) / 2, 226), "DRAW",
                   font=f_draw, fill=MUTED)
        else:
            _flag(c, name, cx, 196)
            nm = name.upper()
            fs = 30
            while d.textlength(nm, font=_font(FONT_BOLD, fs)) > 330 and fs > 18:
                fs -= 2
            fn = _font(FONT_BOLD, fs)
            d.text((cx - d.textlength(nm, font=fn) / 2, 300), nm, font=fn, fill=CREAM)
            lb = "HOME" if i == 0 else "AWAY"
            d.text((cx - d.textlength(lb, font=f_lbl) / 2, 342), lb, font=f_lbl, fill=MUTED)
        val = f"{p}%"
        f_v = _font(FONT_BOLD, 92 if i == fav else 70)
        y_v = 378 if i == fav else 392
        d.text((cx - d.textlength(val, font=f_v) / 2, y_v), val, font=f_v,
               fill=AMBER if i == fav else CREAM)

    # Palkki: suosikin osuus amberilla, muut tummalla. Vali 6 px.
    bx0, bx1, by = MX + 36, W - MX - 36, 506
    total, gap = bx1 - bx0, 6
    x = bx0
    for i, p in enumerate((h_p, d_p, a_p)):
        w = round((total - 2 * gap) * p / 100)
        if w > 0:
            d.rounded_rectangle([x, by, x + w, by + 16], radius=8,
                                fill=AMBER if i == fav else BAR_REST)
        x += w + gap

    d.text((MX, 598), "Model prediction, not betting advice.", font=_font(FONT_MED, 20),
           fill=MUTED)
    out.parent.mkdir(parents=True, exist_ok=True)
    c.convert("RGB").save(out, optimize=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", required=True)
    ap.add_argument("--away", required=True)
    ap.add_argument("--league", required=True, help='esim. "INT-Nations League"')
    ap.add_argument("--title", default="NATIONS LEAGUE")
    ap.add_argument("--tag", default="")
    ap.add_argument("--when", required=True)
    ap.add_argument("--stamp", required=True, help='esim. "as of 23 Sep"')
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pred = fetch_prediction(a.home, a.away, a.league)
    when = a.when
    if a.league == "INT-Nations League":
        letter = unl_league_letter(pred["home_team"])
        if not letter:
            raise SystemExit(f"{a.home}: UNL-lohkoa ei loytynyt taulukosta")
        when = f"{a.when}  ·  LEAGUE {letter}"
    print(render(a.home, a.away, pred, a.title, a.tag, when, a.stamp, Path(a.out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
