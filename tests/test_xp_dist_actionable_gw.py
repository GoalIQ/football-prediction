"""Otsikkokierros = kierros johon voi VIELA vaikuttaa (31.8.2026).

🔴 MITATTU LIVENA 31.8: `meta.deadline_gameweek = 3`, mutta `xp_dist.gw = 2`
kaikilla 519 pelaajalla, ja `components_gw = 2`. Jakauma ja komponentit
kuvasivat siis kierrosta jonka deadline oli mennyt.

Juurisyy: `next_gw = min(pelaamaton fixture)` on KESKEN oleva kierros niin
kauan kuin sen viimeinen ottelu on pelaamatta (maanantain ottelu 31.8).
Horisontin ensimmainen kierros ei ole otsikkokierros.

Sama vikaluokka jonka `src/models/fpl_gameweek.py` dokumentoi neljasti
(siirtosuunnittelu 22.8, chip-EV 24.8, jakokortti 25.8, /fpl-sivu 25.8) ja
joka loytyi viidennen kerran 30.8 (`build_fpl_cs_fdr`) ja kuudennen kerran
30.8 (`render_captain`). Tama on seitsemas ja kahdeksas.
"""
from __future__ import annotations

from src.models import fpl_gameweek as fplgw


def _meta(deadline, nxt):
    return {"deadline_gameweek": deadline, "next_gameweek": nxt}


# --- valinta ---------------------------------------------------------------

def test_otsikko_on_deadline_kierros_ei_horisontin_ensimmainen():
    """Tasmalleen 31.8:n tilanne: GW2 kesken, GW3:n deadline edessa."""
    assert fplgw.actionable_gameweek(_meta(3, 2)) == 3


def test_negatiivinen_kontrolli_kun_ne_ovat_samat_luku_ei_muutu():
    """Ilman tata edellinen lapaisisi myos jos otsikko olisi aina deadline+0."""
    assert fplgw.actionable_gameweek(_meta(3, 3)) == 3


def test_puuttuva_deadline_palaa_entiseen_kaytokseen():
    """Vanha payload: kaytos bittitarkasti entinen, ei kaatumista."""
    assert fplgw.actionable_gameweek(_meta(None, 2)) == 2
    assert fplgw.actionable_gameweek({"next_gameweek": 2}) == 2


# --- rakentajan kytkenta ---------------------------------------------------
#
# Rakentaja tekee verkkohakuja eika sita voi ajaa testissa; testataan se
# looginen valinta jonka rakentaja tekee, samoilla arvoilla, ja se etta
# lahdekoodi TODELLA kutsuu sita eika lue `next_gw`:ta.

def _lahde(nimi):
    import pathlib
    return (pathlib.Path(__file__).resolve().parents[1] / "scripts" / nimi
            ).read_text(encoding="utf-8")


def test_rakentaja_kayttaa_otsikkokierrosta_jakaumaan_ja_komponentteihin():
    s = _lahde("build_fpl_xp.py")
    assert "headline_gw = fplgw.actionable_gameweek(" in s
    assert "summarize_distribution(dist_samples, headline_gw)" in s
    assert 'player_row["components_gw"] = headline_gw' in s
    assert "if g == headline_gw:" in s


def test_rakentaja_ei_enaa_kayta_next_gwta_otsikkona():
    """Negatiivinen kontrolli: jos jokin naista palaa, vika palaa."""
    s = _lahde("build_fpl_xp.py")
    assert "summarize_distribution(dist_samples, next_gw)" not in s
    assert 'player_row["components_gw"] = next_gw' not in s
    assert "if g == next_gw:" not in s


def test_jakauman_siemen_on_sidottu_otsikkokierrokseen():
    """Siemen `next_gw`:sta antaisi eri jakauman kesken kierroksen."""
    s = _lahde("build_fpl_xp.py")
    assert "int(headline_gw))" in s
    assert "int(next_gw))" not in s


def test_otsikko_horisontin_ulkopuolella_on_varoitus_ei_hiljainen_none():
    """Ilman varaputoamista jokainen xp_dist olisi None ja se nayttaisi
    rikkinaiselta putkelta eika vaaralta kierrokselta."""
    s = _lahde("build_fpl_xp.py")
    assert "if headline_gw not in horizon:" in s
    assert "::warning::otsikkokierros" in s
    assert "headline_gw = next_gw" in s


def test_why_sivu_valitsee_saman_kierroksen():
    s = _lahde("build_fpl_why.py")
    assert "gw = fplgw.actionable_gameweek(meta)" in s
    # `gws[0]` saa esiintya VAIN varaputoamisessa (sisennys 8), ei
    # paavalintana (sisennys 4). Rivipohjainen tarkistus, jotta CRLF ei
    # muuta tulosta (muisti: portti-linuxilla-mittaa-rivinvaihtoja).
    rivit = [r.rstrip() for r in s.splitlines()]
    assert "    gw = gws[0]" not in rivit
    assert "        gw = gws[0]" in rivit


def test_horisontin_alkua_ei_siirretty():
    """Tietoinen rajaus: `gameweeks[]` on 12 kuluttajan sopimus (gradaus,
    kortit, API, SPA) ja sen siirto on oma rivinsa. Jos tama testi kaatuu,
    joku laajensi skooppia vahingossa."""
    s = _lahde("build_fpl_xp.py")
    assert "horizon = [g for g in range(next_gw, next_gw + HORIZON_GW)]" in s
