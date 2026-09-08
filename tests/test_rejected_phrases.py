"""Portti: portin kerran hylkaama sanamuoto ei saa palata toiseen skriptiin.

🔴 8.9.2026: skanneri kavi vain `scripts/**.py` lapi. Copya syntyy myos
`src/`-puolella (esim. `src/brand.py`), eika siella hylatty sanamuoto
laukaissut porttia - sama vikaluokka kuin talla tiedostolla jo kerran
korjattu vika (yksi generaattori vs sisarkortti), mutta nyt hakemiston
tasolla: yksi HAKEMISTO ei riita, jos copya kirjoitetaan kahdessa.

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
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "rejected_phrases.json"
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
SCAN_ROOTS = (SCRIPTS, SRC)


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


def _hits(phrase: str) -> list[str]:
    reg = _registry()
    out = []
    for root in SCAN_ROOTS:
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if reg.get("poikkeukset", {}).get(rel):
                continue
            if any(phrase.lower() in lit.lower() for lit in _literals(path)):
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


def test_src_on_oletus_scan_rootsissa() -> None:
    """8.9: skanneri kavi vain `scripts/**.py` lapi. Tama testi kaataisi
    JOS SRC poistuisi oletus-SCAN_ROOTS-listalta uudelleen - toisin kuin
    seuraava testi, tama ei patchaa SCAN_ROOTSia itse, joten mutaatio
    (SRC:n poisto listalta) nakyy tassa."""
    assert SRC in SCAN_ROOTS


def test_skanneri_kavelee_minka_tahansa_scan_rootin_lapi(tmp_path,
                                                          monkeypatch) -> None:
    """`_hits` ei ole kovakoodattu `scripts/`-hakemistoon: se kavelee
    SCAN_ROOTS-listan jokaisen juuren lapi. Todiste: keksitty juuri jonka
    nimi ei ole 'scripts' tai 'src' loytyy silti."""
    import tests.test_rejected_phrases as mod
    fake_root = tmp_path / "jokin_muu_hakemisto"
    fake_root.mkdir()
    (fake_root / "x.py").write_text(
        'X = "every gameweek scored in public"\n', encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "SCAN_ROOTS", (fake_root,))
    assert "jokin_muu_hakemisto/x.py" in mod._hits("scored in public")


def test_negatiivinen_kontrolli_skanneri_loytaa_literaalin(tmp_path) -> None:
    """Jos tarkistin ei nae kovakoodattua osumaa, koko portti on koriste."""
    f = tmp_path / "x.py"
    f.write_text('"""scored in public"""\nX = "every gameweek scored in public"\n',
                 encoding="utf-8")
    lits = _literals(f)
    assert any("scored in public" in s for s in lits), lits
    assert not any(s.strip() == "scored in public" for s in lits), \
        "docstringin pitaa jaada pois, muuten selitys laukaisee portin"
