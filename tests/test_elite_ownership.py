"""EO-by-tier: otoksen jakauma + kehapaatelmavahti (25.8.2026).

🔴 TAUSTA. Ensimmainen versio otti sijoitusotoksen JA valinnat samalta
kierrokselta, ja se on kehapaatelma: kierroksen N jalkeinen sijoitus on
osittain seuraus siita mita manageri omisti kierroksella N.

Mitattu 25.8 GW1:n jalkeen, Bench Boostin kaytto sijoitustasoittain:
    top1k 90,0 % · top10k 87,5 % · top100k 67,5 % · ~1M 27,1 % · ~3M 8,3 %
Monotoninen gradientti 8 -> 90 %. BB lisaa penkkipisteet -> korkeampi
pistemaara -> korkeampi sijoitus. "Top 1k" yhden kierroksen jalkeen on siis
paaosin otos chipin pelanneista, ei otos hyvista managereista, ja sama
valikoituma varjaa jokaisen pelaajan EO-luvun samassa otoksessa.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "fpl_elite_ownership", ROOT / "scripts" / "fpl_elite_ownership.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Otos jakautuu koko tason yli, ei sen karkeen
# ---------------------------------------------------------------------------
def test_otos_jakautuu_koko_tason_yli():
    """🔴 top10k:n otos joka olisi vain sivut 1-20 olisi tosiasiassa top1k
    uudelleen, ja kaksi 'eri' tasoa nayttaisi samat luvut. Se olisi
    mittausvirhe joka nayttaa loydokselta ('karjen tasot ovat yksimielisia').
    """
    m = _load()
    pages = m._sample_pages(200, 20)
    assert len(pages) == 20
    assert min(pages) == 1
    # Viimeisen sivun on oltava tason loppupaassa, ei sen karjessa.
    assert max(pages) > 150, f"otos ei ulotu tason loppuun: {pages}"
    # ...eika otos saa olla pelkka alkupaa
    assert sum(1 for p in pages if p > 100) >= 8, f"otos painottuu karkeen: {pages}"


def test_pieni_taso_otetaan_kokonaan():
    m = _load()
    assert m._sample_pages(20, 20) == list(range(1, 21))
    assert m._sample_pages(5, 20) == [1, 2, 3, 4, 5]


def test_sivunumerot_ovat_uniikkeja_ja_kelvollisia():
    """Sivu 0 tai duplikaatti kuluttaisi pyyntobudjettia ilman uutta dataa."""
    m = _load()
    for last, n in [(200, 20), (2000, 20), (37, 12), (2, 20)]:
        pages = m._sample_pages(last, n)
        assert pages == sorted(set(pages)), (last, n, pages)
        assert all(1 <= p <= last for p in pages), (last, n, pages)


# ---------------------------------------------------------------------------
# Kehapaatelmavahti
# ---------------------------------------------------------------------------
def _write_snapshot(tmp_path, after_gw):
    p = tmp_path / "fpl_rank_snapshot.json"
    p.write_text(json.dumps({
        "meta": {"rank_after_gw": after_gw, "taken_at": "2026-08-25T00:00:00+00:00"},
        "tiers": {"top1k": [1, 2, 3]},
    }), encoding="utf-8")
    return p


def test_sama_kierros_molemmille_estetaan(tmp_path, monkeypatch, capsys):
    """Sijoitus GW1:n jalkeen + GW1:n valinnat = kehapaatelma -> exit 2."""
    m = _load()
    monkeypatch.setattr(m, "SNAPSHOT_PATH", _write_snapshot(tmp_path, 1))
    assert m.main(["--picks", "--gw", "1"]) == 2
    err = capsys.readouterr().err
    assert "KEHAPAATELMA" in err
    assert "--gw 2" in err, "virheen on kerrottava mika ajo olisi kelvollinen"


def test_aiempi_kierros_estetaan_myos(tmp_path, monkeypatch):
    """Sijoitus GW3:n jalkeen + GW2:n valinnat on yha kehallinen: sijoitus
    tuntee jo GW2:n lopputuloksen."""
    m = _load()
    monkeypatch.setattr(m, "SNAPSHOT_PATH", _write_snapshot(tmp_path, 3))
    assert m.main(["--picks", "--gw", "2"]) == 2


def test_puuttuva_snapshot_on_virhe_eika_tyhja_tulos(tmp_path, monkeypatch, capsys):
    """🔴 Tyhja tulos nayttaisi onnistumiselta. Vrt. kontrolli-lapaisi-tyhjana."""
    m = _load()
    monkeypatch.setattr(m, "SNAPSHOT_PATH", tmp_path / "ei-ole.json")
    assert m.main(["--picks", "--gw", "2"]) == 2
    assert "puuttuu" in capsys.readouterr().err


def test_allow_circular_ei_ole_hiljainen_ohitus(tmp_path, monkeypatch):
    """Pakotus on sallittu, mutta sen on merkittava payload. Ilman `circular`-
    kenttaa pinta esittaisi kehalliset luvut neutraaleina."""
    m = _load()
    monkeypatch.setattr(m, "SNAPSHOT_PATH", _write_snapshot(tmp_path, 1))
    calls = {}

    def _fake_build(gw, snap, verbose=True):
        calls["gw"] = gw
        return {"meta": {"circular": gw <= snap["meta"]["rank_after_gw"],
                         "sample": {}}, "players": []}

    monkeypatch.setattr(m, "build", _fake_build)
    monkeypatch.setattr(m, "OUT_PATH", tmp_path / "out.json")
    assert m.main(["--picks", "--gw", "1", "--allow-circular"]) == 0
    written = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert written["meta"]["circular"] is True


def test_myohempi_kierros_sallitaan(tmp_path, monkeypatch):
    """Sijoitus GW1:n jalkeen + GW2:n valinnat = kelvollinen mittaus."""
    m = _load()
    monkeypatch.setattr(m, "SNAPSHOT_PATH", _write_snapshot(tmp_path, 1))
    monkeypatch.setattr(m, "OUT_PATH", tmp_path / "out.json")
    monkeypatch.setattr(m, "build", lambda gw, snap, verbose=True: {
        "meta": {"circular": False, "sample": {}}, "players": []})
    assert m.main(["--picks", "--gw", "2"]) == 0
    written = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert written["meta"]["circular"] is False
