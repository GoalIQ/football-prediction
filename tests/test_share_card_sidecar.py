# -*- coding: utf-8 -*-
"""POSTATTU-KORTTI-EI-OLE-TALLESSA (26.9.2026).

`outputs/` on .gitignoressa ja jokainen `gen_share_card.py`-ajo kirjoittaa
saman tiedostonimen yli, joten 9.9:n postatusta GW4-kortista ei jaanyt mitaan
gitiin - emme voi jalkikateen todistaa mita postasimme. Valiaikainen kaytanto
(kortti kopioidaan goaliq-app/cos-reports/marketing/assets/posted-cards/ +
sha256 draftiin) on kasityota.

Korjaus: `gen_share_card.write_sidecar()` kirjoittaa jokaisen renderoidun
kortin PNG:n vierelle `<png>.json`-sidecarin (sha256 + generated_at + spec),
kutsuttuna YHDESTA paikasta (`main()`, kaikki kolme rendererihaaraa). Nama
testit eivat aja canvas-renderia (ei fontteja testiymparistossa, sama rajoite
kuin `test_share_card_contract.py`:ssa) - ne testaavat sidecar-funktiota
suoraan aidolla PNG-tiedostolla levylla.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "gen_share_card", ROOT / "scripts" / "gen_share_card.py")
gsc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gsc)


def _fake_png(path: Path, payload: bytes = b"not-a-real-png-but-write_sidecar-only-hashes-bytes") -> Path:
    path.write_bytes(payload)
    return path


def test_sidecar_records_matching_sha256_generated_at_and_spec(tmp_path):
    png = _fake_png(tmp_path / "card.png")
    spec = {"title": "GW5 outlook", "generated_at": "2026-09-17",
            "rows": [{"name": "Haaland", "value": "7.9"}]}
    out = gsc.write_sidecar(png, spec)

    assert out == tmp_path / "card.png.json"
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["sha256"] == hashlib.sha256(png.read_bytes()).hexdigest()
    assert doc["generated_at"] == "2026-09-17"
    assert doc["spec"]["rows"] == [{"name": "Haaland", "value": "7.9"}]
    assert doc["png"] == "card.png"


def test_sidecar_generated_at_defaults_to_empty_when_spec_lacks_it():
    # Osa builderista (cs/defence/stats/xp/value/club-best/price-tier) ei
    # kanna generated_at-kenttaa specissa - sidecar ei saa keksia lukua.
    spec = {"title": "x", "rows": []}
    assert spec.get("generated_at", "") == ""


def test_negative_control_mutated_png_no_longer_matches_recorded_sha256(tmp_path):
    """Kontrolli: jos PNG korvataan sidecarin kirjoittamisen JALKEEN, tallennettu
    sha256 EI enaa tasmaa. Ilman tata kontrollia testi olisi voinut laheta
    vihrean myos silla etta tarkistus ei koskaan oikeasti vertaa tavuja."""
    png = _fake_png(tmp_path / "card.png")
    out = gsc.write_sidecar(png, {"title": "x", "rows": []})
    recorded = json.loads(out.read_text(encoding="utf-8"))["sha256"]

    png.write_bytes(b"a different png entirely")
    assert hashlib.sha256(png.read_bytes()).hexdigest() != recorded


def test_sidecar_path_is_png_name_plus_json_suffix(tmp_path):
    assert gsc.sidecar_path(tmp_path / "foo.png") == tmp_path / "foo.png.json"


def test_main_calls_write_sidecar_on_all_three_renderer_branches():
    """Yksi lukija -saanto (CLAUDE.md 6a): jos uusi kutsupaikka main()iin
    lisataan sidecaria kutsumatta, tama kaataa ajon eika jaa hiljaiseksi
    aukoksi (kuten outputs/-tilanne oli ennen tata riviä)."""
    src = (ROOT / "scripts" / "gen_share_card.py").read_text(encoding="utf-8")
    main_src = src[src.index("\ndef main() -> int:"):]
    assert main_src.count("write_sidecar(") == 3, (
        "main(): write_sidecar() ei ole kaikissa kolmessa rendererihaarassa "
        "(reply/gw_outlook/generic) - uusi kutsupaikka unohti sidecarin")
