"""Jakokorttien kuvaus headless Chromella: yksi polku, samat fontit joka koneella.

🔴 MIKSI TAMA ON OMA MODUULINSA (22.9.2026, LANDING-KORTIT-GW3-VANHAT)
Kortit renderoitiin tahan asti vain Villen Windows-koneella. Kun renderointi
kytkettiin `fpl-data-refresh`iin (ubuntu-latest), kaksi asiaa mitattiin
ennen kuin mitaan ajettiin CI:ssa:

1. **Fontti tuli koneelta, ei kortilta.** Pino oli
   `'Segoe UI',system-ui,sans-serif`. Runnerilla ei ole Segoe UI:ta, joten
   fontconfig antaa DejaVu Sansin. Simuloitu Windowsilla samoilla
   DejaVu-tiedostoilla: standouts-kortin alapalkin tarkistusreitti katkesi
   kahdelle riville kohdasta `#top-` / `100`, ja projected-XI-kortin reitti
   valui kokonaan kuvan ulkopuolelle. Kortti joka nayttaa Windowsilla oikealta
   olisi julkaistu automaattisesti rikkinaisena.
2. **Rikki jo Windowsilla.** Projected-XI-kortin alapalkki oli 1 346 px leveä
   1 200 px:n kortilla (mitattu `layout_report`illa): alapalkin teksti
   pidentyi 4.9 jalkeen, eika korttia renderoity kertaakaan sen jalkeen, joten
   kukaan ei nahnyt etta `goaliq.app/fpl/expected-points#gw-xp` leikkautui
   pois. Tarkistusreitti on kortin tarkein rivi (muisti:
   tarkistusreitti-on-ihmisluettava).

KORJAUS (CLAUDE.md 6a kohta 1: yksi lukija joka ei voi palauttaa vaaraa):
  * Fontit ovat repossa (`scripts/card_fonts/`, IBM Plex Sans + Mono, OFL,
    samat perheet joita sivusto lataa) ja upotetaan korttiin data-URIna.
    Isannan fontit eivat voi enaa vaikuttaa asetteluun: sama HTML tuottaa
    saman rivityksen Windowsilla ja Linuxilla (Chrome muotoilee HarfBuzzilla
    molemmissa). `uncovered_chars` kaataa renderoinnin jos kortilla on merkki
    jota upotetut fontit eivat kata, koska se merkki haettaisiin taas
    koneelta.
  * `render_card` mittaa asettelun ENNEN kuvausta ja kieltaytyy kirjoittamasta
    PNG:ta jos teksti valuu kortin tai kehyksensa ulkopuolelle tai leikkautuu
    ilman ellipsia. Vika ei siis voi paatya sivulle hiljaa, eika sen
    loytaminen riipu siita etta joku katsoo kuvaa.
"""
from __future__ import annotations

import base64
import html as _html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent / "card_fonts"
KOKO = (1200, 675)

# Fontsourcen (5.3.0) osajoukot. Nimet ovat samat kuin sivuston Google Fonts
# -latauksessa, joten `src/brand.py`:n MONO-pino osuu upotettuun fonttiin.
_LATIN = ("U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,"
          "U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,"
          "U+2212,U+2215,U+FEFF,U+FFFD")
_LATIN_EXT = ("U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,"
              "U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,"
              "U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF")
SUBSETS = {"latin": _LATIN, "latin-ext": _LATIN_EXT}
FACES = ([("IBM Plex Sans", "ibm-plex-sans", w) for w in (400, 500, 600, 700)]
         + [("IBM Plex Mono", "ibm-plex-mono", 700)])

SANS = "'IBM Plex Sans',sans-serif"


def _ranges(spec: str) -> list[tuple[int, int]]:
    out = []
    for part in spec.split(","):
        a, _, b = part.strip()[2:].partition("-")
        out.append((int(a, 16), int(b or a, 16)))
    return out


_COVERED = [r for spec in SUBSETS.values() for r in _ranges(spec)]


def uncovered_chars(text: str) -> list[str]:
    """Merkit joille upotetuissa fonteissa ei ole glyfia (haettaisiin koneelta)."""
    return sorted({c for c in text
                   if not c.isspace()
                   and not any(a <= ord(c) <= b for a, b in _COVERED)})


