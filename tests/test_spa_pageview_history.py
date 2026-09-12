# -*- coding: utf-8 -*-
"""Portti: pro-SPA:n PostHog mittaa sivunvaihdot, ei vain ensimmaista latausta.

MITATTU VIKA (12.9.2026). `web/pro-spa/src/lib/analytics.ts` kaynnisti
posthogin `capture_pageview: true`. Se kirjaa $pageview:n vain sivun
ensilatauksessa. SvelteKit navigoi history.pushState:lla eika lataa sivua
uudelleen, joten SPA:n sisainen liikkuminen ei nakynyt: PostHogissa 1.16
eri reittia per henkilo $pageview-tapahtumista, kun samat kayttajat
kayttivat tyokalutapahtumissa 22 eri reittia.

Asennettu posthog-js (1.396.6) tukee arvoa `'history_change'`:
`@posthog/types/dist/posthog-config.d.ts` ("Capture pageviews on the initial
page load and on history API changes (pushState, replaceState, popstate)").
`capture_pageleave` on oletuksena `'if_capture_pageview'`, joka
`posthog-core.js`:n `_shouldCapturePageleave`:ssa hyvaksyy myos
`'history_change'`:n, joten pageleave sailyy paalla.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

FP = Path(__file__).resolve().parents[1]
SPA = FP / "web" / "pro-spa"
ANALYTICS = SPA / "src" / "lib" / "analytics.ts"
TYPES = SPA / "node_modules" / "@posthog" / "types" / "dist" / "posthog-config.d.ts"
LOCK = SPA / "package-lock.json"


def _init_options() -> str:
    """posthog.init(...) -kutsun optio-objekti ilman rivikommentteja."""
    src = ANALYTICS.read_text(encoding="utf-8")
    m = re.search(r"posthog\.init\(\s*POSTHOG_KEY\s*,\s*\{(.*?)\n\s*\}\s*\);", src, re.S)
    assert m, "analytics.ts: posthog.init(POSTHOG_KEY, {...}) -kutsua ei loydy"
    return "\n".join(line for line in m.group(1).splitlines() if not line.strip().startswith("//"))


def _option(opts: str, key: str) -> list[str]:
    return [v.strip() for v in re.findall(rf"\b{key}\s*:\s*([^,\n]+)", opts)]


def test_pageview_follows_history_changes() -> None:
    values = _option(_init_options(), "capture_pageview")
    assert values == ["'history_change'"], (
        "capture_pageview pitaa olla 'history_change': arvo true kirjaa vain "
        "ensilatauksen, ja SPA:n navigointi jaa mittaamatta. "
        f"Nyt: {values}"
    )


def test_pageleave_is_not_switched_off() -> None:
    values = _option(_init_options(), "capture_pageleave")
    assert values in ([], ["'if_capture_pageview'"], ["true"]), (
        f"capture_pageleave ei saa sammua pageview-muutoksen mukana, nyt: {values}"
    )


def test_installed_posthog_accepts_history_change() -> None:
    if not TYPES.exists():
        pytest.skip("web/pro-spa/node_modules puuttuu (npm install ajamatta)")
    decl = re.search(r"\bcapture_pageview\s*:\s*([^;]+);", TYPES.read_text(encoding="utf-8"))
    assert decl and "'history_change'" in decl.group(1), (
        f"asennettu @posthog/types ei tunne 'history_change'-arvoa: {decl and decl.group(1)}"
    )


def test_locked_posthog_version_supports_history_change() -> None:
    if not LOCK.exists():
        pytest.skip("web/pro-spa/package-lock.json puuttuu")
    pkgs = json.loads(LOCK.read_text(encoding="utf-8")).get("packages", {})
    ver = (pkgs.get("node_modules/posthog-js") or {}).get("version")
    assert ver, "package-lock.json: posthog-js puuttuu"
    got = tuple(int(x) for x in re.findall(r"\d+", ver)[:3])
    # 1.396.6 on versio josta tyyppi ja HistoryAutocapture tarkistettiin 12.9.2026.
    assert got >= (1, 396, 6), f"lukittu posthog-js {ver} on vanhempi kuin tarkistettu 1.396.6"
