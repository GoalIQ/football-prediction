"""COPY-SYNC-portti: pysyva teksti ei sido ikkunan pituutta eika myy ilmaista kapteenia (6.11.2026).

Ikkuna: xP-projektiossa on enintaan kuusi kierrosta, mutta jaljella olevien maara vaihtuu.
Understat-katkossa 1.11 rakennettu projektio kattoi GW9-14, joten GW9:n jalkeen sivut
sanoivat GW10-14 ja llms.txt yha "next six gameweeks". Sama tapahtuu kauden lopussa.
Sivut johtavat luvun datasta, joten kiintea teksti ei saa vaittaa sita.

Kapteeni: api/premium.py avaa oman XI:n kapteenin ilmaiseksi, mutta openapin kuvaus
myi sita Premiumina. test_captain_free_copy_sync lukee vain html:n ja llms.txt:n.
"""
from __future__ import annotations

import re
from pathlib import Path

from api.premium import RATE_TEAM_FREE_OPEN

ROOT = Path(__file__).resolve().parents[1]
KIINTEA_IKKUNA = re.compile(r"next six gameweeks|six-gameweek", re.I)
PYSYVA_TEKSTI = ("llms.txt", "scripts/build_gw_digest.py", "scripts/render_swap_card.py")


def _lue(polku: str) -> str:
    return (ROOT / polku).read_text(encoding="utf-8")


def test_pysyva_teksti_ei_sido_ikkunan_pituutta():
    viat = {f: KIINTEA_IKKUNA.findall(_lue(f)) for f in PYSYVA_TEKSTI}
    assert not any(viat.values()), viat


def test_suunnittelijaa_ei_myyda_kuuden_kierroksen_mittaisena():
    for f in ("faq.html", "scripts/build_fpl_page.py"):
        assert "six-gameweek planner" not in _lue(f), f


def test_fpl_generaattorin_palkki_ei_lupaa_kaikkia_pelaajia():
    # Projektiossa on vain osa FPL:n pelaajista, ja ikkuna vaihtuu.
    palkki = re.search(r'<div class="sticky-cta".*?</div>', _lue("scripts/build_fpl_page.py"), re.S)
    assert palkki, "sticky-palkki puuttuu"
    assert "every player in the projection" in palkki.group(0)
    assert "all players" not in palkki.group(0)
    assert not KIINTEA_IKKUNA.search(palkki.group(0))


def test_openapi_ei_myy_ilmaista_kapteenia():
    assert "captain.pick" in RATE_TEAM_FREE_OPEN
    teksti = _lue("api/main.py")
    assert "including the captain pick" not in teksti
    assert "The rating and the captain pick are free" in teksti
