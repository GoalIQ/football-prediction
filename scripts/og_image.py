# -*- coding: utf-8 -*-
"""Sivukohtainen jakokuva (og:image) yhdesta lukijasta.

MIKSI TAMA ON OLEMASSA (5.9.2026, auditointi E2): neljalla paasivulla
(`/`, `/fpl`, `/predictions`, `/career`) oli sama geneerinen
`goaliq-social-1200x630.png`, eli jokainen jako naytti feedissa identtiselta
vaikka sivut vastaavat eri kysymyksiin. Alasivuilla oma kortti on ollut
15.8 alkaen, koska `build_fpl_longtail.py` osasi johtaa sen slugista — mutta
se logiikka oli kirjoitettu VAIN sinne, ja kaksi muuta builderia (`_page`
predictions-sivuille ja fpl.html:n head) kayttivat kovakoodattua vakiota.

Sama saanto kolmessa paikassa oli valmiiksi kolme paikkaa vanhentua eri
tahtiin. Nyt se on yksi funktio: uusi sivu saa oman korttinsa heti kun
`assets/brand/og/<slug>-1200x630.png` on olemassa, eika yksikaan builderi
tarvitse muutosta.

KORTIT generoidaan `goaliq-app/assets/brand/gen_og_cards.py`:lla.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

FP_ROOT = Path(__file__).resolve().parents[1]

#: Yhteinen kortti, kun sivulla ei ole omaa. Puuttuva tiedosto EI saa
#: tuottaa rikkinaista URLia: jaettu linkki ilman omaa kuvaa on parempi
#: kuin linkki jonka kuva on 404.
FALLBACK_REL = "assets/brand/goaliq-social-1200x630.png"


def og_image(canonical: str, base: str) -> str:
    """Palauttaa absoluuttisen og:image-URLin sivulle.

    `canonical` on sivun kanoninen URL; slug luetaan sen viimeisesta
    segmentista. Juuri (`https://goaliq.app/` tai ilman polkua) mappautuu
    slugiin `home`, koska muuten viimeinen segmentti olisi verkkotunnus.
    """
    polku_osa = canonical.split("://", 1)[-1]
    polku = polku_osa.split("/", 1)[1] if "/" in polku_osa else ""
    polku = polku.split("?", 1)[0].split("#", 1)[0].strip("/")
    slug = polku.rsplit("/", 1)[-1] if polku else "home"
    # .html-paate pois: kanoninen voi olla joko /career tai /career.html,
    # ja kortin nimi ei saa riippua siita kumpaa muotoa kutsuja kayttaa.
    if slug.endswith(".html"):
        slug = slug[: -len(".html")]
    if not slug:
        slug = "home"

    rel = f"assets/brand/og/{slug}-1200x630.png"
    tiedosto = FP_ROOT / rel
    if not tiedosto.exists():
        return f"{base}/{FALLBACK_REL}"

    # SISALTOTIIVISTE URLIIN (15.8, Villen havainto "linkkikuva edelleen toi
    # sama?"): X ja Bluesky valimuistittavat esikatselukortin URL-kohtaisesti,
    # joten sama tiedostonimi uudella sisallolla tarjoillaan vanhana. Tiiviste
    # muuttuu vain kun kuva muuttuu, eli tama ei riko valimuistia turhaan.
    tiiviste = hashlib.sha256(tiedosto.read_bytes()).hexdigest()[:8]
    return f"{base}/{rel}?v={tiiviste}"
