"""Portti: jokaisella tyokalulla on reitti, otsikko ja kysymys — ja vanha
linkki osuu TYOKALUUN eika ryhmaan.

MITATTU VIKA (4.9.2026, kilpailija-UI-auditointi). Koko premium-tuote oli
yhden URLin takana: `+page.svelte` -> `ToolsHome.svelte`, 24 tyokalua kuudessa
ryhmassa, ja ryhmat olivat hash-tilaa (`#tools=team`) eivat sivuja. Seuraukset
olivat mitattavia: selaimen paluunappi ei liikkunut tyokalujen valilla,
yksittaista tyokalua ei voinut linkittaa eika bookmarkata, millaan nakymalla
ei ollut omaa otsikkoa, ja **19 vanhaa deep-linkkia ohjautui ryhmaan eika
tyokaluun** — linkki "avaa clean sheets" pudotti kayttajan kymmenen tyokalun
pinon ylalaitaan.

Rekisteri `web/pro-spa/src/lib/tools.ts` on saannon 6a kohta 1 mukainen **yksi
lukija**: navi, hakemistokortit, reitit ja vanhojen hashien ohjaus lukevat
kaikki siita. Tama portti pitaa huolen etta lukija ei voi palauttaa vaaraa:

  1. jokaisella tyokalulla on slug, ryhma, otsikko, kysymys, taso ja ankkuri
  2. jokaisen tyokalun ankkuri LOYTYY ToolsHomen markupista (rekisterissa ei
     voi olla tyokalua jota mikaan nakyma ei renderoi)
  3. jokainen ryhma joko sisaltaa tyokaluja tai on perustellulla
     poikkeuslistalla (`GROUPS_WITHOUT_TOOLS`)
  4. kaikki 19 vanhaa hashia ovat tallella ja osoittavat tyokaluun; ryhmaan
     osoittava ohjaus vaatii kirjatun perustelun (`LEGACY_GROUP_TARGETS`)
  5. ToolsHome ei maarittele omaa GROUPS- tai LEGACY_HASH-taulukkoaan

Jokaiselle on negatiivinen kontrolli.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SPA = Path(__file__).resolve().parents[1] / "web" / "pro-spa" / "src"
REGISTRY = SPA / "lib" / "tools.ts"
TOOLS_HOME = SPA / "lib" / "components" / "ToolsHome.svelte"
ROUTE_GROUP = SPA / "routes" / "[group]" / "+page.svelte"
ROUTE_TOOL = SPA / "routes" / "[group]" / "[tool]" / "+page.svelte"

_REQUIRED_FIELDS = ("slug", "group", "title", "question", "tier", "anchor")

# Vanhat `#tools=<id>` -linkit. Lista on tassa erikseen JA rekisterissa: jos
# joku poistaa yhden rekisterista, tama testi kertoo kumpi katosi.
_LEGACY_IDS = [
    "cleansheets",
    "playercard",
    "lookup",
    "rateteam",
    "myteam",
    "fitchecker",
    "value",
    "leaders",
    "differentials",
    "replacements",
    "compare",
    "pricewatch",
    "league",
    "chips",
    "chains",
    "edge",
    "predict",
    "fixtures",
    "standings",
]


def _read(path: Path) -> str:
    if not path.exists():  # pragma: no cover - SPA-lahde puuttuu koneelta
        pytest.skip("SPA-lahdetta ei ole talla koneella")
    return path.read_text(encoding="utf-8")


def _array_body(text: str, name: str) -> str:
    """Palauttaa `export const <name> ... = [ ... ]` -sisallon.

    Huom: hakee sulun VASTA `=`-merkin jalkeen. Ensimmainen `[` on tyypissa
    (`Tool[]`), ja siihen tarttuminen palautti tyhjan taulukon — jolloin
    jokainen vaite meni lapi tyhjana (muisti: kontrolli-lapaisi-tyhjana).
    """
    start = text.index(f"export const {name}")
    eq = text.index("=", start)
    open_bracket = text.index("[", eq)
    depth = 0
    for i in range(open_bracket, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                return text[open_bracket + 1 : i]
    raise AssertionError(f"{name}: sulkeva ] puuttuu")


def _objects(body: str) -> list[str]:
    """Pilkkoo taulukon sisallon ylatason { ... } -lohkoihin."""
    out: list[str] = []
    depth = 0
    start = None
    for i, ch in enumerate(body):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                out.append(body[start : i + 1])
                start = None
    return out


def _field(obj: str, key: str) -> str | None:
    """Kentan arvo joko yksin- tai kaksinkertaisilla lainausmerkeilla.

    🔴 4.9: alkuperainen versio tunsi vain heittomerkit. Kun julkaisuportti
    vaati lyhenteen ("What's coming up..."), kentta piti kirjoittaa
    kaksinkertaisilla — ja portti raportoi sen PUUTTUVANA kenttana. Portti
    olisi siis kaatunut vaarasta syysta, ja pahemmassa suunnassa mikä tahansa
    lainausmerkkityylin vaihto olisi voinut piilottaa oikean puutteen.
    """
    for quote in ("'", '"'):
        m = re.search(rf"\b{key}:\s*\n?\s*{quote}(.*?){quote}", obj, re.S)
        if m:
            return m.group(1)
    return None


def parse_tools(text: str) -> list[dict[str, str | None]]:
    return [
        {k: _field(obj, k) for k in _REQUIRED_FIELDS}
        for obj in _objects(_array_body(text, "TOOLS"))
    ]


def parse_groups(text: str) -> list[str]:
    return [
        g for obj in _objects(_array_body(text, "GROUPS")) if (g := _field(obj, "id"))
    ]


def parse_map(text: str, name: str) -> dict[str, str]:
    start = text.index(f"export const {name}")
    eq = text.index("=", start)
    open_brace = text.index("{", eq)
    depth = 0
    body = ""
    for i in range(open_brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                body = text[open_brace + 1 : i]
                break
    return dict(re.findall(r"(\w+):\s*'([^']*)'", body))


# --------------------------------------------------------------------------
# Tarkistimet (erillisina, jotta negatiiviset kontrollit voivat ajaa ne)
# --------------------------------------------------------------------------


def _missing_fields(text: str) -> list[str]:
    bad = []
    for t in parse_tools(text):
        for k in _REQUIRED_FIELDS:
            if not t.get(k):
                bad.append(f"{t.get('slug') or '?'}.{k}")
    return bad


def _tools_without_markup(registry: str, markup: str) -> list[str]:
    return [
        f"{t['group']}/{t['slug']}"
        for t in parse_tools(registry)
        if t["anchor"] and f'id="{t["anchor"]}"' not in markup
    ]


def _legacy_problems(text: str) -> list[str]:
    mapping = parse_map(text, "LEGACY_HASH_TO_PATH")
    justified = parse_map(text, "LEGACY_GROUP_TARGETS")
    tool_paths = {f"/{t['group']}/{t['slug']}" for t in parse_tools(text)}
    group_paths = {f"/{g}" for g in parse_groups(text)}
    problems = []
    for old in _LEGACY_IDS:
        target = mapping.get(old)
        if not target:
            problems.append(f"{old}: ohjaus puuttuu kokonaan")
        elif target in tool_paths:
            continue
        elif target in group_paths:
            if old not in justified:
                problems.append(f"{old} -> {target}: osoittaa ryhmaan ilman perustelua")
        else:
            problems.append(f"{old} -> {target}: kohde ei ole rekisterissa")
    return problems


# --------------------------------------------------------------------------
# Vaitteet
# --------------------------------------------------------------------------


def test_rekisteri_ei_ole_tyhja() -> None:
    """🔴 Ilman tata jokainen alla oleva vaite menisi lapi tyhjana, jos
    jasennin lakkaa loytamasta taulukkoa (muisti:
    kontrolli-lapaisi-tyhjana). Luvut ovat alarajoja, eivat tarkkoja."""
    text = _read(REGISTRY)
    assert len(parse_tools(text)) >= 20
    assert len(parse_groups(text)) == 6
    assert len(parse_map(text, "LEGACY_HASH_TO_PATH")) == len(_LEGACY_IDS)


def test_jokaisella_tyokalulla_on_kaikki_kentat() -> None:
    puuttuu = _missing_fields(_read(REGISTRY))
    assert not puuttuu, (
        f"Naista tyokaluista puuttuu kentta: {puuttuu}. Tyokalua ei voi lisata "
        "ilman reittia (slug + group), otsikkoa (title) ja yhta lausetta siita "
        "mihin kysymykseen se vastaa (question)."
    )


def test_jokainen_tyokalu_renderoityy_jossain() -> None:
    orvot = _tools_without_markup(_read(REGISTRY), _read(TOOLS_HOME))
    assert not orvot, (
        f"Naiden tyokalujen ankkuria ei loydy ToolsHomesta: {orvot}. Rekisterissa "
        "ei saa olla tyokalua jonka URL avaa tyhjan nakyman."
    )


def test_jokaisella_ryhmalla_on_tyokaluja_tai_perustelu() -> None:
    text = _read(REGISTRY)
    tools = parse_tools(text)
    poikkeukset = set(re.findall(r"'([^']+)'", _array_body(text, "GROUPS_WITHOUT_TOOLS")))
    for g in parse_groups(text):
        if any(t["group"] == g for t in tools):
            continue
        assert g in poikkeukset, (
            f"Ryhmalla '{g}' ei ole yhtaan tyokalua eika sita ole "
            "GROUPS_WITHOUT_TOOLS-listalla perusteluineen."
        )


def test_vanhat_deep_linkit_osuvat_tyokaluun() -> None:
    ongelmat = _legacy_problems(_read(REGISTRY))
    assert not ongelmat, (
        "Vanhojen deep-linkkien ohjaus on rikki: "
        + "; ".join(ongelmat)
        + ". Ennen 4.9 nama osoittivat ryhmaan, jolloin linkki 'avaa clean "
        "sheets' pudotti kayttajan kymmenen tyokalun pinon ylalaitaan."
    )


def test_reitit_ovat_olemassa() -> None:
    for path in (ROUTE_GROUP, ROUTE_TOOL):
        assert path.exists(), f"Reittitiedosto puuttuu: {path}"
    assert "AppShell" in _read(ROUTE_TOOL)


def test_toolshome_ei_maarittele_omaa_navia() -> None:
    markup = _read(TOOLS_HOME)
    assert "$lib/tools" in markup, "ToolsHome ei lue rekisteria"
    for kielletty in ("const GROUPS", "const LEGACY_HASH:"):
        assert kielletty not in markup, (
            f"ToolsHome maarittelee oman {kielletty}-taulukkonsa. Ryhmat ja "
            "vanhojen linkkien ohjaus kuuluvat rekisteriin — kaksi lukijaa "
            "eriytyy ensimmaisessa muutoksessa."
        )


# --------------------------------------------------------------------------
# Negatiiviset kontrollit
# --------------------------------------------------------------------------


def test_negatiivinen_kontrolli_puuttuva_kentta() -> None:
    text = _read(REGISTRY).replace(
        "question: 'Who leads on xG, xA and xGI, with no cut-off?',", "", 1
    )
    assert any(x.endswith(".question") for x in _missing_fields(text)), (
        "Portti ei huomannut puuttuvaa question-kenttaa."
    )


def test_negatiivinen_kontrolli_tyokalu_ilman_markupia() -> None:
    text = _read(REGISTRY).replace("anchor: 'pc-leaders'", "anchor: 'pc-ei-ole'", 1)
    assert "players/leaders" in _tools_without_markup(text, _read(TOOLS_HOME)), (
        "Portti ei huomannut tyokalua jonka ankkuria ei renderoida."
    )


def test_negatiivinen_kontrolli_vanha_linkki_ryhmaan() -> None:
    text = _read(REGISTRY).replace(
        "leaders: '/players/leaders',", "leaders: '/players',", 1
    )
    assert any("leaders" in p for p in _legacy_problems(text)), (
        "Portti ei huomannut vanhaa linkkia joka ohjaa ryhmaan ilman perustelua."
    )


def test_negatiivinen_kontrolli_kadonnut_vanha_linkki() -> None:
    text = _read(REGISTRY).replace("cleansheets: '/players/clean-sheets',", "", 1)
    assert any("cleansheets" in p for p in _legacy_problems(text)), (
        "Portti ei huomannut kadonnutta vanhaa deep-linkkia."
    )
