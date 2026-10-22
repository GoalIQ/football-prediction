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


def _post(text, keys, link="/fpl/expected-points#gw-xp", **kw):
    return {"kind": "post", "text": text, "keys": keys, "link": link, **kw}


@pytest.fixture(autouse=True)
def _vastaukset_paalla(monkeypatch):
    """Pyytamattomat vastaukset ovat oletuksena pois (0/vrk); testit mittaavat niiden muut ehdot."""
    monkeypatch.setattr(gate, "OUTBOUND_REPLIES_PER_DAY", 4)


def _reply(text, keys, age_h=1.0, handle="fpl.page", uri="at://x/1", **kw):
    t = {"uri": uri, "cid": "c1", "handle": handle,
         "created_at": (NOW - timedelta(hours=age_h)).isoformat()}
    return {"kind": "reply", "text": text, "keys": keys, "target": t, **kw}


def chk(item, state=None, blocked=frozenset(), phrases=()):
    return gate.check(item, values=V, gw=7, now=NOW, state=state or _state(), blocklist=set(blocked),
                      phrases=list(phrases))


OK_TEXT = "GW7 captain: Haaland at 8.0 expected points, 32% chance of 10+. goaliq.app/fpl/expected-points"
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


def test_postausvali_koskee_omia_postauksia():
    """22.10: omat postaukset lahtivat pareina 0-5 s valein. Vali ei koske vastauksia."""
    lahella = _state(last_post_at=(NOW - timedelta(minutes=5)).isoformat())
    probs = chk(_post(OK_TEXT, OK_KEYS), state=lahella)
    assert probs and all(p.startswith(gate.GAP_PROBLEM) for p in probs), probs
    assert chk(_post(OK_TEXT, OK_KEYS), state=_state(last_post_at=(NOW - gate.MIN_POST_GAP).isoformat())) == []
    assert chk(_reply("Model has Haaland at 8.0 for GW7.", OK_KEYS[:1]), state=lahella) == []


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


def _mod(gap=2.5, dl_h=16):
    return {"gw": 7, "deadline_utc": (NOW + timedelta(hours=dl_h)).isoformat(), "sections": {
        "captain_top5": {"rows": [{"key": "haaland-mci", "name": "Haaland", "player_id": 1}]},
        "xp_top5": {"rows": [{"key": "haaland-mci", "player_id": 1}, {"key": "cherki-mci", "player_id": 2}]},
        "last_gw": {"available": True, "gw": 6}}}


def _vals(gap=2.5):
    vals = dict(V)
    entry = "https://fantasy.premierleague.com/entry/116920/event/6"
    vals["captain_top5.haaland-mci.gw_xp"] = {"text": "8.0", "value": 8.0,
                                              "public_url": "https://goaliq.app/fpl/expected-points#gw-xp"}
    vals["xp_top5.haaland-mci.gw_xp"] = {"text": "8.0", "value": 8.0, "public_url": "https://goaliq.app/fpl/expected-points#gw-xp"}
    vals["xp_top5.cherki-mci.gw_xp"] = {"text": "x", "value": 8.0 - gap, "public_url": "https://goaliq.app/fpl/expected-points#gw-xp"}
    vals["last_gw.entry_points"] = {"text": "57", "public_url": entry}
    vals["last_gw.fpl_average"] = {"text": "58", "public_url": entry}
    return vals


@pytest.mark.parametrize("gap,perhe", [(2.5, bot.CAPTAIN_CLEAR), (0.3, bot.CAPTAIN_CLOSE)])
def test_varmuuslause_vain_kun_ero_kantaa(monkeypatch, gap, perhe):
    monkeypatch.setattr(bot, "_transfer_cost", lambda gw: 0)
    it = [i for i in bot.fallback_items(_mod(), _vals(gap), NOW, _state()) if i["topic"] == "captain"][0]
    assert any(it["text"] == tpl.format(gw=7, name="Haaland", xp="8.0", p10="32%") for tpl in perhe), it["text"]


def test_tulospostaus_suunta_ja_miinuspisteet(monkeypatch):
    monkeypatch.setattr(bot, "_transfer_cost", lambda gw: 0)
    rec = [i for i in bot.fallback_items(_mod(), _vals(), NOW, _state()) if i["topic"] == "recap"][0]
    assert "below" in rec["text"] and rec["link"].startswith("https://fantasy.premierleague.com/")
    assert rec["card"] is None
    monkeypatch.setattr(bot, "_transfer_cost", lambda gw: 4)
    assert not [i for i in bot.fallback_items(_mod(), _vals(), NOW, _state()) if i["topic"] == "recap"]
    monkeypatch.setattr(bot, "_transfer_cost", lambda gw: None)
    assert not [i for i in bot.fallback_items(_mod(), _vals(), NOW, _state()) if i["topic"] == "recap"]


