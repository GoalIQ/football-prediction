"""STANDOUTS-CARD (27.8.2026): kierroskohtainen "standouts"-jakokortti.

MIKSI: kilpailijat (NextXI, Vollo) saavat ~25 k nayttoa per kierros
vakiomuodolla: 4-5 korttia (kapteeni, korkein katto, turvallisin, uhkapeli)
+ tuotekuva, joka kierros sama. Meilta puuttui toistuva muoto.

LAHDE: data/fpl_xp_projections.json, VAIN XP-DISTRIBUTION-kentat (xp_dist)
+ headline-GW:n xp (gameweeks[].xp). Ei keksittyja lukuja. Kortti EI nayta
per-pelaaja-xP:ta (lukija tarkistaa prosentit ilmaissivulta
/fpl/expected-points, jolla on samat sarakkeet); erottaja alatunnisteessa:
mallin oma entry liigassa + joka kierros julkisesti pisteytetty.
JULKAISUPORTTI 27.8: kapteeni valitaan GW-xP:lla (ei 6 GW:n keskiarvolla,
sama metriikka kuin kapteenirankerissa), "past p90 in fewer than 1 week in
10" (kokonaisluvut + typistys: P(X >= p90) voi olla 20 %), ei "floor"-sanaa,
Thiaw-esto _pool():ssa, linkki sivulle jolla luvut nakyvat.

Valinnat (kaikki headline-GW:sta, vain pelaajat joilla p_start >= 0.6 ja
status a, jotta kortti ei nosta penkkilaista):
  CAPTAIN PICK   suurin GW-xP (gameweeks[].xp headline-GW:lle)
  CEILING        suurin p90 (tasapeli: p_haul) - ei "highest", koska p90 on
                 kokonaisluku ja sama katto voi olla usealla (27.8: 10 kolmella)
  SAFEST PICK    pienin p_blank niista joiden GW-xP >= 4
  THE GAMBLE     suurin p_haul niista joiden p_blank >= 0.35
  Nelja eri nimea (poissulku jarjestyksessa). Nousija (team_flag promoted)
  saa tahden + alaviitteen kuten 25.8 GW2-outlook-kortti.

Tuloste: HTML + PNG (Chrome headless) kuten render_frozen_squad_card.
    python -m scripts.render_standouts_card --out outputs/cards
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from html import escape

from src.brand import logo_svg
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from src.models.fpl_gameweek import actionable_gameweek  # portti: ei next_gameweek suoraan

XP_PATH = config.DATA_DIR / "fpl_xp_projections.json"
# GW-CALLS-LOKI (28.8): kortin nelja nimea kirjataan data/gw_calls.json:iin
# ennen deadlinea (scripts/log_gw_calls.py). Kortti ei saa erota lokista:
# ennen deadlinea eroava kortti = loki on vanha -> kaadu ja pyyda ajamaan
# log_gw_calls; deadlinen jalkeen loki on lukossa -> kortti renderoi LOKIN
# nimet ja luvut, ei tuoretta projektiota (postaus deadlinen jalkeen ei saa
# nayttaa kutsua jota ei kirjattu).
CALLS_LOG_PATH = config.DATA_DIR / "gw_calls.json"
LOG_KEYS = (("captain", "captain_pick"), ("ceiling", "ceiling"),
            ("safest", "safest"), ("gamble", "gamble"))
MIN_P_START = 0.6
# Kova saanto: ei Thiaw-juttuja markkinointiin (muisti thiaw-ei-markkinointiin).
# Esto kuuluu generaattoriin, koska yksi refresh riittaa nostamaan hanet
# "safest"-tiileen (nailed DEF, korkea CS%).
EXCLUDED_NAMES = {"thiaw"}


def _excluded(name: str) -> bool:
    """Vertailu sukunimiosalla ja pienin kirjaimin: 'M.Thiaw' ja 'Thiaw' ovat
    sama pelaaja, eika esto saa lakata jos FPL lisaa etukirjaimen."""
    tail = str(name or "").split(".")[-1].strip().lower()
    return tail in EXCLUDED_NAMES
SAFE_MIN_XP = 4.0
GAMBLE_MIN_BLANK = 0.35

CSS = """
:root{--amber:#F5C542;--ink:#0B0A09;--ink2:#141311;
--cream:#F3F2F2;--muted:#A8A29A;--line:rgba(243,242,242,0.24);}
*{margin:0;padding:0;box-sizing:border-box;}
body{background:#000;}
.card{width:1200px;height:675px;background:
linear-gradient(160deg,var(--ink) 0%,var(--ink2) 70%,#101a17 100%);
font-family:'Segoe UI',system-ui,sans-serif;color:var(--cream);
padding:34px 44px 26px;display:flex;flex-direction:column;}
.hdr{display:flex;justify-content:space-between;align-items:baseline;}
.brand{display:inline-flex;align-items:center;gap:8px;font-family:"IBM Plex Mono",ui-monospace,Consolas,monospace;text-transform:uppercase;font-weight:800;font-size:24px;letter-spacing:.5px;color:var(--cream);}.brand b{font-weight:800;letter-spacing:.5px;}.brand i{font-style:normal;color:var(--amber);}
.title{font-size:22px;font-weight:600;}
.sub{color:var(--muted);font-size:15px;margin-top:4px;text-align:right;}
.tiles{display:flex;gap:18px;margin:26px 0 18px;flex:1;}
.tile{flex:1;border:1px solid var(--line);background:rgba(46,214,194,0.07);
padding:18px 18px 14px;display:flex;flex-direction:column;}
.tile .lbl{font-size:13px;letter-spacing:.12em;color:var(--amber);
text-transform:uppercase;font-weight:700;}
.tile .name{font-size:30px;font-weight:700;margin-top:10px;white-space:nowrap;
overflow:hidden;text-overflow:ellipsis;}
.tile .meta{color:var(--muted);font-size:15px;margin-top:2px;}
.tile .range{color:var(--muted);font-size:15px;margin-top:26px;}
.tile .range b{color:var(--cream);font-weight:600;}
.tile .big{font-size:54px;font-weight:700;color:var(--amber);margin-top:auto;
line-height:1;font-variant-numeric:tabular-nums;}
.tile .big small{font-size:18px;white-space:nowrap;color:var(--muted);font-weight:500;margin-left:6px;}
/* Kiintea korkeus, ei min-height: why-teksti on nyt johdettu ja sen pituus vaihtelee tiilittain (rajaus + tasapeli). Vaihteleva korkeus siirtaa .big-lukua (margin-top:auto), jolloin nelja isoa lukua eivat ole samalla viivalla. */
.tile .why{color:var(--muted);font-size:14px;margin-top:8px;height:54px;}
.fn{color:var(--muted);font-size:13px;margin:-8px 0 8px;}
.ftr{display:flex;justify-content:space-between;color:var(--muted);
font-size:14px;border-top:1px solid var(--line);padding-top:10px;}
.ftr b{color:var(--cream);}
"""


def _pool(players: list[dict]) -> list[dict]:
    return [p for p in players
            if p.get("xp_dist") and p.get("status", "a") == "a"
            and float(p.get("p_start") or 0) >= MIN_P_START
            and not _excluded(p.get("web_name"))
            and gw_xp(p) is not None]


def gw_xp(p: dict):
    """Headline-GW:n xP riville (gameweeks[].xp), EI xp_per_gw (6 GW:n keskiarvo)."""
    gw = (p.get("xp_dist") or {}).get("gw")
    for g in p.get("gameweeks") or []:
        if g.get("gw") == gw:
            return float(g.get("xp") or 0.0)
    return None


def assert_dist_gameweek(players: list[dict], gw: int) -> None:
    """Kaadu jos `xp_dist` on eri kierrokselta kuin kortin otsikko.

    🔴 30.8 (julkaisutarkistaja): kortin otsikko kayttaa `actionable_gameweek`ia
    mutta JOKAINEN luku tulee `xp_dist`:sta, joka lasketaan `next_gameweek`ille.
    Mitattu: otsikko sanoi GW3 ja luvut olivat GW2:n (captain Haaland 5.77, kun
    GW3:n luku on 6.2; gamble B.Fernandes, joka ei ole GW3:n karjessa lainkaan).
    Kortti olisi julkaissut vaaran kierroksen luvut oikean kierroksen nimella.

    🔴 Tarkistus on TASSA eika `build_html`:ssa, koska `pick_standouts`illa on
    KAKSI kuluttajaa: kortti ja `scripts/log_gw_calls.py`, joka ajetaan CI:ssa
    ja nimeaa rivin samalla `actionable_gameweek`illa. Vain kortin suojaaminen
    olisi jattanyt lokipolun auki; se on tanaan turvassa vain siksi etta GW3:n
    freezea ei viela ole, eli sattumalta (muisti:
    yksi-renderointipolku-kahdesta).

    Korjaus on ylavirrassa (`build_fpl_xp.py`: `xp_dist` lasketaan `next_gw`:lle,
    QUEUE: XP-DIST-KIERROS). Siihen asti fail-closed.
    """
    dist_gws = {(p.get("xp_dist") or {}).get("gw") for p in players
                if p.get("xp_dist")}
    dist_gws.discard(None)
    if dist_gws and dist_gws != {gw}:
        raise SystemExit(
            f"STANDOUTS-KIERROSRISTIRIITA: valinta nimetaan kierrokselle GW{gw} "
            f"(actionable_gameweek) mutta xp_dist on kierrokselta "
            f"{sorted(dist_gws)}. Luvut olisivat vaaralta kierrokselta oikean "
            f"kierroksen nimella. Korjaa xp_dist:n kierros "
            f"(QUEUE: XP-DIST-KIERROS) ennen julkaisua.")


def pick_standouts(players: list[dict]) -> dict:
    """Puhdas valintafunktio (testattava). Palauttaa avaimet
    captain/ceiling/safest/gamble -> pelaajarivi tai None."""
    pool = _pool(players)
    if not pool:
        return {"captain": None, "ceiling": None, "safest": None, "gamble": None}
    d = lambda p: p["xp_dist"]
    # Nelja ERI nimea: sama pelaaja ei ole seka katto etta uhkapeli (Isak oli
    # molemmat 27.8 ensimmaisella ajolla). Valinta jarjestyksessa, poissulku.
    taken: list = []
    def rest():
        return [p for p in pool if p["id"] not in taken] if all("id" in p for p in pool)             else [p for p in pool if p["web_name"] not in taken]
    def key(p):
        return p.get("id", p["web_name"])
    captain = max(pool, key=lambda p: (gw_xp(p), d(p)["p_haul"]))
    taken.append(key(captain))
    ceiling = max(rest(), key=lambda p: (d(p)["p90"], d(p)["p_haul"])) if rest() else None
    if ceiling: taken.append(key(ceiling))
    safe_pool = [p for p in rest() if gw_xp(p) >= SAFE_MIN_XP]
    safest = (min(safe_pool, key=lambda p: (d(p)["p_blank"], -gw_xp(p)))
              if safe_pool else None)
    if safest: taken.append(key(safest))
    gamble_pool = [p for p in rest() if d(p)["p_blank"] >= GAMBLE_MIN_BLANK]
    gamble = (max(gamble_pool, key=lambda p: (d(p)["p_haul"], -d(p)["p_blank"]))
              if gamble_pool else None)
    return {"captain": captain, "ceiling": ceiling, "safest": safest,
            "gamble": gamble}


def _key(p: dict):
    return p.get("id", p.get("web_name"))


def claim_scope(pool: list[dict], pick: dict | None, val,
                higher_is_better: bool, earlier: dict) -> dict:
    """YKSI LUKIJA tiilien superlatiiveille (saanto 6a kohta 1).

    🔴 SAMA VIKA KAHDESTI SAMALLA KORTILLA (4.9.2026, julkaisuportti k1 ja k2).
    Jokainen tiili valitaan `rest()`-joukosta josta aiemmat tiilet on jo
    pudotettu, mutta why-teksti oli kovakoodattua proosaa joka vaitti
    superlatiivia KOKO poolista:

      k1  Ceiling sanoi "top ceiling in the pool", kun kapteeni Haalandin
          katto (14) oli korkeampi kuin Isakin (11) - viereisessa tiilessa.
      k2  Sama korjaus jatti Safest-tiilen koskematta: Anderson (blank 17 %)
          nimettiin "safest", vaikka Haaland (5 %) ja Isak (15 %) ovat samalla
          kortilla. Ja ceiling-korjaus itse ohitti TASAPELIN: p90 on
          kokonaisluku, ja GW3:ssa kolme pelaajaa oli 11:ssa (Guehi, Foden,
          Isak), joten "top" ei ollut yksikasitteinen edes rajattuna.

    Siksi why-tekstia ei enaa kirjoiteta tiilikohtaisesti. Tama funktio lukee
    kaikki kolme asiaa samasta datasta:
      ahead   ketka poolissa ovat pickia paremmat (nama on nimettava)
      tied    ketka ovat tasan yhta hyvat ("joint", ei "top")
      on_card kuuluvatko kaikki paremmat aiempiin tiiliin
    Jos joku parempi EI ole kortilla, superlatiivia ei sanota lainkaan
    (fail-closed): silloin vaitteelle ei ole naytettavaa perustelua.

    `earlier` on {label: pelaaja}, esim. {"captain": ..., "ceiling": ...}.
    """
    if pick is None:
        return {"ahead": [], "tied": [], "on_card": True, "labels": []}
    v = val(pick)
    others = [p for p in pool if _key(p) != _key(pick)]
    ahead = [p for p in others
             if (val(p) > v if higher_is_better else val(p) < v)]
    tied = [p for p in others if val(p) == v]
    labels = {_key(p): lbl for lbl, p in earlier.items() if p}
    return {"ahead": ahead, "tied": tied,
            "on_card": all(_key(p) in labels for p in ahead),
            "labels": [labels[_key(p)] for p in ahead if _key(p) in labels]}


def scope_phrase(superlative: str, sc: dict) -> str:
    """Superlatiivi siina laajuudessa kuin se on tosi, tai tyhja."""
    if sc["ahead"] and not sc["on_card"]:
        return ""
    head = f"joint {superlative}" if sc["tied"] else superlative
    if not sc["ahead"]:
        return f"{head} in the pool"
    which = " and ".join(f"our {lbl} pick" for lbl in sc["labels"])
    return f"{head} after {which}"


def _promoted(p: dict) -> bool:
    return (p.get("team_flag") or "") == "promoted"


def _tile(lbl: str, p: dict | None, big: str, small: str, why: str) -> str:
    if p is None:
        return (f'<div class="tile"><div class="lbl">{escape(lbl)}</div>'
                '<div class="name">-</div><div class="meta">no pick this week</div>'
                '<div class="big">-</div></div>')
    star = "*" if _promoted(p) else ""
    return (f'<div class="tile"><div class="lbl">{escape(lbl)}</div>'
            f'<div class="name">{escape(p["web_name"])}</div>'
            f'<div class="meta">{escape(p["pos"])} · {escape(p["team_short"])}{star}'
            f' · {float(p.get("price") or 0):.1f}m</div>'
            # "8 weeks in 10 between a and b": vali p10..p90 kattaa rakenteellisesti
            # >= 80 % (typistys nostaa). EI "range"/"floor": havaittu vaihteluvali
            # oli 0-31 (mitattu n=200 000), joten sisaltavyytta ei luvata.
            f'<div class="range">8 weeks in 10 between <b>{p["xp_dist"]["p10"]}</b> '
            f'and <b>{p["xp_dist"]["p90"]}</b></div>'
            f'<div class="big">{escape(big)}<small>{escape(small)}</small></div>'
            f'<div class="why">{escape(why)}</div></div>')


def _same_player(card_p: dict | None, call: dict | None) -> bool:
    if card_p is None or call is None:
        return card_p is None and call is None
    if card_p.get("id") is not None and call.get("player_id") is not None:
        return int(card_p["id"]) == int(call["player_id"])
    return str(card_p.get("web_name")) == str(call.get("web_name"))


def reconcile_with_log(s: dict, gw: int, log: dict | None, now,
                       players: list[dict]) -> dict:
    """Vertaa kortin valinnat lokiin (data/gw_calls.json). Ei lokirivia ->
    kortti sellaisenaan. Sama -> sellaisenaan. Eroaa: ennen deadlinea
    RuntimeError ("run scripts.log_gw_calls first"), deadlinen jalkeen
    palautetaan lokin nimet ja luvut."""
    import datetime as _dt
    row = next((r for r in (log or {}).get("gameweeks") or []
                if int(r.get("gw", -1)) == int(gw)), None)
    if row is None:
        return s
    calls = {c["call"]: c for c in row.get("calls") or []}
    diffs = [k for k, lk in LOG_KEYS if not _same_player(s.get(k), calls.get(lk))]
    if not diffs:
        return s
    deadline = _dt.datetime.fromisoformat(
        str(row["deadline_utc"]).replace("Z", "+00:00"))
    if now is None:
        now = _dt.datetime.now(_dt.timezone.utc)
    if now < deadline:
        raise RuntimeError(
            f"GW{gw} standouts differ from data/gw_calls.json in {diffs} "
            f"(log written {row.get('logged_at')}); run scripts.log_gw_calls "
            "first so the card and the log say the same names.")
    by_id = {int(p["id"]): p for p in players if p.get("id") is not None}
    by_name = {str(p.get("web_name")): p for p in players}
    out = {}
    for k, lk in LOG_KEYS:
        c = calls.get(lk)
        if c is None:
            out[k] = None
            continue
        base = (by_id.get(int(c["player_id"]))
                if c.get("player_id") is not None else None)
        base = base or by_name.get(str(c.get("web_name"))) or {}
        p = dict(base)
        p.update({"id": c.get("player_id"), "web_name": c.get("web_name"),
                  "team_short": c.get("team_short") or p.get("team_short"),
                  "pos": c.get("pos") or p.get("pos"),
                  "price": p.get("price") or 0.0})
        d = dict(p.get("xp_dist") or {})
        d.update(c.get("xp_dist") or {})
        d["gw"] = gw
        p["xp_dist"] = d
        if c.get("gw_xp") is not None:
            p["gameweeks"] = [{"gw": gw, "xp": c["gw_xp"]}]
        out[k] = p
    return out


def build_html(data: dict, log: dict | None = None, now=None) -> tuple[str, dict]:
    players = data.get("players") or []
    meta = data.get("meta") or {}
    gw = int(actionable_gameweek(meta) or 0)
    assert_dist_gameweek(players, gw)
    s = reconcile_with_log(pick_standouts(players), gw, log, now, players)
    pct = lambda x: f"{round(x * 100)}%"
    # Vertailujoukko on sama kuin valinnassa: koko pooli katolle, ja
    # safestille sama xP-rajattu joukko josta safest valitaan.
    pool = _pool(players)
    safe_pool = [p for p in pool if (gw_xp(p) or 0) >= SAFE_MIN_XP]
    scopes = {
        "ceiling": claim_scope(pool, s["ceiling"],
                               lambda p: p["xp_dist"]["p90"], True,
                               {"captain": s["captain"]}),
        "safest": claim_scope(safe_pool, s["safest"],
                              lambda p: p["xp_dist"]["p_blank"], False,
                              {"captain": s["captain"], "ceiling": s["ceiling"]}),
    }
    tiles = "".join([
        _tile("Captain pick", s["captain"],
              pct(s["captain"]["xp_dist"]["p_haul"]) if s["captain"] else "-",
              "10+ pts",
              (f"top GW{gw} projection in the pool, blanks {pct(s['captain']['xp_dist']['p_blank'])}"
               if s["captain"] else "")),
        # "Ceiling", ei "Highest": p90 on kokonaisluku ja sama katto voi olla
        # usealla (27.8: 10 kolmella, kaikki kortilla). Rajaus ja tasapeli
        # tulevat `claim_scope`ista, ei proosasta (ks. sen docstring).
        _tile("Ceiling", s["ceiling"],
              str(s["ceiling"]["xp_dist"]["p90"]) if s["ceiling"] else "-",
              "pts",
              (", ".join(x for x in [
                  scope_phrase("top ceiling", scopes["ceiling"]),
                  f"10+ in {pct(s['ceiling']['xp_dist']['p_haul'])}"] if x)
               if s["ceiling"] else "")),
        _tile("Safest pick", s["safest"],
              pct(1.0 - s["safest"]["xp_dist"]["p_blank"]) if s["safest"] else "-",
              "3+ pts",
              (", ".join(x for x in [
                  scope_phrase("lowest blank chance", scopes["safest"]),
                  f"median {s['safest']['xp_dist']['median']} pts"] if x)
               if s["safest"] else "")),
        _tile("The gamble", s["gamble"],
              pct(s["gamble"]["xp_dist"]["p_haul"]) if s["gamble"] else "-",
              "10+ pts",
              # Sama pyoristetty haul kuin kapteenilla sanotaan aaneen, ei piiloteta.
              ((f"same haul chance as our captain pick, but blanks "
                f"{pct(s['gamble']['xp_dist']['p_blank'])} of the time")
               if s["gamble"] and s["captain"]
               and pct(s["gamble"]["xp_dist"]["p_haul"]) == pct(s["captain"]["xp_dist"]["p_haul"])
               else (f"but blanks {pct(s['gamble']['xp_dist']['p_blank'])} of the time"
                     if s["gamble"] else ""))),
    ])
    promoted_on_card = any(_promoted(s[k]) for k in s if s[k])
    from scripts.gen_share_card import promoted_footnote
    # 30.8 (portti): sama kovakoodaus kuin projected-XI-kortissa.
    footnote = (f'<div class="fn">{promoted_footnote()}</div>'
                if promoted_on_card else "")
    n = (s["captain"] or {}).get("xp_dist", {}).get("n", 2000) if s["captain"] else 2000
    html = (
        "<!doctype html><meta charset='utf-8'>"
        f"<style>{CSS}</style>"
        '<div class="card">'
        '<div class="hdr"><div><span class="brand">'
        # 30.8 (Villen huomio: vaara variteema): merkki tulee
        # `src/brand.py`:sta, joka on Villen 1.8 paatos "logo on
        # kaikilla sivuilla sama". Kortti renderoi aiemmin pelkkaa
        # turkoosia tekstia ilman amber-laatikkoa, eli KOLMANNEN
        # merkkiversion - tasan sen jonka 1.8 paatos poisti.
        + logo_svg(28) + '<b>Goal<i>IQ</i></b></span></div>'
        f'<div><div class="title">GW{gw} standouts from {n:,} simulated gameweeks</div>'
        '<div class="sub">Same numbers as our xP, run that many times. Only players with '
        'at least a 60% chance of starting.</div></div></div>'
        f'<div class="tiles">{tiles}</div>{footnote}'
        # 🔴 4.9 PORTTI: "every gameweek scored in public" hylattiin 3.9
        # sisarkortista (render_projected_xi_card) EPATOTENA - gw_calls.json
        # sisaltaa vain GW2:n pisteytettyna - mutta hylkays jai siihen yhteen
        # generaattoriin ja eli tassa toisessa 4.9 asti. Korvaus on
        # sisarkortin jo portin lapaissyt sanamuoto.
        '<div class="ftr"><span>The model plays too: <b>entry 116920</b> is '
        'the squad it actually fields</span>'
        '<span>model projections, not betting advice</span>'
        # TARKISTUSREITTI (4.9 portti): paljas URL laskeutuu GW-top-20-tauluun,
        # jossa EI ole Blank- eika 10+-saraketta. Kortin prosentit ovat
        # top-100-taulussa, joten linkki osoittaa sinne.
        '<span>goaliq.app/fpl/expected-points#top-100</span></div>'
        "</div>")
    return html, s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(config.PROJECT_ROOT / "outputs" / "cards"))
    args = ap.parse_args()
    data = json.loads(XP_PATH.read_text(encoding="utf-8"))
    log = (json.loads(CALLS_LOG_PATH.read_text(encoding="utf-8"))
           if CALLS_LOG_PATH.exists() else None)
    html, s = build_html(data, log=log)
    gw = int(actionable_gameweek(data.get("meta") or {}) or 0)
    out_dir = Path(args.out).resolve()  # file-URI vaatii absoluuttisen polun
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"goaliq_standouts_gw{gw}.html"
    html_path.write_text(html, encoding="utf-8")
    for k, p in s.items():
        print(f"  {k:8s} {p['web_name'] if p else '-'} "
              f"{p['xp_dist'] if p else ''}")
    print(f"HTML: {html_path}")
    candidates = [shutil.which(n) for n in
                  ("chrome", "google-chrome", "chromium", "msedge")]
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env)
        if base:
            candidates.append(str(Path(base) / "Google" / "Chrome" / "Application"
                                  / "chrome.exe"))
    for exe in candidates:
        if exe and Path(exe).exists():
            png = out_dir / f"goaliq_standouts_gw{gw}.png"
            subprocess.run([exe, "--headless=new", f"--screenshot={png}",
                            "--window-size=1200,675", "--hide-scrollbars",
                            html_path.as_uri()],
                           check=True, capture_output=True, timeout=60)
            print(f"PNG: {png}")
            break
    else:
        print("Chromea ei loytynyt - kaappaa HTML kasin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
