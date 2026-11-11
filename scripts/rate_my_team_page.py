# -*- coding: utf-8 -*-
"""Hub-sivu /fpl/rate-my-team (11.11.2026, Villen GO myyntiraportin keinolle 2).

MIKSI
-----
Search Console 8.11: haku "rate this team out of 100" antaa GoalIQ:lle sijan 1,
mutta CTR on 0 %, koska hubissa ei ole sivua joka vastaa siihen. SPA:n
`pro.goaliq.app/team/rate-my-team` kanonisoituu `/team`:iin eika ole hubissa.
Sivun lupaus on kayttajan OMA joukkue arvioituna, ei mallin poiminnat (Villen
X-havainto 11.11: "mallien kayttaminen on huijaamista").

MITA SIVU TEKEE
---------------
Team ID -kentta -> `GET https://api.goaliq.app/api/fantasy/rate-team?entry=N`.
Palvelin rajaa vastauksen itse (`api.premium.mask_rate_team_preview_payload`):
arvosana 0-100, prosentti, `beats_benchmark`, kapteeni ja meta. Kentista on
yksi lahde, joten sivu ei nimea tiereja itse. Tayden analyysin linkki vie
SPA:han `?entry=N&src=rate-my-team`,
jolloin SPA ajaa saman arvion itse (`entry_handoff`) ja `src` merkitsee
ostoketjun lahteen (`funnel.ts` markEntry -> `signup_completed` kantaa
`entry_source = src:rate-my-team`).

SAANTO 6a: MIKA VOI VAIHTUA ALLA
--------------------------------
Kierros, deadline, projektion ika (Understat-katko 1.11: projektio jai
GW10:een deadlinen yli), kauden loppu. Yksi lukija `rmtState()` paattaa mita
naytetaan, ja se ajetaan Nodessa synteettisilla vaiheilla
(tests/test_rate_my_team_page.py):
  - `meta.projection_rolled_from` asetettu (palvelin: projektio on rakennettu
    kierrokselle jonka deadline on mennyt) -> EI arvosanaa, vaan "projektio
    rakennetaan uudelleen"
  - `meta.deadline_time` mennyt selaimen kellolla -> EI arvosanaa
  - `meta.projection_rolled_from` PUUTTUU (vanha API: hub voi deployata ennen
    Renderia) -> EI arvosanaa (fail-closed)
  - deadline puuttuu -> kausi ohi / tuntematon, EI arvosanaa (fail-closed)
Sivu itse on staattinen (ei dataa paistohetkelta), joten se ei voi vanhentua
paistossa: kaikki aikasidottu tulee API:sta ajossa.

COPY: `COPY` on sivun KAIKKI nakyva teksti yhdessa paikassa. Julkaisutarkistaja
lukee taman sanakirjan; JS saa saman JSONina, joten teksti ei voi erota
skriptin ja raportin valilla.
"""
from __future__ import annotations

import json
from html import escape

API_BASE = "https://api.goaliq.app"
PATH = "/fpl/rate-my-team"
SPA_TOOL = "https://pro.goaliq.app/team/rate-my-team"
SRC_TAG = "rate-my-team"

