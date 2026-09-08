# -*- coding: utf-8 -*-
"""Portit UCL-ingestiolle.

🔴 TAUSTA (7.9.2026). Jonorivi `UCL-FANTASY-LAAJENNUS` sanoi 6.9 etta
datan saanti on ratkaistu ja URL on `players_70_en_1.json`, "70 = kausi
2026/27". Mitattu 7.9 ennen ensimmaista koodiriviä:

    id=70  http=200  1126 pelaajaa  ottelupaivat 2024  (= kausi 2024/25)
    id=80  http=200  1178 pelaajaa  ottelupaivat 2025  (= kausi 2025/26)
    id=90  http=200  1162 pelaajaa  ottelupaivat 2026  (= KULUVA)
    id 68-79, 81-85  http=403

Vanha id vastaa siis edelleen 200:lla, ja sen data nayttaa taysin
kelvolliselta - 1 126 pelaajaa, hinnat, omistusprosentit. Ero paljastuu vain
paivamaarista. Kovakoodattu id olisi shipannut kahden kauden takaiset luvut.

Siksi kaksi asiaa on portitettu:
  1. kausi ETSITAAN deadlineista, ja haku hylkaa paattyneen kauden
  2. `totPts` ja `minsPlyd` ovat VIIME kaudelta niin kauan kuin
     `teamPlayed == 0` (mitattu: 0 kaikilla 1 162:lla, mutta minuutteja
     1 560 asti), joten ne kannetaan nimella joka sanoo sen
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from scripts import ingest_ucl as iu

ROOT = Path(__file__).resolve().parents[1]
NYT = dt.datetime(2026, 9, 7, 15, 0, tzinfo=dt.timezone.utc)


def _fx(*deadlinet: str) -> dict:
    """fixtures-vastaus annetuilla deadlineilla (syotteen omassa muodossa)."""
    return {"data": {"value": [
        {"mdId": i + 1, "gameday": 1, "gdIsCurrent": 0, "gdIsLocked": 0,
         "subsAllowed": 2, "deadline": d}
        for i, d in enumerate(deadlinet)]}}


def test_kausihaku_hylkaa_paattyneen_kauden(monkeypatch):
    """🔴 TAMA ON SE VIKA JOKA OLI JONORIVISSA. Paattynyt kausi vastaa
    200:lla ja nayttaa kelvolliselta; vain deadline erottaa ne."""
    vanha = _fx("09/17/24 06:45:00 PM", "10/01/24 06:45:00 PM")
    nykyinen = _fx("09/08/26 06:45:00 PM", "10/13/26 06:45:00 PM")

    def fake(polku: str):
        if polku == "fixtures/fixtures_90_en.json":
            return nykyinen
        if polku == "fixtures/fixtures_70_en.json":
            return vanha
        return None

    monkeypatch.setattr(iu, "_hae", fake)
    kausi, _ = iu.loyda_kausi(NYT)
    assert kausi == 90, "haku valitsi paattyneen kauden"


def test_kausihaku_ei_valitse_isointa_id_ta_vaan_pelattavan(monkeypatch):
    """NEGATIIVINEN KONTROLLI: jos haku valitsisi vain suurimman vastaavan
    id:n, tama menisi lapi vaarin. Perustelu on deadline."""
    def fake(polku: str):
        if polku == "fixtures/fixtures_130_en.json":
            return _fx("09/17/24 06:45:00 PM")      # iso id, MENNYT kausi
        if polku == "fixtures/fixtures_90_en.json":
            return _fx("10/13/26 06:45:00 PM")      # pienempi id, tuleva
        return None

    monkeypatch.setattr(iu, "_hae", fake)
    kausi, _ = iu.loyda_kausi(NYT)
    assert kausi == 90


def test_kausihaku_palauttaa_none_kun_mikaan_ei_ole_kesken(monkeypatch):
    """Fail-closed: mieluummin ei artefaktia kuin artefakti vaarasta
    kaudesta. `build` nostaa taman perusteella."""
    monkeypatch.setattr(iu, "_hae",
                        lambda p: _fx("09/17/24 06:45:00 PM")
                        if p.startswith("fixtures/") else None)
    assert iu.loyda_kausi(NYT) is None


def test_viime_kauden_luvut_eivat_saa_points_nimea():
    """🔴 Mitattu: `teamPlayed == 0` kaikilla 1 162 pelaajalla, mutta
    `totPts` yltaa 121:een ja `minsPlyd` 1 560:een - luvut ovat VIIME
    kaudelta. `points`-niminen kentta olisi vaite tasta kaudesta."""
    doc = {"data": {"value": {"playerList": [{
        "id": 1, "pDName": "X", "tName": "T", "cCode": "T", "tId": 9,
        "skill": 4, "value": 11.0, "selPer": 21.0, "pStatus": "",
        "teamPlayed": 0, "totPts": 121, "minsPlyd": 1560}]}}}
    p = iu.normalisoi_pelaajat(doc, 90)[0]
    assert "points" not in p, "viime kauden luku sai taman kauden nimen"
    assert "minutes" not in p
    assert p["prev_season_points"] == 121
    assert p["prev_season_minutes"] == 1560
    assert p["matchdays_played"] == 0


def test_kun_kierroksia_on_pelattu_luvut_ovat_taman_kauden():
    """KONTROLLI: sama funktio toisessa kauden vaiheessa. Ilman tata
    edellinen testi lapaisisi myos silloin kun `points` ei ilmesty
    KOSKAAN (saanto 6a kohta 3)."""
    doc = {"data": {"value": {"playerList": [{
        "id": 1, "pDName": "X", "tName": "T", "cCode": "T", "tId": 9,
        "skill": 3, "value": 7.5, "selPer": 5.0, "pStatus": "",
        "teamPlayed": 2, "totPts": 14, "minsPlyd": 180}]}}}
    p = iu.normalisoi_pelaajat(doc, 90)[0]
    assert p["points"] == 14 and p["minutes"] == 180
    assert p["prev_season_points"] == 0


def test_positio_ja_status_kaannetaan_luettavaksi():
    doc = {"data": {"value": {"playerList": [
        {"id": i, "pDName": f"P{i}", "tName": "T", "cCode": "T", "tId": 9,
         "skill": s, "value": 5.0, "selPer": 1.0, "pStatus": st,
         "teamPlayed": 0, "totPts": 0, "minsPlyd": 0}
        for i, (s, st) in enumerate([(1, ""), (2, "I"), (3, "NIS"), (4, "S")])]}}}
    rivit = iu.normalisoi_pelaajat(doc, 90)
    assert [r["pos"] for r in rivit] == ["GK", "DEF", "MID", "FWD"]
    assert [r["status"] for r in rivit] == [
        "available", "injured", "not_in_squad", "suspended"]

def _pelaaja(i, status, skill=3):
    return {"id": i, "pDName": f"P{i}", "tName": "T", "cCode": "T", "tId": 9,
            "skill": skill, "value": 5.0, "selPer": 1.0, "pStatus": status,
            "teamPlayed": 0, "totPts": 0, "minsPlyd": 0}


def _doc(pelaajat):
    return {"data": {"value": {"playerList": pelaajat}}}


def test_ottelupaivan_kokoonpanokoodit_eivat_pudota_pelaajaa_nakymasta():
    """🔴 INVARIANTTI MITATAAN OTTELUPAIVAN IKKUNASSA, EI NYKYHETKESSA.

    Mitattu 8.9 (MD1) klo 16:23Z: syotteessa oli koodit P (43) ja B (42),
    yhteensa 7,3 % pelaajista. Samana iltana otteluiden jalkeen molemmat
    olivat POISSA. Koodit elavat siis vain siina ikkunassa jossa UEFA on
    julkaissut kokoonpanot - ja tasan silloin kukaan ei aja tata testia.

    Ilman tata rivia 85 pelajaa olisi saanut tilan "unknown", joka ei ole
    `build_ucl_page`in POISSA- eika TOIMITTAVA-listalla: he olisivat
    kadonneet team-news-sivulta ja nakyneet hinnoissa sanana "Unknown".
    Sama luokka kuin CLAUDE.md 6a mekanismi 3.
    """
    rivit = iu.normalisoi_pelaajat(
        _doc([_pelaaja(1, "P"), _pelaaja(2, "B"), _pelaaja(3, "")]), 90)
    assert [r["status"] for r in rivit] == ["available"] * 3, (
        "kokoonpanokoodi luetaan yha tuntemattomaksi - pelaaja katoaa "
        "team-news-sivulta juuri sina paivana kun han on kiinnostavin")


def test_tuntematon_statuskoodi_kaataa_ingestion_eika_paivita_artefaktia():
    """Tuntemattoman koodin pitaa olla NAKYVA PAATOS, ei hiljainen
    'unknown'-kaatopaikka. Jaassa oleva sivu nakyy `updated`-leimasta ja
    punaisesta workflow'sta; vaara tila ei nay mistaan."""
    with pytest.raises(iu.TuntematonStatus, match="ZZZ"):
        iu.normalisoi_pelaajat(_doc([_pelaaja(9, "ZZZ")]), 90)


