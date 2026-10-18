"""Auto-PR:n riskiluokka automergeä varten (18.10.2026, Villen GO: "merge riskiluokan mukaan").

Luokka lasketaan diffistä, ei agentin PR-rungosta: agentin oma "Riskiluokka:"-rivi on tieto, ei portti.
auto-merge.yml ajaa tämän tiedoston MAININ versiosta, joten agentti ei voi löysätä sitä haarallaan.

  sisainen  mergetään automaattisesti, kun testit eivät tuo uusia punaisia. Polut ovat sellaisia, joiden
            merge ei deployaa mitään (Renderin ignoredPaths sisältää docs/*.md ja tests/**, hub-deploy ja
            pro-spa-deploy eivät reagoi niihin), joten tuotanto ei voi muuttua automergellä.
  go        kaikki muu: ihmisen GO ("Annan luvan: merge fp #N").

Testeistä hyväksytään vain UUSI testitiedosto. Olemassa olevan testin muutos tai poisto voisi heikentää
porttia, jonka päälle koko automerge nojaa (agentti ei saa poistaa vartijaa ja mergetä sitä itse), ja
conftest.py tai pytest-asetus voisi ohittaa muut testit.

Käyttö: python riskiluokka.py --profiili kehitys|aallonharja --base origin/main --head <sha> [--json]
Exit 0 = sisainen, 2 = go, 1 = virhe.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys

# Tiedostot, joiden muutos (A tai M) on sisäinen profiileittain. Poisto (D) ei ole koskaan sisäinen.
SISAINEN_MUUTOS = {
    "kehitys": ("docs/AUTO-BACKLOG.md",),
    "aallonharja": ("docs/BENCHMARK.md", "docs/AUTO-BACKLOG.md", "data/fpl_schema_snapshot.json"),
}
# Uusi tiedosto (vain A), joka on sisäinen.
SISAINEN_UUSI = {
    "kehitys": ("tests/test_*.py",),
    "aallonharja": (),
}
# Ei koskaan sisäinen, vaikka osuisi yllä oleviin.
AINA_GO = (
    "tests/conftest.py", "tests/**/conftest.py", "conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg",
    "tests/test_auto_kehitys_*",
)
# Lisätyt rivit, jotka tekevät muutoksesta ihmisen asian.
AINA_GO_RIVIT = (
    ("(lukittu)", "rivin lukitus on ylläpitäjän päätös"),
    ("pytest.skip", "testin ohitus heikentää porttia"),
    ("pytestmark", "moduulitason merkintä voi ohittaa testejä"),
    ("collect_ignore", "keräyksen ohitus heikentää porttia"),
)


def _osuu(polku: str, kuviot) -> bool:
    return any(fnmatch.fnmatchcase(polku, k) for k in kuviot)


def luokittele(profiili: str, muutokset: list[tuple[str, str]], lisatyt: dict[str, list[str]]) -> tuple[str, list[str]]:
    """muutokset = [(status, polku)], status A/M/D/R...; palauttaa (luokka, syyt)."""
    if profiili not in SISAINEN_MUUTOS:
        return "go", [f"tuntematon profiili {profiili}"]
    if not muutokset:
        return "go", ["tyhjä muutos"]
    syyt = []
    for status, polku in muutokset:
        s = status[:1]
        if _osuu(polku, AINA_GO):
            syyt.append(f"{polku}: aina ihmisen päätös")
        elif s == "M" and polku in SISAINEN_MUUTOS[profiili]:
            continue
        elif s == "A" and (polku in SISAINEN_MUUTOS[profiili] or _osuu(polku, SISAINEN_UUSI[profiili])):
            continue
        else:
            syyt.append(f"{polku} ({s}): ei sisäinen polku tälle profiilille")
    for polku, rivit in lisatyt.items():
        for rivi in rivit:
            for merkki, syy in AINA_GO_RIVIT:
                if merkki in rivi:
                    syyt.append(f"{polku}: lisätty '{merkki}' ({syy})")
    return ("go", syyt) if syyt else ("sisainen", [])


def _git(*args: str) -> str:
    return subprocess.run(("git",) + args, check=True, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def _lisatyt(diff: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    nyk = None
    for rivi in diff.splitlines():
        if rivi.startswith("+++ "):
            nimi = rivi[4:]
            nyk = None if nimi == "/dev/null" else (nimi[2:] if nimi.startswith("b/") else nimi)
            if nyk:
                out.setdefault(nyk, [])
        elif rivi.startswith("+") and nyk:
            out[nyk].append(rivi[1:])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profiili", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    vali = f"{a.base}...{a.head}"
    try:
        muutokset = []
        for rivi in _git("diff", "--name-status", "--no-renames", vali).splitlines():
            osat = rivi.split("\t")
            if len(osat) >= 2:
                muutokset.append((osat[0], osat[-1]))
        lisatyt = _lisatyt(_git("diff", "-U0", "--no-renames", vali))
    except subprocess.CalledProcessError as e:
        print(f"git epäonnistui: {e}", file=sys.stderr)
        return 1
    luokka, syyt = luokittele(a.profiili, muutokset, lisatyt)
    if a.json:
        print(json.dumps({"luokka": luokka, "syyt": syyt, "tiedostoja": len(muutokset)}, ensure_ascii=False))
    else:
        print(f"Riskiluokka: {luokka}")
        for s in syyt:
            print(f"  - {s}")
    return 0 if luokka == "sisainen" else 2


if __name__ == "__main__":
    sys.exit(main())
