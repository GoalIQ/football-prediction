"""DefCon-live (2.8.2026): oman joukkueen defensive contribution KESKEN kierroksen.

Miksi tama on ainoa live-pinta jonka rakennamme: FPL:n virallinen appi vei
live-rankit 20.-21.7. featurepudotuksessa, mutta DefCon-kertyma on yha aukko.
Se on uusi pistesaanto, sita on vaikea seurata ottelun aikana, ja meilla on jo
koko DefCon-datamalli (leaders, per-GW-matriisi, xP-komponentti). "Gabriel 7/10,
20 min jaljella" on syy avata appi kesken lauantain.

LAHDE = FPL:n oma `defensive_contribution` element/{gw}/live/-vastauksesta.
Sama kentta jota historiallinen DefCon-putki lukee (fpl_xp.dc_hit,
fpl_leaders) -> live ja historia EIVAT voi ajautua eri mielta. Kynnykset
tulevat fpl_leaders.DEFCON_THRESHOLD:sta samasta syysta.

HUOM minuuttisaanto: historiallinen osumaprosentti suodattaa >= 60 min rivit
(count_dc_hits), koska se mittaa luotettavuutta per taysi peli. LIVE EI SAA
suodattaa: FPL myontaa DefCon-pisteen kun kynnys tayttyy, pelatuista
minuuteista riippumatta. Suodatus tekisi live-nakymasta vaaran.

Esikausi ja kierrosten valit: is_current puuttuu -> available=False + note,
sama konventio kuin price watchissa. Ei keksita dataa jota ei ole.
"""
from __future__ import annotations

import threading
import time
from typing import Any

import requests

from src.models.fpl_leaders import DEFCON_THRESHOLD
from src.models.fpl_rate_team import RateTeamError

FPL_BASE = "https://fantasy.premierleague.com/api"
_UA = {"User-Agent": "GoalIQ/1.0"}

# Live-data muuttuu ottelun aikana jatkuvasti, mutta 0.5 vCPU:n Renderilla ja
# FPL:n rajoitteilla per-pyynto-haku on kohtuuton. 60 s on tarpeeksi tuore
# ottelunseurantaan ja pitaa kuorman kurissa.
_LIVE_TTL_S = 60.0
_lock = threading.Lock()
_live_cache: dict[int, tuple[float, dict[int, dict]]] = {}


def _get(url: str, timeout: float = 15.0) -> Any:
    r = requests.get(url, timeout=timeout, headers=_UA)
    r.raise_for_status()
    return r.json()


def _live_stats(gw: int) -> dict[int, dict]:
    """element_id -> stats-dict kierroksen live-datasta (60 s TTL)."""
    now = time.time()
    with _lock:
        hit = _live_cache.get(gw)
        if hit and (now - hit[0]) < _LIVE_TTL_S:
            return hit[1]
    data = _get(f"{FPL_BASE}/event/{gw}/live/")
    out: dict[int, dict] = {}
    for el in data.get("elements", []):
        if isinstance(el.get("id"), int):
            out[el["id"]] = el.get("stats") or {}
    with _lock:
        _live_cache[gw] = (time.time(), out)
    return out


_fx_cache: dict[int, tuple[float, dict[int, str]]] = {}


