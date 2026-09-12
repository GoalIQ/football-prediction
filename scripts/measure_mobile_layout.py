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
                                            [--wait ".row"] [--click "button.name"]
                                            [--wait-after "dialog[open]"]

Tulostaa JSONia: viewport, dpr, ankkurin etaisyys sivun ylalaidasta,
valitsimien leveydet, vaakavieritys ja media query -tila. Exit 1 jos sivu
vierittyy vaakasuunnassa (se on lahes aina vika, ei valinta). Exit 2 jos jokin
klikattu elementti oli toisen kerroksen peitossa (napautus ei osuisi laitteella).
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


# Klikattavuus mitataan ennen klikkausta: JS-klikkaus onnistuu myos peitetyn
# elementin kohdalla, joten ilman osumatestia rikkinainen napautus (sticky-palkki
# tai toinen kerros paalla) nayttaisi toimivalta. Mittaus kertoo sen aaneen.
OSUMA_JS = r"""
const n = document.querySelector(arguments[0]);
if (!n) return {loytyi: false, klikattava: false};
n.scrollIntoView({block: 'center'});
const r = n.getBoundingClientRect();
const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
return {loytyi: true, klikattava: !!top && (top === n || n.contains(top))};
"""


def _odota(d, sel: str, aikaraja_s: float, uni=None) -> bool:
    """Kyselysilmukka selaimen puolella: ei selenium.support-riippuvuutta."""
    import time
    uni = uni or time.sleep
    kierroksia = max(1, int(aikaraja_s / 0.25))
    for _ in range(kierroksia):
        if d.execute_script("return !!document.querySelector(arguments[0]);", sel):
            return True
        uni(0.25)
    return False


def _chrome():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    o = Options()
    o.add_argument("--headless=new")
    o.add_argument("--hide-scrollbars")
    return webdriver.Chrome(options=o)


def mittaa(url: str, leveys: int, korkeus: int, dpr: int,
           sels: list[str], anchor: str | None, shot: str | None,
           wait: str | None = None, clicks: list[str] | None = None,
           wait_after: str | None = None, aikaraja_s: float = 20.0,
           ajuri=None, uni=None) -> dict:
    """Jarjestys on osa mittausta: lataus -> odota dataa -> klikkaa -> odota
    tulosta -> mittaa. Jos mittaus ajettaisiin ennen klikkausta, avautuvan
    dialogin ensimmainen ruutu mitattaisiin suljettuna."""
    d = (ajuri or _chrome)()
    try:
        # 🔴 TAMA rivi on koko skriptin syy. Ilman sita layout-viewport on
        # ajokoneen ikkuna, ei `leveys`.
        d.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
            "width": leveys, "height": korkeus,
            "deviceScaleFactor": dpr, "mobile": True})
        d.get(url)
        odotukset = {}
        if wait:
            odotukset[wait] = _odota(d, wait, aikaraja_s, uni)
            if not odotukset[wait]:
                raise SystemExit(
                    f"measure_mobile_layout: --wait {wait!r} ei ilmestynyt "
                    f"{aikaraja_s:.0f} s:ssa. Mittaus olisi tyhjasta sivusta.")
        klikkaukset = []
        for sel in clicks or []:
            if not _odota(d, sel, aikaraja_s, uni):
                raise SystemExit(
                    f"measure_mobile_layout: --click {sel!r} ei loytynyt.")
            osuma = d.execute_script(OSUMA_JS, sel)
            d.execute_script("document.querySelector(arguments[0]).click();", sel)
            klikkaukset.append({"sel": sel, **osuma})
        if wait_after:
            odotukset[wait_after] = _odota(d, wait_after, aikaraja_s, uni)
            if not odotukset[wait_after]:
                raise SystemExit(
                    f"measure_mobile_layout: --wait-after {wait_after!r} ei "
                    "ilmestynyt klikkauksen jalkeen.")
        tulos = d.execute_script(MITTA_JS, sels, anchor)
        tulos["odotukset"] = odotukset
        tulos["klikkaukset"] = klikkaukset
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
    ap.add_argument("--wait", default=None,
                    help="CSS-valitsin jota odotetaan ennen klikkauksia (SPA hakee datan mountin jalkeen)")
    ap.add_argument("--click", action="append", default=[],
                    help="CSS-valitsin joka klikataan, jarjestyksessa, voi toistaa")
    ap.add_argument("--wait-after", default=None,
                    help="CSS-valitsin jota odotetaan klikkausten jalkeen, esim. 'dialog[open]'")
    ap.add_argument("--timeout", type=float, default=20.0)
    a = ap.parse_args(argv)
    tulos = mittaa(a.url, a.width, a.height, a.dpr, a.sel, a.anchor, a.shot,
                   wait=a.wait, clicks=a.click, wait_after=a.wait_after,
                   aikaraja_s=a.timeout)
    print(json.dumps(tulos, indent=1, ensure_ascii=False))
    if any(not k["klikattava"] for k in tulos["klikkaukset"]):
        return 2
    return 1 if tulos["sivu_vaakascroll"] else 0


if __name__ == "__main__":
    sys.exit(main())
