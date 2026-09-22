"""Reply-moduulin osiot: YKSI laskenta jota seka generaattori etta lukija ajavat.

X-REPLY-MOOTTORI (22.9.2026, suunnitelma goaliq-app/cos-reports/
ux-uudistus-2026-09/c3-reply-valmius.md luku 2).

MIKSI OSIOT OVAT PUHTAITA FUNKTIOITA
------------------------------------
Generaattori (`scripts/build_reply_module.py`) kutsuu naita kirjoittaessaan
moduulin. Lukija (`reply_module.load_reply_module`) kutsuu SAMOJA funktioita
tuoreella datalla ja vertaa: jos projektio on regeneroitu ja jokin moduulin
luku muuttuisi, lukija kieltaytyy. Kaksi erillista laskentaa (kirjoitus ja
tarkistus) ajautuisivat erilleen hiljaa, ja silloin "moduuli on tuore" olisi
vaite jota mikaan ei mittaa (muisti: yksi lukija tarkoittaa saman FUNKTION).

MIKSI LUKU ON TEKSTINA JA NAYTTOTARKKUUDELLA
-------------------------------------------
Jokainen arvo tallennetaan sellaisena kuin JULKINEN SIVU sen nayttaa
(`text`), samalla pyoristyksella ja samalla funktiolla kuin sivu (`start_pct`,
`_dist_cell`, `fmt_pct`). Reply lainaa tekstia, lukija tarkistaa tekstia.
Jos moduuli tallentaisi 5.48 ja sivu nayttaa 5.5, reply "5.48" olisi luku
jota tarkistusreitilla ei ole (muisti: pyoristyssaanto-eroaa-...).

Jokainen arvo kantaa `routes`-listan: missa julkisessa taulukossa ja milla
rivilla sama teksti pitaisi nakya. Generaattori kavelee listan ja kirjaa
ensimmaisen reitin jolla rivi on; eri teksti samalla rivilla kaataa ajon.
"""
from __future__ import annotations

import re
import unicodedata

MODEL_ENTRY = 116920          # mallin oma FPL-joukkue (fpl.html, gw-calls)
TEMPLATE_EO_MIN = 50.0        # "template" = johtavan otostason EO >= 50 %
CAPTAIN_N = 5
DIFFERENTIAL_N = 5
DIFFERENTIAL_MAX_OWN = 10.0

URL = {
    "gw_xp": "https://goaliq.app/fpl/expected-points#gw-xp",
    "top100": "https://goaliq.app/fpl/expected-points#top-100",
    "differentials": "https://goaliq.app/fpl/differentials",
    "clean_sheets": "https://goaliq.app/fpl#clean-sheets",
    "gw_calls": "https://goaliq.app/fpl#gw-calls",
    "xp_accuracy": "https://goaliq.app/fpl#xp-accuracy",
    "track_record": "https://goaliq.app/fpl#track-record",
    "eo": "https://goaliq.app/fpl#eo-by-tier",
}


def club_url(slug: str) -> str:
    return f"https://goaliq.app/fpl/club/{slug}"


def fpl_entry_url(gw: int, entry: int = MODEL_ENTRY) -> str:
    return f"https://fantasy.premierleague.com/entry/{entry}/event/{gw}"


def slug(name: str, team: str | None = None) -> str:
    """"B.Fernandes", "MUN" -> "b-fernandes-mun". ASCII, jotta avaimen voi
    kirjoittaa luonnokseen kasin ilman ett/o-ongelmia."""
    s = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    if team:
        s = f"{s}-{str(team).lower()}"
    return s


def val(value, text: str, unit: str, src: str, routes: list[tuple[str, tuple]]):
    """Yksi luku. `routes` = [(pinnan tunnus, rivin avain), ...] preferenssijarjestyksessa."""
    return {"value": value, "text": text, "unit": unit, "src": src,
            "routes": [[s, list(k)] for s, k in routes]}


def _pct_int_text(p: dict, key: str) -> str | None:
    from scripts.build_fpl_longtail import _dist_cell
    t = _dist_cell(p, key)
    return None if t == "-" else t


