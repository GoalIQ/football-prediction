# -*- coding: utf-8 -*-
"""/fpl/rate-my-team: sivu ei voi esittaa menneen deadlinen arviota nykyisena (11.11.2026).

TAUSTA. Understat on palauttanut huoltosivun 1.11 ~22 UTC alkaen, ja xP-projektio jai GW10:een GW10:n
deadlinen (6.11 18:30 UTC) yli. API kaantaa kierrokset kellon mukaan (`fpl_gameweek.meta_at_clock`),
joten rate-team vastasi GW11:lle, mutta luvut olivat 1.11:n projektiosta. Uusi hub-sivu nayttaisi
silloin arvosanan "ennen GW11:n deadlinea" luvuista jotka rakennettiin GW10:lle.

SAANTO 6a, kolme mekanismia:
  (1) YKSI LUKIJA: selain paattaa nakyman vain `rmtState()`:lla, ja palvelin kertoo vanhan
      projektion kentassa `meta.projection_rolled_from` (sama lahde kuin `meta_at_clock`).
  (2) POIKKEUKSETON KUTSUPAIKKA: renderointi kulkee `rmtState`:n kautta (lahdetarkistus), eika
      arvosanaa kirjoiteta DOMiin ennen sita.
  (3) INVARIANTTI JOKA VAIHEESSA: sama funktio ajetaan Nodessa synteettisilla hetkilla ennen
      deadlinea, tasan, jalkeen ja uudelleenrakennuksen jalkeen.
Lisaksi sopimus SPA:n kanssa: tayden analyysin linkki kantaa `entry`n ja `src`:n, jotka SPA:n
layout lukee (entry_handoff + markEntry), ja API-osoite on sama kuin SPA:lla.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import src.models.fpl_rate_team as rt
from api.premium import mask_rate_team_payload, mask_rate_team_preview_payload
from scripts import rate_my_team_page as P
from tests.test_fpl_rate_team import _mock_fpl  # noqa: F401 — autouse FPL-mock

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "fpl" / "rate-my-team.html"

DL = "2026-11-21T11:00:00Z"
DL_MS = 1795258800000  # Date.parse(DL)


def _pure_js(html: str) -> str:
    m = re.search(r"/\*RMT-PURE-START\*/(.*?)/\*RMT-PURE-END\*/", html, re.S)
    assert m, "puhdas lohko puuttuu sivulta"
    return m.group(1)


def _node(cases: list[dict]) -> list:
    if shutil.which("node") is None:
        pytest.skip("node puuttuu")
    js = (_pure_js(PAGE.read_text(encoding="utf-8"))
          + "\nvar cases=" + json.dumps(cases) + ";\n"
          "process.stdout.write(JSON.stringify(cases.map(function(c){"
          "return c.fn==='parse' ? parseEntry(c.arg) : rmtState(c.arg, c.now);})));")
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _payload(**meta):
    base = {"deadline_gameweek": 11, "deadline_time": DL, "projection_rolled_from": None}
    base.update(meta)
    return {"rating": {"rating": 74, "rating_max": 100, "percentile": 74.2, "beats_benchmark": False},
            "meta": base}


def test_committed_page_is_what_the_builder_writes():
    import scripts.build_fpl_longtail as L
    assert L.render_rate_my_team().replace("\r\n", "\n") == PAGE.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_sivu_ei_riipu_paistohetkesta():
    """Sivussa ei ole kierrosta, paivaa eika lukua: kaikki aikasidottu tulee API:sta ajossa."""
    import scripts.build_fpl_longtail as L
    a, b = L.render_rate_my_team(), L.render_rate_my_team()
    assert a == b
    nakyva = re.sub(r"<script.*?</script>|<style.*?</style>", "", a, flags=re.S)
    assert not re.search(r"Gameweek \d|GW\d|2026-1\d-\d\d", nakyva), "paistohetken kierros/paiva sivulla"


@pytest.mark.parametrize("now,odotettu", [
    (DL_MS - 3600_000, "ok"),       # ennen deadlinea
    (DL_MS, "locked"),              # tasan
    (DL_MS + 3600_000, "locked"),   # jalkeen, sama (valimuistettu) vastaus
])
def test_vaiheet_deadlinen_ymparilla(now, odotettu):
    (s,) = _node([{"fn": "state", "arg": _payload(), "now": now}])
    assert s["kind"] == odotettu
    if odotettu == "ok":
        assert s["gw"] == 11 and s["deadline"] == DL_MS


def test_vanha_projektio_ei_nay_arvosanana_vaikka_deadline_on_edessa():
    """Understat-katkon tila 11.11: kello on kaantanyt kierroksen 11:een, projektio on GW10:lta."""
    (s,) = _node([{"fn": "state", "arg": _payload(projection_rolled_from=10), "now": DL_MS - 86400_000}])
    assert s == {"kind": "stale", "built": 10, "gw": 11}


def test_uudelleenrakennuksen_jalkeen_arvosana_palaa():
    """Seuraavan kierroksen tuore projektio: rolled_from None ja uusi deadline edessa."""
    seuraava = "2026-11-28T11:00:00Z"
    (s,) = _node([{"fn": "state", "arg": _payload(deadline_gameweek=12, deadline_time=seuraava),
                   "now": DL_MS + 7200_000}])
    assert s["kind"] == "ok" and s["gw"] == 12


@pytest.mark.parametrize("meta,odotettu", [
    ({"deadline_gameweek": None, "deadline_time": None}, "closed"),     # kausi ohi
    ({"deadline_time": None}, "stale"),                                 # deadline tuntematon: fail-closed
    ({"deadline_time": "ei-aika"}, "stale"),
])
def test_puuttuva_tieto_ei_ole_arvosana(meta, odotettu):
    (s,) = _node([{"fn": "state", "arg": _payload(**meta), "now": DL_MS - 3600_000}])
    assert s["kind"] == odotettu


def test_vanha_api_ilman_kenttaa_ei_nayta_arvosanaa():
    """Hub-deploy voi ehtia ennen Render-deployta: vanha vastaus ilman lippua = ei tietoa = ei arvosanaa."""
    p = _payload()
    del p["meta"]["projection_rolled_from"]
    (s,) = _node([{"fn": "state", "arg": p, "now": DL_MS - 3600_000}])
    assert s == {"kind": "stale", "built": None, "gw": 11}


@pytest.mark.parametrize("p", [None, {}, {"rating": {}}, {"rating": {"rating": "74"}, "meta": {}}])
def test_rikkinainen_vastaus_on_invalid(p):
    (s,) = _node([{"fn": "state", "arg": p, "now": 0}])
    assert s["kind"] == "invalid"


@pytest.mark.parametrize("arg,odotettu", [
    ("116920", "116920"),
    ("  116920 ", "116920"),
    ("https://fantasy.premierleague.com/entry/116920/event/10", "116920"),
    ("https://fantasy.premierleague.com/entry/116920/history", "116920"),
    ("fantasy.premierleague.com/entry/116920", "116920"),
    ("entry/12", "12"),
    ("abc", None),
    ("", None),
    (None, None),
    ("12345678901", None),
    ("1169 20", None),
])
def test_team_id_luetaan_numerosta_tai_linkista(arg, odotettu):
    (v,) = _node([{"fn": "parse", "arg": arg}])
    assert v == odotettu


def test_renderointi_kulkee_lukijan_kautta():
    """Arvosana kirjoitetaan vasta rmtState:n 'ok'-haaran jalkeen."""
    ui = P.UI_JS
    i_state = ui.index("var s = rmtState(p, Date.now());")
    i_score = ui.index("String(r.rating)")
    assert i_state < i_score
    for kind in ("invalid", "stale", "locked", "closed"):
        k = ui.index(f"if (s.kind === '{kind}') return")
        assert i_state < k < i_score, kind


def test_palvelin_kertoo_vanhan_projektion(monkeypatch):
    """`meta.projection_rolled_from` = meta_at_clockin `clock_rolled_from`, terveena None."""
    terve = rt.rate_team(entry=424242)["meta"]
    assert "projection_rolled_from" in terve and terve["projection_rolled_from"] is None
    orig = rt._meta_from_events
    monkeypatch.setattr(rt, "_meta_from_events",
                        lambda meta, boot: {**orig(meta, boot), "clock_rolled_from": 10})
    rt._OPTIMAL_XP_CACHE.clear()
    out = rt.rate_team(entry=424242)
    assert out["meta"]["projection_rolled_from"] == 10
    # Ilmainen esimaku ja vanha free-maski paastavat lipun lapi: sivu on ilmainen pinta.
    assert mask_rate_team_preview_payload(out)["meta"]["projection_rolled_from"] == 10
    assert mask_rate_team_payload(out)["meta"]["projection_rolled_from"] == 10


def test_esimaku_sisaltaa_sivun_lukemat_kentat(monkeypatch):
    """Sivu lukee vain ilmaisia kenttia: muuten se nayttaisi tyhjaa ei-Premiumille."""
    prev = mask_rate_team_preview_payload(rt.rate_team(entry=424242))
    r, m = prev["rating"], prev["meta"]
    for k in ("rating", "percentile", "beats_benchmark"):
        assert r.get(k) is not None, k
    for k in ("deadline_gameweek", "deadline_time", "horizon_total_gw", "picks_gw",
              "picks_outdated", "captain_gw", "generated_at"):
        assert k in m, k
    pick = (prev.get("captain") or {}).get("pick") or {}
    assert {"web_name", "team_short", "gw_xp"} <= set(pick)
    ui = P.UI_JS
    for k in ("percentile", "beats_benchmark", "horizon_total_gw", "picks_gw", "picks_outdated",
              "captain_gw", "generated_at", "gw_xp", "team_short", "web_name"):
        assert k in ui, k


def test_linkki_spaan_kantaa_entryn_ja_lahteen_jotka_spa_lukee():
    layout = (ROOT / "web/pro-spa/src/routes/+layout.svelte").read_text(encoding="utf-8")
    assert "q0.get('entry')" in layout and "markEntry(`src:${src}`" in layout
    assert "u.searchParams.set('entry', id);" in P.UI_JS
    assert "u.searchParams.set('src', SRC);" in P.UI_JS
    assert P.SPA_TOOL == "https://pro.goaliq.app/team/rate-my-team"
    tools = (ROOT / "web/pro-spa/src/lib/tools.ts").read_text(encoding="utf-8")
    assert "slug: 'rate-my-team'" in tools and "group: 'team'" in tools


def test_api_osoite_on_sama_kuin_spalla_ja_cors_sallii_sivun():
    cfg = (ROOT / "web/pro-spa/src/lib/config.ts").read_text(encoding="utf-8")
    assert f"?? '{P.API_BASE}'" in cfg
    main = (ROOT / "api/main.py").read_text(encoding="utf-8")
    origins = main[main.index("CORS_ALLOWED_ORIGINS = ["):]
    origins = origins[:origins.index("]")]
    assert '"https://goaliq.app"' in origins


def test_copy_yhdessa_paikassa():
    """JS saa saman sanakirjan JSONina: raportin copy-lista ja sivu eivat voi erota."""
    html = PAGE.read_text(encoding="utf-8")
    assert "window.__RMT_COPY__=" + json.dumps(P.COPY, ensure_ascii=False) + ";" in html
    for k in re.findall(r"C\.(\w+)", P.UI_JS):
        assert k in P.COPY, f"JS lukee puuttuvan copy-avaimen {k}"


def test_piilotettu_cta_on_oikeasti_piilossa():
    """`.giq-btn.giq-btn{display:inline-flex}` (src/site_components.py) ohittaa selaimen [hidden]-saannon.
    Mitattu 11.11 headless Chromella: CTA nakyi "paused"-tilassa ennen tata saantoa."""
    html = PAGE.read_text(encoding="utf-8")
    assert 'id="rmt-cta"' in html and " hidden>" in html
    assert "#rmt-cta[hidden]{display:none!important;}" in html