def test_varapostaukset_lapaisevat_portin(monkeypatch):
    monkeypatch.setattr(bot, "_transfer_cost", lambda gw: 0)
    mod, vals = _mod(), _vals()
    items = bot.fallback_items(mod, vals, NOW, _state())
    assert {i["slot"] for i in items} == {"deadline:gw7", "recap:gw6"}
    for it in items:
        text, links = bot.prepare(it, "t")
        assert gate.check({**it, "text": text}, values=vals, gw=7, now=NOW, state=_state(),
                          blocklist=set(), phrases=gate.rejected_phrases()) == [], text
    # slot kerran: toinen ajo ei tee samaa postausta
    assert bot.fallback_items(mod, vals, NOW, _state(posted_slots=["deadline:gw7", "recap:gw6"])) == []
    # deadline-ikkunan ulkopuolella ei kapteenipostausta
    late = _mod(dl_h=1)
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


# ---------------------------------------------------------------- tyonkulun turvainvariantit

def _wf():
    import yaml
    teksti = (ROOT / ".github" / "workflows" / "bsky-bot.yml").read_text(encoding="utf-8")
    return teksti, yaml.safe_load(teksti)


def test_aivoilla_vain_lukuoikeus_eika_bluesky_tunnusta():
    import yaml
    teksti, doc = _wf()
    aivot = doc["jobs"]["aivot"]
    assert all(v in ("read", "none") for v in aivot["permissions"].values())
    co = [s for s in aivot["steps"] if str(s.get("uses", "")).startswith("actions/checkout")]
    assert co and all((s.get("with") or {}).get("persist-credentials") is False for s in co)
    assert "BLUESKY" not in yaml.safe_dump(aivot)
    claude = [s for s in aivot["steps"] if "claude-code-action" in str(s.get("uses", ""))][0]
    tyokalut = claude["with"]["claude_args"].split('--allowedTools "', 1)[1].split('"', 1)[0]
    assert "Bash" not in tyokalut, "aivot eivat aja koodia: vain Read/Write/haku"
    assert "ANTHROPIC_API_KEY" not in teksti and "anthropic_api_key" not in teksti


def test_releen_kaynnistamat_aivot_eivat_kaadu_bottiesteeseen():
    # 17.10: rele dispatchaa GITHUB_TOKENilla -> actor github-actions[bot]; ilman allowed_bots-rivia
    # claude-code-action kaatuu ennen mallia (3/3 ajoa 16.-17.10). Vain tama botti, ei '*'.
    _t, doc = _wf()
    aivot = doc["jobs"]["aivot"]
    claude = [s for s in aivot["steps"] if "claude-code-action" in str(s.get("uses", ""))][0]
    botit = [b.strip() for b in str(claude["with"].get("allowed_bots", "")).split(",") if b.strip()]
    assert botit == ["github-actions"], botit


def test_salasana_vain_julkaisuaskeleelle():
    import yaml
    _t, doc = _wf()
    for nimi, job in doc["jobs"].items():
        for s in job["steps"]:
            env = yaml.safe_dump(s.get("env") or {})
            if "BLUESKY_APP_PASSWORD" in env:
                assert nimi == "julkaise" and "bsky_bot publish" in str(s.get("run")), s


@pytest.mark.parametrize("tunti,viimeksi_h,deadline_h,odotus", [
    (9, None, 40, True), (17, None, 40, True), (12, None, 40, False),
    (12, None, 5, True), (12, 1, 5, False), (9, 1, 40, False), (12, None, -1, False),
])
def test_aivojen_ajopaatos(tunti, viimeksi_h, deadline_h, odotus):
    now = datetime(2026, 10, 17, tunti, 37, tzinfo=timezone.utc)
    s = _state()
    if viimeksi_h is not None:
        s["last_think_at"] = (now - timedelta(hours=viimeksi_h)).isoformat()
    assert bot.should_think(now, s, now + timedelta(hours=deadline_h)) is odotus
    assert bot.should_think(now, s, now + timedelta(hours=deadline_h), force=True) is True


class _Sessio:
    def __init__(self, ilmoitukset):
        self.n = ilmoitukset

    def notifications(self, limit=50):
        return self.n


def _ilmo(uri, teksti, reason="mention"):
    return {"uri": uri, "cid": "c" + uri[-1], "reason": reason, "indexedAt": NOW.isoformat(),
            "author": {"handle": "fan.bsky.social"}, "record": {"text": teksti}}