def _players_by_id(xp: dict) -> dict:
    return {int(p["id"]): p for p in (xp.get("players") or []) if p.get("id") is not None}


def _club_slugs() -> dict:
    from scripts.build_fpl_longtail import CLUB_SLUGS
    return CLUB_SLUGS


# ---------------------------------------------------------------------------
# Pelaajan arvot (captain_top5 ja player_lookup kayttavat samaa)
# ---------------------------------------------------------------------------
def player_values(p: dict, gw: int) -> dict:
    """Pelaajan julkiset luvut kierrokselle `gw`, sivun omalla muotoilulla."""
    from scripts.build_fpl_longtail import start_pct
    from src.models.fpl_gw_xp import gw_xp

    name, team = p.get("web_name"), p.get("team_short")
    key = (name, team)
    slugs = _club_slugs()
    club = f"club:{slugs[team]}" if team in slugs else None
    out = {}
    g = gw_xp(p, gw)
    if g is not None:
        out["gw_xp"] = val(round(g, 1), f"{g:.1f}", "xP", "xp", [("gw_xp", key)])
    hz = p.get("xp_horizon_total")
    if isinstance(hz, (int, float)):
        r = [("top100", key)] + ([(club, (name,))] if club else []) + [("differentials", key)]
        out["xp_6gw"] = val(round(float(hz), 1), f"{float(hz):.1f}", "xP", "xp", r)
    pr = p.get("price")
    if isinstance(pr, (int, float)):
        r = [("gw_xp", key), ("top100", key)] + ([(club, (name,))] if club else [])
        out["price"] = val(round(float(pr), 1), f"{float(pr):.1f}", "m", "xp", r)
    pg = p.get("xp_per_gw")
    if isinstance(pg, (int, float)):
        out["xp_per_gw"] = val(round(float(pg), 2), f"{float(pg):.2f}", "xP", "xp",
                               [("top100", key), ("differentials", key)])
    # Jakauma VAIN kun se on taman kierroksen. Kesken kierroksen `xp_dist.gw`
    # on kuluva kierros (mitattu 30.8), ja luku olisi vaaran kierroksen.
    d = p.get("xp_dist") or {}
    if d.get("gw") == gw:
        for k, name_k in (("p_haul", "p_10plus"), ("p_blank", "p_blank")):
            t = _pct_int_text(p, k)
            if t is not None:
                out[name_k] = val(int(t.rstrip("%")), t, "%", "xp", [("top100", key)])
    sp = start_pct(p)
    if sp is not None:
        out["start_pct"] = val(sp, f"{sp}%", "%", "xp", [("gw_xp", key), ("top100", key)])
    xm = p.get("xmins")
    if isinstance(xm, (int, float)):
        out["xmins"] = val(int(f"{float(xm):.0f}"), f"{float(xm):.0f}", "min", "xp",
                           [("top100", key)])
    own = p.get("owned_pct")
    if isinstance(own, (int, float)):
        r = [("top100", key)] + ([(club, (name,))] if club else []) + [("differentials", key)]
        out["owned_pct"] = val(round(float(own), 1), f"{float(own):.1f}%", "%", "xp", r)
    return out


def _player_row(p: dict, gw: int) -> dict:
    from src.models.fpl_gw_xp import opponent_text
    return {"player_id": int(p["id"]), "key": slug(p.get("web_name"), p.get("team_short")),
            "name": p.get("web_name"), "team": p.get("team_short"), "pos": p.get("pos"),
            "opponent": opponent_text(p, gw),
            "values": player_values(p, gw)}


def captain_top5(xp: dict, gw: int, blocklist: list[dict]) -> dict:
    """Sama valinta kuin /fpl/best-captain (MAX_CAPTAIN_PER_CLUB), viisi riviä."""
    from src.models.fpl_gw_xp import MAX_CAPTAIN_PER_CLUB, top_projected
    rows = top_projected(xp.get("players") or [], gw, CAPTAIN_N, blocklist,
                         max_per_club=MAX_CAPTAIN_PER_CLUB)
    return {"available": bool(rows), "gw": gw,
            "rule": ("GW xP top 5, at most 2 per club (same selection as "
                     "goaliq.app/fpl/best-captain)"),
            "rows": [_player_row(p, gw) for p in rows]}


