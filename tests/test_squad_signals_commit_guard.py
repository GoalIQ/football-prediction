# -*- coding: utf-8 -*-
"""Portti: valvomaton vahti ei saa committoida muualle kuin mainiin.

TAUSTA (mitattu 20.9.2026). `squad_signals_watch.py` committoi vahtiraportin
hub-repoon Task Schedulerista kahdesti paivassa. 18.9, 19.9 ja 20.9 se
committoi haaralle `feat/mobiili-yksi-ikkunalukija`, koska hubin tyopuu oli
jaanyt siihen edellisesta sessiosta. Kolmen vuorokauden saatavuussignaalit
(18.9 yksin 16 muutosta: Wilson a->i, James a->d, Pau 75->0) eivat olleet
mainissa eivatka originissa, eika kukaan huomannut.

Skriptissa oli jo KOLME dokumentoitua varotointa - eika yksikaan niista
koskenut sita mihin kirjoitetaan. Varotoimi 3 tulosti "PUSH EI MENNYT",
mutta valvomattoman ajon tulostetta ei lue kukaan. CLAUDE.md 6a: vahti joka
kertoo jalkikateen ei riita.

EROTTELEVA FIKSTUURI. Jokainen tapaus ajetaan OIKEASSA git-repossa, ja
"main"-tapaus todistaa etta commit oikeasti onnistuu samalla koodipolulla.
Ilman sita testi lapaisisi myos toteutuksella joka kieltaytyy aina
(muisti: exit-koodi-ei-ole-todiste-mekanismista).
"""
from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _git(juuri: Path, *a: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(juuri), *a],
                          capture_output=True, text=True, timeout=60)


@pytest.fixture()
def hub(tmp_path: Path) -> Path:
    """Oikea git-repo joka jaljittelee hubia: main + yksi feature-haara."""
    juuri = tmp_path / "goaliq-app"
    (juuri / "cos-reports" / "watch").mkdir(parents=True)
    _git(juuri.parent, "init", "-q", "-b", "main", str(juuri))
    _git(juuri, "config", "user.email", "t@t.fi")
    _git(juuri, "config", "user.name", "testi")
    # Hookit pois: tama testi mittaa vahdin porttia, ei repon pre-commitia.
    _git(juuri, "config", "core.hooksPath", str(tmp_path / "ei-hookkeja"))
    (juuri / "README.md").write_text("alku", encoding="utf-8")
    _git(juuri, "add", "-A")
    _git(juuri, "commit", "-qm", "alku")
    _git(juuri, "branch", "feat/mobiili-yksi-ikkunalukija")
    return juuri


@pytest.fixture()
def vahti(hub: Path, monkeypatch):
    mod = importlib.import_module("squad_signals_watch")
    monkeypatch.setattr(mod, "HUB_ROOT", hub)
    monkeypatch.setattr(mod, "HUB_WATCH_DIR", hub / "cos-reports" / "watch")
    return mod


def _raportti(hub: Path, nimi: str = "squad-signals-2026-09-20.md") -> Path:
    p = hub / "cos-reports" / "watch" / nimi
    p.write_text("# Squad signals\n\n| Wilson | Saatavuus | a | i |\n", encoding="utf-8")
    return p


def _haara(hub: Path) -> str:
    return _git(hub, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


# --------------------------------------------------------------------------
# EROTTELEVA PARI: mainissa commit onnistuu, feature-haarassa ei.
# --------------------------------------------------------------------------

def test_mainissa_committoidaan(vahti, hub):
    assert _haara(hub) == "main"
    tulos = vahti.commit_report(_raportti(hub))
    assert "EI COMMITTOITU" not in tulos, tulos
    loki = _git(hub, "log", "--oneline", "-1").stdout
    assert "squad-signals" in loki, f"commit ei syntynyt: {loki!r} / {tulos!r}"


def test_feature_haarassa_ei_committoida(vahti, hub):
    _git(hub, "checkout", "-q", "feat/mobiili-yksi-ikkunalukija")
    ennen = _git(hub, "rev-parse", "HEAD").stdout.strip()

    tulos = vahti.commit_report(_raportti(hub))

    assert "EI COMMITTOITU" in tulos, tulos
    assert "feat/mobiili-yksi-ikkunalukija" in tulos, \
        "tilarivin on nimettava haara, muuten syy jaa arvattavaksi"
    jalkeen = _git(hub, "rev-parse", "HEAD").stdout.strip()
    assert ennen == jalkeen, "haaralle ei saa syntya committia"


def test_irrallinen_head_ei_committoida(vahti, hub):
    sha = _git(hub, "rev-parse", "HEAD").stdout.strip()
    _git(hub, "checkout", "-q", sha)
    ennen = _git(hub, "rev-parse", "HEAD").stdout.strip()

    tulos = vahti.commit_report(_raportti(hub))

    assert "EI COMMITTOITU" in tulos, tulos
    assert _git(hub, "rev-parse", "HEAD").stdout.strip() == ennen


def test_raportti_jaa_levylle_kun_portti_estaa(vahti, hub):
    """Fail-closed ei saa tarkoittaa datan menetysta: vahdin tyo on
    liputtaa muutokset, ja signaali on arvokkaampi kuin commit."""
    _git(hub, "checkout", "-q", "feat/mobiili-yksi-ikkunalukija")
    p = _raportti(hub)
    vahti.commit_report(p)
    assert p.exists() and "Wilson" in p.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Vanhat varotoimet eivat saa rikkoutua uuden alta.
# --------------------------------------------------------------------------

def test_hubin_ulkopuolinen_polku_torjutaan(vahti, tmp_path):
    ulko = tmp_path / "muualla.md"
    ulko.write_text("x", encoding="utf-8")
    assert "ei committoida" in vahti.commit_report(ulko)


def test_kesken_oleva_merge_estaa_yha(vahti, hub):
    (hub / ".git" / "MERGE_HEAD").write_text("deadbeef", encoding="utf-8")
    tulos = vahti.commit_report(_raportti(hub))
    assert "MERGE_HEAD" in tulos


def test_sama_sisalto_ei_tee_tyhjaa_committia(vahti, hub):
    p = _raportti(hub)
    vahti.commit_report(p)
    ennen = _git(hub, "rev-parse", "HEAD").stdout.strip()
    tulos = vahti.commit_report(p)
    assert "ei muutosta" in tulos
    assert _git(hub, "rev-parse", "HEAD").stdout.strip() == ennen


# --------------------------------------------------------------------------
# KUTSUPAIKKAPORTTI: portin on oltava commit_reportissa, ei vain jossain
# apufunktiossa jota kukaan ei kutsu.
# --------------------------------------------------------------------------

def test_portti_on_commit_reportin_rungossa():
    lahde = (ROOT / "scripts" / "squad_signals_watch.py").read_text(encoding="utf-8")
    runko = lahde.split("def commit_report(", 1)[1].split("\ndef ", 1)[0]
    assert "symbolic-ref" in runko, "haaralukija ei ole commit_reportissa"
    assert '!= "main"' in runko, "mainiin vertaaminen puuttuu rungosta"
    # Portin on oltava ENNEN committia, ei sen jalkeen.
    assert runko.index("symbolic-ref") < runko.index('"commit"'), \
        "haaratarkistus ajetaan vasta commitin jalkeen"
