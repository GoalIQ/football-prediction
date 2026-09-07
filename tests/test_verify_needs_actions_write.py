# -*- coding: utf-8 -*-
"""Portti: itsekorjaava askel tarvitsee oikeuden korjata.

🔴 TAUSTA (7.9.2026). 17. kierroksella vaihdoin deployn ehdon mittaukseksi:
`verify_live_pages.sh` dispatchaa `hub-deploy`n aina kun live != repo,
riippumatta siita kuka sivun kirjoitti. Kytkin sen KOLMEEN workflow'hun.

Kaksi niista oli saanut `actions: write` jo 19.8. Kolmas ei, enka huomannut.
Dispatch palautti joka kerta:

    HTTP 403: Resource not accessible by integration

Skripti kasitteli sen VAROITUKSENA, jatkoi pollausta 8 minuuttia ja kaatui
sitten virheella joka nimesi vaaran mekanismin: *"goaliq.app EI servaa repon
sivuja (deploy-verify)"*. Live oli tosiasiassa kunnossa; korjausmekanismi ei
vain voinut korjata mitaan. Workflow oli punainen kahdesti perakkain, ja
autopilotin S1 nosti sen - pysyvasti punainen putki nielee seuraavan oikean
regression (muisti: `pysyvasti-punainen-putki-nielee-regression`).

Portti: jos workflow ajaa skriptin, sen on julistettava oikeus jota skripti
tarvitsee. Neljas workflow ei voi unohtaa sita.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF_DIR = ROOT / ".github" / "workflows"
SKRIPTI = "verify_live_pages.sh"


def _workflowt_jotka_ajavat_skriptin() -> list[Path]:
    return sorted(f for f in WF_DIR.glob("*.yml")
                  if SKRIPTI in f.read_text(encoding="utf-8", errors="replace"))


def _permissions(teksti: str) -> str:
    """Ylatason `permissions:`-lohko ILMAN KOMMENTTEJA.

    🔴 Ensimmainen versio tasta jatti kommentit sisaan, ja lohkossa on
    kommentti joka SELITTAA miksi `actions: write` tarvitaan. Haku osui
    siihen, joten portti oli vihrea myos silloin kun oikeus oli poistettu -
    mutaatio selvisi. Sama kuvio kuin `shareCardLocale.test.ts`:ssa samana
    paivana: portti loysi oman selityksensa.
    """
    m = re.search(r"^permissions:\s*\n((?:[ \t]+.*\n)+)", teksti, re.M)
    if not m:
        return ""
    return "\n".join(r for r in m.group(1).splitlines()
                     if not r.lstrip().startswith("#"))


def test_verify_ajavilla_workflowilla_on_actions_write():
    tiedostot = _workflowt_jotka_ajavat_skriptin()
    assert tiedostot, f"yksikaan workflow ei aja {SKRIPTI}:aa - onko se poistettu?"
    puuttuu = []
    for f in tiedostot:
        teksti = f.read_text(encoding="utf-8", errors="replace")
        if not re.search(r"\bactions:\s*write\b", _permissions(teksti)):
            puuttuu.append(f.name)
    assert not puuttuu, (
        f"nama workflowt ajavat {SKRIPTI}:n itsekorjauksen mutta EIVAT "
        "julista 'permissions: actions: write'. Dispatch palauttaa 403 ja "
        "askel kaatuu virheella joka nimeaa vaaran mekanismin:\n  "
        + "\n  ".join(puuttuu))


def test_kontrolli_havaitsin_lukee_oikeaa_lohkoa():
    """NEGATIIVINEN KONTROLLI. Ilman tata testi voisi olla vihrea siksi etta
    `_permissions` palauttaa tyhjaa, tai siksi etta se osuu johonkin muuhun
    kuin ylatason lohkoon."""
    kelpaa = "permissions:\n  contents: write\n  actions: write\n\njobs:\n"
    ei_kelpaa = "permissions:\n  contents: write\n\njobs:\n"
    # Askeltason `actions: write` EI kelpaa ylatason lohkoksi.
    vaara_paikka = "permissions:\n  contents: write\n\njobs:\n  x:\n    actions: write\n"

    # 🔴 Kommentti joka SELITTAA oikeuden ei ole oikeus.
    vain_kommentti = (
        "permissions:\n  contents: write\n"
        "  # tarvitaan actions: write kun dispatchataan\n\njobs:\n")
    assert not re.search(r"\bactions:\s*write\b", _permissions(vain_kommentti))

    assert re.search(r"\bactions:\s*write\b", _permissions(kelpaa))
    assert not re.search(r"\bactions:\s*write\b", _permissions(ei_kelpaa))
    assert not re.search(r"\bactions:\s*write\b", _permissions(vaara_paikka))
    assert _permissions("jobs:\n  x: y\n") == ""


def test_skripti_kaatuu_heti_jos_dispatch_ei_onnistu():
    """Epaonnistunut korjaus on OMA vikansa. Aiemmin se oli `::warning::`,
    ja askel kaatui 8 min myohemmin vaaralla selityksella."""
    s = (ROOT / "scripts" / SKRIPTI).read_text(encoding="utf-8")
    assert "::error::hub-deployn dispatch EPAONNISTUI" in s
    assert "exit 2" in s, "dispatch-virhe ei keskeyta ajoa"
