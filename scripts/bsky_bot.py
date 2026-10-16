"""GoalIQ:n Bluesky-botti (16.10.2026, Villen GO: "rakenna automaattinen postausbotti, replyt jne.
bluesky only, ei x" + "botin pitaa tietaa mitka postaukset herattavat kiinnostusta ... saa asiakkaita
... lukea ennalta ... ymmartaa fplaa taysin ja valioliigaa ... grafiikat ... lukea X:sta signaaleja").

Kolme alikomentoa, ja vastuu on jaettu niin ettei kirjoittaja voi ohittaa porttia:

  context  Ennakoiva tilannekuva aivoille (Claude-agentti, .github/workflows/bsky-bot.yml): kierros,
           deadline, tarkistetut luvut (reply-moduuli = ainoa lukija), FPL:n hinta- ja statussignaalit,
           tupla/tyhjat kierrokset, Blueskyn ja X:n (vain luku) FPL-tilien tuoreet aiheet tykkayksineen,
           omien postausten tulokset ja kiintiot. Kirjoittaa briefing.json + briefing.md.
  publish  Ottaa ehdotukset (aivojen queue.json + deterministiset varapostaukset + mentioihin
           vastaukset), ajaa JOKAISEN src/marketing/bsky_gate.py:n lapi, renderoi kortin sivun omasta
           jakokortista, postaa, kirjaa lokiin ja tilaan. Ilman BLUESKY_APP_PASSWORDia = kuivaharjoitus.
  perf     Mittaa omien postausten kiinnostuksen (tykkaykset, jaot, vastaukset, lainaukset) ja
           seuraajat aiheittain -> data/bsky_performance.json. Aivot lukevat taulukon ja painottavat
           toimivaa (oppiminen). Asiakkaat: linkit kantavat utm_source=bluesky&utm_medium=partner
           &utm_campaign=<aihe>&utm_content=<postaus>, jolloin tili saa partner=bluesky.

Aivoilla ei ole Bluesky-tunnusta eika kirjoitusoikeutta: ne tuottavat vain dataa (queue.json), ja
publish ajetaan mainin koodista.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from src.marketing import bsky  # noqa: E402
from src.marketing import bsky_gate as gate  # noqa: E402

DATA = config.DATA_DIR
STATE_PATH = DATA / "bsky_state.json"
LOG_PATH = DATA / "bsky_posted.jsonl"
PERF_PATH = DATA / "bsky_performance.json"
TARGETS_PATH = DATA / "bsky_targets.json"
BLOCK_PATH = DATA / "bsky_blocklist.json"
SITE = "https://goaliq.app"
TOPICS = ("captain", "clean_sheets", "differential", "template", "recap", "track_record", "injury",
          "price", "fixtures", "prediction", "player", "reply_question", "mention")
SIGNAL_MAX_AGE = timedelta(hours=12)
BOT_BIO = " Posts and replies are automated."   # julkaisutarkistaja 16.10, ehto mention-vastauksille


# ---------------------------------------------------------------- tila ja loki

def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def load_state() -> dict:
    s = load_json(STATE_PATH, {})
    for k, v in (("posted_slots", []), ("replied_uris", []), ("replied_roots", []),
                 ("author_last_reply", {}), ("daily", {}), ("recent_texts", []),
                 ("handled_notifications", [])):
        s.setdefault(k, v)
    return s


def read_log() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    return [json.loads(x) for x in LOG_PATH.read_text(encoding="utf-8").splitlines() if x.strip()]


def blocklist() -> set[str]:
    return {a["handle"].lower() for a in load_json(BLOCK_PATH, {}).get("accounts") or []}


# ---------------------------------------------------------------- luvut (yksi lukija)

def fresh_module(out_dir: Path) -> tuple[dict | None, dict, str]:
    """Rakentaa reply-moduulin (lempea tila) ja lukee sen AINOAN lukijan kautta.

    Palauttaa (moduuli, {avain: arvo julkisella reitilla}, virhe). Ei moduulia = ei lukuja =
    botti postaa vain lukuja sisaltamattoman tekstin tai ei mitaan.
    """
    from scripts.build_reply_module import build
    from src.marketing import reply_module as rm
    try:
        rc = build(None, False, out_dir, strict=False)
    except Exception as e:  # noqa: BLE001
        return None, {}, f"build: {e!r}"
    if rc != 0:
        return None, {}, f"build exit {rc}"
    files = sorted(out_dir.glob("gw*.json"))
    if not files:
        return None, {}, "moduulia ei kirjoitettu"
    gw = int(re.findall(r"\d+", files[-1].stem)[0])
    try:
        mod = rm.load_reply_module(gw, module_dir=out_dir)
    except rm.ReplyModuleRefused as e:
        return None, {}, f"refused: {e}"
    values = {k: v for k, v, _r, _s in rm.iter_values(mod.get("sections") or {}) if v.get("public_url")}
    return mod, values, ""


def rows(mod: dict, section: str) -> list[dict]:
    return ((mod.get("sections") or {}).get(section) or {}).get("rows") or []


def val(values: dict, key: str) -> str | None:
    v = values.get(key)
    return v.get("text") if v else None


# ---------------------------------------------------------------- linkit ja attribuutio

def utm_link(path: str, topic: str, content: str) -> tuple[str, str]:
    """(nayttoteksti, uri). Nayttoteksti on lyhyt; uri kantaa kanavan tilille asti."""
    path = "/" + path.lstrip("/")
    q = urllib.parse.urlencode({"utm_source": "bluesky", "utm_medium": "partner",
                                "utm_campaign": topic, "utm_content": content})
    base, frag = (path.split("#", 1) + [""])[:2]
    uri = f"{SITE}{base}?{q}" + (f"#{frag}" if frag else "")
    return f"goaliq.app{base}", uri   # nakyva teksti ilman #-osaa; ankkuri on vain osoitteessa


# ---------------------------------------------------------------- deterministiset ehdotukset

# Pohjat ovat julkaisutarkistajan 16.10 korjaamat sellaisenaan. Ne ovat VARA: aivojen (Claude) postaus samaan
# slotiin korvaa pohjan. Runko vaihtuu kierroksittain (sama runko joka viikko = slop-tell nro 1).
# Varmuuslause vain kun data kantaa sen: ilmaistaulukon ykkosen ja kakkosen ero >= CLEAR_GAP xP. Mitattu
# jaadytyksista: GW1 0.08, GW2 0.12, GW3 1.65, GW4 0.03, GW5 0.88, GW6 0.73, GW7 2.46 (raja on paatos).
CLEAR_GAP = 0.5
CAPTAIN_CLEAR = (
    "Not overthinking the armband in GW{gw}. {name} tops the model at {xp} expected points. LINK",
    "Armband's sorted for GW{gw}. The model has {name} at {xp} expected points and a {p10} chance of 10+. LINK",
    "The model's GW{gw} captain is {name}, and it isn't close: {xp} expected points. LINK",
)
CAPTAIN_CLOSE = (
    "Close captain call in GW{gw}. {name} is top of the model at {xp} expected points, but the next name isn't far behind. LINK",
    "No obvious armband in GW{gw}. {name} edges it for the model at {xp} expected points. LINK",
)
# FPL:ssa joukkueen nimi on "GoalIQ's Team", joten "our FPL team"; luvut nakyvat FPL:n entry-sivulla
# (moduulin public_url), ei goaliq.appissa -> linkki sinne, ilman korttia (points-kortti nayttaa eri pelaajat).
RECAP_TEMPLATES = (
    "GW{gw} done. Our FPL team got {pts}, {dir} the average manager's {avg}. LINK",
    "{pts} for our FPL team in GW{gw}, {dir} the FPL average of {avg}. LINK",
    "Our FPL team finished GW{gw} {dir} the average: {pts} against {avg}. Think you can beat it? LINK",
)
GW_XP_PAGE = "/fpl/expected-points#gw-xp"


def _num(values: dict, key: str) -> float | None:
    v = values.get(key)
    try:
        return float(v["value"]) if v else None
    except (KeyError, TypeError, ValueError):
        return None


def _transfer_cost(gw: int) -> int | None:
    """Kierroksen miinuspisteet gw_calls-lokista; None = ei tietoa (tulospostaus ohitetaan)."""
    for row in (load_json(DATA / "gw_calls.json", {}) or {}).get("gameweeks") or []:
        if int(row.get("gw") or -1) == gw:
            ea = row.get("entry_actual") or {}
            c = ea.get("transfers_cost")
            return int(c) if isinstance(c, (int, float)) else None
    return None


def fallback_items(mod: dict, values: dict, now: datetime, state: dict) -> list[dict]:
    """Postaukset jotka botti tekee ilman aivojakin (aivot voivat korvata saman slotin)."""
    out = []
    gw = int(mod["gw"])
    dl = datetime.fromisoformat(str(mod["deadline_utc"]).replace("Z", "+00:00"))
    to_dl = dl - now
    slot = f"deadline:gw{gw}"
    cap = next(iter(rows(mod, "captain_top5")), None)
    xs = rows(mod, "xp_top5")
    if (timedelta(hours=3) <= to_dl <= timedelta(hours=30) and slot not in state["posted_slots"] and cap
            and len(xs) >= 2 and xs[0].get("player_id") == cap.get("player_id")):
        ck = f"captain_top5.{cap['key']}"
        xp, p10 = val(values, f"{ck}.gw_xp"), val(values, f"{ck}.p_10plus")
        a, b = _num(values, f"xp_top5.{xs[0]['key']}.gw_xp"), _num(values, f"xp_top5.{xs[1]['key']}.gw_xp")
        if xp and a is not None and b is not None:
            if a - b >= CLEAR_GAP:
                tpl = CAPTAIN_CLEAR[gw % 3]
                if "{p10}" in tpl and not p10:
                    tpl = CAPTAIN_CLEAR[0]
            else:
                tpl = CAPTAIN_CLOSE[gw % 2]
            keys = [f"{ck}.gw_xp"] + ([f"{ck}.p_10plus"] if "{p10}" in tpl else [])
            out.append({"kind": "post", "topic": "captain", "slot": slot,
                        "text": tpl.format(gw=gw, name=cap["name"], xp=xp, p10=p10),
                        "keys": keys, "link": GW_XP_PAGE, "card": "best-captain"})
    lg = (mod.get("sections") or {}).get("last_gw") or {}
    rslot = f"recap:gw{lg.get('gw')}"
    if (lg.get("available") and rslot not in state["posted_slots"] and lg.get("gw") == gw - 1
            and _transfer_cost(int(lg["gw"])) == 0):   # miinuspisteviikolla brutto/netto mittaamatta
        pts, avg = val(values, "last_gw.entry_points"), val(values, "last_gw.fpl_average")
        url = (values.get("last_gw.entry_points") or {}).get("public_url")
        if pts and avg and url and url == (values.get("last_gw.fpl_average") or {}).get("public_url"):
            d = "above" if int(pts) > int(avg) else ("below" if int(pts) < int(avg) else "level with")
            out.append({"kind": "post", "topic": "recap", "slot": rslot,
                        "text": RECAP_TEMPLATES[lg["gw"] % 3].format(gw=lg["gw"], pts=pts, avg=avg, dir=d),
                        "keys": ["last_gw.entry_points", "last_gw.fpl_average"], "link": url, "card": None})
    return out


# Mentioihin vastataan vain kun data ja kysymys ovat yksiselitteisia (julkaisutarkistaja 16.10, ehdot a-f).
FPL_WORDS = ("fpl", "xp", "captain", "transfer", "gw", "gameweek", "points", "pick", "bench", "wildcard")


def _player_index(mod: dict) -> dict[str, list[dict]]:
    idx: dict[str, list[dict]] = {}
    for r in rows(mod, "player_lookup"):
        name = str(r.get("name") or "")
        if len(name) >= 4:
            idx.setdefault(name.lower(), []).append(r)
    return idx


def _own_texts() -> dict[str, str]:
    return {r["uri"]: r.get("text") or "" for r in read_log() if r.get("uri")}


def mention_items(session, mod: dict, values: dict, state: dict) -> list[dict]:
    """Vastaus vain kun joku mainitsee tai vastaa meille (opt-in) ja KYSYY pelaajasta tai kapteenista."""
    out = []
    idx = _player_index(mod)
    gw = int(mod["gw"])
    handled = set(state["handled_notifications"])
    own = _own_texts()
    for n in session.notifications(50):
        if n.get("reason") not in ("mention", "reply") or n.get("uri") in handled:
            continue
        handled.add(n["uri"])
        rec = n.get("record") or {}
        text = str(rec.get("text") or "")
        low = text.lower()
        if "?" not in text:                                    # b) vain kysymykseen
            continue
        hits = [rs for nm, rs in idx.items() if re.search(rf"\b{re.escape(nm)}\b", low)]
        post = {"uri": n["uri"], "cid": n["cid"], "record": rec}
        ref = bsky.reply_ref(post)
        target = {"uri": n["uri"], "cid": n["cid"], "root_uri": ref["root"]["uri"],
                  "handle": (n.get("author") or {}).get("handle", ""), "reply": ref,
                  "created_at": n.get("indexedAt")}
        parent_uri = ((rec.get("reply") or {}).get("parent") or {}).get("uri", "")
        parent_text = own.get(parent_uri, "")
        if hits:
            if len(hits) != 1 or len(hits[0]) != 1:            # c) ja d) useampi tai samanniminen pelaaja
                continue
            hit = hits[0][0]
            team = str(hit.get("team") or "")
            if not (any(w in low for w in FPL_WORDS) or (team and team.lower() in low)):
                continue                                       # e) tavallinen sana ilman FPL-kontekstia
            if hit["name"].lower() in parent_text.lower():     # f) toistaisi oman postauksen
                continue
            k = f"player_lookup.{hit['key']}"
            xp = val(values, f"{k}.gw_xp")
            if xp:
                label = f"{hit['name']} ({team})" if team else hit["name"]
                out.append({"kind": "mention_reply", "topic": "mention", "target": target,
                            "text": f"The model has {label} at {xp} expected points for GW{gw}.",
                            "keys": [f"{k}.gw_xp"]})
        elif "captain" in low:
            cap = next(iter(rows(mod, "captain_top5")), None)
            key = f"captain_top5.{cap['key']}.gw_xp" if cap else ""
            xp = val(values, key) if cap else None
            if xp and cap["name"].lower() not in parent_text.lower():
                out.append({"kind": "mention_reply", "topic": "mention", "target": target,
                            "text": f"GW{gw}: the model has {cap['name']} top for captain at {xp} expected points.",
                            "keys": [key]})
    state["handled_notifications"] = sorted(handled)[-500:]
    return out


# ---------------------------------------------------------------- signaalit (ennakointi)

def _fpl_bootstrap() -> dict:
    from src.data import fpl_api
    return fpl_api.fetch_bootstrap(max_age_s=600)


def fpl_signals(boot: dict, now: datetime, gw: int) -> dict:
    teams = {t["id"]: t["short_name"] for t in boot.get("teams") or []}
    news, price = [], []
    for e in boot.get("elements") or []:
        own = float(e.get("selected_by_percent") or 0)
        added = e.get("news_added")
        if e.get("news") and added and own >= 3:
            try:
                age = now - datetime.fromisoformat(added.replace("Z", "+00:00"))
            except ValueError:
                age = None
            if age is not None and age <= timedelta(hours=36):
                news.append({"name": e["web_name"], "team": teams.get(e["team"]), "status": e.get("status"),
                             "news": e["news"], "owned_pct": own, "hours_ago": round(age.total_seconds() / 3600, 1)})
        # FPL:n oma ennustin (2026/27): projected_percent = eteneminen kohti muutosta (+-100 = muutos),
        # likelihood = etumerkillinen varmuus. Mitattu 16.10: Raya offset 0 -> 7.5 / 1.
        for pr in e.get("price_change_projections") or []:
            try:
                pct = float(pr.get("projected_percent"))
            except (TypeError, ValueError, AttributeError):
                continue
            if pr.get("offset") == 0 and abs(pct) >= 90 and own >= 1:
                price.append({"name": e["web_name"], "team": teams.get(e["team"]), "owned_pct": own,
                              "direction": "rise" if pct > 0 else "fall", "progress_pct": pct,
                              "likelihood": pr.get("likelihood")})
    rules = (boot.get("game_config") or {}).get("scoring") or {}
    return {"news_36h": sorted(news, key=lambda x: -x["owned_pct"])[:20],
            "price_tonight_fpl_projection": sorted(price, key=lambda x: -x["owned_pct"])[:15],
            "scoring_rules": rules}


def fixture_signals(gw: int) -> dict:
    from src.data import fpl_api
    fx = fpl_api.fetch_fixtures(max_age_s=3600)
    counts: dict[int, dict[int, int]] = {}
    for f in fx:
        ev = f.get("event")
        if ev is None or not (gw <= ev <= gw + 5):
            continue
        for t in (f["team_h"], f["team_a"]):
            counts.setdefault(ev, {}).setdefault(t, 0)
            counts[ev][t] += 1
    boot = _fpl_bootstrap()
    names = {t["id"]: t["short_name"] for t in boot.get("teams") or []}
    out = {}
    for ev, c in sorted(counts.items()):
        dbl = [names[t] for t, n in c.items() if n >= 2]
        blank = [names[t] for t in names if t not in c]
        if dbl or blank:
            out[f"GW{ev}"] = {"double": dbl, "blank": blank}
    return out


def social_signals(now: datetime, state: dict, blocked: set[str]) -> dict:
    """Mista FPL-yhteiso puhuu NYT: Bluesky (vastattavissa) ja X (vain luku, fxtwitter)."""
    tg = load_json(TARGETS_PATH, {})
    bs, xs, errs = [], [], []
    for t in tg.get("bluesky") or []:
        h = t["handle"]
        try:
            for p in bsky.author_feed(h, 10):
                created = datetime.fromisoformat(str(p.get("indexedAt")).replace("Z", "+00:00"))
                if now - created > SIGNAL_MAX_AGE:
                    continue
                rec = p.get("record") or {}
                eligible = (now - created <= gate.TARGET_MAX_AGE and h.lower() not in blocked
                            and p["uri"] not in state["replied_uris"])
                bs.append({"handle": h, "uri": p["uri"], "cid": p["cid"], "created_at": p.get("indexedAt"),
                           "text": str(rec.get("text") or "")[:400], "likes": p.get("likeCount", 0),
                           "reposts": p.get("repostCount", 0), "replies": p.get("replyCount", 0),
                           "reply_eligible": eligible})
        except Exception as e:  # noqa: BLE001
            errs.append(f"bluesky {h}: {e!r}"[:200])
    import requests
    for h in tg.get("x") or []:
        try:
            # fxtwitter antaa ajoittain 404:n olemassa olevalle tilille (reply_targets.py): toinen yritys.
            for yritys in range(2):
                r = requests.get(f"https://api.fxtwitter.com/2/profile/{h}/statuses?count=10",
                                 headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
                if r.status_code != 404 or yritys:
                    break
            r.raise_for_status()
            for s in r.json().get("results") or []:
                if ((s.get("author") or {}).get("screen_name") or "").lower() != h.lower():
                    continue        # uudelleenjaot pois (muisti fxtwitter-profiilisyote)
                ts = s.get("created_timestamp")
                if not isinstance(ts, (int, float)) or now.timestamp() - ts > SIGNAL_MAX_AGE.total_seconds():
                    continue
                xs.append({"handle": h, "hours_ago": round((now.timestamp() - ts) / 3600, 1),
                           "text": str(s.get("text") or "")[:300], "likes": s.get("likes", 0),
                           "reposts": s.get("reposts", 0), "replies": s.get("replies", 0)})
        except Exception as e:  # noqa: BLE001
            errs.append(f"x {h}: {e!r}"[:200])
    return {"bluesky": sorted(bs, key=lambda x: -x["likes"]),
            "x_read_only": sorted(xs, key=lambda x: -x["likes"])[:25], "errors": errs}


def cmd_context(out_dir: Path) -> int:
    now = datetime.now(timezone.utc)
    out_dir.mkdir(parents=True, exist_ok=True)
    state = load_state()
    mod, values, err = fresh_module(out_dir / "module")
    brief: dict = {"generated_at": now.isoformat(timespec="seconds"), "module_error": err or None}
    if mod:
        gw = int(mod["gw"])
        dl = datetime.fromisoformat(str(mod["deadline_utc"]).replace("Z", "+00:00"))
        brief.update({"gw": gw, "deadline_utc": mod["deadline_utc"],
                      "hours_to_deadline": round((dl - now).total_seconds() / 3600, 1)})
        compact = {}
        for k, v in values.items():
            sec = k.split(".", 1)[0]
            if sec == "player_lookup" and not k.endswith((".gw_xp", ".xp_6gw")):
                continue
            compact[k] = {"text": v.get("text"), "page": bsky_gate_page(v.get("public_url"))}
        brief["numbers"] = compact
        brief["numbers_note"] = ("ONLY these numbers may appear in text, exactly as written, and every one "
                                 "must be listed in the item's keys. A post that uses numbers must link to the "
                                 "page where they appear (`page`), and all its numbers must come from that one "
                                 "page. Text without numbers is also fine.")
        try:
            boot = _fpl_bootstrap()
            brief["fpl"] = fpl_signals(boot, now, gw)
            brief["fixtures_double_blank"] = fixture_signals(gw)
        except Exception as e:  # noqa: BLE001
            brief["fpl_error"] = repr(e)[:300]
    brief["social"] = social_signals(now, state, blocklist())
    brief["performance"] = load_json(PERF_PATH, {}).get("by_topic") or {}
    brief["recent_posts"] = [{k: r.get(k) for k in ("at", "kind", "topic", "text", "engagement")}
                             for r in read_log()[-15:]]
    day = (state["daily"].get(now.date().isoformat()) or {})
    brief["caps_left_today"] = {"post": gate.POSTS_PER_DAY - day.get("post", 0),
                                "reply": gate.OUTBOUND_REPLIES_PER_DAY - day.get("reply", 0)}
    brief["posted_slots"] = state["posted_slots"][-20:]
    save_json(out_dir / "briefing.json", brief)
    print(f"briefing: gw={brief.get('gw')} numerot={len(brief.get('numbers') or {})} "
          f"bsky={len(brief['social']['bluesky'])} x={len(brief['social']['x_read_only'])} "
          f"virheet={len(brief['social']['errors'])} moduuli={err or 'ok'}")
    return 0


# ---------------------------------------------------------------- julkaisu

def _mark(state: dict, item: dict, now: datetime) -> None:
    day = now.date().isoformat()
    d = state["daily"].setdefault(day, {})
    key = "post" if item["kind"] == "post" else ("reply" if item["kind"] == "reply" else "mention")
    d[key] = d.get(key, 0) + 1
    state["daily"] = {k: v for k, v in state["daily"].items() if k >= (now.date() - timedelta(days=14)).isoformat()}
    if item.get("slot"):
        state["posted_slots"] = (state["posted_slots"] + [item["slot"]])[-200:]
    t = item.get("target") or {}
    if t.get("uri"):
        state["replied_uris"] = (state["replied_uris"] + [t["uri"]])[-2000:]
        state["replied_roots"] = (state["replied_roots"] + [t.get("root_uri") or t["uri"]])[-2000:]
    if item["kind"] == "reply" and t.get("handle"):
        state["author_last_reply"][t["handle"].lower()] = now.isoformat()
    state["recent_texts"] = (state["recent_texts"] + [item["text"]])[-60:]


def bsky_gate_page(url) -> str | None:
    return gate.page_of(str(url)) if url else None


def prepare(item: dict, content_id: str) -> tuple[str, dict]:
    """LINK-paikkamerkki -> lyhyt nayttoteksti; palauttaa (teksti, {nayttoteksti: uri}).
    goaliq.app-polku saa utm:t (kanava tilille asti); ulkoinen osoite (FPL:n entry-sivu) ei."""
    text, links = item["text"], {}
    if item.get("link") and item["kind"] == "post":
        link = str(item["link"])
        if link.startswith("http"):
            disp, uri = link.split("://", 1)[1], link
        else:
            disp, uri = utm_link(link, item.get("topic") or "post", content_id)
        text = text.replace("LINK", disp) if "LINK" in text else f"{text} {disp}"
        links[disp] = uri
    return text.replace("LINK", "").strip(), links


def cmd_publish(queue_path: Path | None, dry: bool, thought: bool = False) -> int:
    now = datetime.now(timezone.utc)
    state = load_state()
    blocked, phrases = blocklist(), gate.rejected_phrases()
    tmp = Path(tempfile.mkdtemp(prefix="bsky_mod_"))
    mod, values, err = fresh_module(tmp)
    if not mod:
        print(f"Ei tuoretta moduulia ({err}): ei lukuja sisaltavia julkaisuja tassa ajossa.")
    pw = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    dry = dry or not pw
    session = None
    if not dry:
        session = bsky.Session(os.environ.get("BLUESKY_HANDLE", bsky.HANDLE), pw)

    items: list[dict] = []
    if session and not state.get("bot_label_at"):
        try:
            session.ensure_bot_label(BOT_BIO)
            state["bot_label_at"] = now.isoformat()
        except Exception as e:  # noqa: BLE001 - ilman merkintaa ei vastata mentioihin
            print(f"botti-merkinta epaonnistui: {e!r}")
    if session and mod and state.get("bot_label_at"):
        items += mention_items(session, mod, values, state)
    if queue_path and queue_path.exists():
        for it in load_json(queue_path, []):
            if isinstance(it, dict) and it.get("kind") in ("post", "reply"):
                it["source"] = "brain"
                items.append(it)
    if mod:
        taken = {i.get("slot") for i in items if i.get("slot")}
        items += [i for i in fallback_items(mod, values, now, state) if i.get("slot") not in taken]

    gw = int(mod["gw"]) if mod else None
    published, rejected = 0, []
    log_rows = []
    for it in items:
        cid = f"{now:%Y%m%d%H}-{published}"
        text, links = prepare(it, cid)
        it = {**it, "text": text}
        probs = gate.check(it, values=values, gw=gw, now=now, state=state, blocklist=blocked, phrases=phrases)
        if probs:
            rejected.append({"text": text, "why": probs, "source": it.get("source", "rule")})
            continue
        image = None
        if it.get("card"):
            # Kuivanakin renderoidaan: ensimmainen ajo todistaa etta Chrome ja kortti toimivat ajoympäristossa.
            try:
                from scripts import bsky_card
                c = bsky_card.render(it["card"])
                print(f"kortti {it['card']}: {c['mime']} {c['w']}x{c['h']} {len(c['bytes'])} t")
                if not dry:
                    image = {"blob": session.upload_image(c["bytes"], c["mime"]), "alt": c["alt"],
                             "w": c["w"], "h": c["h"]}
            except Exception as e:  # noqa: BLE001 - kuva on lisa, ei ehto
                print(f"kortti {it['card']} epaonnistui: {e!r}")
        reply = (it.get("target") or {}).get("reply")
        if it["kind"] == "reply" and not reply:
            t = it.get("target") or {}
            reply = bsky.reply_ref({"uri": t["uri"], "cid": t["cid"], "record": t.get("record") or {}})
        if dry:
            print(f"[KUIVA] {it['kind']}/{it.get('topic')}: {text}" + (f"  [kortti {it['card']}]" if it.get("card") else ""))
            res = {"uri": None, "cid": None}
        else:
            res = session.create_post(text, reply=reply, image=image, links=links)
        _mark(state, it, now)
        published += 1
        log_rows.append({"at": now.isoformat(timespec="seconds"), "uri": res.get("uri"), "cid": res.get("cid"),
                         "kind": it["kind"], "topic": it.get("topic"), "slot": it.get("slot"), "text": text,
                         "keys": it.get("keys") or [], "utm_content": cid if links else None,
                         "card": it.get("card") if image else None, "source": it.get("source", "rule"),
                         "target_handle": (it.get("target") or {}).get("handle"),
                         "target_uri": (it.get("target") or {}).get("uri"), "dry_run": dry,
                         "why": it.get("why"), "anticipation": it.get("anticipation")})
    if thought:
        state["last_think_at"] = now.isoformat()
    if not dry:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            for r in log_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        save_json(STATE_PATH, state)
    elif thought:
        # Kuivana postauksia ei kirjata, mutta aivojen ajohetki kylla: muuten kiintiota kuluu
        # joka tunti niin kauan kuin Bluesky-salasana puuttuu.
        s = load_state()
        s["last_think_at"] = now.isoformat()
        save_json(STATE_PATH, s)
    print(f"julkaistu {published}, hylatty {len(rejected)}, kuiva={dry}")
    for r in rejected:
        print(f"  HYLATTY ({r['source']}): {r['text'][:120]} -> {'; '.join(r['why'])[:300]}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### Bluesky: julkaistu {published}, hylatty {len(rejected)}, kuiva {dry}\n")
            for r in log_rows:
                f.write(f"- {r['kind']}/{r['topic']}: {r['text']}\n")
            for r in rejected:
                f.write(f"- HYLATTY: {r['text'][:140]} ({'; '.join(r['why'])[:200]})\n")
    return 0


# ---------------------------------------------------------------- mittaus ja oppiminen

def engagement(p: dict) -> int:
    return int(p.get("likeCount", 0)) + 2 * (int(p.get("repostCount", 0)) + int(p.get("replyCount", 0))
                                             + int(p.get("quoteCount", 0)))


def topic_table(rows_: list[dict]) -> dict:
    """Aiheittain: n, osuus postauksista joihin reagoitiin, keskimaarainen kiinnostus.
    Beta(1,1)-priori: pieni n ei nayta 100 %:lta (yksi tykkays yhdessa postauksessa)."""
    out: dict = {}
    for r in rows_:
        if r.get("engagement") is None:
            continue
        t = out.setdefault(r.get("topic") or "other", {"n": 0, "engaged": 0, "sum": 0})
        t["n"] += 1
        t["engaged"] += 1 if r["engagement"] > 0 else 0
        t["sum"] += r["engagement"]
    for t in out.values():
        t["engaged_rate_bayes"] = round((t["engaged"] + 1) / (t["n"] + 2), 3)
        t["mean_engagement"] = round(t["sum"] / t["n"], 2)
    return out


def cmd_perf() -> int:
    now = datetime.now(timezone.utc)
    log = read_log()
    uris = [r["uri"] for r in log if r.get("uri") and r.get("at") and
            now - datetime.fromisoformat(r["at"]) <= timedelta(days=30)]
    metrics = {p["uri"]: p for p in bsky.get_posts(uris)} if uris else {}
    for r in log:
        p = metrics.get(r.get("uri"))
        if p:
            r["engagement"] = engagement(p)
            r["likes"], r["reposts"] = p.get("likeCount", 0), p.get("repostCount", 0)
            r["replies"], r["quotes"] = p.get("replyCount", 0), p.get("quoteCount", 0)
    if log:
        LOG_PATH.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in log), encoding="utf-8")
    perf = load_json(PERF_PATH, {})
    fol = perf.get("followers") or []
    try:
        fol.append({"at": now.isoformat(timespec="seconds"), "n": bsky.profile(bsky.HANDLE).get("followersCount")})
    except Exception as e:  # noqa: BLE001
        print(f"profiili: {e!r}")
    perf.update({"updated_at": now.isoformat(timespec="seconds"), "followers": fol[-500:],
                 "by_topic": topic_table(log),
                 "customers_note": ("Tilit ja Premiumit kanavalla partner=bluesky: /api/admin/conversion "
                                    "ei viela erittele kanavaa (backlog-rivi). Klikit: PostHog utm_content.")})
    save_json(PERF_PATH, perf)
    print(f"perf: {len(metrics)} postausta mitattu, aiheita {len(perf['by_topic'])}")
    return 0


THINK_HOURS_UTC = (9, 17)          # aktiivisimmat FPL-tunnit (viestintatyyli 5b) -> kiintio ~2-3 ajoa/vrk
THINK_DEADLINE_WINDOW = timedelta(hours=6)
THINK_MIN_GAP = timedelta(hours=2)


def should_think(now: datetime, state: dict, deadline: datetime | None, force: bool = False) -> bool:
    """Ajetaanko aivot (Claude, kuluttaa tilauksen kiintiota) tassa ajossa."""
    if force:
        return True
    last = state.get("last_think_at")
    if last and now - datetime.fromisoformat(last) < THINK_MIN_GAP:
        return False
    if now.hour in THINK_HOURS_UTC:
        return True
    return bool(deadline and timedelta(0) < deadline - now <= THINK_DEADLINE_WINDOW)


def cmd_should_think(force: bool) -> int:
    now = datetime.now(timezone.utc)
    meta = (load_json(DATA / "fpl_xp_projections.json", {}) or {}).get("meta") or {}
    dl = meta.get("deadline_utc")
    deadline = datetime.fromisoformat(dl.replace("Z", "+00:00")) if dl else None
    think = should_think(now, load_state(), deadline, force)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write("think=" + ("true" if think else "false") + "\n")
    print(f"aivot: {think} (klo {now:%H} UTC, deadline {dl})")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("context")
    c.add_argument("--out", required=True)
    p = sub.add_parser("publish")
    p.add_argument("--queue")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--thought", action="store_true", help="aivot ajettiin tassa ajossa (kirjaa tilaan)")
    st = sub.add_parser("should-think")
    st.add_argument("--force", action="store_true")
    sub.add_parser("perf")
    a = ap.parse_args(argv)
    if a.cmd == "context":
        return cmd_context(Path(a.out))
    if a.cmd == "publish":
        return cmd_publish(Path(a.queue) if a.queue else None, a.dry_run, a.thought)
    if a.cmd == "should-think":
        return cmd_should_think(a.force)
    return cmd_perf()


if __name__ == "__main__":
    raise SystemExit(main())
