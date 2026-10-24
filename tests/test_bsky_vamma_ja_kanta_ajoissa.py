"""Bluesky-botti 24.10.2026 (ylläpitäjä: "Ei tällaisia"): kaksi vikaa samasta päivästä.

1. Pyytämätön vastaus fpl.pagen loukkaantumisuutiseen (Saka, FPL 0 % "Unknown return date" jo 21.10):
   arvailua ja "moving him or sitting tight?" ilman mallin lukua. Portti ei nähnyt mitään, koska lukuja ei ollut.
2. Kanta GW8 avautui 38 min ennen deadlinea, vastaus tuli 17:03Z, eikä yksikään ajo ehtinyt ennen 17:30Z.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from scripts import bsky_bot as bot
from scripts import bsky_kanta as kanta
from src.marketing import bsky_gate as gate

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 23, 14, 59, tzinfo=timezone.utc)
V = {"player_lookup.saka-ars.gw_xp": {"text": "0.4", "public_url": "https://goaliq.app/fpl/expected-points#gw-xp"},
     "player_lookup.de-cuyper-bha.xp_6gw": {"text": "24.8",
                                            "public_url": "https://goaliq.app/fpl/expected-points#xp-6gw"}}

# Sanatarkasti 23.10 14:59Z (data/bsky_posted.jsonl) ja sen kohde (fpl.page).
SAKA_REPLY = ("Fluid in the area is the worrying bit, and a clearer answer only tomorrow doesn't help anyone with a "
              "deadline in a couple of hours. He's also on FPL's own fall list tonight. Are you moving him or "
              "sitting tight?")
SAKA_TARGET = ("\"He's got another MRI this afternoon because he had quite a lot of fluid in the area so it was "
               "difficult to understand the extent of the injury. We will know more probably tomorrow.\"")
# 22.10 17:54Z, meni ulos ja on sellainen vastaus kuin halutaan: kanta + mallin luku.
GOOD_REPLY = ("Playing him at right back makes sense to me. The model likes De Cuyper too, 24.8 expected points "
              "over the next six gameweeks. Is he already in your side or a move this week?")
GOOD_TARGET = "De Cuyper at right back for Brighton again. Worth a move?"


@pytest.fixture(autouse=True)
def _vastaukset_paalla(monkeypatch):
    monkeypatch.setattr(gate, "OUTBOUND_REPLIES_PER_DAY", 2)


def _item(text, keys, target_text, kind="reply"):
    return {"kind": kind, "topic": "reply_question", "text": text, "keys": keys,
            "target": {"uri": "at://x/1", "cid": "c1", "handle": "fpl.page", "text": target_text,
                       "created_at": (NOW - timedelta(hours=1)).isoformat()}}


def _chk(item):
    return gate.check(item, values=V, gw=8, now=NOW, state={}, blocklist=set(), phrases=[])


def test_saka_vastaus_hylataan_kahdesta_syysta():
    probs = _chk(_item(SAKA_REPLY, [], SAKA_TARGET))
    assert any("ilman mallin lukua" in p for p in probs), probs
    assert any("loukkaantumisuutiseen (vastaus" in p for p in probs), probs
    assert any("loukkaantumisuutiseen (kohdepostaus" in p for p in probs), probs


def test_hyva_vastaus_menee_lapi():
    assert _chk(_item(GOOD_REPLY, ["player_lookup.de-cuyper-bha.xp_6gw"], GOOD_TARGET)) == []


def test_luku_ei_vapauta_vammauutista():
    """Mallin luku vamma-aiheeseen on yhä vamma-arvailua: kohde riittää hylkäämään."""
    t = "The model has Saka on 0.4 for GW8. Holding or moving?"
    probs = _chk(_item(t, ["player_lookup.saka-ars.gw_xp"], SAKA_TARGET))
    assert probs == ["pyytamaton vastaus loukkaantumisuutiseen (kohdepostaus: 'MRI')"], probs


def test_vastaus_ilman_lukua_hylataan_vaikka_aihe_olisi_harmiton():
    probs = _chk(_item("Playing him at right back makes sense to me. Already in your side?", [], GOOD_TARGET))
    assert probs == ["pyytamaton vastaus ilman mallin lukua (keys): vastaus antaa luvun tai jaa pois"], probs


def test_kohteen_teksti_on_pakollinen():
    probs = _chk(_item(GOOD_REPLY, ["player_lookup.de-cuyper-bha.xp_6gw"], ""))
    assert any("kohdepostauksen teksti puuttuu" in p for p in probs), probs


@pytest.mark.parametrize("sana", ["injury", "injured", "scan", "MRI", "hamstring", "ruled out", "fitness",
                                  "return date", "knock"])
def test_vammasanasto(sana):
    probs = _chk(_item(GOOD_REPLY, ["player_lookup.de-cuyper-bha.xp_6gw"], f"Update: {sana} news on Mitoma."))
    assert any("loukkaantumisuutiseen" in p for p in probs), (sana, probs)


def test_mentioon_vastataan_vaikka_kysyja_kysyisi_vammasta():
    """Mention on pyydetty: kysyjä haluaa luvun, eikä vamma-aihe estä vastausta hänelle."""
    it = _item("The model has Saka on 0.4 for GW8.", ["player_lookup.saka-ars.gw_xp"],
               "@goaliqapp is Saka worth holding with this thigh injury?", kind="mention_reply")
    assert _chk(it) == []


def test_aivojen_ohje_kertoo_saannon():
    aani = (ROOT / "docs" / "bsky" / "AANI.md").read_text(encoding="utf-8")
    assert "Never reply to injury or medical news" in aani
    assert "skip it (the checker rejects it)" in aani


# ---------------------------------------------------------------- kanta ajoissa

DL = datetime(2026, 10, 31, 11, 0, tzinfo=timezone.utc)   # GW9


def test_kantaa_ei_kysyta_kun_vastaus_ei_ehdi():
    luodut = []
    gw8 = datetime(2026, 10, 23, 17, 30, tzinfo=timezone.utc)
    assert kanta.ask(8, gw8, datetime(2026, 10, 23, 16, 52, tzinfo=timezone.utc), lambda t: None,
                     luodut.append) == "ei-aika"                                    # 23.10: 38 min ennen
    assert kanta.ask(9, DL, DL - kanta.MIN_ASK_LEAD + timedelta(minutes=1), lambda t: None,
                     luodut.append) == "ei-aika"
    assert kanta.ask(9, DL, DL - kanta.MIN_ASK_LEAD, lambda t: None, luodut.append) == "luotu"
    assert len(luodut) == 1
    assert kanta.MIN_ASK_LEAD > kanta.ANSWER_LEAD + gate.MIN_POST_GAP


def test_issue_kertoo_takarajan():
    b = kanta.body(9, DL)
    assert kanta.finnish_time(kanta.answer_by(DL)) in b and kanta.finnish_time(DL) in b
    assert kanta.answer_by(DL) == DL - kanta.ANSWER_LEAD
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo("Europe/Helsinki")
    except Exception:  # noqa: BLE001
        pytest.skip("ei tzdataa")
    # 31.10 on talviaikaa (UTC+2): deadline 13.00, takaraja 10.00
    assert kanta.finnish_time(DL) == "la 31.10. klo 13.00 Suomen aikaa"
    assert "viimeistään la 31.10. klo 10.00 Suomen aikaa" in b


def _take(at):
    return {"gw": 9, "text": "Captain Haaland.", "at": at}


def test_uusi_kanta_viimeisen_aivoajon_jalkeen():
    assert kanta.new_take_since([], None) is False
    assert kanta.new_take_since([_take("2026-10-30T08:00:00Z")], None) is True
    assert kanta.new_take_since([_take("2026-10-30T08:00:00Z")], "2026-10-30T07:00:00+00:00") is True
    assert kanta.new_take_since([_take("2026-10-30T08:00:00Z")], "2026-10-30T09:00:00+00:00") is False
    assert kanta.new_take_since([_take(None)], "2026-10-30T09:00:00+00:00") is True


def test_uusi_kanta_ohittaa_kellon_ja_valin_mutta_ei_deadlinea():
    now = datetime(2026, 10, 30, 12, 37, tzinfo=timezone.utc)
    s = {"last_think_at": (now - timedelta(minutes=30)).isoformat()}
    assert bot.should_think(now, s, DL) is False
    assert bot.should_think(now, s, DL, new_take=True) is True
    assert bot.should_think(DL + timedelta(minutes=5), s, DL, new_take=True) is False


def test_ajopaatos_lukee_kannan_kierroksen_deadlinesta(monkeypatch, tmp_path):
    """Kutsupaikka: cmd_should_think hakee kannan deadline_gameweekille ja välittää tuloksen should_thinkille."""
    now = datetime.now(timezone.utc)
    dl = now + timedelta(hours=20)
    meta = {"meta": {"deadline_utc": dl.isoformat(), "deadline_gameweek": 9}}
    monkeypatch.setattr(bot, "load_json", lambda p, d=None: meta)
    monkeypatch.setattr(bot, "load_state", lambda: {"last_think_at": (now - timedelta(minutes=20)).isoformat()})
    kutsut = []

    def takes(gw, deadline, n):
        kutsut.append((gw, deadline))
        return [{"gw": gw, "text": "Haaland", "at": (now - timedelta(minutes=5)).isoformat()}]
    monkeypatch.setattr(kanta, "current_takes", takes)
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    if now.hour in bot.THINK_HOURS_UTC:
        pytest.skip("kellon ajo ajaisi aivot muutenkin")
    bot.cmd_should_think(False)
    assert kutsut == [(9, dl)]
    assert out.read_text(encoding="utf-8").strip() == "think=true"


def test_aivojen_hetki_on_tilannekuvan_hetki():
    now = datetime(2026, 10, 30, 13, 5, tzinfo=timezone.utc)
    assert bot._think_mark("2026-10-30T12:40:00+00:00", now) == "2026-10-30T12:40:00+00:00"
    assert bot._think_mark("", now) == now.isoformat()
    assert bot._think_mark(None, now) == now.isoformat()
    assert bot._think_mark("2026-10-30T14:00:00+00:00", now) == now.isoformat()   # tulevaisuus ei kelpaa


def test_julkaisu_kirjaa_tilannekuvan_hetken(monkeypatch, tmp_path):
    import json
    monkeypatch.setattr(bot, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(bot, "LOG_PATH", tmp_path / "posted.jsonl")
    monkeypatch.setattr(bot, "fresh_module", lambda out: (None, {}, "testi"))
    monkeypatch.setattr(bot, "blocklist", lambda: set())
    monkeypatch.setattr(gate, "rejected_phrases", lambda: [])
    monkeypatch.delenv("BLUESKY_APP_PASSWORD", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    (tmp_path / "state.json").write_text("{}", encoding="utf-8")
    now = datetime(2026, 10, 30, 13, 5, tzinfo=timezone.utc)
    bot.cmd_publish(None, dry=True, thought=True, now=now, think_at="2026-10-30T12:40:00+00:00")
    assert json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))["last_think_at"] \
        == "2026-10-30T12:40:00+00:00"


def test_tyonkulku_kytkee_kannan_laukaisun():
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / "bsky-bot.yml").read_text(encoding="utf-8"))
    aivot, julkaise = doc["jobs"]["aivot"], doc["jobs"]["julkaise"]
    paata = next(s for s in aivot["steps"] if s.get("id") == "paata")
    assert paata["env"]["GH_TOKEN"] == "${{ secrets.GITHUB_TOKEN }}"
    kuva = next(s for s in aivot["steps"] if "bsky_bot context" in str(s.get("run") or ""))
    assert kuva["id"] == "tilannekuva"
    assert aivot["outputs"]["context_at"] == "${{ steps.tilannekuva.outputs.context_at }}"
    pub = next(s for s in julkaise["steps"] if "bsky_bot publish" in str(s.get("run") or ""))
    # '=' pitää tyhjän arvon yhtenä argumenttina: ilman sitä puuttuva context_at kaataisi koko julkaisun.
    assert "--think-at={0}" in pub["run"] and "needs.aivot.outputs.context_at" in pub["run"]
    import inspect
    assert "context_at=" in inspect.getsource(bot.cmd_context)


def test_tyhja_think_at_ei_kaada_komentoriviä(monkeypatch):
    kutsu = {}
    monkeypatch.setattr(bot, "cmd_publish", lambda *a, **k: kutsu.update(a=a, k=k) or 0)
    assert bot.main(["publish", "--queue", "q.json", "--thought", "--think-at="]) == 0
    assert kutsu["k"]["think_at"] == ""
