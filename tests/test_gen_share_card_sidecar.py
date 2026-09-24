# -*- coding: utf-8 -*-
"""Sidecar-todiste jakokorteille (POSTATTU-KORTTI-EI-OLE-TALLESSA, 24.9.2026).

TAUSTA: `outputs/` on .gitignoressa ja `gen_share_card.py` kirjoittaa aina
saman tiedostonimen yli, joten 9.9 postattua GW4-korttia (M82) ei voi enaa
todistaa — MARKETING_QUEUE viittasi committiin jota ei ole. `write_sidecar`
kirjoittaa PNG:n rinnalle `.json`-todisteen (rivit, artefaktin generated_at
jos tiedossa, sha256) juuri renderoinnin jalkeen, kun tavut ovat viela
tuoreet levylla.

Naitä testejä ei aja canvas-renderin lapi (fontit tulevat goaliq-app-repon
node_modulesista, ei tassa CI-ymparistossa) — `write_sidecar` on riippumaton
PIL:sta ja testataan suoraan mielivaltaisilla tavuilla, sama linja kuin
`test_share_card_contract.py`:n lahdeluku ilman renderointia.
"""
from __future__ import annotations

import hashlib
import importlib
import json

import pytest

gsc = importlib.import_module("scripts.gen_share_card")


def _fake_png(tmp_path, name="card.png", payload=b"not-really-a-png-but-bytes"):
    p = tmp_path / name
    p.write_bytes(payload)
    return p


def test_sidecar_path_swaps_suffix_to_json(tmp_path):
    out = tmp_path / "goaliq_xp_gw6_top10.png"
    assert gsc.sidecar_path(out) == tmp_path / "goaliq_xp_gw6_top10.json"


def test_write_sidecar_records_rows_hash_and_generated_at(tmp_path):
    out = _fake_png(tmp_path, payload=b"hello-card-bytes")
    sc = gsc.write_sidecar(out, card="xp", rows=10, generated_at="2026-09-23T05:00:00Z")
    assert sc == out.with_suffix(".json")
    doc = json.loads(sc.read_text(encoding="utf-8"))
    assert doc["card"] == "xp"
    assert doc["file"] == out.name
    assert doc["rows"] == 10
    assert doc["generated_at"] == "2026-09-23T05:00:00Z"
    assert doc["sha256"] == hashlib.sha256(b"hello-card-bytes").hexdigest()
    # rendered_at on ISO-muotoinen UTC-Z-leima, ei tyhja
    assert doc["rendered_at"].endswith("Z")


def test_write_sidecar_generated_at_may_be_none_but_is_explicit(tmp_path):
    """Osa korttityypeista (cs/defence/stats) ei kanna artefaktin omaa
    aikaleimaa spec-sanakirjassaan. `None` on rehellinen vastaus - kentta ei
    saa hiljaa pudota pois eika vaihtua renderointihetkeen, joka nayttaisi
    tarkemmalta kuin tieto oikeasti on."""
    out = _fake_png(tmp_path)
    sc = gsc.write_sidecar(out, card="defence", rows=20, generated_at=None)
    doc = json.loads(sc.read_text(encoding="utf-8"))
    assert "generated_at" in doc
    assert doc["generated_at"] is None


def test_sidecar_sha256_detects_a_swapped_card(tmp_path):
    """Negatiivinen kontrolli: jos kortti korvataan ajon jalkeen (esim. yliajo
    samalla tiedostonimella), sidecarin sha256 EI enaa tasmaa levylla olevaan
    tiedostoon. Tama on juuri se todiste jota POSTATTU-rivi tarvitsee: ilman
    sita korvautunutta korttia ei voi huomata."""
    out = _fake_png(tmp_path, payload=b"original-card-bytes")
    sc = gsc.write_sidecar(out, card="xp", rows=5, generated_at=None)
    recorded_sha = json.loads(sc.read_text(encoding="utf-8"))["sha256"]

    # Ajo ylikirjoittaa saman tiedostonimen uudella sisallolla eika
    # sidecaria paivitetä (sama tapa kuin manuaalinen kopiointi unohti 9.9).
    out.write_bytes(b"a-different-card-overwrote-the-file")
    live_sha = hashlib.sha256(out.read_bytes()).hexdigest()

    assert recorded_sha != live_sha, (
        "kontrolli lapaisi tyhjana: ylikirjoitettu kortti sai saman sha256:n "
        "kuin alkuperainen, eika testi voi koskaan huomata vaihtoa")


def _write_fake_png(path, payload=b"fake-bytes"):
    path.write_bytes(payload)
    return path


@pytest.mark.parametrize("kind,spec_extra,fake_out_name,expected_rows", [
    ("generic", {"rows": [{}] * 7, "file": "generic.png", "title": "t"}, "generic.png", 7),
    ("gw_outlook", {"kind": "gw_outlook", "fixtures": [{}, {}, {}],
                     "gw": 6, "generated_at": "2026-09-24T00:00:00Z",
                     "file": "outlook.png"}, "outlook.png", 3),
    ("reply", {"kind": "reply_list", "rows": [{"a": 1}, {"a": 2}],
                "as_of": "23 Sep", "title": "t", "file": "reply.png"},
     "reply.png", 2),
])
def test_main_writes_a_sidecar_with_correct_row_count_on_every_path(
        tmp_path, monkeypatch, kind, spec_extra, fake_out_name, expected_rows):
    """Kaikki kolme main()-haaraa (geneerinen render, gw_outlook, reply-kortit)
    laskevat rivimaaran eri spec-avaimesta (rows vs fixtures). Ajetaan main()
    oikeasti mockatuilla renderointifunktioilla (ei PIL:ia, ei fontteja) ja
    luetaan syntynyt sidecar levylta - jos joku haara unohtaisi kutsua
    write_sidecaria tai laskisi vaaran avaimen, testi kaatuu."""
    out_path = tmp_path / fake_out_name
    card_name = "xp" if kind != "gw_outlook" else "gw-outlook"

    def fake_builder(args):
        return dict(spec_extra)

    monkeypatch.setitem(gsc.BUILDERS, card_name, fake_builder)
    monkeypatch.setattr(gsc, "OUT_DIR", tmp_path)

    if kind == "gw_outlook":
        monkeypatch.setattr(gsc, "render_gw_outlook",
                             lambda spec, out: _write_fake_png(out))
    elif kind == "reply":
        monkeypatch.setattr(gsc, "REPLY_RENDERERS", {
            "reply_list": lambda spec, out: _write_fake_png(out)})
    else:
        monkeypatch.setattr(gsc, "render", lambda spec, out: _write_fake_png(out))

    argv = ["gen_share_card.py", card_name]
    if kind == "reply":
        argv += ["--gw", "6"]
    monkeypatch.setattr(gsc.sys, "argv", argv)

    rc = gsc.main()
    assert rc == 0

    sidecar = out_path.with_suffix(".json")
    assert sidecar.exists(), f"{kind}: sidecar ei syntynyt ({sidecar})"
    doc = json.loads(sidecar.read_text(encoding="utf-8"))
    assert doc["rows"] == expected_rows, f"{kind}: vaara rivimaara sidecarissa"
    assert doc["sha256"] == hashlib.sha256(out_path.read_bytes()).hexdigest()
