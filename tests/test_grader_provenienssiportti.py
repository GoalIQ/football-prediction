# -*- coding: utf-8 -*-
"""Graderi ei gradaa runkoa jonka provenienssi puuttuu (12.9.2026, Villen paatos).

🔴 MITATTU. `data/model_squad_frozen/gw4.json` on runko jossa 8/15 vaihtui ja
jonka meta sanoo `transfers: []`, `hits: 0` — runko jota malli ei voi
saavuttaa yhdellakaan sallitulla siirtomaaralla. `provenance(gw4)` palauttaa
`None`, ja **korttigeneraattori kieltaytyy** renderoimasta sita
(`require_entry_provenance`). Sama portti puuttui graderilta: se olisi
gradannut rungon jonka oma meta sanoo `squad_match: false`.

Villen paatos: GW4 gradataan ENTRYSTA, kuten GW1-GW3 tosiasiassa on gradattu
(`data/model_squad_gw_scores.json`:n rivit kantavat `active_chip` ja
`transfer_cost`, eli ne tulevat `grade_model_squad.py`:sta).

🔴 MIKSI PORTTI EIKA PELKKA PAATOS. Ilman porttia paatos jaa cron-jarjestyksen
varaan: entry-putki (`model-squad-grade.yml`, cron `17 */6`) ehtii
normaalitilassa ensin, ja silloin tama graderi ohittaa GW4:n koska `done`
sisaltaa sen. Mutta jos entry-putki kaatuu (ADMIN_TOKEN, 502, punainen ajo),
tama graderi saa vuoron ja kirjaa vaaran rungon pisteet **append-only**-lokiin
peruuttamattomasti. Portti tekee paatoksesta rakenteen: vaara vaihtoehto on
mahdoton riippumatta siita kumpi putki ehtii.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _graderi():
    spec = importlib.util.spec_from_file_location(
        "grade_model_squad_gw", ROOT / "scripts" / "grade_model_squad_gw.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _runko(gw, *, squad_source="chain", from_gw=None, verified=None):
    d = {
        "meta": {"gw": gw, "squad_source": squad_source, "from_gw": from_gw,
                 "frozen_at": f"2026-09-0{gw}T07:00:00Z",
                 "deadline": f"2026-09-0{gw}T17:30:00Z",
                 "transfers": [], "hits": 0},
        "captain": 1, "vice_captain": 2,
        "xi": [{"id": i, "web_name": f"P{i}", "pos": (1 if i == 1 else
                                                      2 if i <= 5 else
                                                      3 if i <= 9 else 4),
                "price": 50, "club": i} for i in range(1, 12)],
        "bench": [{"id": i, "web_name": f"P{i}",
                   "pos": (1 if i == 12 else 2 if i == 13 else 3),
                   "price": 45, "club": i} for i in range(12, 16)],
    }
    if verified is not None:
        d["meta"]["entry_verified"] = verified
    return d


def _verifioitu(gw):
    return {"gw": gw, "entry": 116920, "at": "2026-09-05T13:11:21Z",
            "squad_match": True, "captain_match": True, "common": 15,
            "match": True}


def _aja(monkeypatch, tmp_path, rungot, *, ratkennut=True):
    m = _graderi()
    for gw, r in rungot.items():
        (tmp_path / f"gw{gw}.json").write_text(
            json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8", newline="\n")
    loki = tmp_path / "scores.json"
    monkeypatch.setattr(m, "FROZEN_DIR", tmp_path)
    monkeypatch.setattr(m, "LOG_PATH", loki)

    class _R:
        def __init__(self, payload):
            self._p = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._p

    def _get(url, **kw):
        if "bootstrap-static" in url:
            return _R({"events": [{"id": g, "finished": ratkennut,
                                   "data_checked": ratkennut,
                                   "average_entry_score": 50}
                                  for g in rungot]})
        return _R({"elements": [{"id": i, "stats": {"total_points": 5,
                                                    "minutes": 90}}
                                for i in range(1, 16)]})

    monkeypatch.setattr(m.requests, "get", _get)
    rc = m.main()
    tallennettu = (json.loads(loki.read_text(encoding="utf-8"))
                   if loki.exists() else None)
    return rc, tallennettu


def test_provenienssi_puuttuu_ei_gradata(monkeypatch, tmp_path, capsys):
    """🔴 Ydintesti: gw4:n muotoinen runko (chain, from_gw None, ei verifiointia)."""
    rc, loki = _aja(monkeypatch, tmp_path, {4: _runko(4)})
    out = capsys.readouterr().out
    assert rc == 0, "kieltaytyminen ei ole virhe, se on kieltaytyminen"
    assert loki is None, (
        "runko jonka provenienssi puuttuu KIRJATTIIN append-only-lokiin — "
        "vaara luku season raceen peruuttamattomasti")
    assert "::warning::" in out and "EI GRADATA" in out
    assert "grade_model_squad.py" in out, "ohjeen on kerrottava mika gradaa"


def test_verifioitu_runko_gradataan(monkeypatch, tmp_path):
    """Negatiivinen kontrolli: portti ei saa estaa kaikkea."""
    rc, loki = _aja(monkeypatch, tmp_path,
                    {3: _runko(3, verified=_verifioitu(3))})
    assert rc == 0 and loki is not None, "verifioitu runko jai gradaamatta"
    rivi = loki["gameweeks"][0]
    assert rivi["gw"] == 3 and rivi["points"] > 0
    assert rivi["provenance"] == "entry_verified"
    assert rivi["source"] == "frozen_squad", (
        "provenienssi ei nay rivilla -> sekaprovenienssia ei voi havaita")


def test_reseed_runko_gradataan(monkeypatch, tmp_path):
    """`entry_picks` on oma peruste: rivi TULEE entryn pickeista."""
    rc, loki = _aja(monkeypatch, tmp_path,
                    {3: _runko(3, squad_source="entry_picks")})
    assert loki is not None and loki["gameweeks"][0]["provenance"] == "entry_picks"


def test_ratkeamaton_kierros_ei_gradata_eika_valita_provenienssista(
        monkeypatch, tmp_path, capsys):
    """Jarjestys: ratkeamisehto ensin. Ilman tata portti huutaisi
    provenienssista kierroksista joita ei viela pelata."""
    rc, loki = _aja(monkeypatch, tmp_path, {4: _runko(4)}, ratkennut=False)
    out = capsys.readouterr().out
    assert rc == 0 and loki is None
    assert "ei vielä ratkennut" in out
    assert "EI GRADATA" not in out


def test_portti_on_kytketty_lahteessa():
    """Lisavarmistus: kutsu on olemassa, kommentit poistettu ennen etsintaa
    (muisti 12.9: merkkijonoportti osui omaan perustelukommenttiinsa)."""
    src = (ROOT / "scripts" / "grade_model_squad_gw.py").read_text(
        encoding="utf-8")
    koodi = "\n".join(r.split("#", 1)[0] for r in src.split("\n"))
    assert "require_entry_provenance" in koodi
    assert "ProvenienssiPuuttuu" in koodi


def test_repon_gw4_ei_lapaise_porttia():
    """🔴 Elava tila: oikea gw4.json EI saa lapaista. Jos tama kaatuu,
    joko rivi on korjattu tai portti on rikki — kumpikin on syyta tietaa."""
    from src.models.fpl_model_entry import (ProvenienssiPuuttuu,
                                            require_entry_provenance)
    frozen_dir = ROOT / "data" / "model_squad_frozen"
    gw4 = frozen_dir / "gw4.json"
    if not gw4.exists():
        pytest.skip("gw4.json puuttuu")
    with pytest.raises(ProvenienssiPuuttuu):
        require_entry_provenance(
            json.loads(gw4.read_text(encoding="utf-8")), frozen_dir)