def test_mentioihin_vastataan_vain_tunnistettuun_kysymykseen():
    mod = {"gw": 7, "sections": {
        "player_lookup": {"rows": [{"key": "saka-ars", "name": "Saka", "team": "ARS"},
                                   {"key": "thomas-cov", "name": "Thomas", "team": "COV"},
                                   {"key": "wilson-ful", "name": "Wilson", "team": "FUL"},
                                   {"key": "wilson-new", "name": "Wilson", "team": "NEW"}]},
        "captain_top5": {"rows": [{"key": "haaland-mci", "name": "Haaland"}]}}}
    vals = {**V, "player_lookup.saka-ars.gw_xp": {"text": "5.3", "public_url": "x"},
            "player_lookup.thomas-cov.gw_xp": {"text": "4.3", "public_url": "x"},
            "player_lookup.wilson-ful.gw_xp": {"text": "4.1", "public_url": "x"}}
    s = _state()
    ses = _Sessio([_ilmo("at://a/1", "@goaliqapp is Saka worth a transfer?"),
                   _ilmo("at://a/2", "@goaliqapp who should I captain?"),
                   _ilmo("at://a/3", "@goaliqapp nice work"),
                   _ilmo("at://a/4", "liked", reason="like"),
                   _ilmo("at://a/5", "@goaliqapp your captain blanked lol"),
                   _ilmo("at://a/6", "@goaliqapp did you see Thomas Frank's team?"),
                   _ilmo("at://a/7", "@goaliqapp Wilson for GW7?"),
                   _ilmo("at://a/8", "@goaliqapp Saka or Thomas for points?")])
    out = bot.mention_items(ses, mod, vals, s)
    assert [o["target"]["uri"] for o in out] == ["at://a/1", "at://a/2"]
    assert "Saka (ARS)" in out[0]["text"] and "Haaland" in out[1]["text"]
    assert set(s["handled_notifications"]) == {f"at://a/{i}" for i in (1, 2, 3, 5, 6, 7, 8)}
    for o in out:   # pohjavastaus laapaisee portin (yksi luku, ei linkkia, ei tuotenimea)
        assert gate.check(o, values=vals, gw=7, now=NOW, state=_state(), blocklist=set(),
                          phrases=gate.rejected_phrases()) == [], o["text"]
    # toinen ajo: samaan ilmoitukseen ei vastata uudelleen
    assert bot.mention_items(ses, mod, vals, s) == []


@pytest.mark.parametrize("teksti", [
    "Haaland is a crucial pick at 8.0 this week.",
    "Haaland is not just a captain, he's a lock at 8.0.",
    "Best odds of the week: Haaland at 8.0.",
    "Here's the thing: Haaland at 8.0.",
    "Haaland at 8.0!! Huge!",
])
def test_tyylikiellot(teksti):
    probs = chk(_post(teksti, ["captain_top5.haaland-mci.gw_xp"]))
    assert any("tyyli" in p or "huutomerk" in p for p in probs), probs


@pytest.mark.parametrize("teksti", [
    # 21.10 julkaistu sellaisenaan: luettiin myyntikehotukseksi (malli piti hanta GW8:n FWD #3:na).
    "Pedro at that price is a hard sell for me. The model has him on 4.4 for GW8, fine but not a must-have.",
    "Vuskovic is getting the best-value pick treatment today and I buy it.",
    "Still not sold on Delap.",
    "Saka at that price is a tough sell.",
])
def test_siirtoverbi_kuvaannollisena_hylataan(teksti):
    probs = chk({"kind": "post", "text": teksti, "keys": []})
    assert any("siirtoverbi" in p for p in probs), probs


@pytest.mark.parametrize("teksti", [
    "Saka owners, waiting is the cheap move. Selling now only makes sense if you already wanted out.",
    "Not at that price for me. Who's buying Pedro this week?",
    "Holding Bruno into GW8.",
])
def test_kirjaimellinen_siirtokieli_paasee(teksti):
    probs = chk({"kind": "post", "text": teksti, "keys": []})
    assert not any("siirtoverbi" in p for p in probs), probs


@pytest.mark.parametrize("teksti", [
    "Rate my team is free on goaliq.app.",
    "Free mini-league tool with head-to-head odds for your league.",
    "Track three players on the watchlist, no sign-in needed.",
    "Our fit checker works with no login.",
    "Chip timing for free: plan your Wildcard.",
])
def test_premium_tyokalua_ei_luvata_ilmaiseksi(teksti):
    # 17.10.2026 Villen paatos: henkilokohtaiset tyokalut ovat Premiumia.
    probs = chk({"kind": "post", "text": teksti, "keys": []})
    assert any("Premium-tyokalun ilmaiseksi" in p for p in probs), probs