def font_face_css() -> str:
    """@font-face-saannot data-URIna. Tiedoston puuttuminen kaataa heti:
    hiljainen fallback koneen fonttiin on tasan se vika jota tama estaa."""
    rules = []
    for family, stem, weight in FACES:
        for subset, rng in SUBSETS.items():
            f = FONT_DIR / f"{stem}-{subset}-{weight}-normal.woff2"
            b64 = base64.b64encode(f.read_bytes()).decode("ascii")
            rules.append(
                f"@font-face{{font-family:'{family}';font-style:normal;"
                f"font-weight:{weight};font-display:block;"
                f"src:url(data:font/woff2;base64,{b64}) format('woff2');"
                f"unicode-range:{rng};}}")
    return "".join(rules)


def with_fonts(html: str) -> str:
    """Kortin HTML upotetuilla fonteilla. Lisataan VASTA kuvattavaan
    tiedostoon: `build_html`in tulos pysyy ilman base64-dataa, jotta
    tekstiportit (publish_gate, BANNED_COPY) eivat skannaa fonttitiedostoja."""
    if "<style>" not in html:
        raise ValueError("kortin HTML:ssa ei ole <style>-lohkoa fonteille")
    return html.replace("<style>", "<style>" + font_face_css(), 1)


def find_chrome() -> str | None:
    candidates = [shutil.which(n) for n in
                  ("chrome", "google-chrome", "chromium", "msedge")]
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env)
        if base:
            candidates.append(str(Path(base) / "Google" / "Chrome"
                                  / "Application" / "chrome.exe"))
    for exe in candidates:
        if exe and Path(exe).exists():
            return exe
    return None


def _base_args(exe: str, size: tuple[int, int]) -> list[str]:
    args = [exe, "--headless=new", f"--window-size={size[0]},{size[1]}",
            "--hide-scrollbars",
            # Fontit ovat data-URIna mutta latautuvat silti asynkronisesti:
            # virtuaaliaika antaa niiden valmistua ennen kuvausta.
            "--virtual-time-budget=5000"]
    # Ubuntu 23.10+ rajoittaa kayttajanimiavaruuksia (AppArmor), ja Chromen
    # hiekkalaatikko voi kaatua runnerilla "No usable sandbox". Sivu on oma
    # generoimamme tiedosto ilman verkkoresursseja, joten hiekkalaatikon
    # ohitus CI:n Linuxilla ei avaa mitaan.
    if sys.platform.startswith("linux") and os.environ.get("CI"):
        args.append("--no-sandbox")
    return args


# Mittaus ajetaan selaimessa fonttien latauduttua. Kolme vikaluokkaa:
#   outside   tekstirivi kortin tai lahimman reunallisen kehyksen ulkopuolella
#   clipped   overflow:hidden leikkaa tekstin ILMAN ellipsia (hiljainen katkos)
#   ellipsis  tarkoituksellinen katkaisu (varoitus, ei kaada)
#   fonts     upotettu fontti ei latautunut (status error)
_MEASURE_JS = r"""
<script>
(function(){
  function desc(el){var c=el.getAttribute&&el.getAttribute('class');
    var t=(el.textContent||'').replace(/\s+/g,' ').trim().slice(0,60);
    return el.tagName.toLowerCase()+(c?'.'+String(c).split(' ').join('.'):'')+' "'+t+'"';}
  function frame(el,card){var e=el;while(e&&e!==card){var s=getComputedStyle(e);
    if(parseFloat(s.borderTopWidth)||parseFloat(s.borderRightWidth)||
       parseFloat(s.borderBottomWidth)||parseFloat(s.borderLeftWidth))return e;
    e=e.parentElement;}return card;}
  function clippedBy(el,card){var e=el;while(e&&e!==card){
    if(getComputedStyle(e).overflowX!=='visible')return true;e=e.parentElement;}return false;}
  function run(){
    var card=document.querySelector('.card');var out={outside:[],clipped:[],ellipsis:[],fonts:[],card:null};
    if(!card){out.outside.push('no .card element');return done(out);}
    var cr=card.getBoundingClientRect();out.card=[cr.width,cr.height];
    var w=document.createTreeWalker(card,NodeFilter.SHOW_TEXT);var n;
    while((n=w.nextNode())){
      if(!n.textContent.trim())continue;var el=n.parentElement;
      if(clippedBy(el,card))continue;
      var f=frame(el,card);var fr=f.getBoundingClientRect();
      var rg=document.createRange();rg.selectNodeContents(n);var rs=rg.getClientRects();
      for(var i=0;i<rs.length;i++){var r=rs[i];if(!r.width)continue;
        if(r.right>fr.right+1||r.left<fr.left-1||r.bottom>fr.bottom+1||r.top<fr.top-1){
          out.outside.push(desc(el)+' out of '+desc(f).slice(0,40)+' at '+[r.left,r.top,r.right,r.bottom].map(Math.round).join(','));break;}}
    }
    card.querySelectorAll('*').forEach(function(el){var s=getComputedStyle(el);
      if(s.overflowX!=='visible'&&el.scrollWidth>el.clientWidth+1)
        (s.textOverflow==='ellipsis'?out.ellipsis:out.clipped).push(desc(el)+' '+el.scrollWidth+'>'+el.clientWidth);});
    document.fonts.forEach(function(ff){if(ff.status==='error')out.fonts.push(ff.family+' '+ff.weight);});
    done(out);
  }
  function done(out){var p=document.createElement('pre');p.id='__card_layout';
    p.textContent=JSON.stringify(out);document.body.appendChild(p);}
  document.fonts.ready.then(run);
})();
</script>
"""


