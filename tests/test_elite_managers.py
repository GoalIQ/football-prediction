"""ELITE-MANAGERS: kehapaatelmavahti + tyhjan tuloksen vartija (25.8.2026)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "fpl_elite_managers", ROOT / "scripts" / "fpl_elite_managers.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _snap(tmp_path, after_gw):
    p = tmp_path / "snap.json"
    p.write_text(json.dumps({
        "meta": {"rank_after_gw": after_gw},
        "tiers": {"top1k": [1, 2, 3]},
    }), encoding="utf-8")
    return p


def _isolate(m, tmp_path, monkeypatch, after_gw):
    """Eristä verkosta ja datahakemistosta.

    🔴 Sama syy kuin EO-testeissa: mutaatioajossa 25.8 vahti tehtiin
    fail-openiksi ja virhepolkua testaava testi putosi tuotantopolulle,
    teki oikeita FPL-kutsuja ja kirjoitti oikeaan datahakemistoon."""
    monkeypatch.setattr(m, "SNAPSHOT_PATH", _snap(tmp_path, after_gw))
    monkeypatch.setattr(m, "OUT_PATH", tmp_path / "out.json")

    def _no_network(*a, **kw):
        raise AssertionError("testi yritti verkkokutsua")

    monkeypatch.setattr(m, "build", _no_network)
    return m


def test_sama_kierros_estetaan(tmp_path, monkeypatch, capsys):
    """Sijoitus GW1:n jalkeen + GW1:n siirrot = 'karki siirsi X:n sisaan'
    muuttuu havainnoksi 'X pelasi hyvin'."""
    m = _isolate(_load(), tmp_path, monkeypatch, 1)
    assert m.main(["--gw", "1"]) == 2
    err = capsys.readouterr().err
    assert "KEHAPAATELMA" in err
    assert "--gw 2" in err


def test_puuttuva_snapshot_on_virhe(tmp_path, monkeypatch, capsys):
    m = _load()
    monkeypatch.setattr(m, "SNAPSHOT_PATH", tmp_path / "ei-ole.json")
    assert m.main(["--gw", "2"]) == 2
    assert "puuttuu" in capsys.readouterr().err


def test_tyhja_otos_ei_kirjoita_tiedostoa(tmp_path, monkeypatch, capsys):
    """🔴 Kierroksen valinnat eivat ole julkisia ennen sen deadlinea: jokainen
    picks-kutsu vastaa 404 ja koko otos putoaa missing:iin. Ilman vartijaa ajo
    kirjoittaisi tyhjan tiedoston, poistuisi nollalla ja nayttaisi tulokselta.
    """
    m = _load()
    monkeypatch.setattr(m, "SNAPSHOT_PATH", _snap(tmp_path, 1))
    out = tmp_path / "out.json"
    monkeypatch.setattr(m, "OUT_PATH", out)
    monkeypatch.setattr(m, "build", lambda gw, snap, top, verbose=True: {
        "meta": {"circular": False},
        "tiers": {"top1k": {"n_sampled": 0, "hold_pct": None}},
    })
    assert m.main(["--gw", "2"]) == 2
    assert not out.exists(), "tyhja tulos EI saa paatya levylle"
    assert "deadline" in capsys.readouterr().err


def test_osittainen_otos_kirjoitetaan_mutta_varoittaa(tmp_path, monkeypatch, capsys):
    """Yksi taso ilman otosta ei saa kaataa koko ajoa - mutta se ei saa
    myoskaan mennä hiljaa lapi."""
    m = _load()
    monkeypatch.setattr(m, "SNAPSHOT_PATH", _snap(tmp_path, 1))
    out = tmp_path / "out.json"
    monkeypatch.setattr(m, "OUT_PATH", out)
    monkeypatch.setattr(m, "build", lambda gw, snap, top, verbose=True: {
        "meta": {"circular": False},
        "tiers": {"top1k": {"n_sampled": 50, "hold_pct": 20.0},
                  "top10k": {"n_sampled": 0, "hold_pct": None}},
    })
    assert m.main(["--gw", "2"]) == 0
    assert out.exists()
    assert "top10k" in capsys.readouterr().err


def test_hold_lasketaan_tuloksena_eika_puuttuvana(tmp_path, monkeypatch):
    """🔴 Manageri joka ei tehnyt siirtoa KUULUU otokseen: hold on myos
    valinta. Vain 404 (tr is None) pudottaa managerin."""
    m = _load()
    monkeypatch.setattr(m.fpl_api, "fetch_entry_transfers",
                        lambda e, **kw: [] if e != 3 else None)
    monkeypatch.setattr(m.fpl_api, "fetch_entry_picks", lambda e, gw, **kw: (
        None if e == 3 else {"active_chip": None, "entry_history": {},
                             "picks": [{"element": 9, "is_captain": True}]}))
    t = m.collect_tier("top1k", [1, 2, 3], 2, verbose=False)
    assert t["n_sampled"] == 2, "tyhja siirtolista kuuluu otokseen"
    assert t["n_missing"] == 1, "404 pudottaa"
    assert t["hold"] == 2, "molemmat pitivat joukkueensa"
    assert t["_cap"] == {9: 2}