@pytest.mark.parametrize("teksti", [
    "Free Hit or Wildcard this week? The planner likes holding.",
    "One free transfer and a bench problem. Rate my team says hold.",
    "Clean sheet chances are free on goaliq.app, no sign-in.",
    "Your rival has Haaland. Do you?",
])
def test_fpl_termit_ja_ilmainen_sisalto_paasevat(teksti):
    probs = chk({"kind": "post", "text": teksti, "keys": []})
    assert not any("Premium-tyokalun ilmaiseksi" in p for p in probs), probs


def test_lukukatto_vastaus_yksi_postaus_kaksi():
    keys = ["captain_top5.haaland-mci.gw_xp", "captain_top5.haaland-mci.p_10plus"]
    assert any("liikaa lukuja" in p for p in chk(_reply("Haaland 8.0 and 32% for GW7.", keys)))
    assert chk(_post("Haaland 8.0 and a 32% chance of 10+ in GW7.", keys)) == []
    k3 = keys + ["cs_top.ars.cs_pct"]
    assert any("liikaa lukuja" in p for p in chk(_post("Haaland 8.0, 32% for 10+, Arsenal 49%.", k3)))


def test_luvun_sivu_on_linkin_sivu():
    """6a: ensimmaiset pohjat linkittivat best-captain-sivulle, jolla 8.0 ei nay (julkaisutarkistaja 16.10)."""
    k = ["captain_top5.haaland-mci.gw_xp"]
    assert chk(_post("Haaland tops the model at 8.0.", k, link="/fpl/expected-points#gw-xp")) == []
    probs = chk(_post("Haaland tops the model at 8.0.", k, link="/fpl/best-captain"))
    assert any("nakyy sivulla" in p for p in probs), probs
    assert any("ilman linkkia" in p for p in chk(_post("Haaland tops the model at 8.0.", k, link=None)))
    assert chk(_post("Everyone's on Haaland this week. Fair enough.", [], link=None)) == []


def test_pyytamattomat_vastaukset_oletuksena_pois(monkeypatch):
    import importlib
    monkeypatch.delenv("BSKY_OUTBOUND_REPLIES_PER_DAY", raising=False)
    g2 = importlib.reload(gate)
    try:
        assert g2.OUTBOUND_REPLIES_PER_DAY == 0
        probs = g2.check(_reply("Model has Haaland at 8.0 for GW7.", ["captain_top5.haaland-mci.gw_xp"]),
                         values=V, gw=7, now=NOW, state=_state(), blocklist=set(), phrases=[])
        assert any("kiintio" in p for p in probs)
    finally:
        importlib.reload(gate)


def test_mention_estolista_ja_ika():
    t = {"uri": "at://m/1", "cid": "c", "handle": "ffscoutfpl.bsky.social",
         "created_at": (NOW - timedelta(hours=1)).isoformat()}
    it = {"kind": "mention_reply", "text": "The model has Haaland at 8.0 for GW7.",
          "keys": ["captain_top5.haaland-mci.gw_xp"], "target": t}
    assert any("estolistalla" in p for p in chk(it, blocked={"ffscoutfpl.bsky.social"}))
    old = {**it, "target": {**t, "handle": "fan.bsky.social", "created_at": (NOW - timedelta(hours=9)).isoformat()}}
    assert any("4 h" in p for p in chk(old))


def test_bio_lause_omana_lauseenaan():
    s = " Posts and replies are automated."
    assert bsky.bio_with_suffix("Beat the model: code jgi6j9", s) == "Beat the model: code jgi6j9. Posts and replies are automated."
    rikki = "Beat the model: code jgi6j9 Posts and replies are automated."
    assert bsky.bio_with_suffix(rikki, s) == "Beat the model: code jgi6j9. Posts and replies are automated."
    ok = "Free at goaliq.app. Posts and replies are automated."
    assert bsky.bio_with_suffix(ok, s) == ok


# ---------------------------------------------------------------- X-jono (Villen paatos 17.10)

_LINK = "https://goaliq.app/fpl/expected-points?utm_source=bluesky&utm_medium=partner&utm_campaign=captain&utm_content=2026101710-0#gw-xp"


def _row(**kw):
    r = {"at": (NOW - timedelta(hours=1)).isoformat(), "uri": "at://did:plc:abc/app.bsky.feed.post/3mxzcg",
         "kind": "post", "topic": "captain", "dry_run": False, "source": "rule", "utm_content": "2026101710-0",
         "text": "Armband's sorted for GW7. The model has Haaland at 8.0 expected points. goaliq.app/fpl/expected-points",
         "links": {"goaliq.app/fpl/expected-points": _LINK}}
    r.update(kw)
    return r


def test_x_versio_vaihtaa_lahteen_ja_sailyttaa_ankkurin():
    x = bot.x_version(_row())
    assert "utm_source=x&" in x and "utm_source=bluesky" not in x and x.endswith("#gw-xp")
    assert x.startswith("Armband's sorted for GW7.")
    assert bot.x_length(x) == len(x) - len(x.split(" ")[-1]) + 23


