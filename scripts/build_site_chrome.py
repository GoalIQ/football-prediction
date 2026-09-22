# -*- coding: utf-8 -*-
"""Kasin yllapidettyjen juurisivujen jaettu "runko": ylapalkki, identiteetti-
schema ja erottelurivi. Lahde: `src/site_nav.py` + `src/site_identity.py`.

MIKSI (22.9.2026, web-audit T5 + T7 + brandisekaannus, Villen GO):
generaattorit (fpl.html, fpl/**, predictions/**, ucl/**) kutsuvat samoja
funktioita suoraan. Juurisivut (index.html, predictions.html, faq.html,
career.html ...) yllapidetaan kasin, joten ne saavat saman merkkijonon
GEN-lohkoihin taman skriptin kautta. Ilman tata palkki olisi jalleen
kopioitu kymmeneen tiedostoon, ja juuri se tuotti seitseman eri versiota.

LOHKOT
  SITE-NAV       <body>:n alussa, palkki         (kaikki juurisivut)
  SITE-NAV-CSS   </head>:n edessa, palkin tyyli  (kaikki juurisivut)
  SITE-IDENTITY  Organization (+ WebSite etusivulla)  (IDENTITY_PAGES)
  SITE-DISAMBIG  footerin erottelurivi                (DISAMBIG_PAGES)
  SITE-DISAMBIG-FAQ  faq.html:n nakyva kysymys; FAQPage-JSON-LD:n sama
                 kysymys kirjoitetaan JSON-rakenteeseen (JSON ei salli
                 kommenttimarkkereita).

AJO (idempotentti):
    python -m scripts.build_site_chrome           # kirjoittaa
    python -m scripts.build_site_chrome --check   # exit 1 jos jokin sivu on
                                                  # jaljessa lahteesta

--check on portti (`tests/test_site_chrome.py`): lahteen muutos ilman tata
ajoa kaataa testin, joten sivut eivat voi jaada eri versioon hiljaa.
Fail-closed: puuttuva markkeri kaataa ajon eika ohita sivua.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import site_identity as SI  # noqa: E402
from src import site_nav as SN  # noqa: E402
from src.copy_stamp import HASH_RE, paivita_leima  # noqa: E402

#: Kokonaan generoidut juurisivut: palkki tulee builderista, ei taalta.
FULLY_GENERATED = {"fpl.html": "scripts/build_fpl_page.py render_page()"}

#: Juurisivut joille palkkia EI laiteta. Perustelu pakollinen (CLAUDE.md
#: 6a, mekanismi 2): uusi sivu saa palkin oletuksena.
NAV_EXEMPT = {
    "reset-password.html": (
        "Salasanan palautus sahkopostin linkista. Kayttaja on keskella "
        "sovelluksen tilinhallintaa; palkin 'Try Premium' ja osiolinkit "
        "veisivat pois tehtavasta. Ei sitemapissa."),
    "subscription-managed.html": (
        "Stripe-portaalin paluusivu joka ohjaa heti takaisin sovellukseen "
        "(goaliq://). Sivu nakyy sekunnin. Ei sitemapissa."),
}

#: Sivu -> korostettu osio. Oletus None (ei korostusta).
ACTIVE = {
    "predictions.html": "predictions",
    "world-cup-2026-predictions.html": "predictions",
    "career.html": "fpl",
}

#: Organization-lohko (+WebSite). True = myos WebSite (vain etusivu).
IDENTITY_PAGES = {"index.html": True, "predictions.html": False,
                  "faq.html": False}

#: Footerin erottelurivi: sivut joilla brandihaku laskeutuu (etusivu,
#: /predictions sijalla 7 vedonlyontihaulle, /faq jossa sama asia pitkana).
DISAMBIG_PAGES = ("index.html", "predictions.html", "faq.html")

FAQ_PAGE = "faq.html"
FAQ_BEGIN = "<!-- GEN:SITE-DISAMBIG-FAQ-START src/site_identity.py renders this; do not edit by hand -->"
FAQ_END = "<!-- GEN:SITE-DISAMBIG-FAQ-END -->"


def nav_pages() -> list[str]:
    """Juurisivut jotka saavat palkin. JOHDETTU, ei kasin listattu: uusi
    juurisivu saa palkin oletuksena (sama periaate kuin apply_mobile_css).
    Sivut ilman omaa <style>-elementtia ovat uudelleenohjaustynkia."""
    out = []
    for p in sorted(ROOT.glob("*.html")):
        n = p.name
        if n in FULLY_GENERATED or n in NAV_EXEMPT or n.startswith("_"):
            continue
        if "</style>" not in p.read_text(encoding="utf-8"):
            continue
        out.append(n)
    return out


def _fill(txt: str, begin: str, end: str, content: str, where: str,
          inline: bool = False) -> str:
    a = txt.find(begin)
    b = txt.find(end)
    if a < 0 or b < 0 or b < a:
        raise SystemExit(
            f"build_site_chrome: {where}: markkeri puuttuu "
            f"({begin[:40]}... / {end}). Lisaa lohko sivulle, ala ohita.")
    if txt.count(begin) != 1 or txt.count(end) != 1:
        raise SystemExit(f"build_site_chrome: {where}: markkeri useammin kuin kerran")
    sep = "" if inline else "\n"
    return txt[:a + len(begin)] + sep + content + sep + txt[b:]


def faq_details_html() -> str:
    return (
        f'    <details id="{SI.DISAMBIG_ANCHOR}">\n'
        f"      <summary>{SI.DISAMBIG_QUESTION}</summary>\n"
        f"      <div>\n        <p>{SI.DISAMBIG_ANSWER}</p>\n      </div>\n"
        "    </details>"
    )


_LD_RE = re.compile(r'(<script type="application/ld\+json">\n)(.*?)(\n</script>)', re.S)


def _faq_jsonld(txt: str) -> str:
    """Varmista etta FAQPage-JSON-LD sisaltaa erottelukysymyksen tasmalleen
    lahteen sanoin, toiseksi kysymykseksi ("What is GoalIQ?":n jalkeen).
    Rakenteinen data vaatii etta vastaus on myos sivulla nakyvissa; se
    tulee SITE-DISAMBIG-FAQ-lohkosta samasta vakiosta."""
    for m in _LD_RE.finditer(txt):
        try:
            obj = json.loads(m.group(2))
        except ValueError:
            continue
        if not isinstance(obj, dict) or obj.get("@type") != "FAQPage":
            continue
        ents = [e for e in obj.get("mainEntity", [])
                if e.get("name") != SI.DISAMBIG_QUESTION]
        pos = next((i + 1 for i, e in enumerate(ents)
                    if e.get("name") == "What is GoalIQ?"), 0)
        ents.insert(pos, SI.disambig_faq_entity())
        obj["mainEntity"] = ents
        new = json.dumps(obj, ensure_ascii=False, indent=1)
        return txt[:m.start(2)] + new + txt[m.end(2):]
    raise SystemExit("build_site_chrome: faq.html: FAQPage-JSON-LD puuttuu")


def render(name: str, txt: str) -> str:
    if name in nav_pages():
        # 🔴 SAMALLE RIVILLE markkerien kanssa, ja lohko on headissa ENNEN
        # sivun omaa <style>-elementtia. `apply_mobile_css` liittaa
        # MOBILE-CSS:n viimeiseen </style>:iin jonka rivilla EI ole "GEN:".
        # Omalla rivillaan tama lohko olisi ollut juuri se: MOBILE-CSS olisi
        # mennyt taman GEN-lohkon sisaan ja seuraava ajo olisi pyyhkinyt sen
        # (muisti: css-meni-gen-lohkoon-ja-builderi-pyyhki). Mitattu 22.9
        # `apply_mobile_css --check`illa ennen korjausta.
        txt = _fill(txt, SN.CSS_BEGIN, SN.CSS_END, SN.site_nav_style(), name,
                    inline=True)
        txt = _fill(txt, SN.BEGIN, SN.END, SN.site_nav_html(ACTIVE.get(name)), name)
    if name in IDENTITY_PAGES:
        txt = _fill(txt, SI.IDENTITY_BEGIN, SI.IDENTITY_END,
                    SI.identity_block(IDENTITY_PAGES[name]), name)
    if name in DISAMBIG_PAGES:
        txt = _fill(txt, SI.DISAMBIG_BEGIN, SI.DISAMBIG_END,
                    SI.footer_disambig_html(), name)
    if name == FAQ_PAGE:
        txt = _fill(txt, FAQ_BEGIN, FAQ_END, faq_details_html(), name)
        txt = _faq_jsonld(txt)
    # Copyn tuoreusleima samassa kirjoituksessa (src/copy_stamp.py): jos
    # erottelukysymys tai footerin rivi muuttuu, faq.html:n "Last updated"
    # ei saa jaada jalkeen. VAIN sivuilla joilla on jo tiiviste
    # (data-copy-hash): privacy.html:n ja delete-account.html:n "Last updated"
    # on juridinen paivays, eika palkin muutos saa siirtaa sita (mitattu
    # 22.9: ilman rajausta molemmat olisivat saaneet taman paivan).
    if HASH_RE.search(txt):
        txt, _ = paivita_leima(txt)
    return txt


def pages() -> list[str]:
    return sorted(set(nav_pages()) | set(IDENTITY_PAGES) | set(DISAMBIG_PAGES)
                  | {FAQ_PAGE})


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    check = "--check" in argv
    jaljessa = []
    for name in pages():
        p = ROOT / name
        old = p.read_text(encoding="utf-8")
        new = render(name, old)
        if new == old:
            continue
        jaljessa.append(name)
        if not check:
            p.write_text(new, encoding="utf-8", newline="\n")
    if check and jaljessa:
        print("build_site_chrome --check: jaljessa lahteesta: " + ", ".join(jaljessa))
        print("Aja: python -m scripts.build_site_chrome")
        return 1
    print(f"build_site_chrome: {'tarkistettu' if check else 'kirjoitettu'} "
          f"{len(pages())} sivua, muuttui {len(jaljessa)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
