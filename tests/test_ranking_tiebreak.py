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


def _sidottu_n(pool, key: str) -> int | None:
    """Pienin N jossa tasapeli katkaisee top-N:n rajan, tai None.

    🔴 N JOHDETAAN DATASTA, EI KOVAKOODATA (12.9.2026).
    Vanha versio vaati tasapelin **tasan viidennella sijalla** ja luki elavaa
    otosdataa. Mitattu: kun elite-otos paivittyi GW4:n valintoihin (600 entrya,
    12.9), `captain_pct > 0` -pelaajia oli 10 ja tasapelit siirtyivat
    indekseihin 6, 8, 9 — eli vals[4] == vals[5] ei enaa pitanyt (3.0 vs 1.5)
    ja naiivi lajittelu ei eronnut N=5:lla lainkaan. Testi punastui vaikka
    mikaan ei ollut rikki, ja se on huonompi kuin puuttuva testi: se opettaa
    ohittamaan (sama vikaluokka kuin CLAUDE.md saanto 6a kohta 3).

    Tasapelin PAIKKA on otoksen ominaisuus. Sen OLEMASSAOLO rajalla on se mita
    portti tarvitsee, ja se etsitaan.
    """
    vals = sorted((_cap(p, key) for p in pool if _cap(p, key) > 0), reverse=True)
    for i in range(1, len(vals)):
        if vals[i] == vals[i - 1]:
            return i
    return None


def test_oikeassa_datassa_on_tasapeli_joka_katkaisee_rajan():
    """Ilman tata testi voisi olla vihrea siksi, ettei otoksessa ole tasapelia."""
    players = _eo_players()
    assert players, "EO-artefakti on tyhja"
    pool = [p for p in players if _cap(p, "top1k") > 0]
    assert len(pool) >= 6, f"otos liian pieni ({len(pool)}) tasapelin mittaamiseen"
    n = _sidottu_n(pool, "top1k")
    assert n is not None, (
        "otoksessa ei ole YHTAAN tasapelia captain_pct-sarakkeessa. Portti ei "
        "silloin mittaa mitaan oikealla datalla — synteettinen kontrolli "
        "(test_synteettinen_tasapeli_on_aina_mitattavissa) kantaa sen, mutta "
        "tama on syyta tietaa: paivita otos tai laajenna avainta."
    )


def test_naiivi_lajittelu_eroaa_mutta_ranked_ei():
    """NEGATIIVINEN KONTROLLI: vika on havaittavissa talla otoksella.

    N tulee `_sidottu_n`ista, joten kontrolli mittaa sita rajaa jossa tasapeli
    OIKEASTI on — ei sita jossa se sattui olemaan 29.8.
    """
    players = _eo_players()
    key = "top1k"
    pool = [p for p in players if _cap(p, key) > 0]
    n = _sidottu_n(pool, key)
    if n is None:
        pytest.skip("ei tasapelia otoksessa; synteettinen kontrolli kantaa")
    reversed_pool = list(reversed(pool))

    naive_a = sorted(pool, key=lambda p: -_cap(p, key))[:n]
    naive_b = sorted(reversed_pool, key=lambda p: -_cap(p, key))[:n]
    assert order_differs(naive_a, naive_b), (
        f"naiivi lajittelu ei eronnut N={n}:lla vaikka tasapeli on juuri "
        f"siina rajalla — kontrolli lapaisisi tyhjana"
    )

    ranked_a = ranked(pool, lambda p: _cap(p, key), n)
    ranked_b = ranked(reversed_pool, lambda p: _cap(p, key), n)
    assert not order_differs(ranked_a, ranked_b)


def test_synteettinen_tasapeli_on_aina_mitattavissa():
    """🔴 Portti ei saa olla elavan otoksen sisallon varassa.

    Tama ajaa saman vaitteen fikstuurilla, joten mekanismi on mitattu
    riippumatta siita mita karki sattuu tana viikkona kapteenoimaan.
    """
    pool = [{"id": i, "tiers": {"top1k": {"captain_pct": v}}}
            for i, v in ((411, 62.0), (427, 18.5), (154, 3.0),
                         (165, 3.0), (40, 1.5), (68, 1.5))]
    key = "top1k"
    assert _sidottu_n(pool, key) == 3, "fikstuuri ei enaa sido rajaa N=3:een"
    rev = list(reversed(pool))

    naive_a = sorted(pool, key=lambda p: -_cap(p, key))[:3]
    naive_b = sorted(rev, key=lambda p: -_cap(p, key))[:3]
    assert order_differs(naive_a, naive_b), "fikstuuri ei paljasta vikaa"

    assert not order_differs(ranked(pool, lambda p: _cap(p, key), 3),
                             ranked(rev, lambda p: _cap(p, key), 3))


def test_sivu_ja_kortti_saavat_saman_viimeisen_kapteenin():
    """Sivun ja kortin polut mallinnetaan eri syotejarjestyksina.

    Raja on `_sidottu_n`ista eika kovakoodattu viides: kortin ja sivun on
    oltava samaa mielta juuri siina kohdassa jossa tasapeli katkaistaan.
    """
    players = _eo_players()
    key = "top1k"
    page_input = [p for p in players if _cap(p, key) > 0]
    card_input = sorted(page_input, key=lambda p: str(p.get("web_name") or ""))
    n = _sidottu_n(page_input, key) or min(5, len(page_input))

    page = ranked(page_input, lambda p: _cap(p, key), n)
    card = ranked(card_input, lambda p: _cap(p, key), n)
    assert not order_differs(page, card)
    assert page[n - 1]["id"] == card[n - 1]["id"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
