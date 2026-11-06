# -*- coding: utf-8 -*-
"""Yksi nappi hubille ja SPA:lle (ulkoasuohjelma WP15 / C2, 6.11.2026).

MITATTU 6.11: hubissa 17 ja SPA:ssa 16 eri CTA-valitsinta. Sama luokka tarkoitti
eri asiaa eri sivuilla: `.btn-ghost` oli landingilla teal-aariviiva ja
predictionsissa harmaa, primary landingilla tayteinen ja /fpl:ssa aariviiva.

PORTTI (CLAUDE.md 6a):
  (1) SPA:n generoitu tiedosto on lahteen tuloste, ei kopio.
  (2) Napin jokainen vari on paletissa (`web/design-tokens.json`).
  (3) Variantin valitsin on kaksoisluokka. Yksinkertainen `.giq-btn--primary`
      haviaisi `.content a{color:...}`-saannolle ja amber-teksti amberilla
      pohjalla katoaisi /fpl:ssa.
  (4) Hubin juurisivulla ja generaattorissa ei ole vanhaa nappiluokkaa eika
      omaa saantoa sille. Uusi vanhan mallin nappi kaataa testin.
  (5) SPA:n myyntinapit kayttavat jaettua nappia.

Kaikkia generoituja sivuja ei lueta: ottelu- ja long tail -sivut paivittyvat
bottiajossa, ja sivun tyyli ja merkkaus tulevat aina samasta generaattorista.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src import site_components as SC
from src.site_nav import SITE_NAV_CSS

ROOT = Path(__file__).resolve().parents[1]
TOKENS = json.loads((ROOT / "web" / "design-tokens.json").read_text(encoding="utf-8"))

OLD = ("btn", "btn-primary", "btn-ghost", "btn-green", "btn-quiet", "btn-secondary", "cta")
GENERATORS = ("scripts/build_fpl_page.py", "scripts/build_fpl_longtail.py",
              "scripts/build_prediction_pages.py", "src/free_window.py",
              "src/partners.py", "scripts/mobile_css.py")
SPA_SALES = ("web/pro-spa/src/lib/components/Paywall.svelte",
             "web/pro-spa/src/lib/components/StoreOnlyNotice.svelte",
             "web/pro-spa/src/lib/components/PremiumPreview.svelte")

_CLASS_RE = re.compile(r"""class=\\?["']([^"'\\]*)\\?["']""")
_RULE_RE = re.compile(r"(?:^|[\s,{}>+~])a?\.(" + "|".join(sorted(map(re.escape, OLD), key=len, reverse=True))
                      + r")(?=[\s,{:.>+~\[])")


def old_classes(src: str) -> list[str]:
    """Vanhat nappiluokat class-attribuuteissa."""
    return [t for m in _CLASS_RE.finditer(src) for t in m.group(1).split() if t in OLD]


def old_rules(css: str) -> list[str]:
    """Vanhat nappivalitsimet tyylissa."""
    return [m.group(1) for m in _RULE_RE.finditer(css)]


def _style_of(path: Path) -> str:
    txt = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        return txt
    return "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", txt, flags=re.S))


def _root_pages() -> list[Path]:
    return [p for p in sorted(ROOT.glob("*.html")) if not p.name.startswith("_")]


def test_spa_tiedosto_on_lahteen_tuloste():
    assert SC.SPA_CSS_PATH.read_text(encoding="utf-8") == SC.spa_css(), (
        "Aja: python -m scripts.build_site_chrome")


def test_spa_lataa_napin_teeman_jalkeen():
    src = (ROOT / "web/pro-spa/src/routes/+layout.svelte").read_text(encoding="utf-8")
    theme = src.find("$lib/theme.css")
    comp = src.find("$lib/giq-components.css")
    assert 0 <= theme < comp


def test_hub_saa_napin_samassa_lohkossa_kuin_palkin():
    assert SC.btn_css() in SITE_NAV_CSS


def test_napin_varit_ovat_paletissa():
    css = SC.btn_css().lower()
    palette = {str(v).lower().replace(" ", "") for v in TOKENS["colors"].values()}
    used = set(re.findall(r"#[0-9a-f]{3,8}\b", css)) | set(re.findall(r"rgba\([^)]*\)", css.replace(" ", "")))
    assert used, "vareja ei loytynyt, onko luku rikki?"
    assert used <= palette, f"paletin ulkopuolella: {sorted(used - palette)}"


@pytest.mark.parametrize("name", sorted(SC.VARIANTS))
def test_variantti_voittaa_sivun_linkkisaannon(name):
    css = SC.btn_css()
    assert f".giq-btn.giq-btn--{name}{{" in css
    assert f".giq-btn.giq-btn--{name}:hover{{" in css
    # Yksinkertainen valitsin olisi (0,1,0) ja havisi `.content a`:lle.
    assert not re.search(rf"(?<!\.giq-btn)\.giq-btn--{name}[{{:]", css)


def test_perusnappi_on_kaksoisluokka_ja_44px():
    css = SC.btn_css()
    assert css.startswith(".giq-btn.giq-btn{")
    assert "min-height:44px" in css


@pytest.mark.parametrize("page", _root_pages(), ids=lambda p: p.name)
def test_juurisivulla_ei_vanhaa_nappia(page):
    txt = page.read_text(encoding="utf-8")
    assert not old_classes(txt), f"{page.name}: {sorted(set(old_classes(txt)))}"
    assert not old_rules(_style_of(page)), f"{page.name}: {sorted(set(old_rules(_style_of(page))))}"


@pytest.mark.parametrize("rel", GENERATORS)
def test_generaattorissa_ei_vanhaa_nappia(rel):
    txt = (ROOT / rel).read_text(encoding="utf-8")
    assert not old_classes(txt), f"{rel}: {sorted(set(old_classes(txt)))}"
    assert not old_rules(txt), f"{rel}: {sorted(set(old_rules(txt)))}"


@pytest.mark.parametrize("rel", SPA_SALES)
def test_spa_myyntinappi_on_jaettu(rel):
    assert "giq-btn giq-btn--" in (ROOT / rel).read_text(encoding="utf-8")


def test_spa_teemassa_ei_vanhaa_linkkinappia():
    css = (ROOT / "web/pro-spa/src/lib/theme.css").read_text(encoding="utf-8")
    assert "a.btn-primary" not in css and "a.btn-secondary" not in css


def test_kontrolli_vanha_merkkaus_ja_saanto_osuvat():
    assert old_classes('<a class="btn btn-primary" href="/">x</a>') == ["btn", "btn-primary"]
    assert old_classes(r'f"<a class=\"cta secondary\">"') == ["cta"]
    assert old_rules(".btn{color:red}") == ["btn"]
    assert old_rules("  .cta:hover { color:red }") == ["cta"]
    assert old_rules("a.cta { color:red }") == ["cta"]
    assert old_rules("h1,.btn,.nav-cta{font:x}") == ["btn"]


def test_kontrolli_sallitut_eivat_osu():
    allowed = ('<a class="giq-btn giq-btn--primary">x</a><div class="cta-row"></div>'
               '<a class="gqn-cta"></a><a class="btn-band"></a><a class="cd-cta"></a>')
    assert old_classes(allowed) == []
    assert old_rules(".cta-row{display:flex}.cta-note{color:red}.btn-band{color:red}"
                     ".nav-cta{color:red}.sticky-cta{color:red}.cd-cta{color:red}") == []
