"""Portti: tasapeli katkaistaan samalla saannolla sivulla ja jakokortilla.

Loydos 29.8.2026 (julkaisuportti k1): sivun EO-lohkon kapteenitaulukko lajitteli
pelkalla `-captain_pct`:lla. Python-lajittelu on stabiili, joten tasapelin
ratkaisi syotteen jarjestys, ja syote tulee eri polkua sivulle kuin
jakokortille. Samasta otoksesta saattoi syntya kaksi eri "viidetta kapteenia".

Negatiivinen kontrolli on tassa se tarkein testi: `test_naiivi_lajittelu_eroaa`
mittaa etta vika on OIKEASTI havaittavissa tallä datalla. Ilman sita kaikki muut
testit menisivat lapi myos silloin, jos otoksessa ei sattuisi olemaan yhtaan
tasapelia -- eli portti olisi vihrea vaikka se ei mittaisi mitaan.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from scripts.ranking import _NO_ID, order_differs, ranked

ROOT = Path(__file__).resolve().parents[1]
EO_PATH = ROOT / "data" / "fpl_elite_ownership.json"


def _eo_players() -> list[dict]:
    data = json.loads(EO_PATH.read_text(encoding="utf-8"))
    return [p for p in (data.get("players") or []) if isinstance(p, dict)]


def _cap(p: dict, key: str) -> float:
    return float(((p.get("tiers") or {}).get(key) or {}).get("captain_pct") or 0.0)


def test_tasapeli_katkeaa_idlla():
    rows = [{"id": 427, "v": 3.5}, {"id": 379, "v": 3.5}, {"id": 411, "v": 30.0}]
    assert [r["id"] for r in ranked(rows, lambda r: r["v"])] == [411, 379, 427]


def test_syotteen_jarjestys_ei_vaikuta():
    rows = [{"id": 427, "v": 3.5}, {"id": 379, "v": 3.5}, {"id": 411, "v": 30.0}]
    expected = [r["id"] for r in ranked(rows, lambda r: r["v"])]
    for seed in range(20):
        shuffled = rows[:]
        random.Random(seed).shuffle(shuffled)
        assert [r["id"] for r in ranked(shuffled, lambda r: r["v"])] == expected


def test_idton_rivi_valahtaa_viimeiseksi_tasapelissa():
    rows = [{"v": 3.5}, {"id": 379, "v": 3.5}]
    assert [r.get("id", _NO_ID) for r in ranked(rows, lambda r: r["v"])] == [379, _NO_ID]


def test_oikeassa_datassa_on_tasapeli_juuri_viidennella_sijalla():
    # Ilman tata testi voisi olla vihrea siksi, ettei otoksessa ole tasapelia.
    players = _eo_players()
    assert players, "EO-artefakti on tyhja"
    key = "top1k"
    vals = sorted((_cap(p, key) for p in players if _cap(p, key) > 0), reverse=True)
    assert len(vals) >= 6
    assert vals[4] == vals[5], (
        "otoksessa ei enaa ole tasapelia viidennella sijalla - "
        "paivita testi uudella datalla, ala poista sita"
    )


def test_naiivi_lajittelu_eroaa_mutta_ranked_ei():
    """NEGATIIVINEN KONTROLLI: vika on havaittavissa tallä otoksella."""
    players = _eo_players()
    key = "top1k"
    pool = [p for p in players if _cap(p, key) > 0]
    reversed_pool = list(reversed(pool))

    naive_a = sorted(pool, key=lambda p: -_cap(p, key))[:5]
    naive_b = sorted(reversed_pool, key=lambda p: -_cap(p, key))[:5]
    assert order_differs(naive_a, naive_b), (
        "naiivi lajittelu ei eronnut - kontrolli lapaisisi tyhjana"
    )

    ranked_a = ranked(pool, lambda p: _cap(p, key), 5)
    ranked_b = ranked(reversed_pool, lambda p: _cap(p, key), 5)
    assert not order_differs(ranked_a, ranked_b)


def test_sivu_ja_kortti_saavat_saman_viidennen_kapteenin():
    """Sivun ja kortin polut mallinnetaan eri syotejarjestyksina."""
    players = _eo_players()
    key = "top1k"
    page_input = [p for p in players if _cap(p, key) > 0]
    card_input = sorted(page_input, key=lambda p: str(p.get("web_name") or ""))

    page = ranked(page_input, lambda p: _cap(p, key), 5)
    card = ranked(card_input, lambda p: _cap(p, key), 5)
    assert not order_differs(page, card)
    assert page[4]["id"] == card[4]["id"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
