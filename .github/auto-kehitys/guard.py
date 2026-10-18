"""Auto-kehityksen kieltoportti (16.10.2026).

Agentti ei voi itse pushata eikä avata PR:ää: se ajetaan työssä, jonka
GitHub-token on vain luku. Julkaisutyö ajaa TÄMÄN tiedoston mainin versiosta
(`git show origin/main:.github/auto-kehitys/guard.py`) ennen pushia, joten
agentti ei voi löysätä porttia muokkaamalla sitä omalla haarallaan.

Profiilit:
  kehitys      auto-kehitys.yml: koodi, testit, SPA, generoidut sivut, backlog
  aallonharja  aallonharja.yml: vain benchmark, backlog ja FPL-skeeman tilannekuva

Käyttö:
  python guard.py --profile kehitys --base origin/main --head HEAD
Exit 0 = läpi, 1 = rikkomus, 3 = tyhjä muutos (ei committeja).
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys

# Sallitut polut profiileittain. Kielletty-lista voittaa aina.
SALLITUT = {
    "kehitys": (
        "api/*", "src/*", "scripts/*", "tests/*",
        "web/pro-spa/src/*", "web/pro-spa/static/*", "web/pro-spa/scripts/*",
        "fpl/*", "predictions/*", "*.html", "llms.txt", "sitemap*.xml", "ref-bridge.js",
        "docs/AUTO-BACKLOG.md",
    ),
    "aallonharja": (
        "docs/BENCHMARK.md", "docs/AUTO-BACKLOG.md", "data/fpl_schema_snapshot.json",
    ),
}

# Perustelu jokaiselle: miksi agentti ei koske tähän ilman ihmistä.
KIELLETYT = {
    ".github/*": "työnkulut ja tämä portti: vain ihminen",
    "docs/TUOTEPERIAATTEET.md": "tuoteperiaatteet: vain ihminen",
    "CLAUDE.md": "projektiohje: vain ihminen",
    "render.yaml": "tuotantoinfra",
    "requirements*.txt": "uudet riippuvuudet: ihmisen päätös (Render 512 Mi, toimitusketju)",
    "web/pro-spa/package.json": "uudet riippuvuudet: ihmisen päätös",
    "web/pro-spa/package-lock.json": "uudet riippuvuudet: ihmisen päätös",
    "data/*": "bottien tuottama data: muuta tuottajaskriptiä, älä artefaktia",
    "supabase/*": "tietokanta ja auth",
    "cf-worker/*": "julkaistaan käsin",
    "api/premium.py": "maksut ja Premium-oikeudet",
    "src/regional_pricing.py": "hinnat",
    "web/pro-spa/src/routes/checkout/*": "maksut",
    "index.html": "landing ja myyntilupaus (copy-sync-gate, julkaisuportti)",
    "faq.html": "hinnat ja peruutusehdot",
    "creators.html": "kumppaniehdot",
    "privacy.html": "tietosuojaseloste",
    "delete-account.html": "tilin poisto",
    "reset-password.html": "auth",
    "subscription-managed.html": "tilaukset",
    "_redirects": "julkaisun reititys",
    "robots.txt": "hakukoneohjaus",
    "scripts/render_sync_build_filter.py": "tuotantoinfra",
    "scripts/push_site_repo.sh": "julkaisu",
    "src/mailerlite_sync.py": "sähköpostilista ja tervetuloviesti: ihmisen päätös (18.10.2026)",
    "tests/test_auto_kehitys_*": "tämän portin omat testit",
}

# Tarkka polku, joka ohittaa kiellon yhdessä profiilissa. Perustelu on pakollinen.
POIKKEUKSET = {
    "aallonharja": {
        "data/fpl_schema_snapshot.json": "skeemavahdin tilannekuva: sen kirjoittaa vahti, ei agentti",
    },
}

# Lisätyt rivit, joita ei hyväksytä tuotantokoodiin (tests/ ja docs/ ohitetaan).
KIELLETYT_RIVIT = (
    (re.compile(r"(?i)\bstripe\b"), "maksut (Stripe): ihmisen päätös"),
    (re.compile(r"ANTHROPIC_API_KEY|api\.anthropic\.com"), "maksullinen kielimallirajapinta (0 euron sääntö)"),
    (re.compile(r"(?i)uefa\.com"), "UEFAn käyttöehdot 6.2 kieltävät automaattisen keruun"),
    (re.compile(r"(?i)understat\.com"), "Understatin robots.txt: Disallow: / (vain repoon jo committoitu 2025/26-data)"),
    (re.compile(r"€"), "hinta tai raha julkisessa tekstissä: myyntilupaus on ihmisen"),
    (re.compile(r"\b3[.,]99\b"), "Premiumin hinta: myyntilupaus on ihmisen"),
    (re.compile(r"—"), "em dash on kielletty kaikessa tekstissä"),
)
RIVIPORTISTA_VAPAAT = ("tests/*", "docs/*")

# Generoitu tuloste ei kerro työn koosta, joten sitä ei lasketa rajaan.
GENEROIDUT = ("fpl/*", "predictions/*", "*.html", "sitemap*.xml")
RIVIRAJA = {"kehitys": 900, "aallonharja": 1500}


def _osuu(polku: str, kuviot) -> str | None:
    for k in kuviot:
        if fnmatch.fnmatchcase(polku, k):
            return k
    return None


def tarkista_polut(profiili: str, polut: list[str]) -> list[str]:
    virheet = []
    for p in polut:
        if p in POIKKEUKSET.get(profiili, {}):
            continue
        kielto = _osuu(p, KIELLETYT)
        if kielto:
            virheet.append(f"{p}: kielletty ({KIELLETYT[kielto]})")
        elif not _osuu(p, SALLITUT[profiili]):
            virheet.append(f"{p}: ei profiilin '{profiili}' sallituissa poluissa")
    return virheet


def tarkista_rivit(lisatyt: dict[str, list[str]]) -> list[str]:
    virheet = []
    for polku, rivit in lisatyt.items():
        if _osuu(polku, RIVIPORTISTA_VAPAAT):
            continue
        for rivi in rivit:
            for kuvio, syy in KIELLETYT_RIVIT:
                if kuvio.search(rivi):
                    virheet.append(f"{polku}: lisätty rivi osuu kieltoon ({syy}): {rivi.strip()[:120]}")
    return virheet


def tarkista_koko(profiili: str, muutokset: dict[str, int]) -> list[str]:
    yht = sum(n for p, n in muutokset.items() if not _osuu(p, GENEROIDUT))
    raja = RIVIRAJA[profiili]
    if yht > raja:
        return [f"muutoksen koko {yht} riviä ylittää rajan {raja} (generoituja sivuja ei lasketa)"]
    return []


def tarkista(profiili: str, polut: list[str], lisatyt: dict[str, list[str]],
             muutokset: dict[str, int]) -> list[str]:
    if profiili not in SALLITUT:
        return [f"tuntematon profiili {profiili}"]
    return tarkista_polut(profiili, polut) + tarkista_rivit(lisatyt) + tarkista_koko(profiili, muutokset)


def jasenna_diff(diff: str) -> dict[str, list[str]]:
    """git diff -U0 -> {polku: [lisätyt rivit]}."""
    out: dict[str, list[str]] = {}
    nykyinen = None
    for rivi in diff.splitlines():
        if rivi.startswith("+++ "):
            nimi = rivi[4:]
            nykyinen = None if nimi == "/dev/null" else nimi[2:] if nimi.startswith("b/") else nimi
            if nykyinen:
                out.setdefault(nykyinen, [])
        elif rivi.startswith("+") and nykyinen:
            out[nykyinen].append(rivi[1:])
    return out


def jasenna_numstat(numstat: str) -> dict[str, int]:
    out = {}
    for rivi in numstat.splitlines():
        osat = rivi.split("\t")
        if len(osat) != 3:
            continue
        lis, pois, polku = osat
        # Binääritiedostolla numstat antaa "-": lasketaan yhdeksi muutokseksi.
        out[polku] = (int(lis) if lis.isdigit() else 1) + (int(pois) if pois.isdigit() else 0)
    return out


def _git(*args: str) -> str:
    return subprocess.run(("git",) + args, check=True, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True, choices=sorted(SALLITUT))
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    a = ap.parse_args(argv)
    vali = f"{a.base}...{a.head}"
    polut = [p for p in _git("diff", "--name-only", "--no-renames", vali).splitlines() if p]
    if not polut:
        print("Tyhjä muutos: haaralla ei ole muutoksia.")
        return 3
    lisatyt = jasenna_diff(_git("diff", "-U0", "--no-renames", vali))
    muutokset = jasenna_numstat(_git("diff", "--numstat", "--no-renames", vali))
    virheet = tarkista(a.profile, polut, lisatyt, muutokset)
    if virheet:
        print(f"PORTTI HYLKÄSI ({len(virheet)}):")
        for v in virheet:
            print(f"  - {v}")
        return 1
    print(f"Portti läpi: {len(polut)} tiedostoa, profiili {a.profile}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
