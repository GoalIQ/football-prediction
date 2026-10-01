"""Kausi bootstrapista: yksi lukija sille, mita kautta FPL juuri nyt tarjoilee.

DATAPOHJA-JATKOT kohta 2 (1.10.2026). `scripts/build_fpl_xp.py` lukee
edellisen kauden kausisummat jaadytetysta arkistosta, jonka polku on
kovakoodattu (`fpl_prev_baselines_2526.json`), ja kirjoittaa payloadiin
kovakoodatun `SEASON_LABEL`in ("2026/27"). Kun FPL kaantyy kaudelle 2027/28,
molemmat jatkaisivat hiljaa: kortin "last season" ja `minutes_reason`
osoittaisivat 25/26:een vaikka edellinen kausi on 26/27. Tama moduuli tekee
vaarasta vaihtoehdosta kovaaanisen: builder kaatuu ja kertoo mita jaadyttaa.

Kausi paatellaan ensimmaisen kierroksen deadlinesta (kauden GW1 on elokuussa,
joten heinakuusta eteenpain alkava vuosi Y tarkoittaa kautta Y/Y+1). Kenttaa
`season` bootstrapissa ei ole, ja kalenterivuosi ei kelpaa: tammi-toukokuussa
kausi on alkanut edellisena vuonna.
"""
from __future__ import annotations

import json
from pathlib import Path


class SeasonMismatch(RuntimeError):
    """Jaadytetty arkisto tai kovakoodattu kausi ei vastaa bootstrapia."""


def season_start_year(boot: dict) -> int:
    events = [e for e in (boot.get("events") or []) if e.get("deadline_time")]
    if not events:
        raise SeasonMismatch("bootstrapissa ei ole kierroksia joilla on deadline")
    first = min(events, key=lambda e: e.get("id", 0))
    dl = str(first["deadline_time"])
    year, month = int(dl[:4]), int(dl[5:7])
    return year if month >= 7 else year - 1


def season_label(boot: dict) -> str:
    """Esim. "2026/27"."""
    y = season_start_year(boot)
    return f"{y}/{(y + 1) % 100:02d}"


def prev_season_key(boot: dict) -> str:
    """Bootstrapin kautta EDELTAVA kausi arkiston avainmuodossa, esim. "2526"."""
    y = season_start_year(boot)
    return f"{(y - 1) % 100:02d}{y % 100:02d}"


def check_season_label(label: str, boot: dict) -> None:
    want = season_label(boot)
    if label != want:
        raise SeasonMismatch(
            f"SEASON_LABEL on {label!r}, mutta FPL:n bootstrap on kaudella {want!r}. "
            "Paivita scripts/build_fpl_phase0.py:n SEASON_LABEL kauden vaihtuessa.")


def load_prev_archive(path: Path, boot: dict) -> dict:
    """Edellisen kauden jaadytetty arkisto, VAIN jos se on oikeasti edellinen kausi.

    Puuttuva tai rikkinainen tiedosto -> tyhja arkisto kuten ennenkin (kortti
    nayttaa silloin 'no history' eika keksi lukuja). Vaaran kauden arkisto ->
    SeasonMismatch: hiljainen vanha data on pahempi kuin kaatunut ajo, koska
    'last season' -luvut nayttaisivat oikeilta."""
    try:
        arch = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"players": {}, "meta": {}}
    want = prev_season_key(boot)
    got = (arch.get("meta") or {}).get("season_key")
    if got != want:
        raise SeasonMismatch(
            f"{Path(path).name}: arkiston season_key on {got!r}, mutta bootstrapin "
            f"edellinen kausi on {want!r}. Jaadyta uusi arkisto "
            "(python -m scripts.build_fpl_prev_baselines) ja paivita "
            "PREV_BASELINES_PATH ennen xP-ajoa.")
    return arch
