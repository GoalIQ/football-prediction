"""UEFA Nations League 2026/27 (Villen GO 23.9.2026, jonorivi WC-PREDICT-POIS-TAI-UNL).

World Cup 2026 paattyi 19.7 ja poistui mobiilista. Sama maajoukkuemalli
(martj42 international_results, Dixon-Coles) ennustaa nyt UNL:n, mutta omana
esirakennettuna mallinaan `data/unl_model.json`:

  * Treeni = ottelut joissa ainakin toinen on WC 2026 -maa (include="any"),
    4,5 vuoden ikkuna, decay 0, bayes 1. Takatesti UNL 2022/23 + 2024/25
    (cos-reports/cc-reports/2026-09-23-unl.md), kriteeri log lossin keskiarvo
    kahdella kaudella: any 0,955 vs kaikki maaottelut 0,967 (all voitti vain
    2024/25:n). Pienet maat (Andorra, San Marino) saavat vahvuutensa otteluista
    WC-maita vastaan; kaikki 54 ovat mallissa. Elo-prioria EI kayteta, koska
    nykyinen Elo-taulukko vuotaisi takatestissa tulevaa eika sita voitu mitata.
  * UNL:n sarjavaihe pelataan KOTI- JA VIERASOTTELUINA, joten kotietu
    SAILYY (WC neutraloi sen, koska kisat olivat neutraalilla maalla).

Ottelut ja sarjataulukko tulevat UEFAn omasta julkisesta rajapinnasta
(match.uefa.com / standings.uefa.com, sama taho kuin UCL-syote), ei
football-data.orgista (UNL ei ole sen ilmaistasolla).

Saanto 6a: mika vaihtuu alla -> kausi (seasonYear johdetaan
config.current_season():sta, ei kovakoodata), joukkuenimet (UEFAn nimet
kanonisoidaan YHDESSA lukijassa `resolve_unl_name`), rajapinnan saatavuus
(TTL-cache + vanha vastaus varalle, virhe ei kaada endpointia hiljaa).
"""
from __future__ import annotations

import threading
import time
import unicodedata
from functools import lru_cache

import requests

import config
from src.data.international_results import (
    COMPETITION_WEIGHTS, DEFAULT_COMPETITION_WEIGHT, lataa,
)
from src.data.wc_teams import resolve_wc_name

UNL_LEAGUE = "INT-Nations League"
UNL_COMPETITION_ID = 2014
"""UEFAn competitionId (mitattu 23.9: match.uefa.com, 'UEFA Nations League')."""

UNL_MODEL_PATH = config.DATA_DIR / "unl_model.json"

# Takatestin valitsemat (ks. moduulin docstring). Ikkuna vuosina ennen
# rakennushetkea, jotta malli ei vanhene kiinteaan paivamaaraan.
UNL_WINDOW_YEARS: float = 4.5
UNL_FIT_DECAY: float = 0.0
UNL_FIT_BAYES: float = 1.0
UNL_INCLUDE = "any"

# 54 osallistujaa 2026/27 mallin avaimina (mitattu UEFAn rajapinnasta 23.9;
# Venaja ei ole mukana). UEFAn nimet -> nama: `resolve_unl_name`.
UNL_TEAMS: tuple[str, ...] = (
    "Albania", "Andorra", "Armenia", "Austria", "Azerbaijan", "Belarus",
    "Belgium", "Bosnia-Herzegovina", "Bulgaria", "Croatia", "Cyprus", "Czechia",
    "Denmark", "England", "Estonia", "Faroe Islands", "Finland", "France",
    "Georgia", "Germany", "Gibraltar", "Greece", "Hungary", "Iceland", "Israel",
    "Italy", "Kazakhstan", "Kosovo", "Latvia", "Liechtenstein", "Lithuania",
    "Luxembourg", "Malta", "Moldova", "Montenegro", "Netherlands",
    "North Macedonia", "Northern Ireland", "Norway", "Poland", "Portugal",
    "Republic of Ireland", "Romania", "San Marino", "Scotland", "Serbia",
    "Slovakia", "Slovenia", "Spain", "Sweden", "Switzerland", "Turkey",
    "Ukraine", "Wales",
)
UNL_TEAMS_SET = frozenset(UNL_TEAMS)