def test_x_versio_ilman_tallennettua_linkkia_rakennetaan_polusta():
    x = bot.x_version(_row(links=None))
    assert "https://goaliq.app/fpl/expected-points?utm_source=x&" in x


def test_x_versio_ylipitka_ei_katkaista():
    assert bot.x_version(_row(text="a" * 270 + " goaliq.app/fpl/expected-points")) is None


def test_x_jonoon_vain_tuoreet_oikeat_postaukset():
    rows = [_row(), _row(kind="reply", uri="at://d/app.bsky.feed.post/r1"), _row(dry_run=True, uri=None),
            _row(uri="at://d/app.bsky.feed.post/vanha", at=(NOW - timedelta(hours=7)).isoformat()),
            _row(uri="at://d/app.bsky.feed.post/tehty")]
    got = bot.pending_x_mirror(rows, {"x_mirrored": ["at://d/app.bsky.feed.post/tehty"]}, NOW)
    assert [r["uri"] for r in got] == ["at://did:plc:abc/app.bsky.feed.post/3mxzcg"]


def test_kierroskatsaus_ei_x_jonoon_koska_x_viikkoketju_tekee_sen():
    """19.10: muuten samasta kierroksesta tulisi X-jonoon kaksi katsausta (julkaisutarkistaja)."""
    rows = [_row(topic="recap", uri="at://d/app.bsky.feed.post/recap"), _row()]
    got = bot.pending_x_mirror(rows, {}, NOW)
    assert [r["uri"] for r in got] == ["at://did:plc:abc/app.bsky.feed.post/3mxzcg"]


def test_x_issue_osoitettu_villelle_ja_linkki_blueskyhyn():
    p = bot.x_issue(_row(), bot.x_version(_row()))
    assert p["assignees"] == ["Veikkoville"] and p["labels"] == ["x-jono"]
    assert "https://bsky.app/profile/goaliqapp.bsky.social/post/3mxzcg" in p["body"]
    assert "utm_source=x" in p["body"]


def test_x_mirror_kirjaa_tehdyn_eika_tee_kahdesti(monkeypatch, tmp_path):
    state = _state()
    monkeypatch.setattr(bot, "load_state", lambda: state)
    monkeypatch.setattr(bot, "read_log", lambda: [_row()])
    monkeypatch.setattr(bot, "save_json", lambda path, obj: None)
    tehdyt = []
    bot.cmd_x_mirror(NOW, create=lambda p: tehdyt.append(p) or "url")
    bot.cmd_x_mirror(NOW, create=lambda p: tehdyt.append(p) or "url")
    assert len(tehdyt) == 1 and state["x_mirrored"] == [_row()["uri"]]


def test_x_mirror_epaonnistunut_ei_merkitse(monkeypatch):
    state = _state()
    monkeypatch.setattr(bot, "load_state", lambda: state)
    monkeypatch.setattr(bot, "read_log", lambda: [_row()])
    monkeypatch.setattr(bot, "save_json", lambda path, obj: None)

    def kaatuu(p):
        raise RuntimeError("403")
    bot.cmd_x_mirror(NOW, create=kaatuu)
    assert not state.get("x_mirrored")


_KUVA = "https://cdn.bsky.app/img/feed_fullsize/plain/did:plc:abc/bafkreikortti"


def test_kortin_kuva_haetaan_postauksesta():
    kuvat = {"posts": [{"embed": {"$type": "app.bsky.embed.images#view", "images": [{"fullsize": _KUVA}]}}]}
    media = {"posts": [{"embed": {"media": {"images": [{"fullsize": _KUVA}]}}}]}
    ulkoinen = {"posts": [{"embed": {"external": {"thumb": _KUVA}}}]}
    for doc in (kuvat, media, ulkoinen):
        assert bot.card_image_url("at://did:plc:abc/app.bsky.feed.post/x", fetch=lambda u, d=doc: d) == _KUVA
    assert bot.card_image_url("at://x/app.bsky.feed.post/y", fetch=lambda u: {"posts": [{}]}) is None

    def kaatuu(u):
        raise OSError("verkko")
    assert bot.card_image_url("at://x/app.bsky.feed.post/y", fetch=kaatuu) is None
    assert bot.card_image_url(None) is None


def test_x_issue_sisaltaa_kortin_kuvan():
    p = bot.x_issue(_row(card="best-captain"), bot.x_version(_row()), _KUVA)
    assert f"![kortti]({_KUVA})" in p["body"] and f"Suora linkki kuvaan: {_KUVA}" in p["body"]
    ilman = bot.x_issue(_row(card="best-captain"), bot.x_version(_row()), None)
    assert "kuvaa ei saatu haettua" in ilman["body"] and "bsky.app/profile" in ilman["body"]
    assert "Kortti" not in bot.x_issue(_row(), bot.x_version(_row()))["body"]


