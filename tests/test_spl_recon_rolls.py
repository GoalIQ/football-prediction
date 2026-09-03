# -*- coding: utf-8 -*-
"""SPL-tasmaytys rullaa kierroksen mukana — mitattuna JOKA KAUSIVAIHEESSA.

Vika 3.9.2026 (Villen havainto): `/spl`-sivu tarjosi otsikkoa "How our GW1
clean sheet calls went" kun SPL oli kierroksessa 5 ja nelja kierrosta oli
ratkennut. Syy ei ollut unohdettu ajo: `build_spl_recon.py` oli kerta-ajo,
jossa kierros oli moduulivakio `GW = 1`. Se EI VOINUT tuottaa muuta.

CLAUDE.md saanto 6a mekanismi (3): sama funktio ajetaan synteettisilla
kausivaiheilla — ennen ensimmaista kierrosta, kierros kesken, kierros juuri
ratkennut, kaksi ratkennut, snapshot puuttuu — eika siina vaiheessa jossa
kausi sattuu nyt olemaan. Tuotantodatalla ajettu testi olisi vihrea siihen
asti kun se lakkaa olemasta tosi.

Ei verkkoa: feed ja snapshotit rakennetaan tassa, ja `naive_p` annetaan
parametrina jotta vendoroitua CSV:ta ei tarvita.
"""
import pytest

from scripts import build_spl_recon as recon

NAIVE_P = 0.24


def _match(gw, home, away, finished, hs=None, as_=None, kickoff=None):
    return {"gw": gw, "kickoff": kickoff or f"2026-08-{10 + gw:02d}T16:00:00Z",
            "finished": finished, "home": home, "away": away,
            "home_score": hs, "away_score": as_}


def _feed(phase: str) -> list[dict]:
    """Kausi kahdella kierroksella, vaiheet 'ennen' / 'kesken' / 'gw1' / 'gw2'."""
    gw1 = [_match(1, "A", "B", True, 1, 0), _match(1, "C", "D", True, 2, 2)]
    if phase == "ennen":
        return [_match(1, "A", "B", False), _match(1, "C", "D", False)]
    if phase == "gw1":
        return gw1 + [_match(2, "B", "A", False), _match(2, "D", "C", False)]
    if phase == "kesken":
        # GW2:n toinen ottelu on pelattu, toinen ei. Kierros EI ole ratkennut.
        return gw1 + [_match(2, "B", "A", True, 0, 3), _match(2, "D", "C", False)]
    if phase == "gw2":
        return gw1 + [_match(2, "B", "A", True, 0, 3),
                      _match(2, "D", "C", True, 1, 1)]
    raise AssertionError(phase)


def _snap(gw, pairs):
    return {
        "gameweek": gw,
        "provenance": {"commit": f"deadbeef{gw}", "generated_at": "2026-08-01T00:00:00",
                       "kickoff_utc": "2026-08-11T16:00:00Z", "note": "test",
                       "inseason_matches_in_fit": 0},
        "fixtures": [
            {"kickoff": "x", "home": h, "away": a, "home_short": h, "away_short": a,
             "cs_home_pct": ch, "cs_away_pct": ca}
            for h, a, ch, ca in pairs
        ],
    }


def _snapshots(gws):
    rows = {
        1: [("A", "B", 40.0, 20.0), ("C", "D", 30.0, 25.0)],
        2: [("B", "A", 35.0, 22.0), ("D", "C", 28.0, 26.0)],
    }
    return {gw: _snap(gw, rows[gw]) for gw in gws}


# ---------------------------------------------------------------------------
# Vaiheet
# ---------------------------------------------------------------------------

def test_ennen_ensimmaista_kierrosta_ei_julkaista_mitaan():
    with pytest.raises(SystemExit):
        recon.build_all(_snapshots([1]), _feed("ennen"), naive_p=NAIVE_P)


def test_kierros_kesken_ei_nosta_uusinta():
    """Puolikas kierros ei ole track record: sen otos ei ole valittu vaan
    se joka sattui olemaan valmis."""
    out = recon.build_all(_snapshots([1, 2]), _feed("kesken"), naive_p=NAIVE_P)
    assert out["gameweek"] == 1
    assert out["season_to_date"]["gameweeks"] == [1]
    assert out["sides"] == 4


def test_kierros_ratkesi_uusin_seuraa_mukana():
    """SAMA KOODI, eri vaihe: GW2 ratkeaa -> otsikko vaihtuu itsestaan."""
    yksi = recon.build_all(_snapshots([1, 2]), _feed("gw1"), naive_p=NAIVE_P)
    kaksi = recon.build_all(_snapshots([1, 2]), _feed("gw2"), naive_p=NAIVE_P)
    assert yksi["gameweek"] == 1 and kaksi["gameweek"] == 2
    assert kaksi["season_to_date"]["gameweeks"] == [1, 2]
    assert kaksi["season_to_date"]["sides"] == 8
    # Ylatason luvut ovat UUSIMMAN kierroksen, eivat kauden.
    assert kaksi["sides"] == 4
    assert kaksi["fixtures"][0]["home"] == "B"
    # Negatiivinen kontrolli: funktio ei ole vakio kummankaan suhteen.
    assert yksi["brier"] != kaksi["brier"]


def test_snapshot_puuttuu_ratkenneelta_kierrokselta_KAATAA():
    """Hiljainen ohitus oli koko vian mekanismi: ilman tata `latest` jaatyy
    vanhaan kierrokseen eika mikaan huuda."""
    with pytest.raises(SystemExit) as e:
        recon.build_all(_snapshots([1]), _feed("gw2"), naive_p=NAIVE_P)
    assert "[2]" in str(e.value)


def test_uusin_ei_ole_snapshottien_suurin_vaan_ratkennut():
    """Snapshot voi olla kierrokselle jota ei ole pelattu (extract ajetaan
    ennen buildia). Se ei saa nostaa otsikkoa."""
    feed = _feed("gw1")  # GW2 pelaamatta
    out = recon.build_all(_snapshots([1, 2]), feed, naive_p=NAIVE_P)
    assert out["gameweek"] == 1


def test_summat_lasketaan_riveista_joka_vaiheessa():
    for phase, odotetut in (("gw1", [1]), ("kesken", [1]), ("gw2", [1, 2])):
        out = recon.build_all(_snapshots([1, 2]), _feed(phase), naive_p=NAIVE_P)
        s = out["season_to_date"]
        assert s["gameweeks"] == odotetut
        assert sum(b["sides"] for b in out["gameweeks"]) == s["sides"]
        assert sum(b["actual_cs"] for b in out["gameweeks"]) == s["actual_cs"]


def test_pinnatulla_kierroksella_on_perustelu():
    """Poikkeuslista (mekanismi 2): pinnatun rivin on kannettava syy, jotta
    uusi kierros ei paase listalle vahingossa."""
    for gw, (sha, why) in recon.PINNED_SNAPSHOTS.items():
        assert len(sha) == 40, gw
        assert len(why) > 60, f"GW{gw}: pinnaus ilman perustelua"
        assert "kickoff" in why.lower()
