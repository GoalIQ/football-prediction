"""Portti: portin kerran hylkaama sanamuoto ei saa palata toiseen skriptiin.

MITATTU VIKA (4.9.2026, julkaisuportti k2):

    scripts/render_projected_xi_card.py:373  # 3.9 PORTTI: "every gameweek
                                             # scored in public" oli epatosi
    tests/test_projected_xi_card.py:361      assert "scored in public" not in text
    scripts/render_standouts_card.py:342     'every gameweek scored in public'  <- livenä

3.9 hylatty sanamuoto korjattiin YHTEEN generaattoriin ja lukittiin sen omaan
testiin. Sisarkortti julkaisi sen 4.9 kortin PNG:ssa. Hylkays joka asuu yhden
tiedoston kommentissa ei ole portti - se on muistiinpano.

Tama testi lukee `data/rejected_phrases.json`:in ja ajaa sen JOKAISTA
scripts/-skriptia vasten. Se lukee vain merkkijonoliteraaleja (ei kommentteja
eika docstringeja), joten hylkayksen selittaminen ei laukaise porttia, mutta
kovakoodattu proosa laukaisee. Poikkeuslistalle paasee vain perustelun kanssa
(saanto 6a kohta 2).
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "rejected_phrases.json"
SCRIPTS = ROOT / "scripts"
# 10.9 (QUEUE HYLATYT-SANAMUODOT-SRC): copya syntyy myos src/-puolella
# (esim. src/brand.py, src/models/fpl_why_drivers.py PAGE_LEGEND), eika
# hylatty sanamuoto laukaissut porttia siella. Molemmat puut skannataan;
# poikkeus kirjataan rekisteriin polulla ja perustelulla kuten ennenkin.
SCAN_ROOTS = (SCRIPTS, ROOT / "src")
# 16.9: jakokortin saate ei ole Pythonissa. Portti hylkasi sanamuodon "out in
# FPL", ja se asui `web/pro-spa/src/lib/components/Replacements.svelte`:ssa —
# eli tasan pinnalla jota tama testi ei skannannut. Sama luokka kuin 4.9:n
# sisarkortti: hylkays joka ei kata julkaisevaa pintaa ei ole portti.
WEB_ROOT = ROOT / "web" / "pro-spa" / "src"
WEB_SUFFIXES = (".svelte", ".ts")
# 21.9: kasin yllapidetyt julkiset sivut ja llms.txt. Rekisteri itse
# suositteli korvaukseksi "entry 116920 is the squad it actually fields", ja
# sama vaite eli llms.txt:ssa ja predictions.html:ssa - pinnoilla joita
# portti ei skannannut, koska ne eivat ole skripteja. Juuren *.html
# (myos generoidut fpl.html/index.html: vanhentunut generoitu sivu on sama
# julkinen teksti) ja llms.txt, HTML-kommentit pois.
PAGE_FILES = ("*.html", "llms.txt")
NEWLINE = chr(10)


def _registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _docstrings(tree: ast.AST) -> set[int]:
    """Docstring-solmujen id:t: ne selittavat hylkaystä, eivat julkaise sita."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                out.add(id(body[0].value))
    return out


def _literals(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:  # ei tamän portin asia
        return []
    skip = _docstrings(tree)
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in skip]


def _strip_web_comments(text: str) -> str:
    """// ja /* */ pois: hylkayksen SELITTAMINEN ei saa laukaista porttia
    (sama periaate kuin Pythonin docstring-poikkeus yllä). Karkea mutta
    konservatiivinen: poistaa vain kommentteja, ei koskaan koodia."""
    out = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    out = re.sub(r"(?m)^\s*//.*$", " ", out)
    out = re.sub(r"(?m)^\s*\*.*$", " ", out)
    out = re.sub(r"(?s)<!--.*?-->", " ", out)
    return out


def _web_files() -> list[Path]:
    if not WEB_ROOT.exists():
        return []
    return sorted(p for p in WEB_ROOT.rglob("*")
                  if p.suffix in WEB_SUFFIXES and p.is_file())


def _page_files() -> list[Path]:
    return sorted({p for pat in PAGE_FILES for p in ROOT.glob(pat) if p.is_file()})


