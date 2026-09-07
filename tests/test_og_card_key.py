"""OG-kortin avain ei saa vuotaa osioiden eika alihakemistojen valilla.

MITATTU 7.9.2026 (aamu): `/ucl/team-news` ja `/fpl/team-news` tuottivat saman
paljaan sluginin, joten UCL-sivu jakoi kortin jossa lukee isolla
"goaliq.app/fpl/team-news". Vaara kortti on huonompi kuin ei korttia: se on
julkinen vaite vaarasta kilpailusta.

MITATTU 7.9.2026 (ilta): sama vika kapeammalla ovella. `/fpl/points/gw2`
tuottaa paljaan avaimen `gw2`, ja mika tahansa myohemmin generoitu
`assets/brand/og/gw2-1200x630.png` olisi perinyt sen sivulle hiljaa. Korjaus
ei ole kolmas kovakoodattu ehto vaan POIKKEUSLISTA PERUSTELUINEEN: paljas
avain kelpaa vain nimetyissa hakemistoissa, ja uusi hakemisto joutuu
lisaamaan itsensa listalle nakyvasti (CLAUDE.md 6a(2)).
"""
from __future__ import annotations

import pytest

import scripts.build_fpl_longtail as bl


@pytest.fixture
def og(tmp_path, monkeypatch):
    """Korttihakemisto tmp:hen: testi ei riipu siita mita kortteja on
    generoitu talla koneella tanaan."""
    d = tmp_path / "assets" / "brand" / "og"
    d.mkdir(parents=True)
    for nimi in ("team-news", "gw2", "arsenal", "set-piece-xg",
                 "fpl-team-news", "ucl-team-news"):
        (d / f"{nimi}-1200x630.png").write_bytes(nimi.encode())
    monkeypatch.setattr(bl, "_FP_ROOT", tmp_path)
    return d


def _kuva(url: str) -> str:
    return bl._og_image(url).split("?")[0]


def test_paljas_avain_kelpaa_fpl_juuressa(og):
    """Nykyiset kortit on generoitu talla nimella, joten haara jaa voimaan."""
    assert _kuva(f"{bl.BASE}/fpl/team-news").endswith("/fpl-team-news-1200x630.png")
    (og / "fpl-team-news-1200x630.png").unlink()
    assert _kuva(f"{bl.BASE}/fpl/team-news").endswith("/team-news-1200x630.png")


def test_paljas_avain_kelpaa_artikkeleille(og):
    """`/fpl/note/*`-kortit on generoitu artikkelin sluginilla."""
    assert _kuva(f"{bl.BASE}/fpl/note/set-piece-xg").endswith(
        "/set-piece-xg-1200x630.png")


def test_arkistosivu_ei_peri_paljasta_gw_avainta(og):
    """🔴 TAMAN SHIPIN OMA VIKA. `gw2` on liian yleinen token ollakseen
    sivukohtainen avain."""
    kuva = _kuva(f"{bl.BASE}/fpl/points/gw2")
    assert "gw2-1200x630" not in kuva, (
        "arkistosivu peri kortin pelkan viimeisen palan perusteella")
    assert kuva == bl.SOCIAL_IMAGE


def test_seurasivu_ei_peri_paljasta_avainta(og):
    kuva = _kuva(f"{bl.BASE}/fpl/club/arsenal")
    assert "arsenal-1200x630" not in kuva
    assert kuva == bl.SOCIAL_IMAGE


def test_ucl_ei_peri_fpln_korttia(og):
    """7.9 aamun loydos: eri osio, sama viimeinen pala."""
    assert _kuva(f"{bl.BASE}/ucl/team-news").endswith("/ucl-team-news-1200x630.png")
    (og / "ucl-team-news-1200x630.png").unlink()
    assert _kuva(f"{bl.BASE}/ucl/team-news") == bl.SOCIAL_IMAGE


def test_koko_polusta_johdettu_avain_voittaa_paljaan(og):
    """Jarjestys on merkitseva: tarkempi nimi ensin."""
    assert _kuva(f"{bl.BASE}/fpl/team-news").endswith("/fpl-team-news-1200x630.png")


def test_poikkeuslista_on_nimetty_ja_lyhyt():
    """Uusi hakemisto ei paase listalle vahingossa: se nakyy diffissa ja
    kaataa taman testin, jolloin kirjoittaja joutuu perustelemaan miksi."""
    assert bl._OG_PALJAS_AVAIN_HAKEMISTOT == ("fpl/", "fpl/note/"), (
        "Paljaan avaimen poikkeuslista muuttui. Perustele lisays "
        "`_og_image`-kommentissa ja paivita tama testi tietoisesti - "
        "avain joka on liian yleinen vuotaa kortin toiselle sivulle.")
