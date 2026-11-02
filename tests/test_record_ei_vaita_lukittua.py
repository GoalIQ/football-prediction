# -*- coding: utf-8 -*-
"""Record ei vaita ennen aloitusta kirjattua rivia lukituksi (2.11.2026, WP10).

TAUSTA. predictions.html sanoi livena "Nothing is edited once logged" ja
"N further predictions are already logged and locked". accuracy_pipeline
kuitenkin paivittaa pelaamattoman rivin aloitukseen asti (`_refreshable`):
2.11 kaikilla 2 265 pending-rivilla oli refresh_count > 0 (Arsenal-Hull
kirjattu 1.8., paivitetty 60 kertaa), ja 62/97 viikon aikana gradatusta
rivista erosi kokonaislukuprosenttina siita mita lukija oli nahnyt. Vaite
paljastui, kun SPA:n Fixtures alkoi nayttaa samat rivit ja linkata recordiin.

TOSI VAITE: rivi kirjataan ennen aloitusta, voi muuttua aloitukseen asti, ja
aloituksen jalkeen sita ei muokata ("never edited after kick-off").

Portti: niin kauan kuin putki paivittaa rivia ennen aloitusta, mikaan
julkinen pinta ei saa vaittaa kirjattua rivia muuttumattomaksi. Jos joskus
paatetaan lukita rivi kirjaushetkella, `_refreshable` poistuu ja tama testi
pitaa paivittaa tietoisesti.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Vaitteet jotka ovat epatosia, kun rivi paivittyy aloitukseen asti.
KIELLETYT = [
    r"nothing is edited once logged",
    r"logged and locked",
    r"nothing gets edited once logged",
    r"never edited once logged",
    r"not edited after (it is|it's|being) logged",
    # k2 2.11: rajaamaton "ei muokkauksia" samalla sivulla kuin "can change
    # until kickoff" (predictions.html FAQ + JSON-LD + #record-ingressi).
    r"with no edits",
    r"nothing (is |gets )?edited afterwards",
    # "nakyva luku = gradattava luku" (llms.txt, k1:n blokkaama SPA-lause).
    r"same logged prediction is what",
    r"percentages are the model's prediction, logged before",
    r"locked predictions?",
    # k2 B5 2.11: ottelusivujen generaattori (build_prediction_pages.py,
    # 3 231 sivua) sanoi ennen ottelua "logged before kickoff on <pvm> and
    # will be graded" ja metassa "Logged before kick-off in our public track
    # record and graded after", vaikka sivun luku paivittyy aloitukseen asti.
    r"this prediction was logged before kick-?off on",
    r"will be graded in our",
    r"logged before kick-?off in our public track record and graded after",
    r"away, logged before kick-?off and graded after",
]

# Pinnat: generoidut sivut, generaattorit, SPA, llms.txt. dist/ ja
# node_modules eivat ole lahdetta.
PINNAT = (
    sorted(ROOT.glob("*.html"))
    # Generoidut ottelu- ja liigasivut: generaattorin korjaus ei riita, jos
    # sivuja ei ole ajettu uudelleen (k2 B5 2.11).
    + sorted((ROOT / "predictions").rglob("*.html"))
    + [ROOT / "llms.txt"]
    + sorted((ROOT / "scripts").glob("build_*.py"))
    + sorted((ROOT / "web" / "pro-spa" / "src").rglob("*.svelte"))
    + sorted((ROOT / "web" / "pro-spa" / "src").rglob("*.ts"))
)


def _nakyva(teksti: str) -> str:
    # Python-kommentit ja HTML-kommentit pois: perustelukommentti saa lainata
    # vanhaa vaitetta.
    teksti = re.sub(r"<!--.*?-->", " ", teksti, flags=re.S)
    teksti = re.sub(r"(?m)^\s*#.*$", " ", teksti)
    teksti = re.sub(r"(?m)^\s*//.*$", " ", teksti)
    # Python-merkkijonojen saumat ("...logged "\n "and locked") yhteen.
    teksti = re.sub(r'"\s*\n\s*f?"', "", teksti)
    teksti = re.sub(r"'\s*\n\s*f?'", "", teksti)
    return re.sub(r"\s+", " ", teksti).lower()


def test_putki_paivittaa_rivia_ennen_aloitusta():
    """Portin ehto: jos tama kaatuu, rivi on lukittu kirjaushetkella ja
    KIELLETYT-lista on tarpeeton (paivita tietoisesti)."""
    src = (ROOT / "scripts" / "accuracy_pipeline.py").read_text(encoding="utf-8")
    assert "def _refreshable(" in src
    assert "kickoff > now" in src


def test_mikaan_pinta_ei_vaita_kirjattua_rivia_lukituksi():
    loydot = []
    for p in PINNAT:
        if not p.exists() or "test" in p.name:
            continue
        teksti = _nakyva(p.read_text(encoding="utf-8", errors="replace"))
        for kuvio in KIELLETYT:
            if re.search(kuvio, teksti):
                loydot.append(f"{p.relative_to(ROOT)}: '{kuvio}'")
    assert not loydot, (
        "Rivi paivittyy aloitukseen asti (accuracy_pipeline._refreshable), "
        "joten nama vaitteet ovat epatosia:\n  " + "\n  ".join(loydot))


def test_negatiivinen_kontrolli_heittomerkkisauma():
    s = "'The numbers are the '\n        f'same logged prediction is what the record grades'"
    assert re.search(r"same logged prediction is what", _nakyva(s))


def test_negatiivinen_kontrolli_nakyy_saumoista_huolimatta():
    """Python-generaattorin saumattu merkkijono ei saa piilottaa vaitetta."""
    s = '"N further predictions are "\n        f"already logged and locked for upcoming"'
    assert re.search(KIELLETYT[1], _nakyva(s))
