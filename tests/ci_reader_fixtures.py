# -*- coding: utf-8 -*-
"""Synteettinen repo CI-lukijan testeille (18.9.2026).

EI `test_`-etuliitetta: tama ei ole testi vaan rakennustelineet. Lukijaa
`scripts/ci_test_selection.py` ei voi mitata vain tasta reposta, koska tama repo on
YKSI kohta avaruudessa: siina on tasmalleen yksi `-m "not slow"` -kutsu ja
yksi polkurajattu kutsu. Testi joka mittaa vain nykyista konfiguraatiota on
vihrea siihen asti kun se lakkaa olemasta tosi (CLAUDE.md saanto 6a,
mekanismi 3).

Siksi lukija ajetaan synteettisilla vaiheilla: `-m "not slow"`, `-m "slow"`,
ei markkerivalintaa lainkaan, polkurajaus, `--deselect`, `--ignore`, ja
moduulitason `pytestmark` vs funktiotason `@pytest.mark.slow`.
"""
from __future__ import annotations

from pathlib import Path

INI = ("[pytest]\n"
       "pythonpath = .\n"
       "testpaths = tests\n"
       "markers =\n"
       "    slow: lokaalia dataa vaativat testit (ei CI)\n")


def workflow(komento: str, *, step: str = "Run tests",
             triggers: str = "  push:\n    branches: [main]\n") -> str:
    """Minimaalinen workflow jonka ainoa kiinnostava rivi on pytest-kutsu."""
    return ("name: synteettinen\n"
            "\n"
            "on:\n"
            + triggers +
            "\n"
            "jobs:\n"
            "  t:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v7\n"
            "      - name: Install\n"
            "        run: pip install -r requirements.txt pytest httpx\n"
            "      - name: " + step + "\n"
            "        run: " + komento + "\n")


def tekorepo(tmp: Path, *, workflows: dict, testit: dict, ini: str = INI) -> Path:
    """Kirjoittaa repon: pytest.ini + .github/workflows/* + tests/*."""
    root = Path(tmp)
    (root / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    if ini is not None:
        (root / "pytest.ini").write_text(ini, encoding="utf-8")
    for nimi, sisalto in workflows.items():
        (root / ".github" / "workflows" / nimi).write_text(sisalto, encoding="utf-8")
    for rel, sisalto in testit.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(sisalto, encoding="utf-8")
    return root


# --- testitiedostojen muodot joita kentalla on ------------------------------

MODUULITASO = ('import pytest\n'
               '\n'
               'pytestmark = pytest.mark.slow\n'
               '\n'
               'def test_a():\n'
               '    assert True\n'
               '\n'
               'def test_b():\n'
               '    assert True\n')

FUNKTIOTASO = ('import pytest\n'
               '\n'
               'def test_nopea():\n'
               '    assert True\n'
               '\n'
               '@pytest.mark.slow\n'
               'def test_hidas():\n'
               '    assert True\n')

MODUULITASO_LISTA = ('import pytest\n'
                     '\n'
                     'pytestmark = [pytest.mark.slow, pytest.mark.usefixtures("x")]\n'
                     '\n'
                     'def test_a():\n'
                     '    assert True\n')

LUOKKATASO = ('import pytest\n'
              '\n'
              'class TestHidas:\n'
              '    pytestmark = pytest.mark.slow\n'
              '\n'
              '    def test_a(self):\n'
              '        assert True\n'
              '\n'
              'def test_moduulin_oma():\n'
              '    assert True\n')

EI_MARKKERIA = ('def test_a():\n'
                '    assert True\n'
                '\n'
                'def test_b():\n'
                '    assert True\n')
