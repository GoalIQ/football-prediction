"""Bluesky-botin toistoportti (23.10.2026): aihe ja kuva, ei vain teksti.

GW8:n kapteenista lahti nelja omaa postausta 20.-23.10, kolmessa tasmalleen sama best-captain-kortti
(sama blob, mitattu julkisesta syotteesta). Jokaisen teksti oli eri, joten `similar` paasti ne. Nama
testit toistavat sen sarjan ja mittaavat saman portin kahdella kierroksella (ennen ja jalkeen deadlinen).
"""
from __future__ import annotations

import sys
import types
from datetime import datetime, timedelta, timezone

import scripts
from scripts import bsky_bot as bot
from src.marketing import bsky_gate as gate

DL8 = datetime(2026, 10, 23, 17, 30, tzinfo=timezone.utc)


def _state(**kw):
    s = {"posted_slots": [], "replied_uris": [], "replied_roots": [], "author_last_reply": {},
         "daily": {}, "recent_texts": [], "handled_notifications": [], "pending_posts": [], "own_posts": []}
    s.update(kw)
    return s


def _post(text, topic, card=None, slot=None, source="brain"):
    return {"kind": "post", "text": text, "keys": [], "topic": topic, "card": card, "slot": slot, "source": source}


def _probs(item, state, gw, now):
    return gate.check(item, values={}, gw=gw, now=now, state=state, blocklist=set(), phrases=[])


def _toisto(probs):
    return [p for p in probs if p.startswith(("aihe ", "kortti ", "slot "))]


def test_gw8_kapteenisarja_lahtee_kerran():
    """Sarja sellaisenaan (ajat ja aiheet lokista): vain deadline-slotin postaus menee."""
    state = _state()
    sarja = [
        (datetime(2026, 10, 20, 17, 56, tzinfo=timezone.utc),
         _post("Everyone is staring at the Haaland flag while Saka sits second in the armband list.", "captain",
               "best-captain"), False),
        (datetime(2026, 10, 22, 9, 54, tzinfo=timezone.utc),
         _post("Mbeumo matches Haaland this week and costs far less, a different armband if you want one.",
               "captain", "best-captain"), False),
        (datetime(2026, 10, 22, 11, 52, tzinfo=timezone.utc),
         _post("Close captain call in GW8. B.Fernandes is top of the model.", "captain", "best-captain",
               "deadline:gw8", "rule"), True),
        (datetime(2026, 10, 23, 9, 54, tzinfo=timezone.utc),
         _post("Haaland or Joao Pedro for the armband is the argument everywhere today.", "captain",
               "best-captain"), False),
    ]
    for now, it, menee in sarja:
        probs = _probs(it, state, 8, now)
        assert (probs == []) is menee, (it["text"], probs)
        if not probs:
            bot._mark(state, it, now, 8)
    assert [p["slot"] for p in state["own_posts"]] == ["deadline:gw8"]
    # aivot eivat voi kiertaa kirjoittamalla saman slotin toiseen kertaan
    uusi = _post("Bruno edges it for the armband in GW8.", "captain", "best-captain", "deadline:gw8")
    assert any("slot deadline:gw8 on jo postattu" in p for p in _probs(uusi, state, 8, DL8 - timedelta(hours=3)))


def test_kapteeni_vain_kuluvan_kierroksen_deadline_slotissa():
    s = _state()
    now = DL8 - timedelta(hours=10)
    assert _toisto(_probs(_post("Armband time.", "captain", None, "deadline:gw8"), s, 8, now)) == []
    assert _toisto(_probs(_post("Armband time.", "captain", None, "deadline:gw7"), s, 8, now))
    assert _toisto(_probs(_post("Armband time.", "captain", None, "deadline:gw8"), s, None, now))
    # best-captain-kortti on deadline-postauksen kuva: muu aihe ei saa sita
    assert _toisto(_probs(_post("Cheap Brighton defenders.", "player", "best-captain"), s, 8, now))
    assert _toisto(_probs(_post("Cheap Brighton defenders.", "player", "expected-points"), s, 8, now)) == []


def test_sama_kortti_kerran_kierroksessa_ja_seuraavalla_taas():
    s = _state()
    t1 = DL8 - timedelta(hours=40)
    a = _post("Brighton defenders keep rising on the price list.", "player", "expected-points")
    assert _probs(a, s, 8, t1) == []
    bot._mark(s, a, t1, 8)
    b = _post("Rudoni is barely owned and the fixtures turn now.", "differential", "expected-points")
    assert any("kortti expected-points" in p for p in _probs(b, s, 8, t1 + timedelta(hours=20)))
    # negatiivinen kontrolli: sama aihe ilman korttia on sallittu (player ei ole kerran-aihe)
    c = _post("Vuskovic is the cheap defender people are buying.", "player", None)
    assert _toisto(_probs(c, s, 8, t1 + timedelta(hours=20))) == []
    # vaihe: deadlinen jalkeen moduuli on GW9 ja sama kortti kay taas
    assert _toisto(_probs(b, s, 9, DL8 + timedelta(hours=5))) == []


