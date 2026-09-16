"""UNPROJECTED-SUBJECT (16.9): tyokalu on vastattava myos pelaajasta jolla ei
ole projektiota — seka Replacements etta Compare.

Rowan (luoja) raportoi 15.9: Elanga ei loytynyt Replacements-hausta. Mitattu
tuotannosta samana paivana: FPL merkitsi statuksen `i`, projektio siirsi hanet
`excluded`-listaan ja /api/fantasy/replacements vastasi
404 "Player 454 has no xP projection". Tyokalu siis katosi tasan silla
hetkella kun sen kysymys syntyi.

Vahdittava invariantti on kaksiosainen eika sita voi mitata yhdessa vaiheessa
(CLAUDE.md 6a, mekanismi 3) — sama funktio ajetaan kolmella ulkoisella
tilalla, koska pelaajan saatavuus on juuri se tila joka vaihtuu koodin alla:
  1. kohteella ON projektio       -> xP ja ero-sarake ovat lukuja (entinen)
  2. kohde on `excluded` (injury)  -> vastaus tulee, luvut NULL, ei koskaan 0
  3. kohde on `excluded` (siirtynyt seurasta) -> sama
Ja joka vaiheessa: kohde EI saa ilmestya omaan korvaajalistaansa.

COMPARE (16.9, jatko): sama vika oli Comparessa ja se jai 16.9 aamulla
korjaamatta — `/api/fantasy/compare?players=454,94` vastasi 404 samalla
viestilla. Tyokalupari valehteli siita kenesta voi kysya: loukkaantunut
loytyi Replacementsista mutta ei Comparesta. Molemmat lukevat nyt saman
`resolve_subject_row`-lukijan, joten ne EIVAT VOI eriytya — sita vahtii
`test_molemmat_tyokalut_hyvaksyvat_saman_pelaajan`.
"""
from __future__ import annotations

import copy

import pytest

import src.models.fpl_planner as pl
import src.models.fpl_rate_team as rt
from tests.test_fpl_rate_team import (  # noqa: F401 — _mock_fpl-fixture kayttoon
    FAKE_BOOTSTRAP, FAKE_XP, POOL_BOOT, _mock_fpl,
)

# Kohde jolla on projektio (MID 20, 7.0m) — vaihe 1:n vertailukohta.
PROJECTED_MID = 20
# Uusi MID joka EI ole projektiossa: id 31, sama hinta kuin poolin MID:t,
# joten hintahaarukka loytaa ehdokkaita normaalisti.
OUT_ID = 31
OUT_BOOT = {"id": OUT_ID, "now_cost": 70, "team": 1, "element_type": 3,
            "web_name": "Sidelined", "status": "i", "selected_by_percent": "12.5"}


def _excluded_row(status: str, news: str) -> dict:
    return {"id": OUT_ID, "web_name": "Sidelined", "team_short": "TST",
            "pos": "MID", "price": 7.0, "owned_pct": 12.5, "status": status,
            "news": news, "chance_next": 0, "in_projection": False,
            "excluded_reason": "unavailable",
            # Edelliskauden MITATUT luvut: nama eivat ole ennuste, joten ne
            # kulkevat myos projektoimattomalla rivilla (Compare nayttaa ne).
            "last_season": {"season": "2025/26", "minutes": 2700, "xg": 9.0,
                            "xa": 4.5, "goals": 10, "assists": 5}}


@pytest.fixture
def _with_excluded(monkeypatch):
    """Lisaa pelaajan bootstrappiin mutta EI projektioon — sama muoto kuin
    tuotannon `excluded`-lohko."""
    def _apply(status: str, news: str):
        boot = copy.deepcopy(FAKE_BOOTSTRAP)
        boot["elements"] = list(POOL_BOOT) + [dict(OUT_BOOT, status=status)]
        xp = dict(FAKE_XP)
        xp["excluded"] = [_excluded_row(status, news)]

        def fake_fetch(path):
            if path == "/bootstrap-static/":
                return boot
            raise rt.RateTeamError(404, "Not found on the FPL API.")

        monkeypatch.setattr(rt, "_fetch_fpl", fake_fetch)
        monkeypatch.setattr(rt, "load_xp", lambda: xp)
        rt._FPL_CACHE.clear()
        rt._OPTIMAL_XP_CACHE.clear()
    return _apply


def test_projected_target_still_gets_numbers():
    """Vaihe 1: entinen kayttaytyminen ei muutu."""
    out = pl.replacements(PROJECTED_MID, gws=5)
    assert out["meta"]["target_projected"] is True
    assert out["meta"]["target_note"] is None
    assert isinstance(out["target"]["xp_window"], float)
    assert all(isinstance(r["xp_gap_vs_target"], float) for r in out["players"])


@pytest.mark.parametrize("status,news", [
    ("i", "Unspecified injury - Unknown return date"),
    ("u", "Has joined Al Hilal permanently"),
])
def test_unavailable_target_answers_with_null_not_zero(_with_excluded, status, news):
    """Vaiheet 2-3: vastaus tulee, ja puuttuva projektio nakyy NULLina.

    Nolla olisi ennuste ("Elanga tekee 0 pistetta viidessa kierroksessa"),
    tyhja on tieto siita ettei ennustetta ole. Ero on se mita kayttaja lukee
    ero-sarakkeesta, joten se vahditaan tassa eika UI:ssa.
    """
    _with_excluded(status, news)
    out = pl.replacements(OUT_ID, gws=5)
    assert out["meta"]["target_projected"] is False
    assert out["target"]["projected"] is False
    assert out["target"]["xp_window"] is None
    assert out["target"]["web_name"] == "Sidelined"
    # Hinta luetaan bootstrapista (kymmenyksina), ei `excluded`-rivin
    # miljoonaluvusta: sekaannus tekisi 7.0m:sta 0.7m:n ja haarukasta tyhjan.
    assert out["target"]["price"] == 7.0
    assert out["players"], "korvaajalista ei saa olla tyhja vain siksi etta lahtija on sivussa"
    assert all(r["xp_gap_vs_target"] is None for r in out["players"])
    assert all(isinstance(r["xp_window"], float) for r in out["players"])
    note = out["meta"]["target_note"]
    assert note and "no projection" in note and news[:20] in note