_ALIASES = {
    "turkiye": "Turkey",
    "turkey": "Turkey",
    "bosnia and herzegovina": "Bosnia-Herzegovina",
    "bosnia & herzegovina": "Bosnia-Herzegovina",
    "czech republic": "Czechia",
    "ireland": "Republic of Ireland",
    "republic of ireland": "Republic of Ireland",
    "macedonia": "North Macedonia",
    "fyr macedonia": "North Macedonia",
    "faroe islands": "Faroe Islands",
    "faroes": "Faroe Islands",
}


def _fold(name: str) -> str:
    """Casefold + diakriitit pois ('Türki̇ye' -> 'turkiye', myos U+0307)."""
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.casefold().split())


_BY_FOLD = {_fold(t): t for t in UNL_TEAMS}


def resolve_unl_name(name: str | None) -> str | None:
    """Mika tahansa UNL-maan nimi -> mallin avain, tai None jos ei UNL-maa."""
    if not name:
        return None
    f = _fold(name)
    if f in _BY_FOLD:
        return _BY_FOLD[f]
    if f in _ALIASES:
        return _ALIASES[f]
    wc = resolve_wc_name(name)
    return wc if wc in UNL_TEAMS_SET else None


def unl_season_year() -> int:
    """UEFAn seasonYear = kauden paattymisvuosi ('2627' -> 2027)."""
    kausi = config.current_season()
    return 2000 + int(str(kausi)[2:])


# ---------------------------------------------------------------------------
# Malli
# ---------------------------------------------------------------------------
def window_start(now=None) -> str:
    import datetime as dt
    now = now or dt.datetime.now(dt.timezone.utc)
    return (now - dt.timedelta(days=int(UNL_WINDOW_YEARS * 365))).date().isoformat()


def training_data(start: str):
    """Treenidata ikkunassa (UNL_INCLUDE, ks. moduulin docstring)."""
    return lataa(window_start=start, include=UNL_INCLUDE)


def fit_unl_model(start: str):
    from src.models.dixon_coles import DixonColesModel
    df = training_data(start)
    dc = DixonColesModel(per_team_home_adv=False).fit(
        df, decay=UNL_FIT_DECAY, date_col="date", l2_attack_defence=UNL_FIT_BAYES,
        shrink_defence_to_mean=True, competition_col="tournament",
        competition_weights=COMPETITION_WEIGHTS,
        default_competition_weight=DEFAULT_COMPETITION_WEIGHT,
    )
    return dc, df


def save_unl_model(dc, meta: dict) -> None:
    import json
    payload = {
        "meta": meta,
        "attack": dc.attack,
        "defence": dc.defence,
        "home_advantage": dc.home_advantage,
        "home_advantage_per_team": dc.home_advantage_per_team,
        "rho": dc.rho,
        "teams_": list(dc.teams_),
        "per_team_home_adv": dc.per_team_home_adv,
        "model_type_": getattr(dc, "model_type_", "dc"),
    }
    with open(UNL_MODEL_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)


@lru_cache(maxsize=1)
def load_unl_model():
    """Esirakennettu UNL-malli (ei fittia ajossa, Render Starter ei jaksa)."""
    import json
    from src.models.dixon_coles import DixonColesModel
    with open(UNL_MODEL_PATH, encoding="utf-8") as f:
        d = json.load(f)
    return DixonColesModel(
        attack=d["attack"], defence=d["defence"],
        home_advantage=d["home_advantage"],
        home_advantage_per_team=d["home_advantage_per_team"],
        rho=d["rho"], teams_=d["teams_"],
        per_team_home_adv=d.get("per_team_home_adv", False),
        model_type_=d.get("model_type_", "dc"),
    )


@lru_cache(maxsize=1)
def unl_model_meta() -> dict:
    import json
    with open(UNL_MODEL_PATH, encoding="utf-8") as f:
        return json.load(f).get("meta") or {}


# ---------------------------------------------------------------------------
# UEFAn rajapinta: ottelut ja sarjataulukko
# ---------------------------------------------------------------------------
_HEADERS = {"User-Agent": "curl/8.4.0", "Accept": "application/json"}
_TTL_SEC = 30 * 60
_cache: dict[str, tuple[float, object]] = {}
_lock = threading.Lock()


