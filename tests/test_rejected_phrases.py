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
scripts/- JA src/-puun skriptia vasten. Se lukee vain merkkijonoliteraaleja
(ei kommentteja eika docstringeja), joten hylkayksen selittaminen ei
laukaise porttia, mutta kovakoodattu proosa laukaisee. Poikkeuslistalle
paasee vain perustelun kanssa (saanto 6a kohta 2).

LAAJENNUS (7.9.2026, HYLATYT-SANAMUODOT-SRC): skanneri kattoi alun perin
vain `scripts/**.py`, mutta copya syntyy myos `src/`-puolella (esim.
`src/brand.py`) - siella hylatty sanamuoto ei olisi laukaissut porttia.
Skannaus kattaa nyt molemmat, jotta reika ei ole tiedostopolun mukaan
valikoiva.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from tests import test_rejected_phrases as rp

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "rejected_phrases.json"
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"


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


def _skannattavat() -> list[Path]:
    return sorted(SCRIPTS.rglob("*.py")) + sorted(SRC.rglob("*.py"))


def _hits(phrase: str) -> list[str]:
    reg = _registry()
    out = []
    for path in _skannattavat():
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


def test_negatiivinen_kontrolli_skanneri_loytaa_literaalin(tmp_path) -> None:
    """Jos tarkistin ei nae kovakoodattua osumaa, koko portti on koriste."""
    f = tmp_path / "x.py"
    f.write_text('"""scored in public"""\nX = "every gameweek scored in public"\n',
                 encoding="utf-8")
    lits = _literals(f)
    assert any("scored in public" in s for s in lits), lits
    assert not any(s.strip() == "scored in public" for s in lits), \
        "docstringin pitaa jaada pois, muuten selitys laukaisee portin"


def test_src_puu_on_mukana_skannauksessa(tmp_path, monkeypatch) -> None:
    """HYLATYT-SANAMUODOT-SRC (7.9): tama on se kontrolli joka olisi ollut
    tyhja ENNEN laajennusta - `_hits` ei nahnyt yhtaan src/-tiedostoa,
    joten kovakoodattu hylatty sanamuoto siella olisi lapaissyt portin
    hiljaa. Osoitetaan etta `_skannattavat()` todella kavelee `src`-juuren
    (ei vain kansiota jonka nimi sattuu olemaan "src"), monkeypatchaamalla
    moduulin oma SRC-vakio tmp_pathiin."""
    src_root = tmp_path / "src"
    (src_root / "models").mkdir(parents=True)
    huono = src_root / "models" / "brand.py"
    huono.write_text('X = "every gameweek scored in public"\n', encoding="utf-8")

    monkeypatch.setattr(rp, "ROOT", tmp_path)
    monkeypatch.setattr(rp, "SRC", src_root)
    monkeypatch.setattr(rp, "SCRIPTS", tmp_path / "ei_ole_olemassa")

    osumat = rp._hits("scored in public")
    assert osumat == ["src/models/brand.py"], osumat


def test_src_ei_ollut_mukana_ennen_laajennusta_negatiivinen_kontrolli(tmp_path, monkeypatch) -> None:
    """NEGATIIVINEN KONTROLLI edelliselle: toistaa TASMALLEEN saman
    tilanteen mutta ajaa VANHAA `_hits`-muotoa (skannaus vain SCRIPTS-
    listasta, sama kuin ennen 7.9-laajennusta). Sen pitaa OLLA SOKEA src-
    osumalle - jos se nakisi sen, kontrolli itse olisi rikki eika todistaisi
    etta laajennus oli tarpeen."""
    src_root = tmp_path / "src"
    src_root.mkdir()
    (src_root / "brand.py").write_text(
        'X = "every gameweek scored in public"\n', encoding="utf-8")
    scripts_root = tmp_path / "scripts_tyhja"
    scripts_root.mkdir()

    def _hits_vain_scripts(phrase: str) -> list[str]:
        reg = rp._registry()
        out = []
        for path in sorted(scripts_root.rglob("*.py")):  # ei src_roottia!
            rel = path.relative_to(tmp_path).as_posix()
            if reg.get("poikkeukset", {}).get(rel):
                continue
            if any(phrase.lower() in lit.lower() for lit in rp._literals(path)):
                out.append(rel)
        return out

    assert _hits_vain_scripts("scored in public") == [], (
        "kontrolli itse on rikki: vanha yhden-kansion skannaus ei saisi "
        "nahda src/-osumaa lainkaan")
