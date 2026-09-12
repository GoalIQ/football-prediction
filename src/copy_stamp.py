# -*- coding: utf-8 -*-
"""Copyn tuoreusleima: yksi lukija sekä portille että generaattorille.

TAUSTA (5.9.2026). `faq.html` sanoi "Last updated: 25 July 2026" samalla kun
sen sisältö puhui neljässä kohdassa 12. syyskuun ilmaisikkunasta. Portti
`tests/test_faq_freshness.py` rakennettiin mittaamaan SUHDETTA eikä hetkeä:
leiman viereen tallennetaan näkyvän copyn tiiviste, ja jos copy muuttuu
leimaa päivittämättä, portti kaatuu.

🔴 MIKSI TÄMÄ MODUULI ON OLEMASSA (12.9.2026). Portti oletti että copyn
muuttaa ihminen. Mitattu: ilmaisikkunan sulkeutuminen 12:30 UTC poisti
lupauslauseen `faq.html`:stä **generaattorilla**
(`check_free_window.fix()` -> `strip_claim` -> `write_text`), eikä mikään
päivittänyt leimaa. Tiiviste oli `834e4eca8357`, sisältö sanoi
`6a25db3a1dbb`, ja `tests.yml` punastui ilman että kukaan oli koskenut
sivuun. Portti oli oikeassa — se vain nimesi tekijäksi ihmisen jota ei ollut.

Sääntö 6a: väärästä vaihtoehdosta tehdään mahdoton. Leiman logiikka asuu
nyt tässä, ja sekä portti että jokainen copyä kirjoittava generaattori
lukee saman funktion. Generaattori joka kirjoittaa sivun uudelleen päivittää
leiman samassa kirjoituksessa, joten leima ei voi jäädä jälkeen
generoidusta muutoksesta.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import re
from pathlib import Path

LEIMA_RE = re.compile(
    r'<p class="updated"(?P<attrs>[^>]*)>\s*Last updated:\s*(?P<pvm>[^<]+?)\s*</p>'
)
HASH_RE = re.compile(r'data-copy-hash="([0-9a-f]{12})"')


def nakyva_copy(teksti: str) -> str:
    """Sivun näkyvä teksti ilman leimaa itseään.

    Kommentit, skriptit ja tyylit pois: ne eivät ole lukijalle näkyvää
    sisältöä, eikä perustelukommentin muokkaus saa pakottaa uutta
    julkaisupäivää. Leima itse rajataan pois, muuten tiiviste riippuisi
    omasta arvostaan.
    """
    runko = teksti.split("<body", 1)[1] if "<body" in teksti else teksti
    runko = re.sub(r"<!--.*?-->", " ", runko, flags=re.S)
    runko = re.sub(r"<(script|style)\b.*?</\1>", " ", runko, flags=re.S | re.I)
    runko = re.sub(r'<p class="updated">.*?</p>', " ", runko, flags=re.S)
    runko = re.sub(r'<p class="updated"[^>]*>.*?</p>', " ", runko, flags=re.S)
    runko = re.sub(r"<[^>]+>", " ", runko)
    return re.sub(r"\s+", " ", runko).strip()


def copy_tiiviste(teksti: str) -> str:
    return hashlib.sha256(nakyva_copy(teksti).encode("utf-8")).hexdigest()[:12]


def _pvm(now: _dt.datetime | None) -> str:
    d = now or _dt.datetime.now(_dt.timezone.utc)
    return f"{d.day} {d.strftime('%B')} {d.year}"


def paivita_leima(teksti: str, *, now: _dt.datetime | None = None) -> tuple[str, bool]:
    """(uusi teksti, muuttuiko). No-op jos leimaa ei ole tai se on ajan tasalla.

    Päivämäärä kirjoitetaan vain kun tiiviste on vanhentunut: muuten joka
    ajo tuottaisi tyhjän commitin pelkän päivän vaihtumisen takia (muisti:
    `rakennusaika-artefaktissa-tuottaa-tyhjan-commitin`).
    """
    leima = LEIMA_RE.search(teksti)
    if not leima:
        return teksti, False
    nyt = copy_tiiviste(teksti)
    vanha = HASH_RE.search(leima.group("attrs"))
    if vanha and vanha.group(1) == nyt:
        return teksti, False
    uusi_leima = (f'<p class="updated" data-copy-hash="{nyt}">Last updated: '
                  f'{_pvm(now)}</p>')
    return teksti[:leima.start()] + uusi_leima + teksti[leima.end():], True


def paivita_tiedoston_leima(path: Path, *,
                            now: _dt.datetime | None = None) -> bool:
    """Päivitä leima levyllä. True jos tiedosto kirjoitettiin."""
    try:
        txt = path.read_text(encoding="utf-8")
    except OSError:
        return False
    uusi, muuttui = paivita_leima(txt, now=now)
    if not muuttui:
        return False
    path.write_text(uusi, encoding="utf-8")
    return True
