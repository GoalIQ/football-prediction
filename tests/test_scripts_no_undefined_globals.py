# -*- coding: utf-8 -*-
"""3.9 (AUTO-S1): fpl-why-refresh kaatui kahdesti NameErroriin (`fplgw`
kaytossa ilman importtia, build_fpl_why.py:554). Yksikkotestit eivat nahneet
sita koska koodipolku ajetaan vain CI:n generate-askeleessa. Tama vahti kay
lapi scripts/ ja src/ symtablella: nimi jota funktio lukee globaalina eika
moduuli maarittele (import, def, class, sijoitus) eika builtin ole -> FAIL.
Ei riippuvuuksia (pyflakes ei ole requirementsissa)."""
from __future__ import annotations

import builtins
import symtable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN = [ROOT / "scripts", ROOT / "src", ROOT / "api"]
BUILTIN = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__spec__",
                                "__builtins__", "__package__", "__loader__",
                                "__path__", "__annotations__"}


def _module_defined(top: symtable.SymbolTable) -> set[str]:
    return {s.get_name() for s in top.get_symbols()
            if s.is_assigned() or s.is_imported() or s.is_parameter()
            or s.is_namespace()}


def _walk(tab: symtable.SymbolTable, defined: set[str], out: list[str], path):
    for s in tab.get_symbols():
        if (s.is_global() or (s.is_referenced() and not s.is_local()
                              and not s.is_free())) and not s.is_assigned():
            n = s.get_name()
            if n not in defined and n not in BUILTIN:
                out.append(f"{path.relative_to(ROOT)}: {tab.get_name()}() lukee "
                           f"maarittelematonta nimea `{n}`")
    for child in tab.get_children():
        _walk(child, defined, out, path)


def _check(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    try:
        top = symtable.symtable(src, str(path), "exec")
    except SyntaxError as e:
        return [f"{path.relative_to(ROOT)}: SyntaxError {e}"]
    defined = _module_defined(top)
    # `from x import *` tekee tarkistuksesta sokean -> ohitetaan moduuli.
    if "import *" in src:
        return []
    out: list[str] = []
    for child in top.get_children():
        _walk(child, defined, out, path)
    return out


def test_no_function_reads_an_undefined_module_global():
    bad: list[str] = []
    for base in SCAN:
        for f in sorted(base.rglob("*.py")):
            if ".venv" in f.parts or "node_modules" in f.parts:
                continue
            bad.extend(_check(f))
    assert not bad, chr(10).join(bad)


def test_guard_catches_the_original_bug(tmp_path):
    """Negatiivinen kontrolli: sama vika synteettisesti -> loytyy."""
    f = tmp_path / "x.py"
    f.write_text("import json" + chr(10) + "def main():" + chr(10) + "    return fplgw.actionable_gameweek({})" + chr(10), encoding="utf-8")
    src = f.read_text(encoding="utf-8")
    top = symtable.symtable(src, str(f), "exec")
    out: list[str] = []
    for child in top.get_children():
        _walk(child, _module_defined(top), out, ROOT / "scripts" / "x.py")
    assert out and "fplgw" in out[0]
