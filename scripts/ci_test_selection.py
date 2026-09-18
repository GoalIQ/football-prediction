# -*- coding: utf-8 -*-
"""YKSI LUKIJA: ajaako CI taman testin?  (18.9.2026)

TAUSTA. 17.9 kirjasin jonoriviksi vaitteen "fp-mainin tests.yml on punainen
test_domestic_golden-driftista (4 testia) -> ESTAA GATEN SEURAAVASSA PUSHISSA",
ja sen perusteella kuusi valmista haaraa jai pushaamatta yli vuorokaudeksi.
18.9 mittasin: vaite oli epatosi.

  * `tests/test_domestic_golden.py` kantaa `pytestmark = pytest.mark.slow`
  * `.github/workflows/tests.yml` ajaa `pytest -m "not slow" -q`
  * `pytest.ini`: slow = golden-testit jotka vaativat lokaalin datan (ei CI)
  => CI ei aja sita testia koskaan, eika se voi tehda tests.yml:sta punaista.

Eika kyse ollut driftista: virhe oli `HTTP 404 Invalid league 'ESP-La Liga-FD'`,
koska testi vaatii `downloaded_files/`-kansion jota tallä koneella ei ole.

VIKALUOKKA: **lokaali testifaili raportoitiin CI-tilana.** Sama luokka kuin
muistit `exit-koodi-ei-ole-todiste-mekanismista` ja
`vain-schedule-ajot-mittarissa`: mittari mittasi eri asiaa kuin vaite sanoi.

Vika syntyi UNOHDUKSESTA. Vastaus kysymykseen "ajaako CI taman" makasi
KOLMESSA tiedostossa (workflow'n pytest-kutsu, testitiedoston markkerit,
pytest.ini), ja lukija oli ihminen joka muistaa tai ei muista katsoa kaikki
kolme. Pinta joka joutuu muistamaan suodatuksen tarkoittaa etta joku unohtaa
sen (CLAUDE.md saanto 6a, mekanismi 1). Siksi tassa on yksi lukija joka lukee
kaikki kolme lahdetta ja vastaa AJAA / EI AJA + mika workflow + mika syy.

FAIL-CLOSED. Pytest-kutsu jota ei saada jasennettya EI ole "ei aja" vaan
epavarma (`Verdict.epavarmat`). "Ei aja" on tasmalleen se vastaus jonka
vaarin antaminen maksoi vuorokauden, joten sita ei anneta arvaamalla.

AJO:
  python scripts/ci_test_selection.py tests/test_domestic_golden.py
  python scripts/ci_test_selection.py tests/test_parlay.py::test_domestic_and_mixed_parlay
  python scripts/ci_test_selection.py --slow-files
  python scripts/ci_test_selection.py --json tests/test_domestic_golden.py

Pelkka stdlib (ei pytestia, ei yaml-kirjastoa): lukijan on vastattava myos
silloin kun riippuvuudet eivat asennu.
"""
from __future__ import annotations

import argparse
import ast
import configparser
import json
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ".github/workflows"


# ---------------------------------------------------------------------------
# 1. TESTITIEDOSTON MARKKERIT  (ast, ei importtia)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Item:
    """Yksi kerattava testi: nodeid + markkerit jotka siihen patevat."""
    nodeid: str
    file: str
    markers: frozenset


def _mark_names(node: ast.AST) -> set:
    """`pytest.mark.slow`, `pytest.mark.skipif(...)`, lista naista -> nimet."""
    out: set = set()
    if isinstance(node, (ast.List, ast.Tuple)):
        for el in node.elts:
            out |= _mark_names(el)
        return out
    if isinstance(node, ast.Call):
        return _mark_names(node.func)
    if isinstance(node, ast.Attribute):
        owner = node.value
        if (isinstance(owner, ast.Attribute) and owner.attr == "mark"
                and isinstance(owner.value, ast.Name) and owner.value.id == "pytest"):
            out.add(node.attr)
        elif isinstance(owner, ast.Name) and owner.id == "mark":
            # `from pytest import mark` -> mark.slow
            out.add(node.attr)
    return out


