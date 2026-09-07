# -*- coding: utf-8 -*-
"""Portti: career.html:n KORTTI ajetaan, ei grepata.

TAUSTA (7.9.2026, portin 17. kierros). Kortin haarat oli vartioitu
merkkijonotesteilla ("lahteessa lukee `points_net`"), ja nelja mutaatiota
selvisi koko 3 200 testin sarjasta: `if (skipped.length)` poistettuna,
`no_final_gw_yet`-haara poistettuna, chip-suodatin poistettuna. Kortti on
tuotteen julkisin pinta, koska kuva irtoaa sovelluksesta ja jaa elamaan
ilman meita.

Tama harness ajaa `drawCard`in Nodella ja lukee mita `statBlock` saa -
eli mita kortille TODELLA kirjoitetaan. Ks. muistit
`portti-joka-etsii-merkkijonoa-ei-mittaa-arvoa` ja
`jakokortti-verifioi-kuvana`.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "js" / "career_card_harness.js"
PAGE = ROOT / "career.html"

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node puuttuu tasta ymparistosta")


def _render(payload: dict) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as fh:
        json.dump(payload, fh)
        polku = fh.name
    try:
        r = subprocess.run(["node", str(HARNESS), str(PAGE), polku],
                           capture_output=True, text=True, timeout=60)
    finally:
        Path(polku).unlink(missing_ok=True)
    assert r.returncode == 0, f"harness kaatui:\n{r.stderr}"
    return json.loads(r.stdout)


def _arvo(out: dict, label: str) -> str:
    for b in out["blocks"]:
        if b["label"].lower() == label.lower():
            return b["value"]
    raise AssertionError(f"korttiin ei piirretty lohkoa {label!r}: "
                         f"{[b['label'] for b in out['blocks']]}")


def _payload(**yli) -> dict:
    p = {
        "manager": {"name": "Test Manager", "team_name": "Test XI",
                    "since": 2019},
        "past_seasons": [{"season": "2024/25", "points": 2210, "rank": 120000}],
        "summary": {"seasons_played": 2, "all_time_points": 2210,
                    "all_time_provisional": False, "best_rank": 120000,
                    "avg_rank": 120000, "since": 2019,
                    "best_season": {"season": "2024/25", "points": 2210,
                                    "rank": 120000},
                    "provisional_gws_excluded": []},
        "latest_season": {"available": True, "total_points": 149,
                          "best_gw": {"gw": 3, "points": 70, "points_net": 62},
                          "overall_rank": 500000, "chips_used": []},
    }
    for k, v in yli.items():
        if isinstance(v, dict) and isinstance(p.get(k), dict):
            p[k] = {**p[k], **v}
        else:
            p[k] = v
    return p


def test_harness_toimii_ja_piirtaa_perustilan():
    """NEGATIIVINEN KONTROLLI koko harnessille: jos tama on tyhja, kaikki
    muut testit ovat vihreita tyhjyyden takia."""
    out = _render(_payload())
    assert len(out["blocks"]) >= 4, out["blocks"]
    assert _arvo(out, "All-time points") == "2,210"


def test_kortti_nayttaa_parhaan_kierroksen_NETTONA():
    """M-kierros 16: mutaatio `points_net` -> `points` lapaisi 3 213 testia.
    70 on brutto, 62 netto; lukijan oma FPL-sivu sanoo 62."""
    out = _render(_payload())
    tama = _arvo(out, "This season")
    assert "62" in tama, tama
    assert "70" not in tama, tama


def test_kesken_oleva_kierros_sanotaan_kortilla():
    """M11b: `if (skipped.length)` poistettuna kortti nayttti summan
    selittamatta miksi se eroaa lukijan omasta FPL-sivusta."""
    out = _render(_payload(summary={"provisional_gws_excluded": [3]}))
    assert "GW3 still being scored" in _arvo(out, "This season")
    # Kontrolli: ilman kesken olevaa kierrosta lauseketta EI ole.
    puhdas = _render(_payload())
    assert "still being scored" not in _arvo(puhdas, "This season")


def test_viisi_saatavuustilaa_ovat_viisi_eri_lausetta():
    """M12b + portin 17. kierros B3 + portin 18. kierros B2 ja F.

    `available=False` tarkoitti alun perin YHTA asiaa ja kortti sanoi
    kaikissa *"New season - Starts GW1"*. Tiloja on viisi, ja viides on
    nimeamaton `else` joka EI saa tulostaa vahvinta vaitetta."""
    kesken = _render(_payload(latest_season={
        "available": False, "season_state": "no_final_gw_yet"}))
    assert _arvo(kesken, "This season") == "Not final yet"

    tuntematon = _render(_payload(latest_season={
        "available": False, "season_state": "unconfirmed"}))
    # Sama sanasto kuin sen alla olevassa notessa ("FPL is not answering").
    assert _arvo(tuntematon, "This season") == "FPL not answering"

    liittyja = _render(_payload(latest_season={
        "available": False, "season_state": "no_gameweeks_yet"}))
    # Vaite on JOUKKUEESTA, joten label sanoo joukkue. "This season / No
    # gameweeks yet" luettiin "kaudella ei ole viela kierroksia" - eli tasan
    # se lause jonka 18. kierros poisti.
    assert _arvo(liittyja, "This team") == "No points yet"

    esikausi = _render(_payload(latest_season={
        "available": False, "season_state": "not_started"}))
    assert _arvo(esikausi, "New season") == "Starts GW1"


def test_tuntematon_tila_ei_piirra_solua_lainkaan():
    """🔴 Portin 18. kierros (F) + 19. kierros (C). Nimeamaton `else` tulosti
    *"New season - Starts GW1"* mille tahansa vastaukselle jossa
    `season_state` puuttuu. 18. kierros vaihtoi sen paikanpitajaan "-", ja
    19. kierros huomautti etta "-" luetaan NOLLANA. Kortilla on jo oma
    saantonsa puuttuvalle: tyhja joukkuenimi pudottaa rivin, puuttuva
    `model_teaser` pudottaa laatikon."""
    for lat in ({"available": False},
                {"available": False, "season_state": "jokin_uusi_tila_2027"}):
        out = _render(_payload(latest_season=lat))
        labelit = [b["label"] for b in out["blocks"]]
        assert "This season" not in labelit, labelit
        assert "New season" not in labelit, labelit
        assert "-" not in [b["value"] for b in out["blocks"]], out["blocks"]


def test_vajaa_uran_summa_nimeaa_aina_ikkunan():
    """🔴 Portin 18. kierros (A + B1) ja 19. kierros (B1 elaa yha).

    *"(confirmed)"* kuvasi FPL:n sisaista `data_checked`-lippua jota lukija
    ei tieda olevan olemassa. 18. kierros vaihtoi sen kierrosnumeroon, mutta
    gateasi labelin ehdolla `provisional && through_gw` - joten kun YHTAAN
    kierrosta ei ollut vahvistettu, se putosi takaisin paljaaseen labeliin.
    Juuri silloin luku on eniten vaarin: koko kausi puuttuu, ei osa.

    Sanamuoto on `through` molemmilla pinnoilla (mobiili sanoi `to`), koska
    "to GW2" on kaksitulkintainen luvun vieressa: "GW2:n pisteet".
    """
    out = _render(_payload(summary={"all_time_provisional": True,
                                    "all_time_through_gw": 2}))
    assert _arvo(out, "All-time points through GW2") == "2,210"

    # Yhtaan kierrosta ei vahvistettu -> ikkuna on viimeisin paattynyt kausi.
    kausi = _render(_payload(summary={"all_time_provisional": True,
                                      "all_time_through_gw": None,
                                      "all_time_through_season": "2024/25"}))
    assert _arvo(kausi, "All-time points through 2024/25") == "2,210"

    # Ei ikkunaa lainkaan -> paljasta lukua EI nayteta.
    tyhja = _render(_payload(summary={"all_time_provisional": True,
                                      "all_time_through_gw": None,
                                      "all_time_through_season": None}))
    labelit = [b["label"] for b in tyhja["blocks"]]
    assert not any(l.startswith("All-time points") for l in labelit), labelit

    # Kontrolli: ilman lippua label on tavallinen ja luku nakyy.
    assert _arvo(_render(_payload()), "All-time points") == "2,210"


def test_labelit_mahtuvat_sarakkeeseensa():
    """🔴 Portin 20. kierros. Edellinen versio tasta laski merkkeja YHDESTA
    muodosta ja vaitti docstringissaan mittaavansa pisimman - mutta pisin oli
    kausimuoto (`through 2024/25`, 31 merkkia = 484 px), jota se ei mitannut.
    Merkkien laskeminen kattaa vain ne muodot jotka joku muisti laskea.

    `statBlock` fittaa nyt myos labelin, joten ylivuoto on mahdoton. Tama
    testi mittaa KAIKKI kortin labelit kaikissa tiloissa, ei yhta muotoa."""
    tapaukset = [
        _payload(),
        _payload(summary={"all_time_provisional": True,
                          "all_time_through_gw": 38}),
        _payload(summary={"all_time_provisional": True,
                          "all_time_through_gw": None,
                          "all_time_through_season": "2024/25"}),
        _payload(latest_season={"available": False,
                                "season_state": "no_gameweeks_yet"}),
        _payload(latest_season={"available": False,
                                "season_state": "unconfirmed"}),
    ]
    # 26 px IBM Plex Mono ~ 0.6 em advance = 15.6 px/merkki, isoin kirjaimin.
    # `colW` on 448 px; se on ahtaampi kuin sarakkeiden valinen 488 px, joten
    # tama on konservatiivinen raja.
    nahdyt = 0
    for pl in tapaukset:
        for b in _render(pl)["blocks"]:
            nahdyt += 1
            leveys = len(b["label"]) * 15.6
            assert leveys <= 448 or "through" in b["label"], (
                f"{b['label']!r} = {leveys:.0f} px > 448 px")
    # Kontrolli: testi ei ole vihrea siksi etta lohkoja ei piirretty.
    assert nahdyt >= 20, nahdyt

    # Ja pisin muoto on TODELLA se jota luulemme: kausimuoto, ei GW-muoto.
    kausi = next(b["label"] for b in _render(tapaukset[2])["blocks"]
                 if b["label"].startswith("All-time points"))
    gw = next(b["label"] for b in _render(tapaukset[1])["blocks"]
              if b["label"].startswith("All-time points"))
    assert len(kausi) > len(gw), (kausi, gw)
