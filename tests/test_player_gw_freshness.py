"""PLAYER-GW-STALE-GUARD: portti tapaukselle "ajoi, ei tehnyt mitään".

Tausta 23.8.2026: `fpl/player-gw.json` oli tuotannossa 25 h vanha ja 31
pelaajassa samalla kun `fpl-data-refresh` ajoi vihreänä joka 3. tunti.
Health-steppi tarkistaa vain `outcome == failure`, eikä skip-haara (exit 0,
ei diffiä) näy missään. Tämä portti mittaa tuotosta, ei exit-koodia.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

import scripts.check_player_gw_freshness as g


NYT = datetime(2026, 8, 23, 12, 0)


@pytest.fixture
def tiedostot(monkeypatch, tmp_path):
    """STATS + OUT väliaikaisina; kutsuja kirjoittaa sisällön."""
    stats = tmp_path / "fpl_player_stats.json"
    out = tmp_path / "player-gw.json"
    monkeypatch.setattr(g, "STATS", stats)
    monkeypatch.setattr(g, "OUT", out)
    return stats, out


def _kirjoita(stats, out, *, basis="2026/27", n_stats=186, n_out=186,
              generated="2026-08-23T11:00:00"):
    stats.write_text(json.dumps({
        "meta": {"basis_season": basis},
        "players": [[i] for i in range(n_stats)],
    }), encoding="utf-8")
    out.write_text(json.dumps({
        "meta": {"basis_season": basis, "generated_at": generated,
                 "n_players": n_out},
        "players": {},
    }), encoding="utf-8")


def test_tuore_ja_taysi_lapaisee(tiedostot):
    stats, out = tiedostot
    _kirjoita(stats, out)
    assert g.tarkista(now=NYT) == []


def test_jaassa_oleva_output_kaataa(tiedostot):
    """Tasan tuotannon tapaus: 25 h vanha, elävä basis."""
    stats, out = tiedostot
    _kirjoita(stats, out, generated="2026-08-22T07:45:51", n_out=31)
    viat = g.tarkista(now=NYT)
    assert viat, "25 h vanhan outputin PITÄÄ kaataa portti"
    assert any("vanha" in v for v in viat)


def test_romahtanut_kate_kaataa_vaikka_aikaleima_on_tuore(tiedostot):
    """Kate on oma vahtinsa: tuore aikaleima ei saa peittää vajaata joukkoa."""
    stats, out = tiedostot
    _kirjoita(stats, out, n_out=31, generated="2026-08-23T11:30:00")
    viat = g.tarkista(now=NYT)
    assert any("kate" in v for v in viat)


def test_jaadytetty_basis_ei_vaadi_tuoreutta(tiedostot):
    """Päättyneellä kaudella SKIP on oikea tulos — portti ei saa huutaa."""
    stats, out = tiedostot
    _kirjoita(stats, out, basis="2025/26", generated="2026-05-01T00:00:00",
              n_out=31)
    assert g.tarkista(now=NYT) == []


def test_puuttuva_output_elavalla_kaudella_kaataa(tiedostot):
    stats, out = tiedostot
    _kirjoita(stats, out)
    out.unlink()
    assert g.tarkista(now=NYT)


def test_rikkinainen_aikaleima_kaataa_eika_kaadu(tiedostot):
    stats, out = tiedostot
    _kirjoita(stats, out, generated="ei-aikaleima")
    viat = g.tarkista(now=NYT)
    assert any("aikaleima" in v for v in viat)


def test_raja_on_12h_eika_esim_36h(tiedostot):
    """Raja mitataan, ei oleteta: 13 h kaatuu, 11 h ei."""
    stats, out = tiedostot
    _kirjoita(stats, out,
              generated=(NYT - timedelta(hours=13)).isoformat(timespec="seconds"))
    assert g.tarkista(now=NYT)
    _kirjoita(stats, out,
              generated=(NYT - timedelta(hours=11)).isoformat(timespec="seconds"))
    assert g.tarkista(now=NYT) == []