def _pytestmark(body: list) -> set:
    """Moduuli- tai luokkatason `pytestmark = ...`."""
    out: set = set()
    for st in body:
        if isinstance(st, ast.Assign):
            targets = st.targets
        elif isinstance(st, ast.AnnAssign):
            targets = [st.target]
        else:
            continue
        if any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in targets):
            if st.value is not None:
                out |= _mark_names(st.value)
    return out


def _decorators(node) -> set:
    out: set = set()
    for d in node.decorator_list:
        out |= _mark_names(d)
    return out


def collected_items(path, root: Path = ROOT) -> list:
    """Testitiedoston kerattavat testit ja niiden markkerit.

    Kolme tasoa niin kuin pytest ne perii: moduulin `pytestmark`, luokan
    `pytestmark` + dekoraattorit, ja funktion dekoraattorit. Moduulitason
    markkeri koskee jokaista testia (= koko tiedosto jaa pois), funktiotason
    vain omaansa (= tiedosto ajaa OSITTAIN). Se ero on se jonka 17.9 vaite
    ohitti.
    """
    p = Path(path)
    if not p.is_absolute():
        p = root / p
    rel = p.resolve().relative_to(Path(root).resolve()).as_posix()
    tree = ast.parse(p.read_text(encoding="utf-8"), filename=rel)
    mod = _pytestmark(tree.body)
    items: list = []
    for st in tree.body:
        if (isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef))
                and st.name.startswith("test")):
            items.append(Item(rel + "::" + st.name, rel,
                              frozenset(mod | _decorators(st))))
        elif isinstance(st, ast.ClassDef) and st.name.startswith("Test"):
            cls = _decorators(st) | _pytestmark(st.body)
            for m in st.body:
                if (isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and m.name.startswith("test")):
                    items.append(Item(rel + "::" + st.name + "::" + m.name, rel,
                                      frozenset(mod | cls | _decorators(m))))
    if not items:
        # Tyhja tiedosto tai testit generoituvat: markkerit tiedetaan, nodeidit
        # ei. Palautetaan moduuli itse, jotta vastaus ei ole hiljainen "ei aja".
        items.append(Item(rel, rel, frozenset(mod)))
    return items


def all_test_files(root: Path = ROOT) -> list:
    ini = pytest_ini(root)
    base = [Path(root) / tp for tp in ini["testpaths"]] or [Path(root)]
    out: set = set()
    for b in base:
        if not b.exists():
            continue
        for f in b.rglob("test_*.py"):
            if "__pycache__" in f.parts:
                continue
            out.add(f.resolve().relative_to(Path(root).resolve()).as_posix())
    return sorted(out)


def marked_items(marker: str, root: Path = ROOT) -> dict:
    """Tiedosto -> ne nodeidit jotka kantavat markkerin (`*` = koko moduuli)."""
    out: dict = {}
    for rel in all_test_files(root):
        items = collected_items(rel, root)
        hits = [i.nodeid for i in items if marker in i.markers]
        if not hits:
            continue
        out[rel] = ["*"] if len(hits) == len(items) else hits
    return out


def ei_aja_cissa(root: Path = ROOT) -> dict:
    """Testit joita YKSIKAAN workflow ei valitse. Tiedosto -> nodeidit
    (`*` = koko tiedosto).

    Tama on poikkeuslistan lahde, EIKA `marked_items("slow")`. Ero on se
    muoto joka on yhden muokkauksen paassa (muisti: portti-kirjoitetaan-
    nahdylle-muodolle): uusi markkeri (`-m "not slow and not uvicorn"`),
    uusi `--deselect` tai polkurajaus sulkee testin CI:sta ilman etta
    sanaa "slow" esiintyy missaan. Kun lista johdetaan SULKEUTUMISESTA eika
    yhdesta markkerinimesta, uusi tapa sulkea testi ei paase listalle
    vahingossa.
    """
    ini = pytest_ini(root)
    kutsut = pytest_kutsut(root)
    out: dict = {}
    for rel in all_test_files(root):
        items = collected_items(rel, root)
        ohi = []
        for it in items:
            if not any(_valinta(k, it, ini)[0] for k in kutsut):
                ohi.append(it.nodeid)
        if not ohi:
            continue
        out[rel] = ["*"] if len(ohi) == len(items) else ohi
    return out