# 🔴 Luonnos: julkaisutarkistaja ei ole viela lukenut naita (11.11). Muutos
# tanne = julkinen teksti -> portti ennen mergea.
COPY: dict[str, str] = {
    "title": "Rate my FPL team out of 100 | GoalIQ",
    "desc": ("Enter your FPL team ID and get a rating out of 100: your XI's projected "
             "points against the strongest XI the model found for 100.0m. Free."),
    "h1": "Rate your FPL team out of 100",
    "lede": "Your own squad, rated. Enter your FPL team ID and get a rating out of 100. Free, no sign-in.",
    "label": "Your FPL team ID",
    "help": ("It is the number in the address of your Points page, for example "
             "fantasy.premierleague.com/entry/123456/event/10. You can paste the whole link."),
    "button": "Rate my team",
    "loading": "Rating your team",
    "out_of": "out of 100",
    "share": "Your XI projects {pct}% of the points of the strongest XI the model found for 100.0m over the next {n} gameweeks.",
    "share_n1": "Your XI projects {pct}% of the points of the strongest XI the model found for 100.0m in the next gameweek.",
    "share_any": "Your XI projects {pct}% of the points of the strongest XI the model found for 100.0m over the coming gameweeks.",
    "beats": "Your XI projects more points than the strongest XI the model found for 100.0m over the next {n} gameweeks. That happens when a squad is worth more than 100.0m or the search missed a stronger 15.",
    "beats_any": "Your XI projects more points than the strongest XI the model found for 100.0m over the coming gameweeks. That happens when a squad is worth more than 100.0m or the search missed a stronger 15.",
    "captain": "Suggested captain from your XI for gameweek {gw}: {name} ({team}), {xp} expected points.",
    "basis": "Rated on the squad you picked for gameweek {gw}.",
    "outdated": "FPL shows other sites your picks and transfers only after a deadline, so moves you have made for gameweek {next} are not in this rating yet.",
    "deadline": "Next deadline: gameweek {gw}, {time}.",
    "updated": "Projections built {date}.",
    "cta_lead": "Premium shows the weak spot in your XI and whether to hold or which move to make.",
    "cta": "See the full analysis",
    "stale": "Ratings are paused. The projections were last built for gameweek {built}, and that deadline has passed. The rating comes back once the projections for gameweek {gw} are rebuilt.",
    "stale_unknown": "Ratings are paused because the projections are being rebuilt. Try again later.",
    "locked": "The gameweek {gw} deadline has passed. Ratings for the next gameweek start once its projections are built.",
    "closed": "There is no FPL deadline ahead, so there is nothing to rate until the next season starts.",
    "err_input": "Enter your FPL team ID: the number from the address of your Points page.",
    "err_400": "That does not look like an FPL team ID. It is a number, usually six to eight digits.",
    "err_404": "FPL has no team with that ID, or the team has not played a gameweek yet.",
    "err_503": "The projections are not available right now. Try again in a few minutes.",
    "err_net": "Could not reach GoalIQ. Check your connection and try again.",
    "err_other": "Something went wrong while rating the team. Try again in a minute.",
    "meaning_h2": "What the number means",
    "meaning": ("100 means the best XI from your 15 projects as many points over the coming "
                "gameweeks as the strongest XI the model found inside the 100.0m budget. The "
                "captain is not counted on either side. The projections are GoalIQ's own model, "
                "not FPL's official expected points, and they are updated daily."),
    "own_h2": "Your squad as it stands",
    "own": ("The rating reads the 15 you already have from FPL's public data and says how they "
            "project. What you do with that is your call."),
    "privacy": "The team ID is public FPL data.",
}

# Sivun oma tyyli: lomake ja tulos. Muu tulee longtail-rungosta (_page).
CSS = (
    "<style>"
    ".rmt-form{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;margin:6px 0 4px;}"
    ".rmt-form label{display:block;width:100%;font-family:var(--mono);font-size:var(--fs-small);"
    "color:var(--muted);text-transform:uppercase;letter-spacing:.04em;}"
    ".rmt-form input{flex:1 1 220px;min-width:0;background:var(--paper);color:var(--cream);"
    "border:1px solid var(--line-strong);padding:12px 14px;font-family:var(--mono);font-size:var(--fs-lead);}"
    ".rmt-form input:focus{outline:2px solid var(--amber);outline-offset:1px;}"
    ".rmt-form button{flex:0 0 auto;}"
    ".rmt-help{color:var(--muted);font-size:var(--fs-small);margin:4px 0 18px;overflow-wrap:anywhere;}"
    ".rmt-out{margin:18px 0;}"
    ".rmt-score{display:flex;align-items:baseline;gap:10px;margin:0 0 10px;}"
    ".rmt-score b{font-family:var(--mono);font-size:56px;line-height:1;color:var(--amber);}"
    ".rmt-score span{font-family:var(--mono);color:var(--muted);}"
    ".rmt-out p{margin:0 0 10px;}"
    ".rmt-msg{border:1px solid var(--line);background:var(--paper);padding:14px 16px;}"
    # `.giq-btn.giq-btn{display:inline-flex}` ohittaa UA:n [hidden]-saannon: mitattu 11.11
    # headless Chromella, CTA nakyi "paused"-tilassa. Sama tarkkuus + !important.
    "#rmt-cta[hidden]{display:none!important;}"
    "</style>"
)

