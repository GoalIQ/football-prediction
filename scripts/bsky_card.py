"""Bluesky-postauksen kuva: sivun OMA jakokortti PNG:ksi (16.10.2026).

Villen pyynto: "grafiikat kans postauksiin ... aivan parhaat grafiikat". Paras kortti on 12.10
hyvaksytty uusi ulkoasu, ja se on jo jokaisella goaliq.app/fpl-sivulla (scripts/share_card_js.py).
Siksi kuvaa EI piirreta erikseen: sivu avataan headless-Chromessa repon omasta tiedostosta,
"Share as image" -nappia painetaan ja canvas kaapataan. Kortin luku = sivun luku = postauksen
luku, koska kaikki tulevat samasta [data-card-spec]-rivilistasta (muisti: jakopinta lukee eri
tiedostoa kuin sivu -> ei enaa mahdollista).

Malli: web/pro-spa/scripts/cardlab/hub_preview.py (sama kaappaus, ilman korttiskriptin vaihtoa).
"""
from __future__ import annotations

import base64
import functools
import html
import http.server
import io
import json
import re
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Sivut joilla on jakokortti (grep id="sharecard" 16.10.2026) + kierrosarkistot fpl/points/gwN.
CARD_PAGES = {"best-captain", "defence", "expected-points", "points", "price-changes", "stats",
              "team-news", "xg-leaders"}
_GW_PAGE = re.compile(r"^points/gw\d{1,2}$")
MAX_BYTES = 950_000
HOOK = r"""
window.__cards = [];
const orig = HTMLCanvasElement.prototype.toBlob;
HTMLCanvasElement.prototype.toBlob = function (cb, type, q) {
  try { window.__cards.push({w: this.width, h: this.height, url: this.toDataURL('image/png')}); } catch (e) {}
  return orig.call(this, cb, type, q);
};
HTMLAnchorElement.prototype.click = function () {};
if (navigator.canShare) navigator.canShare = () => false;
"""


class _Hiljainen(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k):  # noqa: D401 - ei palvelinlokia ajon tulosteeseen
        pass


def page_allowed(page: str) -> bool:
    return page in CARD_PAGES or bool(_GW_PAGE.match(page))


def card_spec(page: str, root: Path = ROOT) -> dict | None:
    m = re.search(r"data-card-spec='([^']*)'", (root / "fpl" / f"{page}.html").read_text(encoding="utf-8"))
    if not m:
        return None
    try:
        return json.loads(html.unescape(m.group(1)))
    except ValueError:
        return None


def alt_text(spec: dict | None) -> str:
    """Alt-teksti kortin omasta rivilistasta (saavutettavuus; sama lahde kuin kuva)."""
    if not spec:
        return "GoalIQ data card."
    rows = []
    for r in (spec.get("rows") or [])[:10]:
        team = f" ({r.get('team')})" if r.get("team") else ""
        rows.append(f"{r.get('rank', '')}. {r.get('name', '')}{team} {r.get('value', '')}".strip())
    parts = [str(spec.get("title") or ""), str(spec.get("subtitle") or "")]
    label = spec.get("valueLabel")
    head = ". ".join(p for p in parts if p)
    body = "; ".join(rows)
    return (f"{head}. {label + ': ' if label else ''}{body}")[:1500]


def _shrink(png: bytes) -> tuple[bytes, str]:
    if len(png) <= MAX_BYTES:
        return png, "image/png"
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    for q in (92, 85, 78):
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q, optimize=True)
        if buf.tell() <= MAX_BYTES:
            return buf.getvalue(), "image/jpeg"
    raise ValueError("kortti ei mahdu Blueskyn kuvarajaan")


def render(page: str, root: Path = ROOT) -> dict:
    """{bytes, mime, w, h, alt}. Kaatuu aanekkaasti; kutsuja postaa silloin ilman kuvaa."""
    if not page_allowed(page):
        raise ValueError(f"sivulla {page} ei ole jakokorttia")
    from selenium import webdriver
    from selenium.webdriver.common.by import By

    handler = functools.partial(_Hiljainen, directory=str(root))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    o = webdriver.ChromeOptions()
    o.add_argument("--headless=new")
    o.add_argument("--no-sandbox")
    o.add_argument(f"--user-data-dir={tempfile.mkdtemp(prefix='bskycard_')}")
    o.add_argument("--window-size=1280,1000")
    d = webdriver.Chrome(options=o)
    try:
        d.get(f"http://127.0.0.1:{srv.server_port}/fpl/{page}.html")
        time.sleep(2)
        d.execute_script(HOOK)
        btn = d.find_elements(By.ID, "sharecard")
        if not btn:
            raise RuntimeError(f"{page}: ei jakonappia")
        d.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", btn[0])
        cards = None
        for _ in range(60):
            cards = d.execute_script("return window.__cards")
            if cards:
                break
            time.sleep(0.25)
        if not cards:
            raise RuntimeError(f"{page}: kortti ei syntynyt")
        c = cards[-1]
        data, mime = _shrink(base64.b64decode(c["url"].split(",", 1)[1]))
        return {"bytes": data, "mime": mime, "w": int(c["w"]), "h": int(c["h"]),
                "alt": alt_text(card_spec(page, root))}
    finally:
        d.quit()
        srv.shutdown()


if __name__ == "__main__":
    import sys
    out = render(sys.argv[1])
    Path(sys.argv[2]).write_bytes(out["bytes"])
    print(out["mime"], out["w"], out["h"], len(out["bytes"]), out["alt"][:200])
