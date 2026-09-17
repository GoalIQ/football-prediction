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
    """Freeze-graderin rivi (score_gw + main): source + provenance."""
    r = {"gw": gw, "points": 63, "points_before_captain": 55,
         "captain_reason": "captain", "captain_points_added": 8,
         "bench_points": 3, "autosubs": [], "fpl_average": 55,
         "graded_at": f"2026-09-0{gw}T15:00:07Z",
         "frozen_at": f"2026-09-0{gw}T07:00:00Z",
         "source": "frozen_squad", "provenance": "entry_verified"}
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
    pudonnut EI muutu entryksi vaan kaataa."""
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
    assert mss.CANONICAL_SOURCE == "entry"
    assert mss.ENTRY_SCORES_PATH.name == "model_squad_gw_scores.json", (
        "julkiset lukijat (model-race, rate-team, recap) lukevat tata nimea")


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


def _aja_freeze(monkeypatch, tmp_path, loki: Path, gws: list[int]):
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
        return _R({"elements": [{"id": i, "stats": {"total_points": 5,
                                                    "minutes": 90}}
                                for i in range(1, 16)]})

    monkeypatch.setattr(m.requests, "get", _get)
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
    doc = mss.load_gw_scores(mss.ENTRY_SCORES_PATH, source=mss.CANONICAL_SOURCE)
    assert mss.series_source(doc) in (None, mss.CANONICAL_SOURCE)
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
    assert mss.CANONICAL_SOURCE == mss.SOURCE_ENTRY
    assert "12.9.2026" in mss.CANONICAL_DECISION
    assert "GW1-GW4" in mss.CANONICAL_DECISION