def xp_top5(xp: dict, gw: int, blocklist: list[dict]) -> dict:
    """/fpl/expected-points#gw-xp:n viisi ensimmaista rivia, SAMA funktio kuin sivu
    (`fpl_gw_xp.free_rows`: vaikutettava kierros, max 3 per seura, estolista).

    Oma osio eika captain_top5: kapteenilista rajaa 2 per seura, joten sen
    jarjestys voi erota sivun jarjestyksesta. Kortti joka numeroi rivit 1-5 ja
    ohjaa #gw-xp:hen tarvitsee sivun oman jarjestyksen.
    """
    from src.models.fpl_gw_xp import free_rows
    fgw, rows = free_rows(xp, blocklist)
    if fgw != gw:
        return {"available": False, "gw": gw,
                "reason": f"free GW xP list is for GW{fgw}"}
    out = []
    for i, p in enumerate(rows[:5]):
        r = _player_row(p, gw)
        key = (p.get("web_name"), p.get("team_short"))
        r["values"]["rank"] = val(i + 1, str(i + 1), "#", "xp", [("gw_xp", key)])
        out.append(r)
    return {"available": bool(out), "gw": gw,
            "rule": "GW xP top 5, at most 3 per club (same list as goaliq.app/fpl/expected-points#gw-xp)",
            "rows": out}


def player_lookup(xp: dict, gw: int, blocklist: list[dict]) -> dict:
    """Jokainen projektion pelaaja. Estolistan nimet pois (ei markkinointiin)."""
    from src.models.fpl_gw_xp import excluded
    rows = [_player_row(p, gw) for p in (xp.get("players") or [])
            if p.get("id") is not None and not excluded(p.get("web_name"), blocklist)]
    return {"available": bool(rows), "gw": gw, "rows": rows}


# ---------------------------------------------------------------------------
# Puhtaat pelit: sama tiedosto ja sama muotoilu kuin /fpl#clean-sheets
# ---------------------------------------------------------------------------
def cs_top(phase0: dict, gw: int) -> dict:
    from src.models.fmt import fmt_pct
    rows = []
    for t in phase0.get("teams") or []:
        for fx in t.get("fixtures") or []:
            if fx.get("gw") != gw or fx.get("cs_pct") is None:
                continue
            cs = float(fx["cs_pct"])
            rows.append({
                "key": str(t.get("short") or "").lower(),
                "team": t.get("name"), "team_short": t.get("short"),
                "opponent": fx.get("opponent"), "opponent_short": fx.get("opponent_short"),
                "venue": fx.get("venue"),
                "values": {"cs_pct": val(round(cs, 1), fmt_pct(cs), "%", "phase0",
                                         [("clean_sheets", (t.get("name"),))])},
            })
    # Kaksi ottelua samalla kierroksella = kaksi rivia samalle seuralle. Sivu
    # nayttaa seuran kerran, joten avain erotetaan vastustajalla.
    seen: dict[str, int] = {}
    for r in rows:
        seen[r["key"]] = seen.get(r["key"], 0) + 1
    for r in rows:
        if seen[r["key"]] > 1:
            r["key"] = f"{r['key']}-v-{str(r['opponent_short'] or '').lower()}"
    rows.sort(key=lambda r: (-r["values"]["cs_pct"]["value"], r["team"] or ""))
    return {"available": bool(rows), "gw": gw, "rows": rows}


