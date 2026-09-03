# -*- coding: utf-8 -*-
"""SPL-sivun datapohjalause ARTEFAKTISTA, ei kasin (3.9.2026).

MIKSI. `spl.html` on kasin yllapidetty sivu, ja sen datapohjalause sanoi
"fitted on two seasons of SPL results". Malli fittaa nyt kolme kausiavainta
ja 36 pelattua taman kauden ottelua (`data/spl_xp_projections.json` ->
`meta.team_strength_source`, `meta.inseason_matches_in_fit`). Luku oli tosi
kun se kirjoitettiin ja vanheni itsestaan, eika mikaan huutanut.

Sama vikaluokka kuin FPL-sivun nousijavaraus 30.8 ja tests.yml:n
"fitted on 1 match" 28.8: KOVAKOODATTU LUKU joka kuvaa liikkuvaa tilaa.
CLAUDE.md saanto 6a: alä korjaa lukua, poista mahdollisuus kirjoittaa se
kasin. Lause syntyy nyt artefaktista markkerien valiin, ja
`tests/test_spl_page_basis.py` kaatuu jos sivu ja artefakti eroavat.

Ajetaan `fpl-data-refresh.yml`:ssa heti `build_spl_xp`:n jalkeen.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PAGE = ROOT / "spl.html"
XP = ROOT / "data" / "spl_xp_projections.json"
BEGIN = "<!-- GEN:SPL-BASIS -->"
END = "<!-- /GEN:SPL-BASIS -->"


def seasons_and_matches(meta: dict) -> tuple[int, int]:
    """(kausien maara fitissa, taman kauden pelatut ottelut fitissa)."""
    src = str(meta.get("team_strength_source") or "")
    kaudet = len(set(re.findall(r"'(\d{4})'", src)))
    n = meta.get("inseason_matches_in_fit")
    return kaudet, int(n) if isinstance(n, int) else 0


def basis_html(meta: dict) -> str:
    kaudet, inseason = seasons_and_matches(meta)
    sana = {1: "one season", 2: "two seasons", 3: "three seasons",
            4: "four seasons"}.get(kaudet, f"{kaudet} seasons")
    # Kierroksista oppiminen sanotaan aaneen, koska se on eri asia
    # joukkuevoimille ja pelaajaluvuille - ja lukija olettaa muuten saman.
    oppii = (
        f"Team strengths are refitted on every result, so they include "
        f"{inseason} matches already played this season."
        if inseason else
        "Team strengths refit on every result once this season's matches "
        "start landing.")
    return (
        f"{BEGIN}\n"
        "    <p><strong>Data basis:</strong> team strengths come from a "
        "goals-based\n"
        f"    Dixon-Coles model fitted on {sana} of SPL results. {oppii}\n"
        "    No public per-match xG feed exists for this league, so player "
        "attack\n"
        "    projections use realized goal and assist rates. Minutes are the "
        "coarse\n"
        "    part: the RSL Fantasy API publishes season totals and no "
        "per-round\n"
        "    history, so a player's minutes estimate moves with his season "
        "aggregate\n"
        "    rather than with last week. The confidence labels on the tool "
        "say so.</p>\n"
        f"    {END}"
    )


SEASON_WORD = {1: "one season", 2: "two seasons", 3: "three seasons",
               4: "four seasons"}


def sync_faq(html: str, meta: dict) -> str:
    """JSON-LD:n FAQ sanoi saman asian omin sanoin ja vanheni erikseen.
    Sama luku, yksi lahde: sivulla ei saa olla kahta eri kausimaaraa."""
    kaudet, inseason = seasons_and_matches(meta)
    sana = SEASON_WORD.get(kaudet, f"{kaudet} seasons")
    lisa = (f", including {inseason} matches already played this season"
            if inseason else "")
    return re.sub(
        r"fitted on (?:one season|two seasons|three seasons|four seasons|"
        r"\d+ seasons) of Saudi Pro League results"
        r"(?:, including \d+ matches already played this season)?",
        f"fitted on {sana} of Saudi Pro League results{lisa}",
        html)


def main() -> int:
    meta = json.loads(XP.read_text(encoding="utf-8")).get("meta") or {}
    html = PAGE.read_text(encoding="utf-8")
    uusi = basis_html(meta)
    if BEGIN in html and END in html:
        a = html.index(BEGIN)
        b = html.index(END, a) + len(END)
        out = html[:a] + uusi + html[b:]
    else:
        # Ensimmainen ajo: korvataan kasin kirjoitettu kappale markkereilla.
        pat = re.compile(
            r"<p><strong>Data basis:</strong>.*?</p>", re.S)
        if not pat.search(html):
            print("VIRHE: spl.html:sta ei loydy datapohjalausetta eika "
                  "markkereita — sivu on muuttunut, tarkista kasin.")
            return 2
        out = pat.sub(lambda _m: uusi, html, count=1)
    out = sync_faq(out, meta)
    if out == html:
        print("spl.html: datapohjalause oli jo ajan tasalla.")
        return 0
    PAGE.write_text(out, encoding="utf-8")
    kaudet, inseason = seasons_and_matches(meta)
    print(f"spl.html: datapohjalause paivitetty ({kaudet} kautta, "
          f"{inseason} taman kauden ottelua fitissa).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
