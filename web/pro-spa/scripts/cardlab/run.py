"""Renderoi cardlab/index.html:n kortit PNG:ksi headless-Chromella.

Kaytto: python run.py <out-dir>
"""
from __future__ import annotations

import base64
import functools
import http.server
import sys
import tempfile
import threading
import time
from pathlib import Path

from selenium import webdriver

HERE = Path(__file__).resolve().parent


def main() -> int:
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(HERE))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    o = webdriver.ChromeOptions()
    o.add_argument("--headless=new")
    o.add_argument(f"--user-data-dir={tempfile.mkdtemp(prefix='cardlab_')}")
    d = webdriver.Chrome(options=o)
    try:
        d.get(f"http://127.0.0.1:{srv.server_port}/index.html")
        for _ in range(40):
            if d.execute_script("return window.__ready === true"):
                break
            time.sleep(0.25)
        time.sleep(1.5)
        d.set_script_timeout(60)
        cards = d.execute_async_script("const cb = arguments[0]; window.renderAll().then(cb, e => cb({error: String(e)}));")
        if "error" in cards:
            print("VIRHE", cards["error"]); return 1
        for k, url in cards.items():
            (out / f"{k}.png").write_bytes(base64.b64decode(url.split(",", 1)[1]))
            print(k, "ok")
        for e in d.get_log("browser") if hasattr(d, "get_log") else []:
            print("console:", e.get("message", "")[:200])
    finally:
        d.quit(); srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
