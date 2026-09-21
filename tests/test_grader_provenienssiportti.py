# -*- coding: utf-8 -*-
"""Jaadytetty graderi: mika on mallin rivi ja mika ei (21.9.2026, Villen paatos).

HISTORIA. 12.9 Villen paatos oli etta julkinen sarja on ENTRY-sarja, ja
tama graderi kieltaytyi gradaamasta runkoa jota ei ollut todistettu entryn
rungoksi (`require_entry_provenance`). 21.9 paatos kaantyi: julkinen track
record mittaa MALLIN JAADYTETTYA rivia, koska 18.9 Ville ajoi GW5:n rivin
yli ja entry-sarja mittasi silloin mallin ja Villen yhdistelmaa.

UUSI SAANTO, rakenteena:
  * Kelvollinen freeze gradataan MYOS kun entry poikkeaa siita. Ero
    kirjataan riville (`entry_diverged`, `entry_diff`).
  * Rakenteellisesti epakelpo freeze (`squad_rebuilt: true` = putosi
    vapaaseen optimiin; mitattu gw4.json 12.9: 8/15 vaihtui, transfers [])
    EI gradaudu. Se ei ole mallin saavutettava rivi. Julkinen lukija
    kayttaa kierrokselle entrya vain jos poikkeuspaatos on kirjattu.
  * Entryn rivia ei saatu luettua -> kierros jaa seuraavaan ajoon, koska
    loki on append-only eika mittaamatonta eroa kirjoiteta pysyvasti.
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


def _runko(gw, *, squad_source="chain", from_gw=None, verified=None,
           rebuilt=None, hits=0, transfers=0):
    d = {
        "meta": {"gw": gw, "squad_source": squad_source, "from_gw": from_gw,
                 "frozen_at": f"2026-09-0{gw}T07:00:00Z",
                 "deadline": f"2026-09-0{gw}T17:30:00Z",
                 "transfers": [{"out": 90 + i, "in": 95 + i}
                               for i in range(transfers)],
                 "hits": hits},
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
    if rebuilt is not None:
        d["meta"]["squad_rebuilt"] = rebuilt
    return d


def _verifioitu(gw):
    return {"gw": gw, "entry": 116920, "at": "2026-09-05T13:11:21Z",
            "squad_match": True, "captain_match": True, "common": 15,
            "match": True}


def _picks(xi_vaihto=None, kapteeni=1, kustannus=0, chip=None):
    """Entryn pickit. `xi_vaihto=(ulos, sisaan)` siirtaa penkilta XI:hin."""
    xi = list(range(1, 12))
    bench = list(range(12, 16))
    if xi_vaihto:
        ulos, sisaan = xi_vaihto
        xi[xi.index(ulos)] = sisaan
        bench[bench.index(sisaan)] = ulos
    jarj = xi + bench
    return {"picks": [{"element": e, "position": i + 1,
                       "is_captain": e == kapteeni,
                       "is_vice_captain": e == 2,
                       "multiplier": 1} for i, e in enumerate(jarj)],
            "entry_history": {"event_transfers_cost": kustannus},
            "active_chip": chip}


class _R:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._p


#: Entryn historia kuten FPL sen antaa (mitattu 116920: GW1-4 nolla siirtoa,
#: wildcard GW2). FT-saldo lasketaan testissa samalla lukijalla kuin
#: graderissa, eika sita kovakoodata.
HISTORIA = {"current": [{"event": g, "event_transfers": 0,
                         "event_transfers_cost": 0} for g in range(1, 5)],
            "chips": [{"name": "wildcard", "event": 2}]}


def _aja(monkeypatch, tmp_path, rungot, *, ratkennut=True, picks=None,
         picks_status=200, historia=None, historia_status=200):
    m = _graderi()
    for gw, r in rungot.items():
        (tmp_path / f"gw{gw}.json").write_text(
            json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8", newline="\n")
    loki = tmp_path / "scores.json"
    monkeypatch.setattr(m, "FROZEN_DIR", tmp_path)
    monkeypatch.setattr(m, "LOG_PATH", loki)

    def _get(url, **kw):
        if "bootstrap-static" in url:
            return _R({"events": [{"id": g, "finished": ratkennut,
                                   "data_checked": ratkennut,
                                   "average_entry_score": 50}
                                  for g in rungot]})
        if "/picks/" in url:
            return _R(picks if picks is not None else _picks(),
                      status=picks_status)
        if "/history/" in url:
            return _R(historia if historia is not None else HISTORIA,
                      status=historia_status)
        return _R({"elements": [{"id": i, "stats": {"total_points": 5,
                                                    "minutes": 90}}
                                for i in range(1, 16)]})

    monkeypatch.setattr(m.requests, "get", _get)
    rc = m.main()
    tallennettu = (json.loads(loki.read_text(encoding="utf-8"))
                   if loki.exists() else None)
    return rc, tallennettu


def _rivi(loki, gw):
    return next(r for r in loki["gameweeks"] if r["gw"] == gw)


# --- 1. epakelpo freeze ei ole mallin rivi --------------------------------

def test_epakelpo_freeze_ei_gradaudu(monkeypatch, tmp_path, capsys):
    """🔴 gw4:n muoto: myohempi freeze joka putosi vapaaseen optimiin."""
    rc, loki = _aja(monkeypatch, tmp_path,
                    {3: _runko(3, verified=_verifioitu(3)),
                     4: _runko(4, rebuilt=True)})
    out = capsys.readouterr().out
    assert rc == 0, "kieltaytyminen ei ole virhe"
    assert [r["gw"] for r in loki["gameweeks"]] == [3], (
        "epakelpo freeze KIRJATTIIN append-only-lokiin mallin rivina")
    assert "::warning::" in out and "EI GRADATA" in out
    assert "unscored-listaan" in out and "entryn lukua" in out
    # 21.9 Villen paatos: luku kirjataan DIAGNOSTISESTI omaan listaansa.
    u = loki["unscored"]
    assert [x["gw"] for x in u] == [4]
    assert u[0]["code"] == "no_valid_frozen_squad"
    assert u[0]["would_have_scored"] == 5 * 11 + 5, "11 x 5 p + kapteeni"
    assert u[0]["fpl_average"] == 50


def test_kauden_ensimmainen_vapaa_optimi_on_kelvollinen(monkeypatch, tmp_path):
    """Negatiivinen kontrolli: kauden ensimmainen freeze on vapaa optimi
    luonnostaan (ei edellista runkoa). Sita ei saa hylata."""
    rc, loki = _aja(monkeypatch, tmp_path,
                    {1: _runko(1, squad_source="free_optimum", rebuilt=True)})
    assert rc == 0 and [r["gw"] for r in loki["gameweeks"]] == [1]


# --- 2. kelvollinen freeze gradataan vaikka entry poikkeaa ----------------

def test_verifioimaton_kelvollinen_runko_gradataan(monkeypatch, tmp_path):
    """🔴 Ydinmuutos: ennen tama rivi jai gradaamatta (GW1, GW2 levylla).
    Mallin oma rivi on julkinen sarja, joten se gradataan."""
    rc, loki = _aja(monkeypatch, tmp_path, {2: _runko(2, from_gw=1)})
    r = _rivi(loki, 2)
    assert r["source"] == "frozen_squad" and r["points"] > 0
    assert r["provenance"] == "frozen_only"
    assert r["entry_diverged"] is False


def test_entry_poikkeaa_rivi_gradataan_ja_ero_kirjataan(monkeypatch, tmp_path,
                                                        capsys):
    """GW5:n tapaus: sama 15 ja kapteeni, eri XI (P13 penkilta P11:n tilalle)."""
    rc, loki = _aja(monkeypatch, tmp_path,
                    {5: _runko(5, squad_source="entry_picks", from_gw=4)},
                    picks=_picks(xi_vaihto=(11, 13)))
    r = _rivi(loki, 5)
    assert r["entry_diverged"] is True
    assert r["entry_diff"]["xi_only_frozen"] == [11]
    assert r["entry_diff"]["xi_only_entry"] == [13]
    assert r["entry_diff"]["common"] == 15 and r["entry_diff"]["captain_match"]
    # Pisteet ovat JAADYTETYN XI:n, eivat entryn.
    assert 11 in r["xi_ids"] and 13 not in r["xi_ids"]
    assert "entry poikkesi" in capsys.readouterr().out


def test_verifioitu_runko_gradataan(monkeypatch, tmp_path):
    rc, loki = _aja(monkeypatch, tmp_path,
                    {3: _runko(3, verified=_verifioitu(3))})
    rivi = _rivi(loki, 3)
    assert rivi["provenance"] == "entry_verified"
    assert rivi["source"] == "frozen_squad"


def test_reseed_runko_gradataan(monkeypatch, tmp_path):
    rc, loki = _aja(monkeypatch, tmp_path,
                    {3: _runko(3, squad_source="entry_picks")})
    assert _rivi(loki, 3)["provenance"] == "entry_picks"


# --- 3. siirtokustannus FPL:n saannoilla ------------------------------------

def test_gw2_kolme_siirtoa_on_kahdeksan_fpln_saannolla(monkeypatch, tmp_path):
    """Mitattu 21.9: GW2:n jaadytetty rivi teki 3 siirtoa GW1-rungosta, ja
    FT-saldo GW2:lle on 1 kaikilla (GW1 rajaton) -> (3 - 1) x 4 = 8."""
    rc, loki = _aja(monkeypatch, tmp_path,
                    {2: _runko(2, from_gw=1, hits=2, transfers=3)},
                    picks=_picks(chip="wildcard"))
    r = _rivi(loki, 2)
    assert r["transfer_cost"] == 8 and r["transfer_cost_source"] == "fpl_rules_gw2"


def test_reseed_kayttaa_fpln_saldoa_ei_freezen_laskuria(monkeypatch, tmp_path):
    """GW5 mitattu: freeze sanoi 1 hitti (-4), mutta reseed perii entryn
    saldon, ja FPL:n oma saldo historiasta oli 3 -> 2 siirtoa = 0."""
    from src.models.fpl_entry_history import free_transfers_for_gw
    ft = free_transfers_for_gw(HISTORIA, 5)
    assert ft is not None and ft >= 2, "fikstuurin on oltava erotteleva"
    rc, loki = _aja(monkeypatch, tmp_path,
                    {5: _runko(5, squad_source="entry_picks", hits=1,
                               transfers=2)})
    r = _rivi(loki, 5)
    assert r["transfer_cost"] == 0
    assert r["transfer_cost_source"] == "fpl_rules_entry_ft"


def test_yksi_siirto_on_aina_ilmainen(monkeypatch, tmp_path):
    rc, loki = _aja(monkeypatch, tmp_path,
                    {6: _runko(6, from_gw=5, hits=1, transfers=1)})
    r = _rivi(loki, 6)
    assert r["transfer_cost"] == 0
    assert r["transfer_cost_source"] == "one_transfer_always_free"


def test_ketjun_monta_siirtoa_on_todentamaton_ei_arvattu(monkeypatch, tmp_path):
    """Ketju jatkui mallin omilla siirroilla: sen FT-laskuri on mitattu
    vaaraksi, eika entryn saldo ole mallin saldo -> None (brutto +
    nakyva merkinta), ei freezen omaa hittia."""
    rc, loki = _aja(monkeypatch, tmp_path,
                    {6: _runko(6, from_gw=5, hits=1, transfers=2)})
    r = _rivi(loki, 6)
    assert r["transfer_cost"] is None
    assert r["transfer_cost_source"] == "unverified"


def test_lukematon_historia_jattaa_reseed_kierroksen_seuraavaan_ajoon(
        monkeypatch, tmp_path, capsys):
    rc, loki = _aja(monkeypatch, tmp_path,
                    {5: _runko(5, squad_source="entry_picks", transfers=2)},
                    historia_status=503)
    assert rc == 0 and loki is None
    assert "seuraavaan ajoon" in capsys.readouterr().out


# --- 4. vaiheet --------------------------------------------------------------

def test_ratkeamaton_kierros_ei_gradata(monkeypatch, tmp_path, capsys):
    """Vaihe: kesken oleva kierros. Ratkeamisehto ensin, ei huutoa
    epakelpoudesta eika tyhjaa lokia."""
    rc, loki = _aja(monkeypatch, tmp_path, {4: _runko(4, rebuilt=True)},
                    ratkennut=False)
    out = capsys.readouterr().out
    assert rc == 0 and loki is None
    assert "ei vielä ratkennut" in out
    assert "EI GRADATA" not in out


def test_lukematon_entry_jattaa_kierroksen_seuraavaan_ajoon(monkeypatch,
                                                            tmp_path, capsys):
    """Append-only: mittaamatonta eroa ei kirjata pysyvasti."""
    rc, loki = _aja(monkeypatch, tmp_path, {3: _runko(3)}, picks_status=503)
    assert rc == 0 and loki is None
    assert "seuraavaan ajoon" in capsys.readouterr().out


def test_graderi_ei_enaa_kayta_provenienssia_porttina():
    """Kutsupaikka: `require_entry_provenance` saa olla lahteessa vain
    tietona (except -> frozen_only), ei `continue`-porttina. Kommentit
    poistettu ennen etsintaa (muisti 12.9)."""
    src = (ROOT / "scripts" / "grade_model_squad_gw.py").read_text(
        encoding="utf-8")
    koodi = "\n".join(r.split("#", 1)[0] for r in src.split("\n"))
    assert "freeze_invalid(" in koodi
    i = koodi.index("except ProvenienssiPuuttuu")
    assert "continue" not in koodi[i:i + 200], (
        "provenienssi on taas portti: mallin oma rivi jaisi gradaamatta")


def test_repon_gw4_on_epakelpo():
    """🔴 Elava tila: oikea gw4.json on epakelpo freeze. Jos tama kaatuu,
    joko rivi on korjattu tai saanto on rikki - kumpikin on syyta tietaa."""
    from src.models.model_squad_scores import freeze_invalid
    gw4 = ROOT / "data" / "model_squad_frozen" / "gw4.json"
    if not gw4.exists():
        pytest.skip("gw4.json puuttuu")
    assert freeze_invalid(json.loads(gw4.read_text(encoding="utf-8")),
                          earlier_exists=True)


def test_diagnostiikka_on_idempotentti(monkeypatch, tmp_path):
    """Append-only: toinen ajo ei kirjaa GW4:aa uudelleen."""
    rungot = {3: _runko(3, verified=_verifioitu(3)), 4: _runko(4, rebuilt=True)}
    _aja(monkeypatch, tmp_path, rungot)
    rc, loki = _aja(monkeypatch, tmp_path, rungot)
    assert [x["gw"] for x in loki["unscored"]] == [4]
