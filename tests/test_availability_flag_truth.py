"""PORTTI: hakurivin saatavuusmerkki ei saa vaittaa enempaa kuin lahde.

MITATTU VIKA 16.9: `PlayerSearch.svelte` palautti sanan `out` kahdesta eri
syysta — FPL:n saatavuuslipusta JA siita ettei pelaaja ole projektiossa.
Tuotannon artefaktissa samana paivana 178 `excluded`-rivista kaksi oli
`below_min_xp`:

    id 395 Lewis  (MCI)  status `a`, chance null, news ""   -> rivi sanoi "out"
    id 344 Gruev  (LEE)  status `d`, chance 25             -> rivi sanoi "out"

FPL:n oma bootstrap sanoo Lewisista `status: "a"`. Sanoimme siis hakurivilla
eri asian kuin lahde, ja lukija tarkistaa sen yhdella ilmaisella kutsulla.

Sama vika oli korttisaatteessa ("out in FPL") ja julkaisuportti hylkasi sen
aamulla. Hylkays EI kattanut tata, koska portti etsii LITERAALIA `out in FPL`
ja hakurivi rakentaa saman vaitteen palasista (`{ text: 'out' }`). Siksi tama
testi ajaa FUNKTIOTA eika greppaa merkkijonoa (muisti:
`portti-kirjoitetaan-nahdylle-muodolle`, `testi-kutsuu-funktiota-ei-kutsupaikkaa`).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

NEWLINE = chr(10)
ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "web" / "pro-spa" / "src" / "lib" / "availabilityFlag.ts"

# (status, chance_next, in_projection, excluded_reason) -> odotettu merkki
TAPAUKSET = [
    # FPL:n lippu: "out" on tosi
    ({"status": "i", "chance_next": 0, "in_projection": False}, "out"),
    ({"status": "s", "chance_next": 0, "in_projection": False}, "out"),
    ({"status": "n", "chance_next": None, "in_projection": False}, "out"),
    # Seurasta lahtenyt EI ole kierrossidonnainen -> oma sanansa
    ({"status": "u", "chance_next": 0, "in_projection": False}, "left club"),
    # Kyseenalainen: FPL:n oma prosentti, ei meidan tulkintaamme
    ({"status": "d", "chance_next": 25, "in_projection": True}, "25%"),
    ({"status": "d", "chance_next": None, "in_projection": True}, "doubt"),
    # 🔴 TUOTANNON TAPAUS 16.9: ei projektiota MUTTA FPL sanoo `a`.
    # "out" tassa on suoraan epatosi.
    ({"status": "a", "chance_next": None, "in_projection": False,
      "excluded_reason": "below_min_xp"}, "no xP"),
    # Pelikelpoinen ja projektiossa -> ei merkkia lainkaan
    ({"status": "a", "chance_next": None, "in_projection": True}, None),
]


def _node() -> str:
    """Node 22.6+ strippaa TS-tyypit natiivisti. Sama tulkki jolla mobiilirepo
    ajaa `node lib/*.test.ts`."""
    for cand in ("node", "node.exe"):
        try:
            subprocess.run([cand, "-v"], capture_output=True, timeout=20, check=True)
            return cand
        except Exception:
            continue
    pytest.skip("node puuttuu")
    return "node"


def _aja(rows: list[dict]) -> list:
    """Ajaa OIKEAN TS-moduulin Nodella (type-stripping, Node 22.6+).

    Portti ei saa olla kopio logiikasta Pythonissa: silloin se vartioisi
    kopiota eika sita mita kayttaja nakee. Moduuli importataan sellaisenaan
    siita tiedostosta jonka SPA buildaa.
    """
    if not MODULE.exists():
        pytest.skip("availabilityFlag.ts puuttuu")
    url = MODULE.as_uri()
    ohjelma = (
        "import { availabilityFlag } from " + json.dumps(url) + ";" + NEWLINE
        + "console.log(JSON.stringify("
        + json.dumps(rows) + ".map(availabilityFlag)));"
    )
    out = subprocess.run(
        [_node(), "--disable-warning=ExperimentalWarning",
         "--experimental-strip-types", "--input-type=module", "-e", ohjelma],
        capture_output=True, text=True, timeout=90)
    if out.returncode != 0 and "strip-types" in (out.stderr or ""):
        out = subprocess.run(
            [_node(), "--input-type=module", "-e", ohjelma],
            capture_output=True, text=True, timeout=90)
    assert out.returncode == 0, out.stderr[-1500:]
    return json.loads(out.stdout)


def test_merkki_vastaa_rivia_jokaisessa_luokassa() -> None:
    rivit = [t[0] for t in TAPAUKSET]
    odotetut = [t[1] for t in TAPAUKSET]
    tulos = _aja(rivit)
    saadut = [(f or {}).get("text") if f else None for f in tulos]
    assert saadut == odotetut, list(zip(rivit, saadut, odotetut))


def test_pelikelpoinen_ei_saa_saada_out_merkkia() -> None:
    """EROTTELEVA: tama on se rivi joka oli tuotannossa vaarin. Ilman tata
    koko testi menisi lapi myos vanhalla toteutuksella, koska muut luokat
    olivat jo oikein."""
    tulos = _aja([{"status": "a", "chance_next": None, "in_projection": False,
                   "excluded_reason": "below_min_xp"}])
    merkki = tulos[0]
    assert merkki is not None, "rivin pitaa kertoa ettei xP:ta ole"
    assert merkki["text"] != "out", (
        "FPL sanoo `a` — 'out' olisi eri asia kuin lahde")
    assert merkki["tone"] != "out", (
        "neutraali savy: tama ei ole saatavuusvaite vaan tieto omasta luvustamme")


def test_seurasta_lahtenyt_ei_ole_kierrossidonnainen() -> None:
    """`u` on pysyva tila, `i` ei. Sama sana molemmille kadottaisi eron."""
    tulos = _aja([{"status": "u", "chance_next": 0, "in_projection": False},
                  {"status": "i", "chance_next": 0, "in_projection": False}])
    assert tulos[0]["text"] != tulos[1]["text"]
