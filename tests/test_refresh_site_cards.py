"""Portti: fpl-data-refreshin korttiaskel (scripts/refresh_site_cards.py).

Nelja lupausta, kukin omalla testillaan (22.9.2026):
  1. Nakyva sisalto ei muuttunut -> ei renderointia eika tiedostomuutoksia.
  2. Sisalto muuttui -> VAIN muuttunut kortti renderoidaan; XI --dry-run.
  3. Exit-koodi tulee MANIFESTISTA, ei renderoijilta: renderoija palauttaa 0
     myos silloin kun Chromea ei loytynyt eika kuvaa syntynyt.
  4. Kaatuminen kirjaa `stale_since`n (portin armonajan alku).
"""
from __future__ import annotations

import pytest

from scripts import publish_cards_to_site as P
from scripts import refresh_site_cards as R

META6 = {"deadline_gameweek": 6, "deadline_utc": "2026-10-10T10:00:00+00:00",
         "next_gameweek": 6}
NYKYISET = {"gameweek-card.webp": "s-uusi", "projected-xi-card.webp": "x-uusi"}


@pytest.fixture
def ymparisto(monkeypatch):
    tila = {"manifesti": {}, "kutsut": [], "merkitty": []}
    monkeypatch.setattr(P, "lue_meta", lambda *a, **k: dict(META6))
    monkeypatch.setattr(P, "lue_manifesti", lambda *a, **k: dict(tila["manifesti"]))
    monkeypatch.setattr(P, "nykyiset_tiivisteet", lambda now=None: dict(NYKYISET))
    monkeypatch.setattr(P, "merkitse_vanhaksi",
                        lambda nimet, now: tila["merkitty"].extend(nimet))

    def renderoija(nimi, paivittaa=True, rc=0, poikkeus=None):
        def main(argv):
            tila["kutsut"].append((nimi, list(argv)))
            if poikkeus:
                raise poikkeus
            if paivittaa:
                tila["manifesti"][nimi] = {"gw": 6, "signature": NYKYISET[nimi]}
            return rc
        return main
    tila["renderoija"] = renderoija

    def aseta(standouts, xi):
        monkeypatch.setitem(R.RENDEROIJAT, "gameweek-card.webp",
                            ("render_standouts_card", lambda: standouts([])))
        monkeypatch.setitem(R.RENDEROIJAT, "projected-xi-card.webp",
                            ("render_projected_xi_card", lambda: xi(["--dry-run"])))
    tila["aseta"] = aseta
    return tila


def _ei_saa(nimi, ymparisto):
    return ymparisto["renderoija"](nimi, poikkeus=AssertionError("ei saa kutsua"))


def test_sama_sisalto_ei_renderoi(ymparisto):
    ymparisto["manifesti"] = {n: {"gw": 6, "signature": NYKYISET[n]} for n in P.NIMET}
    ymparisto["aseta"](_ei_saa("gameweek-card.webp", ymparisto),
                       _ei_saa("projected-xi-card.webp", ymparisto))
    assert R.main([]) == 0
    assert ymparisto["kutsut"] == [] and ymparisto["merkitty"] == []


def test_vain_muuttunut_kortti_renderoidaan_ja_xi_dry_run(ymparisto):
    ymparisto["manifesti"] = {"gameweek-card.webp": {"signature": "s-uusi"},
                              "projected-xi-card.webp": {"signature": "x-vanha"}}
    ymparisto["aseta"](_ei_saa("gameweek-card.webp", ymparisto),
                       ymparisto["renderoija"]("projected-xi-card.webp"))
    assert R.main([]) == 0
    assert ymparisto["kutsut"] == [("projected-xi-card.webp", ["--dry-run"])]


def test_oikea_xi_kutsu_on_dry_run():
    """Kutsulokiin ei kirjoiteta cronista (Villen GO -kirjaus): tarkistetaan
    oikeasta RENDEROIJAT-taulusta, ei fikstuurista."""
    import inspect
    src = inspect.getsource(R)
    assert 'render_projected_xi_card.main(["--dry-run"])' in src


def test_renderoija_exit_0_ilman_kuvaa_on_silti_vika(ymparisto):
    """Chromea ei loytynyt -> renderoija palauttaa 0, manifesti ei muutu."""
    ymparisto["aseta"](ymparisto["renderoija"]("gameweek-card.webp", paivittaa=False),
                       ymparisto["renderoija"]("projected-xi-card.webp", paivittaa=False))
    assert R.main([]) == 1
    assert sorted(ymparisto["merkitty"]) == sorted(P.NIMET)


def test_ensimmaisen_kaatuminen_ei_esta_toista(ymparisto):
    ymparisto["aseta"](
        ymparisto["renderoija"]("gameweek-card.webp",
                                poikkeus=RuntimeError("GW6 standouts differ from log")),
        ymparisto["renderoija"]("projected-xi-card.webp"))
    assert R.main([]) == 1
    assert [k[0] for k in ymparisto["kutsut"]] == ["gameweek-card.webp",
                                                   "projected-xi-card.webp"]
    assert ymparisto["manifesti"]["projected-xi-card.webp"]["signature"] == "x-uusi"
    assert ymparisto["merkitty"] == ["gameweek-card.webp"]
