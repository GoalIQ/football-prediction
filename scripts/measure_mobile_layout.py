# -*- coding: utf-8 -*-
"""Mittaa sivun asettelu PUHELIMEN LEVEYDELLA, laite-emulaatiolla.

🔴 MIKSI TAMA ON OLEMASSA (12.9.2026). Yritin mitata `/fpl/expected-points`in
ottelusaraketta muuttamalla selaimen ikkunan kokoa 406 px:iin. Ikkuna muuttui,
mutta `window.innerWidth` pysyi **1536**:ssa koko ajan - eli mittaus olisi
kertonut tyopoydan asettelusta ja nimennyt sen puhelimeksi. Sama ansa on
kirjattu muistiin kahdesti (`cdp-laite-emulaatio-on-mittari`,
`headless-chrome-ilman-emulaatiota-nayttaa-ylivuotoa`), ja silti se melkein
meni lapi kolmannen kerran.

Erona pelkkaan ikkunan kokoon: `Emulation.setDeviceMetricsOverride` asettaa
LAYOUT-viewportin, `mobile: true` laukaisee mobiiliheuristiikat ja
`deviceScaleFactor` vastaa oikeaa puhelinta. Media queryt evaluoituvat vasta
silloin oikein.

KAYTTO:
    python -m scripts.measure_mobile_layout <url> [--width 390] [--shot polku.png]
                                            [--anchor gw-xp] [--sel ".lb"]

Tulostaa JSONia: viewport, dpr, ankkurin etaisyys sivun ylalaidasta,
valitsimien leveydet, vaakavieritys ja media query -tila. Exit 1 jos sivu
vierittyy vaakasuunnassa (se on lahes aina vika, ei valinta).
"""
from __future__ import annotations

import argparse
import json
import sys

MITTA_JS = r"""
const sels = arguments[0];
const anchor = arguments[1];
const el = anchor ? document.getElementById(anchor) : null;
const out = {
  viewport: innerWidth + 'x' + innerHeight,
  dpr: devicePixelRatio,
  sivu_vaakascroll: document.documentElement.scrollWidth > innerWidth + 1,
  sivun_leveys_px: document.documentElement.scrollWidth,
  sivun_korkeus_px: document.documentElement.scrollHeight,
  elementit: {}
};
if (el) {
  out.ankkuri = {
    id: anchor,
    etaisyys_ylhaalta_px: Math.round(el.getBoundingClientRect().top + scrollY),
    ruudullisia: Math.round((el.getBoundingClientRect().top + scrollY) / innerHeight * 10) / 10
  };
}
for (const s of sels) {
  const n = document.querySelector(s);
  if (!n) { out.elementit[s] = null; continue; }
  const r = n.getBoundingClientRect();
  out.elementit[s] = {
    leveys_px: Math.round(r.width),
    korkeus_px: Math.round(r.height),
    etaisyys_ylhaalta_px: Math.round(r.top + scrollY),
    nakyy: getComputedStyle(n).display !== 'none',
    // Oma vaakavieritys (esim. .lb-wrap): sisalto leveampi kuin kaare.
    oma_vaakascroll: n.scrollWidth > n.clientWidth + 1
  };
}
return out;
"""


def mittaa(url: str, leveys: int, korkeus: int, dpr: int,
           sels: list[str], anchor: str | None, shot: str | None) -> dict:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    o = Options()
    o.add_argument("--headless=new")
    o.add_argument("--hide-scrollbars")
    d = webdriver.Chrome(options=o)
    try:
        # 🔴 TAMA rivi on koko skriptin syy. Ilman sita layout-viewport on
        # ajokoneen ikkuna, ei `leveys`.
        d.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
            "width": leveys, "height": korkeus,
            "deviceScaleFactor": dpr, "mobile": True})
        d.get(url)
        tulos = d.execute_script(MITTA_JS, sels, anchor)
        # Kontrolli: jos emulaatio ei purrut, viewport ei ole pyydetty leveys
        # ja kaikki muut luvut ovat tyopoydan lukuja vaarassa nimessa.
        if tulos["viewport"].split("x")[0] != str(leveys):
            raise SystemExit(
                f"measure_mobile_layout: laite-emulaatio EI purrut "
                f"(viewport {tulos['viewport']}, pyydettiin {leveys}). "
                "Tulos olisi tyopoydan asettelu puhelimen nimella.")
        if shot:
            if anchor:
                d.execute_script(
                    "const e=document.getElementById(arguments[0]);"
                    "if(e) scrollTo(0, e.getBoundingClientRect().top+scrollY-20);",
                    anchor)
            d.save_screenshot(shot)
            tulos["kuva"] = shot
        return tulos
    finally:
        d.quit()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("url")
    ap.add_argument("--width", type=int, default=390,
                    help="layout-viewportin leveys (oletus 390 = iPhone 14)")
    ap.add_argument("--height", type=int, default=844)
    ap.add_argument("--dpr", type=int, default=3)
    ap.add_argument("--sel", action="append", default=[],
                    help="CSS-valitsin mitattavaksi, voi toistaa")
    ap.add_argument("--anchor", default=None,
                    help="elementin id jonka etaisyys mitataan")
    ap.add_argument("--shot", default=None)
    a = ap.parse_args(argv)
    tulos = mittaa(a.url, a.width, a.height, a.dpr, a.sel, a.anchor, a.shot)
    print(json.dumps(tulos, indent=1, ensure_ascii=False))
    return 1 if tulos["sivu_vaakascroll"] else 0


if __name__ == "__main__":
    sys.exit(main())