def test_x_mirror_hakee_kortin_kuvan(monkeypatch):
    """Kutsupaikka: ilman card_image_url-kutsua cmd_x_mirrorissa kuva ei tule issueen."""
    state = _state()
    monkeypatch.setattr(bot, "load_state", lambda: state)
    monkeypatch.setattr(bot, "read_log", lambda: [_row(card="team-news")])
    monkeypatch.setattr(bot, "save_json", lambda path, obj: None)
    tehdyt = []
    bot.cmd_x_mirror(NOW, create=lambda p: tehdyt.append(p) or "url",
                     image_fetch=lambda u: {"posts": [{"embed": {"images": [{"fullsize": _KUVA}]}}]})
    assert len(tehdyt) == 1 and f"![kortti]({_KUVA})" in tehdyt[0]["body"]


def test_julkaisu_tallentaa_linkin_ja_tyonkulku_ajaa_x_jonon():
    import inspect
    assert '"links": links or None' in inspect.getsource(bot.cmd_publish)
    _t, doc = _wf()
    job = doc["jobs"]["julkaise"]
    assert job["permissions"].get("issues") == "write"
    askel = [s for s in job["steps"] if "bsky_bot x-mirror" in str(s.get("run"))]
    assert askel and "GITHUB_TOKEN" in str(askel[0].get("env"))
    nimet = [s.get("name") for s in job["steps"]]
    assert nimet.index(askel[0]["name"]) > nimet.index("Julkaise (portti jokaiselle)")
    assert nimet.index(askel[0]["name"]) < nimet.index("Tila mainiin")


# 18.10: aivot ajoivat 17.10 onnistuneesti mutta queue.json puuttui -> julkaisu luki "ei postattavaa", ajo vihrea.
_SALAISUUS = "ghp_" + "x" * 8 + "SALAINEN"


def _exec(tmp_path, write_target=None, error=False):
    msgs = [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "/proc/self/environ"}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": _SALAISUUS, "is_error": error}]}},
    ]
    if write_target:
        msgs.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t2", "name": "Write", "input": {"file_path": write_target, "content": _SALAISUUS}}]}})
    msgs.append({"type": "result", "subtype": "success", "num_turns": 3, "is_error": False})
    p = tmp_path / "exec.json"
    p.write_text(__import__("json").dumps(msgs), encoding="utf-8")
    return p


def test_puuttuva_jono_on_virhe_ei_hiljainen_nolla(tmp_path, capsys):
    rc = bot.cmd_brain_trace(_exec(tmp_path), tmp_path / "queue.json")
    out = capsys.readouterr().out
    assert rc == 1 and "::error::" in out


@pytest.mark.parametrize("sisalto,odotus", [("[]", 0), ('[{"kind": "post"}]', 0), ('{"kind": "post"}', 1), ("rikki", 1)])
def test_jonon_muoto(tmp_path, sisalto, odotus):
    q = tmp_path / "queue.json"
    q.write_text(sisalto, encoding="utf-8")
    assert bot.cmd_brain_trace(_exec(tmp_path, write_target=str(q)), q) == odotus


def test_kulku_nayttaa_vain_tyokalujen_nimet(tmp_path, capsys):
    q = tmp_path / "queue.json"
    q.write_text("[]", encoding="utf-8")
    bot.cmd_brain_trace(_exec(tmp_path, write_target="/tmp/bsky/queue.json", error=True), q)
    out = capsys.readouterr().out
    assert "Read VIRHE" in out and "Write(queue.json) ok" in out
    assert _SALAISUUS not in out and "environ" not in out


def test_kulku_kestaa_actionin_init_rivin(tmp_path, capsys):
    """20.10: claude-code-action@v1 (db77d4d) kirjoitti execution_fileen init-rivin, jonka message on
    merkkijono. Kulku kaatui AttributeErroriin, ja aivojen jono jai siirtamatta (0 postausta).
    Rivi on sanatarkasti tuotannon ajosta 39466306906."""
    import json
    p = _exec(tmp_path, write_target="/tmp/bsky/queue.json")
    msgs = json.loads(p.read_text(encoding="utf-8"))
    msgs.insert(0, {"type": "system", "subtype": "init", "message": "Claude Code initialized",
                    "model": "claude-sonnet-5-5"})
    p.write_text(json.dumps(msgs), encoding="utf-8")
    q = tmp_path / "queue.json"
    q.write_text("[]", encoding="utf-8")
    assert bot.cmd_brain_trace(p, q) == 0
    assert "Write(queue.json) ok" in capsys.readouterr().out


