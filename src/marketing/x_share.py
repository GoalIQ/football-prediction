"""X:n oma jakolinkki (23.10.2026, ylläpitäjän päätös): yksi napautus avaa X:n valmiilla tekstillä.

Ei rajapintaa eikä automaatiota: ylläpitäjä painaa itse Post. Sama lukija X-jonon molemmille tuottajille
(scripts/bsky_bot.py x_issue ja scripts/x_viikkoketju.py issue), jotta linkin teksti on aina täsmälleen
se teksti, jonka portti on tarkistanut.
"""
from __future__ import annotations

import urllib.parse

X_INTENT = "https://x.com/intent/tweet?text="


def x_intent_url(text: str) -> str:
    return X_INTENT + urllib.parse.quote(text, safe="")
