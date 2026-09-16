"""UNAVAILABLE-TARGET (16.9): "kuka korvaa X:n" on vastattava silloinkin kun
X:lla ei ole projektiota.

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
            "excluded_reason": "unavailable"}


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
