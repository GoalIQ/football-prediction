"""Season race -datan kokoaminen (BTM V2 vaihe c) — puhdas logiikka.

Luvut ovat eri joka kierroksella, jotta väärä kaava (esim. summa erotusten
sijaan tai käänteinen etumerkki) tuottaa eri tuloksen.

Rehellisyyssäännöt joita nämä vartioivat:
  - ennen ensimmäistä gradausta ei arvata mitään
  - puuttuvaa kierrosta EI tulkita nollaksi
  - malli ei pelaa chippejä ja se lukee datassa
"""
from __future__ import annotations

from src.models.fpl_model_race import (
    NOTE_NOT_STARTED,
    build_race,
)


def _log(*rows: dict) -> dict:
    return {"gameweeks": list(rows)}


def _mrow(gw: int, points: int, **extra) -> dict:
    r = {"gw": gw, "points": points, "fpl_average": 50 + gw,
         "captain_id": 100 + gw, "captain_reason": "captain",
         "captain_points_added": gw, "bench_points": gw * 2,
         "autosubs": [{"out": 1, "in": 12, "pos": 1}]}
    r.update(extra)
    return r


def _hist(*pairs: tuple[int, int], bench: int = 3) -> dict:
    return {"current": [{"event": gw, "points": p, "points_on_bench": bench,
                         "event_transfers_cost": 0} for gw, p in pairs]}


# --- tyhjä tila -----------------------------------------------------------

def test_ennen_ensimmaista_gradausta_ei_arvata():
    r = build_race(None, None)
    assert r["meta"]["available"] is False
    assert r["meta"]["note"] == NOTE_NOT_STARTED
    assert r["gameweeks"] == []
    assert r["totals"]["you"] is None


def test_tyhja_loki_kohdellaan_samoin_kuin_puuttuva():
    assert build_race({"gameweeks": []}, None)["meta"]["available"] is False


# --- mallin puoli ilman käyttäjää ----------------------------------------

def test_mallin_rivit_naytetaan_ilman_entrya():
    r = build_race(_log(_mrow(1, 61), _mrow(2, 45)), None)
    assert r["meta"]["available"] is True
    assert r["totals"]["model"] == 106
    assert r["totals"]["you"] is None and r["totals"]["diff"] is None
    assert [g["gw"] for g in r["gameweeks"]] == [1, 2]
    assert all(g["your_points"] is None for g in r["gameweeks"])
    assert "Add your FPL team ID" in r["meta"]["note"]


def test_malli_ei_pelaa_chippeja_lukee_datassa():
    r = build_race(_log(_mrow(1, 61)), None)
    assert r["meta"]["model_plays_chips"] is False


def test_rivit_jarjestetaan_kierroksen_mukaan():
    r = build_race(_log(_mrow(3, 30), _mrow(1, 61), _mrow(2, 45)), None)
    assert [g["gw"] for g in r["gameweeks"]] == [1, 2, 3]


# --- kumulatiivinen ero ---------------------------------------------------

def test_kumulatiivinen_ero_on_juokseva_summa_eika_summien_erotus():
    """GW1 sinä 70 vs malli 61 (+9), GW2 sinä 40 vs 45 (-5) -> 9, 4."""
    r = build_race(_log(_mrow(1, 61), _mrow(2, 45)), _hist((1, 70), (2, 40)))
    diffs = [g["diff"] for g in r["gameweeks"]]
    cums = [g["cumulative_diff"] for g in r["gameweeks"]]
    assert diffs == [9, -5]
    assert cums == [9, 4]
    assert r["totals"]["diff"] == 4
    assert r["totals"]["you"] == 110


def test_etumerkki_on_sina_miinus_malli():
    """Häviötilanne saa näkyä negatiivisena — molemmat suunnat samalla painolla."""
    r = build_race(_log(_mrow(1, 61)), _hist((1, 50)))
    assert r["gameweeks"][0]["diff"] == -11
    assert r["totals"]["diff"] == -11


def test_puuttuvaa_kierrosta_ei_tulkita_nollaksi():
    """Käyttäjä liittyi GW2:ssa: GW1 jää vertailun ulkopuolelle, EI -61."""
    r = build_race(_log(_mrow(1, 61), _mrow(2, 45)), _hist((2, 50)))
    g1, g2 = r["gameweeks"]
    assert g1["your_points"] is None and g1["diff"] is None
    assert g2["diff"] == 5
    assert r["totals"]["diff"] == 5
    assert r["meta"]["compared_gws"] == 1
    assert r["totals"]["model"] == 106      # mallin summa on silti koko kausi


def test_ei_yhteisia_kierroksia_kerrotaan():
    r = build_race(_log(_mrow(1, 61)), _hist((5, 50)))
    assert r["totals"]["diff"] is None
    assert "No overlapping gameweeks" in r["meta"]["note"]


