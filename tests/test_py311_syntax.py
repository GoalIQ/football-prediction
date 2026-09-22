# -*- coding: utf-8 -*-
"""PYTHON 3.11 -SYNTAKSIPORTTI: lokaali 3.14 hyvaksyy f-stringin jota CI ei.

🔴 MIKSI (22.9): tests.yml oli punainen nelja ajoa putkeen 21.9 illasta.
`tests/test_ucl_no_projection.py:514` kirjoitti f-stringin lausekkeeseen
kenoviivan (`{alku.replace(', ', ',\\n  ', 1)}`). PEP 701 (python 3.12)
salli sen, joten lokaali `.venv` (3.14) ajoi tiedoston vihreana. CI ajaa
3.11:lla ja kaatui SyntaxErroriin jo pytestin KERAYSVAIHEESSA:
"Interrupted: 1 error during collection". Keraysvirhe ei punaa yhta testia
vaan keskeyttaa koko ajon, eli jokainen muu regressio jai samalla
nakymattomiin (16:12 ajossa oli erillinen portti punaisena, eika
myohemmista ajoista voinut lukea oliko se korjautunut).

MIKSI EI `ast.parse(feature_version=(3, 11))`: mitattu 22.9, 3.14 jasentaa
taman tiedoston sillakin virheetta. Feature_version ei kata PEP 701:ta.

KAKSI HAARAA, MOLEMMAT MITTAAVAT OIKEAA ASIAA OMASSA YMPARISTOSSAAN:

  3.11 (CI)   `compile()` jokaiselle seuratulle .py-tiedostolle. Tama on
              oikea kielioppi, ei jaljitelma — ja se kattaa myos scripts/-
              tiedostot joita mikaan testi ei importtaa mutta joita
              workflow't ajavat samalla 3.11:lla.
  3.12+       tokenize-pohjainen tarkistus niille nelja rakenteelle jotka
              PEP 701 salli ja 3.11 ei: kenoviiva lausekkeessa, sama
              lainausmerkki sisakkain, kommentti lausekkeessa, ja
              yksirivisen f-stringin lauseke joka jatkuu seuraavalle
              riville. Taman haaran tehtava on kaataa lokaali ajo ENNEN
              pushia, koska CI-haara nakee vian vasta pushin jalkeen.
"""
from __future__ import annotations

import io
import subprocess
import sys
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

PEP701 = sys.version_info >= (3, 12)


def _tracked_py_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True,
        text=True, check=True).stdout
    return [ROOT / line for line in out.splitlines() if line.strip()]


def _quote_of(fstring_start: str) -> str:
    """`rf'''` -> `'''`, `f"` -> `"`."""
    return fstring_start.lstrip("rRfFbBuU")


def pep701_violations(source: str) -> list[tuple[int, str]]:
    """Palauttaa (rivi, syy) jokaiselle f-stringille jota 3.11 ei jasenna.

    Pino pitaa kirjaa sisakkaisista f-stringeista. `depth` = kuinka monen
    korvauskentan (`{...}`) sisalla ollaan; syvyys > 0 = lausekekoodia,
    jossa 3.11 kieltaa kenoviivan ja kommentin. FSTRING_MIDDLE syvyydella 0
    on tavallista tekstia ja saa sisaltaa kenoviivan.
    """
    if not PEP701:
        return []
    found: list[tuple[int, str]] = []
    # Jokainen pinon alkio: [lainausmerkki, kenttasyvyys, alkurivi]
    stack: list[list] = []
    toks = tokenize.generate_tokens(io.StringIO(source).readline)
    for tok in toks:
        tt, text, (row, _), (erow, _) = tok.type, tok.string, tok.start, tok.end
        in_expr = any(fs[1] > 0 for fs in stack)
        if tt == tokenize.FSTRING_START:
            if in_expr:
                _check_nested_quote(text, stack, row, found)
            stack.append([_quote_of(text), 0, row])
            continue
        if not stack:
            continue
        top = stack[-1]
        if tt == tokenize.FSTRING_END:
            quote, _, start_row = stack.pop()
            if len(quote) == 1 and erow != start_row:
                found.append((start_row, "yksirivinen f-string jatkuu "
                              "usealle riville (3.11: ei sallittu)"))
            continue
        if tt == tokenize.OP and text == "{":
            top[1] += 1
        elif tt == tokenize.OP and text == "}":
            top[1] = max(0, top[1] - 1)
        # in_expr luettiin ennen syvyyden paivitysta: kentan avaava `{`
        # on viela tekstia, sulkeva `}` viela lauseketta.
        if not in_expr:
            continue
        if tt == tokenize.COMMENT:
            found.append((row, "kommentti f-stringin lausekkeessa"))
        elif "\\" in text:
            found.append((row, "kenoviiva f-stringin lausekkeessa"))
        elif tt == tokenize.STRING:
            _check_nested_quote(text, stack, row, found)
    return found


