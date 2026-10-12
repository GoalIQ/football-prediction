"""Sivujen jakokortit uudella JS:lla paikallisesti PNG:ksi.

Kopioi repon fpl/<sivu>.html:t, vaihtaa niiden kortti-scriptin uuteen
SHARE_CARD_JS:aan, palvelee repojuuren assetit ja kaappaa canvasin toBlobista.
Kaytto (fp:n .venv): python hub_preview.py <out-dir> [sivu ...]
"""
from __future__ import annotations

import base64
import functools
import http.server
import re
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

FP = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(FP))
from scripts.share_card_js import SHARE_CARD_JS  # noqa: E402
from selenium import webdriver  # noqa: E402
from selenium.webdriver.common.by import By  # noqa: E402

PAGES = ["expected-points", "defence", "best-captain", "stats", "points", "xg-leaders"]
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
NEW = SHARE_CARD_JS.replace("__CARD_ROWS_FN__", "function(){return null;}")
OLD_BLOCK = re.compile(r"<script>\s*\(function\(\)\{\s*// --- Dimensions and palette:.*?\}\)\(\);\s*</script>", re.S)


def main() -> int:
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    pages = sys.argv[2:] or PAGES
    root = Path(tempfile.mkdtemp(prefix="hubprev_"))
    (root / "fpl").mkdir()
    shutil.copytree(FP / "assets", root / "assets")
    for pg in pages:
        html = (FP / "fpl" / f"{pg}.html").read_text(encoding="utf-8")
        new, n = OLD_BLOCK.subn(lambda m: NEW.strip(), html)
        print(pg, "korvattu", n)
        (root / "fpl" / f"{pg}.html").write_text(new, encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    o = webdriver.ChromeOptions(); o.add_argument("--headless=new")
    o.add_argument(f"--user-data-dir={tempfile.mkdtemp(prefix='hubprev_ch_')}")
    o.add_argument("--window-size=1280,1000")
    d = webdriver.Chrome(options=o)
    try:
        for pg in pages:
            d.get(f"http://127.0.0.1:{srv.server_port}/fpl/{pg}.html"); time.sleep(3)
            d.execute_script(HOOK)
            btn = d.find_elements(By.ID, "sharecard")
            if not btn:
                print(pg, "ei jakonappia"); continue
            d.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", btn[0])
            for _ in range(40):
                cards = d.execute_script("return window.__cards")
                if cards: break
                time.sleep(0.25)
            if not cards:
                print(pg, "ei korttia, nappi:", btn[0].text); continue
            c = cards[-1]
            (out / f"{pg}.png").write_bytes(base64.b64decode(c["url"].split(",", 1)[1]))
            print(pg, f"{c['w']}x{c['h']}")
    finally:
        d.quit(); srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
