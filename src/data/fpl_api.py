"""FPL:n virallisen API:n client (fantasy.premierleague.com/api).

Käytetään FPL Phase 1 (xP) -builderissa ja -backtestissä: pelaajien
kausibaselinet + per-GW-historia (element-summary) + fixturet tuloksineen.
Pelkkä JSON-HTTP — EI selainta, EI soccerdataa (FBref/Chrome-riippuvuus
todettu rikkinäiseksi palvelinajossa, ks. Phase 1 -riskilippuraportti).

Levyvälimuisti config.RAW_DATA_DIR/fpl/ alla (gitignoressa):
  - bootstrap/fixtures: TTL-pohjainen (tunteja) — kevyet, haetaan tuoreena.
  - element-summary: per pelaaja per kausi; valmiin kauden data ei muutu,
    joten backtest-ajot osuvat välimuistiin. Kesken kauden refresh-job
    pakottaa uudelleenhaun (force=True).
"""
from __future__ import annotations

import datetime as _dt
import json
import time
from pathlib import Path

import requests

import config

FPL_BASE = "https://fantasy.premierleague.com/api"
HEADERS = {"User-Agent": "Mozilla/5.0 (GoalIQ refresh job)"}
CACHE_DIR = config.RAW_DATA_DIR / "fpl"

# Kohtelias tahti element-summary-haulle (841 pelaajaa) — ei hakata FPL:ää.
SUMMARY_DELAY_S = 0.15


def _cache_path(name: str) -> Path:
    p = CACHE_DIR / name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _get_json(url: str) -> dict | list:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def _read_cache(path: Path, max_age_s: float | None) -> dict | list | None:
    if not path.exists():
        return None
    if max_age_s is not None:
        age = time.time() - path.stat().st_mtime
        if age > max_age_s:
            return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_cache(path: Path, data: dict | list) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def fetch_bootstrap(max_age_s: float = 3600, force: bool = False) -> dict:
    """bootstrap-static: pelaajat (elements), joukkueet, GW:t (events).

    TTL oli 6 h ja refresh ajaa 3 h valein, eli cache oli PIDEMPI kuin
    paivitysvali: paikallinen builderiajo saattoi leipoa artefaktiin jopa 6 h
    vanhan joukkuejaon. Siirtoikkunassa se tarkoittaa etta pelaajan projektio
    lasketaan vaaran joukkueen otteluita vastaan (10.8.2026: Bruno G. yha
    Newcastlessa, 10,2 % omistus). 1 h pitaa cachen tarkoituksen (ei hakata
    FPL:aa 500 kutsulla) ilman etta se voi olla tuoreinta refreshia jaljessa.
    Lukittu testissa tests/test_fpl_transfer_watch.py."""
    path = _cache_path("bootstrap_static.json")
    if not force:
        cached = _read_cache(path, max_age_s)
        if cached is not None:
            return cached
    data = _get_json(f"{FPL_BASE}/bootstrap-static/")
    _write_cache(path, data)
    return data


def fetch_fixtures(max_age_s: float = 6 * 3600, force: bool = False) -> list:
    """fixtures: kaikki kauden ottelut event/kickoff/tulos-kentillä."""
    path = _cache_path("fixtures.json")
    if not force:
        cached = _read_cache(path, max_age_s)
        if cached is not None:
            return cached
    data = _get_json(f"{FPL_BASE}/fixtures/")
    _write_cache(path, data)
    return data


def fetch_element_summary(element_id: int, season_key: str,
                          force: bool = False) -> dict:
    """element-summary/{id}: pelaajan per-GW-historia (history-lista).

    season_key erottelee kaudet välimuistissa (esim. "2526") — valmiin
    kauden tiedostot eivät vanhene, kesken kauden refresh käyttää force=True.
    """
    path = _cache_path(f"summary_{season_key}/element_{element_id}.json")
    if not force:
        cached = _read_cache(path, max_age_s=None)
        if cached is not None:
            return cached
    data = _get_json(f"{FPL_BASE}/element-summary/{element_id}/")
    _write_cache(path, data)
    time.sleep(SUMMARY_DELAY_S)
    return data


def season_key_from_bootstrap(boot: dict) -> str:
    """Kausiavain events-deadlineista, esim. 2025-08 → "2526"."""
    first = boot["events"][0]["deadline_time"]  # esim. "2025-08-15T17:30:00Z"
    y = int(first[:4])
    return f"{y % 100:02d}{(y + 1) % 100:02d}"


def fetch_all_summaries(boot: dict, force: bool = False,
                        progress_every: int = 100) -> dict[int, list[dict]]:
    """Hae kaikkien pelaajien per-GW-historiat. Palauttaa {element_id: history}.

    Ensimmäinen ajo ~841 pyyntöä (muutama minuutti kohteliaalla tahdilla),
    sen jälkeen levyvälimuistista.
    """
    season_key = season_key_from_bootstrap(boot)
    out: dict[int, list[dict]] = {}
    ids = [e["id"] for e in boot["elements"]]
    for i, eid in enumerate(ids, 1):
        s = fetch_element_summary(eid, season_key, force=force)
        out[eid] = s.get("history", [])
        if progress_every and i % progress_every == 0:
            print(f"      element-summary {i}/{len(ids)}")
    return out


def parse_kickoff(s: str | None) -> _dt.datetime | None:
    if not s:
        return None
    try:
        return _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Yleisliigan standings + entryn picks (EO-BY-TIER, 25.8)
