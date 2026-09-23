# -*- coding: utf-8 -*-
"""Siirtokortti: kaksi FPL-pelaajaa rinnakkain nykyisella brandilla (23.9.2026).

Kaytto: kierroksen ostetuin vs myydyin (tai mika tahansa pari). Luvut luetaan
TUOREUSVARMENNETUSTA reply-moduulista (`load_reply_module`, sama lukija kuin
X-moottorissa), ei kasin: moduuli kieltaytyy, jos yksikin luku on liikkunut
lahteesta. Paremman xP:n korostus lasketaan datasta.

Kortilla vain luvut joilla on ilmainen julkinen reitti moduulissa
(`public_url`): hinta, xP seuraavat 6 kierrosta ja omistus.

AJO:
    python -m scripts.render_swap_card --gw 6 --left gro-bha --right joao-pedro-che \
        --left-label "MOST BOUGHT" --right-label "MOST SOLD" --stamp "as of 23 Sep" \
        --out outputs/cards/gw6_swap.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from scripts.gen_share_card import (AMBER, CREAM, FONT_BOLD, FONT_MED, INK, INK2,
                                    MUTED, WORDMARK, _draw_kit_pil, _font)
from src.marketing.reply_module import load_reply_module

W, H, MX = 1200, 675, 60
PANEL_BG = (24, 23, 21)
PUBLIC_KEYS = ("price", "xp_6gw", "owned_pct")


def player_values(gw: int, key: str) -> dict:
    m = load_reply_module(gw, sections=["player_lookup"])
    sec = m["sections"]["player_lookup"]
    rows = sec["rows"] if isinstance(sec, dict) else sec
    row = next((r for r in rows if r["key"] == key), None)
    if row is None:
        raise SystemExit(f"{key}: ei moduulissa gw{gw}")
    # IBM Plex Monon ß-glyfi (ſʒ-muoto) lukee kortilla "Groʒ":na (julkaisu-
    # tarkistaja 23.9); @OfficialFPL:n oma grafiikka kirjoittaa GROSS.
    out = {"name": row["name"].replace("ß", "ss"), "team": row["team"]}
    for k in PUBLIC_KEYS:
        v = row["values"].get(k) or {}
        if not v.get("public_url"):
            raise SystemExit(f"{key}.{k}: ei julkista reittia, ei kortille")
        out[k] = v
    return out


def render(gw: int, left: dict, right: dict, left_label: str, right_label: str,
           stamp: str, out: Path) -> Path:
    grad = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        grad.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(INK, INK2)))
    c = grad.resize((W, H)).convert("RGBA")
    d = ImageDraw.Draw(c)
    if WORDMARK.exists():
        wm = Image.open(WORDMARK).convert("RGBA")
        wm = wm.resize((int(wm.width * 56 / wm.height), 56), Image.LANCZOS)
        c.alpha_composite(wm, (W - MX - wm.width, 48))

    f_t = _font(FONT_BOLD, 46)
    title = f"{left_label} VS {right_label}"
    d.text((MX, 44), f"GW{gw} ", font=f_t, fill=AMBER)
    d.text((MX + d.textlength(f"GW{gw} ", font=f_t), 44), title, font=f_t, fill=CREAM)
    d.text((MX, 104), f"xP over the next six gameweeks  ·  GoalIQ model  ·  {stamp}",
           font=_font(FONT_MED, 20), fill=MUTED)

    better = 0 if left["xp_6gw"]["value"] >= right["xp_6gw"]["value"] else 1
    top, bottom = 164, 572
    col_w = (W - 2 * MX - 24) // 2
    for i, (p, lab) in enumerate(((left, left_label), (right, right_label))):
        x0 = MX + i * (col_w + 24)
        d.rounded_rectangle([x0, top, x0 + col_w, bottom], radius=16, fill=PANEL_BG)
        hi = i == better
        d.text((x0 + 28, top + 22), lab, font=_font(FONT_BOLD, 22), fill=AMBER if hi else MUTED)
        _draw_kit_pil(c, x0 + 28, top + 70, 64, p["team"])
        fn = 40
        while d.textlength(p["name"], font=_font(FONT_BOLD, fn)) > col_w - 140 and fn > 24:
            fn -= 2
        d.text((x0 + 108, top + 68), p["name"], font=_font(FONT_BOLD, fn), fill=CREAM)
        d.text((x0 + 108, top + 116), f"{p['team']}  ·  £{p['price']['text']}m",
               font=_font(FONT_MED, 22), fill=MUTED)
        xp = p["xp_6gw"]["text"]
        f_x = _font(FONT_BOLD, 120)
        d.text((x0 + 28, top + 176), xp, font=f_x, fill=AMBER if hi else CREAM)
        d.text((x0 + 28 + d.textlength(xp, font=f_x) + 14, top + 260), "xP",
               font=_font(FONT_BOLD, 34), fill=AMBER if hi else CREAM)
        d.text((x0 + 28, top + 336), f"{p['owned_pct']['text']} owned",
               font=_font(FONT_MED, 24), fill=MUTED)

    d.text((MX, 604), "Model projection, not betting advice.", font=_font(FONT_MED, 20),
           fill=MUTED)
    out.parent.mkdir(parents=True, exist_ok=True)
    c.convert("RGB").save(out, optimize=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gw", type=int, required=True)
    ap.add_argument("--left", required=True)
    ap.add_argument("--right", required=True)
    ap.add_argument("--left-label", default="IN")
    ap.add_argument("--right-label", default="OUT")
    ap.add_argument("--stamp", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    print(render(a.gw, player_values(a.gw, a.left), player_values(a.gw, a.right),
                 a.left_label, a.right_label, a.stamp, Path(a.out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
