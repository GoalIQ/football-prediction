# -*- coding: utf-8 -*-
"""A2 (ulkoasuohjelma WP2, 1.11.2026): landingin hero-CTA vie suoraan kassaan.

MITATTU 1.11: hero "Get Premium · €25 a year" vei osoitteeseen
`pro.goaliq.app/?tab=premium` (esikatselu + kirjautumislaatikko), kun
hintapaneelin "Get the season pass" vei suoraan `/checkout?plan=season`.
Innokkain kavija sai yhden askeleen enemman. Nappi on GEN:FREE-CTA-lohkossa,
jonka `check_free_window.py --fix` renderoi `src.free_window`ista, joten
korjaus on generaattorissa ja portti lukee seka generaattorin etta sivun.
Teksti ja hinta eivat muutu (kertamaksupassi on oma pakettinsa, WP6).
"""
from __future__ import annotations

import re
from pathlib import Path

from src import free_window as FW

ROOT = Path(__file__).resolve().parents[1]


def _href(html: str, cta: str) -> str:
    m = re.search(rf'<a [^>]*href="([^"]+)"[^>]*data-cta="{cta}"', html)
    assert m, f'data-cta="{cta}" puuttuu'
    return m.group(1)


def test_hero_ja_hintapaneeli_vievat_samaan_kassaan():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    hero = _href(html, "hero-premium")
    paneeli = _href(html, "pricing-season")
    assert hero == paneeli == FW.season_checkout_url() == "https://pro.goaliq.app/checkout?plan=season"


def test_generaattori_kirjoittaa_kassaosoitteen_ja_saman_tekstin():
    nappi = FW.hero_cta_closed_html()
    assert f'href="{FW.season_checkout_url()}"' in nappi
    assert "tab=premium" not in nappi
    # WP6 (4.11.2026): vuosipaketti on kertamaksu -> src.price_copy.season_cta.
    assert "Get Premium &middot; &euro;25 for the season &#9656;</a>" in nappi
    assert 'data-cta="hero-premium"' in nappi


def test_sivun_lohko_on_generaattorin_tuloste():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    m = re.search(r"<!-- GEN:FREE-CTA-START[^>]*-->\n?(.*?)\n?<!-- GEN:FREE-CTA-END -->", html, re.S)
    assert m and m.group(1).strip() == FW.hero_cta_html().strip()
