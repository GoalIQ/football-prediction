"""PostHogiin ei saa lahtea kirjautumissalaisuuksia (14.9.2026).

TAUSTA: Google-kirjautumisen ja magic linkin paluuosoite on
`https://pro.goaliq.app/#access_token=<JWT>&provider_token=<google>&refresh_token=...`.
posthog-js tallensi sen sellaisenaan. Mitattu 14.9: 72 tapahtumaa, 8 henkiloa,
16.7. alkaen, viidessa eri kentassa: `$current_url`, `$session_entry_url`,
`$set` / `$set_once` (-> henkilon `$initial_current_url`) ja
`$web_vitals_*_event`.

MITA TAMA VARTIOI (CLAUDE.md 6a: yksi lukija joka ei voi palauttaa vaaraa):
  1. `scrubSecrets` poistaa salaisuudet MISTA TAHANSA kentasta, myos sellaisesta
     jota ei viela ole (rekursiivinen, ei kenttalistaa). Fikstuurit ovat
     tuotannossa nahdyn tapahtuman muotoisia.
  2. Negatiiviset kontrollit: tavalliset osoitteet, `?ref=ROWAN`, `src`/`srcp`
     ja PostHogin oma projektiavain (`token`) sailyvat. Ilman niita koukku
     joka tyhjentaa kaiken lapaisisi kohdan 1 ja rikkoisi analytiikan.
  3. KUTSUPAIKKA: `posthog.init` kayttaa koukkua, ja SPA:ssa on tasan yksi
     `posthog.init`. Funktion testi yksin olisi vihrea vaikka kukaan ei
     kutsuisi sita (muisti: testi-kutsuu-funktiota-ei-kutsupaikkaa).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

FP = Path(__file__).resolve().parents[1]
SRC = FP / "web" / "pro-spa" / "src"
HARNESS = FP / "tests" / "js" / "scrub_secrets_harness.mjs"

# Synteettiset, mutta samaa muotoa kuin tuotannossa: JWT on kolme base64url-osaa,
# Googlen token alkaa ya29., Supabasen refresh-token on lyhyt satunnaisjono.
JWT = ("eyJhbGciOiJFUzI1NiIsImtpZCI6InRlc3QiLCJ0eXAiOiJKV1QifQ"
       ".eyJzdWIiOiIwMDAwIiwiZW1haWwiOiJ4QGV4YW1wbGUuY29tIn0"
       ".c2lnbmF0dXJlLXRlc3QtdmFsdWU")
GOOGLE = "ya29.a0AdMD6ExampleExampleExample_-Example"
REFRESH = "hqqtestrefresh"
RETURN_URL = (f"https://pro.goaliq.app/#access_token={JWT}&expires_at=1789290294"
              f"&expires_in=3600&provider_token={GOOGLE}"
              f"&refresh_token={REFRESH}&sb=&token_type=bearer")
SECRETS = (JWT, GOOGLE, REFRESH, "eyJhbGciOiJFUzI1NiIsImtpZCI6InRlc3Qi")

PROJECT_KEY = "phc_ExampleProjectKey123"

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node puuttuu tasta ymparistosta")


def _scrub(values: list) -> list:
    r = subprocess.run(
        ["node", "--experimental-strip-types", "--no-warnings", str(HARNESS)],
        input=json.dumps(values), capture_output=True, text=True,
        encoding="utf-8", timeout=60, cwd=str(FP))
    assert r.returncode == 0, f"harness kaatui:\n{r.stderr}"
    return json.loads(r.stdout)


def _production_shaped_event() -> dict:
    """Tapahtuma siina muodossa kuin posthog-js antaa sen before_sendille.
    Jokainen 14.9 mitattu vuotokentta on mukana."""
    vitals = {"name": "FCP", "value": 812, "$current_url": RETURN_URL}
    return {
        "uuid": "01990000-0000-7000-8000-000000000000",
        "event": "$pageview",
        "properties": {
            "token": PROJECT_KEY,
            "$current_url": RETURN_URL,
            "$session_entry_url": RETURN_URL,
            "$referrer": "https://goaliq.app/",
            "$pathname": "/",
            "$web_vitals_FCP_event": vitals,
            "$set": {"$current_url": RETURN_URL},
            "$set_once": {"$initial_current_url": RETURN_URL},
        },
        "$set": {"$current_url": RETURN_URL},
        "$set_once": {"$initial_current_url": RETURN_URL},
        "timestamp": "2026-09-13T08:04:55.744Z",
    }


def test_production_shaped_event_has_no_secrets():
    [out] = _scrub([_production_shaped_event()])
    dumped = json.dumps(out)
    for s in SECRETS:
        assert s not in dumped, f"salaisuus jai tapahtumaan: {s[:12]}..."
    # Osoite sailyy kayttokelpoisena analytiikalle: vain arvot pois.
    assert out["properties"]["$current_url"].startswith(
        "https://pro.goaliq.app/#access_token=[redacted]")
    assert "expires_in=3600" in out["properties"]["$current_url"]


def test_unknown_future_field_is_covered():
    """Kentta jota posthog-js ei viela lahetta. Kenttalistaan perustuva
    korjaus paastaisi taman lapi; rekursiivinen ei."""
    [out] = _scrub([{"properties": {"$some_new_url_field": [{"x": RETURN_URL}]}}])
    assert JWT not in json.dumps(out) and GOOGLE not in json.dumps(out)


def test_bare_jwt_without_param_name():
    [out] = _scrub([{"properties": {"$exception_message": f"bad token {JWT} rejected"}}])
    assert JWT not in json.dumps(out)


def test_query_string_and_magic_link_forms():
    urls = [f"https://pro.goaliq.app/?token_hash=abc123def&type=magiclink",
            f"https://pro.goaliq.app/?x=1&refresh_token={REFRESH}#tools=week",
            f"access_token={JWT}"]
    out = _scrub(urls)
    assert "abc123def" not in out[0] and "type=magiclink" in out[0]
    assert REFRESH not in out[1] and out[1].endswith("#tools=week")
    assert JWT not in out[2]


def test_deeper_than_recursion_cap_is_still_scrubbed():
    """Syvyyskatto ei saa olla fail-open."""
    node: dict = {"leaf": RETURN_URL}
    for _ in range(40):
        node = {"child": node}
    [out] = _scrub([node])
    assert JWT not in json.dumps(out)


@pytest.mark.parametrize("value", [
    "https://pro.goaliq.app/?src=nav-signin&srcp=fpl",
    "https://pro.goaliq.app/?ref=ROWAN#tools=week",
    "https://pro.goaliq.app/players/leaders",
    "https://goaliq.app/",
    PROJECT_KEY,
    "checkout_opened",
    "",
])
def test_negative_controls_unchanged(value):
    assert _scrub([value]) == [value]


def test_non_string_values_survive():
    event = {"properties": {"price": 25, "ok": True, "none": None, "list": [1, 2]}}
    assert _scrub([event]) == [event]


# ---------------------------------------------------------------------------
# KUTSUPAIKKA
# ---------------------------------------------------------------------------

def _spa_sources() -> list[Path]:
    return [p for p in SRC.rglob("*") if p.suffix in (".ts", ".svelte", ".js")]


def test_posthog_init_uses_scrub_hook():
    text = (SRC / "lib" / "analytics.ts").read_text(encoding="utf-8")
    m = re.search(r"posthog\.init\(\s*POSTHOG_KEY\s*,\s*\{(.*?)\n\t*\}\);", text, re.S)
    assert m, "posthog.init-kutsua ei loytynyt analytics.ts:sta"
    opts = re.sub(r"//[^\n]*", "", m.group(1))
    assert re.search(r"\bbefore_send\s*:[^\n]*\bscrubSecrets\s*\(", opts), (
        "posthog.init ei kayta scrubSecrets-koukkua: kirjautumistokenit "
        "vuotavat PostHogiin OAuth-paluun osoitteesta")


def test_single_posthog_instance_in_spa():
    """Toinen init ohittaisi koukun kokonaan."""
    inits = [p for p in _spa_sources()
             if re.search(r"\bposthog\w*\.init\s*\(", p.read_text(encoding="utf-8"))]
    assert [p.name for p in inits] == ["analytics.ts"], (
        f"posthog.init loytyy useammasta tiedostosta: {inits}. Jokainen "
        "instanssi tarvitsee scrubSecrets-koukun.")
