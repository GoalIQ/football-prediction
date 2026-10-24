"""Bluesky-botin julkaisuportti (16.10.2026). Jokainen ulos lahteva teksti kulkee taman lapi.

Villen saanto 6b (julkaisuportti) automaatiossa: ihmisen julkaisutarkistaja hyvaksyy pohjat ja
ajonaikaisen agentin ohjeen, ja tama tiedosto tekee mekaanisen osan JOKA KERTA. Oletus on hylkays:
`check()` palauttaa ongelmat, ja tyhja lista on ainoa tapa paasta ulos.

Mita mitataan (kaikki kaatavat):
  1. luvut: jokainen numero tulee kaytettyjen moduuliavainten teksteista (ilmaissivu nayttaa saman),
     tai on kierrosnumero. "10+" vain p_10plus-avaimen kanssa.
  2. kielletyt merkit (em/en dash, kaarevat lainausmerkit, ellipsi, U+FFFD) ja hylatyt sanamuodot
     (data/rejected_phrases.json).
  3. pituus: 300 merkkia (Blueskyn raja on 300 grafeemia; merkkimaara on tiukempi tai sama).
  4. vastaus: ei linkkia eika tuotenimea (C1: vastaus antaa luvun, ei mainosta), kohdepostaus alle
     4 h vanha, kohdetili ei estolistalla, samaan ketjuun ei kahdesti, tekijalle tauko 48 h.
     Pyytamaton vastaus tuo mallin luvun eika koske vammoja, ei vastauksessa eika kohteessa (24.10).
  5. toisto: ei lahes samaa tekstia kuin 40 viimeisessa (Blueskyn yhteisoohje 3.1: spammi).
  6. kiintiot: omia postauksia 3/vrk ja noin 3 h valein, vastauksia muiden postauksiin 4/vrk.
  7. toisto aiheena ja kuvana: kapteeni ja best-captain-kortti vain deadline-slotissa, sama slot kerran,
     sama kortti ja kerran-aiheet (captain, owner_take, recap) kerran kierroksessa.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

import config
from scripts.public_text import BANNED

MAX_CHARS = 300
POSTS_PER_DAY = 3
# 22.10.2026 (Villen GO): aivot ehdottavat 0-4 kohdetta ja julkaisu postasi kaikki samassa ajossa, joten omat
# postaukset lahtivat pareina 0-5 s valein (16.-21.10 viitena paivana). Seurattujen syotteessa pari kilpailee
# itsensa kanssa. Tavoite on noin 3 h: ajot ovat tunnin valein (:37) ja aivoajon julkaisu lahtee ~15 min
# myohemmin, joten 2 h 30 min raja paastaa postauksen kolmannen tunnin ajossa eika siirra sita neljanteen.
MIN_POST_GAP = timedelta(hours=2, minutes=30)
GAP_PROBLEM = "postausvali"
# Pyytamattomat vastaukset muiden postauksiin. OLETUS 0 (16.10.2026): atproto-botin opas: "please only
# interact (like, repost, reply, etc.) if the user has tagged the bot account ... or your bot may be flagged
# for spam". Ville paattaa: repo-muuttuja BSKY_OUTBOUND_REPLIES_PER_DAY (tyonkulku valittaa sen).
OUTBOUND_REPLIES_PER_DAY = int(os.environ.get("BSKY_OUTBOUND_REPLIES_PER_DAY") or 0)
MENTION_REPLIES_PER_DAY = 3      # "kaytto, ei sanamuoto": vastaus kaikkeen minuuteissa = botin tunnusmerkki
# Lukuja tekstissa (kierrosnumeroa ei lasketa). Luku tukee kantaa, ei korvaa sita; kolme lukua
# samassa tekstissa on tunnusmerkki eika todiste (tyyliohje D2). Postauksen kortti kantaa loput.
MAX_NUMBERS = {"post": 2, "reply": 1, "mention_reply": 1}
# Tyyliohjeen kielletyt kuviot (pienilla kirjaimilla, osamerkkijono). Sanasto + rakenteet.
STYLE_TELLS = (
    "additionally", "align with", "bolstered", "crucial", "delve", "emphasizing", "enduring", "enhance",
    "fostering", "garner", "highlight", "interplay", "intricate", "meticulous", "pivotal", "robust",
    "showcase", "tapestry", "testament", "underscore", "vibrant", "serves as", "stands as",
    "not just ", "rather than", "in short", "the bottom line", "let's dive", "here's the thing",
    "game-changer", "game changer", "it's worth noting", "as you spotted", "great question",
    "betting", " odds", "tips", "lock of the week",
)
# 22.10.2026: FPL:ssa buy/sell/dump luetaan siirtoneuvoksi. Botin vastaus "Pedro at that price is a hard
# sell for me" (21.10) tarkoitti "en ostaisi", mutta luettiin myyntikehotukseksi, vaikka malli piti
# pelaajaa kierroksen kolmantena hyokkaajana, ja kohde kysyi "Are you AI?". Siirtoverbi vain
# kirjaimellisessa merkityksessa (docs/bsky/AANI.md).
TRANSFER_IDIOMS = (
    "hard sell", "tough sell", "easy sell", "an easy buy", "i buy it", "i'm buying it", "not buying it",
    "i'm sold", "not sold on", "sold on him", "sold on the",
)
# 17.10.2026 (Villen paatos, goaliq-app cos-reports/2026-10-17-tyokalut-maksumuuriin-spec.md): henkilokohtaiset
# FPL-tyokalut ovat Premiumia. Botti ei saa luvata niita ilmaiseksi. Ilmaista on sisalto: ennusteet, clean sheet
# -taulukot, expected points -sivut, track record ja artikkelit. Saanto: tyokalun nimi ja ilmaisuussana samassa
# virkkeessa = hylkays. "Free Hit" ja "free transfer" ovat FPL:n omia termeja eivatka ilmaisuuslupauksia.
PREMIUM_TOOL_TERMS = (
    "rate my team", "rate your team", "rate my draft", "team rater", "your captain", "captain for your",
    "mini-league", "mini league", "head-to-head", "h2h", "rival", "watchlist", "fit checker", "season race",
    "beat the model", "gameweek review", "gw review", "season ledger", "squad news", "defcon live",
    "planner", "chip timing", "transfer suggestions",
)
_FREE_CLAIM_RE = re.compile(
    r"\bfree\b(?!\s*(?:hit|transfers?|kicks?|agents?))|no sign[- ]?in|no log[- ]?in|no account|without an account",
    re.I)
# 23.10.2026 (ylläpitäjän päätös): owner_take-aihe rakentuu ylläpitäjän omasta kannasta (scripts/bsky_kanta.py).
# Teksti kertoo kannan olevan tilin takana olevan ihmisen eikä mallin, mutta ei väitä postausta ihmisen kirjoittamaksi
# (tili on automaatio, bio sanoo sen).
OWNER_TAKE_TOPIC = "owner_take"
OWNER_TAKE_PHRASES = (
    "the person behind this account", "the human behind this account", "the human running this account",
    "the person running this account",
)
HUMAN_AUTHORED_CLAIMS = (
    "i wrote", "i'm writing", "written by a human", "written by me", "human-written", "human written",
    "hand-written", "handwritten", "not automated", "not a bot", "i'm a human", "i am a human", "no bot",
)
# 24.10.2026 (yllapitaja: "Ei tallaisia"): botti vastasi pyytamatta fpl.pagen loukkaantumisuutiseen (Saka:
# "another MRI ... fluid in the area") arvailulla ja kysymyksella "moving him or sitting tight?", vaikka FPL oli
# merkinnyt hanet 21.10 tilaan 0 % "Unknown return date". Vastauksessa ei ollut mallin lukua, joten lukuportti ei
# nahnyt mitaan. Pyytamaton vastaus tuo mallin luvun (C1: vastaus antaa luvun) eika koske vammoja: mallilla ei
# ole niihin lisattavaa. Kohdepostauksen teksti on pakollinen, jotta vamma-aihe nakyy myos siita.
INJURY_RE = re.compile(
    r"\b(?:injur(?:y|ies|ed)|scans?|mri|fluid|hamstring|thigh|knee|ankle|groin|calf|knock|strain|fracture|"
    r"surgery|setback|illness|medical|specialist|fitness|ruled out|return date|out for)\b", re.I)
TARGET_MAX_AGE = timedelta(hours=4)
AUTHOR_COOLDOWN = timedelta(hours=48)
SIMILAR = 0.8
# 23.10.2026 (yllapitaja): GW8:n kapteenista lahti nelja omaa postausta kolmessa paivassa (20.-23.10), ja
# kolmessa oli tasmalleen sama kuva (best-captain-kortti, sama blob). Teksti oli joka kerta eri, joten
# toistosaanto (`similar`) ei nahnyt sita, ja 23.10 aivot asettuivat Haalandin taakse mallin kapteenia
# (B.Fernandes) vastaan. Kapteeni kuuluu deadline-postaukselle, jonka slot menee kerran; kortti ja
# kerran-aiheet kerran kierroksessa.
SLOT_ONLY_TOPICS = {"captain": "deadline"}
SLOT_ONLY_CARDS = {"best-captain": "deadline"}
ONCE_PER_GW_TOPICS = ("captain", "owner_take", "recap")
# Ennen 23.10 lokiin ei kirjattu kierrosta: sellainen rivi lasketaan kuluvaan kierrokseen, jos se on alle
# 7 vrk vanha. Suunta on varovainen: se voi estaa liikaa yhden kierroksen ajan, mutta ei paasta toistoa.
LEGACY_GW_WINDOW = timedelta(days=7)

# Ei lookaheadia: "15.6m" ja "8.0xP" tarkistetaan myos (yksikko perassa ei vapauta lukua).
_NUM_RE = re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)?%?\+?")
_GW_RE = re.compile(r"\b(?:GW|Gameweek\s*)(\d{1,2})\b", re.I)
_URL_RE = re.compile(r"https?://\S+|\b[\w-]+\.(?:app|com|net|org|io|co|uk)\b\S*", re.I)


def rejected_phrases(path: Path | None = None) -> list[str]:
    p = path or (config.DATA_DIR / "rejected_phrases.json")
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [str(x.get("phrase")).lower() for x in d.get("phrases") or [] if x.get("phrase")]


def allowed_numbers(values: dict[str, dict]) -> set[str]:
    """`values`: {avain: moduulin arvo} vain julkisella reitilla (public_url) olevat."""
    out: set[str] = set()
    for key, v in values.items():
        if not v.get("public_url"):
            continue
        t = str(v.get("text") or "").strip()
        if t:
            out.add(t)
            out.add(t.rstrip("%"))
        if key.endswith("p_10plus"):
            out.add("10+")
    return out


def page_of(url: str, site: str = "https://goaliq.app") -> str:
    """Sivun tunniste ilman skeemaa, kyselya ja #-osaa: 'goaliq.app/fpl/expected-points'."""
    if not url.startswith("http"):
        url = site + "/" + url.lstrip("/")
    s = urllib.parse.urlsplit(url)
    return (s.netloc + s.path).rstrip("/").lower()


