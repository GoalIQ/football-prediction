# -*- coding: utf-8 -*-
"""Portti: sivun COMMITOINTI ja sen DEPLOY eivat saa erota toisistaan.

TAUSTA (7.9.2026). `fpl-page-refresh.yml` oli punainen kahdesti yossa
virheella "goaliq.app ei servaa HEAD-sisaltoa". Diagnoosi ei ollut se mita
virheteksti vaitti (Pages-deploy failasi). Mitattu: live servasi tasmalleen
commitin `5d217815b` fpl.html + index.html kun mainissa oli `7a81f8c29`.

Ketju:
  1. `fpl-data-refresh.yml` committaa fpl.html + index.html viestilla
     `[skip ci]`. CF Pages on direct upload (cutover 15.8) eika deployaa
     pushista, ja `[skip ci]` estaa muutkin workflowt. Sivu jai repoon.
  2. `fpl-page-refresh.yml` dispatchasi hub-deployn vain ehdolla
     `steps.push.outputs.pushed == 'true'`. Koska data-refresh oli jo
     kirjoittanut samat sivut, tama ajo sanoi "Ei muutoksia" ja ohitti
     dispatchin.
  3. Jaljelle jai ajo joka VERIFIOI liven mutta ei voinut KORJATA sita.

Vikaluokka on se etta deployn ehto oli "kuka kirjoitti" eika "mita live
servaa". Korjaus on `scripts/verify_live_pages.sh`, joka mittaa ja
dispatchaa mittauksen perusteella. Tama testi pitaa huolen etta uusi
sivuja committoiva workflow ei voi UNOHTAA sita: lisays listalle vaatii
perustelun kirjoittamista, jolloin unohdus muuttuu tietoiseksi valinnaksi.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"
VERIFY = "scripts/verify_live_pages.sh"

# Sivut jotka goaliq.app servaa ja joita builderit kirjoittavat.
SIVUT = ("fpl.html", "index.html", "predictions.html")

# POIKKEUSLISTA. Avain = workflow-tiedoston nimi, arvo = PERUSTELU.
# Tyhja perustelu ei kelpaa: rivin lisaaminen on kirjoitustyota, jolloin
# vahingossa syntyva poikkeus on kalliimpi kuin oikean asian tekeminen.
POIKKEUKSET: dict[str, str] = {}


def _workflow_tekstit() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8", errors="replace")
            for p in sorted(WF.glob("*.yml"))}


def _committaa_sivuja(teksti: str) -> list[str]:
    """Workflow'n `git add` -rivit jotka koskevat servattua sivua."""
    osumat = []
    for rivi in teksti.splitlines():
        if "git add" not in rivi:
            continue
        for sivu in SIVUT:
            # Sanaraja: `index.html` ei saa osua `sitemap-index.html`:aan.
            if re.search(r"(?<![\w./-])" + re.escape(sivu), rivi):
                osumat.append(rivi.strip())
                break
    return osumat


def test_sivuja_committoiva_workflow_myos_verifioi_liven():
    puuttuu = []
    for nimi, teksti in _workflow_tekstit().items():
        if not _committaa_sivuja(teksti):
            continue
        if nimi in POIKKEUKSET:
            assert POIKKEUKSET[nimi].strip(), (
                f"{nimi} on poikkeuslistalla ilman perustelua")
            continue
        if VERIFY not in teksti:
            puuttuu.append(nimi)
    assert not puuttuu, (
        "nama workflowt committoivat servattavan sivun mutta eivat aja "
        f"{VERIFY}:aa:\n  " + "\n  ".join(puuttuu) +
        "\n(sivu jaa repoon menematta ulos; ks. taman tiedoston otsikko)")


def test_verify_dispatchaa_mittauksen_eika_pushin_perusteella():
    """Ydin: skripti ei saa palata vanhaan ehtoon.

    Jos dispatch ripustettaisiin taas `pushed`-lippuun, koko portti olisi
    vihrea samalla kun vika olisi ennallaan.
    """
    s = (ROOT / VERIFY).read_text(encoding="utf-8", errors="replace")
    assert "hub-deploy.yml" in s, "skripti ei dispatchaa hub-deployta"
    assert "pushed" not in s, (
        "dispatch nojaa taas pushed-lippuun - ehdon on oltava mittaus")


def test_yksikaan_workflow_ei_dispatchaa_hub_deployta_pushed_ehdolla():
    """NEGATIIVINEN KONTROLLI: vanha muoto ei saa jaada eloon rinnalle.

    Ilman tata korjaus olisi voinut olla lisays eika vaihto, ja vanha
    sokea haara olisi jaanyt tekemaan saman vian toisessa tiedostossa.
    """
    jaljella = []
    for nimi, teksti in _workflow_tekstit().items():
        rivit = teksti.splitlines()
        for i, rivi in enumerate(rivit):
            if "hub-deploy.yml" not in rivi:
                continue
            # Etsi askeleen `if:` korkeintaan 12 rivia ylospain.
            konteksti = "\n".join(rivit[max(0, i - 12):i])
            if "steps.push.outputs.pushed" in konteksti:
                jaljella.append(f"{nimi}:{i + 1}")
    assert not jaljella, (
        "hub-deploy dispatchataan yha 'pushasinko mina' -ehdolla: "
        + ", ".join(jaljella))


def test_kontrolli_loytaa_puuttuvan_verifyn():
    """NEGATIIVINEN KONTROLLI havaitsimelle itselleen.

    Ilman tata `_committaa_sivuja` voisi palauttaa tyhjaa (esim. regex
    lakkaisi osumasta) ja paaportti olisi vihrea tyhjana. Sama ansa kuin
    'kontrolli lapaisi tyhjana' 25.8.
    """
    keksitty = 'run: |\n  git add fpl.html sitemap.xml\n'
    assert _committaa_sivuja(keksitty), "havaitsin ei nae git addia lainkaan"
    assert not _committaa_sivuja('run: git add data/fpl_xp_projections.json')
    assert not _committaa_sivuja('run: git add sitemap-index.html'), (
        "sanaraja puuttuu: sitemap-index.html ei ole index.html")


def test_portti_nakee_oikeat_workflowt_juuri_nyt():
    """Ilman tata paaportti voisi olla vihrea siksi etta se ei loyda
    YHTAAN sivua committoivaa workflow'ta."""
    nimet = [n for n, t in _workflow_tekstit().items() if _committaa_sivuja(t)]
    assert len(nimet) >= 3, f"odotettiin >= 3 sivubuilderia, loytyi {nimet}"