def test_unavailable_target_never_becomes_its_own_replacement(_with_excluded):
    """Kohde ilman projektiota sijoittuisi 0 xP:lla listan hannille — mutta se
    ei kuulu listalle lainkaan, ei edes viimeisena."""
    _with_excluded("i", "Unspecified injury - Unknown return date")
    out = pl.replacements(OUT_ID, gws=5, top_n=10, bracket=3.0)
    assert OUT_ID not in [r["id"] for r in out["players"]]


def test_unknown_player_is_still_404(_with_excluded):
    """Aukko ei saa levita: tuntematon ID on yha 404, ei tyhja kortti."""
    _with_excluded("i", "Unspecified injury - Unknown return date")
    with pytest.raises(rt.RateTeamError) as e:
        pl.replacements(99999)
    assert e.value.status_code == 404


# ---------------------------------------------------------------------------
# COMPARE: sama lukija, sama invariantti
# ---------------------------------------------------------------------------

# Kaksi projektoitua MID:ia fikstuurista (POOL: MID 15-24, paras 15).
MID_A, MID_B = 15, 16


@pytest.mark.parametrize("status,news", [
    ("i", "Unspecified injury - Unknown return date"),
    ("u", "Has joined Al Hilal permanently"),
])
def test_compare_hyvaksyy_pelaajan_ilman_projektiota(_with_excluded, status, news):
    """Vertailu ei saa kaatua 404:aan siksi etta toinen on sivussa — juuri
    silloin kysytaan 'kumpi naista'."""
    _with_excluded(status, news)
    out = pl.compare_players([OUT_ID, MID_A])
    nimet = [r["web_name"] for r in out["players"]]
    assert "Sidelined" in nimet, nimet
    rivi = next(r for r in out["players"] if r["id"] == OUT_ID)
    assert rivi["projected"] is False
    # NULL, ei nolla: nolla tekisi sivussa olevasta automaattisesti
    # huonoimman, ja se olisi mallin vaite eika mittaus.
    assert rivi["xp_horizon_total"] is None
    assert rivi["xp_per_gw"] is None
    assert rivi["status"] == status
    # Mitattu historia kulkee: se on se mita sivussa olevasta voi verrata.
    assert rivi["xg90_prev"] == round(9.0 * 90.0 / 2700, 2)
    assert rivi["prev_season"] == "2025/26"
    # Projektoitu rivi sailyy ennallaan.
    toinen = next(r for r in out["players"] if r["id"] == MID_A)
    assert toinen["projected"] is True
    assert isinstance(toinen["xp_horizon_total"], float)
    assert out["meta"]["unprojected"] == ["Sidelined"]
    assert "unavailable" in (out["meta"]["unprojected_note"] or "")


def test_compare_verdict_ei_ranki_ilman_kahta_projektoitua(_with_excluded):
    """Yksi projektoitu rivi -> ei kantaa. Ilman tata `ranked[1]` olisi
    IndexError tai, pahempaa, sivussa oleva nollalla viimeisena."""
    _with_excluded("i", "Unspecified injury - Unknown return date")
    out = pl.compare_players([OUT_ID, MID_A])
    v = out["verdict"]
    assert v["pick"] is None
    assert v["margin_xp_horizon"] is None
    assert "Sidelined" in v["text"] and "no expected-points number" in v["text"]


def test_compare_verdict_lasketaan_projektoiduista_kun_niita_on_kaksi(_with_excluded):
    """Kolme pelaajaa, joista yksi sivussa: kanta lasketaan kahdesta
    projektoidusta eika sivussa oleva paase mukaan jarjestykseen."""
    _with_excluded("i", "Unspecified injury - Unknown return date")
    out = pl.compare_players([OUT_ID, MID_A, MID_B])
    v = out["verdict"]
    assert v["pick"] is not None
    assert v["pick"]["id"] in (MID_A, MID_B)
    assert v["margin_xp_horizon"] is not None
    assert "Sidelined" not in v["text"]


def test_molemmat_tyokalut_hyvaksyvat_saman_pelaajan(_with_excluded):
    """VAHTI ERIYTYMISTA VASTAAN: 16.9 Replacements korjattiin ja Compare jai
    404:aan, eli sama kysymys sai kaksi eri vastausta riippuen siita minka
    valilehden kayttaja avasi. Molemmat kayttavat nyt samaa lukijaa; tama
    testi kaatuu jos toinen niista lakkaa."""
    _with_excluded("i", "Unspecified injury - Unknown return date")
    r = pl.replacements(OUT_ID, gws=5)
    c = pl.compare_players([OUT_ID, MID_A])
    assert r["target"]["web_name"] == "Sidelined"
    assert any(x["id"] == OUT_ID for x in c["players"])
    # Sama lippu samasta lahteesta molemmilla pinnoilla.
    assert r["target"]["projected"] is False
    assert next(x for x in c["players"] if x["id"] == OUT_ID)["projected"] is False


def test_compare_tuntematon_id_on_yha_404(_with_excluded):
    """Aukko ei saa levita Comparessakaan."""
    _with_excluded("i", "Unspecified injury - Unknown return date")
    with pytest.raises(rt.RateTeamError) as e:
        pl.compare_players([99999, MID_A])
    assert e.value.status_code == 404
