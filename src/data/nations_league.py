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

Otteluita ja sarjataulukkoa EI ole 3.10.2026 alkaen. Ne haettiin UEFAn
rajapinnasta (match.uefa.com / standings.uefa.com); haku lopetettiin Villen
paatoksella.
UNL ei ole football-data.orgin ilmaistasolla, joten korvaavaa lahdetta ei ole.
Ennustemalli (martj42, CC0) jaa. Portti: tests/test_no_uefa_fetch.py.

Saanto 6a: mika vaihtuu alla -> kausi (seasonYear johdetaan
config.current_season():sta, ei kovakoodata), joukkuenimet (kanonisoidaan
YHDESSA lukijassa `resolve_unl_name`).
"""
from __future__ import annotations

import unicodedata
from functools import lru_cache

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


def display_data(start: str):
    """H2H, vire ja joukkuekortti: KAIKKI maaottelut ikkunassa. Mallin
    treenidata ("any") jattaa pois pienten maiden keskinaiset ottelut, jolloin
    esim. Andorra-Malta-H2H olisi tyhja ja viimeiset viisi ottelua vaarat."""
    return lataa(window_start=start, include="all")


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
# Ottelut ja sarjataulukko: ei lahdetta (UEFA-haku lopetettu 3.10.2026)
# ---------------------------------------------------------------------------
# Reitit vastaavat 200 + tyhja lista, jolloin klientit nayttavat oman
# tyhjatilansa ("No Nations League matches scheduled", "Group tables are
# unavailable"). 503 olisi nayttanyt verkkovirheelta.


def cached_matches() -> list | None:
    """Ei otteluita valimuistissa: /api/fixtures/by-date jattaa UNL:n pois."""
    return None


def unl_fixtures(days: int, now=None) -> tuple[list[dict], bool]:
    return [], False


def unl_standings() -> tuple[list[dict], bool]:
    return [], False