def _match_state_by_team(gw: int) -> dict[int, str]:
    """team_id -> 'upcoming' | 'live' | 'finished' talle kierrokselle.

    🔴 MIKSI TAMA ON PAKKO OLLA (4.9.2026): ilman ottelun tilaa rivi ei voi
    kertoa tarinaa vaan pelkan luvun. "Kaksi puuttuu" on eri asia kesken
    ottelun (viela ehtii) ja ottelun jalkeen (jai vajaaksi) — sama luku,
    vastakkainen merkitys. Aiempi payload ei erottanut naita lainkaan, joten
    kayttoliittyman oli pakko jattaa tulkinta lukijalle.

    Tuplakierros: joukkueella voi olla kaksi ottelua. Tila on 'live' jos yksi
    on kaynnissa, 'finished' vasta kun kaikki alkaneet ovat ohi ja alkamatta
    olevia ei ole, muuten 'upcoming'.
    """
    now = time.time()
    with _lock:
        hit = _fx_cache.get(gw)
        if hit and (now - hit[0]) < _LIVE_TTL_S:
            return hit[1]
    try:
        fixtures = _get(f"{FPL_BASE}/fixtures/?event={gw}")
    except Exception:
        # Fixture-feedin katko ei saa kaataa DefCon-nakymaa. Tuntematon tila
        # on eri asia kuin "paattynyt": kayttoliittyma nayttaa silloin pelkan
        # luvun ilman tarinaa (nolla ei ole sama kuin ei tietoa).
        return {}
    by_team: dict[int, list[dict]] = {}
    for fx in fixtures if isinstance(fixtures, list) else []:
        for key in ("team_h", "team_a"):
            tid = fx.get(key)
            if isinstance(tid, int):
                by_team.setdefault(tid, []).append(fx)
    out: dict[int, str] = {}
    for tid, fxs in by_team.items():
        started = [f for f in fxs if f.get("started")]
        if not started:
            out[tid] = "upcoming"
            continue
        all_done = all(
            bool(f.get("finished") or f.get("finished_provisional"))
            for f in started
        )
        pending = len(fxs) > len(started)
        out[tid] = "finished" if (all_done and not pending) else "live"
    with _lock:
        _fx_cache[gw] = (time.time(), out)
    return out


def _entry_picks(entry_id: int, gw: int) -> list[dict]:
    data = _get(f"{FPL_BASE}/entry/{entry_id}/event/{gw}/picks/")
    picks = data.get("picks")
    if not isinstance(picks, list):
        raise RateTeamError(502, "FPL returned no picks for that team.")
    return picks


def _unavailable(note: str) -> dict:
    return {
        "meta": {
            "available": False,
            "gw": None,
            "generated_at": None,
            "thresholds": DEFCON_THRESHOLD,
            "note": note,
        },
        "players": [],
    }


def defcon_story(dc: int, threshold: int | None, hit: bool,
                 match_state: str | None) -> dict | None:
    """Rivin tarina: kategoria + lause. None = ei sanottavaa.

    EI TOIMINTOVERBIA (tietoinen valinta 4.9): Shatteredin indeksissa
    jokaisella rivilla on "WATCH ->" tai "VIEW ->". Meilla ei ole paikkaa
    johon "watch" veisi — live-ottelusivua ei ole, ja pelaajakortti avautuisi
    tyhjana hakuna. Toimintoverbi joka vie umpikujaan on huonompi kuin ei
    verbia lainkaan, joten kentta jatetaan pois kunnes kohde on olemassa.

    🔴 MIKSI RIVI EI SAA OLLA PELKKA LUKU (auditointi 4.9.2026): lista oli
    13 rivia muodossa `Tavernier BOU · MID · 90'  11/12`. Sama luku tarkoittaa
    kahta vastakkaista asiaa sen mukaan onko ottelu kesken vai ohi, ja lukijan
    piti paatella se itse. FPL Shatteredin "intelligence index" tekee saman
    datan luettavaksi: kategoria + yksi lause + toiminto.

    MITATTU ENNEN KIRJOITTAMISTA (`scripts/measure_defcon_rows.py`, 8 077
    pelaaja-GW-rivia kaudelta 2025/26) — jokainen haara laukeaa oikeasti:
      lopputila:  osui 13,9 %  ·  jai <= 2 vajaaksi 9,6 %  ·  jai kauemmas 76,5 %
      kesken (75', lineaarinen arvio): <= 2 puuttuu 15,3 %  ·  osunut 12,8 %
    Haaraa jota ei laukea ei kirjoiteta (muisti:
    syyn-haara-joka-ei-laukea-on-copyn-lupaus).

    Lause ja luku tulevat SAMASTA rivista: jokainen lause sisaltaa saman
    `dc`/`threshold`-parin joka rivilla nakyy, eika mitaan johdeta muualta.

    `match_state=None` (fixture-feed ei vastannut) EI ole "paattynyt": silloin
    palautetaan neutraali lause ilman aikamuotoa. Tuntematon on oma tilansa.
    """
    if threshold is None:
        return None
    if hit:
        return {"tag": "SCORED", "line": f"Has the two points at {dc} of {threshold}."}
    remaining = max(0, threshold - dc)
    if match_state == "finished":
        if remaining <= 2:
            return {"tag": "JUST SHORT",
                    "line": f"Finished {remaining} short of {threshold}."}
        return {"tag": "SHORT", "line": f"Finished on {dc} of {threshold}."}
    if match_state == "live":
        if remaining <= 2:
            return {
                "tag": "CLOSE",
                "line": (f"{remaining} away from {threshold} with the match "
                         "still on."),
            }
        return {"tag": "BUILDING",
                "line": f"{dc} of {threshold} with the match still on."}
    if match_state == "upcoming":
        return {"tag": "NOT STARTED", "line": "Has not kicked off yet."}
    # Tuntematon tila: ei aikamuotoa, pelkka luku lauseena.
    return {"tag": None, "line": f"{dc} of {threshold}."}


