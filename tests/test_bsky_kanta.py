"""Ylläpitäjän kanta botin raaka-aineeksi (23.10.2026): issue kerran kierroksessa, vain OWNER/MEMBER, portti."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from scripts import bsky_bot as bot
from scripts import bsky_kanta as kanta
from src.marketing import bsky_gate as gate

DL = datetime(2026, 10, 24, 17, 30, tzinfo=timezone.utc)
GW = 9


def _c(assoc, body="Captain Haaland, model too low on Salah.", **kw):
    return {"author_association": assoc, "body": body, "created_at": "2026-10-23T09:00:00Z", **kw}


def test_ask_vain_48h_ennen_deadlinea_ja_tasan_kerran():
    luodut = []
    ok = kanta.ask(GW, DL, DL - timedelta(hours=47), lambda t: None, luodut.append)
    assert ok == "luotu" and luodut[0]["title"] == "Kanta GW9" and luodut[0]["labels"] == ["kanta"]
    assert kanta.ask(GW, DL, DL - timedelta(hours=49), lambda t: None, luodut.append) == "ei-aika"
    assert kanta.ask(GW, DL, DL + timedelta(hours=1), lambda t: None, luodut.append) == "ei-aika"
    assert kanta.ask(GW, DL, DL - timedelta(hours=30), lambda t: {"number": 1}, luodut.append) == "jo-olemassa"
    assert len(luodut) == 1


def test_read_suodattaa_omistajan_ja_deadlinen():
    kommentit = [_c("OWNER"), _c("MEMBER", "second"), _c("NONE", "random"), _c("CONTRIBUTOR", "x"),
                 _c("OWNER", "bot says", user={"type": "Bot"}), _c("OWNER", "  ")]
    now = DL - timedelta(hours=5)
    assert [t["text"] for t in kanta.read(GW, DL, now, kommentit)] == [kommentit[0]["body"], "second"]
    assert kanta.read(GW, DL, now, kommentit)[0]["gw"] == GW
    assert kanta.read(GW, DL, DL + timedelta(minutes=1), kommentit) == []


def test_context_kayttaa_kantaa(monkeypatch):
    mod = {"gw": 9, "deadline_utc": "2026-10-24T17:30:00Z"}
    monkeypatch.setattr(kanta, "current_takes", lambda *a, **k: [])
    assert bot.owner_takes(mod, DL) == []
    assert bot.owner_takes(None, DL) == []
    monkeypatch.setattr(kanta, "current_takes", lambda gw, dl, now, **k: [{"gw": gw, "text": "t", "at": None}])
    assert bot.owner_takes(mod, DL)[0]["gw"] == 9


def _check(text, take):
    it = {"kind": "post", "topic": "owner_take", "text": text, "keys": []}
    return gate.check(it, values={}, gw=GW, now=DL - timedelta(hours=5), state={}, blocklist=set(), phrases=[],
                      owner_take=take)


GOOD = "The human running this account is on Haaland for GW9, and the model leaves room for that call."
TAKE = [{"gw": 9, "text": "Haaland", "at": None}]


def test_portti_owner_take():
    assert _check(GOOD, TAKE) == []
    assert any("ilman" in p for p in _check(GOOD, []))
    assert any("ilman" in p for p in _check(GOOD, None))
    assert any("ilman" in p for p in _check(GOOD, [{"gw": 8, "text": "old", "at": None}]))
    assert any("ihmisen" in p for p in _check("Haaland is the captain pick for GW9.", TAKE))
    assert any("kirjoittamaksi" in p for p in _check(GOOD + " I wrote this myself.", TAKE))


def test_portti_ei_vaadi_kantaa_muilta_aiheilta():
    it = {"kind": "post", "topic": "captain", "text": "Haaland is the model captain pick for GW9.", "keys": []}
    assert gate.check(it, values={}, gw=GW, now=DL, state={}, blocklist=set(), phrases=[]) == []


def test_topics_sisaltaa_owner_take():
    assert "owner_take" in bot.TOPICS