# ---------------------------------------------------------------------------
# 2. pytest.ini
# ---------------------------------------------------------------------------

def pytest_ini(root: Path = ROOT) -> dict:
    cfg = configparser.ConfigParser()
    path = Path(root) / "pytest.ini"
    data: dict = {"testpaths": [], "markers": {}, "addopts": []}
    if not path.exists():
        return data
    cfg.read_string(path.read_text(encoding="utf-8"))
    if not cfg.has_section("pytest"):
        return data
    sec = cfg["pytest"]
    data["testpaths"] = shlex.split(sec.get("testpaths", ""))
    data["addopts"] = shlex.split(sec.get("addopts", ""))
    for rivi in (sec.get("markers", "") or "").splitlines():
        rivi = rivi.strip()
        if not rivi:
            continue
        nimi, _, kuvaus = rivi.partition(":")
        data["markers"][nimi.strip()] = kuvaus.strip()
    return data


# ---------------------------------------------------------------------------
# 3. WORKFLOW'N PYTEST-KUTSUT  (ei yaml-kirjastoa)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Kutsu:
    workflow: str
    step: str
    triggers: tuple
    argv: tuple
    line: int
    raw: str


_RUN = re.compile(r"^(?P<ind>[ \t]*)(?:-[ \t]+)?run:[ \t]*(?P<rest>.*)$")
_STEP = re.compile(r"^[ \t]*-[ \t]+name:[ \t]*(?P<name>.*)$")
_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_SPLIT = re.compile(r"(?:\|\||&&|[;|&])")

# Optiot jotka SYOVAT seuraavan argumentin. Ilman tata listaa `-m` jattaisi
# "not slow" -merkkijonon polkuargumentiksi ja kaikki jaisi valitsematta.
_VALUE_OPTS = {
    "-m", "-k", "-p", "-n", "-c", "-o", "-W", "-r",
    "--deselect", "--ignore", "--ignore-glob", "--rootdir", "--junitxml",
    "--override-ini", "--maxfail", "--tb", "--durations", "--cov",
    "--cov-report", "--dist", "--color", "--log-level", "--timeout",
}


def _triggers(text: str) -> tuple:
    lines = text.splitlines()
    out: list = []
    i = 0
    while i < len(lines) and not re.match(r"^on:\s*(.*)$", lines[i]):
        i += 1
    if i >= len(lines):
        return ()
    inline = re.match(r"^on:\s*(.+)$", lines[i])
    if (inline and inline.group(1).strip()
            and not inline.group(1).lstrip().startswith("#")):
        return tuple(x.strip(" []") for x in inline.group(1).split(",")
                     if x.strip(" []"))
    i += 1
    nykyinen = None
    taso = None            # `on:`-lohkon avainten sisennys, esim. 2
    while i < len(lines):
        rivi = lines[i]
        if rivi.strip() and not rivi.startswith((" ", "\t")):
            break
        if not rivi.strip() or rivi.lstrip().startswith("#"):
            i += 1
            continue
        ind = len(rivi) - len(rivi.lstrip())
        m = re.match(r"^[ \t]*([a-z_]+):[ \t]*(.*)$", rivi)
        if m and taso is None:
            taso = ind
        if m and ind == taso:
            # Triggeri (push, pull_request, schedule, workflow_dispatch).
            nykyinen = m.group(1)
            out.append(nykyinen)
        elif nykyinen and out and ind > (taso or 0):
            # Triggerin tarkennus. `branches: [main]` ratkaisee sen, ajaako
            # workflow tassa haarassa - muisti: vain-schedule-ajot-mittarissa.
            b = re.match(r"^[ \t]*branches:[ \t]*(.+)$", rivi)
            if b:
                haarat = [x.strip(" []'\"") for x in b.group(1).split(",")]
                out[-1] = nykyinen + ":" + "/".join(x for x in haarat if x)
        i += 1
    return tuple(out)