def test_jono_siirretaan_vaikka_kulku_kaatuisi():
    """Kulku on diagnostiikkaa. Sen kaatuminen ei saa pudottaa aivojen jonoa: 20.10 upload-artifact
    skippautui kaatuneen kulun takia ja julkaisu ei saanut mitaan."""
    _t, doc = _wf()
    askel = [s for s in doc["jobs"]["aivot"]["steps"] if str(s.get("uses", "")).startswith("actions/upload-artifact")]
    assert len(askel) == 1
    ehto = str(askel[0].get("if"))
    assert "!cancelled()" in ehto and "steps.paata.outputs.think == 'true'" in ehto


def test_workflow_ajaa_kulun_aivojen_jalkeen():
    wf = (Path(__file__).resolve().parents[1] / ".github/workflows/bsky-bot.yml").read_text(encoding="utf-8")
    assert "id: aivot_run" in wf
    assert "python -m scripts.bsky_bot brain-trace --exec \"$EXEC_FILE\" --queue /tmp/bsky/queue.json" in wf
    assert "steps.aivot_run.outputs.execution_file" in wf
    assert wf.index("id: aivot_run") < wf.index("brain-trace") < wf.index("upload-artifact")


def test_aivot_eivat_kayta_aliagenttia():
    """18.10: aivot antoivat ehdotukset bsky-tarkistaja-aliagentille (Task/Agent), joka ajoi taustalla; ajo paattyi
    ennen vastausta eika queue.json syntynyt koskaan (17.10 ja 18.10 09 UTC). Tarkistus tehdaan samassa ajossa."""
    wf = (Path(__file__).resolve().parents[1] / ".github/workflows/bsky-bot.yml").read_text(encoding="utf-8")
    allowed = wf.split("--allowedTools", 1)[1].split("\n", 1)[0]
    assert "Task" not in allowed and "Agent" not in allowed
    prompt = wf.split("prompt: |", 1)[1]
    assert "(Task tool)" not in prompt and "subagent (" not in prompt
    assert ".claude/agents/bsky-tarkistaja.md" in prompt and "Write [] if nothing passes" in prompt


class _PostausSessio:
    postit: list[str] = []

    def __init__(self, *a, **k):
        pass

    def create_post(self, text, **kw):
        _PostausSessio.postit.append(text)
        return {"uri": f"at://goaliq/{len(_PostausSessio.postit)}", "cid": "c"}


def test_julkaisu_levittaa_aivojen_postaukset_ja_jono_vanhenee(monkeypatch, tmp_path):
    """22.10: aivot ehdottivat 2-3 postausta ja julkaisu postasi ne samalla sekunnilla. Nyt ajo postaa yhden,
    loput odottavat tilassa seuraaviin tunnin ajoihin, uusi aivojen jono korvaa odottavat ja odottava vanhenee."""
    import json
    monkeypatch.setattr(bot, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(bot, "LOG_PATH", tmp_path / "posted.jsonl")
    monkeypatch.setattr(bot, "fresh_module", lambda out: ({"gw": 7}, V, ""))
    monkeypatch.setattr(bot, "mention_items", lambda *a: [])
    monkeypatch.setattr(bot, "fallback_items", lambda *a: [])
    monkeypatch.setattr(bot, "blocklist", lambda: set())
    monkeypatch.setattr(gate, "rejected_phrases", lambda: [])
    monkeypatch.setattr(bsky, "Session", _PostausSessio)
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "x")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(_PostausSessio, "postit", [])
    (tmp_path / "state.json").write_text(json.dumps({"bot_label_at": "2026-10-16T00:00:00+00:00"}), encoding="utf-8")
    a, b, c, d = ("Arsenal are the clean sheet everyone is circling this week.",
                  "Nobody mentions Brentford at home and they should.",
                  "The template keeper is about to lose his place to a cheaper option.",
                  "Midfield is where the armband debate gets interesting this time.")
    q = tmp_path / "queue.json"
    t0 = datetime(2026, 10, 16, 9, 50, tzinfo=timezone.utc)

    def _tag(*xs):
        return [f"{x} {bot.POST_HASHTAG}" for x in xs]   # julkaisu lisaa tunnisteen (22.10)

    def aja(h, jono=None):
        if jono is not None:
            q.write_text(json.dumps([{"kind": "post", "topic": "player", "text": x} for x in jono]), encoding="utf-8")
        elif q.exists():
            q.unlink()
        bot.cmd_publish(q, dry=False, thought=jono is not None, now=t0 + timedelta(hours=h))
        return [p["text"] for p in bot.load_state()["pending_posts"]]

    assert aja(0, [a, b, c]) == [b, c] and _PostausSessio.postit == _tag(a)
    assert aja(1) == [b, c] and _PostausSessio.postit == _tag(a)              # alle 3 h: ei mitaan
    assert aja(3) == [c] and _PostausSessio.postit == _tag(a, b)
    assert aja(4, [d]) == [d] and _PostausSessio.postit == _tag(a, b)         # uusi jono korvaa c:n, d odottaa valia
    assert aja(10.1) == [] and _PostausSessio.postit == _tag(a, b)            # d vanheni (yli 6 h)
    ajat = [datetime.fromisoformat(json.loads(r)["at"]) for r in (tmp_path / "posted.jsonl").read_text().splitlines()]
    assert ajat[1] - ajat[0] >= gate.MIN_POST_GAP