# 🔴 rmtState ja parseEntry ovat PUHTAITA: ei DOMia, ei kelloa (kello
# annetaan). Testi leikkaa ne merkkien valista ja ajaa Nodessa.
STATE_JS = r"""/*RMT-PURE-START*/
function parseEntry(s) {
  s = String(s == null ? '' : s).trim();
  var m = s.match(/entry\/(\d{1,10})(?:\/|$|\?|#)/);
  if (m) return m[1];
  if (/^\d{1,10}$/.test(s)) return s;
  return null;
}
function rmtState(p, now) {
  if (!p || !p.rating || typeof p.rating.rating !== 'number') return {kind: 'invalid'};
  var m = p.meta || {};
  var gw = (typeof m.deadline_gameweek === 'number') ? m.deadline_gameweek : null;
  if (typeof m.projection_rolled_from === 'number') {
    // Season over: no next gameweek, so the stale text would print without a number.
    if (gw === null) return {kind: 'closed'};
    return {kind: 'stale', built: m.projection_rolled_from, gw: gw};
  }
  // Old API without the field (the hub can deploy before Render): missing data is not a healthy state.
  if (!('projection_rolled_from' in m)) return {kind: 'stale', built: null, gw: gw};
  if (gw === null) return {kind: 'closed'};
  var dl = m.deadline_time ? Date.parse(m.deadline_time) : NaN;
  if (!isFinite(dl)) return {kind: 'stale', built: null, gw: gw};
  if (dl <= now) return {kind: 'locked', gw: gw};
  return {kind: 'ok', gw: gw, deadline: dl};
}
function fill(t, v) {
  return String(t).replace(/\{(\w+)\}/g, function (_, k) { return (v && v[k] != null) ? String(v[k]) : ''; });
}
/*RMT-PURE-END*/
"""

UI_JS = r"""(function () {
  'use strict';
  var C = window.__RMT_COPY__, API = window.__RMT_API__, SPA = window.__RMT_SPA__, SRC = window.__RMT_SRC__;
  var form = document.getElementById('rmt-form'), input = document.getElementById('rmt-id');
  var out = document.getElementById('rmt-out'), cta = document.getElementById('rmt-cta');
  if (!form || !input || !out) return;
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function msg(text) { out.innerHTML = ''; out.appendChild(el('p', 'rmt-msg', text)); if (cta) cta.hidden = true; }
  function track(name, props) { try { if (window.posthog) posthog.capture(name, props || {}); } catch (e) {} }
  function dateText(iso) {
    var d = new Date(iso); if (!isFinite(d.getTime())) return null;
    try { return d.toLocaleDateString(undefined, {day: 'numeric', month: 'short', year: 'numeric'}); } catch (e) { return d.toISOString().slice(0, 10); }
  }
  function timeText(ms) {
    var d = new Date(ms);
    try { return d.toLocaleString(undefined, {weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'}); } catch (e) { return d.toISOString(); }
  }
  function render(p, id) {
    var s = rmtState(p, Date.now());
    track('hub_rate_team_result', {state: s.kind});
    if (s.kind === 'invalid') return msg(C.err_other);
    if (s.kind === 'stale') return msg(s.built != null ? fill(C.stale, {built: s.built, gw: s.gw}) : C.stale_unknown);
    if (s.kind === 'locked') return msg(fill(C.locked, {gw: s.gw}));
    if (s.kind === 'closed') return msg(C.closed);
    var r = p.rating, m = p.meta || {}, n = m.horizon_total_gw;
    out.innerHTML = '';
    var sc = el('div', 'rmt-score'); sc.appendChild(el('b', null, String(r.rating))); sc.appendChild(el('span', null, C.out_of));
    out.appendChild(sc);
    var pct = r.rating;
    var known = (typeof n === 'number' && n > 0);
    out.appendChild(el('p', null, r.beats_benchmark ? fill(known ? C.beats : C.beats_any, {n: n})
      : fill(!known ? C.share_any : (n === 1 ? C.share_n1 : C.share), {pct: pct, n: n})));
    var cap = p.captain && p.captain.pick;
    if (cap && cap.web_name && typeof cap.gw_xp === 'number') {
      out.appendChild(el('p', null, fill(C.captain, {gw: m.captain_gw || s.gw, name: cap.web_name, team: cap.team_short || '', xp: cap.gw_xp.toFixed(1)})));
    }
    if (typeof m.picks_gw === 'number') out.appendChild(el('p', 'note', fill(C.basis, {gw: m.picks_gw})));
    if (m.picks_outdated) out.appendChild(el('p', 'note', fill(C.outdated, {next: s.gw})));
    out.appendChild(el('p', 'note', fill(C.deadline, {gw: s.gw, time: timeText(s.deadline)})));
    var built = m.generated_at ? dateText(m.generated_at) : null;
    if (built) out.appendChild(el('p', 'note', fill(C.updated, {date: built})));
    if (cta) {
      try {
        var u = new URL(cta.getAttribute('href') || SPA, location.href);
        u.searchParams.set('entry', id);
        u.searchParams.set('src', SRC);
        u.searchParams.set('srcp', 'fpl-rate-my-team');
        cta.setAttribute('href', u.toString());
      } catch (e) {}
      cta.hidden = false;
    }
  }
  function run(id) {
    out.innerHTML = ''; out.appendChild(el('p', 'note', C.loading));
    track('hub_rate_team_submitted', {});
    var ctrl = ('AbortController' in window) ? new AbortController() : null;
    var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, 45000) : null;
    fetch(API + '/api/fantasy/rate-team?entry=' + encodeURIComponent(id), ctrl ? {signal: ctrl.signal} : {})
      .then(function (res) {
        if (timer) clearTimeout(timer);
        if (res.ok) return res.json().then(function (p) { render(p, id); });
        track('hub_rate_team_result', {state: 'http_' + res.status});
        msg(res.status === 400 ? C.err_400 : res.status === 404 ? C.err_404 : res.status === 503 ? C.err_503 : C.err_other);
      })
      .catch(function () { if (timer) clearTimeout(timer); track('hub_rate_team_result', {state: 'network'}); msg(C.err_net); });
  }
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var id = parseEntry(input.value);
    if (!id) return msg(C.err_input);
    run(id);
  });
  try {
    var q = new URLSearchParams(location.search).get('entry');
    var pre = parseEntry(q);
    if (pre) { input.value = pre; run(pre); }
  } catch (e) {}
})();
"""


