# -*- coding: utf-8 -*-
"""Kevyt cron-tulkki fp-repon omalle dispatch-relaylle.

Ported goaliq-app/scripts/autopilot/cron_realization.py:sta (samat neljä
funktiota, sama käyttäytyminen) — EI riippuvuutta toiseen repoon. `relay.py`
elää nyt fp-repossa (QUEUE ACTIONS-MINUUTIT-RELAY-FP:HEN, 26.9.2026:
goaliq-appin Actions-kiintiö oli 25.9 90 %:ssa), joten sen cron-tulkin on
oltava tässä eikä sisarpolun takana — sisarpolku ei ole olemassa CI:ssä.

Kattaa vain sen mitä relay tarvitsee: `parse_cron` + `_matches` (due_since)
ja `cron_exprs` (workflow-YAML:n cron-rivit). `firings`/`count_firings`
(S14-mittarin oma tarve) EI ole tässä — ne kuuluvat mittariin, ei relayhin.
"""
from __future__ import annotations

import re
from datetime import datetime


def _field(spec: str, lo: int, hi: int) -> set[int]:
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        step = 1
        if "/" in part:
            part, s = part.split("/", 1)
            step = int(s)
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            a, b = (int(x) for x in part.split("-", 1))
        else:
            a = b = int(part)
        out.update(range(a, b + 1, step))
    return out


def parse_cron(expr: str) -> dict:
    m, h, dom, mon, dow = expr.split()
    return {"min": _field(m, 0, 59), "hour": _field(h, 0, 23),
            "dom": _field(dom, 1, 31), "mon": _field(mon, 1, 12),
            "dow": _field(dow, 0, 7), "dom_any": dom == "*", "dow_any": dow == "*"}


def _matches(c: dict, t: datetime) -> bool:
    if t.minute not in c["min"] or t.hour not in c["hour"] or t.month not in c["mon"]:
        return False
    dow = (t.weekday() + 1) % 7   # cron: 0 = sunnuntai
    dom_ok = t.day in c["dom"]
    dow_ok = dow in c["dow"] or (dow == 0 and 7 in c["dow"])
    if c["dom_any"] and c["dow_any"]:
        return True
    if c["dom_any"]:
        return dow_ok
    if c["dow_any"]:
        return dom_ok
    return dom_ok or dow_ok


CRON_RE = re.compile(r"^\s*-\s*cron:\s*['\"]([^'\"]+)['\"]", re.M)


def cron_exprs(yaml_text: str) -> list[str]:
    return CRON_RE.findall(yaml_text)
