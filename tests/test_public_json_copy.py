"""check_copy_style.scan_public_json: suomi ja em dash pois julkisista payloadeista.

Tausta (23.8.2026, BACKEND-FI-JULKISESSA-PAYLOADISSA): portti skannasi HTML:n,
SPA:n ja openapi.jsonin, muttei sitä mitä API palauttaa `data/`-artefakteista
sellaisenaan. Mitattu tuotannosta:

    /api/fantasy/rate-team -> meta.projection_accuracy.meta.population
        = "pelanneet (minuutit > 0)"

Aiempi sääntö (em dash + skandinaaviset merkit) EI olisi napannut sitä: siinä
ei ole kumpaakaan. Siksi mukana on suomen sanalista — ja siksi tässä on
negatiivinen kontrolli sekä väärille positiivisille (pelaajanimet) että
väärille negatiivisille.
"""
from __future__ import annotations

import json

import scripts.check_copy_style as cs


def _kirjoita(tmp_path, nimi: str, doc: dict):
    d = tmp_path / "data"
    d.mkdir(exist_ok=True)
    (d / nimi).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def _skannaa(monkeypatch, tmp_path, nimi: str, doc: dict):
    _kirjoita(tmp_path, nimi, doc)
    monkeypatch.setattr(cs, "PUBLIC_JSON", [f"data/{nimi}"])
    return cs.scan_public_json(root=tmp_path)


def test_nappaa_suomen_ilman_skandeja_ja_ilman_dashia(monkeypatch, tmp_path):
    """Tuotannon oikea tapaus: 'pelanneet (minuutit > 0)'."""
    osumat = _skannaa(monkeypatch, tmp_path, "a.json", {
        "meta": {"population": "pelanneet (minuutit > 0)"}})
    assert len(osumat) == 1
    assert "suomenkielinen" in osumat[0][2]


def test_nappaa_em_dashin(monkeypatch, tmp_path):
    osumat = _skannaa(monkeypatch, tmp_path, "b.json", {
        "meta": {"product": "GoalIQ Fantasy Phase 0 — clean sheet %"}})
    assert len(osumat) == 1
    assert "dash" in osumat[0][2]


def test_pelaajanimen_umlaut_ei_ole_osuma(monkeypatch, tmp_path):
    """Väärä positiivinen jonka ensimmäinen versio tuotti 200 kertaa."""
    osumat = _skannaa(monkeypatch, tmp_path, "c.json", {
        "players": [{"web_name": "Lindelöf", "full_name": "Victor Lindelöf"},
                    {"web_name": "Schär"},
                    {"web_name": "Abdülkadir Ömür"}]})
    assert osumat == []


def test_skandit_kopio_kentassa_ovat_osuma(monkeypatch, tmp_path):
    """Sama merkki eri kentässä: nimessä ok, kopiossa ei."""
    osumat = _skannaa(monkeypatch, tmp_path, "d.json", {
        "meta": {"note": "Sisältää vain kotipelit"}})
    assert len(osumat) == 1


def test_englanninkielinen_copy_lapaisee(monkeypatch, tmp_path):
    osumat = _skannaa(monkeypatch, tmp_path, "e.json", {
        "meta": {
            "method": "walk-forward backtest on the completed season",
            "population": "players with minutes (minutes > 0)",
            "product": "GoalIQ Fantasy Phase 0 - clean sheet % + model FDR",
        },
        "players": [{"web_name": "Haaland", "pts": 12}],
    })
    assert osumat == []


def test_rikkinainen_json_on_osuma_ei_hiljainen_ohitus(monkeypatch, tmp_path):
    d = tmp_path / "data"
    d.mkdir(exist_ok=True)
    (d / "f.json").write_text("ei-json{", encoding="utf-8")
    monkeypatch.setattr(cs, "PUBLIC_JSON", ["data/f.json"])
    osumat = cs.scan_public_json(root=tmp_path)
    assert len(osumat) == 1
    assert "ei luettavissa" in osumat[0][2]


def test_puuttuva_tiedosto_ei_ole_osuma(monkeypatch, tmp_path):
    monkeypatch.setattr(cs, "PUBLIC_JSON", ["data/ei-olemassa.json"])
    assert cs.scan_public_json(root=tmp_path) == []


def test_tuotannon_artefaktit_ovat_puhtaita():
    """Elävä kontrolli: repon omat julkiset artefaktit läpäisevät."""
    assert cs.scan_public_json() == []
