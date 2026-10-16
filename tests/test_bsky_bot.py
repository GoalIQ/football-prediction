"""Bluesky-botti (16.10.2026): portti, linkkien facetit, varapostaukset, oppimistaulukko.

Portti on ainoa asia aivojen (Claude-agentti) ja julkisen postauksen valissa. Jokaiselle kiellolle on
positiivinen ja negatiivinen kontrolli: portti joka ei koskaan hylkaa on yhta arvoton kuin puuttuva.
"""
from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import bsky_bot as bot
from src.marketing import bsky, bsky_gate as gate

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 16, 18, 0, tzinfo=timezone.utc)
V = {
    "captain_top5.haaland-mci.gw_xp": {"text": "8.0", "public_url": "https://goaliq.app/fpl/expected-points#gw-xp"},
    "captain_top5.haaland-mci.p_10plus": {"text": "32%", "public_url": "https://goaliq.app/fpl/expected-points"},
    "cs_top.ars.cs_pct": {"text": "49%", "public_url": "https://goaliq.app/fpl#clean-sheets"},
    "player_lookup.saka-ars.price": {"text": "10.2", "public_url": None},
}


def _state(**kw):
    s = {"posted_slots": [], "replied_uris": [], "replied_roots": [], "author_last_reply": {},
         "daily": {}, "recent_texts": [], "handled_notifications": []}
    s.update(kw)
    return s


def _post(text, keys, **kw):
    return {"kind": "post", "text": text, "keys": keys, **kw}


def _reply(text, keys, age_h=1.0, handle="fpl.page", uri="at://x/1", **kw):
    t = {"uri": uri, "cid": "c1", "handle": handle,
         "created_at": (NOW - timedelta(hours=age_h)).isoformat()}
    return {"kind": "reply", "text": text, "keys": keys, "target": t, **kw}


def chk(item, state=None, blocked=frozenset(), phrases=()):
    return gate.check(item, values=V, gw=7, now=NOW, state=state or _state(), blocklist=set(blocked),
                      phrases=list(phrases))


OK_TEXT = "GW7 captain: Haaland at 8.0 expected points, 32% chance of 10+. goaliq.app/fpl/best-captain"
OK_KEYS = ["captain_top5.haaland-mci.gw_xp", "captain_top5.haaland-mci.p_10plus"]


def test_kelvollinen_postaus_lapi():
    assert chk(_post(OK_TEXT, OK_KEYS)) == []


@pytest.mark.parametrize("teksti,syy", [
    ("Haaland at 8.1 expected points.", "luku"),                 # luku jota avain ei kanna
    ("Haaland at 8.0 expected points, price 15.6m.", "luku"),    # yksikko perassa ei vapauta
    ("Haaland at 8.0 expected points — easy.", "em dash"),
    ("Haaland at 8.0 expected points, deadline 10:00.", "luku"),
    ("GW9 captain: Haaland at 8.0.", "kierros"),
])
def test_luvut_ja_merkit_hylataan(teksti, syy):
    probs = chk(_post(teksti, ["captain_top5.haaland-mci.gw_xp"]))
    assert probs and any(syy in p for p in probs), probs


def test_avain_ilman_julkista_reittia_ei_kelpaa():
    probs = chk(_post("Saka costs 10.2 now.", ["player_lookup.saka-ars.price"]))
    assert any("luku" in p for p in probs)


def test_10plus_vain_p10_avaimen_kanssa():
    assert chk(_post("Haaland at 8.0, chance of 10+.", ["captain_top5.haaland-mci.gw_xp"]))
    assert chk(_post("Haaland at 8.0, 32% chance of 10+.", OK_KEYS)) == []


def test_hylatty_sanamuoto():
    assert chk(_post("Haaland at 8.0 expected points.", OK_KEYS[:1]), phrases=["expected points"])


def test_vastaus_ei_linkkia_eika_tuotenimea():
    keys = ["captain_top5.haaland-mci.gw_xp"]
    assert chk(_reply("Model has Haaland at 8.0 for GW7.", keys)) == []
    assert any("linkki" in p for p in chk(_reply("Haaland 8.0, see goaliq.app/fpl", keys)))
    assert any("tuotenimi" in p for p in chk(_reply("GoalIQ has Haaland at 8.0.", keys)))


def test_vastaus_tuoreus_estolista_ja_tauko():
    keys = ["captain_top5.haaland-mci.gw_xp"]
    t = "Model has Haaland at 8.0 for GW7."
    assert any("4 h" in p for p in chk(_reply(t, keys, age_h=5)))
    assert any("estolistalla" in p for p in chk(_reply(t, keys, handle="ffscoutfpl.bsky.social"),
                                                    blocked={"ffscoutfpl.bsky.social"}))
    s = _state(author_last_reply={"fpl.page": (NOW - timedelta(hours=10)).isoformat()})
    assert any("48 h" in p for p in chk(_reply(t, keys), state=s))
    s2 = _state(replied_uris=["at://x/1"])
    assert any("jo vastattu" in p for p in chk(_reply(t, keys), state=s2))