def _hits(phrase: str) -> list[str]:
    reg = _registry()
    out = []
    for path in sorted(p for root in SCAN_ROOTS for p in root.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if reg.get("poikkeukset", {}).get(rel):
            continue
        if any(phrase.lower() in lit.lower() for lit in _literals(path)):
            out.append(rel)
    for path in _web_files() + _page_files():
        rel = path.relative_to(ROOT).as_posix()
        if reg.get("poikkeukset", {}).get(rel):
            continue
        body = _strip_web_comments(path.read_text(encoding="utf-8"))
        if phrase.lower() in body.lower():
            out.append(rel)
    return out


def test_rekisteri_ei_ole_tyhja() -> None:
    """Ilman tata koko portti menisi lapi tyhjana jos tiedosto tyhjenee."""
    reg = _registry()
    assert len(reg["phrases"]) >= 3
    assert all(p["phrase"] and p["why"] for p in reg["phrases"])


def test_jokaisella_hylkayksella_on_paivays_ja_korvaus() -> None:
    for p in _registry()["phrases"]:
        assert p.get("rejected"), p
        assert p.get("replacement"), f"{p['phrase']}: mika on korvaus?"


def test_poikkeuksella_on_perustelu() -> None:
    for tiedosto, syy in _registry().get("poikkeukset", {}).items():
        assert str(syy).strip(), f"{tiedosto}: poikkeukselle ei ole syyta"
        assert (ROOT / tiedosto).exists(), f"{tiedosto}: poikkeus osoittaa " \
                                           "tiedostoon jota ei ole"


@pytest.mark.parametrize("phrase", [p["phrase"] for p in _registry()["phrases"]])
def test_hylatty_sanamuoto_ei_ole_missaan_skriptissa(phrase: str) -> None:
    osumat = _hits(phrase)
    tiedot = {p["phrase"]: p for p in _registry()["phrases"]}[phrase]
    assert not osumat, (
        f"{phrase!r} on hylatty {tiedot['rejected']} ({tiedot['why']}) mutta "
        f"se on kovakoodattuna: {osumat}. Korvaus: {tiedot['replacement']}. "
        "Jos se on tosi juuri tassa, lisaa tiedosto rekisterin "
        "poikkeuslistalle PERUSTELUN kanssa."
    )


def test_negatiivinen_kontrolli_web_skanneri() -> None:
    """Jos web-tarkistin ei nae kovakoodattua saatetta, portti on koriste
    juuri silla pinnalla jolla 16.9:n vika oli."""
    koodi = NEWLINE.join([
        "<script>",
        '  // PORTTI: "out in FPL" oli vaara sanamuoto',
        "  const a = `x out in FPL, no projection`;",
        "</script>",
    ])
    assert "out in FPL" in _strip_web_comments(koodi), (
        "literaali katosi kommenttien mukana -> portti ei nakisi mitaan")
    pelkka_selitys = NEWLINE.join([
        "<script>",
        '  // selitys: "out in FPL" hylattiin 16.9',
        "</script>",
    ])
    assert "out in FPL" not in _strip_web_comments(pelkka_selitys), (
        "pelkka selitys laukaisisi portin -> hylkaysta ei voisi dokumentoida")


def test_web_skannattavia_tiedostoja_on() -> None:
    """Tyhja tiedostolista tekisi web-portista aanettoman."""
    assert len(_web_files()) >= 50


def test_negatiivinen_kontrolli_skanneri_loytaa_literaalin(tmp_path) -> None:
    """Jos tarkistin ei nae kovakoodattua osumaa, koko portti on koriste."""
    f = tmp_path / "x.py"
    f.write_text('"""scored in public"""\nX = "every gameweek scored in public"\n',
                 encoding="utf-8")
    lits = _literals(f)
    assert any("scored in public" in s for s in lits), lits
    assert not any(s.strip() == "scored in public" for s in lits), \
        "docstringin pitaa jaada pois, muuten selitys laukaisee portin"


def test_julkiset_sivut_ovat_skannattavien_joukossa() -> None:
    """21.9: llms.txt ja kasin yllapidetyt sivut kuuluvat porttiin. Tyhja
    lista tekisi laajennuksesta aanettoman."""
    nimet = {p.name for p in _page_files()}
    assert {"llms.txt", "predictions.html", "creators.html", "faq.html",
            "index.html"} <= nimet
    assert len(nimet) >= 20


def test_negatiivinen_kontrolli_sivuskanneri(tmp_path, monkeypatch) -> None:
    """Kovakoodattu hylatty lause juuren sivulla laukaisee portin, mutta
    HTML-kommentissa selitetty ei."""
    import tests.test_rejected_phrases as t
    (tmp_path / "x.html").write_text(
        "<p>entry 116920 is the squad it actually fields</p>", encoding="utf-8")
    (tmp_path / "y.html").write_text(
        "<!-- hylatty: the squad it actually fields --><p>ok</p>",
        encoding="utf-8")
    monkeypatch.setattr(t, "ROOT", tmp_path)
    monkeypatch.setattr(t, "SCAN_ROOTS", ())
    monkeypatch.setattr(t, "WEB_ROOT", tmp_path / "ei-ole")
    assert t._hits("squad it actually fields") == ["x.html"]