def _get_cached(key: str, url: str, params: dict) -> tuple[object, bool]:
    """(data, stale). Tuore haku TTL:n jalkeen; virheessa vanha vastaus
    stale-lipulla. Ilman vanhaa vastausta virhe nousee kutsujalle."""
    now = time.time()
    with _lock:
        hit = _cache.get(key)
    if hit and now - hit[0] < _TTL_SEC:
        return hit[1], False
    try:
        r = requests.get(url, params=params, headers=_HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception:
        if hit:
            return hit[1], True
        raise
    with _lock:
        _cache[key] = (now, data)
    return data, False


def _team(t: dict) -> str | None:
    tr = (t or {}).get("translations") or {}
    for n in (t.get("internationalName") if t else None,
              ((tr.get("displayName") or {}).get("EN")),
              ((tr.get("displayOfficialName") or {}).get("EN"))):
        r = resolve_unl_name(n)
        if r:
            return r
    return None


def _matchday(md) -> int | None:
    """UEFA: {'sequenceNumber': '1', ...} (merkkijono, mitattu 23.9)."""
    v = md.get("sequenceNumber") if isinstance(md, dict) else md
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def fixtures_from_matches(raw: list, date_from, date_to) -> list[dict]:
    """UEFAn ottelurivit -> /api/fixtures-muoto. Vain pelaamattomat,
    [date_from, date_to]-ikkunassa, joukkuenimet mallin avaimina (Predict-
    esitaytto osuu suoraan). Puhdas funktio: testataan synteettisilla riveilla."""
    out = []
    for m in raw or []:
        if m.get("status") == "FINISHED":
            continue
        ko = m.get("kickOffTime") or {}
        dt_s = ko.get("dateTime") or ""
        d = (ko.get("date") or dt_s[:10])
        if not d or not (date_from.isoformat() <= d <= date_to.isoformat()):
            continue
        h, a = _team(m.get("homeTeam") or {}), _team(m.get("awayTeam") or {})
        if not h or not a:
            continue
        out.append({
            "date": d,
            "datetime": dt_s or None,
            "home_team": h,
            "away_team": a,
            "home_team_short_name": (m.get("homeTeam") or {}).get("teamCode"),
            "away_team_short_name": (m.get("awayTeam") or {}).get("teamCode"),
            "matchday": _matchday(m.get("matchday")),
        })
    out.sort(key=lambda f: f["datetime"] or f["date"])
    return out


def unl_fixtures(days: int, now=None) -> tuple[list[dict], bool]:
    import datetime as dt
    now = now or dt.datetime.now(dt.timezone.utc)
    year = unl_season_year()
    raw, stale = _get_cached(
        f"unl-matches:{year}", "https://match.uefa.com/v5/matches",
        {"competitionId": UNL_COMPETITION_ID, "seasonYear": year,
         "limit": 500, "offset": 0, "order": "ASC"})
    today = now.date()
    return fixtures_from_matches(raw, today, today + dt.timedelta(days=days)), stale


def groups_from_standings(raw: list) -> list[dict]:
    """UEFAn standings -> /api/standings turnausmuoto {group, rows}. Rivin
    avaimet samat kuin football-data-polun `_fd_standings_row` + form."""
    groups = []
    for g in raw or []:
        name = ((g.get("group") or {}).get("metaData") or {}).get("groupName")
        rows = []
        for it in sorted(g.get("items") or [], key=lambda x: x.get("rank") or 99):
            team = _team(it.get("team") or {})
            if not team:
                continue
            rows.append({
                "position": it.get("rank"),
                "team_name": team,
                "team_short_name": (it.get("team") or {}).get("teamCode"),
                "team_crest": None,
                "played_games": it.get("played", 0),
                "won": it.get("won", 0),
                "draw": it.get("drawn", 0),
                "lost": it.get("lost", 0),
                "goals_for": it.get("goalsFor", 0),
                "goals_against": it.get("goalsAgainst", 0),
                "goal_difference": it.get("goalDifference", 0),
                "points": it.get("points", 0),
                "form": None,
            })
        if name and rows:
            groups.append({"group": name, "rows": rows})
    return groups


def unl_standings() -> tuple[list[dict], bool]:
    year = unl_season_year()
    raw, stale = _get_cached(
        f"unl-standings:{year}", "https://standings.uefa.com/v1/standings",
        {"competitionId": UNL_COMPETITION_ID, "seasonYear": year})
    return groups_from_standings(raw), stale
