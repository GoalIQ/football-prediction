# -*- coding: utf-8 -*-
"""Portti: FAQ:n "Last updated" ei voi jaada jalkeen sisallostaan.

TAUSTA (5.9.2026): `faq.html` sanoi "Last updated: 25 July 2026", mutta sen
sisalto puhui neljassa kohdassa 12. syyskuun ilmaisikkunasta. Leima oli siis
kuusi viikkoa jaljessa omaa sisaltoaan sivulla, jonka puoli tehtavaa on
vastata kysymykseen "paljonko Premium maksaa". Mikaan ei huutanut siita.

MIKSI TAMA MUOTO EIKA PAIVAMAARAVERTAILU: ensimmainen versio talla portilla
vertasi leimaa sivun myohaisimpaan mainittuun paivamaaraan. Se kaatui heti
oikeaan sisaltoon: "12 September" on TULEVA lupaus (ikkuna sulkeutuu), ei
merkki vanhentuneesta leimasta. Ja "onko sivu tuore tanaan" olisi
vaihesidottu testi, joka on vihrea siihen asti kun se lakkaa olemasta tosi —
tasan se vikaluokka jonka talon saanto 3.9 kieltaa.

INVARIANTTI ON SIIS SUHDE, EI HETKI: leiman viereen on tallennettu sivun
nakyvan copyn tiiviste. Jos copy muuttuu eika leimaa paiviteta, tiiviste ei
tasmaa ja portti kaatuu. Se pitaa riippumatta siita mika paiva tanaan on ja
riippumatta siita, mita paivamaaria copy mainitsee.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAQ = ROOT / "faq.html"

# 🔴 YKSI LUKIJA (12.9.2026). Leiman logiikka siirrettiin `src/copy_stamp.py`:hyn
# koska copyn voi muuttaa myos GENERAATTORI, ei vain ihminen: ilmaisikkunan
# sulkeutuminen 12:30 UTC poisti lupauslauseen faq.html:sta
# `check_free_window.fix()`illa, eika mikaan paivittanyt leimaa -> tama portti
# punastui ilman etta kukaan oli koskenut sivuun. Nyt sama funktio paivittaa
# leiman siella missa copy kirjoitetaan.
from src.copy_stamp import (  # noqa: E402
    HASH_RE, LEIMA_RE, copy_tiiviste, nakyva_copy)

__all__ = ["HASH_RE", "LEIMA_RE", "copy_tiiviste", "nakyva_copy"]


def test_leima_vastaa_nykyista_copya() -> None:
    teksti = FAQ.read_text(encoding="utf-8", errors="replace")

    leima = LEIMA_RE.search(teksti)
    assert leima, 'faq.html: "Last updated" -leimaa ei loytynyt odotetussa muodossa'

    tallennettu = HASH_RE.search(leima.group("attrs"))
    assert tallennettu, (
        'faq.html: leimalta puuttuu data-copy-hash. Lisaa se: '
        "python -c \"from tests.test_faq_freshness import copy_tiiviste;"
        "import pathlib;print(copy_tiiviste(pathlib.Path('faq.html')"
        '.read_text(encoding=\'utf-8\')))"'
    )

    nyt = copy_tiiviste(teksti)
    assert tallennettu.group(1) == nyt, (
        f"faq.html:n copy on muuttunut leiman jalkeen (leima sanoo "
        f"'{leima.group('pvm')}', tiiviste {tallennettu.group(1)}, nyt {nyt}). "
        "Paivita seka paivamaara etta data-copy-hash."
    )


def test_hinta_vastaus_on_auki() -> None:
    """Hinta ei saa olla klikkauksen takana sivulla joka vastaa hintaan."""
    teksti = FAQ.read_text(encoding="utf-8", errors="replace")
    m = re.search(
        r"<details([^>]*)>\s*<summary>How much does Premium cost[^<]*</summary>",
        teksti,
    )
    assert m, "faq.html: hintakysymysta ei loytynyt odotetussa muodossa"
    assert "open" in m.group(1), (
        "faq.html: hintavastaus ei ole auki oletuksena (<details open>)."
    )


def test_negatiivinen_kontrolli_muuttunut_copy_kaataa() -> None:
    """Kontrolli: portti EI saa olla vihrea siksi etta se ei mittaa mitaan.

    Ilman tata `nakyva_copy` voisi palauttaa tyhjan merkkijonon (esim. jos
    <body>-jako muuttuu), jolloin tiiviste olisi vakio ja tasmaisi ikuisesti.
    """
    teksti = FAQ.read_text(encoding="utf-8", errors="replace")
    copy = nakyva_copy(teksti)
    assert len(copy) > 500, "nakyva_copy palautti liian vahan -> portti on inertti"

    muokattu = teksti.replace(
        "How much does Premium cost", "How much does Premium cost per week", 1
    )
    assert copy_tiiviste(muokattu) != copy_tiiviste(teksti), (
        "copyn muutos ei muuttanut tiivistetta -> portti ei nakisi vanhentumista"
    )
