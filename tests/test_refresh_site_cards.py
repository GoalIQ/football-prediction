"""Portti: fpl-data-refreshin korttiaskel (scripts/refresh_site_cards.py).

Kolme lupausta, kukin omalla testillaan (22.9.2026):
  1. Sama kierros -> ei renderointia eika tiedostomuutoksia (ei churnia).
  2. Kierros vaihtui -> MOLEMMAT kortit samasta datasta.
  3. Exit-koodi tulee MANIFESTISTA, ei renderoijilta: renderoija palauttaa 0
     myos silloin kun Chromea ei loytynyt eika kuvaa syntynyt.
"""
from __future__ import annotations

import pytest

from scripts import publish_cards_to_site as P
from scripts import refresh_site_cards as R

META6 = {"deadline_gameweek": 6, "deadline_utc": "2026-10-10T10:00:00+00:00",
         "next_gameweek": 6}


@pytest.fixture
def ymparisto(monkeypatch):
    tila = {"manifesti": {}, "kutsut": []}
    monkeypatch.setattr(P, "lue_meta", lambda *a, **k: dict(META6))
    monkeypatch.setattr(P, "lue_manifesti", lambda *a, **k: dict(tila["manifesti"]))

    def renderoija(nimi, paivittaa=True, rc=0, poikkeus=None):
        def main(argv):
            tila["kutsut"].append((nimi, list(argv)))
            if poikkeus:
                raise poikkeus
            if paivittaa:
                tila["manifesti"][nimi] = {"gw": 6}
            return rc
        return main
    tila["renderoija"] = renderoija

    def aseta(standouts, xi):
        monkeypatch.setattr(R.render_standouts_card, "main", standouts)
        monkeypatch.setattr(R.render_projected_xi_card, "main", xi)
    tila["aseta"] = aseta
    return tila


def test_sama_kierros_ei_renderoi(ymparisto):
    ymparisto["manifesti"] = {n: {"gw": 6} for n in P.NIMET}
    ymparisto["aseta"](ymparisto["renderoija"]("gameweek-card.webp", poikkeus=AssertionError("ei saa kutsua")),
                       ymparisto["renderoija"]("projected-xi-card.webp", poikkeus=AssertionError("ei saa kutsua")))
    assert R.main([]) == 0
    assert ymparisto["kutsut"] == []


def test_kierros_vaihtui_renderoi_molemmat_ja_xi_dry_run(ymparisto):
    ymparisto["manifesti"] = {"gameweek-card.webp": {"gw": 6},
                              "projected-xi-card.webp": {"gw": 5}}
    ymparisto["aseta"](ymparisto["renderoija"]("gameweek-card.webp"),
                       ymparisto["renderoija"]("projected-xi-card.webp"))
    assert R.main([]) == 0
    assert [k[0] for k in ymparisto["kutsut"]] == ["gameweek-card.webp",
                                                   "projected-xi-card.webp"]
    # Projected XI EI saa kirjoittaa kutsulokiin cronista (Villen GO -kirjaus).
    assert ymparisto["kutsut"][1][1] == ["--dry-run"]


def test_renderoija_exit_0_ilman_kuvaa_on_silti_vika(ymparisto):
    """Chromea ei loytynyt -> renderoija palauttaa 0, manifesti ei muutu."""
    ymparisto["aseta"](ymparisto["renderoija"]("gameweek-card.webp", paivittaa=False),
                       ymparisto["renderoija"]("projected-xi-card.webp", paivittaa=False))
    assert R.main([]) == 1


def test_ensimmaisen_kaatuminen_ei_esta_toista(ymparisto):
    ymparisto["aseta"](
        ymparisto["renderoija"]("gameweek-card.webp",
                                poikkeus=RuntimeError("GW6 standouts differ from log")),
        ymparisto["renderoija"]("projected-xi-card.webp"))
    assert R.main([]) == 1
    assert [k[0] for k in ymparisto["kutsut"]] == ["gameweek-card.webp",
                                                   "projected-xi-card.webp"]
    assert ymparisto["manifesti"]["projected-xi-card.webp"]["gw"] == 6
