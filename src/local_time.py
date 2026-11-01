"""Yksi aikavyohykesaanto hub-sivuille (ulkoasuohjelma WP2, 1.11.2026).

MITATTU 1.11: hub nayttaa ajat UTC:na ("Next deadline: Gameweek 10,
6 November at 18:30 UTC", ottelusivu "Sun 01 Nov 2026, 16:30 UTC"), SPA
lukijan omassa ajassa ("Fri 6 Nov, 20:30 EET", Fixtures "18:30"). Sama
deadline ja sama ottelu nayttivat kahdelta eri ajalta.

SAANTO (sama molemmilla pinnoilla):
  - Lukija nakee ajan OMASSA vyohykkeessaan, vyohykkeen nimi perassa,
    en-GB-muodossa: "Fri 6 Nov, 20:30 EET". SPA:ssa tama on
    `web/pro-spa/src/lib/gameweek.ts formatDeadline`.
  - Hubin staattinen HTML kantaa UTC-tekstin (nimetty "UTC"), joten sivu on
    oikein ilman JavaScriptia, hakukoneelle ja valimuistille. `<time
    datetime>` kantaa hetken koneluettavana.
  - `LOCAL_TIME_JS` vaihtaa selaimessa jokaisen `time[data-giq-local]`-
    elementin tekstin samaan muotoon kuin SPA. Alkuperainen UTC-teksti jaa
    `title`-attribuuttiin.

Portti: tests/test_local_time_rule.py (muoto, ei-JS-fallback ja etta
generaattorit kayttavat tata moduulia eivatka kirjoita omaa).
"""
from __future__ import annotations

import datetime as _dt
from html import escape

ATTR = "data-giq-local"

# Sama muotoilu kuin SPA:n formatDeadline: en-GB, weekday short, day numeric,
# month short, 2-digit hour/minute, perassa vyohykkeen lyhenne.
LOCAL_TIME_JS = (
    "(function(){"
    "function run(){"
    "var els=document.querySelectorAll('time[" + ATTR + "]'),i;"
    "for(i=0;i<els.length;i++){"
    "var el=els[i],d=new Date(el.getAttribute('datetime'));"
    "if(isNaN(d.getTime()))continue;"
    "try{"
    "var w=d.toLocaleString('en-GB',{weekday:'short',day:'numeric',month:'short',"
    "hour:'2-digit',minute:'2-digit'});"
    "var z='',p=new Intl.DateTimeFormat('en-GB',{timeZoneName:'short'}).formatToParts(d),j;"
    "for(j=0;j<p.length;j++)if(p[j].type==='timeZoneName')z=p[j].value;"
    "if(!el.title)el.title=el.textContent;"
    "el.textContent=w+(z?' '+z:'');"
    "}catch(e){}"
    "}}"
    "if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run);"
    "else run();"
    "})();"
)


def iso_utc(dt: _dt.datetime) -> str:
    """Koneluettava hetki `<time datetime>`:iin, aina UTC ja Z."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def time_tag(dt: _dt.datetime, utc_text: str) -> str:
    """`<time>` jonka staattinen teksti on UTC ja jonka skripti lokalisoi.

    `utc_text` on pinnan oma UTC-muotoilu ja sen PITAA nimeta vyohyke, jotta
    ilman JavaScriptia luettu aika ei nayta paikalliselta.
    """
    if "UTC" not in utc_text:
        raise ValueError(f"time_tag: UTC-tekstista puuttuu vyohyke: {utc_text!r}")
    return f'<time datetime="{iso_utc(dt)}" {ATTR}>{escape(utc_text)}</time>'


def local_time_script() -> str:
    return f"<script>{LOCAL_TIME_JS}</script>"


def with_local_time_script(html_fragment: str) -> str:
    """Skripti vain jos sivulla on lokalisoitava aika (ei turhaa JS:aa)."""
    return local_time_script() if ATTR in html_fragment else ""