# ---------------------------------------------------------------------------
# Differentiaalit: sama funktio kuin /fpl/differentials (API:n kautta)
# ---------------------------------------------------------------------------
def differentials(diff_payload: dict, gw: int, n: int = DIFFERENTIAL_N) -> dict:
    meta = diff_payload.get("meta") or {}
    rows = []
    for p in (diff_payload.get("players") or [])[:n]:
        key = (p.get("web_name"), p.get("team_short"))
        rows.append({
            "player_id": int(p["id"]), "key": slug(p.get("web_name"), p.get("team_short")),
            "name": p.get("web_name"), "team": p.get("team_short"), "pos": p.get("pos"),
            "values": {
                "owned_pct": val(round(float(p["owned_pct"]), 1), f"{float(p['owned_pct']):.1f}%",
                                 "%", "differentials", [("differentials", key)]),
                "xp_6gw": val(round(float(p["xp_horizon_total"]), 1),
                              f"{float(p['xp_horizon_total']):.1f}", "xP", "differentials",
                              [("differentials", key)]),
                "xp_per_gw": val(round(float(p["xp_per_gw"]), 2), f"{float(p['xp_per_gw']):.2f}",
                                 "xP", "differentials", [("differentials", key)]),
            }})
    ok = bool(rows) and meta.get("gw") == gw
    return {"available": ok, "gw": gw,
            "reason": None if ok else f"differentials payload is for GW{meta.get('gw')}",
            "rule": (f"owned {DIFFERENTIAL_MAX_OWN:.0f}% or less, ranked by "
                     f"{meta.get('horizon_total_gw') or 6}-gameweek xP (same list as "
                     "goaliq.app/fpl/differentials)"),
            "horizon_gw": meta.get("horizon_total_gw"),
            "rows": rows if ok else []}


