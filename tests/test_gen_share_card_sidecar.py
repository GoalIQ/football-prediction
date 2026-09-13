# -*- coding: utf-8 -*-
"""POSTATTU-KORTTI-EI-OLE-TALLESSA (12.9.2026).

`outputs/` on .gitignoressa ja jokainen `gen_share_card.py`-ajo kirjoittaa
saman tiedostonimen yli, joten postattua korttia ei voinut jalkikateen
todistaa: 9.9 postattu GW4-kortti (M82) ei ollut enaa olemassa missaan, ja
MARKETING_QUEUE viittasi commitiin jossa sita ei koskaan ollut.

Nama testit eivat aja canvas-renderia (sama rajoite kuin
`test_share_card_contract.py`:ssa: ei pytestista) vaan testaavat
sidecar-mekanismia suoraan mielivaltaisen "PNG"-tiedoston paalla — sidecarin
sisalto ei riipu siita miten tavut syntyivat, vain siita mita levylla on.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.gen_share_card as gsc


def _write_fake_png(path: Path, content: bytes = b"fake-png-bytes") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


# ---------------------------------------------------------------------------
# write_sidecar: rivit + generated_at + sha256 levylla PNG:n vieressa
# ---------------------------------------------------------------------------

def test_write_sidecar_records_rows_generated_at_and_matching_sha256(tmp_path):
    png = _write_fake_png(tmp_path / "goaliq_value.png", b"hello-card")
    spec = {"rows": [{"rank": 1, "name": "Haaland"}], "generated_at": "2026-09-09"}

    sc_path = gsc.write_sidecar(spec, "value", png)

    assert sc_path == png.with_suffix(".png.json")
    payload = json.loads(sc_path.read_text(encoding="utf-8"))
    assert payload["card"] == "value"
    assert payload["rows"] == spec["rows"]
    assert payload["source_generated_at"] == "2026-09-09"
    assert payload["sha256"] == __import__("hashlib").sha256(b"hello-card").hexdigest()
    # generated_at (sidecarin oma aikaleima) on ISO-muotoinen eika tyhja.
    assert payload["generated_at"]


def test_write_sidecar_source_generated_at_is_empty_string_not_missing(tmp_path):
    """Builder joka ei tunne lahdeartefaktin generated_at:ia (esim. `stats`,
    kausiaggregaatti) ei saa nayttaa siltä että kentta unohtui — tyhja
    merkkijono on eri asia kuin puuttuva sidecar."""
    png = _write_fake_png(tmp_path / "goaliq_stats.png")
    payload_path = gsc.write_sidecar({"rows": []}, "stats", png)
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["source_generated_at"] == ""
    assert payload["rows"] == []


def test_write_sidecar_hashes_the_bytes_on_disk_not_a_stale_reference(tmp_path):
    """sha256 lasketaan LUETUISTA tavuista, ei jostain muistissa olevasta
    kuvasta — sama vikaluokka kuin 27.7:n hiljainen ohitus (loki valehteli
    onnistumisesta). Kaksi eri sisaltoa -> kaksi eri shaa."""
    png_a = _write_fake_png(tmp_path / "a.png", b"AAAA")
    png_b = _write_fake_png(tmp_path / "b.png", b"BBBB")
    sha_a = json.loads(gsc.write_sidecar({"rows": []}, "cs", png_a).read_text())["sha256"]
    sha_b = json.loads(gsc.write_sidecar({"rows": []}, "cs", png_b).read_text())["sha256"]
    assert sha_a != sha_b


# ---------------------------------------------------------------------------
# verify_sidecar: PORTTI joka kaataa jos kortilla ei ole tallennettua kuvaa
# tai shaa (rivin oma DoD)
# ---------------------------------------------------------------------------

def test_verify_sidecar_passes_for_a_freshly_written_pair(tmp_path):
    png = _write_fake_png(tmp_path / "ok.png", b"content")
    gsc.write_sidecar({"rows": [{"rank": 1}]}, "cs", png)
    gsc.verify_sidecar(png)  # ei poikkeusta


def test_verify_sidecar_raises_when_png_is_missing(tmp_path):
    missing = tmp_path / "ghost.png"
    with pytest.raises(FileNotFoundError, match="PNG puuttuu|puuttuu"):
        gsc.verify_sidecar(missing)


def test_verify_sidecar_raises_when_sidecar_is_missing(tmp_path):
    """🔴 TAMA ON RIVIN OMA DoD: kortti ilman tallennettua shaa ei saa
    lapaista hiljaa (POSTATTU-KORTTI-EI-OLE-TALLESSA)."""
    png = _write_fake_png(tmp_path / "no_sidecar.png", b"content")
    with pytest.raises(FileNotFoundError, match="sidecar"):
        gsc.verify_sidecar(png)


def test_verify_sidecar_raises_when_file_changed_after_sidecar_was_written(tmp_path):
    """NEGATIIVINEN KONTROLLI TOISEEN SUUNTAAN: sidecar on olemassa mutta
    valehtelee — tiedosto on vaihtunut sen kirjoittamisen jalkeen."""
    png = _write_fake_png(tmp_path / "tampered.png", b"original")
    gsc.write_sidecar({"rows": []}, "defence", png)
    png.write_bytes(b"tampered-afterwards")
    with pytest.raises(ValueError, match="sha256"):
        gsc.verify_sidecar(png)


# ---------------------------------------------------------------------------
# MUTAATIO: jos `write_sidecar` unohtaisi lukea levylta (esim. hashaisi
# `spec`:sta johdettua merkkijonoa canvasin sijaan), tama testi kaataisi sen
# ennen kuin `test_write_sidecar_hashes_the_bytes_on_disk...` ehtisi.
# ---------------------------------------------------------------------------

def test_sidecar_path_keeps_the_original_extension_in_the_stem(tmp_path):
    """`sidecar_path` ei saa tuottaa `.json`ia joka korvaa `.png`:n nimen
    kokonaan (esim. `goaliq_value.json`) — silloin kaksi eri korttia joilla
    on sama runko-osa mutta joku muu paate voisivat tormata, ja polku ei
    olisi ihmisluettavissa vierekkain PNG:n kanssa."""
    p = gsc.sidecar_path(Path("/tmp/outputs/cards/goaliq_value.png"))
    assert p.name == "goaliq_value.png.json"
