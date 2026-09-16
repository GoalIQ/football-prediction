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
    # 16.9 toinen kierros: teksti nimeaa SYYN (johdettu rivista) eika sano
    # kiinteaa "no expected-points number to rank".
    assert "Sidelined" in v["text"] and "No xP to rank" in v["text"]


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


# ---------------------------------------------------------------------------
# SYY JOHDETAAN RIVISTA, EI KOVAKOODATA
# ---------------------------------------------------------------------------
#
# PORTTI 16.9 (toinen kierros) blokkasi ensimmaisen korjaukseni: kirjoitin
# syyksi kiinteasti "FPL lists him as unavailable". Mitattu tuotannon
# artefaktista samana paivana: 178 `excluded`-rivista 176 on `unavailable`
# mutta KAKSI on `below_min_xp`, ja niilla FPL:n status on `a` (Lewis, MCI,
# tyhja news) ja `d` (Gruev, 25 %). Heista olisimme sanoneet jaettavassa
# kuvassa etta FPL listaa heidat unavailableksi. FPL:n oma bootstrap sanoo
# muuta, ja lukija kumoaa sen yhdella ilmaisella kutsulla.
#
# Fikstuuri on kirjoitettu KORJATUSTA TAPAUKSESTA: molemmat oikeat muodot
# ovat mukana, ja testi vaatii ettei kumpikaan tuota toisen sanamuotoa.

def _excluded(pid: int, nimi: str, status: str, chance, reason: str,
              news: str = "") -> dict:
    return {"id": pid, "web_name": nimi, "team_short": "TST", "pos": "MID",
            "price": 7.0, "owned_pct": 3.0, "status": status, "news": news,
            "chance_next": chance, "in_projection": False,
            "excluded_reason": reason}


SYYT = {
    # (status, chance, excluded_reason) -> mita tekstissa PITAA lukea / EI saa
    "lipun_takia_sivussa": (
        _excluded(OUT_ID, "Flagged", "i", 0, "unavailable",
                  "Unspecified injury - Unknown return date"),
        "FPL lists him as unavailable", "under"),
    "kynnyksen_alla_mutta_pelikelpoinen": (
        _excluded(OUT_ID, "Fit", "a", None, "below_min_xp", ""),
        "under", "unavailable"),
    "kynnyksen_alla_ja_kyseenalainen": (
        _excluded(OUT_ID, "Doubt", "d", 25, "below_min_xp",
                  "Knee injury - 25% chance of playing"),
        "under", "unavailable"),
    "lippu_ilman_reason_kenttaa": (
        _excluded(OUT_ID, "Gone", "u", 0, "unavailable",
                  "Has joined Al Hilal permanently"),
        "FPL lists him as unavailable", "under"),
}


@pytest.fixture
def _with_row(monkeypatch):
    """Kuten `_with_excluded`, mutta rivi annetaan sellaisenaan."""
    def _apply(rivi: dict):
        boot = copy.deepcopy(FAKE_BOOTSTRAP)
        boot["elements"] = list(POOL_BOOT) + [dict(OUT_BOOT,
                                                   status=rivi["status"])]
        xp = dict(FAKE_XP)
        xp["excluded"] = [rivi]
        xp["meta"] = dict(FAKE_XP["meta"], min_xp_total=1.0)

        def fake_fetch(path):
            if path == "/bootstrap-static/":
                return boot
            raise rt.RateTeamError(404, "Not found on the FPL API.")

        monkeypatch.setattr(rt, "_fetch_fpl", fake_fetch)
        monkeypatch.setattr(rt, "load_xp", lambda: xp)
        rt._FPL_CACHE.clear()
        rt._OPTIMAL_XP_CACHE.clear()
    return _apply


@pytest.mark.parametrize("nimi", sorted(SYYT))
def test_syy_vastaa_rivia_kaikilla_pinnoilla(_with_row, nimi):
    rivi, pitaa_lukea, ei_saa_lukea = SYYT[nimi]
    _with_row(rivi)

    verdict = pl.compare_players([OUT_ID, MID_A])["verdict"]["text"]
    note = pl.compare_players([OUT_ID, MID_A])["meta"]["unprojected_note"]
    target = pl.replacements(OUT_ID, gws=5)["meta"]["target_note"]

    for pinta, teksti in (("compare verdict", verdict),
                          ("compare note", note),
                          ("replacements note", target)):
        assert pitaa_lukea in teksti, f"{pinta}: {teksti!r}"
        assert ei_saa_lukea not in teksti, (
            f"{pinta} sanoo enemman kuin lahde: {teksti!r}")


def test_kynnys_luetaan_artefaktista_ei_kovakoodata(_with_row):
    """Jos `build_fpl_xp.MIN_XP_TOTAL` muuttuu, copy seuraa. Kovakoodattu
    luku jaisi vaittamaan vanhaa rajaa eika mikaan kaataisi."""
    rivi, _, _ = SYYT["kynnyksen_alla_mutta_pelikelpoinen"]
    _with_row(rivi)
    t1 = pl.compare_players([OUT_ID, MID_A])["verdict"]["text"]
    assert "1 xP" in t1 and "6-gameweek horizon" in t1, t1

    import src.models.fpl_rate_team as rt2
    vanha = rt2.load_xp()
    muokattu = dict(vanha)
    muokattu["meta"] = dict(vanha["meta"], min_xp_total=2.5)
    rt2.load_xp = lambda: muokattu  # type: ignore[assignment]
    try:
        rt._FPL_CACHE.clear()
        t2 = pl.compare_players([OUT_ID, MID_A])["verdict"]["text"]
    finally:
        rt2.load_xp = vanha and rt2.load_xp  # palautus tapahtuu fixturessa
    assert "2.5 xP" in t2, t2


def test_verdict_ei_viittaa_paikkaan_koska_se_menee_kuvaan(_with_row):
    """Kortilla verdict renderoityy tilastorivien ALLE, joten 'below' osoittaa
    footeriin. Sama merkkijono kahdella pinnalla ei saa kantaa paikkaviitetta."""
    rivi, _, _ = SYYT["lipun_takia_sivussa"]
    _with_row(rivi)
    teksti = pl.compare_players([OUT_ID, MID_A])["verdict"]["text"]
    for sana in ("below", "above", "on the left", "on the right"):
        assert sana not in teksti.lower(), f"paikkaviite {sana!r}: {teksti!r}"


def test_mitattua_hantaa_ei_luvata_ilman_lukua(_with_row):
    """Note lupasi 'last season's measured stats' kaikille, mutta compare
    nollaa ne alle 450 minuutin kaudelta. Lupaus vain kun luku on rivilla."""
    rivi, _, _ = SYYT["kynnyksen_alla_mutta_pelikelpoinen"]
    _with_row(rivi)  # ei last_season-lohkoa -> ei xg90_prev
    note = pl.compare_players([OUT_ID, MID_A])["meta"]["unprojected_note"]
    assert "last season" not in note.lower(), note
    assert "price and ownership" in note, note
