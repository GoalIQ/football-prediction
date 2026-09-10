"""Portti: workflow joka committaa servattavan sivun myos deployaa sen.

🔴 SAMA VIKA KOLMESTI, JA JOKA KERTA LIVE JAI YHDEN COMMITIN JALKEEN.

  19.8  `accuracy-log.yml` committasi fpl.html:n `[skip ci]`-viestilla eika
        dispatchannut hub-deployta. Ville: "sama lukema jo pari paivaa".
  7.9   `fpl-data-refresh.yml` committasi samat sivut ilman dispatchia, ja
        `fpl-page-refresh.yml` dispatchasi vain jos SE ITSE oli pushannut.
        Live servasi commitin 5d217815b kun mainissa oli 7a81f8c29 (md5).
  9.9   `ucl-refresh.yml` luotiin 7.9 kommentilla "EI [skip ci], jotta
        hub-deploy ajaa". Se oletus oli vaara: GITHUB_TOKENilla tehty push ei
        koskaan kaynnista workflow'ta, lipusta riippumatta. Ensimmainen
        onnistunut ajo (91c0382d2) committasi kolme UCL-sivua, sai nolla
        check-runia, ja goaliq.app/ucl servasi edellista committia
        (md5 mitattu kaikista kolmesta). Autopilotin S10 huusi, ei repo.

Kahdesti korjattiin workflow. Tama korjaa LUOKAN (CLAUDE.md 6a): jos
workflow `git add`aa servattavan polun ja pushaa, sen on ajettava
`scripts/verify_live_pages.sh` ainakin yhdella niista tiedostoista jotka se
itse lisaa. Unohdus kaataa testin sina hetkena kun workflow kirjoitetaan,
ei viikon paasta kun joku vertaa md5:ia.

MITA MITATAAN. `git add`-rivien polut jotka osuvat servattavaan joukkoon
(html, llms.txt, sitemap*.xml, robots.txt, _redirects, fpl/, predictions/,
ucl/). Data-tiedostot (`data/*.json`) eivat ole servattavia: api.goaliq.app
lukee ne Renderin deploysta, ei CF Pagesista, ja se on eri portti
(render-deploy-verifioidaan-commitista).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
VERIFY = "verify_live_pages.sh"
DYNAAMINEN = "$(python scripts/verify_targets.py)"
from scripts.verify_targets import CORE  # noqa: E402

# Sama joukko kuin autopilotin S10_PUBLISHABLE_RE (goaliq-app
# scripts/autopilot/signals.py), ilman scripts/ ja workflows/ jotka eivat
# ole sivuja vaan sivujen syita.
SERVATTAVA_RE = re.compile(
    r"^(.*\.html|llms\.txt|sitemap[^/]*\.xml|robots\.txt|_redirects|"
    r"(fpl|predictions|ucl)(/.*)?)$")

# Workflow -> perustelu. Rivi ilman perustelua ei kelpaa, ja rivi jonka
# workflow ei enaa lisaa servattavaa polkua on kuollut ja kaataa testin.
POIKKEUKSET: dict[str, str] = {}

_GIT_ADD_RE = re.compile(r"git add\s+([^\n|&>;]+)")
_VERIFY_RE = re.compile(re.escape(VERIFY) + r"\s*([^\n|&>;]*)")


def _run_lohkot(doc: dict) -> list[str]:
    out = []
    for job in (doc.get("jobs") or {}).values():
        for step in (job or {}).get("steps") or []:
            r = (step or {}).get("run")
            if isinstance(r, str):
                out.append(r)
    return out


def _polut(runit: list[str], regex: re.Pattern) -> list[str]:
    out = []
    for r in runit:
        for m in regex.finditer(r):
            for tok in m.group(1).split():
                if tok.startswith("-") or tok.startswith("$"):
                    continue
                out.append(tok.strip('"').rstrip("/") + ("/" if tok.endswith("/") else ""))
    return out


def analysoi(runit: list[str]) -> dict:
    """Puhdas funktio run-lohkoista, jotta portti voi mitata itsensa."""
    lisatyt = _polut(runit, _GIT_ADD_RE)
    servattavat = [p for p in lisatyt if SERVATTAVA_RE.match(p)]
    pushaa = any("git push" in r for r in runit)
    dynaaminen = any(VERIFY in r and DYNAAMINEN in r for r in runit)
    if dynaaminen:
        # DEPLOY-VERIFY-MUUTTUNEET-SIVUT (10.9): lista tulee ajon diffista
        # (scripts/verify_targets.py), ydin aina mukana. Staattinen lista
        # mitattiin vihreaksi sivuilla jotka eivat muuttuneet.
        verifioidut = list(CORE)
    else:
        verifioidut = _polut(runit, _VERIFY_RE) if any(VERIFY in r for r in runit) else None
    return {"servattavat": servattavat, "pushaa": pushaa, "verifioidut": verifioidut,
            "dynaaminen": dynaaminen}


def _kattaa(tiedosto: str, lisatyt: list[str]) -> bool:
    for p in lisatyt:
        if p.endswith("/") and tiedosto.startswith(p):
            return True
        if p == tiedosto:
            return True
    return False


def puutteet(nimi: str, runit: list[str], juuri: Path = ROOT) -> list[str]:
    a = analysoi(runit)
    if not (a["servattavat"] and a["pushaa"]):
        return []
    if nimi in POIKKEUKSET:
        return []
    if a["verifioidut"] is None:
        return [f"{nimi}: lisaa {sorted(set(a['servattavat']))[:4]} ja pushaa, "
                f"mutta ei aja {VERIFY} - sivu jaa repoon eika paady liveen"]
    viat = []
    if not a["verifioidut"]:
        viat.append(f"{nimi}: {VERIFY} ilman argumentteja verifioi oletussivut "
                    "(fpl.html index.html), ei niita joita tama workflow lisaa")
    for f in a["verifioidut"]:
        if not (juuri / f).exists():
            viat.append(f"{nimi}: {VERIFY} {f} - tiedostoa ei ole repossa")
        if not a["dynaaminen"] and not _kattaa(f, a["servattavat"]):
            viat.append(f"{nimi}: {VERIFY} {f} - workflow ei lisaa sita, "
                        "joten verifiointi mittaa vaaraa sivua")
    return viat


def _workflowt() -> list[tuple[str, list[str]]]:
    out = []
    for p in sorted(WORKFLOWS.glob("*.yml")):
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        out.append((p.name, _run_lohkot(doc)))
    return out


def test_servattavan_sivun_committaava_workflow_verifioi_deployn():
    viat = [v for nimi, runit in _workflowt() for v in puutteet(nimi, runit)]
    assert not viat, "\n".join(viat)


def test_portti_nakee_edes_yhden_verifioivan_workflown():
    """Portti joka ei loyda mitaan mitattavaa on vihrea vaarasta syysta."""
    osumat = [n for n, r in _workflowt() if analysoi(r)["servattavat"]]
    assert "ucl-refresh.yml" in osumat and "accuracy-log.yml" in osumat, osumat


def test_poikkeuslistalla_ei_ole_kuolleita_rivaja():
    nimet = {n for n, _ in _workflowt()}
    for n, syy in POIKKEUKSET.items():
        assert n in nimet, f"poikkeus {n} ei vastaa yhtaan workflow'ta"
        assert len(syy.strip()) >= 20, f"poikkeus {n} ilman perustelua"


# --- Portti mitataan synteettisilla workflow'illa, ei nykyhetken repolla ---

_PUSH = 'git add ucl/index.html\ngit commit -m "x [skip ci]"\ngit push origin main\n'


def test_portti_kaataa_workflown_joka_committaa_sivun_ilman_verifiointia():
    assert puutteet("synt.yml", [_PUSH]), "sivu committiin ilman deployta lapaisi"


def test_portti_hyvaksyy_verifioinnin_omalla_sivulla(tmp_path):
    (tmp_path / "ucl").mkdir()
    (tmp_path / "ucl" / "index.html").write_text("x", encoding="utf-8")
    ok = puutteet("synt.yml", [_PUSH, f"bash scripts/{VERIFY} ucl/index.html"],
                  juuri=tmp_path)
    assert not ok, ok


def test_portti_kaataa_verifioinnin_vaaralla_sivulla(tmp_path):
    (tmp_path / "fpl.html").write_text("x", encoding="utf-8")
    viat = puutteet("synt.yml", [_PUSH, f"bash scripts/{VERIFY} fpl.html"],
                    juuri=tmp_path)
    assert viat and "vaaraa sivua" in viat[0], viat


def test_portti_ei_valita_datasta_ilman_sivua():
    """`data/*.json` ei ole CF Pagesin sivu: eri portti, ei tama."""
    assert not puutteet("synt.yml", [
        'git add data/x.json\ngit push origin main\n'])


def test_portti_ei_valita_workflowsta_joka_ei_pushaa():
    assert not puutteet("synt.yml", ["git add ucl/index.html\n"])


def test_dynaaminen_lista_kattaa_workflown_lisaamat_sivut():
    """Dynaaminen muoto: verify_targets lukee git diffin, joten sen tulos
    sisaltaa juuri ne sivut jotka workflow committoi (+ ydin). Mitataan
    funktiolla, ei nykyhetken diffilla."""
    from scripts.verify_targets import targets
    diff = ["fpl/defence.html", "fpl/stats.html", "data/fpl_stats.json"]
    got = targets(diff)
    assert "fpl/defence.html" in got and "fpl/stats.html" in got
    assert "data/fpl_stats.json" not in got
    for c in CORE:
        assert c in got and (ROOT / c).exists(), c


def test_dynaaminen_muoto_tunnistetaan_eika_tokenisoida():
    runit = ["git add fpl/defence.html", "git push",
             "bash scripts/verify_live_pages.sh $(python scripts/verify_targets.py)"]
    a = analysoi(runit)
    assert a["dynaaminen"] and a["verifioidut"] == list(CORE)
    assert puutteet("x.yml", runit) == []
