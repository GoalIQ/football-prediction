"""TOTEUTUNEET FPL-pisteet projektion rinnalle (22.8.2026, Villen tilaus).

MIKSI: sivu on tahan asti nayttanyt vain sen mita malli ODOTTI. Villen
kysymys oli suora: "oisko hyva jos naytettais myos fpl pisteet mita pelaajat
sai oikeesti". Se on myos ainoa tapa jolla lukija voi tarkistaa projektion
ilman ulkoista lahdetta — sama linja kuin julkisen track recordin kanssa.

LAHDE: `fpl/player-gw.json`, jonka `scripts/build_fpl_player_gw.py` kirjoittaa
FPL:n virallisesta element-summary-historiasta. EI uutta datalahdetta eika
uutta verkkokutsua serve-ajassa: tiedosto on jo olemassa ja cron paivittaa
sen. Basis-kausi luetaan tiedoston metasta, joten 25/26-arkistoa EI voi
vahingossa esittaa kuluvan kauden toteumana.

RAJOITE JOKA ON RAKENTEESSA EIKA KONVENTIOSSA: rivi palautetaan vain
kierroksille jotka tiedosto kantaa. Pelaamattomalle kierrokselle ei ole
riviä, joten `points_for(gw)` palauttaa tyhjan kartan eika nollia — nolla
olisi vaite ("pelasi eika saanut pisteita"), puuttuva on totuus.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAYER_GW_PATH = ROOT / "fpl" / "player-gw.json"

# Levyvalimuisti mtime-avaimella: API lukee levylta (Render-konventio), ja
# cron kirjoittaa tiedoston uusiksi ~3 h valein. Ilman mtime-avainta prosessi
# jaisi kayntiin jaadytettyyn nakymaan (sama vikaluokka kuin _DATA_CACHE
# 22.8: pysyva cache piti Serie A:ta tyhjana koko prosessin elinian).
_LOCK = threading.Lock()
_CACHE: dict[str, object] = {"mtime": None, "doc": None}


def _load() -> dict | None:
    if not PLAYER_GW_PATH.exists():
        return None
    mtime = PLAYER_GW_PATH.stat().st_mtime
    with _LOCK:
        if _CACHE["mtime"] == mtime:
            return _CACHE["doc"]  # type: ignore[return-value]
    try:
        doc = json.loads(PLAYER_GW_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    with _LOCK:
        _CACHE["mtime"] = mtime
        _CACHE["doc"] = doc
    return doc


def basis_season() -> str | None:
    doc = _load()
    return ((doc or {}).get("meta") or {}).get("basis_season")


def max_gw() -> int | None:
    doc = _load()
    gw = ((doc or {}).get("meta") or {}).get("max_gw")
    return gw if isinstance(gw, int) and gw > 0 else None


# ---------------------------------------------------------------------------
# Jaadytetty xP (22.8 ilta, Villen havainto)
# ---------------------------------------------------------------------------
# 🔴 MIKSI TAMA ON PAKOLLINEN "Model vs actual" -listalle: elava xP LIIKKUU
# kesken ja jalkeen kierroksen, koska malli lukee FPL:n live-dataa. Mitattu
# tuotannosta 22.8 klo 18:15 UTC, GW1: Gabriel 5.78 -> 5.14, B.Fernandes
# 5.70 -> 4.74, Lammens 4.07 -> 2.88. Drift on systemaattisesti ALASPAIN
# niilla jotka alisuorittivat, eli projektio paivittyy kohti toteumaa.
#
# Jos toteumaa verrataan elavaan lukuun, malli nayttaa TARKEMMALTA kuin se
# oli: Gabrielin virhe olisi -0.14 kun se oikeasti oli -0.78. Se on juuri se
# nakyma jonka piti olla se paikka jossa mallin virhe on luettavissa.
#
# Oikea vertailukohta on deadline-freeze (`scripts/freeze_fpl_xp_gw.py`),
# joka on IMMUTABLE ja kirjoitetaan ennen kierroksen alkua — sama periaate
# kuin ottelulokissa. Freeze on ollut olemassa 30.7 lahtien; taalla se vain
# kytketaan kayttoon.
FROZEN_DIR = ROOT / "data" / "fpl_xp_frozen"

_FROZEN_LOCK = threading.Lock()
_FROZEN_CACHE: dict[int, tuple[float, dict]] = {}


def _load_frozen(gw: int) -> dict | None:
    p = FROZEN_DIR / f"gw{gw}.json"
    if not p.exists():
        return None
    mtime = p.stat().st_mtime
    with _FROZEN_LOCK:
        hit = _FROZEN_CACHE.get(gw)
        if hit and hit[0] == mtime:
            return hit[1]
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    with _FROZEN_LOCK:
        _FROZEN_CACHE[gw] = (mtime, doc)
    return doc


def frozen_xp_for(gw: int) -> dict[int, float]:
    """{element_id: xP} sellaisena kuin se oli kierroksen deadline-freezessa.

    Tyhja kartta kun freezea ei ole -> kutsuja EI saa nayttaa
    "Model vs actual" -listaa lainkaan. Elavan luvun kayttaminen sen sijasta
    olisi juuri se vaaristyma jota vastaan tama funktio on olemassa.
    """
    doc = _load_frozen(gw)
    if not doc:
        return {}
    out: dict[int, float] = {}
    for r in doc.get("players") or []:
        try:
            out[int(r["id"])] = float(r["xp"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def frozen_meta(gw: int) -> dict | None:
    """Freezen meta (deadline, frozen_at) — UI kertoo MILLOIN luku pinnattiin."""
    doc = _load_frozen(gw)
    return (doc or {}).get("meta")


def points_for(gw: int, season: str | None = None) -> dict[int, int]:
    """{element_id: toteutuneet FPL-pisteet} annetulle kierrokselle.

    `season` (esim. "2026/27") on VARTIJA eika suodatin: jos se annetaan ja
    tiedoston basis on eri kausi, palautetaan tyhja. Ilman tata 25/26-arkiston
    pisteet voisivat renderoityä kuluvan kauden rivin viereen ilman etta
    mikaan kaatuu — tasan se hiljainen vikaluokka joka on osunut ennenkin
    (korttien vaara lahde 17.8, kausisekoitus stats-buildissa 22.8).
    """
    doc = _load()
    if not doc:
        return {}
    meta = doc.get("meta") or {}
    if season and meta.get("basis_season") != season:
        return {}
    cols = meta.get("cols") or []
    try:
        i_gw, i_pts = cols.index("gw"), cols.index("pts")
    except ValueError:
        return {}
    out: dict[int, int] = {}
    for pid, rows in (doc.get("players") or {}).items():
        # 🔴 TUPLAKIERROS (korjattu 22.8, julkaisuportin loydos): aiempi versio
        # katkaisi silmukan ENSIMMAISEN osuman jalkeen, joten kahden ottelun
        # kierroksella vain toisen ottelun pisteet paatyivat lukuun. FPL:n oma
        # GW-summa on molempien summa, joten sivu olisi nayttanyt pienempaa
        # lukua kuin pelaajan oma FPL-tili — ja copy sanoo luvun tulevan
        # "official FPL feed" -lahteesta. Vika olisi ilmennyt vasta kauden
        # ensimmaisella DGW:lla eika mikaan olisi kaatunut.
        yhteensa = None
        for r in rows:
            if len(r) > max(i_gw, i_pts) and r[i_gw] == gw:
                try:
                    yhteensa = (yhteensa or 0) + int(r[i_pts])
                except (TypeError, ValueError):
                    pass
        if yhteensa is not None:
            out[int(pid)] = yhteensa
    return out
