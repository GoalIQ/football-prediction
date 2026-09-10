"""YKSI LUKIJA sille, mika repon sisallosta on goaliq.app:n julkista sivustoa.

SITE-REPO-SPLIT vaihe 1 (10.9.2026). Ennen tata tiedostoa sivuston
polkulista eli kolmena `grep -vE`-rivina `hub-deploy.yml`:n sisalla, ja
"mika on julkista" oli vastattavissa vain lukemalla workflow'ta. Kun sama
lista tarvitaan toiseen kohteeseen (site-repo `GoalIQ/goaliq-site`, johon
football-prediction pushaa outputin), kaksi kasin yllapidettya kopiota
ajautuisivat erilleen - sama luokka kuin `test_workflow_deps`:n
"sama lista kuin fpl-data-refreshissa" -kommentti 17.8 (CLAUDE.md 6a).

Siksi:
  * `hub-deploy.yml` kokoaa stagingin `python scripts/site_output.py list`
    -komennolla eika omalla suodattimellaan (portti:
    tests/test_site_output_single_source.py).
  * Sama lista menee seka CF Pagesiin (direct upload) etta site-repoon.
  * `PUBLIC_DATA` on ainoa reitti jolla `data/`-polku paasee sivustolle.
    Jokaisella rivilla on perustelu; rivi ilman perustelua tai olematon
    polku kaataa testin.

Miksi `data/`-polkuja on mukana lainkaan: fpl.html, fpl/points*.html ja
SPA:n /spl-sivu lupaavat lukijalle "Source: data/gw_calls.json in the public
repository" ja linkittavat GitHubiin. Kun football-prediction menee
privaatiksi, ne linkit kuolevat ellei tiedostoja viedä sinne minne linkki
osoittaa. `public_data_url()` on se yksi paikka josta linkin isanta luetaan;
builderit eivat kirjoita osoitetta itse.

Kaytto:
    python scripts/site_output.py list            # polut, yksi per rivi
    python scripts/site_output.py stage <dir>     # kopioi polut hakemistoon
    python scripts/site_output.py check <polku>   # 0 jos polku on sivustoa
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --- Sivuston lahdekoodi ja data EIVAT ole sivustoa -------------------------
# Hakemistot (etuliite) jotka eivat koskaan paady sivustolle.
EXCLUDED_DIRS = (
    "src/", "tests/", "scripts/", "notebooks/", "web/", "data/", "outputs/",
    "logs/", "docs/", "api/", "supabase/", "pages/", ".github/",
    ".devcontainer/",
)
# Tiedostopaatteet jotka eivat koskaan paady sivustolle.
EXCLUDED_SUFFIXES = (
    ".py", ".sql", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".lock",
)
# Juuritason tiedostot jotka eivat ole sivustoa.
EXCLUDED_ROOT_RE = re.compile(
    r"^(\.gitignore|\.gitattributes|CNAME|render\.yaml|requirements.*|"
    r"README.*|DEPLOY\.md|CLAUDE\.md|app\.py|config\.py|bt\.log)$"
)

# --- Poikkeuslista: data-artefaktit joihin julkaistu sivu linkittaa --------
# polku -> perustelu. Hakemisto paattyy kauttaviivaan. Testi vaatii etta
# polku on repossa ja perustelu on vahintaan 20 merkkia.
PUBLIC_DATA: dict[str, str] = {
    "data/gw_calls.json":
        "fpl.html 'Gameweek calls, logged and scored' -taulukon lahde; "
        "sivu lupaa 'Source: data/gw_calls.json in the public repository'.",
    "data/model_squad_frozen/":
        "fpl.html: 'the squad the captain came from'; mallin oma rivi "
        "jaadytettyna ennen deadlinea, yksi tiedosto per kierros.",
    "data/fpl_xp_gw_accuracy.json":
        "fpl.html xP-tarkkuustaulukko + fpl/points*.html 'The second figure "
        "is read from data/fpl_xp_gw_accuracy.json'.",
    "data/fpl_xp_frozen/":
        "fpl.html: 'frozen projections ... each written in a single commit "
        "dated before the deadline' - lupaus vaatii tiedoston JA historian.",
    "data/fpl_elite_managers.json":
        "fpl.html elite ownership -osio: 'Source: data/fpl_elite_managers.json "
        "in the public repository'.",
    "data/fpl_elite_ownership.json":
        "fpl.html elite ownership -taulukot linkittavat tahan tiedostoon.",
    "data/spl_deadline_snapshots/":
        "SPA /spl: 'The archived files are in the public repo, one per "
        "round: data/spl_deadline_snapshots'.",
}

# Isanta johon builderien "Source:"-linkit osoittavat. VAIHE 4 (cutover)
# vaihtaa taman `GoalIQ/goaliq-site`ksi yhdella rivilla; siihen asti se on
# nykyinen julkinen repo, koska site-repoa ei viela ole.
PUBLIC_REPO = "GoalIQ/football-prediction"


def public_data_url(path: str) -> str:
    """GitHub-osoite PUBLIC_DATA-polulle. Hakemisto -> tree, tiedosto -> blob.

    Kaataa ajon jos polku ei ole poikkeuslistalla: builder ei voi linkittaa
    tiedostoon jota site-repo ei kanna.
    """
    key = path if path in PUBLIC_DATA else path.rstrip("/") + "/"
    if key not in PUBLIC_DATA:
        raise KeyError(f"{path!r} ei ole PUBLIC_DATA-listalla (scripts/site_output.py)")
    kind = "tree" if key.endswith("/") else "blob"
    return f"https://github.com/{PUBLIC_REPO}/{kind}/main/{key.rstrip('/')}"


def is_public_data(path: str) -> bool:
    for key in PUBLIC_DATA:
        if key.endswith("/"):
            if path.startswith(key):
                return True
        elif path == key:
            return True
    return False


def is_site_path(path: str) -> bool:
    """Onko gitin seuraama polku osa julkista sivustoa."""
    path = path.replace("\\", "/")
    if is_public_data(path):
        return True
    if path.startswith(EXCLUDED_DIRS):
        return False
    if path.endswith(EXCLUDED_SUFFIXES):
        return False
    if "/" not in path and EXCLUDED_ROOT_RE.match(path):
        return False
    return True


def site_paths(tracked: list[str]) -> list[str]:
    return [p for p in tracked if p and is_site_path(p)]


def tracked_files(root: Path = ROOT) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True, check=True,
    ).stdout.decode("utf-8")
    return [p for p in out.split("\0") if p]


def stage(dest: Path, root: Path = ROOT) -> int:
    n = 0
    for rel in site_paths(tracked_files(root)):
        src = root / rel
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    return n


def main(argv: list[str]) -> int:
    if len(argv) >= 1 and argv[0] == "list":
        sys.stdout.write("\n".join(site_paths(tracked_files())) + "\n")
        return 0
    if len(argv) >= 2 and argv[0] == "stage":
        n = stage(Path(argv[1]))
        print(f"staging: {n} tiedostoa -> {argv[1]}")
        return 0
    if len(argv) >= 2 and argv[0] == "check":
        return 0 if is_site_path(argv[1]) else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