def _words(t: str) -> set[str]:
    return set(re.findall(r"[a-z0-9.%]+", t.lower()))


def similar(a: str, b: str) -> bool:
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return False
    return len(wa & wb) / len(wa | wb) >= SIMILAR


def gw_posts(posts: list[dict], gw: int | None, now: datetime) -> list[dict]:
    """Omat postaukset kuluvalta kierrokselta (`state["own_posts"]`). YKSI lukija portille ja briefingille."""
    out = []
    for p in posts or []:
        if p.get("gw") is not None and gw is not None:
            if int(p["gw"]) == gw:
                out.append(p)
            continue
        try:
            at = datetime.fromisoformat(str(p.get("at")).replace("Z", "+00:00"))
        except ValueError:
            out.append(p)   # aika puuttuu: lasketaan mukaan (fail-closed)
            continue
        if now - at <= LEGACY_GW_WINDOW:
            out.append(p)
    return out


def check(item: dict, *, values: dict[str, dict], gw: int | None, now: datetime,
          state: dict, blocklist: set[str], phrases: list[str],
          owner_take: list[dict] | None = None) -> list[str]:
    """Palauttaa ongelmat. `item`: {kind: post|reply|mention_reply, text, keys, target?}.
    `owner_take`: kuluvan kierroksen ylläpitäjän kommentit (bsky_kanta.read); owner_take-aihe vaatii niitä."""
    text = str(item.get("text") or "")
    kind = item.get("kind")
    probs: list[str] = []
    if not text.strip():
        return ["tyhja teksti"]
    if len(text) > MAX_CHARS:
        probs.append(f"pituus {len(text)} > {MAX_CHARS}")
    for ch, name in BANNED.items():
        if ch in text:
            probs.append(f"kielletty merkki: {name}")
    low = text.lower()
    for tell in STYLE_TELLS:
        if tell in low:
            probs.append(f"tyylikielto: {tell.strip()!r}")
    for idiom in TRANSFER_IDIOMS:
        if idiom in low:
            probs.append(f"tyylikielto: siirtoverbi kuvaannollisena {idiom!r} (luetaan siirtoneuvoksi)")
    if re.search(r"\b(?:is|are|was)n't [^.,;]{1,40}, (?:it|they|he|she)(?:'s| is| are)\b", low):
        probs.append("tyylikielto: negatiivinen parallelismi (ei X, vaan Y)")
    if text.count("!") > 1:
        probs.append("yli yksi huutomerkki")
    for lause in re.split(r"[.!?\n]+", low):
        tyokalu = next((t for t in PREMIUM_TOOL_TERMS if t in lause), None)
        if tyokalu and _FREE_CLAIM_RE.search(lause):
            probs.append(f"lupaa Premium-tyokalun ilmaiseksi: {tyokalu!r}")
    if item.get("topic") == OWNER_TAKE_TOPIC:
        if gw is None or not any(t.get("gw") == gw and str(t.get("text") or "").strip() for t in owner_take or []):
            probs.append("owner_take ilman tämän kierroksen ylläpitäjän vastausta")
        if kind != "post":
            probs.append("owner_take vain omana postauksena")
        if not any(ph in low for ph in OWNER_TAKE_PHRASES):
            probs.append("owner_take ei kerro kannan olevan tilin takana olevan ihmisen")
        for claim in HUMAN_AUTHORED_CLAIMS:
            if claim in low:
                probs.append(f"väittää postauksen ihmisen kirjoittamaksi: {claim!r}")
    for ph in phrases:
        if ph and ph in low:
            probs.append(f"hylatty sanamuoto: {ph!r}")

    used = {k: values[k] for k in item.get("keys") or [] if k in values}
    missing = [k for k in item.get("keys") or [] if k not in values]
    if missing:
        probs.append(f"avaimet eivat ole tuoreessa moduulissa: {missing[:5]}")
    ok_nums = allowed_numbers(used)
    gws = {str(gw)} if gw is not None else set()
    body = _URL_RE.sub(" ", text)
    for m in _GW_RE.finditer(body):
        if m.group(1) not in gws and m.group(1) not in {str(int(g) - 1) for g in gws}:
            probs.append(f"kierros GW{m.group(1)} ei ole moduulin kierros tai edellinen")
    body = _GW_RE.sub(" ", body)
    nums = [m.group(0) for m in _NUM_RE.finditer(body)]
    for n in nums:
        if n not in ok_nums and n.rstrip("%") not in ok_nums:
            probs.append(f"luku {n!r} ei tule kaytetyista moduuliavaimista")
    cap_n = MAX_NUMBERS.get(kind, 1)
    if len([n for n in nums if n != "10+"]) > cap_n:
        probs.append(f"liikaa lukuja ({len(nums)} > {cap_n}): yksi luku tukee kantaa")

    # 6a (julkaisutarkistaja 16.10): luvun on nayttava sivulla, jolle postaus linkittaa. Ensimmaiset pohjat
    # linkittivat best-captain-sivulle, jolla 8.0 ei nay. Postaus jossa on lukuja tarvitsee linkin.
    if kind == "post" and used:
        link = item.get("link")
        if not link:
            probs.append("lukuja ilman linkkia sivulle jolla ne nakyvat")
        else:
            lp = page_of(str(link))
            for k, v in used.items():
                if page_of(str(v.get("public_url") or "")) != lp:
                    probs.append(f"luku {k} nakyy sivulla {page_of(str(v.get('public_url') or ''))}, linkki vie {lp}")
    # Julkaisutarkistaja 23.10 (fp #44): kanta on ihmisen, mutta mallia koskeva vaite tarvitsee mallin luvun
    # tekstiin. Luku tuo mukanaan linkkisaannon ylla. Ilman tata "the model leaves room for that call" meni lapi.
    if item.get("topic") == OWNER_TAKE_TOPIC and not any(
            n in ok_nums or n.rstrip("%") in ok_nums for n in nums if n != "10+"):
        probs.append("owner_take ilman mallin lukua tekstissa (keys + linkki): kanta tarvitsee todisteen")

    if kind in ("reply", "mention_reply"):
        if _URL_RE.search(text):
            probs.append("vastauksessa linkki")
        if "goaliq" in low:
            probs.append("vastauksessa tuotenimi")
        tgt = item.get("target") or {}
        if not tgt.get("uri") or not tgt.get("cid"):
            probs.append("vastauksen kohde puuttuu")
        if tgt.get("uri") in set(state.get("replied_uris") or []):
            probs.append("tahan postaukseen on jo vastattu")
        if (tgt.get("root_uri") or tgt.get("uri")) in set(state.get("replied_roots") or []):
            probs.append("tahan ketjuun on jo vastattu")
    if kind in ("reply", "mention_reply"):   # estolista ja 4 h koskevat myos mentioita (tarkistaja 16.10)
        tgt = item.get("target") or {}
        handle = str(tgt.get("handle") or "").lower()
        if handle in blocklist:
            probs.append(f"kohdetili estolistalla: {handle}")
        try:
            created = datetime.fromisoformat(str(tgt.get("created_at")).replace("Z", "+00:00"))
            if now - created > TARGET_MAX_AGE:
                probs.append(f"kohdepostaus {int((now - created).total_seconds() // 3600)} h vanha (raja 4 h)")
        except ValueError:
            probs.append("kohdepostauksen aika puuttuu")
        last = (state.get("author_last_reply") or {}).get(handle)
        if kind == "reply" and last and now - datetime.fromisoformat(last) < AUTHOR_COOLDOWN:
            probs.append(f"tekijalle vastattu alle 48 h sitten: {handle}")
    if kind == "reply":   # pyytamaton vastaus; mentioon vastataan, vaikka kysyja kysyisi vammasta
        if not any(n in ok_nums or n.rstrip("%") in ok_nums for n in nums if n != "10+"):
            probs.append("pyytamaton vastaus ilman mallin lukua (keys): vastaus antaa luvun tai jaa pois")
        tgt_text = str((item.get("target") or {}).get("text") or "")
        if not tgt_text.strip():
            probs.append("pyytamattoman vastauksen kohdepostauksen teksti puuttuu")
        for where, t in (("vastaus", text), ("kohdepostaus", tgt_text)):
            m = INJURY_RE.search(t)
            if m:
                probs.append(f"pyytamaton vastaus loukkaantumisuutiseen ({where}: {m.group(0)!r})")

    day = now.date().isoformat()
    counts = (state.get("daily") or {}).get(day) or {}
    if kind == "post" and counts.get("post", 0) >= POSTS_PER_DAY:
        probs.append(f"omien postausten kiintio {POSTS_PER_DAY}/vrk taynna")
    last_post = state.get("last_post_at")
    if kind == "post" and last_post and now - datetime.fromisoformat(last_post) < MIN_POST_GAP:
        mins = int((now - datetime.fromisoformat(last_post)).total_seconds() // 60)
        probs.append(f"{GAP_PROBLEM}: edellisesta omasta postauksesta {mins} min (raja {MIN_POST_GAP})")
    if kind == "reply" and counts.get("reply", 0) >= OUTBOUND_REPLIES_PER_DAY:
        probs.append(f"vastauskiintio {OUTBOUND_REPLIES_PER_DAY}/vrk taynna")
    if kind == "mention_reply" and counts.get("mention", 0) >= MENTION_REPLIES_PER_DAY:
        probs.append(f"mention-vastauskiintio {MENTION_REPLIES_PER_DAY}/vrk taynna")
    for prev in (state.get("recent_texts") or [])[-40:]:
        if similar(text, prev):
            probs.append("lahes sama teksti kuin aiempi postaus (toisto)")
            break
    if kind == "post":
        topic, card, slot = item.get("topic"), item.get("card"), str(item.get("slot") or "")
        for name, val, only in (("aihe", topic, SLOT_ONLY_TOPICS), ("kortti", card, SLOT_ONLY_CARDS)):
            if val in only and (gw is None or slot != f"{only[val]}:gw{gw}"):
                probs.append(f"{name} {val} vain {only[val]}-postauksessa (slot {only[val]}:gw<N>)")
        if slot and slot in (state.get("posted_slots") or []):
            probs.append(f"slot {slot} on jo postattu")
        done = gw_posts(state.get("own_posts") or [], gw, now)
        if card and any(p.get("card") == card for p in done):
            probs.append(f"kortti {card} on jo kaytetty talla kierroksella (sama kuva)")
        if topic in ONCE_PER_GW_TOPICS and any(p.get("topic") == topic for p in done):
            probs.append(f"aihe {topic} on jo postattu talla kierroksella")
    return probs
