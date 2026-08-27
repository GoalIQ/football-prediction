# -*- coding: utf-8 -*-
"""VAHTI: CI:ssä ajettava builderi ei saa lukea `data/raw/` suoraan levyltä.

TAUSTA 27.8.2026. `build_team_confidence.py` luki `data/raw/fpl/fixtures.json`
suoraan (`(RAW / "fixtures.json").read_text`). Tiedosto oli Villen koneen
cachessa muttei runnerilla -> FileNotFoundError -> koko fpl-data-refresh
punainen 26.8 19:39 -> 27.8 13:20 (3 ajoa), commit-askel ja GW2-freeze
skipattiin, artefakti jäi 26.8 16:13:een. Sama luokka kuin
[[skripti-toimii-vain-villen-koneella]] ja [[fail-safe-jaatyy-alavirtaan]].

Sääntö: raw-cachea luetaan vain `src/data/fpl_api.py`:n fetchereiden kautta
(ne hakevat verkosta jos tiedostoa ei ole). Tämä testi lukee workflow'ista
mitkä skriptit CI ajaa ja kieltää niiltä suoran RAW-levyluvun.

Poikkeus: jäädytetty 25/26-arkisto (`*.archive.json`, `summary_2526/`) EI
ole cache vaan CI purkaa sen itse askeleessa "Unpack frozen 2025/26 FPL
archive". Testi varmistaa että purkuaskel on yhä workflow'ssa, muuten
poikkeus lakkaa olemasta perusteltu.

Negatiivinen kontrolli: sama tunnistin ajetaan tunnetulle rikkovalle
riville (myös rivinvaihdon yli), jotta tiedetään että se näkee sen minkä
takia se on olemassa.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

# Suora levyluku raw-polusta: RAW-muuttuja, RAW_DATA_DIR tai "data/raw"
# samassa lausekkeessa kuin read_text/open/read_csv/load. Lauseke saa
# jatkua seuraavalle riville.
_RAW_READ = re.compile(
    r"(?:\bRAW\b|RAW_DATA_DIR|data/raw|data\\raw)[\s\S]{0,200}?"
    r"(?:\.read_text\(|\.read_bytes\(|open\(|read_csv\(|read_json\(|json\.load\()"
)
_ARCHIVE_READ = re.compile(r"archive\.json|summary_\{PREV_SEASON\}|summary_2526")

# Skriptit joilla on tietoinen poikkeus. Jokainen rivi = syy.
ALLOW: dict[str, str] = {}


def _ci_scripts() -> set[str]:
    """`python -m scripts.x` ja `python scripts/x.py` workflow-tiedostoista."""
    out: set[str] = set()
    for wf in WORKFLOWS.glob("*.yml"):
        text = wf.read_text(encoding="utf-8", errors="replace")
        out.update(re.findall(r"python(?:3)?\s+-m\s+scripts\.([A-Za-z0-9_]+)", text))
        out.update(re.findall(r"python(?:3)?\s+scripts/([A-Za-z0-9_]+)\.py", text))
    return out


def _detect(source: str) -> list[str]:
    return [m.group(0) for m in _RAW_READ.finditer(source)
            if not _ARCHIVE_READ.search(m.group(0))]


def test_detector_sees_the_line_that_broke_the_pipeline():
    """Negatiivinen kontrolli: tunnistimen on nähtävä 26.8 rivi."""
    broken = 'fx = json.loads((RAW / "fixtures.json").read_text(encoding="utf-8"))'
    assert _detect(broken), "tunnistin ei näe riviä jonka takia se on olemassa"
    broken2 = ('boot = json.loads((config.RAW_DATA_DIR / "fpl" / '
               '"bootstrap_static.json").read_text())')
    assert _detect(broken2)
    # Rivinvaihto lausekkeen keskellä ei saa piilottaa lukua.
    broken3 = ('boot = json.loads((config.RAW_DATA_DIR / "fpl"\n'
               '    / "bootstrap_static.json").read_text(encoding="utf-8"))')
    assert _detect(broken3)
    # Arkistoluku on sallittu (CI purkaa arkiston itse).
    archived = ('boot = json.loads((RAW / f"bootstrap_static_{PREV_SEASON}'
                '.archive.json").read_text())')
    assert not _detect(archived)
    fine = 'boot = fetch_bootstrap()\nfx = fetch_fixtures()'
    assert not _detect(fine)


def test_archive_unpack_step_still_exists():
    """Arkistoluvun poikkeus on perusteltu vain jos CI purkaa arkiston."""
    wf = (WORKFLOWS / "fpl-data-refresh.yml").read_text(encoding="utf-8")
    assert "Unpack frozen 2025/26 FPL archive" in wf


def test_ci_scripts_do_not_read_raw_cache_directly():
    scripts = _ci_scripts()
    assert scripts, "workflow'ista ei löytynyt yhtään skriptiä - regex rikki?"
    offenders = {}
    for name in sorted(scripts):
        path = ROOT / "scripts" / f"{name}.py"
        if not path.exists() or name in ALLOW:
            continue
        hits = _detect(path.read_text(encoding="utf-8", errors="replace"))
        if hits:
            offenders[name] = [h[:120] for h in hits[:3]]
    assert not offenders, (
        "CI-skripti lukee data/raw/ suoraan levyltä (runnerilla tiedostoa ei "
        f"ole, ks. 27.8): {offenders}")


def test_team_confidence_uses_fetchers():
    """Sama asia kohdistettuna: 26.8 rikkoutunut skripti käyttää fetchereitä."""
    src = (ROOT / "scripts" / "build_team_confidence.py").read_text(encoding="utf-8")
    assert "fetch_fixtures()" in src and "fetch_bootstrap()" in src
    assert not _detect(src)
