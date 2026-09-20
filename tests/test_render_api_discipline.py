# -*- coding: utf-8 -*-
"""Portti: Renderin ymparistoa EI saa kirjoittaa joukkopaatepisteella.

🔴 MITATTU TUOTANTOVIKA 20.9.2026, itse aiheutettu.

`scripts/set_regional_prices.py` kutsui
    PUT /v1/services/{id}/env-vars
yhden alkion listalla. Se paatepiste **KORVAA KOKO YMPARISTON** annetulla
listalla - se ei lisaa siihen. `goaliq-api`:n 16 muuttujasta jai yksi.

Seuraukset, mitatut:
  - `STRIPE_SECRET_KEY` katosi -> ostaminen palautti 500,
  - `PREMIUM_ENFORCE` katosi -> oletus off -> koko Premium-lista
    (479 pelaajaa) annettiin ilmaiseksi kaikille,
  - `REVENUECAT_WEBHOOK_AUTH` katosi -> mobiiliosto olisi veloittanut
    antamatta Premiumia.

Mikaan ei kertonut siita. Palvelu kaynnistyi, vastasi 200 ja tarjoili dataa.
Vika loytyi sattumalta tyhjasta hintalistasta.

Oikea paatepiste on `PUT .../env-vars/{key}`: se koskee tasan yhteen
avaimeen, eika muiden arvoja laheteta lainkaan - silloin unohdettu muuttuja
EI VOI kadota. Tama testi tekee vaarasta kutsusta mahdottoman.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKANNATTAVAT = (ROOT / "scripts", ROOT / "api", ROOT / "src")

#: `/env-vars` ILMAN `/{avain}` peraa = joukkopaatepiste.
JOUKKO_RE = re.compile(r"/env-vars(?![/\w])")

#: Poikkeukset perusteluineen (CLAUDE.md 6a kohta 2).
POIKKEUKSET = {
    "scripts/set_regional_prices.py::nayta":
        "LUKEE listan (GET), ei kirjoita. Luku ei voi pyyhkia mitaan.",
}


def _literaalit(path: Path) -> list[tuple[str, int]]:
    try:
        puu = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    return [(n.value, getattr(n, "lineno", 0)) for n in ast.walk(puu)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _tiedostot() -> list[Path]:
    return sorted(p for juuri in SKANNATTAVAT if juuri.exists()
                  for p in juuri.rglob("*.py"))


def _kirjoittaako(lahde: str, rivi: int) -> bool:
    """Onko saman kutsun lahella PUT/POST/PATCH-metodi.

    Pelkka URL ei ole vaarallinen; vaarallinen on KIRJOITUS siihen. Ikkuna
    on karkea mutta konservatiivinen: mieluummin yksi turha osuma kuin
    yksi ohi mennyt.
    """
    rivit = lahde.split(chr(10))
    ala, yla = max(0, rivi - 8), min(len(rivit), rivi + 8)
    ikkuna = chr(10).join(rivit[ala:yla])
    return bool(re.search(r'method\s*=\s*["\'](PUT|POST|PATCH)', ikkuna))


def test_env_vars_joukkopaatepistetta_ei_kirjoiteta():
    loydot = []
    for p in _tiedostot():
        rel = p.relative_to(ROOT).as_posix()
        lahde = p.read_text(encoding="utf-8")
        for teksti, rivi in _literaalit(p):
            if not JOUKKO_RE.search(teksti):
                continue
            if not _kirjoittaako(lahde, rivi):
                continue
            loydot.append(f"{rel}:{rivi}")
    assert not loydot, (
        "Renderin JOUKKOpaatepisteeseen kirjoitetaan: " + ", ".join(loydot) +
        ". `PUT /v1/services/{id}/env-vars` KORVAA KOKO YMPARISTON. "
        "Kayta `PUT .../env-vars/{key}`, joka koskee yhteen avaimeen. "
        "20.9.2026 tama kutsu pyyhki tuotannosta 15 muuttujaa ja antoi "
        "Premiumin ilmaiseksi, eika mikaan kertonut siita.")


def test_poikkeuksella_on_perustelu():
    for avain, syy in POIKKEUKSET.items():
        assert str(syy).strip(), f"{avain}: poikkeukselle ei ole syyta"


def test_skanneri_loytaa_istutetun_kutsun(tmp_path):
    """Ilman tata portti voisi olla koriste."""
    f = tmp_path / "x.py"
    f.write_text(
        "import urllib.request\n"
        "def paha():\n"
        "    r = urllib.request.Request(\n"
        "        'https://api.render.com/v1/services/srv-x/env-vars',\n"
        "        data=b'[]', method='PUT')\n", encoding="utf-8")
    lahde = f.read_text(encoding="utf-8")
    osui = [t for t, rivi in _literaalit(f)
            if JOUKKO_RE.search(t) and _kirjoittaako(lahde, rivi)]
    assert osui, "skanneri ei nae joukkokutsua"


@pytest.mark.parametrize("url,joukko", [
    ("https://api.render.com/v1/services/srv-x/env-vars", True),
    ("https://api.render.com/v1/services/srv-x/env-vars?limit=20", True),
    ("https://api.render.com/v1/services/srv-x/env-vars/STRIPE_SECRET_KEY", False),
    ("https://api.render.com/v1/services/srv-x/env-vars/{VAR}", False),
])
def test_kuvio_erottaa_yhden_avaimen_joukosta(url, joukko):
    assert bool(JOUKKO_RE.search(url)) is joukko, url