# ---------------------------------------------------------------------------
# Mallin XI vs eliitin template
# ---------------------------------------------------------------------------
def model_vs_template(frozen: dict | None, elite: dict | None, frozen_xp: dict | None,
                      gw: int) -> dict:
    """Mallin jaadytetty XI vs template (johtavan otostason EO >= 50 %).

    Saatavilla VAIN kun molemmat puoliskot ovat samalta hetkelta:
    - `model_squad_frozen/gw{N}.json` on olemassa (jaadytetaan ~1 vrk ennen
      deadlinea; ennen sita mallin kierroksen joukkuetta EI OLE),
    - templaten picks-kierros on N-1 (viimeisin julkinen ennen deadlinea) tai
      N (deadlinen jalkeen, toteutunut template).
    Muuten osio on `available: false` syyn kanssa. Vanhempi template olisi
    vaite eilisesta joukosta tamanpaivaisessa asussa (muisti:
    vanha-luku-ei-ole-todiste-nykytilasta).
    """
    if not frozen:
        return {"available": False, "gw": gw,
                "reason": (f"model squad for GW{gw} not frozen yet (it is frozen about "
                           "a day before the deadline)")}
    em = (elite or {}).get("meta") or {}
    pg = em.get("picks_gameweek")
    if pg not in (gw - 1, gw):
        return {"available": False, "gw": gw,
                "reason": (f"template sample is GW{pg} picks (generated "
                           f"{str(em.get('generated_at') or '')[:10]}); GW{gw} needs "
                           f"GW{gw - 1} or GW{gw} picks")}
    tiers = [k for k in ("top1k", "top10k", "top100k")
             if k in ((em.get("sample") or {}))]
    lead = tiers[0] if tiers else "top1k"
    n_lead = ((em.get("sample") or {}).get(lead) or {}).get("n_sampled")
    xi = frozen.get("xi") or []
    xi_ids = {int(p["id"]) for p in xi}
    fxp = {int(p["id"]): p for p in (frozen_xp or {}).get("players") or []}

    def eo(p):
        return float((((p.get("tiers") or {}).get(lead)) or {}).get("eo_pct") or 0.0)

    template = [p for p in (elite or {}).get("players") or [] if eo(p) >= TEMPLATE_EO_MIN]
    t_ids = {int(p["id"]) for p in template}
    lead_label = {"top1k": "top 1k", "top10k": "top 10k", "top100k": "top 100k"}[lead]

    def mrow(p):
        pid = int(p["id"])
        x = fxp.get(pid, {}).get("xp", p.get("xp"))
        return {"player_id": pid, "key": slug(p.get("web_name"), p.get("team_short")),
                "name": p.get("web_name"), "team": p.get("team_short"),
                "values": {"gw_xp_frozen": val(round(float(x or 0), 2), f"{float(x or 0):.2f}",
                                               "xP", "frozen_xp",
                                               [("points_gw", (p.get("web_name"), p.get("team_short")))])}}

    def trow(p):
        pid = int(p["id"])
        fp = fxp.get(pid) or {}
        x = fp.get("xp")
        name = p.get("web_name")
        team = p.get("team")
        vals = {"eo_pct": val(round(eo(p), 1), f"{eo(p):.1f}%", "%", "elite",
                              [("eo", (f"{name} ({team})",))])}
        if x is not None:
            vals["gw_xp_frozen"] = val(round(float(x), 2), f"{float(x):.2f}", "xP", "frozen_xp",
                                       [("points_gw", (name, team))])
        return {"player_id": pid, "key": slug(name, team), "name": name, "team": team,
                "values": vals}

    model_only = sorted((mrow(p) for p in xi if int(p["id"]) not in t_ids),
                        key=lambda r: -r["values"]["gw_xp_frozen"]["value"])
    template_only = [trow(p) for p in sorted(template, key=lambda p: -eo(p))
                     if int(p["id"]) not in xi_ids]
    # xP-ERO VAIN VERTAILUKELPOISENA. Summa yhdeksasta mallin pelaajasta
    # miinus summa viidesta templaten pelaajasta ei ole ero vaan pelaajamaaran
    # ero (mitattu GW4-datalla 22.9: "+14.55"). Ero lasketaan vain kun
    # molemmilla puolilla on yhta monta nimea (yksi yhteen -vaihdot) ja
    # jokaisella on jaadytetty luku. Muuten osio sanoo miksi ei.
    t_known = [r for r in template_only if "gw_xp_frozen" in r["values"]]
    if len(model_only) != len(template_only):
        xp_gap = {"available": False,
                  "reason": (f"{len(model_only)} model-only vs {len(template_only)} "
                             "template-only players: no like-for-like total")}
    elif len(t_known) != len(template_only):
        xp_gap = {"available": False,
                  "reason": "a template player has no frozen GW xP (outside the projection)"}
    else:
        m_sum = sum(r["values"]["gw_xp_frozen"]["value"] for r in model_only)
        t_sum = sum(r["values"]["gw_xp_frozen"]["value"] for r in t_known)
        gap = round(m_sum - t_sum, 2)
        xp_gap = {"available": True, "n_each_side": len(model_only), "values": {
            "gw_xp_gap": val(gap, f"{gap:+.2f}", "xP", "frozen_xp", [])}}
    return {
        "available": True, "gw": gw,
        "template_rule": (f"players with {TEMPLATE_EO_MIN:.0f}% or more effective ownership "
                          f"in the {lead_label} sample (n={n_lead}), GW{pg} picks"),
        "template_picks_gw": pg, "template_generated_at": em.get("generated_at"),
        "model_frozen_at": (frozen.get("meta") or {}).get("frozen_at"),
        "model_only": model_only, "template_only": template_only,
        "xp_gap": xp_gap,
    }