def test_kerran_aiheet():
    s = _state()
    t = DL8 - timedelta(hours=60)
    r = _post("GW7 done for our FPL team.", "recap", None, "recap:gw7", "rule")
    assert _probs(r, s, 8, t) == []
    bot._mark(s, r, t, 8)
    toinen = _post("Our GW7 left a lot on the bench, here is where it went.", "recap")
    assert any("aihe recap" in p for p in _probs(toinen, s, 8, t + timedelta(hours=10)))
    for topic in gate.ONCE_PER_GW_TOPICS:
        assert topic in bot.TOPICS


def test_vanhat_rivit_ilman_kierrosta_lasketaan_viikon():
    now = DL8
    rivit = [{"at": (now - timedelta(days=6)).isoformat(), "gw": None, "card": "a"},
             {"at": (now - timedelta(days=8)).isoformat(), "gw": None, "card": "b"},
             {"at": None, "gw": None, "card": "c"},
             {"at": now.isoformat(), "gw": 7, "card": "d"},
             {"at": now.isoformat(), "gw": 8, "card": "e"}]
    assert [p["card"] for p in gate.gw_posts(rivit, 8, now)] == ["a", "c", "e"]


def test_tila_taytetaan_lokista(monkeypatch):
    loki = [{"at": "2026-10-22T11:52:02+00:00", "uri": "at://p/1", "kind": "post", "topic": "captain",
             "card": "best-captain", "slot": "deadline:gw8"},
            {"at": "2026-10-22T12:00:00+00:00", "uri": "at://p/2", "kind": "reply", "topic": "reply_question"},
            {"at": "2026-10-22T13:00:00+00:00", "uri": None, "kind": "post", "topic": "player"}]
    monkeypatch.setattr(bot, "read_log", lambda: loki)
    monkeypatch.setattr(bot, "load_json", lambda path, default: {})
    s = bot.load_state()
    assert s["own_posts"] == [{"at": "2026-10-22T11:52:02+00:00", "gw": None, "topic": "captain",
                               "card": "best-captain", "slot": "deadline:gw8"}]


def _mod(gw, dl):
    return {"gw": gw, "deadline_utc": dl.isoformat(), "sections": {
        "captain_top5": {"rows": [{"key": "haaland-mci", "name": "Haaland", "player_id": 1}]},
        "xp_top5": {"rows": [{"key": "haaland-mci", "player_id": 1}, {"key": "cherki-mci", "player_id": 2}]},
        "last_gw": {"available": False}}}


def _vals():
    page = "https://goaliq.app/fpl/expected-points#gw-xp"
    return {"captain_top5.haaland-mci.gw_xp": {"text": "8.0", "value": 8.0, "public_url": page},
            "captain_top5.haaland-mci.p_10plus": {"text": "32%", "public_url": "https://goaliq.app/fpl/expected-points"},
            "xp_top5.haaland-mci.gw_xp": {"text": "8.0", "value": 8.0, "public_url": page},
            "xp_top5.cherki-mci.gw_xp": {"text": "x", "value": 5.5, "public_url": page}}


def test_julkaisu_kirjaa_kierroksen_ja_seuraava_deadline_paasee(monkeypatch):
    """Kutsupaikka: cmd_publish kirjaa postauksen kierroksen. Ilman sita GW8:n kortti estaisi GW9:n
    deadline-postauksen viikon ajan (vanhan rivin saanto)."""
    state = _state()
    now = DL8 - timedelta(hours=16)
    monkeypatch.setattr(bot, "load_state", lambda: state)
    monkeypatch.setattr(bot, "fresh_module", lambda d: (_mod(8, DL8), _vals(), ""))
    monkeypatch.setattr(bot, "blocklist", lambda: set())
    monkeypatch.delenv("BLUESKY_APP_PASSWORD", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    def _ei_chromea(card):
        raise RuntimeError("ei korttia testissa")
    kortti = types.SimpleNamespace(render=_ei_chromea)
    monkeypatch.setitem(sys.modules, "scripts.bsky_card", kortti)
    monkeypatch.setattr(scripts, "bsky_card", kortti, raising=False)

    assert bot.cmd_publish(None, dry=True, now=now) == 0
    assert state["own_posts"] and state["own_posts"][-1]["gw"] == 8
    assert state["own_posts"][-1]["slot"] == "deadline:gw8"

    dl9 = DL8 + timedelta(days=7)
    gw9 = _post("No obvious armband in GW9.", "captain", "best-captain", "deadline:gw9", "rule")
    assert _toisto(_probs(gw9, state, 9, dl9 - timedelta(hours=20))) == []
    gw8_uudelleen = _post("No obvious armband in GW8.", "captain", "best-captain", "deadline:gw8", "rule")
    assert _toisto(_probs(gw8_uudelleen, state, 8, now + timedelta(hours=3)))