def test_yksittainen_eksynyt_koodi_ei_pysayta_paivitysta():
    """NEGATIIVINEN KONTROLLI: kynnys on osuus, ei nolla. Portti joka kaatuu
    yhdesta rivista opetetaan ohittamaan."""
    pelaajat = [_pelaaja(i, "") for i in range(200)] + [_pelaaja(999, "ZZZ")]
    rivit = iu.normalisoi_pelaajat(_doc(pelaajat), 90)
    assert rivit[-1]["status"] == "unknown"
    assert len(rivit) == 201


def test_vajaa_syote_ei_kirjoita_artefaktia(monkeypatch):
    """Osittainen data myrkyttaa kaiken alavirran (muisti:
    osittainen-data-myrkyttaa-cachen)."""
    monkeypatch.setattr(iu, "loyda_kausi",
                        lambda nyt=None: (90, _fx("10/13/26 06:45:00 PM")))
    monkeypatch.setattr(iu, "_hae", lambda p: {"data": {"value": {
        "playerList": [{"id": 1, "pDName": "X", "tName": "T", "cCode": "T",
                        "tId": 9, "skill": 3, "value": 5.0, "selPer": 1.0,
                        "pStatus": "", "teamPlayed": 0, "totPts": 0,
                        "minsPlyd": 0}]}}})
    with pytest.raises(SystemExit, match="vajaa"):
        iu.build(NYT)


