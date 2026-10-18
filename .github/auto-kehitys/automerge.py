"""Automergen ehdokkaat (18.10.2026, Villen GO: merge riskiluokan mukaan). Käyttää riskiluokka.py:tä.

  luokittele --prt prt.json --out-dir DIR
      Lukee `gh pr list --json number,title,headRefName,headRefOid,author,labels,isDraft` -tuloksen,
      hakee jokaisen auto/- ja aallonharja/-PR:n headin ja luokittelee sen. Kirjoittaa:
        ehdokkaat.json  sisäiset, joita ei ole vetoaitu eikä merkitty punaisiksi (matriisiksi)
        go.json         ihmisen GO:ta vaativat syineen (merkitään kerran labelilla)
      ja tulostaa GITHUB_OUTPUTiin `ehdokkaat=<json>` ja `maara=<n>`.

Ehdokkaaksi pääsee vain PR, jonka on avannut työnkulku (github-actions), joka ei ole luonnos, jonka
haara on auto/ tai aallonharja/, ja jolla ei ole labelia `ei-automergea` (ylläpitäjän veto) tai
`automerge-punainen` (edellinen yritys toi uusia punaisia testejä; label pois = uusi yritys).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

PROFIILIT = {"auto/": "kehitys", "aallonharja/": "aallonharja"}
BOTIT = {"app/github-actions", "github-actions[bot]", "github-actions"}
VETO = "ei-automergea"
PUNAINEN = "automerge-punainen"
ODOTTAA = "odottaa-go"


def _riskiluokka():
    polku = Path(__file__).with_name("riskiluokka.py")
    spec = importlib.util.spec_from_file_location("riskiluokka", polku)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def profiili(haara: str) -> str | None:
    for etuliite, nimi in PROFIILIT.items():
        if haara.startswith(etuliite):
            return nimi
    return None


def esisuodata(pr: dict) -> str | None:
    """None = luokitellaan; muuten syy, miksi PR ohitetaan kokonaan."""
    if profiili(pr.get("headRefName", "")) is None:
        return "ei auto/- tai aallonharja/-haara"
    if (pr.get("author") or {}).get("login") not in BOTIT:
        return "ei työnkulun avaama"
    if pr.get("isDraft"):
        return "luonnos"
    labelit = {lb.get("name") for lb in pr.get("labels") or []}
    if VETO in labelit:
        return "ylläpitäjän veto (ei-automergea)"
    if PUNAINEN in labelit:
        return "edellinen yritys toi uusia punaisia testejä"
    return None


def _git(*args: str) -> str:
    return subprocess.run(("git",) + args, check=True, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def luokittele(prt: list[dict], hae=True) -> tuple[list[dict], list[dict], list[dict]]:
    rl = _riskiluokka()
    ehdokkaat, go, ohitetut = [], [], []
    for pr in prt:
        syy = esisuodata(pr)
        if syy:
            ohitetut.append({"number": pr.get("number"), "syy": syy})
            continue
        sha, prof = pr["headRefOid"], profiili(pr["headRefName"])
        if hae:
            _git("fetch", "-q", "origin", f"pull/{int(pr['number'])}/head")
        muutokset = []
        for rivi in _git("diff", "--name-status", "--no-renames", f"origin/main...{sha}").splitlines():
            osat = rivi.split("\t")
            if len(osat) >= 2:
                muutokset.append((osat[0], osat[-1]))
        lisatyt = rl._lisatyt(_git("diff", "-U0", "--no-renames", f"origin/main...{sha}"))
        luokka, syyt = rl.luokittele(prof, muutokset, lisatyt)
        rivi = {"number": int(pr["number"]), "sha": sha, "profiili": prof, "otsikko": pr.get("title", "")[:110]}
        if luokka == "sisainen":
            ehdokkaat.append(rivi)
        else:
            labelit = {lb.get("name") for lb in pr.get("labels") or []}
            go.append({**rivi, "syyt": syyt[:8], "merkitty": ODOTTAA in labelit})
    return ehdokkaat, go, ohitetut


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="komento", required=True)
    lk = sub.add_parser("luokittele")
    lk.add_argument("--prt", required=True)
    lk.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    prt = json.loads(Path(a.prt).read_text(encoding="utf-8"))
    ehdokkaat, go, ohitetut = luokittele(prt)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "ehdokkaat.json").write_text(json.dumps(ehdokkaat, ensure_ascii=False), encoding="utf-8")
    (out / "go.json").write_text(json.dumps(go, ensure_ascii=False), encoding="utf-8")
    for o in ohitetut:
        print(f"PR #{o['number']}: ohitettu ({o['syy']})")
    for g in go:
        print(f"PR #{g['number']}: GO ({'; '.join(g['syyt'][:3])})")
    for e in ehdokkaat:
        print(f"PR #{e['number']}: sisäinen, automerge-ehdokas")
    print(f"ehdokkaat={json.dumps(ehdokkaat, ensure_ascii=False)}")
    print(f"maara={len(ehdokkaat)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
