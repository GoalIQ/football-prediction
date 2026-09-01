"""PROJECTED-XI-KORTTI (29.8.2026, GW-PROJECTED-XI-CARD): viikkokortti
"projected points top 15 + mallin free-hit-XI".

MIKSI: Solio Analytics postaa joka kierros ~1 h ennen deadlinea kortin
"Projected pts & Solio picks" (vasen: GW-xP top 15 yhdella desimaalilla,
oikea: esimerkki free-hit-XI kentalla + penkki). Wolfy kysyi 28.8 DM:ssa
"have you posted a team like this" (cos-reports/competitors/
2026-08-28-solio-projected-xi-card.md). Villen paatos 28.8: NUMEROT kortille
(GW-xP top 15, 1 desimaali), ei pelkka jarjestys.

LAHDE: data/fpl_xp_projections.json. GW-xP = gameweeks[].xp headline-GW:lle
(actionable_gameweek), EI xp_per_gw (6 GW:n keskiarvo; muisti
xp-per-gw-ei-ole-gw-xp). XI = free_optimum() samasta poolista kuin mallin
oma rivi, mutta pelaajan arvona TAMAN kierroksen xP (free hit = yhden
kierroksen paras 15 samoilla joukkuesaannoilla: 100.0m, max 3/seura).
Kapteeni = XI:n korkein GW-xP, penkki FPL:n penkkijarjestyksessa.

PORTIT (kaikki generaattorissa, ei vasta postauksessa):
  - vain status 'a' (loukkaantunut/epavarma ei nouse kortille)
  - estolista scripts/publish_blocklist.json + Thiaw-esto sukunimiosalla
    (sama kuin render_standouts_card._excluded): estetty nimi ei paady
    top-15:een EIKA XI-pooliin; lisaksi publish_gate.blocked_names ajetaan
    valmiille tekstille (kaksi vahtia, eri koodipolku)
  - ei em dashia, ei sanoja odds / Pro / optimiser-jargon copyssa
  - kortti ei saa erota data/gw_calls.json:sta ennen deadlinea
    (reconcile kuten standouts: eroava -> kaadu, aja loki ensin)

GW-CALLS-LOKI: XI + kapteeni kirjataan yhdeksi kutsuksi (projected_xi)
data/gw_calls.json:iin ennen deadlinea (src/models/gw_calls.upsert_call),
gradataan FPL:n saannoilla (kapteeni tuplana, autosubit penkilta).
--dry-run ei kirjoita lokiin. Deadlinen jalkeen loki on lukossa (fail-closed).

Tuloste: HTML + PNG (Chrome headless) 1200x675 kuten muut kortit.
    python -m scripts.render_projected_xi_card --out outputs/cards --dry-run
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
from html import escape

from src.brand import logo_svg
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from scripts.build_fpl_longtail import _kit_defs, _kit_svg
from scripts.publish_gate import blocked_names, load_blocklist
from src.models.fpl_gameweek import actionable_gameweek  # portti: ei next_gameweek suoraan
# FREE-GW-XP (30.8): valintafunktiot ovat jaetussa moduulissa, jotta kortti ja
# ilmaissivun tarkistusreitti EIVAT voi laskea eri listaa. Ks. src/models/fpl_gw_xp.
from src.models.fpl_gw_xp import (EXCLUDED_NAMES, club_of as _club_of,
                                  eligible, excluded as _excluded, gw_xp,
                                  opponent_text as _opp_text,
                                  top_projected as _top_projected)
from src.models.gw_calls import (PROJECTED_XI_CALL, DeadlinePassed, NEW_LOG,
                                 build_projected_xi_call, parse_utc,
                                 upsert_call)

XP_PATH = config.DATA_DIR / "fpl_xp_projections.json"
CALLS_LOG_PATH = config.DATA_DIR / "gw_calls.json"
TOP_N = 15
POS_TYPE = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}
TYPE_POS = {v: k for k, v in POS_TYPE.items()}
# Kova saanto: ei Thiaw-juttuja markkinointiin (muisti thiaw-ei-markkinointiin).
# Sama esto kuin standouts-kortilla; estolista taydentaa sita.
# Copy-portti: sanat joita kortilla ei saa olla (em dash, vedonlyonti,
# Premium-termi ilmaispinnalla, optimoijan sisainen sanasto).
BANNED_COPY = ("—", r"\bodds\b", r"\bPro\b", r"\boptimi[sz]er\b", r"\bsolver\b",
               r"\blegal\b", r"\bfeasible\b", r"\bconstraints?\b")

CSS = """
:root{--amber:#F5C542;--ink:#0B0A09;--ink2:#141311;
--cream:#F3F2F2;--muted:#A8A29A;--line:rgba(243,242,242,0.24);}
*{margin:0;padding:0;box-sizing:border-box;}
body{background:#000;}
.card{width:1200px;height:675px;background:
linear-gradient(160deg,var(--ink) 0%,var(--ink2) 70%,#101a17 100%);
font-family:'Segoe UI',system-ui,sans-serif;color:var(--cream);
padding:26px 40px 20px;display:flex;flex-direction:column;}
.hdr{display:flex;justify-content:space-between;align-items:baseline;}
.brand{display:inline-flex;align-items:center;gap:8px;font-family:"IBM Plex Mono",ui-monospace,Consolas,monospace;text-transform:uppercase;font-weight:800;font-size:24px;letter-spacing:.5px;color:var(--cream);}.brand b{font-weight:800;letter-spacing:.5px;}.brand i{font-style:normal;color:var(--amber);}
.title{font-size:21px;font-weight:600;}
.sub{color:var(--muted);font-size:14px;margin-top:3px;text-align:right;}
.body{display:flex;gap:26px;margin-top:14px;flex:1;min-height:0;}
.left{width:470px;display:flex;flex-direction:column;}
.right{flex:1;display:flex;flex-direction:column;min-width:0;}
.lbl{font-size:12px;letter-spacing:.12em;color:var(--amber);
text-transform:uppercase;font-weight:700;margin-bottom:6px;}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;}
td{padding:3px 4px;font-size:15px;line-height:20px;white-space:nowrap;
border-bottom:1px solid rgba(243,242,242,0.08);}
td.rk{color:var(--muted);width:26px;text-align:right;padding-right:8px;}
td.nm{font-weight:600;max-width:190px;overflow:hidden;text-overflow:ellipsis;}
td.tm{color:var(--muted);width:92px;}
td.ps{color:var(--muted);width:44px;}
td.xp{color:var(--amber);font-weight:700;text-align:right;width:52px;font-size:16px;}
.pitch{background:rgba(46,214,194,0.13);border:1px solid var(--line);
padding:4px 2px;flex:1;display:flex;flex-direction:column;
justify-content:space-evenly;min-height:0;}
.xirow{display:flex;justify-content:space-evenly;}
.xip{width:118px;text-align:center;position:relative;}
.xip b{display:block;font-size:14px;font-weight:600;margin-top:1px;
white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.xip span{display:block;font-size:12px;color:var(--muted);
font-variant-numeric:tabular-nums;white-space:nowrap;}
.xip span i{font-style:normal;color:var(--amber);font-weight:700;}
.badge{position:absolute;top:-3px;right:20px;background:var(--amber);
color:var(--ink);font-size:12px;font-weight:700;width:20px;height:20px;
border-radius:50%;line-height:20px;}
.badge.v{background:var(--cream);}
.bench{display:flex;align-items:center;gap:10px;border-top:1px solid var(--line);
padding-top:6px;margin-top:8px;}
.bench .blbl{color:var(--muted);font-size:13px;width:52px;}
.bench .xip{width:104px;}
.bench .xip b{font-size:13px;}
.lblrow{display:flex;justify-content:space-between;align-items:baseline;}
.tot{color:var(--muted);font-size:13px;white-space:nowrap;margin-bottom:6px;}
.tot b{color:var(--amber);font-size:17px;font-variant-numeric:tabular-nums;}
.fn{color:var(--muted);font-size:12px;margin-top:6px;}
.ftr{display:flex;justify-content:space-between;color:var(--muted);
font-size:13px;border-top:1px solid var(--line);padding-top:8px;margin-top:8px;}
.ftr b{color:var(--cream);}
svg.kit{display:block;margin:0 auto;}
"""


# ---------------------------------------------------------------------------
# Puhtaat valintafunktiot (testattavat)
# ---------------------------------------------------------------------------




def top_projected(players: list[dict], gw: int, n: int = TOP_N,
                  blocklist: list[dict] | None = None) -> list[dict]:
    """Kortin GW-xP top n. Toteutus on `src.models.fpl_gw_xp.top_projected`.

    30.8 (Villen paatos): seurakatto. Ilman sita lista oli GW3:lle 8x Man City
    + 3x Hull viidestatoista, eli 11/15 kahdesta ottelusta. Se ei ole vaara
    mallilta - molemmat kohtaavat nousijan - mutta **FPL sallii korkeintaan
    kolme pelaajaa per seura**, joten viisi rivia viidestatoista oli
    saantojen takia pelikelvottomia.

    Funktio jaettiin 30.8 ilmaissivun kanssa (FREE-GW-XP): kortin alapalkin
    tarkistusreitti osoittaa nyt taulukkoon joka on laskettu TASTA samasta
    funktiosta, joten kortti ja sivu eivat voi ajautua eri listaan.
    """
    return _top_projected(players, gw, n, blocklist)


def _xi_pool(players: list[dict], gw: int,
             blocklist: list[dict] | None = None) -> list[dict]:
    """Optimoijan pooli, jossa pelaajan arvo on TAMAN kierroksen xP.
    Sama rivimuoto kuin fpl_rate_team._projection_pool, mutta ilman
    bootstrapia: hinta ja seura ovat artefaktissa."""
    out = []
    for p in eligible(players, gw, blocklist):
        et = POS_TYPE.get(p.get("pos"))
        if et is None or p.get("price") is None or p.get("id") is None:
            continue
        x = gw_xp(p, gw)
        out.append({
            "id": int(p["id"]), "web_name": p.get("web_name"),
            "team_short": p.get("team_short") or "",
            "element_type": et,
            "club": p.get("team") or p.get("team_short"),
            "price": int(round(float(p["price"]) * 10)),
            "owned_pct": float(p.get("owned_pct") or 0.0),
            "xp_per_gw": x, "xp_horizon_total": x,
            "gameweeks": p.get("gameweeks") or [],
            "xmins": p.get("xmins"),
            "p_start": p.get("p_start"),
            "gw_xp": x,
        })
    return out


def free_hit_xi(players: list[dict], gw: int, cache_key: str,
                blocklist: list[dict] | None = None) -> dict:
    """Yhden kierroksen paras 15 free_optimum():lla (sama optimoija kuin
    mallin oma rivi). Palauttaa xi (positiojarjestys, rivin sisalla xP
    laskevasti), bench (GK ensin, sitten xP laskevasti), captain, vice,
    formation, xi_xp (kapteeni tuplana)."""
    from src.models.fpl_rate_team import free_optimum
    pool = _xi_pool(players, gw, blocklist)
    res = free_optimum(pool, cache_key)
    xi = list(res.get("xi") or [])
    bench = list(res.get("bench") or [])
    if len(xi) != 11 or len(bench) != 4:
        raise RuntimeError(f"free-hit squad incomplete: XI {len(xi)}, bench {len(bench)}")
    for p in xi + bench:
        p["gw_xp"] = gw_xp(p, gw)
        p["pos"] = TYPE_POS[p["element_type"]]
    xi.sort(key=lambda p: (p["element_type"], -p["gw_xp"], p["id"]))
    gks = [p for p in bench if p["element_type"] == 1]
    outfield = sorted([p for p in bench if p["element_type"] != 1],
                      key=lambda p: (-p["gw_xp"], p["id"]))
    bench = gks + outfield
    ranked = sorted(xi, key=lambda p: (-p["gw_xp"], p["id"]))
    captain, vice = ranked[0], ranked[1]
    counts = {t: sum(1 for p in xi if p["element_type"] == t) for t in (2, 3, 4)}
    formation = f"{counts[2]}-{counts[3]}-{counts[4]}"
    return {"xi": xi, "bench": bench, "captain": captain, "vice": vice,
            "formation": formation,
            # 30.8 (portti B5): summa lasketaan NAYTETYISTA luvuista.
            # Aiemmin se laskettiin pyoristamattomista (53.90 + 6.15 = 60.05
            # -> "60.0"), kun taas kortin omat 1 desimaalin luvut summautuvat
            # 60.3:een. Lukija jolla on laskin nakee ristiriidan kortin
            # sisalla, ja se on tasan se yleiso jolle kortti tehdaan.
            "xi_xp": round(sum(round(p["gw_xp"], 1) for p in xi)
                           + round(captain["gw_xp"], 1), 1)}


# ---------------------------------------------------------------------------
# Loki
# ---------------------------------------------------------------------------

def xi_call(sq: dict) -> dict:
    return build_projected_xi_call(sq["xi"], sq["bench"], sq["captain"],
                                   sq.get("vice"), sq["formation"])


def reconcile_with_log(sq: dict, gw: int, log: dict | None, now) -> dict:
    """Ennen deadlinea kortti ei saa erota lokista: jos lokissa on
    projected_xi-kutsu talle GW:lle ja sen XI/kapteeni eroaa, kaadu ja
    pyyda kirjaamaan loki ensin (sama saanto kuin standouts). Deadlinen
    jalkeen lokin kutsu voittaa: kortti renderoi kirjatun XI:n."""
    row = next((r for r in (log or {}).get("gameweeks") or []
                if int(r.get("gw", -1)) == int(gw)), None)
    if row is None:
        return sq
    call = next((c for c in row.get("calls") or []
                 if c.get("call") == PROJECTED_XI_CALL), None)
    if call is None:
        return sq
    mine = xi_call(sq)
    same = (sorted(int(r["player_id"]) for r in mine["xi"])
            == sorted(int(r["player_id"]) for r in call.get("xi") or [])
            and int(mine["captain"]["player_id"]) == int((call.get("captain") or {}).get("player_id", -1)))
    if same:
        return sq
    if now is None:
        now = _dt.datetime.now(_dt.timezone.utc)
    if now < parse_utc(row["deadline_utc"]):
        raise RuntimeError(
            f"GW{gw} projected XI differs from data/gw_calls.json (logged "
            f"{row.get('logged_at')}); rerun with the log written first so "
            "the card and the log show the same XI.")
    def _row(r):
        return {"id": r["player_id"], "web_name": r.get("web_name"),
                "team_short": r.get("team_short"), "pos": r.get("pos"),
                "element_type": POS_TYPE.get(r.get("pos"), 0),
                "gw_xp": float(r.get("gw_xp") or 0.0)}
    xi = [_row(r) for r in call.get("xi") or []]
    bench = [_row(r) for r in call.get("bench") or []]
    cap = _row(call["captain"])
    vice = _row(call["vice_captain"]) if call.get("vice_captain") else None
    return {"xi": xi, "bench": bench, "captain": cap, "vice": vice,
            "formation": call.get("formation") or sq.get("formation"),
            "xi_xp": float(call.get("value") or 0.0)}


# ---------------------------------------------------------------------------
# Renderointi
# ---------------------------------------------------------------------------

def _fmt_utc(s: str | None, with_day: bool = False) -> str:
    if not s:
        return ""
    return _stamp(parse_utc(s), with_day)


def _stamp(t: _dt.datetime, with_day: bool = False) -> str:
    """'Fri 4 Sep 17:30 UTC' / '29 Aug 07:05 UTC': paivan etunolla pois,
    tunnin etunolla jaa (7:05 lukisi 12 h -kellolta)."""
    t = t.astimezone(_dt.timezone.utc)
    day = f"{t.strftime('%a')} {t.day}" if with_day else str(t.day)
    return f"{day} {t.strftime('%b %H:%M')} UTC"


def _promoted(p: dict) -> bool:
    return (p.get("team_flag") or "") == "promoted"


def _cell(p: dict, cap_id: int, vice_id: int, size: int = 46) -> str:
    badge = ""
    if int(p["id"]) == cap_id:
        badge = '<span class="badge">C</span>'
    elif int(p["id"]) == vice_id:
        badge = '<span class="badge v">V</span>'
    return ('<div class="xip">' + badge + _kit_svg(p["team_short"], size=size)
            + f'<b>{escape(str(p["web_name"]))}</b>'
            + f'<span>{escape(str(p["team_short"]))} · <i>{float(p["gw_xp"]):.1f}</i></span></div>')


def build_html(data: dict, log: dict | None = None, now=None,
               blocklist: list[dict] | None = None) -> tuple[str, dict]:
    players = data.get("players") or []
    meta = data.get("meta") or {}
    gw = int(actionable_gameweek(meta) or 0)
    if now is None:
        now = _dt.datetime.now(_dt.timezone.utc)
    top = top_projected(players, gw, TOP_N, blocklist)
    sq = free_hit_xi(players, gw, f"projected-xi-gw{gw}-{meta.get('generated_at')}",
                     blocklist)
    sq = reconcile_with_log(sq, gw, log, now)
    cap_id, vice_id = int(sq["captain"]["id"]), int(sq["vice"]["id"]) if sq.get("vice") else -1

    rows = "".join(
        "<tr>"
        f'<td class="rk">{i}</td>'
        f'<td class="nm">{escape(str(p["web_name"]))}</td>'
        f'<td class="tm">{escape(str(p["team_short"]))}{"*" if _promoted(p) else ""}'
        f' {escape(_opp_text(p, gw))}</td>'
        f'<td class="ps">{escape(str(p["pos"]))}</td>'
        f'<td class="xp">{gw_xp(p, gw):.1f}</td>'
        "</tr>"
        for i, p in enumerate(top, 1))
    by_type = {t: [p for p in sq["xi"] if p["element_type"] == t] for t in (1, 2, 3, 4)}
    pitch = "".join('<div class="xirow">' + "".join(_cell(p, cap_id, vice_id) for p in by_type[t])
                    + "</div>" for t in (1, 2, 3, 4))
    bench_html = "".join(_cell(p, -1, -1, size=36) for p in sq["bench"])
    shorts = [p["team_short"] for p in sq["xi"] + sq["bench"]]
    promoted_on_card = any(_promoted(p) for p in top)
    from scripts.gen_share_card import promoted_footnote
    # 30.8 (portti): luku oli kovakoodattu "one PL match". own_matches on 1
    # tanaan ja 2 kun GW2 gradataan ma 31.8 - eli VAARIN silla hetkella kun
    # kortti julkaistaan 4.9. Sama kovakoodaus shippasi jo 25.8 ja korjattiin
    # gen_share_cardiin; tama generaattori ei kutsunut korjausta.
    footnote = (f'<div class="fn">{escape(promoted_footnote())}'
                '<br>Max 3 per club</div>'
                if promoted_on_card else "")
    deadline = _fmt_utc(meta.get("deadline_utc"), with_day=True)
    proj_at = _fmt_utc(meta.get("generated_at"))
    card_at = _stamp(now)

    html = (
        "<!doctype html><meta charset='utf-8'>"
        f"<style>{CSS}</style>"
        f'<svg width="0" height="0" style="position:absolute">{_kit_defs(shorts)}</svg>'
        '<div class="card">'
        '<div class="hdr"><div><span class="brand">'
        # 30.8 (Villen huomio: vaara variteema): merkki tulee
        # `src/brand.py`:sta, joka on Villen 1.8 paatos "logo on
        # kaikilla sivuilla sama". Kortti renderoi aiemmin pelkkaa
        # turkoosia tekstia ilman amber-laatikkoa, eli KOLMANNEN
        # merkkiversion - tasan sen jonka 1.8 paatos poisti.
        + logo_svg(28) + '<b>Goal<i>IQ</i></b></span></div>'
        f'<div><div class="title">GW{gw} projected points and the model&#39;s free-hit XI</div>'
        f'<div class="sub">GW{gw} deadline {deadline} · GoalIQ model, projection run {proj_at}</div></div></div>'
        '<div class="body">'
        f'<div class="left"><div class="lbl">Projected points, best {len(top)} '
        f'at most three per club</div>'
        f'<table><tbody>{rows}</tbody></table>{footnote}</div>'
        f'<div class="right"><div class="lblrow"><div class="lbl">Free-hit XI for GW{gw} only ({sq["formation"]})</div>'
        f'<div class="tot"><b>{sq["xi_xp"]:.1f}</b> projected, captain doubled</div></div>'
        f'<div class="pitch">{pitch}</div>'
        f'<div class="bench"><span class="blbl">Bench</span>{bench_html}</div>'
        # 1.9 (QUEUE: KORTTI-BEST15-KAKSIMERKITYS). Ennen: alaviite sanoi
        # "Best 15 for this gameweek alone under the same squad rules" -
        # mutta "Best 15" ON vasemman paneelin top-lista (TOP_N = 15), ei
        # tama oikea paneeli (XI + halvin penkki). Alaviite kuvasi siis
        # VIERESSA olevaa paneelia, ei omaansa. Portin suositus 30.8.
        '<div class="fn">Best XI inside the 100.0m budget. The bench is the '
        'cheapest cover that still projects minutes, so the money goes into '
        'the XI. C = captain, V = vice.</div>'
        '</div></div>'
        # 1.9 (QUEUE: KORTTI-ENTRY-EROTUS). Ennen: "The model plays too:
        # entry 116920" nimesi entry 116920:n TASAN talla kortilla jonka
        # oikea puoli on free-hit-XI jota malli EI pelaa (wildcard kaytettiin
        # GW2:ssa) - lukija joka avaa entryn deadlinen jalkeen nakee eri
        # joukkueen. Portin suositus 30.8: sano eksplisiittisesti etta tama
        # EI ole mallin oma joukkue.
        '<div class="ftr"><span>Not the model&#39;s own team. That one is '
        'public: <b>entry 116920</b>, scored every gameweek</span>'
        f'<span>model projections, not betting advice · card made {card_at}</span>'
        # 🔴 TARKISTUSREITTI, EI KOTISIVUOSOITE (KORTTI-TARKISTUSREITTI 30.8).
        # Alapalkki osoitti `/fpl/expected-points`-sivun JUUREEN, joka rankkaa
        # kuuden kierroksen yhteissummalla: Haaland oli kortilla 6.2 ja
        # sivulla 35.6, ja jarjestys oli eri. Lukija joka kavelee reitin
        # loytaa toiset luvut kuin ne joita han tuli tarkistamaan, eli reitti
        # oli pahempi kuin ei reittia. `#gw-xp` on sama lista samasta
        # funktiosta (src.models.fpl_gw_xp.top_projected).
        '<span>projected points list: goaliq.app/fpl/expected-points#gw-xp</span></div>'
        "</div>")
    payload = {"gw": gw, "deadline_utc": meta.get("deadline_utc"),
               "top": top, "squad": sq, "call": xi_call(sq)}
    return html, payload


def _visible_text(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def gate(html: str, blocklist: list[dict] | None = None) -> None:
    """Kaadu jos kortilla on estolistan nimi tai kielletty copy-sana.
    Ajetaan valmiille tekstille: eri koodipolku kuin _excluded, jotta
    suodattimen reika ei paase lapi hiljaa."""
    text = _visible_text(html)
    hits = blocked_names(text, blocklist if blocklist is not None else load_blocklist())
    if hits:
        raise RuntimeError("publish gate: blocked name on card: "
                           + ", ".join(h["name"] for h in hits))
    bad = [w for w in BANNED_COPY if re.search(w, text)]
    if bad:
        raise RuntimeError(f"publish gate: banned copy on card: {bad}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load_log() -> dict:
    if CALLS_LOG_PATH.exists():
        return json.loads(CALLS_LOG_PATH.read_text(encoding="utf-8"))
    return json.loads(json.dumps(NEW_LOG))


def write_call(log: dict, payload: dict, meta: dict, now) -> dict:
    """upsert_call fail-closed: deadlinen jalkeen nostaa DeadlinePassed."""
    return upsert_call(log, payload["gw"], payload["deadline_utc"], payload["call"],
                       now, source={"projection_generated_at": meta.get("generated_at")})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(config.PROJECT_ROOT / "outputs" / "cards"))
    ap.add_argument("--dry-run", action="store_true",
                    help="renderoi kortti, ala kirjoita data/gw_calls.json:iin")
    args = ap.parse_args(argv)
    data = json.loads(XP_PATH.read_text(encoding="utf-8"))
    meta = data.get("meta") or {}
    blocklist = load_blocklist()
    log = _load_log()
    now = _dt.datetime.now(_dt.timezone.utc)
    html, payload = build_html(data, log=log, now=now, blocklist=blocklist)
    gate(html, blocklist)
    gw = payload["gw"]
    sq = payload["squad"]
    print(f"GW{gw} top {len(payload['top'])}:")
    for i, p in enumerate(payload["top"], 1):
        print(f"  {i:2d} {p['web_name']:16s} {p['team_short']:4s} {p['pos']:4s} {gw_xp(p, gw):.1f}")
    print(f"XI ({sq['formation']}), captain {sq['captain']['web_name']}, "
          f"{sq['xi_xp']:.1f} projected:")
    for p in sq["xi"]:
        print(f"  {p['pos']} {p['web_name']:16s} {p['team_short']:4s} {p['gw_xp']:.1f}")
    print("  bench: " + ", ".join(f"{p['web_name']} {p['gw_xp']:.1f}" for p in sq["bench"]))

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"goaliq_projected_xi_gw{gw}.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"HTML: {html_path}")
    candidates = [shutil.which(n) for n in ("chrome", "google-chrome", "chromium", "msedge")]
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env)
        if base:
            candidates.append(str(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"))
    for exe in candidates:
        if exe and Path(exe).exists():
            png = out_dir / f"goaliq_projected_xi_gw{gw}.png"
            subprocess.run([exe, "--headless=new", f"--screenshot={png}",
                            "--window-size=1200,675", "--hide-scrollbars",
                            html_path.as_uri()],
                           check=True, capture_output=True, timeout=60)
            print(f"PNG: {png}")
            break
    else:
        print("Chromea ei loytynyt - kaappaa HTML kasin.")

    if args.dry_run:
        print("dry-run: gw_calls.json ei kirjoitettu.")
        return 0
    try:
        write_call(log, payload, meta, now)
    except DeadlinePassed as e:
        print(f"VIRHE: {e}")
        return 1
    CALLS_LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n",
                              encoding="utf-8")
    print(f"OK: GW{gw} projected_xi kirjattu -> {CALLS_LOG_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