def visible_text(html: str) -> str:
    """Kortin teksti ilman tyyleja ja skripteja (SVG:n <text> jaa mukaan)."""
    body = re.sub(r"<(style|script)\b.*?</\1>", " ", html, flags=re.S)
    return _html.unescape(re.sub(r"<[^>]+>", " ", body))


def layout_report(exe: str, html_path: Path,
                  size: tuple[int, int] = KOKO) -> dict:
    """Asettelu mitattuna samalla selaimella ja ikkunalla kuin kuvaus."""
    src = html_path.read_text(encoding="utf-8")
    tmp = html_path.with_name(html_path.stem + ".layout.html")
    tmp.write_text(src + _MEASURE_JS, encoding="utf-8")
    try:
        r = subprocess.run(_base_args(exe, size) + ["--dump-dom", tmp.as_uri()],
                           capture_output=True, timeout=90)
    finally:
        tmp.unlink(missing_ok=True)
    dom = r.stdout.decode("utf-8", "replace")
    m = re.search(r'<pre id="__card_layout">(.*?)</pre>', dom, re.S)
    if not m:
        return {"error": "mittausraporttia ei syntynyt (exit %s): %s" % (
            r.returncode, r.stderr.decode("utf-8", "replace")[-400:])}
    return json.loads(_html.unescape(m.group(1)))


def problems(report: dict, text: str = "") -> list[str]:
    """Kaatavat loydokset. Ellipsi ei kaada: se on suunniteltu katkaisu."""
    out = []
    if report.get("error"):
        out.append(report["error"])
    out += ["valuu yli: " + x for x in report.get("outside", [])]
    out += ["leikkautuu ilman ellipsia: " + x for x in report.get("clipped", [])]
    out += ["fontti ei latautunut: " + x for x in report.get("fonts", [])]
    if report.get("card") and [round(v) for v in report["card"]] != list(KOKO):
        out.append("kortin koko %s, odotettu %s" % (report["card"], KOKO))
    miss = uncovered_chars(text)
    if miss:
        out.append("merkit ilman upotettua glyfia: %s" % " ".join(
            "%s(U+%04X)" % (c, ord(c)) for c in miss))
    return out


class CardLayoutError(RuntimeError):
    pass


def render_card(exe: str, html_path: Path, png_path: Path,
                size: tuple[int, int] = KOKO) -> dict:
    """Mittaa ja kuvaa. Kaatava loydos -> CardLayoutError eika PNG:ta.

    Vanha PNG poistetaan ENSIN: muuten epaonnistunut ajo jattaisi edellisen
    kuvan paikalleen, ja `publish_cards_to_site` julkaisisi sen tuoreena.
    """
    png_path.unlink(missing_ok=True)
    report = layout_report(exe, html_path, size)
    vika = problems(report, visible_text(html_path.read_text(encoding="utf-8")))
    if vika:
        raise CardLayoutError(
            f"{html_path.name}: asettelu rikki, PNG:ta ei kirjoitettu:\n  "
            + "\n  ".join(vika))
    subprocess.run(_base_args(exe, size) + [f"--screenshot={png_path}",
                                            html_path.as_uri()],
                   check=True, capture_output=True, timeout=90)
    if not png_path.exists() or png_path.stat().st_size == 0:
        raise CardLayoutError(f"{png_path.name}: Chrome ei kirjoittanut kuvaa")
    for e in report.get("ellipsis", []):
        print(f"::notice::{html_path.name}: katkaistu ellipsilla: {e}")
    return report
