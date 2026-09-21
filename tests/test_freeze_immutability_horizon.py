# -*- coding: utf-8 -*-
"""FREEZE-IMMUTABILITEETIN HORISONTTI (18.9.2026).

🔴 MITATTU LOYDOS (adversariaalinen tarkistaja 18.9). Jonorivi
FREEZE-BANK-MYYNTIHINTA sanoi:

    "**VAIKUTTAA HUOMISEEN GW5-FREEZEEN** (deadline 18.9 17:30 UTC) ->
     push ennen sita tai syote on vaara."

Mitattu samana paivana: `data/model_squad_frozen/gw5.json` oli JO
origin/mainissa, `frozen_at 2026-09-17T12:18:34Z`, commit 2bba4babd, ja
`freeze_model_squad_gw.main()` kieltaytyy ylikirjoittamasta. Haaran
ensimmainen vaikutus on GW6, ei GW5. Koko kiireellisyyspremissi oli kumottu,
ja se kumoutui koska immutabiliteettia EI ollut luettavissa mistaan — se oli
yksi rivi `main()`:n sisalla (`if out.exists(): return 0`) ja jokainen muu
pinta paatteli sen kasin.

Portti (CLAUDE.md 6a.1): `freeze_status` on yksi lukija joka ei voi palauttaa
"kirjoitettava" jaadytetylle kierrokselle, `first_writable_gw` antaa sen
luvun jonka jonorivi ja raportti saavat sanoa, ja `main()` TULOSTAA
mittauksen leiman kanssa.

Hermeettinen: tmp_path-hakemisto + synteettiset eventit, ei verkkoa.
"""
from __future__ import annotations

import datetime as _dt
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UTC = _dt.timezone.utc


