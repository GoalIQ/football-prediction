# -*- coding: utf-8 -*-
"""POSTATTU-KORTTI-EI-OLE-TALLESSA (12.9): `outputs/` on gitignoroitu ja
jokainen `gen_share_card.py`-ajo kirjoittaa saman tiedostonimen yli. Mitattu
12.9: 9.9:n postattu GW4-kortti (M82) ei ole enaa olemassa missaan —
MARKETING_QUEUE.md:n commit-viittaus osoittaa tyhjaa, koska `outputs/` ei ole
koskaan ollut gitissa. Emme voineet todistaa mita postasimme emmeka verrata
seuraavaa korttia edelliseen ilman datan rekonstruointia gitista.

Korjaus: jokainen renderointi kirjoittaa PNG:n rinnalle `<tiedosto>.json`
-sidecarin (sha256 + kortin sisalto + renderointihetki), joten todiste
sailyy vaikka itse kuva hukkuisi ajojen alle.

Canvas-renderia (`render`/`render_gw_outlook*`) ei voi ajaa pytestista —
sama linja kuin `test_share_card_contract.py`:ssa (fontit tulevat
goaliq-app-repon node_modulesista eika niita ole CI-runnerilla). Sidecar
itsessaan ei riipu PIL-piirrosta, joten se testataan suoraan; kolme
renderointifunktiota testataan lahdekoodiluvulla (kutsuvatko ne sidecaria).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts" / "gen_share_card.py"


def _fake_png(tmp_path: Path, name: str, body: bytes = b"not-a-real-png") -> Path:
    p = tmp_path / name
    p.write_bytes(body)
    return p


def test_sidecar_records_matching_sha256_and_rows(tmp_path):
    from scripts.gen_share_card import _write_sidecar

    out = _fake_png(tmp_path, "card.png", b"pixel-bytes-v1")
    spec = {"title": "TOP VALUE PICKS", "generated_at": "2026-09-12T06:00:00Z",
            "rows": [{"rank": 1, "name": "Haaland"}]}
    side = _write_sidecar(spec, out)

    assert side == out.with_name("card.png.json")
    payload = json.loads(side.read_text(encoding="utf-8"))
    assert payload["sha256"] == hashlib.sha256(b"pixel-bytes-v1").hexdigest()
    assert payload["file"] == "card.png"
    assert payload["title"] == "TOP VALUE PICKS"
    assert payload["source_generated_at"] == "2026-09-12T06:00:00Z"
    assert payload["rows"] == [{"rank": 1, "name": "Haaland"}]
    assert payload["rendered_at"], "renderointihetki puuttuu — provenienssi ei ole taydellinen"


def test_sidecar_falls_back_to_fixtures_for_gw_outlook_cards(tmp_path):
    """gw-outlook-kortit kantavat `fixtures`ia, ei `rows`ia — sidecar EI SAA
    jattaa niita tyhjiksi (silloin sidecar ei todistaisi mitaan sisallosta)."""
    from scripts.gen_share_card import _write_sidecar

    out = _fake_png(tmp_path, "outlook.png")
    spec = {"kind": "gw_outlook", "gw": 5,
            "fixtures": [{"home": "Arsenal", "away": "Chelsea"}]}
    payload = json.loads(_write_sidecar(spec, out).read_text(encoding="utf-8"))
    assert payload["rows"] == [{"home": "Arsenal", "away": "Chelsea"}]


def test_sidecar_hash_changes_with_the_actual_bytes(tmp_path):
    """NEGATIIVINEN KONTROLLI: sha256 tulee TIEDOSTOSTA, ei specista. Ilman
    tata sidecar voisi kirjoittaa minka tahansa (esim. vanhan) tiivisteen
    eika todistaisi etta juuri TAMA kuva syntyi."""
    from scripts.gen_share_card import _write_sidecar

    spec = {"title": "X", "rows": []}
    out_a = _fake_png(tmp_path, "a.png", b"version-a")
    out_b = _fake_png(tmp_path, "b.png", b"version-b")
    hash_a = json.loads(_write_sidecar(spec, out_a).read_text())["sha256"]
    hash_b = json.loads(_write_sidecar(spec, out_b).read_text())["sha256"]
    assert hash_a != hash_b
    assert hash_a == hashlib.sha256(b"version-a").hexdigest()


# ---------------------------------------------------------------------------
# Lahdekoodiluku: kaikki kolme renderointifunktiota kutsuvat sidecaria
# ---------------------------------------------------------------------------

def test_all_three_render_functions_write_a_sidecar():
    src = SRC.read_text(encoding="utf-8")
    for fn in ("def render(", "def render_gw_outlook(",
               "def render_gw_outlook_hero("):
        start = src.index(fn)
        end = src.index("\ndef ", start + 1)
        body = src[start:end]
        assert "_write_sidecar(spec, out_path)" in body, (
            f"{fn} ei enaa kirjoita sidecaria — postattu kortti katoaisi "
            "taas jaljettomiin seuraavalla ajolla."
        )


def test_negative_control_missing_sidecar_call_is_caught():
    """MUTAATIO: jos kutsu poistetaan yhdesta funktiosta, edellisen testin
    on kaadeuttava eika lapaistava hiljaa."""
    src = SRC.read_text(encoding="utf-8")
    mutated = src.replace(
        '    canvas.convert("RGB").save(out_path, "PNG")\n'
        '    _write_sidecar(spec, out_path)\n',
        '    canvas.convert("RGB").save(out_path, "PNG")\n',
        1,
    )
    assert mutated != src, "mutaatio ei osunut — testi ei mittaisi mitaan"
    start = mutated.index("def render(")
    end = mutated.index("\ndef ", start + 1)
    assert "_write_sidecar(spec, out_path)" not in mutated[start:end], (
        "mutaatio ei poistanut kutsua odotetusti"
    )
