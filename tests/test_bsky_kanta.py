"""Ylläpitäjän kanta botin raaka-aineeksi (23.10.2026): issue kerran kierroksessa, vain OWNER/MEMBER, portti."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

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


PAGE = "https://goaliq.app/fpl/expected-points#gw-xp"
VALUES = {"player_lookup.haaland-mci.gw_xp": {"text": "6.1", "public_url": PAGE},
          "player_lookup.salah-liv.gw_xp": {"text": "5.2", "public_url": "https://goaliq.app/fpl/team-news"}}
KEY = ["player_lookup.haaland-mci.gw_xp"]


def _check(text, take, keys=KEY, kind="post", link="/fpl/expected-points#gw-xp"):
    it = {"kind": kind, "topic": "owner_take", "text": text, "keys": keys, "link": link}
    return gate.check(it, values=VALUES, gw=GW, now=DL - timedelta(hours=5), state={}, blocklist=set(),
                      phrases=[], owner_take=take)


GOOD = ("The human running this account is on Haaland for GW9. The model has him on 6.1 expected points. "
        "goaliq.app/fpl/expected-points")
TAKE = [{"gw": 9, "text": "Haaland", "at": None}]


def test_portti_owner_take():
    assert _check(GOOD, TAKE) == []
    assert any("ylläpitäjän vastausta" in p for p in _check(GOOD, []))
    assert any("ylläpitäjän vastausta" in p for p in _check(GOOD, None))
    assert any("ylläpitäjän vastausta" in p for p in _check(GOOD, [{"gw": 8, "text": "old", "at": None}]))
    assert any("ihmisen" in p for p in _check("Haaland is the captain pick for GW9. 6.1 for the model.", TAKE))
    assert any("kirjoittamaksi" in p for p in _check(GOOD + " I wrote this myself.", TAKE))


def test_owner_take_vaatii_mallin_luvun_ja_linkin():
    """Julkaisutarkistaja 23.10 (fp #44): 'the model leaves room for that call' meni lapi ilman todistetta."""
    tyhja = "The human running this account is on Haaland for GW9, and the model leaves room for that call."
    assert any("mallin lukua" in p for p in _check(tyhja, TAKE))
    assert any("mallin lukua" in p for p in _check(tyhja, TAKE, keys=[]))   # avain ilman lukua tekstissa
    assert any("ilman linkkia" in p for p in _check(GOOD, TAKE, link=None))
    vaara_sivu = GOOD.replace("Haaland", "Salah").replace("6.1", "5.2")
    assert any("linkki vie" in p for p in _check(vaara_sivu, TAKE, keys=["player_lookup.salah-liv.gw_xp"]))
    assert any("omana postauksena" in p for p in _check(GOOD, TAKE, kind="reply"))


def test_portti_ei_vaadi_kantaa_muilta_aiheilta():
    it = {"kind": "post", "topic": "player", "text": "Haaland is the model pick for GW9.", "keys": []}
    assert gate.check(it, values={}, gw=GW, now=DL, state={}, blocklist=set(), phrases=[]) == []


def test_topics_sisaltaa_owner_take():
    assert "owner_take" in bot.TOPICS


def test_issue_loytyy_vaikka_label_puuttuu(monkeypatch):
    """Jos label pudotetaan, label-haku on tyhja: ilman toista hakua ask avaisi issuen joka tunti."""
    haut = []

    def req(url, token, data=None):
        haut.append(url)
        if "labels=kanta" in url:
            return []
        return [{"title": "Kanta GW8", "number": 1}, {"title": "Kanta GW9", "number": 2, "pull_request": {}},
                {"title": "Kanta GW9", "number": 3}]
    monkeypatch.setattr(kanta, "_req", req)
    assert kanta._find_issue("t", 9)["number"] == 3
    assert len(haut) == 2
    luodut = []
    assert kanta.ask(GW, DL, DL - timedelta(hours=20), lambda t: kanta._find_issue("t", GW), luodut.append) \
        == "jo-olemassa" and luodut == []


def test_tyonkulku_kytkee_kannan():
    """Ilman tokenia current_takes palauttaa tyhjan ja owner_take ei koskaan toimi (hiljainen vika)."""
    import yaml
    doc = yaml.safe_load((Path(__file__).resolve().parents[1] / ".github" / "workflows" / "bsky-bot.yml")
                         .read_text(encoding="utf-8"))
    aivot, julkaise = doc["jobs"]["aivot"], doc["jobs"]["julkaise"]
    assert aivot["permissions"].get("issues") == "read"
    assert julkaise["permissions"].get("issues") == "write"

    def askel(job, ajo):
        return next(s for s in job["steps"] if ajo in str(s.get("run") or ""))
    assert "GH_TOKEN" in askel(aivot, "bsky_bot context")["env"]
    assert "GH_TOKEN" in askel(julkaise, "bsky_bot publish")["env"]
    kysy = askel(julkaise, "bsky_kanta ask")
    assert "GH_TOKEN" in kysy["env"] and kysy.get("continue-on-error") is True
    nimet = [s.get("name") for s in julkaise["steps"]]
    assert nimet.index(kysy["name"]) < nimet.index(askel(julkaise, "bsky_bot publish")["name"])
    ohje = next(s for s in aivot["steps"] if "claude-code-action" in str(s.get("uses", "")))["with"]["prompt"]
    assert "owner_take" in ohje and "used_this_gw" in ohje