# --- premium-portitus -----------------------------------------------------

def test_free_saa_eron_muttei_erittelya():
    r = build_race(_log(_mrow(1, 61)), _hist((1, 70)), premium=False)
    g = r["gameweeks"][0]
    assert g["diff"] == 9                    # kilpailun tulos on ilmainen
    assert g["cumulative_diff"] == 9
    assert "model_captain_id" not in g       # syy on premium
    assert "model_bench_points" not in g
    assert "model_autosubs" not in g
    assert r["meta"]["masked"] is True


def test_premium_saa_erittelyn_molemmilta_puolilta():
    r = build_race(_log(_mrow(1, 61)), _hist((1, 70)), premium=True)
    g = r["gameweeks"][0]
    assert g["model_captain_id"] == 101
    assert g["model_captain_points"] == 1
    assert g["model_bench_points"] == 2
    assert g["model_autosubs"] == [{"out": 1, "in": 12, "pos": 1}]
    assert g["your_bench_points"] == 3
    assert r["meta"]["masked"] is False


def test_fpl_keskiarvo_kulkee_mukana_molemmissa():
    for prem in (True, False):
        r = build_race(_log(_mrow(1, 61)), None, premium=prem)
        assert r["gameweeks"][0]["fpl_average"] == 51


# --- 7.9: kolme tilaa, ei yksi "provisional" -------------------------------

def test_row_state_erottaa_kesken_olevan_ja_vahvistamattoman():
    """🔴 Kaksi kierrosta samaa vikaa. 20. kierros haaroitti tekstin FPL:n
    `event.finished`ista, ja 21. kierros mittasi ettei se kelpaa: 7.9 GW3:n
    `events[3].finished` oli False samalla kun `fixtures/?event=3` sanoi
    10/10 pelattua. Teksti olisi kertonut lukijalle etta otteluita on
    kesken, kun ne oli kaikki pelattu - eli sama vaarin nimetty mekanismi
    jonka korjaamiseksi tilakone rakennettiin.

    Kentta on nyt `all_fixtures_played`, jonka gradaaja laskee otteluista
    (sama luku jolla se ratkaisee gradattavuuden)."""
    from src.models.fpl_model_race import row_state
    assert row_state({"provisional": False}) == "final"
    assert row_state({"provisional": False, "all_fixtures_played": False}) == "final"
    assert row_state({"provisional": True, "all_fixtures_played": False}) == "in_progress"
    assert row_state({"provisional": True, "all_fixtures_played": True}) == "awaiting_check"
    # Kolmas haara: kentta puuttuu -> emme voi sanoa kummasta on kyse.
    assert row_state({"provisional": True}) == "unknown"
    assert row_state(None) == "unknown"


def test_race_payload_kantaa_tilan_jokaiselle_riville():
    from src.models.fpl_model_race import build_race
    loki = {"gameweeks": [
        {"gw": 1, "points": 41, "fpl_average": 50, "provisional": False,
         "all_fixtures_played": True},
        {"gw": 2, "points": 108, "fpl_average": 81, "provisional": True,
         "all_fixtures_played": True},
        {"gw": 3, "points": 30, "fpl_average": 51, "provisional": True,
         "all_fixtures_played": False},
    ]}
    out = build_race(loki, None)
    tilat = [r["state"] for r in out["gameweeks"]]
    assert tilat == ["final", "awaiting_check", "in_progress"], tilat
    assert out["meta"]["provisional_states"] == {"2": "awaiting_check",
                                                 "3": "in_progress"}
    # Kontrolli: lopullinen kierros EI ole listalla.
    assert "1" not in out["meta"]["provisional_states"]


def test_tila_seuraa_otteluita_ei_fpln_tapahtumalippua():
    """MITATTU TAPAUS 7.9.2026, jossa kaksi lippua ovat eri mielta.

    FPL:n `events[3].finished` oli **False** samalla kun
    `fixtures/?event=3` sanoi **10/10 finished**. `event.finished` kaantyy
    vasta bonusten jalkeen; sen sanoo gradaajan oma docstring.

    Fikstuuri kantaa MOLEMMAT kentat ristiriitaisina, joten testi kaatuu jos
    joku palauttaa ehdon `finished`iin - eika vain siina tapauksessa jossa
    kentat sattuvat olemaan samaa mielta.
    """
    from src.models.fpl_model_race import row_state
    riita = {"gw": 3, "provisional": True,
             "all_fixtures_played": True,   # ottelut: kaikki pelattu
             "finished": False}             # FPL:n tapahtumalippu: ei viela
    assert row_state(riita) == "awaiting_check", (
        "tila luettiin FPL:n tapahtumalipusta, ei otteluista")

    # Ja toisin pain: ottelut kesken, tapahtumalippu jo kaantynyt.
    riita2 = {"gw": 4, "provisional": True,
              "all_fixtures_played": False, "finished": True}
    assert row_state(riita2) == "in_progress"


