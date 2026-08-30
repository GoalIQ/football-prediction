"""Portti: workflow'n `git add` -lista on builderin kirjoituskohteiden ylijoukko.

Tausta (30.8.2026). `fpl-page-refresh` kaatui kolmesti heti UTC-keskiyon
jalkeen (26.8 00:52, 28.8 00:17, 30.8 02:38) ja loki nimesi syyn vaarin:
"Push-yritys N epaonnistui (kilpailu?)". Kyse ei ollut kilpailusta.
`build_fpl_page.py` kirjoittaa `predictions.html`:n (LIVE_BACK/FWD-ikkuna
lasketaan `date.today()`:sta, joten se muuttuu vuorokauden vaihtuessa), mutta
workflow'n `git add` -whitelist ei sisaltanyt sita -> tiedosto jai
vaiheistamatta -> `git rebase` kieltaytyi -> kaikki viisi yritysta kaatuivat
samaan asiaan. Sivu jai 5 h dataa jalkeen eika mikaan huutanut: data-workflow
oli vihrea ja sivu-workflow'n punaisuus luettiin ohimenevaksi kilpailuksi.

Tama portti lukee kirjoituskohteet builderin AST:sta, ei listasta eika
kommentista, joten uusi kirjoituskohde ei voi livahtaa lapi hiljaa.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"

# Builderin juurimuuttujat -> repojuuri.
_JUURET = {"ROOT", "_FP_ROOT"}


def _ratkaise(solmu: ast.AST, vakiot: dict) -> str | None:
    """`ROOT / "fpl" / f"{x}.html"` -> "fpl/*". None jos ei ole polku."""
    if isinstance(solmu, ast.Name):
        if solmu.id in _JUURET:
            return ""
        return vakiot.get(solmu.id)
    if isinstance(solmu, ast.BinOp) and isinstance(solmu.op, ast.Div):
        vasen = _ratkaise(solmu.left, vakiot)
        if vasen is None:
            return None
        oikea = solmu.right
        if isinstance(oikea, ast.Constant) and isinstance(oikea.value, str):
            osa = oikea.value
        elif isinstance(oikea, ast.JoinedStr):
            # f-string-nimi (esim. per-seura-sivu) -> jokerisegmentti, jolloin
            # kattavuus vaatii hakemistotokenin eika yksittaista tiedostoa.
            osa = "*"
        else:
            return None
        return (vasen + "/" + osa).lstrip("/")
    return None


def _lue_polkuvakiot(puu: ast.Module) -> dict:
    """Moduulitason `NIMI = ROOT / "a" / "b"` -> {"NIMI": "a/b"}."""
    vakiot: dict = {}
    for solmu in puu.body:
        if not isinstance(solmu, ast.Assign) or len(solmu.targets) != 1:
            continue
        kohde = solmu.targets[0]
        if not isinstance(kohde, ast.Name):
            continue
        polku = _ratkaise(solmu.value, vakiot)
        if polku:
            vakiot[kohde.id] = polku
    return vakiot


def kirjoituskohteet(skripti: Path) -> set:
    """Builderin kirjoittamat repopolut AST:sta.

    Kirjoitukseksi lasketaan `X.write_text(...)`, `write_*(X, ...)` ja
    `open(X, "w")` - kaikki tavat joilla nama builderit kirjoittavat levylle.
    """
    puu = ast.parse(skripti.read_text(encoding="utf-8"))
    vakiot = _lue_polkuvakiot(puu)
    kohteet: set = set()

    for solmu in ast.walk(puu):
        if not isinstance(solmu, ast.Call):
            continue
        f = solmu.func
        ehdokas = None
        if isinstance(f, ast.Attribute) and f.attr in {"write_text", "write_bytes"}:
            ehdokas = f.value
        elif isinstance(f, ast.Name) and f.id.startswith("write_") and solmu.args:
            ehdokas = solmu.args[0]
        elif isinstance(f, ast.Name) and f.id == "open" and len(solmu.args) >= 2:
            tila = solmu.args[1]
            if isinstance(tila, ast.Constant) and "w" in str(tila.value):
                ehdokas = solmu.args[0]
        if ehdokas is None:
            continue
        polku = _ratkaise(ehdokas, vakiot)
        if polku:
            kohteet.add(polku)
    return kohteet


# 🔴 Molemmat kutsumuodot on lueteltava. Ensimmainen versio tasta portista
# etsi vain muotoa `build_fpl_page.py` ja oli siksi sokea `accuracy-log`ille,
# joka ajaa saman builderin moduulina (`python -m scripts.build_fpl_page`).
# Portti oli vihrea mittaamalla vaaraa koodipolkua.
BUILDERIT = {
    "scripts/build_fpl_page.py": ["scripts.build_fpl_page", "build_fpl_page.py"],
    "scripts/build_fpl_longtail.py": [
        "scripts.build_fpl_longtail",
        "build_fpl_longtail.py",
    ],
    "scripts/build_prediction_pages.py": [
        "scripts.build_prediction_pages",
        "build_prediction_pages.py",
    ],
}


def _rivit_ilman_kommentteja(run: str) -> list:
    return [r for r in run.splitlines() if not r.strip().startswith("#")]


def workflow_tyot_jotka_bakettavat() -> list:
    """[(workflow, git add -tokenit, builderin kirjoituskohteet), ...]"""
    tulos = []
    for polku in sorted(WORKFLOWS.glob("*.yml")):
        wf = yaml.safe_load(polku.read_text(encoding="utf-8"))
        if not isinstance(wf, dict):
            continue
        for job in wf.get("jobs", {}).values():
            steps = job.get("steps", []) or []
            rivit = []
            for s in steps:
                run = s.get("run")
                if run:
                    rivit += _rivit_ilman_kommentteja(run)
            teksti = "\n".join(rivit)

            kohteet: set = set()
            for skripti, kutsut in BUILDERIT.items():
                if any(k in teksti for k in kutsut):
                    kohteet |= kirjoituskohteet(ROOT / skripti)
            if not kohteet:
                continue

            tokenit = []
            for r in rivit:
                m = re.search(r"\bgit add (.+)", r)
                if m:
                    osa = m.group(1).split("||")[0].split("&&")[0]
                    tokenit += [t for t in osa.replace("\\", " ").split() if t]
            tulos.append((polku.name, tokenit, kohteet))
    return tulos


def kattaako(tokenit: list, kohde: str) -> bool:
    """Tasmays on token- tai hakemistotasolla, EI merkkijonon osumaa.

    `fpl/` ei saa kuitata `fpl.html`:aa eika `index.html` `fpl/index.html`:aa.
    """
    for t in tokenit:
        if t == kohde:
            return True
        hakemisto = t if t.endswith("/") else t + "/"
        if kohde.startswith(hakemisto):
            return True
    return False


def test_loytyy_edes_yksi_bakettava_workflow():
    """Kontrolli: portti ei saa lapaista tyhjana."""
    tyot = workflow_tyot_jotka_bakettavat()
    assert tyot, "yksikaan workflow ei aja buildereita - portti mittaisi tyhjaa"
    nimet = {t[0] for t in tyot}
    assert "fpl-page-refresh.yml" in nimet
    assert "accuracy-log.yml" in nimet


def test_builderin_kirjoituskohteet_loytyvat():
    """Kontrolli: AST-poiminta ei saa palauttaa tyhjaa joukkoa."""
    kohteet = kirjoituskohteet(ROOT / "scripts" / "build_fpl_page.py")
    for odotettu in (
        "predictions.html",
        "fpl.html",
        "index.html",
        "world-cup-2026-predictions.html",
    ):
        assert odotettu in kohteet, (odotettu, sorted(kohteet))


@pytest.mark.parametrize(
    "wf,tokenit,kohteet",
    [pytest.param(*t, id=t[0]) for t in workflow_tyot_jotka_bakettavat()],
)
def test_git_add_kattaa_builderin_kirjoituskohteet(wf, tokenit, kohteet):
    puuttuvat = sorted(k for k in kohteet if not kattaako(tokenit, k))
    assert not puuttuvat, (
        wf
        + ": builder kirjoittaa naihin mutta `git add` ei vaiheista niita: "
        + str(puuttuvat)
        + ". Vaiheistamaton tiedosto saa `git rebase`:n kieltaytymaan ja "
        "push-silmukan kaatumaan viidesti samaan asiaan."
    )


def test_kattaako_ei_hyvaksy_merkkijonon_osumaa():
    """Negatiivinen kontrolli itse tasmaykselle."""
    assert not kattaako(["fpl/"], "fpl.html")
    assert not kattaako(["index.html"], "fpl/index.html")
    assert not kattaako(["predictions/"], "predictions.html")
    assert kattaako(["fpl/"], "fpl/club/arsenal.html")
    assert kattaako(["predictions.html"], "predictions.html")


def test_push_silmukka_kayttaa_autostashia():
    """Ilman autostashia yksikin vaiheistamaton tiedosto jaadyttaa silmukan."""
    puuttuu = []
    for polku in sorted(WORKFLOWS.glob("*.yml")):
        teksti = polku.read_text(encoding="utf-8")
        if "for i in 1 2 3 4 5" not in teksti:
            continue
        for rivi in teksti.splitlines():
            r = rivi.strip()
            if r.startswith("#"):
                continue
            if "git rebase" in r and "--abort" not in r and "--autostash" not in r:
                puuttuu.append(polku.name + ": " + r)
    assert not puuttuu, "push-silmukka rebasettaa ilman --autostashia: " + str(puuttuu)
