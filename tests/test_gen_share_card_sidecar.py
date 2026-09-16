"""POSTATTU-KORTTI-EI-OLE-TALLESSA (mitattu 12.9.2026, korjattu 16.9).

`outputs/` on football-predictionin .gitignoressa ja jokainen
`gen_share_card.py`-ajo kirjoittaa saman tiedostonimen yli. Seuraus: 9.9
postattua GW4-korttia (M82) ei ole enaa olemassa missaan, ja
MARKETING_QUEUE-viittaus commit-hashiin `9ff5df035` on tyhja (`git log --
outputs/cards/` ei nayta gitignoroitua polkua) — emme voi todistaa mita
oikeasti postasimme emmeka verrata seuraavaa korttia edelliseen muuten kuin
rekonstruoimalla data gitista.

`write_sidecar` kirjoittaa jokaisen ajon jalkeen `<kortti>.png.json`in,
jossa on rivit jotka kortti nayttaa, lahdeartefaktin generated_at, ja PNG:n
sha256 — jalkimmainen todistaa etta juuri TAMA tiedosto vastaa sidecaria
eika joku myohempi uudelleenajo samalla nimella.
"""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "gen_share_card", ROOT / "scripts" / "gen_share_card.py")
gsc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gsc)


def test_sidecar_carries_rows_generated_at_and_matching_sha(tmp_path):
    png = tmp_path / "goaliq-cs.png"
    png.write_bytes(b"\x89PNG-fake-bytes-for-the-test")
    spec = {"title": "Best clean sheet odds", "generated_at": "2026-09-16T03:00:00",
            "rows": [{"rank": 1, "name": "Arsenal", "value": "62%"}]}

    sidecar_path = gsc.write_sidecar(png, spec)

    assert sidecar_path == png.with_suffix(".png.json")
    doc = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert doc["file"] == "goaliq-cs.png"
    assert doc["source_generated_at"] == "2026-09-16T03:00:00"
    assert doc["rows"] == spec["rows"]
    assert doc["sha256"] == hashlib.sha256(png.read_bytes()).hexdigest()


def test_sidecar_falls_back_to_fixtures_for_gw_outlook_cards(tmp_path):
    """gw-outlook-kortin spec kantaa `fixtures`ia, ei `rows`ia — sidecar ei
    saa jaada tyhjaksi vain siksi etta avain on eri."""
    png = tmp_path / "goaliq-gw4-outlook.png"
    png.write_bytes(b"fake-png")
    spec = {"title": "GW4 outlook", "gw": 4,
            "fixtures": [{"home": "Arsenal", "away": "Chelsea"}]}

    doc = json.loads(gsc.write_sidecar(png, spec).read_text(encoding="utf-8"))
    assert doc["rows"] == spec["fixtures"]
    assert doc["source_generated_at"] is None


def test_sidecar_sha_reveals_a_file_swapped_after_the_fact(tmp_path):
    """NEGATIIVINEN KONTROLLI: jos joku ajaa generaattorin uudelleen SAMALLA
    tiedostonimella eika sidecaria paiviteta (esim. kasin kopioitu tiedosto
    postausta varten), tallennettu sha256 ei enaa tasmaa levylla olevaan
    kuvaan — juuri se tila jota sidecarin piti tehda mahdottomaksi jaada
    huomaamatta."""
    png = tmp_path / "goaliq-value.png"
    png.write_bytes(b"original-render")
    sidecar_path = gsc.write_sidecar(png, {"rows": []})
    saved = json.loads(sidecar_path.read_text(encoding="utf-8"))

    png.write_bytes(b"a-later-rerun-overwrote-the-same-filename")

    assert saved["sha256"] != hashlib.sha256(png.read_bytes()).hexdigest()


def test_main_writes_a_sidecar_after_every_render_call():
    """PORTTI JOKA ESTAA TOISTUMISEN: jos main():iin lisataan uusi
    renderointihaara (uusi korttityyppi) joka ei kutsu write_sidecar:ia,
    juuri se korttityyppi voisi taas kadota jaljittomasti postauksen
    jalkeen. Mitataan lahdekoodista suoraan, ei kaytoksesta, koska
    kaytosportti vaatisi PIL-fontit + kaikki datalahteet joka korttityypille."""
    src = inspect.getsource(gsc.main)
    render_result_vars = set(re.findall(
        r"\b(p|pth)\s*=\s*render(?:_gw_outlook(?:_hero)?)?\(", src))
    sidecar_input_vars = set(re.findall(r"write_sidecar\((p|pth),", src))
    assert render_result_vars == {"p", "pth"}, (
        "testi olettaa etta main() sitoo renderoinnin tuloksen nimiin "
        "p/pth — jos main() on muuttunut, paivita talle testille nama nimet")
    assert sidecar_input_vars == render_result_vars, (
        f"renderointi sitoo tulokset {render_result_vars} mutta "
        f"write_sidecar kutsutaan vain naille: {sidecar_input_vars} — "
        "jokin korttityyppi jaisi tallentamatta")