def load_defcon_live(entry_id: int | None = None,
                     ids: list[int] | None = None) -> dict:
    """Live DefCon -kertyma joko entryn kokoonpanolle tai annetuille id:ille.

    Nostaa RateTeamErrorin vain kayttajan syotteen tai ylavirran vian takia;
    puuttuva kierros ei ole virhe vaan available=False.
    """
    from src.data.fpl_api import fetch_bootstrap

    if entry_id is None and not ids:
        raise RateTeamError(400, "Give either entry or ids.")

    boot = fetch_bootstrap()
    events = boot.get("events") or []
    current = next((e for e in events if e.get("is_current")), None)
    if current is None:
        return _unavailable(
            "DefCon live goes live when a gameweek is in play."
        )
    gw = int(current["id"])

    pos_by_type = {
        int(t["id"]): t.get("singular_name_short")
        for t in (boot.get("element_types") or [])
        if isinstance(t.get("id"), int)
    }
    team_short = {
        int(t["id"]): t.get("short_name")
        for t in (boot.get("teams") or [])
        if isinstance(t.get("id"), int)
    }
    elements = {
        int(e["id"]): e for e in (boot.get("elements") or [])
        if isinstance(e.get("id"), int)
    }

    if entry_id is not None:
        picks = _entry_picks(entry_id, gw)
        wanted = [(int(p["element"]), int(p.get("position") or 0),
                   bool(p.get("is_captain")))
                  for p in picks if isinstance(p.get("element"), int)]
    else:
        wanted = [(int(i), 0, False) for i in (ids or [])]

    stats = _live_stats(gw)
    match_state = _match_state_by_team(gw)

    players: list[dict] = []
    for element_id, squad_pos, is_captain in wanted:
        el = elements.get(element_id)
        if el is None:
            continue
        pos = pos_by_type.get(int(el.get("element_type") or 0)) or "?"
        thr = DEFCON_THRESHOLD.get(pos)  # GKP -> None, ei DefConia
        st = stats.get(element_id) or {}
        dc = int(st.get("defensive_contribution", 0) or 0)
        minutes = int(st.get("minutes", 0) or 0)
        players.append({
            "id": element_id,
            "web_name": el.get("web_name"),
            "team_short": team_short.get(int(el.get("team") or 0)),
            "pos": pos,
            "squad_position": squad_pos or None,
            "is_captain": is_captain,
            "minutes": minutes,
            "defcon": dc,
            "threshold": thr,
            # Kynnys tayttyy minuuteista riippumatta — EI 60 min suodatusta,
            # toisin kuin historiallisessa osumaprosentissa.
            "hit": thr is not None and dc >= thr,
            "remaining": None if thr is None else max(0, thr - dc),
            "eligible": thr is not None,
            # 'upcoming' | 'live' | 'finished' | None (feed ei vastannut).
            # None EI ole 'finished': tuntematon tila on oma tilansa.
            "match_state": match_state.get(int(el.get("team") or 0)),
        })
        players[-1]["story"] = defcon_story(
            dc, thr, players[-1]["hit"], players[-1]["match_state"]
        )

    return {
        "meta": {
            "available": True,
            "gw": gw,
            "generated_at": current.get("deadline_time"),
            "thresholds": DEFCON_THRESHOLD,
            "note": (
                "Defensive contribution so far this gameweek, straight from "
                "the FPL match feed. A defender scores 2 points at 10 combined "
                "clearances, blocks, interceptions and tackles; a midfielder "
                "or forward at 12 including ball recoveries. Goalkeepers do "
                "not score defensive contribution."
            ),
        },
        "players": players,
    }