def test_postausvali_alkaa_lokista_kun_tilassa_ei_ole_aikaa(monkeypatch, tmp_path):
    """Ennen 22.10 tilaan ei kirjattu postausaikaa: ensimmainen ajo ei saa postata heti edellisen perään."""
    import json
    monkeypatch.setattr(bot, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(bot, "LOG_PATH", tmp_path / "posted.jsonl")
    rivit = [{"at": "2026-10-22T11:52:02+00:00", "kind": "post", "uri": "at://goaliq/1"},
             {"at": "2026-10-22T12:10:00+00:00", "kind": "mention_reply", "uri": "at://goaliq/2"},
             {"at": "2026-10-22T12:20:00+00:00", "kind": "post", "uri": None}]   # kuivaharjoitus
    (tmp_path / "posted.jsonl").write_text("\n".join(json.dumps(r) for r in rivit) + "\n", encoding="utf-8")
    assert bot.load_state()["last_post_at"] == "2026-10-22T11:52:02+00:00"


def test_tunniste_saa_tag_facetin_tavuoffseteilla():
    """Ilman facettia #FPL on pelkkaa tekstia: ei hashtag-sivua eika #-syotteita (22.10)."""
    t = "Groß is the pick. goaliq.app/fpl/expected-points #FPL"
    f = bsky.tag_facets(t)
    assert len(f) == 1 and f[0]["features"] == [{"$type": "app.bsky.richtext.facet#tag", "tag": "FPL"}]
    b = t.encode("utf-8")
    assert b[f[0]["index"]["byteStart"]:f[0]["index"]["byteEnd"]] == b"#FPL"
    assert bsky.tag_facets("goaliq.app/fpl#clean-sheets and C# code") == []


def test_create_post_kirjoittaa_tunnisteen_facetin(monkeypatch):
    s = object.__new__(bsky.Session)
    s.did = "did:plc:goaliq"
    kirjattu = {}
    monkeypatch.setattr(s, "_post", lambda path, **kw: kirjattu.update(kw["json"]["record"]) or {"uri": "u"})
    s.create_post("Arsenal again. goaliq.app/fpl #FPL", links={"goaliq.app/fpl": "https://goaliq.app/fpl?utm_source=bluesky"})
    tyypit = [x["features"][0]["$type"] for x in kirjattu["facets"]]
    assert tyypit == ["app.bsky.richtext.facet#link", "app.bsky.richtext.facet#tag"]


def test_tunniste_vain_omaan_postaukseen_ja_kun_mahtuu():
    assert bot.prepare({"kind": "post", "text": "Arsenal again."}, "c")[0] == "Arsenal again. #FPL"
    assert bot.prepare({"kind": "post", "text": "Arsenal LINK again.", "link": "/fpl"}, "c")[0] == \
        "Arsenal goaliq.app/fpl again. #FPL"
    assert bot.prepare({"kind": "reply", "text": "Arsenal again."}, "c")[0] == "Arsenal again."
    assert bot.prepare({"kind": "mention_reply", "text": "Arsenal again."}, "c")[0] == "Arsenal again."
    assert bot.prepare({"kind": "post", "text": "Arsenal again. #GW8"}, "c")[0] == "Arsenal again. #GW8"
    assert bot.prepare({"kind": "post", "text": "Saka is the #2 captain."}, "c")[0] == "Saka is the #2 captain. #FPL"
    taysi = "a" * (gate.MAX_CHARS - 4)
    assert bot.prepare({"kind": "post", "text": taysi}, "c")[0] == taysi      # ei ylita 300:aa, ei kaada postausta


def test_x_versio_pudottaa_tunnisteen_jos_raja_ylittyy():
    teksti = "a" * 254 + " goaliq.app/fpl/expected-points #FPL"
    x = bot.x_version(_row(text=teksti))
    assert x is not None and not x.endswith("#FPL") and x.endswith(_LINK.replace("utm_source=bluesky", "utm_source=x"))
    assert bot.x_version(_row(text="Arsenal again. goaliq.app/fpl/expected-points #FPL")).endswith(" #FPL")
