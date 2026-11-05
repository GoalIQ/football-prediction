"""Kanta vasta jäädytetyn rivin jälkeen (5.11.2026, ylläpitäjän sääntö: "vasta kun jäädytetty rivi on valmis").

GW10:n issue avautui 4.11 18:49Z ja mallin rivi jäädytettiin 5.11 12:59Z. Kanta vertaa ihmistä malliin, joten
vastaus ennen jäädytystä voi kiistellä rivin kanssa, jota malli ei pelaa. Sääntö mitataan jokaisessa vaiheessa
(CLAUDE.md 6a(3)): ennen jäädytystä, jäädytyshetkellä, jäädytyksen jälkeen ja deadlinen jälkeen.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from scripts import bsky_kanta as kanta

DL = datetime(2026, 11, 6, 18, 30, tzinfo=timezone.utc)          # GW10
JAADYTYS = datetime(2026, 11, 5, 12, 59, tzinfo=timezone.utc)    # data/model_squad_frozen/gw10.json
ISSUE_AUKESI = datetime(2026, 11, 4, 18, 49, tzinfo=timezone.utc)
VILLE = {"login": "Veikkoville", "type": "User"}


def _kommentti(at: datetime | str | None) -> dict:
    created = at.strftime("%Y-%m-%dT%H:%M:%SZ") if isinstance(at, datetime) else at
    return {"user": VILLE, "author_association": "CONTRIBUTOR", "body": "1. Haaland.", "created_at": created}


def _kysy(now, frozen):
    luodut = []
    return kanta.ask(10, DL, now, lambda t: None, luodut.append, frozen=frozen), luodut


@pytest.mark.parametrize("now", [ISSUE_AUKESI, DL - kanta.ASK_WINDOW, JAADYTYS - timedelta(minutes=1)])
def test_ennen_jaadytysta_ei_kysyta(now):
    """Aikaikkuna on auki, mutta riviä ei ole: issueta ei avata (4.11 18:49Z olisi nyt 'ei-jaadytetty')."""
    assert kanta.ask_due(DL, now)
    tila, luodut = _kysy(now, frozen=None)
    assert tila == "ei-jaadytetty" and luodut == []


def test_jaadytys_tulevaisuudessa_ei_kelpaa():
    tila, luodut = _kysy(JAADYTYS - timedelta(minutes=1), frozen=JAADYTYS)
    assert tila == "ei-jaadytetty" and luodut == []


@pytest.mark.parametrize("now", [JAADYTYS, JAADYTYS + timedelta(hours=1), DL - kanta.MIN_ASK_LEAD])
def test_jaadytyksen_jalkeen_kysytaan_kerran(now):
    tila, luodut = _kysy(now, frozen=JAADYTYS)
    assert tila == "luotu" and len(luodut) == 1 and luodut[0]["title"] == "Kanta GW10"


def test_jaadytyskaan_ei_avaa_liian_myohaan():
    """Aikaraja pätee yhä: jäädytys ei ohita MIN_ASK_LEADia (GW8 24.10)."""
    tila, luodut = _kysy(DL - kanta.MIN_ASK_LEAD + timedelta(minutes=1), frozen=JAADYTYS)
    assert tila == "ei-aika" and luodut == []


def test_read_hylkaa_ennen_jaadytysta_kirjoitetun():
    now = DL - timedelta(hours=5)
    hylatyt = Counter()
    ennen = _kommentti(JAADYTYS - timedelta(minutes=1))
    tasan = _kommentti(JAADYTYS)
    jalkeen = _kommentti(JAADYTYS + timedelta(hours=5))
    takes = kanta.read(10, DL, now, [ennen, tasan, jalkeen], hylatyt, frozen=JAADYTYS)
    assert [t["at"] for t in takes] == [tasan["created_at"], jalkeen["created_at"]]
    assert hylatyt == {"ennen jäädytystä": 1}


def test_read_ilman_jaadytysta_ei_mitaan():
    hylatyt = Counter()
    assert kanta.read(10, DL, DL - timedelta(hours=5), [_kommentti(JAADYTYS)], hylatyt, frozen=None) == []
    assert hylatyt == {"ei jäädytystä": 1}


@pytest.mark.parametrize("at", [None, "", "eilen", "2026-11-05T14:00:00"])
def test_read_hylkaa_kommentin_ilman_aikaa(at):
    """Naiivia tai puuttuvaa leimaa ei arvata: kanta joka voi olla ennen jäädytystä ei pääse läpi."""
    hylatyt = Counter()
    assert kanta.read(10, DL, DL - timedelta(hours=5), [_kommentti(at)], hylatyt, frozen=JAADYTYS) == []
    assert hylatyt == {"aika puuttuu": 1}


def test_deadlinen_jalkeen_ei_mitaan_vaikka_jaadytetty():
    assert kanta.read(10, DL, DL, [_kommentti(JAADYTYS + timedelta(hours=1))], frozen=JAADYTYS) == []


def _kirjoita(d, gw, meta):
    (d / f"gw{gw}.json").write_text(json.dumps({"meta": meta}), encoding="utf-8")


def test_frozen_at_lukee_jaadytyksen(monkeypatch, tmp_path):
    monkeypatch.setattr(kanta, "FROZEN_DIR", tmp_path)
    assert kanta.frozen_at(10) is None                                   # tiedostoa ei ole
    _kirjoita(tmp_path, 10, {"gw": 10, "frozen_at": "2026-11-05T12:59:00Z"})
    assert kanta.frozen_at(10) == JAADYTYS
    _kirjoita(tmp_path, 11, {"gw": 10, "frozen_at": "2026-11-05T12:59:00Z"})
    assert kanta.frozen_at(11) is None                                   # toisen kierroksen tiedosto
    _kirjoita(tmp_path, 12, {"gw": 12, "frozen_at": "2026-11-05T12:59:00"})
    assert kanta.frozen_at(12) is None                                   # naiivi leima
    (tmp_path / "gw13.json").write_text("{rikki", encoding="utf-8")
    assert kanta.frozen_at(13) is None


def test_frozen_dir_on_jaadytysskriptin_hakemisto():
    """Yksi lähde: sama hakemisto, johon freeze_model_squad_gw.py kirjoittaa."""
    from scripts import freeze_model_squad_gw as freeze
    assert kanta.FROZEN_DIR.resolve() == freeze.FROZEN_DIR.resolve()


def test_kutsupaikat_valittavat_jaadytyksen(monkeypatch):
    """`ask` ja `read` eivät voi unohtaa jäädytystä: `frozen` on pakollinen nimetty argumentti."""
    with pytest.raises(TypeError):
        kanta.ask(10, DL, JAADYTYS, lambda t: None, lambda p: None)      # type: ignore[call-arg]
    with pytest.raises(TypeError):
        kanta.read(10, DL, JAADYTYS, [])                                 # type: ignore[call-arg]
    kysytyt = []
    monkeypatch.setattr(kanta, "frozen_at", lambda gw: kysytyt.append(gw) or None)
    monkeypatch.setenv("GH_TOKEN", "t")
    monkeypatch.setattr(kanta, "_find_issue", lambda token, gw: None)
    monkeypatch.setattr(kanta, "_req", lambda *a, **k: pytest.fail("ei saa luoda issueta ilman jäädytystä"))
    assert kanta.cmd_ask(10, DL, JAADYTYS + timedelta(hours=1)) == 0
    assert kysytyt == [10]
