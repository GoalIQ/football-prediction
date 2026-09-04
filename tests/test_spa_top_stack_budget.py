"""Portti: premiumin ylapino ei saa kasvaa tyokalunavin edelle.

MITATTU VIKA (4.9.2026, kilpailija-UI-auditointi). `pro.goaliq.app`:n
tyokalunavi (`SegmentNav`) oli **938 px** ja ensimmainen tyokalupaneeli
**1 006 px** sivun ylalaidasta 1299x1266-ikkunassa. 1366x768-lapparilla se
tarkoittaa, etta **maksava kayttaja ei nae ilman vieritysta etta tuotteessa on
tyokaluja lainkaan.** Ennen navia renderoityi: brandilohko, tilinapit, kaksi
banneria, alkupera-rivi, mini-liigabanneri ja DefCon-lista 13 rivilla.

Vika ei syntynyt kerralla. Jokainen lohko lisattiin yksi kerrallaan, ja
jokaisella oli oma hyva perustelunsa ("aikakriittinen", "haudattu linkki = ei
kayttajia", "loydettavyys"). Kukaan ei mitannut summaa. Siksi taman portin
muoto on **perusteltu poikkeuslista** (CLAUDE.md saanto 6a kohta 2): uusi
komponentti ei paase navin ylapuolelle vahingossa, koska testi kaatuu ja
kirjoittajan on kirjoitettava tahan miksi se kuuluu sinne.

Kolme vaitetta:
  1. Navin ylapuolella saa olla vain `_ALLOWED_ABOVE_NAV`-listan komponentit.
  2. `Provenance` ja `LeagueBanner` renderoityvat navin JALKEEN.
  3. DefConin 13 rivin lista on kokoontaitettu (`{#if expanded}`), eli vain
     yhteenvetorivi on navin ylapuolella.

Ja `+page.svelte`:ssa SPL-nosto on `ToolsHome`:n jalkeen.

Jokaiselle on negatiivinen kontrolli: tarkistin ajetaan muokattuun tekstiin ja
sen ON kaaduttava. Ilman sita portti voisi olla inertti (muisti:
gate-substring-osuma-on-sokea).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SPA = Path(__file__).resolve().parents[1] / "web" / "pro-spa" / "src"
TOOLS_HOME = SPA / "lib" / "components" / "ToolsHome.svelte"
PAGE = SPA / "routes" / "+page.svelte"
DEFCON = SPA / "lib" / "components" / "DefConLive.svelte"

# Komponentit jotka SAAVAT renderoitya tyokalunavin ylapuolella, ja miksi.
# Lisays tahan on tietoinen paatos ja nakyy diffissa.
_ALLOWED_ABOVE_NAV: dict[str, str] = {
    # Ostopolku: nama korvaavat koko tyokalunakyman (upgradeOpen-haara), eivat
    # tyonna sita alaspain.
    "PremiumPreview": "upgrade-nakyma korvaa tyokalut, ei lisaa niiden paalle",
    "LoginBox": "upgrade-nakyma korvaa tyokalut, ei lisaa niiden paalle",
    "Paywall": "upgrade-nakyma korvaa tyokalut, ei lisaa niiden paalle",
    # Kertaluontoinen toimenpide web-ostajalle: ilman tata han ei paase
    # kirjautumaan uudelleen. Piilottaa itsensa kun salasana on asetettu.
    "SetPassword": "kertaluontoinen pakollinen toimenpide web-ostajalle",
    # Aikakriittinen live-signaali kesken kierroksen. Sallittu VAIN koska
    # lista on kokoontaitettu: navin ylapuolelle jaa yksi yhteenvetorivi.
    # Ks. vaite 3 alla - se pitaa taman poikkeuksen rehellisena.
    "DefConLive": "aikakriittinen, ja lista on kokoontaitettu (ks. test_defcon_lista_on_kokoontaitettu)",
    # Navi itse.
    "SegmentNav": "tama on navi",
}

_COMPONENT_RE = re.compile(r"<([A-Z][A-Za-z0-9_]*)\b")


def _read(path: Path) -> str:
    if not path.exists():  # pragma: no cover - SPA-lahde puuttuu koneelta
        pytest.skip("SPA-lahdetta ei ole talla koneella")
    return path.read_text(encoding="utf-8")


def _markup(text: str) -> str:
    """Templaatti ilman <script>- ja <style>-lohkoja."""
    body = text.split("</script>", 1)[-1]
    return body.split("<style>", 1)[0]


def _components_above_nav(text: str) -> list[str]:
    markup = _markup(text)
    idx = markup.find("<SegmentNav")
    assert idx != -1, "SegmentNav puuttuu ToolsHomesta - portti mittaisi tyhjaa"
    return _COMPONENT_RE.findall(markup[:idx])


def _check_above_nav(text: str) -> list[str]:
    """Palauttaa luvattomat komponentit navin ylapuolelta."""
    return sorted({c for c in _components_above_nav(text) if c not in _ALLOWED_ABOVE_NAV})


def _check_after_nav(text: str, component: str) -> bool:
    """True jos komponentti renderoityy VAIN navin jalkeen."""
    markup = _markup(text)
    nav = markup.find("<SegmentNav")
    first = markup.find(f"<{component}")
    return first > nav >= 0


def _check_defcon_collapsed(text: str) -> bool:
    """True jos rivilista on `{#if expanded}` -haaran sisalla."""
    markup = _markup(text)
    guard = markup.find("{#if expanded}")
    lista = markup.find('<ul id="dcl-list"')
    return guard != -1 and lista != -1 and guard < lista


def _check_spl_after_tools(text: str) -> bool:
    markup = _markup(text)
    tools = markup.find("<ToolsHome")
    spl = markup.find('class="spl-note"')
    return tools != -1 and spl > tools


# --------------------------------------------------------------------------
# Vaitteet
# --------------------------------------------------------------------------


def test_navin_ylapuolella_vain_perustellut_komponentit() -> None:
    luvattomat = _check_above_nav(_read(TOOLS_HOME))
    assert not luvattomat, (
        "Nama komponentit renderoityvat tyokalunavin YLAPUOLELLA: "
        f"{luvattomat}. Mitattu 4.9.2026: jokainen lohko navin edessa tyontaa "
        "tyokalut kauemmas, ja summa oli 938 px. Jos lohko kuuluu sinne, "
        "lisaa se _ALLOWED_ABOVE_NAV-listaan PERUSTELUN kanssa; muuten "
        "siirra se navin alle."
    )


def test_alkupera_ja_liigabanneri_ovat_navin_jalkeen() -> None:
    text = _read(TOOLS_HOME)
    for component in ("Provenance", "LeagueBanner"):
        assert _check_after_nav(text, component), (
            f"{component} renderoityy ennen tyokalunavia. Kumpikaan ei ole "
            "aikakriittinen: alkupera on luottamusrivi ja mini-liiga on "
            "kausipitka kutsu. Molemmat kuuluvat tyokalujen jalkeen."
        )


def test_defcon_lista_on_kokoontaitettu() -> None:
    assert _check_defcon_collapsed(_read(DEFCON)), (
        "DefConin rivilista ei ole `{#if expanded}` -haaran takana. "
        "DefConLive on sallittu navin ylapuolella VAIN silla ehdolla, etta "
        "sielta nakyy yksi yhteenvetorivi eika 13 rivin lista (~450 px)."
    )


def test_spl_nosto_on_tyokalujen_jalkeen() -> None:
    assert _check_spl_after_tools(_read(PAGE)), (
        "SPL-nosto renderoityy ennen tyokaluja. Se on kausipitka nosto, ei "
        "aikakriittinen - kuuluu tyokalujen alle."
    )


# --------------------------------------------------------------------------
# Negatiiviset kontrollit: portin on kaaduttava kun vika tuodaan takaisin
# --------------------------------------------------------------------------


def test_negatiivinen_kontrolli_uusi_komponentti_navin_ylle() -> None:
    text = _read(TOOLS_HOME)
    rikottu = text.replace("<SegmentNav", "<UusiBanneri />\n<SegmentNav", 1)
    assert "UusiBanneri" in _check_above_nav(rikottu), (
        "Portti ei huomannut navin ylapuolelle lisattya komponenttia."
    )


def test_negatiivinen_kontrolli_provenance_takaisin_ylos() -> None:
    text = _read(TOOLS_HOME)
    rikottu = text.replace("<SegmentNav", "<Provenance />\n<SegmentNav", 1)
    assert not _check_after_nav(rikottu, "Provenance"), (
        "Portti ei huomannut Provenancen paluuta navin ylapuolelle."
    )


def test_negatiivinen_kontrolli_defcon_lista_auki() -> None:
    text = _read(DEFCON)
    rikottu = text.replace("{#if expanded}", "{#if true}")
    assert not _check_defcon_collapsed(rikottu), (
        "Portti ei huomannut etta kokoontaitto poistettiin."
    )


def test_negatiivinen_kontrolli_spl_takaisin_ylos() -> None:
    text = _read(PAGE)
    rikottu = text.replace("<main>", '<p class="spl-note"></p>\n<main>', 1)
    assert not _check_spl_after_tools(rikottu), (
        "Portti ei huomannut SPL-noston paluuta tyokalujen edelle."
    )