# ---------------------------------------------------------------------------
# 🔴 NAMA EIVAT TOIMI GH-RUNNERILTA. Kirjattu tapaus: FPL-suuntaiset kutsut
# estettiin GitHubin IP-avaruudesta. Aja Renderista tai paikallisesti.
#
# 🔴 EIVAT MYOSKAAN ENNEN KIERROKSEN DEADLINEA. Mitattu 15.8: yleisliigan 314
# standings palautti 0 rivia ja entryn picks vastasi "Not found" - valinnat
# eivat ole julkisia ennen deadlinea. Mitattu uudelleen 25.8 GW1:n jalkeen:
# molemmat vastaavat normaalisti.
OVERALL_LEAGUE_ID = 314

# Standings-sivutus on raskaampi kuin element-summary (isompi vastaus, ja
# haemme naita satoja), joten tahti on hitaampi kuin SUMMARY_DELAY_S.
STANDINGS_DELAY_S = 0.35
PICKS_DELAY_S = 0.25


def fetch_league_standings(page: int, league_id: int = OVERALL_LEAGUE_ID,
                           max_age_s: float = 12 * 3600,
                           force: bool = False) -> dict:
    """Yksi sivu klassisen liigan standingsia (50 riviä/sivu).

    Valimuisti on TTL-pohjainen eika ikuinen: sijoitukset muuttuvat joka
    kierroksella, joten jaadytetty sivu antaisi vaaran otoksen seuraavalla
    kierroksella.
    """
    path = _cache_path(f"standings/{league_id}-p{page}.json")
    if not force:
        cached = _read_cache(path, max_age_s)
        if cached is not None:
            return cached
    url = (f"{FPL_BASE}/leagues-classic/{league_id}/standings/"
           f"?page_standings={page}")
    data = _get_json(url)
    _write_cache(path, data)
    time.sleep(STANDINGS_DELAY_S)
    return data


def fetch_entry_picks(entry_id: int, gw: int, force: bool = False) -> dict | None:
    """Yhden entryn valinnat yhdelle kierrokselle.

    Valimuisti on IKUINEN (max_age_s=None): pelatun kierroksen valinnat eivat
    enaa muutu. Tama on koko haun kannattavuuden ehto - ilman sita jokainen
    ajo maksaisi tuhansia pyyntoja uudelleen.

    Palauttaa None jos entrylla ei ole rivia talle kierrokselle (404). Se ei
    ole virhe: manageri on voinut liittya myohemmin. 🔴 None EI ole sama kuin
    "ei valintoja" - kutsuja ei saa laskea sita nollaksi vaan jattaa otoksesta.
    """
    path = _cache_path(f"picks/{gw}/{entry_id}.json")
    if not force:
        cached = _read_cache(path, None)
        if cached is not None:
            return cached
    url = f"{FPL_BASE}/entry/{entry_id}/event/{gw}/picks/"
    try:
        data = _get_json(url)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        raise
    _write_cache(path, data)
    time.sleep(PICKS_DELAY_S)
    return data


def fetch_entry_history(entry_id: int, max_age_s: float = 600,
                        force: bool = False) -> dict:
    """Entryn kausihistoria: pisteet, penkkipisteet ja siirtokustannus per GW.

    TTL on lyhyt eika ikuinen: kesken kierroksen `points` elaa, ja bonukset
    voivat viela liikuttaa jo pelattuakin kierrosta kunnes FPL merkitsee sen
    `data_checked`:iksi.
    """
    path = _cache_path(f"entry-history/{entry_id}.json")
    if not force:
        cached = _read_cache(path, max_age_s)
        if cached is not None:
            return cached
    data = _get_json(f"{FPL_BASE}/entry/{entry_id}/history/")
    _write_cache(path, data)
    return data


def fetch_event_live(gw: int, max_age_s: float = 600,
                     force: bool = False) -> dict:
    """Kierroksen live-pistedata per pelaaja (event/{gw}/live/).

    Sama TTL-perustelu kuin entry-historialla: luku ei ole lukossa ennen
    `data_checked`:ia, joten ikuinen valimuisti jaadyttaisi provisionaalisen
    arvon lopulliseksi.
    """
    path = _cache_path(f"event-live/{gw}.json")
    if not force:
        cached = _read_cache(path, max_age_s)
        if cached is not None:
            return cached
    data = _get_json(f"{FPL_BASE}/event/{gw}/live/")
    _write_cache(path, data)
    return data


def fetch_entry_transfers(entry_id: int, force: bool = False) -> list | None:
    """Entryn KAIKKI siirrot kauden alusta (entry/{id}/transfers/).

    🔴 TYHJA LISTA ON DATAA, EI PUUTTUVAA TIETOA. Manageri joka ei tehnyt
    yhtaan siirtoa palauttaa `[]`, ja se on merkityksellinen havainto (hold on
    myos valinta). Vain 404 tarkoittaa "ei rivia" -> None. Kutsuja ei saa
    kohdella naita samoin: `[]` kuuluu otokseen, `None` ei.

    Valimuisti on TTL-pohjainen eika ikuinen: lista KASVAA kauden mittaan, ja
    jaadytetty kopio jattaisi uusimmat siirrot nakymatta.
    """
    path = _cache_path(f"transfers/{entry_id}.json")
    if not force:
        cached = _read_cache(path, 900)
        if cached is not None:
            return cached
    try:
        data = _get_json(f"{FPL_BASE}/entry/{entry_id}/transfers/")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        raise
    _write_cache(path, data)
    time.sleep(PICKS_DELAY_S)
    return data