def test_gradaaja_kirjoittaa_kentan_jota_lukija_lukee():
    """Lukija ja kirjoittaja eri tiedostoissa: jos gradaaja lakkaa
    kirjoittamasta kenttaa, `row_state` palauttaa hiljaa `unknown` kaikelle.
    Portti lukee kirjoittajan lahteen."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1]
           / "scripts" / "grade_model_squad.py").read_text(encoding="utf-8")
    assert '"all_fixtures_played": all_played' in src, (
        "gradaaja ei enaa laske kenttaa otteluista")
    assert '"all_fixtures_played": status["all_fixtures_played"]' in src, (
        "gradaaja ei enaa kirjoita kenttaa riville")


# --- Portin 22. kierros: kaksi eri hetkea ei ole vertailu -------------------

_LOKI_GW3_PROV = {"gameweeks": [
    {"gw": 1, "points": 41, "fpl_average": 50, "provisional": False,
     "all_fixtures_played": True},
    {"gw": 2, "points": 108, "fpl_average": 81, "provisional": False,
     "all_fixtures_played": True},
    # Jaadytetty luku: bonukset eivat olleet viela tulleet kun tama
    # kirjoitettiin.
    {"gw": 3, "points": 58, "fpl_average": 51, "provisional": True,
     "all_fixtures_played": True},
]}


def _hist22(pisteet: dict[int, int]) -> dict:
    return {"current": [{"event": gw, "points": p, "event_transfers_cost": 0,
                         "points_on_bench": 0}
                        for gw, p in sorted(pisteet.items())]}


def test_vanhentunut_mallipuoli_ei_tuota_eroa():
    """🔴 MITATTU TUOTANNOSTA 7.9.2026 12:08 UTC.

        /api/fantasy/model-race?entry=116920 -> GW3 malli 58, sina 72, ero 14
        /entry/116920/history/               -> GW3 points 72

    Sama entry, sama kierros, kaksi eri lukua: mallin puoli jaadytetysta
    artefaktista (15 h 43 min vanha), kayttajan puoli pyyntohetkelta.
    Ilmaispinta sanoi *"olet mallia edella 14 pisteella"* kun tosiasiallinen
    ero oli **0**. Koko ero oli vanhentumista.
    """
    from src.models.fpl_model_race import build_race
    kayttaja = _hist22({1: 41, 2: 108, 3: 72})
    out = build_race(_LOKI_GW3_PROV, kayttaja)   # ei mallin elavaa historiaa

    gw3 = out["gameweeks"][2]
    assert gw3["stale_model_points"] is True
    assert gw3["diff"] is None, "kahden eri hetken ero julkaistiin"
    assert gw3["cumulative_diff"] is None
    # Ja summat kattavat SAMAT kierrokset molemmilla puolilla.
    assert out["totals"]["model"] == 41 + 108
    assert out["totals"]["you"] == 41 + 108
    assert out["totals"]["diff"] == 0
    assert out["totals"]["stale_gws"] == [3]


def test_elava_mallipuoli_palauttaa_vertailun():
    """NEGATIIVINEN KONTROLLI: kun mallin puoli luetaan samalta hetkelta,
    rivi vertaa taas - eli `None` yllä on tilan seuraus eika vakio."""
    from src.models.fpl_model_race import build_race
    kayttaja = _hist22({1: 41, 2: 108, 3: 72})
    malli = _hist22({1: 41, 2: 108, 3: 72})   # sama entry, sama hetki
    out = build_race(_LOKI_GW3_PROV, kayttaja, model_history=malli)

    gw3 = out["gameweeks"][2]
    assert gw3["stale_model_points"] is False
    assert gw3["model_points"] == 72, "elava luku ei syrjayttanyt jaadytettya"
    assert gw3["diff"] == 0, "ero oli kokonaan vanhentumista"
    assert out["totals"]["stale_gws"] == []
    assert out["totals"]["model"] == 41 + 108 + 72


def test_lopullinen_kierros_lukee_yha_lokista():
    """Lopullista kierrosta ei haeta uudelleen: se ei liiku, ja jokainen
    ylimaarainen FPL-kutsu on kuormaa. Vain provisionaalinen rivi tarvitsee
    elavan lukeman."""
    from src.models.fpl_model_race import build_race
    kayttaja = _hist22({1: 41, 2: 108})
    # Mallin "elava" historia valehtelee lopullisista kierroksista; lokin
    # pitaa voittaa, muuten `provisional`-ehto ei tee mitaan.
    malli = _hist22({1: 999, 2: 999})
    loki = {"gameweeks": _LOKI_GW3_PROV["gameweeks"][:2]}
    out = build_race(loki, kayttaja, model_history=malli)
    assert [r["model_points"] for r in out["gameweeks"]] == [41, 108]