def _run_blocks(text: str) -> list:
    """(askeleen nimi, 1-pohjainen rivinumero, komentolohko)."""
    lines = text.splitlines()
    out: list = []
    step = ""
    i = 0
    while i < len(lines):
        rivi = lines[i]
        s = _STEP.match(rivi)
        if s:
            step = s.group("name").strip().strip("'\"")
        m = _RUN.match(rivi)
        if not m or rivi.lstrip().startswith("#"):
            i += 1
            continue
        ind = len(m.group("ind").expandtabs(8))
        rest = m.group("rest").strip()
        if rest and rest not in ("|", "|-", "|+", ">", ">-", ">+"):
            out.append((step, i + 1, rest.strip("'\"")))
            i += 1
            continue
        j = i + 1
        body: list = []
        while j < len(lines):
            r = lines[j]
            if not r.strip():
                body.append("")
                j += 1
                continue
            if len(r) - len(r.lstrip()) <= ind:
                break
            body.append(r)
            j += 1
        out.append((step, i + 2, "\n".join(body)))
        i = j
    return out


def _logical_lines(block: str, start: int) -> list:
    """Kommentit pois, kenoviivajatkot yhteen. Rivinumero = ensimmainen rivi."""
    out: list = []
    pending: list = []
    p_line = start
    for k, raw in enumerate(block.splitlines()):
        line = raw.strip()
        if not pending and (not line or line.startswith("#")):
            continue
        if not pending:
            p_line = start + k
        if line.endswith("\\"):
            pending.append(line[:-1])
            continue
        pending.append(line)
        out.append((p_line, " ".join(x.strip() for x in pending).strip()))
        pending = []
    if pending:
        out.append((p_line, " ".join(x.strip() for x in pending).strip()))
    return out


def _pytest_argv(command: str) -> list:
    """Komentorivi -> pytestin argumentit, tai [] jos pytest ei ole komento.

    `pip install -r requirements.txt pytest httpx` EI ole pytest-kutsu vaikka
    sana esiintyy rivilla. Siksi katsotaan komennon PAIKKAA, ei substringia.
    """
    out: list = []
    for pala in _SPLIT.split(command):
        pala = pala.strip().strip("{}() \t")
        if not pala or "pytest" not in pala:
            continue
        try:
            toks = shlex.split(pala, posix=True)
        except ValueError:
            out.append(["<<EI-JASENNETTAVISSA>>", pala])
            continue
        while toks and (_ENV_ASSIGN.match(toks[0])
                        or toks[0] in ("env", "sudo", "time", "nice")):
            toks = toks[1:]
        if not toks:
            continue
        if toks[0] in ("pytest", "py.test"):
            out.append(toks[1:])
        elif (re.match(r"^(python[0-9.]*|py|coverage)$", toks[0])
              and "-m" in toks[:4] and "pytest" in toks[:5]):
            k = toks.index("pytest")
            out.append(toks[k + 1:])
    return out


