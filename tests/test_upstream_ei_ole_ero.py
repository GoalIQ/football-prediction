"""Upstream-hairio ei saa nayttaa mitatulta erolta (12.9.2026).

🔴 MITTAUS JOKA SYNNYTTI TAMAN. `fpl-data-refresh` oli punainen kolme
perakkaista ajoa (11:42, 12:30, 12:49 UTC). Kaksi askelta kaatui, molemmat
samasta syysta: **FPL vastasi GH-runnerille HTTP 503.** Paikallisesti sama
API vastasi 200 samalla minuutilla.

Kumpikaan askel ei sanonut sita:

  verify_model_entry_matches_freeze
    "Entryn 116920 GW4-rivi ei ole luettavissa (HTTP 503) vaikka deadline on
     mennyt. Joko tilia ei ole pelattu tassa kierroksessa tai entry-id on
     vaara."  -> kumpikaan vaihtoehto ei ollut totta.
    Step health kaansi sen viela muotoon "FPL-entry EI VASTAA jaadytettya
    runkoa ... kirjaa poikkeus data/model_squad_exceptions/gw{N}.json".
    Poikkeus olisi valkolistannut eron jota ei ollut mitattu, pysyvasti.

  build_founder_stats
    paljas urllib.error.HTTPError -traceback, vaikka askelen kommentti
    workflow'ssa lupasi "fail-safe: jos FPL-API on nurin, askel ei kaada
    ajoa". Lupaus koski vain sanitya.

Invariantti: **"en saanut luettua" ei ole "ei tasmaa"** (muisti
`nolla-ei-ole-sama-kuin-ei-tietoa`, `selitys-nimeaa-vaaran-mekanismin`).
Ja koska hiljainen fail-open jaatyy alavirtaan, molemmilla on ikaraja jonka
jalkeen se on oma vikansa.
"""
from __future__ import annotations

import datetime as _dt
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _mod(nimi: str):
    spec = importlib.util.spec_from_file_location(
        nimi, ROOT / "scripts" / f"{nimi}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _Vastaus:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("ei JSONia")
        return self._payload


# ---------------------------------------------------------------------------
# verify_model_entry_matches_freeze.fetch_picks — kolme tilaa
# ---------------------------------------------------------------------------
def test_503_on_unreachable_ei_not_played(monkeypatch):
    v = _mod("verify_model_entry_matches_freeze")
    kutsut = []
    monkeypatch.setattr(v.requests, "get",
                        lambda *a, **k: kutsut.append(1) or _Vastaus(503))
    picks, status, kind = v.fetch_picks(1, 4, sleep=lambda _s: None)
    assert kind == "unreachable"
    assert picks is None and "503" in status
    assert len(kutsut) == v.RETRIES, "transientti pitaa yrittaa uudelleen"


def test_404_on_not_played(monkeypatch):
    v = _mod("verify_model_entry_matches_freeze")
    kutsut = []
    monkeypatch.setattr(v.requests, "get",
                        lambda *a, **k: kutsut.append(1) or _Vastaus(404))
    _, status, kind = v.fetch_picks(1, 4, sleep=lambda _s: None)
    assert kind == "not_played" and status == "404"
    assert len(kutsut) == 1, "404 on aito vastaus, ei yriteta uudelleen"


def test_verkkovirhe_on_unreachable(monkeypatch):
    v = _mod("verify_model_entry_matches_freeze")

    def kaatuu(*a, **k):
        raise OSError("connection reset")

    monkeypatch.setattr(v.requests, "get", kaatuu)
    _, _, kind = v.fetch_picks(1, 4, sleep=lambda _s: None)
    assert kind == "unreachable"


def test_ensimmainen_yritys_onnistuu_ei_odota(monkeypatch):
    """Negatiivinen kontrolli: retry ei saa hidastaa onnistunutta polkua."""
    v = _mod("verify_model_entry_matches_freeze")
    nukuttu = []
    monkeypatch.setattr(v.requests, "get",
                        lambda *a, **k: _Vastaus(200, {"picks": [{"element": 1}]}))
    picks, status, kind = v.fetch_picks(1, 4, sleep=lambda s: nukuttu.append(s))
    assert kind == "ok" and picks == [{"element": 1}] and not nukuttu


# ---------------------------------------------------------------------------
# main(): unreachable -> varoitus, ei virhe, ei poikkeuskehotusta
# ---------------------------------------------------------------------------
def _freeze_tiedosto(tmp_path, gw, deadline, *, verified=None):
    d = {"meta": {"gw": gw, "deadline": deadline,
                  "frozen_at": "2026-09-11T07:45:25Z"},
         "captain": 1,
         "xi": [{"id": i} for i in range(1, 12)],
         "bench": [{"id": i} for i in range(12, 16)]}
    if verified:
        d["meta"]["entry_verified"] = verified
    p = tmp_path / f"gw{gw}.json"
    p.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n",
                 encoding="utf-8")
    return p


