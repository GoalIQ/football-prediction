"""Portti: ketjun uudelleenaloitus entrysta on eksplisiittinen, ei fallback.

TAUSTA (4.9.2026). `entry_mismatch` kaataa freezen kun peritty runko ei ole
entryn runko. Pelkka esto on umpikuja: ketju oli jo eronnut (GW2:n wildcard)
eika `_prev_freeze` osaa palata takaisin. Villen paatos 4.9 oli aloittaa
ketju uudelleen entryn omista pickeista.

Reitti ulos on siis oltava - mutta jos se olisi HILJAINEN fallback ("jos
ketju eroaa, ota entry"), se olisi tasan sama vikaluokka jota portti estaa:
runko vaihtuisi ilman etta kukaan paattaa sita. Siksi reseed on tiedosto
jossa on gw, source_gw, syy, paattaja ja paivays, ja vajaa tai vaaralle
kierrokselle kirjattu reseed on VIRHE eika ohitus.

Toinen mitattu asia: entryn rivilla voi olla pelaaja jota poolissa ei ole.
4.9 se oli Dovin (id 171, status u, "joined Leyton Orient on loan"). Han on
oikein suodatettu poolista, mutta han on yha entryn 15:ssa. Jos siemen
kaatuu siihen, ketjua ei voi aloittaa lainkaan; jos hanet lisataan pooliin,
hanesta tulee OSTETTAVA (muisti: fpl-lahtenyt-pelaaja-pysyy-bootstrapissa).
Oikea vastaus on kolmas: rungossa xP 0:lla, poolin ulkopuolella.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import freeze_model_squad_gw as freeze
from src.models import fpl_model_entry as entry_mod

KENTAT = {"gw": 3, "source_gw": 2, "reason": "wildcard katkaisi ketjun",
          "decided_by": "Ville", "decided_at": "2026-09-04"}


def _kirjoita(tmp_path, data, gw=3):
    d = tmp_path / "model_squad_reseed"
    d.mkdir(exist_ok=True)
    (d / f"gw{gw}.json").write_text(json.dumps(data), encoding="utf-8")
    return d


# --- load_reseed ------------------------------------------------------------

def test_kelvollinen_reseed_hyvaksytaan(tmp_path, monkeypatch):
    monkeypatch.setattr(freeze, "RESEED_DIR", _kirjoita(tmp_path, KENTAT))
    r, virhe = freeze.load_reseed(3)
    assert virhe is None
    assert r["source_gw"] == 2


def test_ei_tiedostoa_ei_ole_virhe(tmp_path, monkeypatch):
    monkeypatch.setattr(freeze, "RESEED_DIR", tmp_path / "tyhja")
    assert freeze.load_reseed(3) == (None, None)


def test_puuttuva_perustelu_on_virhe(tmp_path, monkeypatch):
    vajaa = dict(KENTAT, reason="")
    monkeypatch.setattr(freeze, "RESEED_DIR", _kirjoita(tmp_path, vajaa))
    r, virhe = freeze.load_reseed(3)
    assert r is None and "reason" in virhe


def test_vaaralle_kierrokselle_kirjattu_on_virhe(tmp_path, monkeypatch):
    monkeypatch.setattr(freeze, "RESEED_DIR",
                        _kirjoita(tmp_path, dict(KENTAT, gw=4)))
    r, virhe = freeze.load_reseed(3)
    assert r is None and "gw=4" in virhe


def test_source_gw_ei_saa_olla_tuleva(tmp_path, monkeypatch):
    monkeypatch.setattr(freeze, "RESEED_DIR",
                        _kirjoita(tmp_path, dict(KENTAT, source_gw=3)))
    r, virhe = freeze.load_reseed(3)
    assert r is None and "source_gw" in virhe


def test_rikkinainen_json_on_virhe(tmp_path, monkeypatch):
    d = tmp_path / "model_squad_reseed"
    d.mkdir()
    (d / "gw3.json").write_text("{ ei jsonia", encoding="utf-8")
    monkeypatch.setattr(freeze, "RESEED_DIR", d)
    r, virhe = freeze.load_reseed(3)
    assert r is None and "JSON" in virhe


# --- entry_seed -------------------------------------------------------------

def _pool(ids):
    return [{"id": i, "web_name": "P%d" % i, "element_type": 3, "club": i % 20,
             "price": 50, "xp_horizon_total": 1.0, "gameweeks": []}
            for i in ids]


def _bootstrap(pid, tiimi=7):
    return {"elements": [{"id": pid, "web_name": "Lahtenyt", "team": tiimi,
                          "element_type": 1, "now_cost": 40, "status": "u",
                          "news": "joined X on loan",
                          "selected_by_percent": "0.1"}],
            "teams": [{"id": tiimi, "name": "Coventry", "short_name": "COV"}]}


def _hae(ids):
    def hae(entry, gw):
        return [{"element": i} for i in ids]
    return hae


def _historia(value=999, bank=8):
    def h(entry, gw):
        return {"value": value, "bank": bank}, None
    return h


def test_siemen_tulee_entryn_pickeista():
    ids = list(range(1, 16))
    siemen, virhe = entry_seed_apu(ids, ids)
    assert virhe is None
    assert [p["id"] for p in siemen["xi"] + siemen["bench"]] == ids


def entry_seed_apu(pick_ids, pool_ids, value=999, bank=8, off=None):
    off = off or []
    return freeze.entry_seed(
        2, _pool(pool_ids), _bootstrap(off[0]) if off else {"elements": [], "teams": []},
        hae=_hae(pick_ids), hae_historia=_historia(value, bank))


def test_budjetti_luetaan_entryn_historiasta_ei_vakiosta():
    """100.0 olisi vaara: wildcardin jalkeen tilin arvo ei ole lahtoarvo,
    ja vaara budjetti muuttaisi siirtomoottorin vastausta hiljaa."""
    ids = list(range(1, 16))
    siemen, _ = entry_seed_apu(ids, ids, value=999, bank=8)
    assert siemen["meta"]["budget"] == 100.7
    siemen2, _ = entry_seed_apu(ids, ids, value=1012, bank=3)
    assert siemen2["meta"]["budget"] == 101.5


def test_wildcardin_jalkeen_ei_rullausta():
    ids = list(range(1, 16))
    siemen, _ = entry_seed_apu(ids, ids)
    assert siemen["meta"]["ft_left"] == 0
    assert freeze._ft_available(siemen["meta"]) == 1


def test_liigasta_lahtenyt_on_rungossa_muttei_poolissa():
    """Mitattu tapaus: Dovin (171) entryn 15:ssa, ei poolissa."""
    ids = list(range(1, 15)) + [171]
    siemen, virhe = entry_seed_apu(ids, list(range(1, 15)), off=[171])
    assert virhe is None, virhe
    assert 171 in siemen["_off_pool"]
    lahtenyt = siemen["_off_pool"][171]
    assert lahtenyt["xp_horizon_total"] == 0.0
    assert lahtenyt["xp_per_gw"] == 0.0
    assert lahtenyt["gameweeks"] == []
    assert lahtenyt["off_pool"] is True
    # ...eika han saa olla poolissa: pool tulee kutsujalta eika siemen
    # kirjoita siihen.
    pool = _pool(list(range(1, 15)))
    assert 171 not in {p["id"] for p in pool}


def test_tuntematon_pelaaja_on_virhe():
    """Poolista JA bootstrapista puuttuva id ei saa mennä lapi hiljaa."""
    ids = list(range(1, 15)) + [999]
    siemen, virhe = entry_seed_apu(ids, list(range(1, 15)), off=[171])
    assert siemen is None and "999" in virhe


def test_vajaa_rivi_on_virhe():
    ids = list(range(1, 15))
    siemen, virhe = entry_seed_apu(ids, ids)
    assert siemen is None and "14" in virhe


def test_entryn_haku_epaonnistuu_fail_closed():
    def hae(entry, gw):
        raise entry_mod.EntryHakuVirhe("verkkovirhe")
    siemen, virhe = freeze.entry_seed(
        2, _pool(range(1, 16)), {"elements": [], "teams": []},
        hae=hae, hae_historia=_historia())
    assert siemen is None and "verkkovirhe" in virhe


def test_historian_haku_epaonnistuu_fail_closed():
    def h(entry, gw):
        return None, "entryn historiaa ei saatu"
    ids = list(range(1, 16))
    siemen, virhe = freeze.entry_seed(
        2, _pool(ids), {"elements": [], "teams": []},
        hae=_hae(ids), hae_historia=h)
    assert siemen is None and "historiaa" in virhe


# --- kytkenta ---------------------------------------------------------------

def test_reseed_on_kytketty_ennen_ketjua():
    """Portti joka on olemassa muttei kytketty on inertti. Reseedin ON
    ohitettava `_prev_freeze` KOKONAAN, ei vain entry_mismatch."""
    lahde = Path(freeze.__file__).read_text(encoding="utf-8")
    i = lahde.index("reseed, reseed_virhe = load_reseed(gw)")
    j = lahde.index("siirtotiedot = None", i)
    lohko = lahde[i:j]
    assert "entry_seed(" in lohko
    assert "_prev_freeze(gw)" in lohko
    # ...ja ketjun haara (entry_mismatch) on `else`-puolella
    assert lohko.index("entry_seed(") < lohko.index("_prev_freeze(gw)")
    assert "entry_mismatch(" in lohko


def test_reseed_nakyy_freezen_metassa():
    lahde = Path(freeze.__file__).read_text(encoding="utf-8")
    assert '"squad_source"' in lahde
    assert '"reseed": reseed_meta' in lahde


def test_gitignore_ei_niela_reseed_tiedostoa():
    """Mitattu 4.9: `/data/*` nielaisi tiedoston, jolloin CI ei olisi
    nahnyt paatosta lainkaan ja runnerin freeze olisi ottanut ketjun tien."""
    gi = (Path(freeze.__file__).resolve().parent.parent / ".gitignore"
          ).read_text(encoding="utf-8")
    assert "!/data/model_squad_reseed/" in gi
    assert "!/data/model_squad_reseed/*.json" in gi
