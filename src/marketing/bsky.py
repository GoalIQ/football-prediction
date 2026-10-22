"""Bluesky (AT Protocol) -asiakas GoalIQ-botille (16.10.2026, Villen GO: "bluesky only, ei x").

Vain `requests`, ei uusia riippuvuuksia. Julkiset luvut (profiilit, syotteet, postausten
tykkaykset) haetaan ilman tunnusta public.api.bsky.app:sta; kirjoitus ja ilmoitukset vaativat
sovellussalasanan (BLUESKY_APP_PASSWORD, ei paatunnusta).

Kirjoittava osa EI paata mitaan: se postaa vain sen, minka scripts/bsky_bot.py on ajanut
portin (src/marketing/bsky_gate.py) lapi.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import requests

HANDLE = "goaliqapp.bsky.social"
PDS = "https://bsky.social"
PUBLIC = "https://public.api.bsky.app"
UA = {"User-Agent": "GoalIQ-bot/1.0 (+https://goaliq.app)"}
MAX_IMAGE_BYTES = 950_000          # Blueskyn raja ~976 kt
_URL_RE = re.compile(r"https?://[^\s]+")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def link_facets(text: str, links: dict[str, str] | None = None) -> list[dict]:
    """Linkkien facetit UTF-8-tavuoffseteilla (AT Protocolin vaatimus, ei merkkioffsetit).

    `links` = {nayttoteksti: uri}: lyhyt "goaliq.app/fpl/x" nakyy tekstissa, ja facet vie
    utm-osoitteeseen (attribuutio ilman 90 merkin linkkia tekstissa)."""
    out = []
    for disp, uri in (links or {}).items():
        i = text.find(disp)
        if i >= 0:
            start = len(text[:i].encode("utf-8"))
            out.append({"index": {"byteStart": start, "byteEnd": start + len(disp.encode("utf-8"))},
                        "features": [{"$type": "app.bsky.richtext.facet#link", "uri": uri}]})
    for m in _URL_RE.finditer(text):
        url = m.group(0).rstrip(".,)")
        start = len(text[:m.start()].encode("utf-8"))
        out.append({"index": {"byteStart": start, "byteEnd": start + len(url.encode("utf-8"))},
                    "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}]})
    return out


_TAG_RE = re.compile(r"(?:^|(?<=\s))#([A-Za-z][A-Za-z0-9_]{0,63})\b")


def tag_facets(text: str) -> list[dict]:
    """Hashtagien facetit. Ilman facettia "#FPL" on Blueskyssa pelkkaa tekstia: ei linkkia hashtag-sivulle
    eika tunnistetta, jolla hashtag-haku ja #-syotteet loytavat postauksen (22.10.2026)."""
    out = []
    for m in _TAG_RE.finditer(text):
        start = len(text[:m.start()].encode("utf-8"))
        out.append({"index": {"byteStart": start, "byteEnd": start + len(m.group(0).encode("utf-8"))},
                    "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": m.group(1)}]})
    return out


def _get(path: str, params: dict, base: str = PUBLIC, token: str | None = None) -> dict:
    h = dict(UA)
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = requests.get(f"{base}/xrpc/{path}", params=params, headers=h, timeout=30)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- julkinen luku

def profile(actor: str) -> dict:
    return _get("app.bsky.actor.getProfile", {"actor": actor})


def author_feed(actor: str, limit: int = 20) -> list[dict]:
    """Tilin omat postaukset (ei vastauksia, ei uudelleenjakoja)."""
    d = _get("app.bsky.feed.getAuthorFeed", {"actor": actor, "limit": limit, "filter": "posts_no_replies"})
    out = []
    for it in d.get("feed") or []:
        if it.get("reason"):            # uudelleenjako: ei tilin oma
            continue
        p = it.get("post") or {}
        if (p.get("author") or {}).get("handle", "").lower() != actor.lower():
            continue
        out.append(p)
    return out


def get_posts(uris: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(uris), 25):
        out += _get("app.bsky.feed.getPosts", {"uris": uris[i:i + 25]}).get("posts") or []
    return out


# ---------------------------------------------------------------- kirjoitus (tunnus)