def test_kiintiot():
    day = NOW.date().isoformat()
    full = _state(daily={day: {"post": gate.POSTS_PER_DAY, "reply": gate.OUTBOUND_REPLIES_PER_DAY}})
    assert any("kiintio" in p for p in chk(_post(OK_TEXT, OK_KEYS), state=full))
    assert any("kiintio" in p for p in chk(_reply("Model has Haaland at 8.0 for GW7.", OK_KEYS[:1]), state=full))


def test_toisto_hylataan():
    s = _state(recent_texts=[OK_TEXT])
    assert any("toisto" in p for p in chk(_post(OK_TEXT, OK_KEYS), state=s))


def test_facetit_tavuoffseteilla_ja_utm():
    disp, uri = bot.utm_link("/fpl/best-captain", "captain", "2026101618-0")
    assert disp == "goaliq.app/fpl/best-captain"
    assert "utm_source=bluesky" in uri and "utm_medium=partner" in uri and "utm_content=2026101618-0" in uri
    text = f"Groß 9.0 expected points. {disp}"          # monitavuinen merkki ennen linkkia
    f = bsky.link_facets(text, {disp: uri})[0]
    start = len(text[:text.index(disp)].encode("utf-8"))
    assert f["index"] == {"byteStart": start, "byteEnd": start + len(disp.encode("utf-8"))}
    assert f["features"][0]["uri"] == uri
    _d, u2 = bot.utm_link("/fpl#gw-calls", "recap", "x")
    assert u2.endswith("#gw-calls") and "?utm_source" in u2


def test_varapostaukset_lapaisevat_portin():
    mod = {"gw": 7, "deadline_utc": (NOW + timedelta(hours=16)).isoformat(), "sections": {
        "captain_top5": {"rows": [{"key": "haaland-mci", "name": "Haaland"}]},
        "cs_top": {"rows": [{"key": "ars", "team": "Arsenal"}]},
        "last_gw": {"available": True, "gw": 6}}}
    vals = dict(V)
    vals["last_gw.entry_points"] = {"text": "57", "public_url": "https://fantasy.premierleague.com/entry/116920/event/6"}
    vals["last_gw.fpl_average"] = {"text": "58", "public_url": "https://fantasy.premierleague.com/entry/116920/event/6"}
    items = bot.fallback_items(mod, vals, NOW, _state())
    assert {i["slot"] for i in items} == {"deadline:gw7", "recap:gw6"}
    for it in items:
        text, links = bot.prepare(it, "t")
        assert gate.check({**it, "text": text}, values=vals, gw=7, now=NOW, state=_state(),
                          blocklist=set(), phrases=gate.rejected_phrases()) == [], text
    # slot kerran: toinen ajo ei tee samaa postausta
    assert bot.fallback_items(mod, vals, NOW, _state(posted_slots=["deadline:gw7", "recap:gw6"])) == []
    # deadline-ikkunan ulkopuolella ei kapteenipostausta
    late = {**mod, "deadline_utc": (NOW + timedelta(hours=1)).isoformat()}
    assert "deadline:gw7" not in {i["slot"] for i in bot.fallback_items(late, vals, NOW, _state())}


def test_oppimistaulukko_ei_nayta_yhta_osumaa_varmana():
    t = bot.topic_table([{"topic": "captain", "engagement": 1}, {"topic": "recap", "engagement": 0},
                         {"topic": "recap", "engagement": 0}, {"topic": "x", "engagement": None}])
    assert t["captain"]["engaged_rate_bayes"] == round(2 / 3, 3)
    assert t["recap"]["engaged_rate_bayes"] == 0.25
    assert "x" not in t


@pytest.mark.parametrize("polku", ["data/bsky_state.json", "data/bsky_posted.jsonl", "data/bsky_performance.json",
                                   "data/bsky_targets.json", "data/bsky_blocklist.json",
                                   "data/fpl_schema_snapshot.json"])
def test_botin_tiedostot_eivat_ole_gitignoressa(polku):
    """Gitignoroitu tila = botti unohtaa joka ajossa mita on postannut (ja toistaa)."""
    r = subprocess.run(["git", "check-ignore", "-q", polku], cwd=ROOT, stdin=subprocess.DEVNULL,
                       capture_output=True)
    assert r.returncode == 1, f"{polku} on gitignoressa"