def _check_nested_quote(text: str, stack: list, row: int,
                        found: list) -> None:
    inner = text.lstrip("rRfFbBuU")
    for quote, _, _ in stack:
        if quote in inner:
            found.append((row, f"sama lainausmerkki {quote} sisakkain "
                          "f-stringissa"))
            return


# --- Erottelevat fikstuurit: jokainen vika on 3.11:lle SyntaxError ---------

BAD = {
    "kenoviiva": 'x = f"{a.replace(\', \', \',\\n\')}"\n',
    "sama_lainausmerkki": 'x = f"{d["k"]}"\n',
    "kommentti": 'x = f"""{a  # selite\n}"""\n',
    "yksirivinen_monirivinen": 'x = f"{a +\n b}"\n',
    "sisakkainen_fstring_samalla_merkilla": 'x = f"{f"{a}"}"\n',
    # Taman portin syntysyy, sellaisenaan (rivi 514, 21.9):
    "mitattu_muoto": ("linkattu = (f\"<li>{alku.replace(', ', ',\\n  ', 1)}"
                      " at \"\n    f'<a>{loppu}</a>')\n"),
}

GOOD = {
    "kenoviiva_tekstiosassa": 'x = f"a\\n{b}"\n',
    "eri_lainausmerkki": 'x = f"{d[\'k\']}"\n',
    "kolmoislainaus_sisalla_yksi": "x = f'''{d['k']}'''\n",
    "monirivinen_kolmoislainaus": 'x = f"""{a +\n b}"""\n',
    "muotoilu": 'x = f"{a:>10.2f} {b!r} {c:{w}}"\n',
    "kenoviiva_ennen_ja_jalkeen": 'x = "\\n".join(f"[{n}]" for n in y)\n',
    "tavallinen_merkkijono": "x = 'a\\n' + \"b\"  # kommentti\n",
}


@pytest.mark.skipif(not PEP701, reason="3.11: compile()-haara mittaa")
@pytest.mark.parametrize("name", sorted(BAD))
def test_tunnistaa_3_11_kelvottoman_muodon(name):
    assert pep701_violations(BAD[name]), (
        f"{name}: portti ei tunnista muotoa jota 3.11 ei jasenna")


@pytest.mark.skipif(not PEP701, reason="3.11: compile()-haara mittaa")
@pytest.mark.parametrize("name", sorted(GOOD))
def test_ei_vaaraa_halytysta_3_11_kelpoisesta(name):
    assert not pep701_violations(GOOD[name]), (
        f"{name}: 3.11-kelpoinen muoto halyttaa: "
        f"{pep701_violations(GOOD[name])}")


@pytest.mark.skipif(PEP701, reason="vain CI:n 3.11 kayttaa oikeaa kielioppia")
@pytest.mark.parametrize("name", sorted(BAD))
def test_fikstuurit_ovat_oikeasti_3_11_kelvottomia(name):
    """Fikstuuri joka jasentyy 3.11:lla ei todista porttia: se on
    vaara esimerkki. CI ajaa taman ja pitaa fikstuurit rehellisina."""
    with pytest.raises(SyntaxError):
        compile(BAD[name], name, "exec")


@pytest.mark.skipif(PEP701, reason="vain CI:n 3.11 kayttaa oikeaa kielioppia")
@pytest.mark.parametrize("name", sorted(GOOD))
def test_hyvat_fikstuurit_jasentyvat_3_11(name):
    compile(GOOD[name], name, "exec")


def test_repo_jasentyy_python_3_11_kieliopilla():
    rikki: list[str] = []
    for path in _tracked_py_files():
        if not path.exists():
            continue
        src = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(ROOT).as_posix()
        if PEP701:
            try:
                rikki += [f"{rel}:{r}: {syy}"
                          for r, syy in pep701_violations(src)]
            except (tokenize.TokenError, SyntaxError) as e:
                rikki.append(f"{rel}: ei tokenisoidu: {e}")
        else:
            try:
                compile(src, rel, "exec")
            except SyntaxError as e:
                rikki.append(f"{rel}:{e.lineno}: {e.msg}")
    assert not rikki, (
        "CI (tests.yml) ajaa python 3.11:lla. Nama rivit kaatavat sen "
        "keraysvaiheessa tai workflow'n ajossa:\n  " + "\n  ".join(rikki))