# --- artefaktin oma tila ---------------------------------------------------

def _artefakti():
    p = ROOT / "data" / "ucl_fantasy.json"
    if not p.exists():
        pytest.skip("ucl_fantasy.json ei ole viela ajettu")
    return json.loads(p.read_text(encoding="utf-8"))


def test_artefakti_on_kuluvalta_kaudelta():
    """🔴 Tama on se portti joka olisi kaatanut jonorivin premissin.
    Julkaistu artefakti EI saa olla kaudelta jonka kaikki kierrokset ovat
    menneisyydessa."""
    d = _artefakti()
    dls = [dt.datetime.fromisoformat(k["deadline_utc"])
           for k in d["matchdays"] if k.get("deadline_utc")]
    assert dls, "artefaktissa ei ole yhtaan deadlinea"
    nyt = dt.datetime.now(dt.timezone.utc)
    assert max(dls) > nyt, (
        f"artefaktin viimeinen deadline on menneisyydessa ({max(dls)}) - "
        "kausi on ohi tai id on vaara")


def test_artefakti_sanoo_mista_kaudesta_luvut_ovat():
    d = _artefakti()
    perusta = (d["meta"] or {}).get("points_basis") or ""
    assert "last season" in perusta, perusta
    # Ja jos yhtaan kierrosta ei ole pelattu, `points`-kenttaa ei ole.
    if all(p["matchdays_played"] == 0 for p in d["players"]):
        assert not any("points" in p for p in d["players"]), (
            "viime kauden luku kantaa taman kauden nimea")


def test_artefakti_paasee_gittiin_ja_workflow_committaa_sen():
    """🔴 KAKSI VIKAA JOTKA OVAT JO SATTUNEET TASSA REPOSSA, molemmat
    saman artefaktin ympärilla:

    (a) `/data/*` on ignoroitu ja poikkeukset luetellaan kasin. Uusi
        artefakti EI paase repoon ilman rivia, eika mikaan huuda.
    (b) `data/gw_recap.json` oli JAASSA 7 vuorokautta, koska workflow ajoi
        builderin joka ajossa mutta commit-askeleen `git add` -lista ei
        sisaltanyt sen ulostuloa. Askel onnistui joka kerta.

    Tama portti mittaa molemmat.
    """
    import subprocess

    r = subprocess.run(
        ["git", "check-ignore", "-q", "data/ucl_fantasy.json"],
        cwd=ROOT, capture_output=True)
    assert r.returncode != 0, (
        "data/ucl_fantasy.json on gitignoressa - artefakti ei paase repoon. "
        "Lisaa `!/data/ucl_fantasy.json`.")

    wf = (ROOT / ".github" / "workflows" / "ucl-refresh.yml").read_text(
        encoding="utf-8")
    addit = "\n".join(r for r in wf.splitlines() if "git add" in r)
    assert "data/ucl_fantasy.json" in addit, (
        "workflow ajaa ingestion muttei committaa sen ulostuloa - luvut "
        "elavat vain runnerin levylla (sama vika kuin gw_recap 31.8-7.9)")


