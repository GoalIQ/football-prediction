# -*- coding: utf-8 -*-
"""KAKSI-GRADERIA-YKSI-TIEDOSTO (17.9.2026): yksi lukija, kaksi tiedostoa,
poikkeuslista perusteluineen.

🔴 MITATTU 12.9. `data/model_squad_gw_scores.json`:iin kirjoitti kaksi
skriptia CI:sta: entry-graderi (`model-squad-grade.yml`, cron 17 */6,
ylikirjoittaa, rivit ilman source-kenttaa) ja freeze-graderi
(`fpl-data-refresh.yml`, cron 0 */3, append-only, `source: frozen_squad`).
Sama GW3 olisi 72 p vs 63 p. Sekaprovenienssi on tarttuva: entry-graderi
ohittaa rivin jolla ei ole `provisional`-kenttaa ("jo lopullinen"), joten
freeze-rivi jaisi sarjaan pysyvasti. Kumpi ehtii ensin ratkesi
cron-jarjestyksesta.

Tama tiedosto mittaa kolme mekanismia:
  A  lukija ei voi palauttaa sekasarjaa (mutaatio kaataa)
  B  molemmat kirjoittajat kulkevat lukijan kautta ENNEN kirjoitusta
     (kutsupaikkaportti: skriptit ajetaan sekasarjaa vasten, ja vanha koodi
     OIKEASTI onnistuisi siina - exit-koodi ei ole todiste mekanismista)
  C  elava tiedosto on yhden provenienssin sarja joka ajossa, ja sen
     legacy-rivit on lueteltu perusteluineen (uusi source-ton rivi kaataa,
     migroitu rivi kaataa vanhentuneena)
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from src.models import model_squad_scores as mss

ROOT = Path(__file__).resolve().parents[1]
ENTRY_GRADER = ROOT / "scripts" / "grade_model_squad.py"
FROZEN_GRADER = ROOT / "scripts" / "grade_model_squad_gw.py"
GRADE_WF = ROOT / ".github" / "workflows" / "model-squad-grade.yml"
REFRESH_WF = ROOT / ".github" / "workflows" / "fpl-data-refresh.yml"

# ---------------------------------------------------------------------------
# POIKKEUSLISTA: elavan entry-sarjan rivit joilla EI ole source-kenttaa.
# Jokainen rivi tarvitsee kirjoitetun syyn. Uusi source-ton rivi (esim. GW5
# vanhalla kirjoittajalla) kaataa testin; migroitu rivi kaataa sen
# vanhentuneena, jolloin rivi poistetaan listalta samassa diffissa.
# ---------------------------------------------------------------------------
_LEGACY_SYY = (
    "Gradattu grade_model_squad.py:lla ennen 17.9.2026, jolloin source-kentta "
    "lisattiin. Rivilla on entry-graderin kentat (captain_id, transfer_cost, "
    "active_chip) eika yhtaan freeze-graderin kenttaa. Migraatio "
    "(stamp_legacy_source) muuttaa tuotantodataa -> Villen GO; siihen asti "
    "lukija hyvaksyy rivin legacy-entryna.")
LEGACY_RIVIT_ILMAN_SOURCEA: dict[int, str] = {
    1: "GW1, graded_at 2026-08-25. " + _LEGACY_SYY,
    2: "GW2 (wildcard), graded_at 2026-09-01. " + _LEGACY_SYY,
    3: "GW3 (3xc), graded_at 2026-09-07. " + _LEGACY_SYY,
    4: ("GW4, graded_at 2026-09-15. Villen paatos 12.9: GW4 entrysta, ei "
        "jaadytetysta rivista (data/model_squad_exceptions/gw4.json). "
        + _LEGACY_SYY),
}


# ---------------------------------------------------------------------------
# Fikstuurit: rivit tasan siina muodossa jossa kumpikin graderi ne kirjoittaa
# ---------------------------------------------------------------------------
def _entry_rivi(gw: int, **kw) -> dict:
    """Entry-graderin rivi ENNEN 17.9 (ei source-kenttaa) = levyn muoto."""
    r = {"gw": gw, "points": 60, "points_net": 60, "bench_points": 4,
         "transfer_cost": 0, "fpl_average": 55, "captain_id": 426,
         "captain_points_added": 6, "active_chip": None, "autosubs": [],
         "provisional": False, "all_fixtures_played": True,
         "graded_at": f"2026-09-0{gw}T15:00:07+00:00"}
    r.update(kw)
    return r


def _frozen_rivi(gw: int, **kw) -> dict:
    """Freeze-graderin rivi (score_gw + main): source + provenance.

    Kentat pidetaan graderin todellisen tulosteen kanssa samoina; ajautumista
    vartioi test_fikstuurit_vastaavat_graderien_todellisia_riveja (xi_ids
    puuttui talta 18.9 asti, ja siksi se puuttui myos sormenjaljesta)."""
    r = {"gw": gw, "points": 63, "points_before_captain": 55,
         "captain_reason": "captain", "captain_id": 1,
         "captain_points_added": 8,
         "bench_points": 3, "autosubs": [], "fpl_average": 55,
         "xi_ids": list(range(1, 12)),
         "graded_at": f"2026-09-0{gw}T15:00:07Z",
         "frozen_at": f"2026-09-0{gw}T07:00:00Z",
         "source": "frozen_squad", "provenance": "entry_verified",
         # 21.9.2026 (Villen paatos "mallin rivi"): hitti ja entryn ero riville.
         "transfer_cost": 0, "transfer_cost_source": "no_transfers",
         "entry_diverged": False,
         "entry_diff": {"common": 15, "missing": [], "extra": [],
                        "xi_only_frozen": [], "xi_only_entry": [],
                        "bench_order_match": True, "captain_match": True,
                        "vice_match": True}}
    r.update(kw)
    return r


def _doc(*rows, meta=None) -> dict:
    return {"meta": dict(meta or {}), "gameweeks": list(rows)}


def _kirjoita(path: Path, doc: dict) -> bytes:
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return path.read_bytes()


# ===========================================================================
# A. LUKIJA EI VOI PALAUTTAA SEKASARJAA
# ===========================================================================
def test_sekasarja_gw3_entry_gw4_frozen_kaataa(tmp_path):
    """🔴 Ydintapaus: tasan se tila jonka cron-jarjestys olisi tuottanut."""
    doc = _doc(_entry_rivi(3), _frozen_rivi(4))
    with pytest.raises(mss.ProvenienssiRistiriita) as ei:
        mss.validate_gw_scores(doc, source=mss.SOURCE_ENTRY)
    assert "GW3=entry" in str(ei.value) and "GW4=frozen_squad" in str(ei.value)
    # Sama tulos kummankin kirjoittajan nakokulmasta - kumpikaan ei saa sarjaa.
    with pytest.raises(mss.ProvenienssiRistiriita):
        mss.validate_gw_scores(doc, source=mss.SOURCE_FROZEN)
    p = tmp_path / "scores.json"
    _kirjoita(p, doc)
    with pytest.raises(mss.ProvenienssiRistiriita):
        mss.load_gw_scores(p, source=mss.SOURCE_ENTRY)


def test_puhdas_entry_sarja_ok_myos_legacy_rivin_kanssa():
    doc = _doc(_entry_rivi(3), _entry_rivi(4, source="entry"))
    assert mss.validate_gw_scores(doc, source="entry") is doc
    assert mss.series_source(doc) == "entry"


def test_puhdas_frozen_sarja_ok():
    doc = _doc(_frozen_rivi(1), _frozen_rivi(3),
               meta={"series_source": "frozen_squad"})
    assert mss.validate_gw_scores(doc, source="frozen_squad") is doc
    assert mss.series_source(doc) == "frozen_squad"


def test_source_ton_entry_muotoinen_rivi_on_legacy_entry():
    """Poikkeuslistan saanto: source puuttuu = entry, koska levyn rivit ovat
    entry-pohjaisia (perustelu moduulissa: LEGACY_SOURCELESS)."""
    assert mss.LEGACY_SOURCELESS == mss.SOURCE_ENTRY
    assert mss.row_source(_entry_rivi(2)) == "entry"


@pytest.mark.parametrize("kentta", mss.FROZEN_FINGERPRINT)
def test_source_ton_rivi_freeze_sormenjaljella_ei_ole_legacy(kentta):
    """Legacy-saanto ei saa olla fail-open: freeze-rivi josta source on
    pudonnut EI muutu entryksi vaan kaataa.

    HUOM: tama testi nimeaa kentat yksi kerrallaan, mutta se EI ole vartijan
    olemassaolon todiste - parametrisointi kulkee saman tuplen yli, ja tyhja
    tuple POISTAA taman testin (skip) sen sijaan etta kaataisi sen. Olemassaolo
    mitataan alempana: test_sormenjalkivartija_on_olemassa_ja_erottaa_graderit
    ja test_freeze_rivi_jolta_source_putosi_ei_lue_entryksi."""
    r = _entry_rivi(4)
    r[kentta] = _frozen_rivi(4)[kentta]
    with pytest.raises(mss.ProvenienssiRistiriita) as ei:
        mss.row_source(r)
    assert kentta in str(ei.value)


def test_meta_joka_valehtelee_sarjasta_kaataa():
    doc = _doc(_entry_rivi(3, source="entry"),
               meta={"series_source": "frozen_squad"})
    with pytest.raises(mss.ProvenienssiRistiriita):
        mss.series_source(doc)


def test_lukija_ei_anna_toisen_provenienssin_sarjaa(tmp_path):
    """Kaksi tiedostoa -rakenteen ydin: vaikka polut osoitettaisiin ristiin,
    kirjoittaja ei saa toisen sarjaa kasiinsa."""
    entry = tmp_path / "entry.json"
    _kirjoita(entry, _doc(_entry_rivi(3)))
    with pytest.raises(mss.ProvenienssiRistiriita) as ei:
        mss.load_gw_scores(entry, source=mss.SOURCE_FROZEN)
    assert "model_squad_frozen_gw_scores.json" in str(ei.value), (
        "virheen on nimettava kirjoittajan oma tiedosto")
    frozen = tmp_path / "frozen.json"
    _kirjoita(frozen, _doc(_frozen_rivi(3)))
    with pytest.raises(mss.ProvenienssiRistiriita):
        mss.load_gw_scores(frozen, source=mss.SOURCE_ENTRY)
    # ...ja oikea pari menee lapi.
    assert mss.load_gw_scores(entry, source="entry")["gameweeks"][0]["gw"] == 3
    assert mss.load_gw_scores(frozen, source="frozen_squad")["gameweeks"][0]["gw"] == 3


def test_tuntematon_source_kaataa():
    with pytest.raises(mss.ProvenienssiRistiriita):
        mss.row_source(_entry_rivi(1, source="render"))
    with pytest.raises(mss.ProvenienssiRistiriita):
        mss.validate_gw_scores(_doc(), source="render")


def test_puuttuva_tiedosto_on_tyhja_sarja_kirjoittajan_provenienssilla(tmp_path):
    doc = mss.load_gw_scores(tmp_path / "ei-ole.json", source="frozen_squad")
    assert doc == {"meta": {"series_source": "frozen_squad"}, "gameweeks": []}


def test_luettu_sarja_kantaa_aina_series_sourcen(tmp_path):
    """Legacy-tiedostossa metaa ei ole; lukija leimaa sen, jotta kirjoittaja
    ei voi kirjoittaa sarjaa joka ei sano provenienssiaan."""
    p = tmp_path / "legacy.json"
    p.write_text(json.dumps({"gameweeks": [_entry_rivi(1)]}), encoding="utf-8")
    doc = mss.load_gw_scores(p, source="entry")
    assert doc["meta"]["series_source"] == "entry"


def test_rikkinainen_tiedosto_kaataa_eika_tyhjenny(tmp_path):
    """Vanha entry-graderi nielaisi ValueErrorin ja jatkoi tyhjalla
    `existing`illa - eli olisi ylikirjoittanut sarjan uusilla riveilla."""
    p = tmp_path / "rikki.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(mss.SarjaVirhe):
        mss.load_gw_scores(p, source="entry")
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(mss.SarjaVirhe):
        mss.load_gw_scores(p, source="entry")


def test_gw_kahdesti_kaataa():
    with pytest.raises(mss.SarjaVirhe):
        mss.series_source(_doc(_entry_rivi(3), _entry_rivi(3)))


def test_stamp_legacy_source_migraatio_on_puhdas():
    alkup = _doc(_entry_rivi(1), _entry_rivi(2, source="entry"))
    jaljennos = json.loads(json.dumps(alkup))
    out = mss.stamp_legacy_source(alkup)
    assert alkup == jaljennos, "migraatio muutti syotetta"
    assert [r["source"] for r in out["gameweeks"]] == ["entry", "entry"]
    assert out["meta"]["series_source"] == "entry"
    # Kaikki muu bitilleen sama.
    for a, b in zip(alkup["gameweeks"], out["gameweeks"]):
        assert {k: v for k, v in b.items() if k != "source"} == \
               {k: v for k, v in a.items() if k != "source"}
    with pytest.raises(mss.ProvenienssiRistiriita):
        mss.stamp_legacy_source(_doc(_entry_rivi(1), _frozen_rivi(2)))


@pytest.mark.parametrize("vaihe, rivit, kaatuu", [
    ("esikausi: tyhja", [], False),
    ("GW1 provisionaalinen", [_entry_rivi(1, provisional=True)], False),
    ("GW1 lopullinen + GW2 provisionaalinen",
     [_entry_rivi(1), _entry_rivi(2, provisional=True, source="entry")], False),
    ("neljä lopullista, legacy + uusi muoto",
     [_entry_rivi(1), _entry_rivi(2), _entry_rivi(3), _entry_rivi(4, source="entry")],
     False),
    ("freeze-rivi tarttunut entry-sarjaan",
     [_entry_rivi(1), _entry_rivi(2), _entry_rivi(3), _frozen_rivi(4)], True),
    ("entry-rivi tarttunut freeze-sarjaan",
     [_frozen_rivi(1), _entry_rivi(2, source="entry")], True),
])
def test_invariantti_joka_vaiheessa(vaihe, rivit, kaatuu):
    """Saanto 6a(3): sama funktio synteettisilla vaiheilla, ei nykyhetkella.
    Ainoa vaihe joka saa kaatua on sekaprovenienssi."""
    doc = _doc(*rivit)
    if kaatuu:
        with pytest.raises(mss.ProvenienssiRistiriita):
            mss.series_source(doc)
    else:
        mss.series_source(doc)  # ei poikkeusta


# ===========================================================================
# B. KUTSUPAIKKAPORTIT: molemmat kirjoittajat kulkevat lukijan kautta
# ===========================================================================
def _lataa(polku: Path, nimi: str):
    spec = importlib.util.spec_from_file_location(nimi, polku)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_kaksi_kirjoittajaa_kaksi_tiedostoa():
    """Rakenne: entry-graderi kirjoittaa entry-sarjaan, freeze-graderi omaan
    tiedostoonsa, ja polut tulevat lukijamoduulista (yksi maarittely)."""
    e = _lataa(ENTRY_GRADER, "grade_model_squad_kk")
    f = _lataa(FROZEN_GRADER, "grade_model_squad_gw_kk")
    assert e.OUT_PATH == mss.ENTRY_SCORES_PATH
    assert f.LOG_PATH == mss.FROZEN_SCORES_PATH
    assert e.OUT_PATH != f.LOG_PATH
    # 21.9.2026: julkinen sarja on jaadytetty rivi, ja pinnat lukevat sen
    # load_public_model_series()-lukijalla (ei tiedostonimella).
    assert mss.CANONICAL_SOURCE == "frozen_squad"
    assert mss.ENTRY_SCORES_PATH.name == "model_squad_gw_scores.json"


def _mock_entry_fpl(monkeypatch, g, gws: list[int]):
    boot = {"events": [{"id": gw, "finished": True, "data_checked": True,
                        "average_entry_score": 55} for gw in gws]}
    fixtures = [{"event": gw, "finished_provisional": True} for gw in gws]
    monkeypatch.setattr(g.fpl_api, "fetch_bootstrap", lambda **kw: boot)
    monkeypatch.setattr(g.fpl_api, "fetch_fixtures", lambda **kw: fixtures)
    monkeypatch.setattr(g.fpl_api, "fetch_entry_history", lambda *a, **kw: {
        "current": [{"event": gw, "points": 60, "points_on_bench": 4,
                     "event_transfers_cost": 0} for gw in gws]})
    monkeypatch.setattr(g.fpl_api, "fetch_entry_picks", lambda *a, **kw: {
        "active_chip": None, "automatic_subs": [],
        "picks": [{"element": 426, "multiplier": 2, "is_captain": True}]})
    monkeypatch.setattr(g.fpl_api, "fetch_event_live", lambda *a, **kw: {
        "elements": [{"id": 426, "stats": {"total_points": 6}}]})


def test_entry_graderi_kieltaytyy_sekasarjasta(tmp_path, monkeypatch):
    """🔴 Kutsupaikkaportti 1. Vanha `build()` luki tiedoston raa'alla
    json.loadsilla, piti molemmat rivit "jo lopullisina" (freeze-rivilla ei
    ole provisional-kenttaa -> None) ja palautti sekasarjan kirjoitettavaksi.
    Uusi kaatuu lukijaan ennen kuin mitaan on rakennettu."""
    g = _lataa(ENTRY_GRADER, "grade_model_squad_kp1")
    out = tmp_path / "scores.json"
    ennen = _kirjoita(out, _doc(_entry_rivi(3), _frozen_rivi(4)))
    monkeypatch.setattr(g, "OUT_PATH", out)
    _mock_entry_fpl(monkeypatch, g, [3, 4])
    with pytest.raises(mss.ProvenienssiRistiriita):
        g.build(verbose=False)
    assert out.read_bytes() == ennen


def test_entry_graderi_ei_rakenna_sarjaa_rikkinaisen_paalle(tmp_path, monkeypatch):
    """🔴 Kutsupaikkaportti 1b, erottelee LUKUKUTSUN (ei vain loppuvalidoinnin):
    vanha `build()` nielaisi ValueErrorin, jatkoi `existing = {}`:lla ja
    palautti onnistuneesti sarjan jossa on vain tuoreet rivit - eli olisi
    ylikirjoittanut koko historian. Lukija kaatuu rikkinaiseen tiedostoon."""
    g = _lataa(ENTRY_GRADER, "grade_model_squad_kp1b")
    out = tmp_path / "scores.json"
    out.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(g, "OUT_PATH", out)
    _mock_entry_fpl(monkeypatch, g, [3])
    with pytest.raises(mss.SarjaVirhe):
        g.build(verbose=False)


def test_entry_graderi_kirjoittaa_sourcen_ja_sailyttaa_legacyn(
        tmp_path, monkeypatch):
    """DoD 1: uusi rivi kantaa source=entry ja meta sanoo sarjan; legacy-rivi
    sailyy BITILLEEN (migraatio on erillinen GO, ei sivuvaikutus)."""
    g = _lataa(ENTRY_GRADER, "grade_model_squad_kp2")
    out = tmp_path / "scores.json"
    legacy = _entry_rivi(3)
    _kirjoita(out, _doc(legacy, meta={"generated_at": "2026-09-07T15:00:07+00:00"}))
    monkeypatch.setattr(g, "OUT_PATH", out)
    _mock_entry_fpl(monkeypatch, g, [3, 4])
    doc = g.build(verbose=False)
    assert doc["meta"]["series_source"] == "entry"
    assert doc["gameweeks"][0] == legacy, "legacy-rivi muuttui"
    assert doc["gameweeks"][1]["gw"] == 4
    assert doc["gameweeks"][1]["source"] == "entry"
    # ...ja tulos lapaisee lukijan: se on se mita main() kirjoittaa.
    mss.validate_gw_scores(doc, source="entry")


def _runko(gw: int) -> dict:
    """Verifioitu freeze (lapaisee require_entry_provenance)."""
    return {
        "meta": {"gw": gw, "squad_source": "entry_picks", "from_gw": gw - 1,
                 "frozen_at": f"2026-09-0{gw}T07:00:00Z",
                 "deadline": f"2026-09-0{gw}T17:30:00Z",
                 "transfers": [], "hits": 0,
                 "entry_verified": {"gw": gw, "entry": 116920,
                                    "at": f"2026-09-0{gw}T18:11:21Z",
                                    "squad_match": True, "captain_match": True,
                                    "common": 15, "match": True}},
        "captain": 1, "vice_captain": 2,
        "xi": [{"id": i, "web_name": f"P{i}",
                "pos": (1 if i == 1 else 2 if i <= 5 else 3 if i <= 9 else 4),
                "price": 50, "club": i} for i in range(1, 12)],
        "bench": [{"id": i, "web_name": f"P{i}",
                   "pos": (1 if i == 12 else 2 if i == 13 else 3),
                   "price": 45, "club": i} for i in range(12, 16)],
    }


def _entry_picks_payload() -> dict:
    """FPL:n `entry/{id}/event/{gw}/picks/` joka vastaa `_runko`a tasan."""
    return {"picks": [{"element": i, "position": i, "is_captain": i == 1,
                       "is_vice_captain": i == 2,
                       "multiplier": 2 if i == 1 else (1 if i <= 11 else 0)}
                      for i in range(1, 16)],
            "entry_history": {"event_transfers_cost": 0},
            "active_chip": None}


def _aja_freeze(monkeypatch, tmp_path, loki: Path, gws: list[int],
                viritys=None):
    """`viritys(m)` ajetaan ennen main()ia (kutsupaikan vakoilu)."""
    m = _lataa(FROZEN_GRADER, "grade_model_squad_gw_kp")
    frozen_dir = tmp_path / "frozen"
    frozen_dir.mkdir(exist_ok=True)
    for gw in gws:
        (frozen_dir / f"gw{gw}.json").write_text(
            json.dumps(_runko(gw), separators=(",", ":")) + "\n",
            encoding="utf-8", newline="\n")
    monkeypatch.setattr(m, "FROZEN_DIR", frozen_dir)
    monkeypatch.setattr(m, "LOG_PATH", loki)

    class _R:
        def __init__(self, payload):
            self._p = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._p

    def _get(url, **kw):
        if "bootstrap-static" in url:
            return _R({"events": [{"id": g, "finished": True,
                                   "data_checked": True,
                                   "average_entry_score": 50} for g in gws]})
        if "/picks/" in url:
            # 21.9: graderi mittaa entryn eron ennen gradausta. Entry = runko.
            return _R(_entry_picks_payload())
        return _R({"elements": [{"id": i, "stats": {"total_points": 5,
                                                    "minutes": 90}}
                                for i in range(1, 16)]})

    monkeypatch.setattr(m.requests, "get", _get)
    if viritys is not None:
        viritys(m)
    return m.main()


def test_freeze_graderi_kieltaytyy_entry_sarjasta(tmp_path, monkeypatch, capsys):
    """🔴 Kutsupaikkaportti 2. Erotteleva fikstuuri: entry-sarja jossa on
    legacy-GW3, ja pending GW4-freeze joka LAPAISEE provenienssiportin.
    Vanha koodi: `done = {3}`, GW4 gradataan ja APPENDATAAN entry-sarjaan,
    rc 0 - eli tasan 12.9 mitattu tarttuva sekaprovenienssi. Uusi: lukija
    kieltaytyy, rc 1, tiedosto koskematon."""
    loki = tmp_path / "entry_series.json"
    ennen = _kirjoita(loki, _doc(_entry_rivi(3)))
    rc = _aja_freeze(monkeypatch, tmp_path, loki, [4])
    out = capsys.readouterr().out
    assert rc == 1, "freeze-graderi kirjoitti entry-sarjaan tai vaikeni"
    assert loki.read_bytes() == ennen, "entry-sarja muuttui"
    assert "::error::" in out


def test_freeze_graderi_kirjoittaa_omaan_sarjaansa(tmp_path, monkeypatch):
    """Negatiivinen kontrolli: oma tiedosto -> gradaa, ja tulos on yhden
    provenienssin freeze-sarja jonka meta sanoo sen."""
    loki = tmp_path / "frozen_series.json"
    rc = _aja_freeze(monkeypatch, tmp_path, loki, [4])
    assert rc == 0 and loki.exists()
    doc = json.loads(loki.read_text(encoding="utf-8"))
    assert doc["meta"]["series_source"] == "frozen_squad"
    assert [r["source"] for r in doc["gameweeks"]] == ["frozen_squad"]
    mss.validate_gw_scores(doc, source="frozen_squad")
    with pytest.raises(mss.ProvenienssiRistiriita):
        mss.load_gw_scores(loki, source="entry")


# ---------------------------------------------------------------------------
# SORMENJALKIVARTIJAN OLEMASSAOLO (adversariaalinen loydos 18.9.2026)
#
# 🔴 MITATTU: `FROZEN_FINGERPRINT = ()` -> tama tiedosto 31 passed, 2 skipped,
# exit 0. Vartija KATOSI eika mikaan punastunut: sita vartioi vain
# test_source_ton_rivi_freeze_sormenjaljella_ei_ole_legacy, joka on
# parametrisoitu saman tuplen yli, ja tyhja parametrisointi on pytestille SKIP.
# Vahinko: freeze-rivi jolta `source` on pudonnut luetaan legacy-entryna, ja
# koska GW1-GW4 ovat LEGACY_RIVIT_ILMAN_SOURCEA-listalla, myos elavan
# tiedoston portti hyvaksyy sen -> julkinen sarja nayttaisi GW4:lle
# freeze-pisteet (mitattu 12.9: GW3 63 p freezesta vs 72 p entrysta), ja
# model-race, gw_recap ja rate-team-kortti lukisivat sen vaieten.
#
# Kaksi EI-PARAMETRISOITUA testia, joiden vertailukohta on graderien
# TODELLINEN tuloste eika `_entry_rivi`/`_frozen_rivi`-fikstuuri (fikstuuri voi
# ajautua koodista erilleen ilman etta mikaan huomauttaa).
# ---------------------------------------------------------------------------
@pytest.fixture
def todellinen_freeze_rivi(tmp_path, monkeypatch) -> dict:
    """Rivi jonka freeze-graderi OIKEASTI kirjoittaa (main() ajettuna)."""
    loki = tmp_path / "sormenjalki_frozen.json"
    assert _aja_freeze(monkeypatch, tmp_path, loki, [4]) == 0
    rivit = json.loads(loki.read_text(encoding="utf-8"))["gameweeks"]
    assert len(rivit) == 1 and rivit[0]["source"] == mss.SOURCE_FROZEN
    return rivit[0]


@pytest.fixture
def todellinen_entry_rivi(tmp_path, monkeypatch) -> dict:
    """Rivi jonka entry-graderi OIKEASTI kirjoittaa (build() ajettuna)."""
    g = _lataa(ENTRY_GRADER, "grade_model_squad_sormenjalki")
    monkeypatch.setattr(g, "OUT_PATH", tmp_path / "sormenjalki_entry.json")
    _mock_entry_fpl(monkeypatch, g, [4])
    rivit = g.build(verbose=False)["gameweeks"]
    assert len(rivit) == 1 and rivit[0]["source"] == mss.SOURCE_ENTRY
    return rivit[0]


def test_freeze_rivi_jolta_source_putosi_ei_lue_entryksi(todellinen_freeze_rivi):
    """🔴 Mekanismi, ei merkkijono. Tasan se rivi jonka freeze-graderi
    kirjoittaa, ilman `source`-kenttaa, ei saa lukeutua legacy-entryksi -
    kumpikaan rivi- eika sarjatasolla. Tyhja (tai vaarille kentille osoittava)
    FROZEN_FINGERPRINT KAATAA taman, ei poista sita."""
    r = {k: v for k, v in todellinen_freeze_rivi.items() if k != "source"}
    with pytest.raises(mss.ProvenienssiRistiriita):
        mss.row_source(r)
    # Sarjataso: legacy-GW vieressa freeze-rivi ei pese itseaan entryksi.
    with pytest.raises(mss.ProvenienssiRistiriita):
        mss.series_source(_doc(_entry_rivi(3), r))
    # ...eika elavan tiedoston poikkeuslista voi hyvaksya sita: sourceless_gws
    # nakisi GW4:n, joka ON listalla, mutta lukija kaatuu ennen sita.
    with pytest.raises(mss.ProvenienssiRistiriita):
        mss.validate_gw_scores(_doc(_entry_rivi(3), r), source=mss.SOURCE_ENTRY)


def test_fikstuurit_vastaavat_graderien_todellisia_riveja(
        todellinen_freeze_rivi, todellinen_entry_rivi):
    """Fikstuuri joka on ajautunut koodista erilleen tekee koko tiedostosta
    teatteria: `_frozen_rivi`:lta puuttui `xi_ids`, joten sormenjalkitestikin
    mittasi vain niita kenttia jotka fikstuuri sattui tuntemaan."""
    assert set(_frozen_rivi(4)) == set(todellinen_freeze_rivi), (
        "_frozen_rivi ei vastaa freeze-graderin tulostetta: "
        f"puuttuu {sorted(set(todellinen_freeze_rivi) - set(_frozen_rivi(4)))}, "
        f"ylimaaraisia {sorted(set(_frozen_rivi(4)) - set(todellinen_freeze_rivi))}")
    # `_entry_rivi` on TARKOITUKSELLA 17.9 edeltava muoto: sama kentta-
    # joukko ilman `source`-kenttaa.
    assert set(_entry_rivi(4)) == set(todellinen_entry_rivi) - {"source"}, (
        "_entry_rivi ei vastaa entry-graderin tulostetta: "
        f"puuttuu {sorted(set(todellinen_entry_rivi) - {'source'} - set(_entry_rivi(4)))}, "
        f"ylimaaraisia {sorted(set(_entry_rivi(4)) - set(todellinen_entry_rivi))}")


def test_sormenjalkivartija_on_olemassa_ja_erottaa_graderit(
        todellinen_freeze_rivi, todellinen_entry_rivi):
    """Vartijan OLEMASSAOLO ja kattavuus, mitattuna kumpaakin graderia vasten.

    Kolme vaatimusta:
      1. tuple ei ole tyhja eika kevennetty (>=4 kenttaa)
      2. jokainen kentta on freeze-graderin todellisella rivilla - vartija ei
         saa vartioida kenttaa jota kukaan ei kirjoita
      3. yksikaan kentta ei ole entry-graderin rivilla - muuten laillinen
         legacy-rivi kaatuisi
    ja neljas joka estaa hiljaisen ajautumisen: tuple on TASAN freeze-rivin
    kentat miinus entry-rivin kentat. Jos kumpaan tahansa graderiin lisataan
    kentta, tama kaatuu ja kirjoittaja joutuu paattamaan onko se sormenjalki.
    """
    ff = set(mss.FROZEN_FINGERPRINT)
    assert len(mss.FROZEN_FINGERPRINT) == len(ff), "tuplessa on duplikaatteja"
    assert len(ff) >= 4, (
        "FROZEN_FINGERPRINT tyhjennettiin tai kevennettiin: sourceless "
        "freeze-rivi lukeutuisi legacy-entryksi ja julkinen sarja voisi "
        "nayttaa freeze-pisteita (12.9: 63 p vs 72 p).")
    vain_freeze = set(todellinen_freeze_rivi) - set(todellinen_entry_rivi)
    assert ff <= set(todellinen_freeze_rivi), (
        f"vartioidut kentat {sorted(ff - set(todellinen_freeze_rivi))} eivat "
        f"ole freeze-graderin rivilla - vartija ei vartioi mitaan.")
    assert not (ff & set(todellinen_entry_rivi)), (
        f"kentat {sorted(ff & set(todellinen_entry_rivi))} ovat MOLEMMILLA "
        f"riveilla - laillinen legacy-entry-rivi kaatuisi.")
    assert ff == vain_freeze, (
        f"sormenjalki ei vastaa graderien todellista eroa. Vain freezessa: "
        f"{sorted(vain_freeze)}; tuplessa: {sorted(ff)}. Lisaa uusi kentta "
        f"tupleen tai perustele diffissa miksi se ei erota graderia.")
    # Ja mekanismi kenttakohtaisesti, ILMAN parametrisointia: laillinen
    # legacy-entry-rivi + yksi sormenjalkikentta = ristiriita, ei legacy.
    for kentta in sorted(ff):
        laillinen = {k: v for k, v in todellinen_entry_rivi.items()
                     if k != "source"}
        assert mss.row_source(laillinen) == mss.SOURCE_ENTRY
        laillinen[kentta] = todellinen_freeze_rivi[kentta]
        with pytest.raises(mss.ProvenienssiRistiriita, match=kentta):
            mss.row_source(laillinen)


# ---------------------------------------------------------------------------
# KIRJOITUSPORTIT MITTAAVAT MEKANISMIA, EI MERKKIJONOA (loydos 18.9.2026)
#
# Lahdeportti (test_kirjoittaja_lukee_ja_validoi_lukijan_kautta_lahteessa) vaatii
# vain etta merkkijono `validate_gw_scores(` esiintyy ennen `.write_text(`.
# Yksi muokkaus - `validate_gw_scores(empty_gw_scores(SOURCE), source=SOURCE)` -
# pitaa merkkijonon paikallaan mutta validoi tyhjan docin, ja kirjoitus menee
# lapi validoimatta. Nama kaksi testia vakoilevat KUTSUPAIKKAA ja vaativat etta
# validoitava olio on tasan se sarja joka palautetaan / kirjoitetaan levylle.
# ---------------------------------------------------------------------------
def test_entry_graderin_paluuvalidointi_validoi_palautetun_sarjan(
        tmp_path, monkeypatch):
    g = _lataa(ENTRY_GRADER, "grade_model_squad_vakooja")
    out = tmp_path / "scores.json"
    _kirjoita(out, _doc(_entry_rivi(3)))
    monkeypatch.setattr(g, "OUT_PATH", out)
    _mock_entry_fpl(monkeypatch, g, [3, 4])
    nahdyt = []
    oikea = mss.validate_gw_scores

    def _vakooja(doc, *, source):
        nahdyt.append((doc, source))
        return oikea(doc, source=source)

    monkeypatch.setattr(g, "validate_gw_scores", _vakooja)
    doc = g.build(verbose=False)
    assert nahdyt, "build() ei validoinut mitaan"
    validoitu, source = nahdyt[-1]
    assert validoitu is doc, (
        "validoitu olio ei ole build()in palauttama sarja - portti validoi "
        "jotain muuta kuin sen mita main() kirjoittaa")
    assert source == mss.SOURCE_ENTRY
    assert [r["gw"] for r in validoitu["gameweeks"]] == [3, 4], (
        "validoitu sarja oli tyhja tai vaillinainen")


def test_freeze_graderin_kirjoitusportti_validoi_levylle_menevan_sarjan(
        tmp_path, monkeypatch):
    loki = tmp_path / "frozen_series.json"
    nahdyt = []
    oikea = mss.validate_gw_scores

    def _viritys(m):
        def _vakooja(doc, *, source):
            # Kopio talteen: portti on ENNEN kirjoitusta, joten myohempi
            # mutaatio ei saa peittaa sita mita portti oikeasti naki.
            nahdyt.append((copy.deepcopy(doc), source))
            return oikea(doc, source=source)
        monkeypatch.setattr(m, "validate_gw_scores", _vakooja)

    rc = _aja_freeze(monkeypatch, tmp_path, loki, [4], viritys=_viritys)
    assert rc == 0 and loki.exists()
    levy = json.loads(loki.read_text(encoding="utf-8"))
    assert nahdyt, "freeze-graderi kirjoitti levylle validoimatta mitaan"
    validoitu, source = nahdyt[-1]
    assert source == mss.SOURCE_FROZEN
    assert validoitu["gameweeks"] == levy["gameweeks"], (
        "validoitu sarja ei ole se joka kirjoitettiin levylle")
    assert validoitu["gameweeks"], "validoitu sarja oli tyhja"


# ---------------------------------------------------------------------------
# JULKISEEN ARTEFAKTIIN KIRJOITETTU VAITE (loydos 18.9.2026)
#
# `_META_DEFAULTS["rules"]` kirjoitetaan freeze-sarjan metaan kun tiedostoa ei
# ole (kausivaihdos tai poistettu tiedosto) ja pushataan julkiseen repoon.
# Siina luki: "a chip round scores lower here than on the entry" - ehdoton
# vaite jota ei vartioinut yksikaan testi. Se on epatosi: chip voi lisata 0 p.
# Portti mittaa suunnan score_gw:lla ja vaatii etta teksti sanoo mitatun
# suunnan, ei lupausta.
# ---------------------------------------------------------------------------
def test_freeze_metan_chip_vaite_on_mitattu_suunta():
    from src.models import fpl_autosub

    runko = _runko(4)
    minuutit = {i: 90 for i in range(1, 16)}

    def _mittaa(kapteenin_pisteet):
        pisteet = {i: (kapteenin_pisteet if i == 1 else 5)
                   for i in range(1, 16)}
        rivi = fpl_autosub.score_gw(runko, pisteet, minuutit)
        perus = sum(pisteet[i] for i in rivi["xi_ids"])
        return {
            "perus": perus,                                # kapteeni x1
            "kapteeni": pisteet[1],
            "freeze": rivi["points"],                      # kapteeni x2
            "entry_3xc": perus + 2 * pisteet[1],           # kapteeni x3
            "entry_bb": perus + pisteet[1] + rivi["bench_points"],
        }

    # Vertailu on mielekas vain jos freeze OIKEASTI kaksinkertaistaa
    # kapteenin (muuten "entry_3xc" ei ole yhden chipin ero vaan kahden).
    for m in (_mittaa(0), _mittaa(8)):
        assert m["freeze"] == m["perus"] + m["kapteeni"], (
            "freeze-rivi ei kaksinkertaista kapteenia; talla mittauksella ei "
            "voi sanoa mitaan chip-erosta")
    nolla = _mittaa(0)
    assert nolla["freeze"] == nolla["entry_3xc"], (
        "3xc nollan tehneelle kapteenille lisaa 2x0 = 0 p, joten chip-kierros "
        "on TASAN sama - 'a chip round scores lower' on epatosi")
    tuottoisa = _mittaa(8)
    assert tuottoisa["freeze"] < tuottoisa["entry_3xc"], (
        "pisteita tehneella kapteenilla 3xc-kierros on aidosti korkeampi")
    for m in (nolla, tuottoisa):
        assert m["freeze"] <= m["entry_3xc"] and m["freeze"] <= m["entry_bb"], (
            "tosi suunta on 'ei koskaan enempaa'")

    mod = _lataa(FROZEN_GRADER, "grade_model_squad_gw_meta")
    saannot = mod._META_DEFAULTS["rules"]
    assert "never scores higher" in saannot, (
        "meta ei sano mitattua suuntaa; artefaktin teksti on julkista tekstia")
    for ylivaite in ("scores lower here than on the entry",
                     "always scores lower",
                     "scores lower than on the entry"):
        assert ylivaite not in saannot, (
            f"ehdoton vaite {ylivaite!r} palasi metaan: chip voi lisata 0 p, "
            f"jolloin kierrokset ovat tasan samat (mitattu yllä).")


def _koodi(p: Path) -> str:
    """Lahde ilman kommentteja (muisti 12.9: merkkijonoportti osui omaan
    perustelukommenttiinsa)."""
    return "\n".join(r.split("#", 1)[0]
                     for r in p.read_text(encoding="utf-8").split("\n"))


@pytest.mark.parametrize("skripti, oma", [
    (ENTRY_GRADER, "source=SOURCE_ENTRY"),
    (FROZEN_GRADER, "source=SOURCE_FROZEN"),
])
def test_kirjoittaja_lukee_ja_validoi_lukijan_kautta_lahteessa(skripti, oma):
    """Lahdeportti kaytostestin pariksi: raaka luku sarjatiedostosta on
    poistettu, ja seka luku etta kirjoitus kulkevat lukijamoduulin kautta."""
    k = _koodi(skripti)
    assert "from src.models.model_squad_scores import" in k
    assert "load_gw_scores(" in k and oma in k
    assert "validate_gw_scores(" in k
    for raaka in ("json.loads(OUT_PATH.read_text", "json.loads(LOG_PATH.read_text",
                  "json.load(open("):
        assert raaka not in k, f"{skripti.name}: raaka luku {raaka!r} palasi"
    assert k.index("validate_gw_scores(") < k.index(".write_text("), (
        "validointi on kirjoituksen JALKEEN - se ei ole portti")


def test_workflow_vartija_kulkee_saman_lukijan_kautta():
    """Runner on se joka kirjoittaa gitiin (Render vain palauttaa). Jos Render
    ajaa vanhempaa koodia kuin repo, runnerin portti on viimeinen."""
    k = _koodi(GRADE_WF)
    assert "from src.models.model_squad_scores import" in k
    assert "validate_gw_scores(d, source=SOURCE_ENTRY)" in k
    assert k.index("validate_gw_scores(") < k.index("json.dump(d,"), (
        "validointi on kirjoituksen jalkeen")


def test_refresh_committaa_freeze_sarjan():
    """Oma tiedosto ilman git add -rivia eläisi vain runnerin levylla ja
    graderi gradaisi samat kierrokset joka ajossa (muisti:
    gitignored-fix-silent-regression)."""
    wf = REFRESH_WF.read_text(encoding="utf-8", errors="replace")
    addit = "\n".join(r for r in wf.splitlines() if "git add" in r)
    assert "data/model_squad_frozen_gw_scores.json" in addit
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "!/data/model_squad_frozen_gw_scores.json" in gi


# ===========================================================================
# C. ELAVA TIEDOSTO: invariantti joka ajossa + poikkeuslista
# ===========================================================================
def test_repon_entry_sarja_on_yhden_provenienssin_ja_legacy_on_lueteltu():
    if not mss.ENTRY_SCORES_PATH.exists():
        pytest.skip("entry-sarjaa ei ole (esikausi)")
    doc = mss.load_gw_scores(mss.ENTRY_SCORES_PATH, source=mss.SOURCE_ENTRY)
    assert mss.series_source(doc) in (None, mss.SOURCE_ENTRY)
    ilman = mss.sourceless_gws(doc)
    uudet = [g for g in ilman if g not in LEGACY_RIVIT_ILMAN_SOURCEA]
    assert not uudet, (
        f"GW{uudet} kirjoitettiin ilman source-kenttaa 17.9 jalkeen - "
        f"kirjoittaja ohitti lukijan. Uusi rivi ei paase poikkeuslistalle "
        f"vahingossa: kirjoita syy LEGACY_RIVIT_ILMAN_SOURCEA-listaan.")
    vanhentuneet = [g for g in LEGACY_RIVIT_ILMAN_SOURCEA if g not in ilman]
    assert not vanhentuneet, (
        f"GW{vanhentuneet} on migroitu (source on) - poista ne "
        f"LEGACY_RIVIT_ILMAN_SOURCEA-listalta, lista ei saa kasvaa hiljaa "
        f"kumpaankaan suuntaan.")
    for gw, syy in LEGACY_RIVIT_ILMAN_SOURCEA.items():
        assert syy.strip(), f"GW{gw} poikkeuslistalla ilman perustelua"


def test_repon_freeze_sarja_on_freeze_sarja_jos_se_on_olemassa():
    if not mss.FROZEN_SCORES_PATH.exists():
        pytest.skip("freeze-sarjaa ei ole viela kirjoitettu")
    doc = mss.load_gw_scores(mss.FROZEN_SCORES_PATH, source=mss.SOURCE_FROZEN)
    assert not mss.sourceless_gws(doc), "freeze-sarjassa ei ole legacy-riveja"


def test_kanoninen_paatos_on_kirjattu():
    """Paatos on vakio jolla on perustelu, ei kommentti."""
    assert mss.CANONICAL_SOURCE == mss.SOURCE_FROZEN
    assert "21.9.2026" in mss.CANONICAL_DECISION
    assert "unscored_gws" in mss.CANONICAL_DECISION


# ===========================================================================
# D. RUNNERIN PORTTI TOIMII ILMAN ASENNETTUJA RIIPPUVUUKSIA
# ===========================================================================
def test_lukijamoduuli_importtautuu_pelkalla_stdlibilla():
    """`model-squad-grade.yml` ajaa validoinnin runnerilla jolla EI ole
    `pip install`ia (vain checkout + `python - <<PY`). Workflow'n kommentti
    vaittaa ettei lukijamoduuli tarvitse asennettuja riippuvuuksia; tama
    mittaa sen. Jos joku lisaa `import requests`in moduuliin tai
    `config.py`:hyn, entry-cron menisi punaiseksi joka 6. tunti ja
    kanoninen sarja lakkaisi paivittymasta - ja tests.yml (jolla
    riippuvuudet ON) pysyisi vihreana.

    `python -S -E` jattaa site-packagesin ja PYTHONPATHin pois, joten vain
    stdlib nakyy. Vartija: jos `requests` silti importtautuu, eristys ei
    toiminut eika testi mittaa mitaan - silloin kaadutaan eri viestilla."""
    import subprocess
    import sys
    koodi = (
        "import sys; sys.path.insert(0, '.')\n"
        "try:\n"
        "    import requests\n"
        "except ImportError:\n"
        "    pass\n"
        "else:\n"
        "    raise SystemExit('ERISTYS EPAONNISTUI: site-packages nakyy')\n"
        "from src.models.model_squad_scores import SOURCE_ENTRY, validate_gw_scores\n"
        "validate_gw_scores({'meta': {}, 'gameweeks': []}, source=SOURCE_ENTRY)\n"
    )
    r = subprocess.run([sys.executable, "-S", "-E", "-c", koodi], cwd=ROOT,
                       capture_output=True, text=True, timeout=60)
    assert "ERISTYS EPAONNISTUI" not in (r.stderr + r.stdout), (
        "python -S -E ei eristanyt site-packagesia; testi ei mittaa mitaan")
    assert r.returncode == 0, (
        "lukijamoduuli ei importtaudu pelkalla stdlibilla - runnerin portti "
        f"model-squad-grade.yml:ssa kaatuisi joka ajolla:\n{r.stderr[-800:]}")
