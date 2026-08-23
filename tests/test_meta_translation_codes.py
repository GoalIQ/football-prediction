"""Käännettävyys: käyttäjälle näkyvä proosa kantaa vakaan tunnisteen.

Tausta (23.8.2026, BACKEND-EN-VUOTAA-ES-PT): `meta.note`, `meta.disclaimer`,
`meta.method`, `meta.caveat` ja `meta.excluded_note` renderöidään RAAKANA
yhdessätoista paikassa mobiilissa ja SPA:ssa, joten es/pt-käyttäjä saa
käännetyn otsikon ja englanninkielisen alaviitteen. Oikea korjaus on
käännökset, mutta ne ovat uutta julkista tekstiä ja kuuluvat julkaisuporttiin.
Välivaihe: backend lähettää proosan rinnalle vakaan tunnisteen, jolloin
klientti kääntää omasta i18n:stään ja proosa jää varakieleksi.

Nämä testit vartioivat kolmea asiaa: tunniste on olemassa, se on tunniste eikä
lause, ja se erottaa variantit toisistaan (yksi koodi kaikille olisi hyödytön).
"""
from __future__ import annotations

import re

import pytest

import scripts.check_copy_style as cs
from src.models import fpl_model_race as mr


CODE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


# ---------------------------------------------------------------------------
# model-race: kolme varianttia, kolme eri koodia
# ---------------------------------------------------------------------------
def test_model_race_ei_alkanut_kantaa_koodin():
    out = mr.build_race(None, None, premium=True)
    meta = out["meta"]
    assert meta["note"] == mr.NOTE_NOT_STARTED
    assert meta["note_code"] == mr.CODE_NOT_STARTED
    assert CODE.match(meta["note_code"])


def test_model_race_koodit_ovat_eri():
    """Yksi koodi kaikille varianteille ei kääntäisi mitään oikein."""
    koodit = {mr.CODE_NOT_STARTED, mr.CODE_NO_ENTRY, mr.CODE_NO_OVERLAP}
    assert len(koodit) == 3
    assert all(CODE.match(k) for k in koodit)


def test_model_race_ei_em_dashia_proosassa():
    """Julkinen API-payload on copy-pintaa siinä missä HTML."""
    for teksti in (mr.NOTE_NOT_STARTED, mr.NOTE_NO_ENTRY):
        assert "—" not in teksti and "–" not in teksti


# ---------------------------------------------------------------------------
# price watch: note-variantit + disclaimer
# ---------------------------------------------------------------------------
def _bootstrap(started: bool) -> dict:
    ev = [{"finished": True}] if started else [{"finished": False}]
    return {"events": ev, "elements": [], "total_players": 0}


@pytest.mark.parametrize("started,n_active,odotettu", [
    (False, 0, "price_watch.note.preseason"),
    (True, 0, "price_watch.note.no_activity"),
    (True, 5, "price_watch.note.none_near_threshold"),
])
def test_price_watch_note_koodit_erottavat_variantit(started, n_active, odotettu):
    from scripts.build_fpl_price_watch import _empty_note

    teksti, koodi = _empty_note(_bootstrap(started), n_active)
    assert koodi == odotettu
    assert CODE.match(koodi)
    assert teksti and teksti[0].isupper()


def test_price_watch_payload_kantaa_molemmat_koodit():
    from scripts.build_fpl_price_watch import build_payload

    payload = build_payload(_bootstrap(False))
    meta = payload["meta"]
    assert CODE.match(meta["disclaimer_code"])
    # tyhjä lista -> note + note_code pareittain
    assert meta.get("note")
    assert meta.get("note_code") == "price_watch.note.preseason"


# ---------------------------------------------------------------------------
# Portti: proosakenttä ilman paria punaa ajon
# ---------------------------------------------------------------------------
def test_portti_on_vihrea_repon_omilla_artefakteilla():
    assert cs.scan_meta_codes() == []


def test_portti_nappaa_puuttuvan_koodin(monkeypatch, tmp_path):
    import json

    d = tmp_path / "data"
    d.mkdir()
    (d / "x.json").write_text(json.dumps(
        {"meta": {"note": "Something a user will read."}}), encoding="utf-8")
    monkeypatch.setattr(cs, "PUBLIC_JSON", ["data/x.json"])
    puutteet = cs.scan_meta_codes(root=tmp_path)
    assert len(puutteet) == 1
    assert "note_code" in puutteet[0][2]


def test_portti_nappaa_koodin_joka_on_lause(monkeypatch, tmp_path):
    """Koodi joka on proosaa ei ole koodi."""
    import json

    d = tmp_path / "data"
    d.mkdir()
    (d / "x.json").write_text(json.dumps(
        {"meta": {"note": "Something.", "note_code": "Something."}}),
        encoding="utf-8")
    monkeypatch.setattr(cs, "PUBLIC_JSON", ["data/x.json"])
    puutteet = cs.scan_meta_codes(root=tmp_path)
    assert len(puutteet) == 1
    assert "ei ole tunniste" in puutteet[0][2]


def test_portti_hyvaksyy_parin(monkeypatch, tmp_path):
    import json

    d = tmp_path / "data"
    d.mkdir()
    (d / "x.json").write_text(json.dumps(
        {"meta": {"note": "Something.", "note_code": "thing.note.v1"}}),
        encoding="utf-8")
    monkeypatch.setattr(cs, "PUBLIC_JSON", ["data/x.json"])
    assert cs.scan_meta_codes(root=tmp_path) == []


def test_tyhja_proosa_ei_vaadi_koodia(monkeypatch, tmp_path):
    """null/tyhjä note on normaali tila (ei mitään sanottavaa)."""
    import json

    d = tmp_path / "data"
    d.mkdir()
    (d / "x.json").write_text(json.dumps({"meta": {"note": None}}),
                              encoding="utf-8")
    monkeypatch.setattr(cs, "PUBLIC_JSON", ["data/x.json"])
    assert cs.scan_meta_codes(root=tmp_path) == []
