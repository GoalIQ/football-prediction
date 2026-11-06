# -*- coding: utf-8 -*-
"""Yksi varilahde kaikille pinnoille (ulkoasuohjelma WP7, 5.11.2026).

MITATTU 5.11: paletti oli samoissa arvoissa ~3 300 hub-sivulla, SPA:n
theme.css:ssa ja sovelluksen lib/theme.ts:ssa, mutta mikaan ei pitanyt sita
niin. Kolme kertaa aiemmin sama vikaluokka eli hiljaa:
  - 1.8 magenta "poistettiin", mutta 24 rgba-literaalia ohitti tokenit;
  - 1.11 --ok/--bad olivat kaytossa mutta maarittelematta -> vaalean teeman
    fallbackit AA:n alla (tests/test_spa_status_tokens.py);
  - --s-5 puuttui -> neljan komponentin margin katosi.
5.11 SPA:ssa oli viela 31 var()-viittausta maarittelemattomiin tokeneihin
(--teal, --muted, --muted-fg, --surface-alt, --line, --amber). Selain kaytti
joka kerta komponentin omaa fallbackia, eli vari oli kovakoodattu vaikka
koodi naytti tokenilta. Kaksi niista oli paletin ulkopuolella (#2a2724 ja
0.13-alfa, kaksi eri sisaviivan harmaata).

PORTTI (CLAUDE.md 6a): web/design-tokens.json on lahde (web/ ei julkaistu hubiin).
  (1) SPA:n theme.css:n brandimuuttujat == tokens.json.
  (2) SPA:n jokainen var(--x) viittaa maariteltyyn tokeniin (theme.css tai
      sama tiedosto). Fallback ei saa kantaa varia hiljaa.
  (3) Jokaisen julkaistun hub-sivun :root-varit ovat paletissa.
  (4) Sovelluksen giq-paletti == tokens.json (vain kun goaliq-app on
      sisarhakemistossa; CI:ssa skip, ks. test_chip_ev_render_claims).
  (5) SPA-komponentin tyylissa ei ole paletin hexia suoraan (kayta var()),
      paitsi perustellut poikkeukset alla.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOKENS = json.loads((ROOT / "web" / "design-tokens.json").read_text(encoding="utf-8"))
COLORS = TOKENS["colors"]
SPA = ROOT / "web" / "pro-spa" / "src"
THEME = SPA / "lib" / "theme.css"
APP_THEME = ROOT.parent / "goaliq-app" / "lib" / "theme.ts"

#: Hub-sivujen :root-arvot jotka eivat ole paletissa, perusteluineen.
HUB_ROOT_POIKKEUKSET: dict[tuple[str, str], str] = {
    ("reset-password.html", "rgba(10,8,32,0.14)"):
        "Supabasen salasanan palautussivu, vanha vaalea pohja; ei linkitetty "
        "hubista, kayttaja tulee vain sahkopostin linkista. Uudistetaan C-osassa.",
}

#: SPA-tiedostot joissa paletin hex saa olla suoraan, perusteluineen.
SPA_HEX_POIKKEUKSET: dict[str, str] = {
    "lib/shareCard.ts": "Canvas-piirto: ctx.fillStyle ei lue CSS-muuttujia.",
    "lib/components/Hero.svelte": "SVG-merkin fill-attribuutti (logo), ei tyylia.",
    "lib/components/GoalsXgChart.svelte": "Kommentti joka dokumentoi mitatun kontrastin.",
    "routes/spl/+page.svelte": "Kommentti joka dokumentoi Villen havainnon.",
    "lib/giq-components.css": "Generoitu src/site_components.py:sta. Sama merkkijono kuin hubissa, jossa sivun muuttujat eivat ole yhtenaiset; varit todistetaan paletista testissa test_napin_varit_ovat_paletissa.",
}


def _norm(v: str) -> str:
    v = v.strip().lower().replace(" ", "")
    m = re.fullmatch(r"rgba\((\d+),(\d+),(\d+),([\d.]+)\)", v)
    if m:
        a = float(m.group(4))
        return f"rgba({m.group(1)},{m.group(2)},{m.group(3)},{a:g})"
    return v


PALETTE = {_norm(v) for v in COLORS.values()}


def _root_vars(css: str) -> dict[str, str]:
    out: dict[str, str] = {}
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for blk in re.findall(r":root\s*\{(.*?)\}", css, re.S):
        for name, val in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", blk):
            out[name] = val.strip()
    return out


def _resolve(tok: dict[str, str], name: str, depth: int = 0) -> str:
    v = tok[name]
    m = re.fullmatch(r"var\((--[\w-]+)(?:,.*)?\)", v)
    if m and depth < 10:
        return _resolve(tok, m.group(1), depth + 1)
    return v


def test_tokens_json_on_ehja():
    assert set(TOKENS) >= {"colors", "spa_theme_css", "app_theme_ts_giq"}
    for name, v in COLORS.items():
        assert re.fullmatch(r"#[0-9A-F]{6}|rgba\(\d+,\d+,\d+,[\d.]+\)", v), (name, v)
    for mapping in ("spa_theme_css", "app_theme_ts_giq"):
        for k, ref in TOKENS[mapping].items():
            assert ref in COLORS, f"{mapping}.{k} -> {ref} puuttuu colors-lohkosta"


def test_spa_theme_css_vastaa_lahdetta():
    tok = _root_vars(THEME.read_text(encoding="utf-8"))
    eroja = []
    for var, ref in TOKENS["spa_theme_css"].items():
        if var not in tok:
            eroja.append(f"{var} puuttuu theme.css:sta")
            continue
        got = _norm(_resolve(tok, var))
        if got != _norm(COLORS[ref]):
            eroja.append(f"{var} = {got}, lahde {ref} = {COLORS[ref]}")
    assert not eroja, eroja


def _spa_files() -> list[Path]:
    return [p for ext in ("*.svelte", "*.css", "*.ts") for p in SPA.rglob(ext)
            if "node_modules" not in p.parts]


def test_spa_var_viittaukset_osuvat_maariteltyihin_tokeneihin():
    maaritellyt = set(_root_vars(THEME.read_text(encoding="utf-8")))
    viat = []
    for f in _spa_files():
        t = f.read_text(encoding="utf-8")
        # Tiedoston omat maaritelmat: --x: ... (tyylilohko tai style-merkkijono)
        # ja Sveltén style:--x={...} -direktiivi.
        omat = set(re.findall(r"(--[\w-]+)\s*:", t)) | set(re.findall(r"style:(--[\w-]+)", t))
        for m in re.finditer(r"var\(\s*(--[\w-]+)", t):
            nimi = m.group(1)
            if nimi not in maaritellyt and nimi not in omat:
                rivi = t.count("\n", 0, m.start()) + 1
                viat.append(f"{f.relative_to(SPA).as_posix()}:{rivi} {nimi}")
    assert not viat, (
        "var() viittaa tokeniin jota theme.css ei maarittele, joten selain kayttaa "
        f"fallbackia (= kovakoodattu vari): {viat}")


def _hub_html() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "*.html"], cwd=ROOT, capture_output=True,
                         text=True, check=True, stdin=subprocess.DEVNULL).stdout.split()
    files = [ROOT / f for f in out if not f.startswith(("web/", "tests/", "node_modules/"))]
    assert len(files) > 100, len(files)  # glob ei saa tyhjentya hiljaa
    return files


def test_hub_sivujen_root_varit_ovat_paletissa():
    viat: dict[str, set[str]] = {}
    kaytetyt_poikkeukset = set()
    for f in _hub_html():
        t = f.read_text(encoding="utf-8", errors="replace")
        if ":root" not in t:
            continue
        for name, val in _root_vars(t).items():
            v = _norm(val)
            if not re.match(r"#|rgba?\(", v):
                continue
            avain = (f.name, v)
            if avain in HUB_ROOT_POIKKEUKSET:
                kaytetyt_poikkeukset.add(avain)
                continue
            if v not in PALETTE:
                viat.setdefault(f"{name} {v}", set()).add(f.relative_to(ROOT).as_posix())
    assert not viat, {k: sorted(v)[:5] for k, v in viat.items()}
    vanhentuneet = set(HUB_ROOT_POIKKEUKSET) - kaytetyt_poikkeukset
    assert not vanhentuneet, f"poikkeus ei enaa osu mihinkaan, poista se: {vanhentuneet}"


def test_spa_komponentit_eivat_kovakoodaa_palettia():
    brandi = {v.lower() for v in COLORS.values() if v.startswith("#")}
    viat = []
    for f in _spa_files():
        rel = f.relative_to(SPA).as_posix()
        if f == THEME or rel in SPA_HEX_POIKKEUKSET:
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for h in re.findall(r"#[0-9a-fA-F]{6}\b", line):
                if h.lower() in brandi:
                    viat.append(f"{rel}:{i}: {line.strip()[:90]}")
    assert not viat, viat
    for rel in SPA_HEX_POIKKEUKSET:
        assert (SPA / rel).exists(), f"poikkeuksen tiedosto puuttuu, poista rivi: {rel}"


@pytest.mark.skipif(not APP_THEME.exists(), reason="goaliq-app ei ole sisarhakemistossa (CI)")
def test_sovelluksen_giq_paletti_vastaa_lahdetta():
    t = APP_THEME.read_text(encoding="utf-8")
    m = re.search(r"export const giq = \{(.*?)\}\s*as const", t, re.S)
    assert m, "lib/theme.ts: giq-objektia ei loydy"
    giq = dict(re.findall(r"(\w+)\s*:\s*'(#[0-9A-Fa-f]{6})'", m.group(1)))
    eroja = []
    for key, ref in TOKENS["app_theme_ts_giq"].items():
        if _norm(giq.get(key, "")) != _norm(COLORS[ref]):
            eroja.append(f"giq.{key} = {giq.get(key)}, lahde {ref} = {COLORS[ref]}")
    assert not eroja, eroja


def test_negatiivinen_kontrolli_vanha_fallback_kaatuisi():
    """Portti (2) nakee 5.11:n vian muodon: var(--teal, #2ed6c2) ilman --teal-tokenia."""
    maaritellyt = set(_root_vars(THEME.read_text(encoding="utf-8")))
    assert "--teal" not in maaritellyt and "--line" not in maaritellyt