def pytest_kutsut(root: Path = ROOT) -> list:
    out: list = []
    wf_dir = Path(root) / WORKFLOW_DIR
    if not wf_dir.exists():
        return out
    for wf in sorted(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml"))):
        text = wf.read_text(encoding="utf-8")
        rel = wf.resolve().relative_to(Path(root).resolve()).as_posix()
        trig = _triggers(text)
        for step, start, block in _run_blocks(text):
            for line, command in _logical_lines(block, start):
                for argv in _pytest_argv(command):
                    out.append(Kutsu(rel, step, trig, tuple(argv), line, command))
    return out


# ---------------------------------------------------------------------------
# 4. VALINTA: valitseeko tama kutsu taman testin?
# ---------------------------------------------------------------------------

class _Markkerit(dict):
    """Tuntematon markkerinimi on False, ei NameError."""

    def __missing__(self, key):
        return False


_MARKER_EXPR_OK = re.compile(r"^[\w\s()]+$")


def marker_expr_matches(expr: str, markers) -> bool:
    """`-m` -lauseke pytestin semantiikalla (nimet, and/or/not, sulut)."""
    expr = (expr or "").strip()
    if not expr:
        return True
    if not _MARKER_EXPR_OK.match(expr):
        raise ValueError("markkerilauseketta ei jasennetty: " + repr(expr))
    ns = _Markkerit({m: True for m in markers})
    return bool(eval(expr, {"__builtins__": {}}, ns))  # noqa: S307


@dataclass
class _Opts:
    marker: object = None
    keyword: object = None
    paths: list = field(default_factory=list)
    deselect: list = field(default_factory=list)
    ignore: list = field(default_factory=list)
    jasentymaton: bool = False


def parse_pytest_argv(argv) -> _Opts:
    o = _Opts()
    argv = list(argv)
    if argv[:1] == ["<<EI-JASENNETTAVISSA>>"]:
        o.jasentymaton = True
        return o
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--":
            o.paths.extend(argv[i + 1:])
            break
        if a.startswith("-"):
            nimi, eq, inline = a.partition("=")
            if eq:
                arvo = inline
            elif nimi in _VALUE_OPTS:
                arvo = argv[i + 1] if i + 1 < len(argv) else ""
                i += 1
            else:
                arvo = None
            if nimi == "-m" and arvo is not None:
                o.marker = arvo
            elif nimi == "-k" and arvo is not None:
                o.keyword = arvo
            elif nimi == "--deselect" and arvo:
                o.deselect.append(arvo)
            elif nimi in ("--ignore", "--ignore-glob") and arvo:
                o.ignore.append(arvo)
        else:
            o.paths.append(a)
        i += 1
    return o


def _norm(x: str) -> str:
    return x.replace("\\", "/").strip().rstrip("/")


def _sisaltyy(item: Item, arg: str) -> bool:
    arg = _norm(arg)
    if arg in ("", ".", "./"):
        return True
    if "::" in arg:
        return item.nodeid == arg or item.nodeid.startswith(arg + "::")
    return item.file == arg or item.file.startswith(arg + "/")


@dataclass
class Verdict:
    target: str
    runs: bool
    reason: str
    workflows: tuple
    rivit: tuple
    epavarmat: tuple
    items: tuple

    def as_dict(self) -> dict:
        return {"target": self.target, "runs": self.runs, "reason": self.reason,
                "workflows": list(self.workflows), "rivit": list(self.rivit),
                "epavarmat": list(self.epavarmat),
                "items": [{"nodeid": i.nodeid, "markers": sorted(i.markers)}
                          for i in self.items]}


def _valinta(kutsu: Kutsu, item: Item, ini: dict) -> tuple:
    o = parse_pytest_argv(kutsu.argv)
    if o.jasentymaton:
        return None, "pytest-kutsua ei saatu jasennettya"
    polut = o.paths or list(ini.get("testpaths") or ["."])
    if not any(_sisaltyy(item, p) for p in polut):
        return False, "polkurajaus " + str(polut) + " ei kata tiedostoa"
    for ig in o.ignore:
        if _sisaltyy(item, ig):
            return False, "--ignore " + ig
    for ds in o.deselect:
        if _sisaltyy(item, ds):
            return False, "--deselect " + ds
    if o.marker:
        try:
            osuu = marker_expr_matches(o.marker, item.markers)
        except ValueError as e:
            return None, str(e)
        if not osuu:
            mk = ("{" + ", ".join(sorted(item.markers)) + "}"
                  if item.markers else "{}")
            return False, ('markkerivalinta -m "' + o.marker
                           + '" ei osu markkereihin ' + mk)
    if o.keyword:
        return None, ('-k "' + o.keyword
                      + '" valitsee nimen mukaan (ei paatettavissa staattisesti)')
    valinta = ('-m "' + o.marker + '"') if o.marker else "ei markkerivalintaa"
    return True, "valitsee (" + valinta + ", polut " + str(polut) + ")"


def ci_runs(target: str, root: Path = ROOT) -> Verdict:
    """AJAA / EI AJA + mika workflow + mika syy. Yksi lahde, kolme tiedostoa."""
    file_osa = target.split("::", 1)[0]
    items = collected_items(file_osa, root)
    if "::" in target:
        t = _norm(target)
        items = [i for i in items if i.nodeid == t or i.nodeid.startswith(t + "::")]
        if not items:
            raise ValueError("nodeid ei loydy tiedostosta: " + target)
    ini = pytest_ini(root)
    kutsut = pytest_kutsut(root)
    rivit: list = []
    epavarmat: list = []
    ajavat: list = []
    valitut: set = set()
    for k in kutsut:
        osuvat = []
        for it in items:
            ok, syy = _valinta(k, it, ini)
            if ok is None:
                epavarmat.append(k.workflow + ":" + str(k.line) + " "
                                 + it.nodeid + ": " + syy)
            elif ok:
                osuvat.append((it, syy))
                valitut.add(it.nodeid)
        trig = ",".join(k.triggers) or "ei triggereita"
        otsikko = (k.workflow + ":" + str(k.line) + " [" + trig + "] "
                   + (k.step or "(nimeton askel)"))
        komento = "pytest " + " ".join(shlex.quote(a) for a in k.argv)
        if osuvat:
            ajavat.append(k.workflow)
            kuvaus = (str(len(osuvat)) + "/" + str(len(items)) + " testia"
                      if len(osuvat) != len(items) else "kaikki")
            rivit.append("AJAA  " + otsikko + "\n        " + komento
                         + "\n        -> " + kuvaus + ": " + osuvat[0][1])
        else:
            eka = _valinta(k, items[0], ini)[1] if items else ""
            rivit.append("ei    " + otsikko + "\n        " + komento
                         + "\n        -> " + str(eka))
    runs = bool(ajavat)
    if runs and len(valitut) < len(items):
        reason = ("CI ajaa " + str(len(valitut)) + "/" + str(len(items))
                  + " testia: " + ", ".join(sorted(set(ajavat))))
    elif runs:
        reason = "CI ajaa: " + ", ".join(sorted(set(ajavat)))
    else:
        mk = sorted({m for i in items for m in i.markers})
        reason = "CI EI aja tata. Lokaali punainen EI ole CI-tila."
        if mk:
            reason += " Markkerit: " + str(mk) + "."
        for m in mk:
            kuvaus = ini.get("markers", {}).get(m)
            if kuvaus:
                reason += " pytest.ini: " + m + " = " + kuvaus
    return Verdict(target, runs, reason, tuple(sorted(set(ajavat))),
                   tuple(rivit), tuple(epavarmat), tuple(items))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _tulosta(v: Verdict) -> None:
    print(("AJAA    " if v.runs else "EI AJA  ") + v.target)
    for r in v.rivit:
        print("  " + r)
    if v.epavarmat:
        print("  EPAVARMAT (fail-closed: nama eivat ole 'ei aja'):")
        for e in v.epavarmat:
            print("    - " + e)
    print("  => " + v.reason)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ajaako CI taman testin?")
    ap.add_argument("target", nargs="?",
                    help="tests/test_x.py tai tests/test_x.py::test_y")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--slow-files", action="store_true",
                    help="listaa slow-merkityt tiedostot ja niiden CI-tila")
    ap.add_argument("--excluded", action="store_true",
                    help="listaa KAIKKI testit joita yksikaan workflow ei aja")
    ap.add_argument("--root", default=str(ROOT))
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    if a.excluded:
        ulkona = ei_aja_cissa(root)
        if a.json:
            print(json.dumps(ulkona, indent=1))
            return 0
        if not ulkona:
            print("Jokainen testi ajaa jossakin workflow'ssa.")
        for rel, nodeids in sorted(ulkona.items()):
            print("EI AJA " + rel + "  "
                  + ("koko tiedosto" if nodeids == ["*"]
                     else str(len(nodeids)) + " testia"))
        return 0
    if a.slow_files:
        osumat = marked_items("slow", root)
        if a.json:
            print(json.dumps(osumat, indent=1))
            return 0
        for rel, nodeids in sorted(osumat.items()):
            v = ci_runs(rel, root)
            print(("AJAA   " if v.runs else "EI AJA ") + rel + "  slow: "
                  + ("koko moduuli" if nodeids == ["*"]
                     else str(len(nodeids)) + " testia"))
        return 0
    if not a.target:
        ap.error("anna testipolku tai --slow-files")
    v = ci_runs(a.target, root)
    if a.json:
        print(json.dumps(v.as_dict(), ensure_ascii=False, indent=1))
    else:
        _tulosta(v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
