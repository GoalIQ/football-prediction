"""SEO-404-FALLBACK kohta 3: 301-kartta commitin 6908a643 rename-pareista.

Commit 6908a643 (5.8.2026, #229 F1+F2) nimesi uudelleen 1 360 ottelusivua
neljassa liigassa (la-liga 380, serie-a 380, ligue-1 306, bundesliga 294)
ilman yhtaan uudelleenohjausta. Vanhat URLit palauttavat CF Pagesin
SPA-fallbackin takia etusivun 200:lla -> 1 360 soft-404:aa (viikkoauditointi
2026-08-19, F1).

Tama skripti johtaa kartan MEKAANISESTI, ei kasityona:
- vanhat polut  = commitin poistolista (git, taman repon historia)
- joukkuenimet  = vanhan sivun <title> parent-commitissa
                  ("HOME vs AWAY Prediction - LIIGA | GoalIQ")
- uusi slug     = nykyisen generaattorin oma logiikka
                  (scripts.slugs.slug + DISPLAY_NAMES), EI kopioitu kaava —
                  jos generaattori muuttuu, tama skripti seuraa perassa.

FAIL-CLOSED: jokaisen vanhan polun on tuotettava uusi polku joka on
commitin LISAYSLISTASSA (eli sivu jonka rename todella loi). Yksikin
osumaton pari kaataa ajon — vajaata karttaa ei kirjoiteta.

Tuloste: _redirects (CF Pages -muoto, extensionless-polut; CF:n oma 308
normalisoi .html-pyynnot extensionlessiksi ennen naita saantoja).
Staattisia riveja saa olla enintaan 2000; 1360 mahtuu, ja raja
tarkistetaan ajossa.

Ajo:  .venv/Scripts/python.exe scripts/build_seo_redirects.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from scripts.build_prediction_pages import (  # noqa: E402
    DISPLAY_NAMES,
    DISPLAY_NAME_COMPS,
)
from scripts.slugs import slug  # noqa: E402

RENAME_COMMIT = "6908a6439ee9c7d3369253d862b4202719d30fd7"
OUT_PATH = config.PROJECT_ROOT / "_redirects"
CF_STATIC_LIMIT = 2000

# Liigahakemisto -> onko DISPLAY_NAMES kaytossa (sama rajaus kuin
# generaattorissa: PL/BSA-URLeja ei liikutettu eika niita ole D-listalla).
LEAGUE_DIRS_WITH_DISPLAY = {"la-liga", "serie-a", "ligue-1", "bundesliga"}
assert len(DISPLAY_NAME_COMPS) == len(LEAGUE_DIRS_WITH_DISPLAY)

TITLE_RE = re.compile(r"<title>(.*?) vs (.*?) Prediction – ", re.DOTALL)


def _name_status() -> tuple[list[str], set[str]]:
    raw = subprocess.run(
        ["git", "show", RENAME_COMMIT, "--name-status", "--format="],
        cwd=config.PROJECT_ROOT, capture_output=True, check=True,
    ).stdout.decode("utf-8", errors="replace")
    deleted, added = [], set()
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) != 2 or not parts[1].startswith("predictions/"):
            continue
        if not parts[1].endswith(".html") or parts[1].endswith("index.html"):
            continue
        if parts[0] == "D":
            deleted.append(parts[1])
        elif parts[0] == "A":
            added.add(parts[1])
    return deleted, added


def _old_title_names(path: str) -> tuple[str, str]:
    html = subprocess.run(
        ["git", "show", f"{RENAME_COMMIT}^:{path}"],
        cwd=config.PROJECT_ROOT, capture_output=True, check=True,
    ).stdout.decode("utf-8", errors="replace")
    m = TITLE_RE.search(html)
    if not m:
        raise SystemExit(f"VIRHE: title ei jasenny: {path}")
    return m.group(1).strip(), m.group(2).strip()


def main() -> int:
    deleted, added = _name_status()
    print(f"poistettuja ottelusivuja {len(deleted)}, lisattyja {len(added)}")
    if len(deleted) != 1360:
        raise SystemExit(f"VIRHE: odotettu 1360 poistettua, saatiin {len(deleted)}")

    rows: list[tuple[str, str]] = []
    for old in deleted:
        league_dir = old.split("/")[1]
        if league_dir not in LEAGUE_DIRS_WITH_DISPLAY:
            raise SystemExit(f"VIRHE: odottamaton liigahakemisto: {old}")
        home, away = _old_title_names(old)
        new_name = (f"{slug(DISPLAY_NAMES.get(home, home))}-vs-"
                    f"{slug(DISPLAY_NAMES.get(away, away))}.html")
        new = f"predictions/{league_dir}/{new_name}"
        if new not in added:
            raise SystemExit(
                f"VIRHE: johdettu kohde ei ole commitin lisayslistassa:\n"
                f"  {old}\n  -> {new}\n  ({home} / {away})")
        rows.append((old[:-len(".html")], new[:-len(".html")]))

    # Sama vanha URL ei saa esiintya kahdesti (kartta olisi moniselitteinen).
    if len({o for o, _ in rows}) != len(rows):
        raise SystemExit("VIRHE: duplikaatti vanhoissa poluissa")
    if len(rows) > CF_STATIC_LIMIT:
        raise SystemExit(f"VIRHE: {len(rows)} rivia > CF-raja {CF_STATIC_LIMIT}")

    lines = [
        "# 301-kartta commitin 6908a643 uudelleennimeamille ottelusivuille.",
        "# GENEROITU: scripts/build_seo_redirects.py - ala muokkaa kasin.",
    ]
    lines += [f"/{o} /{n} 301" for o, n in rows]
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Kirjoitettu: {OUT_PATH} ({len(rows)} saantoa)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