# ---------------------------------------------------------------------------
# Viimeisin pelattu kierros ja track record
# ---------------------------------------------------------------------------
def last_gw(entry_event: dict | None, events: list[dict], gw_calls: dict | None,
            next_gw: int, live_points: dict | None = None,
            captain_multiplier: int = 2) -> dict:
    """Viimeisin KOKONAAN pelattu ja FPL:n tarkistama kierros ennen `next_gw`:ta.

    Kesken kierroksen (deadline mennyt, ottelut kesken) edellinen kierros on
    viimeisin pelattu - kesken olevan kierroksen pisteet eivat ole tulos.
    """
    done = [e for e in events if e.get("finished") and e.get("data_checked")
            and int(e["id"]) < next_gw]
    if not done:
        return {"available": False, "reason": "no finished and checked gameweek yet"}
    ev = max(done, key=lambda e: int(e["id"]))
    g = int(ev["id"])
    eh = (entry_event or {}).get("entry_history") or {}
    if int(eh.get("event") or -1) != g:
        return {"available": False, "gw": g,
                "reason": f"FPL entry {MODEL_ENTRY} history for GW{g} not fetched"}
    url = fpl_entry_url(g)
    vals = {
        "entry_points": val(int(eh["points"]), str(int(eh["points"])), "pts", "fpl_entry",
                            [("fpl_entry", ("points",))]),
        "fpl_average": val(int(ev["average_entry_score"]), str(int(ev["average_entry_score"])),
                           "pts", "fpl_bootstrap", [("fpl_entry", ("average",))]),
    }
    if eh.get("event_transfers_cost"):
        c = int(eh["event_transfers_cost"])
        vals["transfer_cost"] = val(c, str(c), "pts", "fpl_entry", [("fpl_entry", ("cost",))])
    cap = None
    for row in (gw_calls or {}).get("gameweeks") or []:
        if row.get("gw") != g:
            continue
        for c in row.get("calls") or []:
            if c.get("call") == "model_captain":
                cap = c
    out = {"available": True, "gw": g, "entry": MODEL_ENTRY, "entry_url": url,
           "values": vals}
    # Kapteenin pisteet FPL:n live-datasta (alkuperaislahde); reitti on
    # /fpl#gw-calls-rivi "Model squad captain", joka nayttaa samat luvut.
    pid = (cap or {}).get("player_id")
    if pid is not None and live_points and int(pid) in live_points:
        pts = int(live_points[int(pid)])
        # Kerroin entryn picksista (Triple Captain = 3); jaadytetty runko ei
        # kanna chipia (GW3: meta.chip None vaikka sivu sanoo "tripled").
        captain_multiplier = next(
            (int(pk["multiplier"]) for pk in (entry_event or {}).get("picks") or []
             if int(pk.get("element") or -1) == int(pid)
             and int(pk.get("multiplier") or 0) >= 2), int(captain_multiplier))
        ret = pts * int(captain_multiplier)
        out["captain"] = {
            "player_id": int(pid), "name": cap.get("web_name"), "team": cap.get("team_short"),
            "multiplier": int(captain_multiplier),
            "values": {
                "captain_points": val(pts, str(pts), "pts", "fpl_live",
                                      [("gw_calls", (g, "Model squad captain"))]),
                "captain_return": val(ret, str(ret), "pts", "fpl_live",
                                      [("gw_calls", (g, "Model squad captain", "return"))]),
            }}
    return out


def track_record(acc: dict | None, xp_acc: dict | None) -> dict:
    from src.models.fmt import fmt_pct
    out = {"available": False, "values": {}}
    at = (acc or {}).get("all_time") or {}
    if at.get("n"):
        n = int(at["n"])
        p = float(at.get("pct_1x2") or 0.0) * 100
        out["values"]["matches_graded"] = val(n, str(n), "matches", "accuracy",
                                              [("track_record", ("n",))])
        out["values"]["pct_1x2"] = val(round(p, 1), fmt_pct(p), "%", "accuracy",
                                       [("track_record", ("pct_1x2",))])
        out["available"] = True
    gws = [g for g in (xp_acc or {}).get("gameweeks") or [] if g.get("mae") is not None]
    if gws:
        g = max(gws, key=lambda x: int(x["gw"]))
        out["xp_mae_gw"] = int(g["gw"])
        out["values"]["xp_mae_last_gw"] = val(round(float(g["mae"]), 2), f"{float(g['mae']):.2f}",
                                              "pts", "xp_accuracy",
                                              [("xp_accuracy", (int(g["gw"]), "mae"))])
        out["values"]["xp_mae_players"] = val(int(g["n"]), str(int(g["n"])), "players",
                                              "xp_accuracy",
                                              [("xp_accuracy", (int(g["gw"]), "players"))])
        out["available"] = True
    return out