def _load_freeze():
    spec = importlib.util.spec_from_file_location(
        "freeze_model_squad_gw", ROOT / "scripts" / "freeze_model_squad_gw.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dl(gw: int) -> _dt.datetime:
    """GW5 = 2026-09-18 17:30Z (tuotannon oikea leima), viikko per kierros."""
    return _dt.datetime(2026, 9, 18, 17, 30, tzinfo=UTC) + _dt.timedelta(weeks=gw - 5)


def _events(gws=(4, 5, 6, 7), finished=()):
    return [{"id": g, "deadline_time": _dl(g).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "finished": g in finished} for g in gws]


def _freeze_dir(m, tmp_path, jaadytetyt=(5,), frozen_at="2026-09-17T12:18:34Z"):
    d = tmp_path / "model_squad_frozen"
    d.mkdir(parents=True)
    for g in jaadytetyt:
        (d / f"gw{g}.json").write_text(
            json.dumps({"meta": {"gw": g, "frozen_at": frozen_at}}),
            encoding="utf-8")
    m.FROZEN_DIR = d
    return d


# ---------------------------------------------------------------------------
# 1. Lukija ei voi palauttaa "kirjoitettava" jaadytetylle kierrokselle
# ---------------------------------------------------------------------------
#: Kolme vaihetta saman kierroksen ymparilla. Testi joka ajetaan vain
#: deadlinea ennen olisi vihrea siihen asti kun se lakkaa olemasta tosi.
VAIHEET = [
    ("ennen deadlinea", _dl(5) - _dt.timedelta(hours=5)),
    ("kesken kierroksen", _dl(5) + _dt.timedelta(hours=26)),
    ("gradauksen jalkeen", _dl(5) + _dt.timedelta(days=4)),
]


@pytest.mark.parametrize("vaihe,now", VAIHEET, ids=[v[0] for v in VAIHEET])
def test_jaadytetty_kierros_ei_ole_kirjoitettava_missaan_vaiheessa(
        tmp_path, vaihe, now):
    m = _load_freeze()
    _freeze_dir(m, tmp_path)
    st = m.freeze_status(5, _dl(5), now)
    assert st["writable"] is False, vaihe
    assert st["reason"] == "already_frozen"
    assert st["frozen_at"] == "2026-09-17T12:18:34Z"


def test_jaadyttamaton_kierros_on_kirjoitettava_vain_ennen_deadlinea(tmp_path):
    """Parikontrolli: ilman tata "ei kirjoitettava" voisi olla aina tosi."""
    m = _load_freeze()
    _freeze_dir(m, tmp_path)
    st = m.freeze_status(6, _dl(6), _dl(5))
    assert st["writable"] is True and st["reason"] == "ok"
    assert st["frozen_at"] is None


def test_mennyt_deadline_ilman_artefaktia_ei_ole_kirjoitettava(tmp_path):
    """Jalkifittaussuoja: kierroksen rivia ei kirjoiteta deadlinen jalkeen
    vaikka tiedostoa ei olisi. `out.exists()` yksin oli tosi vain siksi etta
    ajo sattui olemaan deadlinen etupuolella."""
    m = _load_freeze()
    _freeze_dir(m, tmp_path, jaadytetyt=())
    st = m.freeze_status(5, _dl(5), _dl(5) + _dt.timedelta(minutes=1))
    assert st["writable"] is False and st["reason"] == "deadline_passed"
    # Tasan deadlinella: FPL sulkee siirrot, joten se on jo myohassa.
    assert m.freeze_status(5, _dl(5), _dl(5))["reason"] == "deadline_passed"


def test_lukukelvoton_artefakti_on_lukossa_ei_kirjoitettava(tmp_path):
    """Fail-closed: rikkinainen JSON ei saa nayttaa puuttuvalta tiedostolta."""
    m = _load_freeze()
    d = _freeze_dir(m, tmp_path, jaadytetyt=())
    (d / "gw5.json").write_text("{ rikki", encoding="utf-8")
    st = m.freeze_status(5, _dl(5), _dl(5) - _dt.timedelta(hours=5))
    assert st["writable"] is False and st["reason"] == "already_frozen"


# ---------------------------------------------------------------------------
# 2. Se luku jonka jonorivi ja raportti saavat sanoa
# ---------------------------------------------------------------------------
def test_first_writable_gw_on_gw6_kun_gw5_on_jaadytetty(tmp_path):
    """🔴 TASAN 18.9:N TILANNE. Jonorivi sanoi GW5; mittaus sanoo GW6."""
    m = _load_freeze()
    _freeze_dir(m, tmp_path)
    now = _dl(5) - _dt.timedelta(hours=5)
    assert m.first_writable_gw(_events(), now) == 6
    # Erotteleva kontrolli: ilman jaadytettya gw5.json:ia vastaus OLISI 5,
    # eli premissi ei ole triviaalisti tosi.
    _freeze_dir(m, tmp_path / "tyhja", jaadytetyt=())
    assert m.first_writable_gw(_events(), now) == 5


def test_first_writable_gw_hyppaa_menneiden_yli(tmp_path):
    m = _load_freeze()
    _freeze_dir(m, tmp_path, jaadytetyt=(5, 6))
    assert m.first_writable_gw(_events(), _dl(5)) == 7
    assert m.first_writable_gw(_events(gws=(4, 5, 6)), _dl(5)) is None


# ---------------------------------------------------------------------------
# 3. KUTSUPAIKKA: ajo tulostaa mittauksen, ei pelkkaa "on jo jaadytetty"
# ---------------------------------------------------------------------------
class _Vastaus:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class _KiinnitettyDt:
    """`_dt`-moduulin sijainen jossa `datetime.now()` on kiinnitetty."""

    timezone = _dt.timezone
    timedelta = _dt.timedelta

    def __init__(self, nyt: _dt.datetime):
        self.datetime = type("_D", (), {
            "now": staticmethod(lambda tz=None: nyt),
            "fromisoformat": staticmethod(_dt.datetime.fromisoformat),
        })


def test_main_kertoo_leiman_ja_ensimmaisen_vaikutuskierroksen(
        tmp_path, monkeypatch, capsys):
    """Ilman `freeze_status`-kutsupaikkaa (`if out.exists(): return 0`) ajo
    tulostaa vain "GW5 on jo jaadytetty" — ja tasan siita puutteesta
    jonorivin vaara premissi syntyi. Tama testi vaatii MITTAUKSEN:
    leiman ja ensimmaisen kierroksen johon muutos voi viela vaikuttaa.
    """
    m = _load_freeze()
    _freeze_dir(m, tmp_path)
    monkeypatch.setattr(
        m, "requests",
        type("R", (), {"get": staticmethod(
            lambda *a, **kw: _Vastaus({"events": _events()}))})())
    monkeypatch.setattr(
        m, "_dt", _KiinnitettyDt(_dl(5) - _dt.timedelta(hours=5)))
    rc = m.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "already_frozen" in out
    assert "2026-09-17T12:18:34Z" in out, "leima puuttuu: vaite ei ole mitattu"
    assert "GW6" in out, "ensimmainen vaikutuskierros puuttuu"


def test_main_ei_vaiti_jaadytetysta_kun_kierros_on_avoinna(
        tmp_path, monkeypatch, capsys):
    """NEGATIIVINEN KONTROLLI: jos artefaktia ei ole, ajo EI saa tulostaa
    immutable-viestia — muuten edellinen testi lapaisisi aina. Ajo etenee
    ohi haaran ja kaatuu vasta myohemmin (tynkadata), mika on oikea merkki:
    immutabiliteetti ei pysayttanyt sita."""
    m = _load_freeze()
    _freeze_dir(m, tmp_path, jaadytetyt=())
    monkeypatch.setattr(
        m, "requests",
        type("R", (), {"get": staticmethod(
            lambda *a, **kw: _Vastaus({"events": _events()}))})())
    monkeypatch.setattr(
        m, "_dt", _KiinnitettyDt(_dl(5) - _dt.timedelta(hours=5)))
    rc = m.main()
    out = capsys.readouterr().out
    assert "already_frozen" not in out and "immutable" not in out
    assert rc == 1, "tynkadatalla ajon kuuluu kaatua, ei kirjoittaa rivia"
    assert not (tmp_path / "model_squad_frozen" / "gw5.json").exists()


# ---------------------------------------------------------------------------
# 4. Jaadytetty hitti on AIKOMUS, ei toteutunut kustannus
#
# 🔴 MITATTU 18.9: `data/model_squad_frozen/gw5.json` (immutable, frozen_at
# 2026-09-17T12:18:34Z) kantaa `meta.hits: 1` ja `meta.ft_available: 1`, eli
# mallin GW5-rivi ottaa -4:n. FPL:n oma saldo samalle kierrokselle mitattiin
# entryn historiasta: `free_transfers_for_gw(hist, 5) == 3` (entry 116920,
# `event_transfers` [0,0,0,0], wildcard GW2) -> kaksi siirtoa ilman hittia.
# Hitti on siis VIRHEELLINEN AIKOMUS lukitussa artefaktissa, eika sita voi
# korjata: freeze on immutable ja `main()` kieltaytyy ylikirjoittamasta.
# Se mita SAA varmistaa on, ettei yksikaan pinta esita sita TOTEUTUNEENA
# kustannuksena. Toteutunut kustannus tulee FPL:n omasta
# `event_transfers_cost`ista (mallin oma entry), ei freezen `hits`ista.
# ---------------------------------------------------------------------------
KUSTANNUSKENTTA = re.compile(r'"transfer_cost"\s*:')
FPL_OMA_KENTTA = "event_transfers_cost"

#: Tiedosto paasee tanne VAIN perustelun kanssa (CLAUDE.md 6a.2). Uusi
#: tiedosto joka kirjoittaa `transfer_cost`in ilman FPL:n omaa kenttaa
#: kaataa taman testin, ja kirjoittaja joutuu kirjoittamaan miksi.
KUSTANNUS_POIKKEUKSET = {
    "scripts/build_gw_recap.py":
        "Lapivienti, ei johdos: lukee valmiin rivin accuracy-lokista, jonka "
        "`transfer_cost`in on kirjoittanut grade_model_squad.py FPL:n "
        "`event_transfers_cost`ista.",
    "src/models/model_squad_scores.py":
        "Lapivienti julkiseen mallisarjaan (21.9.2026, Villen paatos 'mallin "
        "rivi'), ei johdos: jaadytetyn rivin `transfer_cost` on "
        "grade_model_squad_gw.py:n kirjoittama, ja se lukee FPL:n "
        "`event_transfers_cost`in aina kun jaadytetty 15 on entryn 15 "
        "(`transfer_cost_source: fpl_entry_same_squad`). Muuten lahde on "
        "`freeze_hits` ja se kulkee rivin mukana nakyvana, jotta pinta voi "
        "kertoa etta luku on mallin oma aikomus eika FPL:n veloitus. "
        "Entry-fallback-rivi kantaa entry-graderin FPL-kentan sellaisenaan.",
}


def test_julkaistu_siirtokustannus_tulee_fpln_omasta_kentasta():
    loydot = []
    for hakemisto in ("src/models", "scripts"):
        for f in sorted((ROOT / hakemisto).glob("*.py")):
            teksti = f.read_text(encoding="utf-8", errors="replace")
            if not KUSTANNUSKENTTA.search(teksti):
                continue
            rel = f"{hakemisto}/{f.name}"
            if FPL_OMA_KENTTA in teksti:
                continue
            if rel in KUSTANNUS_POIKKEUKSET:
                assert len(KUSTANNUS_POIKKEUKSET[rel]) > 40, rel
                continue
            loydot.append(rel)
    assert not loydot, (
        "nama kirjoittavat julkaistun `transfer_cost`in lukematta FPL:n omaa "
        f"`{FPL_OMA_KENTTA}`-kenttaa: {loydot}. Jaadytetyn freezen `meta.hits` "
        "on AIKOMUS, ei toteutunut kustannus (GW5 18.9: freeze -4, FPL 0).")


def test_poikkeuslista_ei_kanna_kuolleita_riveja():
    """Poikkeus joka ei enaa vastaa mitaan tiedostoa on perustelu jota kukaan
    ei lue. Se poistetaan, ei jateta roikkumaan."""
    for rel in KUSTANNUS_POIKKEUKSET:
        assert (ROOT / rel).exists(), rel
