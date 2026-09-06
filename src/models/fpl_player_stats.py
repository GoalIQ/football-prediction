"""FPL:n omat pisteet ja GoalIQ:n xP samalla rivilla (6.9.2026, Villen tilaus).

MIKSI: Ville halusi "FPL:n omat tilastot omana nakymana niin etta yhdella
sivulla voi verrata expected points (xP) ja pelaajien oikeasti keraamia
pisteita". Tama moduuli on sen nakyman ainoa lukija: /api/fantasy/player-stats
kutsuu `build_response()`, ja SPA + mobiili rakentuvat sen vastauksen paalle.

KOLME LAHDETTA LEVYLLA, EI VERKKOA (Render-konventio, cron paivittaa):
  - `fpl/player-gw.json`        toteuma kierroksittain (FPL element-summary)
  - `data/fpl_player_stats.json` hinta, omistus, status, nimi (FPL bootstrap)
  - `data/fpl_xp_frozen/gwN.json` deadline-freeze, IMMUTABLE vertailukohta
  - `data/fpl_xp_projections.json` elava projektio, VAIN eteenpain (premium)

RAKENTEELLISET PAATOKSET (saanto 6a: yksi lukija joka ei voi palauttaa vaaraa):

1. Aggregaatit lasketaan AINA GW-riveista, myos season-ikkunassa. Jos season
   tulisi stats-tiedoston kausisummasta ja lastN riveista, ikkunan vaihto
   muuttaisi lahdetta eika kukaan huomaisi kun ne eriytyvat (tiedostot
   generoidaan eri ajoissa, mitattu 5.9: stats 18:17, gw 17:09).

2. Kausivartija: stats- ja gw-tiedoston `basis_season` on sama tai vastaus on
   `available:false` syyn kanssa. Kausisekoitus on tunnettu vikaluokka
   (fpl_actuals docstring, stats-build 22.8).

3. Vertailukohta toteumalle on VAIN deadline-freeze. Elava xP liikkuu kohti
   toteumaa kesken kierroksen (fpl_actuals: Gabriel 5.78 -> 5.14), joten
   elavaan lukuun vertaaminen nayttaisi mallin tarkempana kuin se oli.

4. Vertailtava kierros on VALMIS kierros: `compared_gws` rajataan
   `min(finished_events, max_gw)`:hen. Kesken olevalla kierroksella osa
   pelaajista ei ole viela pelannut, ja niiden vertaaminen freezeen
   nayttaisi mallin ylipredikoineen jokaisen sunnuntain pelaajan.

5. Per pelaaja vertailu kattaa vain kierrokset joilla on SEKA freeze-xP ETTA
   toteumarivi. `pts_compared` ja `xp_frozen` ovat samasta kierrosjoukosta,
   muuten erotus valehtelee. Rivin puuttuminen on null, ei nolla: gw-builderi
   pudottaa nollaminuuttiset rivit, mutta taalla ei arvata miksi rivi puuttuu.
   TUNNETTU RAJOITE: penkille jaanyt pelaaja jolla oli freeze-xP ei ole
   vertailussa, joten aggregaatti ei nae ylipredikointia jonka syy on minuutit.
   Se sanotaan aaneen meta.compare_note-kentassa, ei piiloteta.

6. Ilmaista: kaikki FPL:n raakaluvut ja MENNEIDEN kierrosten freeze-vertailu
   (julkinen track record). Premium: `next_gw_xp` ja `xp_horizon_total`
   (eteenpain katsova malli). Villen linjaus 8.8: raakaluvut ilmaiseksi,
   malli maksaa.

`aggregate()` ei lue levya: testit ajavat sen synteettisilla fikstuureilla
joka kauden vaiheessa (esikausi, kesken kierroksen, tuplakierros).
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import threading
from pathlib import Path

import config
from src.models import fpl_actuals
from src.models.fpl_rate_team import RateTeamError

STATS_PATH = config.DATA_DIR / "fpl_player_stats.json"
XP_PATH = config.DATA_DIR / "fpl_xp_projections.json"
FROZEN_DIR = fpl_actuals.FROZEN_DIR

WINDOWS = ("season", "last3", "last5", "last10")
POSITIONS = ("ALL", "GKP", "DEF", "MID", "FWD")

SOURCE = ("FPL official API per-gameweek history; "
          "xP from GoalIQ deadline freezes")
MASK_TEXT = "Next-gameweek and horizon xP are GoalIQ Premium"
COMPARE_NOTE = ("compared_gws are finished gameweeks with a deadline freeze. "
                "Per player, xp_frozen and pts_compared cover the same "
                "gameweeks: those where the player had a freeze xP and an "
                "FPL row (played minutes). A frozen player with no minutes "
                "is not in the comparison.")

# GW-rivin sarakkeet jotka summataan ikkunan yli. Avain = vastauksen kentta,
# arvo = gw-tiedoston sarake. Kaikki FPL:n virallisia lukuja.
_SUM_COLS = {
    "pts": "pts", "mins": "mins", "starts": "starts", "g": "g", "a": "a",
    "xg": "xg", "xa": "xa", "xgi": "xgi", "cs": "cs", "gc": "gc",
    "xgc": "xgc", "saves": "saves", "bonus": "bonus", "bps": "bps",
    "ict": "ict", "yc": "yc", "rc": "rc", "dc": "dc", "tkl": "tkl",
    "cbi": "cbi", "rec": "rec",
}
_ROUND2 = ("xg", "xa", "xgi", "xgc", "ict")
_INT_COLS = tuple(k for k in _SUM_COLS if k not in _ROUND2)

_FROZEN_RE = re.compile(r"^gw(\d+)\.json$")


# ---------------------------------------------------------------------------
# Levylukijat (mtime-cache, sama kuvio kuin fpl_actuals)
# ---------------------------------------------------------------------------
_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, dict]] = {}


def _load_json_cached(path: Path) -> dict | None:
    if not path.exists():
        return None
    mtime = path.stat().st_mtime
    key = str(path)
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and hit[0] == mtime:
            return hit[1]
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    with _LOCK:
        _CACHE[key] = (mtime, doc)
    return doc


def _frozen_gws_on_disk() -> list[int]:
    if not FROZEN_DIR.exists():
        return []
    out = []
    for p in FROZEN_DIR.iterdir():
        m = _FROZEN_RE.match(p.name)
        if m:
            out.append(int(m.group(1)))
    return sorted(out)


def load_sources() -> tuple[dict, dict, dict[int, dict[int, float]], dict | None]:
    """(stats_doc, gw_doc, frozen_by_gw, live_xp). 503 jos runko puuttuu.

    Freezet luetaan `fpl_actuals.frozen_xp_for`:n kautta (sama cache kuin
    Model vs actual -listalla), elava projektio `load_xp_actionable`:n kautta
    joka ei palauta kierrosta jonka deadline on mennyt.
    """
    stats = _load_json_cached(STATS_PATH)
    if stats is None:
        raise RateTeamError(503, "Player stats data is not built yet.")
    gw_doc = fpl_actuals.player_gw_doc()
    if gw_doc is None:
        raise RateTeamError(503, "Per-gameweek player data is not built yet.")
    frozen = {gw: fpl_actuals.frozen_xp_for(gw) for gw in _frozen_gws_on_disk()}
    frozen = {gw: m for gw, m in frozen.items() if m}
    live = None
    if XP_PATH.exists():
        from src.models.fpl_xp import load_xp_actionable
        live = load_xp_actionable(XP_PATH)
        if not (live.get("players") and live.get("meta")):
            live = None
    return stats, gw_doc, frozen, live


# ---------------------------------------------------------------------------
# Puhdas aggregointi
# ---------------------------------------------------------------------------
def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_ts(s) -> _dt.datetime | None:
    if not isinstance(s, str) or not s:
        return None
    try:
        d = _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=_dt.timezone.utc)
    return d


def _latest(*stamps) -> str | None:
    best, best_dt = None, None
    for s in stamps:
        d = _parse_ts(s)
        if d and (best_dt is None or d > best_dt):
            best, best_dt = s, d
    return best


def window_bounds(kind: str, max_gw: int) -> dict:
    """{kind, n, from, to}. Esikaudella (max_gw=0) from=1, to=0 = tyhja."""
    if kind == "season":
        return {"kind": "season", "n": None, "from": 1, "to": max_gw}
    n = int(kind[4:])
    return {"kind": "last_n", "n": n, "from": max(1, max_gw - n + 1),
            "to": max_gw}


def _stats_index(stats_doc: dict) -> dict[int, dict]:
    cols = ((stats_doc.get("meta") or {}).get("cols")) or []
    out: dict[int, dict] = {}
    for row in stats_doc.get("players") or []:
        if not isinstance(row, list) or len(row) < len(cols):
            continue
        d = dict(zip(cols, row))
        try:
            out[int(d["id"])] = d
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _live_index(live_xp: dict | None) -> tuple[dict[int, dict], int | None]:
    """{id: pelaaja}, seuraava vaikutettava kierros (trimmed_from tai
    deadline_gameweek). Elava projektio on jo rajattu actionable-kierroksiin."""
    if not live_xp:
        return {}, None
    meta = live_xp.get("meta") or {}
    nxt = meta.get("trimmed_from")
    if not isinstance(nxt, int):
        nxt = meta.get("deadline_gameweek")
    if not isinstance(nxt, int):
        nxt = meta.get("next_gameweek")
    idx: dict[int, dict] = {}
    for p in live_xp.get("players") or []:
        try:
            idx[int(p["id"])] = p
        except (KeyError, TypeError, ValueError):
            continue
    return idx, (nxt if isinstance(nxt, int) else None)


def _live_fields(p: dict | None, next_gw: int | None) -> tuple:
    """(next_gw_xp, xp_horizon_total) elavasta projektiosta.

    Horisontti summataan jaljella olevista (actionable) kierroksista eika
    lueta tiedoston `xp_horizon_total`-kentasta: se kantaa myos jo alkaneen
    kierroksen (fpl_gameweek.actionable_gameweeks, mitattu 25.8).
    """
    if not p:
        return None, None
    gws = p.get("gameweeks") or []
    nxt = None
    total = 0.0
    seen = False
    for g in gws:
        if not isinstance(g, dict):
            continue
        xp = _num(g.get("xp"))
        if xp is None:
            continue
        seen = True
        total += xp
        if next_gw is not None and g.get("gw") == next_gw:
            nxt = round(xp, 2)
    return nxt, (round(total, 2) if seen else None)


def aggregate(stats_doc: dict, gw_doc: dict,
              frozen_by_gw: dict[int, dict[int, float]],
              live_xp: dict | None, window: str = "season",
              pos: str = "ALL", top_n: int = 0, premium: bool = False) -> dict:
    """Vastausrunko ilman levya. Ks. moduulin docstring paatoksista 1-6."""
    if window not in WINDOWS:
        raise ValueError(f"unknown window {window!r}")
    if pos not in POSITIONS:
        raise ValueError(f"unknown pos {pos!r}")
    smeta = stats_doc.get("meta") or {}
    gmeta = gw_doc.get("meta") or {}
    live_meta = (live_xp or {}).get("meta") or {}

    season_stats = smeta.get("basis_season")
    season_gw = gmeta.get("basis_season")
    generated_at = _latest(smeta.get("generated_at"), gmeta.get("generated_at"),
                           live_meta.get("generated_at"))
    if not season_stats or not season_gw or season_stats != season_gw:
        # Paatos 2: kausisekoitus ei saa renderoitya. Syy on lukijalle, ei
        # lokiin: sivu voi sanoa miksi taulukko on tyhja.
        return {
            "meta": {
                "available": False,
                "reason": (f"season mismatch between sources: stats "
                           f"{season_stats!r}, gameweek rows {season_gw!r}"),
                "generated_at": generated_at,
                "basis_season": None, "max_gw": None, "window": None,
                "frozen_gws": [], "compared_gws": [],
                "masked": not premium, "mask": None if premium else MASK_TEXT,
                "source": SOURCE, "n_players": 0,
            },
            "players": [],
        }
    # Elava projektio eri kaudelta: pudotetaan hiljaa mutta ei sekoiteta.
    if live_xp and live_meta.get("season") not in (None, season_stats):
        live_xp = None
        live_meta = {}

    max_gw = gmeta.get("max_gw")
    max_gw = max_gw if isinstance(max_gw, int) and max_gw > 0 else 0
    win = window_bounds(window, max_gw)
    lo, hi = win["from"], win["to"]

    # Paatos 4: vertailuun kelpaa vain valmis kierros.
    finished = smeta.get("finished_events")
    finished = finished if isinstance(finished, int) else max_gw
    cmp_hi = min(finished, max_gw)
    frozen_gws = sorted(g for g, m in frozen_by_gw.items() if m)
    compared_gws = [g for g in frozen_gws if lo <= g <= min(hi, cmp_hi)]

    cols = gmeta.get("cols") or []
    try:
        idx = {name: cols.index(src) for name, src in _SUM_COLS.items()}
        i_gw = cols.index("gw")
    except ValueError:
        raise RateTeamError(503, "Per-gameweek player data has an unknown layout.")
    need = max([i_gw, *idx.values()]) + 1

    stats_idx = _stats_index(stats_doc)
    live_idx, next_gw = _live_index(live_xp)

    players_out: list[dict] = []
    for pid_s, rows in (gw_doc.get("players") or {}).items():
        try:
            pid = int(pid_s)
        except (TypeError, ValueError):
            continue
        # Per kierros: tuplakierroksella kaksi rivia summautuu (fpl_actuals
        # 22.8 loydos: ensimmainen osuma ei riita).
        per_gw: dict[int, dict] = {}
        for r in rows or []:
            if not isinstance(r, list) or len(r) < need:
                continue
            gw = r[i_gw]
            if not isinstance(gw, int) or gw < lo or gw > hi:
                continue
            acc = per_gw.setdefault(gw, {k: 0.0 for k in _SUM_COLS})
            for k, i in idx.items():
                v = _num(r[i])
                if v is not None:
                    acc[k] += v
        if not per_gw:
            # Ei riveja ikkunassa. Pelaaja jolla ei ole yhtaan rivia koko
            # tiedostossa ei kuulu vastaukseen; ikkunan ulkopuolella pelannut
            # kuuluu mutta nollilla (rivit ovat todiste, ikkuna vain rajaa).
            if not any(isinstance(r, list) and len(r) > i_gw
                       and isinstance(r[i_gw], int) for r in rows or []):
                continue
        fpl = {k: 0.0 for k in _SUM_COLS}
        for acc in per_gw.values():
            for k in _SUM_COLS:
                fpl[k] += acc[k]
        for k in _INT_COLS:
            fpl[k] = int(round(fpl[k]))
        for k in _ROUND2:
            fpl[k] = round(fpl[k], 2)
        games = len(per_gw)
        fpl["games"] = games
        fpl["ppg"] = round(fpl["pts"] / games, 1) if games else None

        # Paatos 5: vertailu vain kierroksilta joilla on molemmat.
        xp_sum = 0.0
        pts_sum = 0
        n_cmp = 0
        for g in compared_gws:
            fx = frozen_by_gw.get(g, {}).get(pid)
            if fx is None or g not in per_gw:
                continue
            xp_sum += float(fx)
            pts_sum += int(round(per_gw[g]["pts"]))
            n_cmp += 1
        gws_out = []
        for g in range(lo, hi + 1):
            fx = frozen_by_gw.get(g, {}).get(pid) if g in frozen_by_gw else None
            gws_out.append({
                "gw": g,
                "pts": int(round(per_gw[g]["pts"])) if g in per_gw else None,
                "xp_frozen": round(float(fx), 2) if fx is not None else None,
            })
        xp_frozen = round(xp_sum, 2) if n_cmp else None
        diff = round(pts_sum - xp_sum, 2) if n_cmp else None

        # Metakentat: stats ensin, elava projektio varalla, muuten null.
        # Ei keksittyja arvoja: puuttuva on null.
        st = stats_idx.get(pid) or {}
        lv = live_idx.get(pid) or {}

        def pick(*cands):
            for c in cands:
                if c is not None and c != "":
                    return c
            return None

        web_name = pick(st.get("name"), lv.get("web_name"))
        team_short = pick(st.get("team"), lv.get("team_short"))
        ppos = pick(st.get("pos"), lv.get("pos"))
        if pos != "ALL" and ppos != pos:
            continue
        price = pick(_num(st.get("price")), _num(lv.get("price")))
        owned = pick(_num(st.get("own")), _num(lv.get("owned_pct")))
        status = pick(st.get("status"), lv.get("status"))
        news = lv.get("news")
        news = news if isinstance(news, str) else None

        nxt_xp, horizon = _live_fields(lv, next_gw) if premium else (None, None)
        players_out.append({
            "id": pid,
            # `code` (FPL:n pysyva pelaajakoodi) ei ole yhdessakaan
            # levylahteessa. Null on totuus; keksitty luku ei.
            "code": None,
            "web_name": web_name, "team_short": team_short, "pos": ppos,
            "price": price, "owned_pct": owned, "status": status, "news": news,
            "fpl": fpl,
            "goaliq": {
                "xp_frozen": xp_frozen,
                "pts_compared": pts_sum if n_cmp else None,
                "n_compared": n_cmp,
                "diff": diff,
                "gws": gws_out,
                "next_gw": next_gw,
                "next_gw_xp": nxt_xp,
                "xp_horizon_total": horizon,
            },
        })

    # Jarjestys: pisteet laskeva, freeze-xP laskeva, id nouseva.
    players_out.sort(key=lambda p: (
        -p["fpl"]["pts"],
        -(p["goaliq"]["xp_frozen"] if p["goaliq"]["xp_frozen"] is not None
          else float("-inf")),
        p["id"]))
    if top_n and top_n > 0:
        players_out = players_out[:top_n]

    return {
        "meta": {
            "available": True,
            "generated_at": generated_at,
            "basis_season": season_stats,
            "max_gw": max_gw,
            "finished_gw": cmp_hi,
            "window": win,
            "frozen_gws": frozen_gws,
            "compared_gws": compared_gws,
            "compare_note": COMPARE_NOTE,
            "masked": not premium,
            "mask": None if premium else MASK_TEXT,
            "source": SOURCE,
            "n_players": len(players_out),
        },
        "players": players_out,
    }


def build_response(window: str = "season", pos: str = "ALL", top_n: int = 0,
                   premium: bool = False) -> dict:
    stats, gw_doc, frozen, live = load_sources()
    return aggregate(stats, gw_doc, frozen, live, window=window, pos=pos,
                     top_n=top_n, premium=premium)