def page_parts(tool_cta: str) -> tuple[str, str, str, str, list[dict]]:
    """(title, desc, hero, body, jsonld). Ei aikaa eika dataa: sivu on sama
    joka paistossa, joten se ei voi vanhentua paistossa (saanto 6a)."""
    c = COPY
    url = f"https://goaliq.app{PATH}"
    hero = (f"<h1>{escape(c['h1'])}</h1>"
            f'<p class="lede">{escape(c["lede"])}</p>')
    config = (
        "<script>"
        f"window.__RMT_COPY__={json.dumps(c, ensure_ascii=False)};"
        f"window.__RMT_API__={json.dumps(API_BASE)};"
        f"window.__RMT_SPA__={json.dumps(SPA_TOOL)};"
        f"window.__RMT_SRC__={json.dumps(SRC_TAG)};"
        "</script>"
    )
    body = (
        CSS
        + '<form id="rmt-form" class="rmt-form" novalidate>'
        f'<label for="rmt-id">{escape(c["label"])}</label>'
        '<input id="rmt-id" name="entry" type="text" inputmode="numeric" autocomplete="off" '
        'spellcheck="false" placeholder="123456">'
        f'<button class="giq-btn giq-btn--primary" type="submit">{escape(c["button"])}</button>'
        "</form>"
        f'<p class="rmt-help">{escape(c["help"])}</p>'
        '<div id="rmt-out" class="rmt-out" aria-live="polite"></div>'
        f'<div class="rec"><p>{escape(c["cta_lead"])}</p>'
        f'<p><a id="rmt-cta" class="giq-btn giq-btn--primary" href="{SPA_TOOL}?src={SRC_TAG}&amp;srcp=fpl-rate-my-team" '
        f'data-cta="rate-my-team" hidden>{escape(c["cta"])}</a></p></div>'
        f"<h2>{escape(c['meaning_h2'])}</h2><p>{escape(c['meaning'])}</p>"
        f"<h2>{escape(c['own_h2'])}</h2><p>{escape(c['own'])}</p>"
        f'<p class="note">{escape(c["privacy"])}</p>'
        + tool_cta
        + config
        + "<script>" + STATE_JS + UI_JS + "</script>"
    )
    jsonld = [{
        "@context": "https://schema.org", "@type": "WebApplication",
        "name": c["h1"], "url": url, "description": c["desc"],
        "applicationCategory": "SportsApplication", "operatingSystem": "Web",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
        "isPartOf": {"@id": "https://goaliq.app/#organization"},
    }]
    return c["title"], c["desc"], hero, body, jsonld