def test_workflow_julistaa_oikeudet_joita_se_kayttaa():
    """7.9: `fpl-data-refresh` oli punainen kahdesti koska sen
    itsekorjaus dispatchasi hub-deployn ILMAN `actions: write` -oikeutta.
    Uusi workflow ei saa toistaa sita."""
    import re
    wf = (ROOT / ".github" / "workflows" / "ucl-refresh.yml").read_text(
        encoding="utf-8")
    m = re.search(r"^permissions:\s*\n((?:[ \t]+.*\n)+)", wf, re.M)
    assert m, "workflow ei julista permissions-lohkoa"
    lohko = "\n".join(r for r in m.group(1).splitlines()
                      if not r.lstrip().startswith("#"))
    assert re.search(r"\bcontents:\s*write\b", lohko), lohko


def test_jaatynyt_syote_kaataa_ajon(monkeypatch):
    """🔴 JAATYMINEN OLI HILJAINEN. Kun tuoreuskentta tulee syotteesta,
    UEFAn jaatyminen tarkoittaa etta artefakti lakkaa muuttumasta ja
    workflow poistuu NOLLALLA "ei muutoksia" -haaraan. Mikaan ei ole
    punainen (muisti: vihrea-putki-nielee-jaatymisen).
    """
    vanha = (NYT - dt.timedelta(hours=100)).strftime("%m/%d/%Y %I:%M:%S %p")
    monkeypatch.setattr(iu, "loyda_kausi",
                        lambda nyt=None: (90, _fx("10/13/26 06:45:00 PM")))
    monkeypatch.setattr(iu, "_hae", lambda p: {
        "meta": {"timestamp": {"utcTime": vanha}},
        "data": {"value": {"playerList": [
            {"id": i, "pDName": f"P{i}", "tName": "T", "cCode": "T",
             "tId": 9, "skill": 3, "value": 5.0, "selPer": 1.0,
             "pStatus": "", "teamPlayed": 0, "totPts": 0, "minsPlyd": 0}
            for i in range(600)]}}})
    with pytest.raises(SystemExit, match="vanha"):
        iu.build(NYT)


def test_kontrolli_tuore_syote_ei_kaada(monkeypatch):
    """NEGATIIVINEN KONTROLLI: ilman tata edellinen lapaisisi myos jos
    `build` kaatuisi aina."""
    tuore = (NYT - dt.timedelta(hours=1)).strftime("%m/%d/%Y %I:%M:%S %p")
    monkeypatch.setattr(iu, "loyda_kausi",
                        lambda nyt=None: (90, _fx("10/13/26 06:45:00 PM")))
    monkeypatch.setattr(iu, "_hae", lambda p: {} if p.startswith("teams/") else {
        "meta": {"timestamp": {"utcTime": tuore}},
        "data": {"value": {"playerList": [
            {"id": i, "pDName": f"P{i}", "tName": "T", "cCode": "T",
             "tId": 9, "skill": 3, "value": 5.0, "selPer": 1.0,
             "pStatus": "", "teamPlayed": 0, "totPts": 0, "minsPlyd": 0}
            for i in range(600)]}}})
    doc = iu.build(NYT)
    assert doc["meta"]["feed_updated_utc"]


def test_feed_aika_sietaa_kapeaa_valilyontia():
    """UEFA kayttaa U+202F:aa ennen AM/PM:aa. Jos merkki vaihtuu
    tavalliseksi valilyonniksi, jasennys ei saa rikkoutua."""
    for vali in (" ", " ", " "):
        doc = {"meta": {"timestamp": {"utcTime": f"9/7/2026 4:04:12{vali}PM"}}}
        assert iu._feed_aika(doc) == "2026-09-07T16:04:12+00:00", vali
    assert iu._feed_aika({"meta": {}}) is None