class Session:
    def __init__(self, handle: str, app_password: str):
        r = requests.post(f"{PDS}/xrpc/com.atproto.server.createSession",
                          json={"identifier": handle, "password": app_password}, headers=UA, timeout=30)
        r.raise_for_status()
        d = r.json()
        self.did = d["did"]
        self.jwt = d["accessJwt"]

    def _post(self, path: str, **kw) -> dict:
        h = dict(UA, Authorization=f"Bearer {self.jwt}")
        h.update(kw.pop("headers", {}))
        r = requests.post(f"{PDS}/xrpc/{path}", headers=h, timeout=60, **kw)
        r.raise_for_status()
        return r.json()

    def ensure_bot_label(self, bio_suffix: str) -> bool:
        """Self-label "bot" + automaatiolause bioon (atproto-botin opas: "bot accounts should identify
        themselves by adding a self-label to their profile"). Idempotentti; True = profiilia muutettiin."""
        h = dict(UA, Authorization=f"Bearer {self.jwt}")
        r = requests.get(f"{PDS}/xrpc/com.atproto.repo.getRecord", headers=h, timeout=30,
                         params={"repo": self.did, "collection": "app.bsky.actor.profile", "rkey": "self"})
        r.raise_for_status()
        d = r.json()
        rec = dict(d.get("value") or {"$type": "app.bsky.actor.profile"})
        vals = list(((rec.get("labels") or {}).get("values")) or [])
        has_label = any(v.get("val") == "bot" for v in vals)
        desc = str(rec.get("description") or "")
        want = bio_with_suffix(desc, bio_suffix)
        need_bio = want != desc and len(want) <= 256
        if has_label and not need_bio:
            return False
        if not has_label:
            vals.append({"val": "bot"})
        rec["labels"] = {"$type": "com.atproto.label.defs#selfLabels", "values": vals}
        if need_bio:
            rec["description"] = want
        self._post("com.atproto.repo.putRecord", json={
            "repo": self.did, "collection": "app.bsky.actor.profile", "rkey": "self",
            "record": rec, "swapRecord": d.get("cid")})
        return True

    def notifications(self, limit: int = 50) -> list[dict]:
        return _get("app.bsky.notification.listNotifications", {"limit": limit},
                    base=PDS, token=self.jwt).get("notifications") or []

    def upload_image(self, data: bytes, mime: str) -> dict:
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError(f"kuva {len(data)} tavua > {MAX_IMAGE_BYTES}")
        return self._post("com.atproto.repo.uploadBlob", data=data,
                          headers={"Content-Type": mime})["blob"]

    def create_post(self, text: str, *, reply: dict | None = None, image: dict | None = None,
                    links: dict[str, str] | None = None) -> dict:
        """`reply` = {"root": {uri,cid}, "parent": {uri,cid}}; `image` = {"blob","alt","w","h"}."""
        rec = {"$type": "app.bsky.feed.post", "text": text, "createdAt": now_iso(), "langs": ["en"]}
        facets = link_facets(text, links) + tag_facets(text)
        if facets:
            rec["facets"] = facets
        if reply:
            rec["reply"] = reply
        if image:
            rec["embed"] = {"$type": "app.bsky.embed.images", "images": [{
                "alt": image["alt"], "image": image["blob"],
                "aspectRatio": {"width": image["w"], "height": image["h"]}}]}
        return self._post("com.atproto.repo.createRecord",
                          json={"repo": self.did, "collection": "app.bsky.feed.post", "record": rec})


def bio_with_suffix(desc: str, suffix: str) -> str:
    """Bio + automaatiolause omana lauseenaan. 16.10 ensimmainen versio liitti lauseen ilman pistetta:
    "...league code jgi6j9 Posts and replies are automated." -> korjataan myos se."""
    s = suffix.strip()
    base = desc.replace(s, "").rstrip()
    if base and base[-1] not in ".!?":
        base += "."
    return f"{base} {s}".strip()


def reply_ref(post: dict) -> dict:
    """Vastausviite postaukselle (julkisen API:n post-objekti): juuri sailyy ketjussa."""
    parent = {"uri": post["uri"], "cid": post["cid"]}
    root = ((post.get("record") or {}).get("reply") or {}).get("root") or parent
    return {"root": {"uri": root["uri"], "cid": root["cid"]}, "parent": parent}