def _aja_main(v, monkeypatch, tmp_path, *, tuntia_deadlinesta, verified=None,
              status=503):
    now = _dt.datetime(2026, 9, 12, 12, 30, tzinfo=_dt.timezone.utc) + \
        _dt.timedelta(hours=tuntia_deadlinesta)
    _freeze_tiedosto(tmp_path, 4, "2026-09-12T12:30:00Z", verified=verified)
    monkeypatch.setattr(v, "FROZEN_DIR", tmp_path)
    monkeypatch.setattr(v.requests, "get", lambda *a, **k: _Vastaus(status))
    monkeypatch.setattr(v.time if hasattr(v, "time") else v, "__name__",
                        getattr(v, "__name__", "v"), raising=False)

    class _Kello(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(v._dt, "datetime", _Kello)
    monkeypatch.setattr(v, "RETRY_SLEEP_S", (0, 0, 0))
    monkeypatch.setattr("sys.argv", ["verify"])
    return v.main()


def test_503_pian_deadlinen_jalkeen_on_varoitus(monkeypatch, tmp_path, capsys):
    v = _mod("verify_model_entry_matches_freeze")
    rc = _aja_main(v, monkeypatch, tmp_path, tuntia_deadlinesta=0.5)
    out = capsys.readouterr().out
    assert rc == 0, "transientti 503 ei saa punastaa koko refreshia"
    assert "::warning::" in out and "::error::" not in out
    assert "poikkeus" not in out.lower() or "ALA kirjaa" in out, (
        "operaattoria ei saa kehottaa valkolistaamaan mittaamatonta eroa")
    assert "EI ero" in out


def test_503_yli_vuorokauden_on_virhe(monkeypatch, tmp_path, capsys):
    """Fail-open on ajallisesti rajattu. Ilman tata vahti voisi olla
    ajamatta kierroksen yli eika mikaan huutaisi."""
    v = _mod("verify_model_entry_matches_freeze")
    rc = _aja_main(v, monkeypatch, tmp_path, tuntia_deadlinesta=30)
    out = capsys.readouterr().out
    assert rc == 1 and "::error::" in out
    assert "ALA kirjaa poikkeusta" in out


def test_jos_kierros_on_jo_verifioitu_ei_eskaloida(monkeypatch, tmp_path, capsys):
    """Kertaalleen mitattu kierros ei muutu virheeksi siksi etta myohempi
    ajo ei saa yhteytta — mittaus on jo tehty."""
    v = _mod("verify_model_entry_matches_freeze")
    rc = _aja_main(v, monkeypatch, tmp_path, tuntia_deadlinesta=48,
                   verified={"gw": 4, "entry": 1, "at": "2026-09-12T13:00:00Z",
                             "squad_match": True, "captain_match": True,
                             "common": 15, "match": True})
    assert rc == 0
    assert "::warning::" in capsys.readouterr().out


def test_ennen_deadlinea_ei_kutsuta_fplaa(monkeypatch, tmp_path, capsys):
    v = _mod("verify_model_entry_matches_freeze")
    rc = _aja_main(v, monkeypatch, tmp_path, tuntia_deadlinesta=-3)
    assert rc == 0
    assert "Deadlineen" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# record_verification: sarjallistus sailyy
# ---------------------------------------------------------------------------
def test_verifiointimerkinta_ei_reformatoi_artefaktia(tmp_path):
    """🔴 Ilman tata yhden metakentan lisays nayttaa gitissa koko rungon
    uudelleenkirjoitukselta, ja "todistettavissa git-historiasta" menettaa
    merkityksensa. Mitattu 12.9: paikallinen ajo tuotti tasan sen diffin."""
    v = _mod("verify_model_entry_matches_freeze")
    p = _freeze_tiedosto(tmp_path, 4, "2026-09-12T12:30:00Z")
    ennen = p.read_text(encoding="utf-8")
    frozen = json.loads(ennen)
    v.record_verification(p, frozen, 4, squad_match=False, captain_match=True,
                          common=7,
                          now=_dt.datetime(2026, 9, 12, 13, 18,
                                           tzinfo=_dt.timezone.utc))
    jalkeen = p.read_text(encoding="utf-8")
    assert jalkeen.endswith("\n"), "rivinvaihto ei saa kadota"
    assert '", "' not in jalkeen, "erottimien jalkeen ei saa tulla valilyonteja"
    # Rivi itse on koskematon: kaikki paitsi entry_verified sailyy sanatarkasti.
    a, b = json.loads(ennen), json.loads(jalkeen)
    b["meta"].pop("entry_verified")
    assert a == b


# ---------------------------------------------------------------------------
# build_founder_stats: transientti ei punasta, mutta ei myoskaan jaadyta
# ---------------------------------------------------------------------------
def _founder(monkeypatch, tmp_path, *, ika_h=None):
    f = _mod("build_founder_stats")
    out = tmp_path / "founder_entry.json"
    if ika_h is not None:
        t = _dt.datetime.now() - _dt.timedelta(hours=ika_h)
        out.write_text(json.dumps({"generated_at": t.strftime("%Y-%m-%dT%H:%M:%S"),
                                   "seasons": 12}), encoding="utf-8")
    monkeypatch.setattr(f, "OUT_PATH", out)
    monkeypatch.setattr(f, "RETRY_SLEEP_S", (0, 0, 0))
    return f, out


def test_founder_503_tuore_artefakti_ei_kaada(monkeypatch, tmp_path):
    f, out = _founder(monkeypatch, tmp_path, ika_h=2)
    monkeypatch.setattr(f, "fetch", lambda: (_ for _ in ()).throw(
        OSError("HTTP Error 503: Service Unavailable")))
    payload, syy = f.fetch_retry(sleep=lambda _s: None)
    assert payload is None and "503" in syy
    assert f.artefaktin_ika_h(out) < f.STALE_ESCALATE_H


def test_founder_503_vanha_artefakti_ylittaa_rajan(monkeypatch, tmp_path):
    f, out = _founder(monkeypatch, tmp_path, ika_h=40)
    assert f.artefaktin_ika_h(out) >= f.STALE_ESCALATE_H, (
        "yli 36 h vanha luku etusivulla ei ole enaa ohimeneva hairio")


def test_founder_ilman_artefaktia_ika_on_none(monkeypatch, tmp_path):
    f, out = _founder(monkeypatch, tmp_path)
    assert f.artefaktin_ika_h(out) is None


def test_founder_retry_yrittaa_kolmesti(monkeypatch, tmp_path):
    f, _ = _founder(monkeypatch, tmp_path)
    kutsut = []

    def kaatuu():
        kutsut.append(1)
        raise OSError("503")

    monkeypatch.setattr(f, "fetch", kaatuu)
    f.fetch_retry(sleep=lambda _s: None)
    assert len(kutsut) == f.RETRIES


def test_founder_onnistuminen_ei_odota(monkeypatch, tmp_path):
    f, _ = _founder(monkeypatch, tmp_path)
    nukuttu = []
    monkeypatch.setattr(f, "fetch", lambda: {"past": []})
    payload, syy = f.fetch_retry(sleep=lambda s: nukuttu.append(s))
    assert payload == {"past": []} and syy == "ok" and not nukuttu


def test_ika_luetaan_generated_atista_ei_mtimesta(monkeypatch, tmp_path):
    """CI:n checkout antaa jokaiselle tiedostolle checkout-hetken, joten
    mtime kertoisi runnerista eika datasta."""
    f, out = _founder(monkeypatch, tmp_path, ika_h=40)
    out.touch()                       # mtime = nyt, sisalto 40 h vanha
    assert f.artefaktin_ika_h(out) >= 39


# ---------------------------------------------------------------------------
# 🔴 PAATOSLOGIIKKA, EI VAIN SEN PALASET (lisatty 12.9 illalla)
#
# Tarkistus mittasi: `fetch_retry` ja `artefaktin_ika_h` olivat katettuja
# erikseen, mutta PAATOS niiden valilla asui `__main__`-lohkossa jota mikaan
# testi ei aja. Kun `raise SystemExit(0)` vaihdettiin `SystemExit(1)`:ksi —
# tasan sama vika joka punasti refreshin kolme kertaa 12.9 — koko 4207
# testin suite pysyi vihreana. Logiikka on nyt `ratkaise_upstream`issa.
# ---------------------------------------------------------------------------
def test_transientti_tuoreella_artefaktilla_ei_punasta():
    f = _mod("build_founder_stats")
    koodi, viesti = f.ratkaise_upstream("HTTP 503", 2.0, nimi="founder.json")
    assert koodi == 0, "transientti 503 tuoreella artefaktilla ei saa punastaa"
    assert "::warning::" in viesti and "::error::" not in viesti


def test_jaatynyt_artefakti_punastaa():
    f = _mod("build_founder_stats")
    koodi, viesti = f.ratkaise_upstream("HTTP 503", f.STALE_ESCALATE_H + 1,
                                        nimi="founder.json")
    assert koodi == 1, "yli ikarajan vanha luku etusivulla on oma vikansa"
    assert "::error::" in viesti


def test_raja_on_inklusiivinen():
    """Tasan rajalla eskaloidaan. Ilman tata `>=` voisi liukua `>`:ksi
    huomaamatta, ja raja ei tarkoittaisi mitaan."""
    f = _mod("build_founder_stats")
    assert f.ratkaise_upstream("x", f.STALE_ESCALATE_H)[0] == 1
    assert f.ratkaise_upstream("x", f.STALE_ESCALATE_H - 0.01)[0] == 0


def test_puuttuva_artefakti_punastaa():
    f = _mod("build_founder_stats")
    koodi, viesti = f.ratkaise_upstream("HTTP 503", None, nimi="founder.json")
    assert koodi == 1 and "ole olemassa" in viesti


def test_retries_on_kolme_eika_vakion_arvo():
    """Tautologinen assertti (`== RETRIES`) ei mittaa mitaan: se on tosi
    vaikka vakio olisi 1. Literaali kaatuu jos retry poistetaan."""
    v = _mod("verify_model_entry_matches_freeze")
    f = _mod("build_founder_stats")
    assert v.RETRIES == 3 and f.RETRIES == 3
    assert len(v.RETRY_SLEEP_S) >= 1 and len(f.RETRY_SLEEP_S) >= 1


def test_verifiointimerkinta_kirjoittaa_lf_eika_crlf(tmp_path):
    """Windowsilla oletuskirjoitus tekisi CRLF:n ja koko tiedosto nayttaisi
    muuttuneelta. Tata puolta ei mitattu ensimmaisessa versiossa."""
    v = _mod("verify_model_entry_matches_freeze")
    p = _freeze_tiedosto(tmp_path, 4, "2026-09-12T12:30:00Z")
    v.record_verification(p, json.loads(p.read_text(encoding="utf-8")), 4,
                          squad_match=False, captain_match=True, common=7,
                          now=_dt.datetime(2026, 9, 12, 13, 18,
                                           tzinfo=_dt.timezone.utc))
    tavut = p.read_bytes()
    assert b"\r\n" not in tavut, "CRLF immutable-artefaktissa"
    assert tavut.endswith(b"\n")
