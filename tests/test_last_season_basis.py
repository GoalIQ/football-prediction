# -*- coding: utf-8 -*-
"""Viime kauden lohko nakyy vain kun se kertoo jotain.

VILLEN HAVAINTO 11.9.2026: "Pelaajakortti nayttaa turhaan edelliskauden
tilastoja." Ehto oli `lsTotals.length > 0 || lsPer90.length > 0` eli
"onko riveja", ja lohko nakyi 475 kortilla.

🔴 JONORIVIN EHTO OLISI TEHNYT REGRESSION. Mitattu 12.9 ENNEN koodausta:
ehto `data_basis in (limited_history, no_history) or minutes_basis_flag in
(short_season, new_club)` olisi tiputtanut 475 -> 212 ja
  (a) piilottanut lohkon KAIKILTA 125 excluded-kortilta (99:lla oikeaa
      sisaltoa, eika niille lasketa xP:ta lainkaan), ja
  (b) sailyttanyt ne 29 no_history-rivia jotka ovat kauttaaltaan nollia.
Kolmihaarainen ehto antaa 271.

Ehto asuu palvelimella, koska sama kysymys kysytaan kolmelta pinnalta
kahdessa repossa (pro-SPA:n kortti, SPA:n jakokortti, mobiilin jakokortti).
Tama testi mittaa EHTOA synteettisilla riveilla, ei tamanhetkista dataa -
muuten portti olisi vihrea vain niin kauan kuin tama kausi sattuu
nayttamaan oikealta (CLAUDE.md 6a, mekanismi 3).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.models import fpl_last_season_basis as B  # noqa: E402

ART = ROOT / "data" / "fpl_xp_projections.json"


def rivi(**kw):
    """Synteettinen pelaajarivi. Taysi 25/26-kausi ellei toisin sanota."""
    ls = {"season": "2025/26", "league": "Premier League", "minutes": 2400,
          "starts": 27, "goals": 8, "assists": 5, "xg": 7.4, "xa": 4.1,
          "cs": 6, "points": 140}
    ls.update(kw.pop("last_season", {}) or {})
    row = {"web_name": "Testi", "data_basis": "pl_history", "last_season": ls}
    row.update(kw)
    return row


NOLLAKAUSI = {"minutes": 0, "starts": 0, "goals": 0, "assists": 0,
              "xg": 0.0, "xa": 0.0, "cs": 0, "points": 0}


# ---------------------------------------------------------------------------
# 1. EHTO synteettisilla riveilla
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("row,excluded,odotus,miksi", [
    # Villen havainto: taysi historia, ei lippua -> EI nayteta.
    (rivi(), False, False, "taysi PL-historia ei selita mitaan"),
    # Ohut otos -> lohko selittaa taman kauden arvion.
    (rivi(data_basis="limited_history",
          last_season={"minutes": 1200}), False, True, "ohut otos"),
    # Nollarivi -> EI koskaan, vaikka luokka olisi 'selittava'.
    (rivi(data_basis="no_history", last_season=NOLLAKAUSI), False, False,
     "kauttaaltaan nollia: ei kerro mitaan"),
    (rivi(data_basis="limited_history", last_season=NOLLAKAUSI), False, False,
     "nolla voittaa luokan"),
    # Minuuttiperusteen liput.
    (rivi(minutes_basis_flag="short_season",
          last_season={"minutes": 694}), False, True, "lyhyt kausi"),
    (rivi(minutes_basis_flag="new_club"), False, True, "seuranvaihto"),
    # excluded[]: ei projektiota, viime kausi on ainoa tuotantoluku.
    (rivi(data_basis=None, in_projection=False,
          last_season={"minutes": 2833, "points": 167}), True, True,
     "Watkins-tapaus: ei xP:ta lainkaan"),
    (rivi(data_basis=None, in_projection=False,
          last_season=NOLLAKAUSI), True, False, "excluded + nollarivi"),
    # Ei last_seasonia lainkaan.
    ({"web_name": "X", "data_basis": "pl_history"}, False, False,
     "ei lohkoa"),
    ({"web_name": "X", "data_basis": "pl_history", "last_season": None},
     False, False, "last_season None"),
])
def test_ehto(row, excluded, odotus, miksi):
    assert B.selittaako(row, excluded) is odotus, miksi


@pytest.mark.parametrize("row,excluded,odotus", [
    (rivi(), False, None),
    (rivi(data_basis="limited_history"), False, B.SYY_OHUT_OTOS),
    (rivi(data_basis="no_history"), False, B.SYY_OHUT_OTOS),
    (rivi(minutes_basis_flag="new_club"), False, B.SYY_UUSI_SEURA),
    (rivi(minutes_basis_flag="short_season"), False, B.SYY_LYHYT_KAUSI),
    (rivi(data_basis=None), True, B.SYY_EI_PROJEKTIOTA),
])
def test_syykoodi(row, excluded, odotus):
    assert B.syy(row, excluded) == odotus


def test_syy_on_none_tasan_silloin_kun_lohko_on_piilossa():
    """Lohko ilman perustelua on lohko jolle ei ole lukutapaa; perustelu ilman
    lohkoa on orpo merkkijono. Nama eivat saa erkaantua."""
    tapaukset = [(rivi(), False), (rivi(data_basis="limited_history"), False),
                 (rivi(last_season=NOLLAKAUSI), False),
                 (rivi(data_basis=None), True)]
    for row, exc in tapaukset:
        assert (B.syy(row, exc) is None) is (not B.selittaako(row, exc))


# ---------------------------------------------------------------------------
# 2. VAIHEINVARIANTTI: sama ehto kauden joka vaiheessa
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("vaihe,row", [
    # (a) Kausi ei ole alkanut: kaikilla on viela ohut otos.
    ("ennen kautta", rivi(data_basis="no_history",
                          last_season={"minutes": 1800})),
    # (b) Kesken kauden: luokka on ehtinyt vaihtua limitediksi.
    ("kesken kauden", rivi(data_basis="limited_history",
                           last_season={"minutes": 1800})),
    # (c) Kauden lopussa: luokka on pl_history ja lippu rauennut.
    ("kauden lopussa", rivi(data_basis="pl_history",
                            last_season={"minutes": 1800})),
])
def test_nollarivi_ei_nay_missaan_kauden_vaiheessa(vaihe, row):
    """Portti joka ajetaan vain tassa kauden vaiheessa on vihrea siihen asti
    kun se lakkaa olemasta tosi."""
    row = dict(row)
    row["last_season"] = dict(row["last_season"], **NOLLAKAUSI)
    assert B.selittaako(row) is False, vaihe


def test_taysi_historia_ei_nay_missaan_kauden_vaiheessa():
    for basis in ("pl_history",):
        for lippu in (None,):
            r = rivi(data_basis=basis, minutes_basis_flag=lippu)
            assert B.selittaako(r) is False


# ---------------------------------------------------------------------------
# 3. attach() kirjoittaa kentat ja laskee jakauman
# ---------------------------------------------------------------------------

def test_attach_kirjoittaa_molemmat_kentat_ja_siivoaa_vanhan_syyn():
    nayta = rivi(data_basis="limited_history")
    piilota = rivi()
    piilota["last_season_reason"] = "thin_sample"   # vanhentunut jaanne
    jakauma = B.attach([nayta, piilota], [])
    assert nayta["last_season_show"] is True
    assert nayta["last_season_reason"] == B.SYY_OHUT_OTOS
    assert piilota["last_season_show"] is False
    assert "last_season_reason" not in piilota, \
        "piilotettu rivi ei saa kantaa perustelua"
    assert jakauma == {B.SYY_OHUT_OTOS: 1, "hidden": 1}


def test_attach_lukee_excluded_rivit_omalla_saannollaan():
    exc = rivi(data_basis=None, in_projection=False)
    B.attach([], [exc])
    assert exc["last_season_show"] is True
    assert exc["last_season_reason"] == B.SYY_EI_PROJEKTIOTA


# ---------------------------------------------------------------------------
# 4. ARTEFAKTIDRIFT: tuotantodata ei saa tuottaa nollarivia nakyviin
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not ART.is_file(), reason="artefaktia ei ole")
def test_yksikaan_nakyva_rivi_ei_ole_kauttaaltaan_nolla():
    """Kaataa buildin jos `build_fpl_xp.py` alkaa tuottaa nollapohjaisia
    last_season-lohkoja uudelle luokalle."""
    d = json.loads(ART.read_text(encoding="utf-8"))
    B.attach(d["players"], d.get("excluded") or [])
    huonot = [p["web_name"] for p in d["players"] + (d.get("excluded") or [])
              if p.get("last_season_show")
              and B._kaikki_nollia(p.get("last_season") or {})]
    assert not huonot, huonot


@pytest.mark.skipif(not ART.is_file(), reason="artefaktia ei ole")
def test_kontrolli_tuotantodata_antaa_seka_nakyvia_etta_piilotettuja():
    """Ilman tata edellinen menisi lapi silla etta ehto piilottaisi KAIKEN
    (muisti: kontrolli-lapaisi-tyhjana)."""
    d = json.loads(ART.read_text(encoding="utf-8"))
    jakauma = B.attach(d["players"], d.get("excluded") or [])
    nakyvat = sum(v for k, v in jakauma.items() if k != "hidden")
    assert nakyvat > 50, jakauma
    assert jakauma.get("hidden", 0) > 50, jakauma
    # Kaikki nelja syyta esiintyvat oikeassa datassa.
    for koodi in (B.SYY_EI_PROJEKTIOTA, B.SYY_UUSI_SEURA,
                  B.SYY_LYHYT_KAUSI, B.SYY_OHUT_OTOS):
        assert jakauma.get(koodi, 0) > 0, (koodi, jakauma)


@pytest.mark.skipif(not ART.is_file(), reason="artefaktia ei ole")
def test_excluded_rivit_eivat_katoa():
    """Jonorivin ehto olisi piilottanut lohkon kaikilta excluded-korteilta.
    Tama on se regressio jota ei saa toistaa."""
    d = json.loads(ART.read_text(encoding="utf-8"))
    exc = d.get("excluded") or []
    B.attach(d["players"], exc)
    nakyvat = [p for p in exc if p.get("last_season_show")]
    assert len(nakyvat) > 50, (
        f"vain {len(nakyvat)}/{len(exc)} excluded-riviä nayttaa viime kauden - "
        "naille ei lasketa xP:ta lainkaan, joten se on kortin ainoa tuotantoluku")


# ---------------------------------------------------------------------------
# 5. PINTA-PARITEETTI: molemmat pinnat lukevat kenttaa, eivat omaa ehtoaan
# ---------------------------------------------------------------------------

SPA_KORTTI = ROOT / "web/pro-spa/src/lib/components/PlayerCard.svelte"


def test_spa_kortti_lukee_palvelimen_kenttaa():
    txt = SPA_KORTTI.read_text(encoding="utf-8")
    assert "last_season_show === true" in txt, \
        "SPA:n kortti ei lue palvelimen ehtoa"
    assert "showLastSeason && cells.length > 0" in txt, \
        "SPA:n JAKOKORTTI ei ole saman portin takana - sama vika matkustaisi kuvana ulos"


def test_spa_kortti_ei_paata_ehtoa_itse():
    """MUTAATIO: vanha ehto ('onko riveja') ei saa palata.

    Jos `showLastSeason` maaritellaan uudelleen pelkista pituuksista, tama
    kaatuu."""
    txt = SPA_KORTTI.read_text(encoding="utf-8")
    rivi_ = next((r for r in txt.splitlines()
                  if "const showLastSeason" in r), "")
    assert rivi_, "showLastSeason-maarittelya ei loydy"
    yhdistetty = txt[txt.index("const showLastSeason"):][:400]
    assert "last_season_show" in yhdistetty, yhdistetty[:200]
