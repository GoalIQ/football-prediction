"""Mitka sivut deploy-verifyn pitaa mitata: NE JOTKA TAMA AJO MUUTTI.

DEPLOY-VERIFY-MUUTTUNEET-SIVUT (10.9.2026). fpl-page-refresh committoi
fpl/defence.html + fpl/stats.html, ja verify sanoi "OK: live-sisalto = repo"
koska se vertasi vain kolmea kiinteaa sivua jotka eivat muuttuneet. hub-deploy
ei kaynnistynyt botin pushista, ja muuttuneet sivut olivat livena vanhoina
kunnes ne dispatchattiin kasin. Vahti oli vihrea tyhjalla vertailulla.

Tama tulostaa verify_live_pages.sh:lle listan: ajon committamat *.html-sivut
(git diff HEAD~1..HEAD) + kiintea ydin, enintaan MAX_PAGES (accuracy-log voi
muuttaa satoja ottelusivuja; niista otetaan deterministinen otos, ydin aina).

    bash scripts/verify_live_pages.sh $(python scripts/verify_targets.py)
"""
from __future__ import annotations

import subprocess
import sys

CORE = ("fpl.html", "index.html", "fpl/xg-leaders.html")
MAX_PAGES = 12


def changed_html(diff_lines: list[str]) -> list[str]:
    out = []
    for line in diff_lines:
        p = line.strip().replace("\\", "/")
        if p.endswith(".html") and not p.startswith(("outputs/", "cos-reports/")):
            out.append(p)
    return out


def targets(diff_lines: list[str], core=CORE, max_pages: int = MAX_PAGES) -> list[str]:
    """Ydin ensin, sitten muuttuneet (deterministisessa jarjestyksessa),
    duplikaatit pois, enintaan max_pages."""
    seen: list[str] = []
    for p in list(core) + sorted(set(changed_html(diff_lines))):
        if p not in seen:
            seen.append(p)
    return seen[:max_pages]


def _git_diff() -> list[str]:
    try:
        out = subprocess.run(["git", "diff", "--name-only", "HEAD~1", "HEAD"],
                             capture_output=True, text=True, check=True).stdout
    except Exception:
        return []
    return out.splitlines()


if __name__ == "__main__":
    print(" ".join(targets(_git_diff())))
