# -*- coding: utf-8 -*-
"""Esirakennettu UEFA-yhteismalli levylla - kylmafitin 211 s poistuu.

MIKSI (9.9.2026). UEFA-yhteisfitti lataa 9 kotiliigaa ja fittaa ~190 seuraa.
Paikallisesti 17 s, Renderin Starter-CPU:lla ja verkkolatauksin mitattu
161 s (502), 171 s (200) ja 8.9 211 s. Warmup ei auta: CL on warmup-listan
kuudes, joten uudelleenkaynnistyksen jalkeen ensimmainen CL-pyynto odottaa
viiden kotiliigan fitin JA oman fittinsa. Tanaan se katkaisi accuracy-login
kahdesti (120 s timeout x 3 yritysta) ja CL jai track recordista.

RATKAISU ON SAMA KUIN WC-MALLILLA (`data/wc_model.json`, #79): CI fittaa
mallin ja committaa TAITETUN DixonColesModelin JSONina; API lataa sen
millisekunneissa ja fittaa livena vain jos artefakti puuttuu, on vaaralle
kaudelle, vaaralla decaylla tai liian vanha. Taitettu malli on tasan se
olio jonka `_fit_uefa_yhteismalli` palauttaa, joten alavirta ei tieda
kumpaa polkua kuljettiin.

🔴 TUOREUSEHTO ON LUKIJASSA, EI KIRJOITTAJASSA. Jos ucl-refresh lakkaa
ajamasta, artefakti vanhenee levylla eika kukaan huomaa - siksi lukija
mittaa ian ja palaa live-fittiin (hidas mutta oikea). Sama ehto molemmilla
puolilla: `is_fresh()` on ainoa paikka jossa saanto on.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import config
from src.models.dixon_coles import DixonColesModel

PATH = config.DATA_DIR / "uefa_joint_model.json"

# ucl-refresh ajaa 6 h valein. 26 h sallii yhden epaonnistuneen vuorokauden
# (esim. football-data.co.uk 503, 8.9) ennen kuin palataan live-fittiin.
MAX_AGE_H = 26.0
FORMAT_VERSION = 1

# 🔴 9.9.2026, ensimmainen CI-bake: 36 seuraa, paikallisesti 121. Runnerilla
# ei ollut football-data.orgin avainta, kotiliigat latautuivat tyhjina, eika
# yksikaan liiga kalibroitunut -> artefakti oli pelkka turnausjoukko ILMAN
# siltaa, ja se committoitiin. Tuore ja oikean kauden artefakti voi silti
# olla vaara. Siksi kelpoisuus mitataan SISALLOSTA: vahintaan yksi
# kalibroitunut liiga (silta on koko mallin idea) ja seuramaara jota pelkka
# turnausjoukko (36) ei voi saavuttaa. 8.9 mitattu: 121 seuraa, 5 liigaa.
MIN_CLUBS = 80


def validate(dc: DixonColesModel, calibrated_leagues: list[str]) -> tuple[bool, str]:
    """(kelpaa, syy) - sama saanto bakelle (ei kirjoiteta) ja lukijalle (ei ladata)."""
    if not calibrated_leagues:
        return False, "ei yhtaan kalibroitunutta liigaa - pelkka turnausjoukko ilman siltaa"
    n = len(getattr(dc, "attack", {}) or {})
    if n < MIN_CLUBS:
        return False, f"vain {n} seuraa (< {MIN_CLUBS}) - kotiliigat puuttuvat"
    return True, f"{n} seuraa, {len(calibrated_leagues)} kalibroitunutta liigaa"


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def save(dc: DixonColesModel, *, tournament: str, season_pair: list[str],
         decay: float, calibrated_leagues: list[str],
         extra: dict | None = None, path: Path | None = None,
         now: _dt.datetime | None = None) -> dict:
    """Sarjallista taitettu malli. Palauttaa metan (testeille ja lokille).

    Kieltaytyy (ValueError) jos malli ei lapaise `validate`a: ohutta
    artefaktia ei kirjoiteta levylle edes valiaikaisesti.
    """
    ok, syy = validate(dc, calibrated_leagues)
    if not ok:
        raise ValueError(f"artefaktia ei kirjoiteta: {syy}")
    meta = {
        "calibrated_leagues": sorted(calibrated_leagues),
        "format_version": FORMAT_VERSION,
        "built_at": (now or _now()).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tournament": tournament,
        "season_pair": list(season_pair),
        "decay": round(float(decay), 4),
        "n_clubs": len(dc.attack),
        **(extra or {}),
    }
    payload = {
        "meta": meta,
        "attack": dc.attack,
        "defence": dc.defence,
        "home_advantage": dc.home_advantage,
        "home_advantage_per_team": dc.home_advantage_per_team,
        "rho": dc.rho,
        "teams_": list(dc.teams_),
        "per_team_home_adv": getattr(dc, "per_team_home_adv", False),
        "model_type_": getattr(dc, "model_type_", "dc"),
    }
    (path or PATH).write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    return meta


def is_fresh(meta: dict, *, tournament: str, season_pair: list[str],
             decay: float, now: _dt.datetime | None = None) -> tuple[bool, str]:
    """(kelpaa, syy). Syy on lokia varten: hiljainen fallback jaisi nakymatta."""
    if meta.get("format_version") != FORMAT_VERSION:
        return False, f"format_version {meta.get('format_version')} != {FORMAT_VERSION}"
    if meta.get("tournament") != tournament:
        return False, f"tournament {meta.get('tournament')!r} != {tournament!r}"
    if list(meta.get("season_pair") or []) != list(season_pair):
        return False, f"season_pair {meta.get('season_pair')} != {list(season_pair)}"
    if round(float(meta.get("decay", -1)), 4) != round(float(decay), 4):
        return False, f"decay {meta.get('decay')} != {round(float(decay), 4)}"
    try:
        built = _dt.datetime.strptime(meta["built_at"], "%Y-%m-%dT%H:%M:%SZ") \
            .replace(tzinfo=_dt.timezone.utc)
    except (KeyError, ValueError):
        return False, "built_at puuttuu tai on rikki"
    ika_h = ((now or _now()) - built).total_seconds() / 3600.0
    if ika_h > MAX_AGE_H:
        return False, f"ika {ika_h:.1f} h > {MAX_AGE_H} h"
    if ika_h < -1.0:
        return False, f"built_at on tulevaisuudessa ({ika_h:.1f} h)"
    return True, f"ika {ika_h:.1f} h"


def load(*, tournament: str, season_pair: list[str], decay: float,
         path: Path | None = None,
         now: _dt.datetime | None = None) -> tuple[DixonColesModel | None, str]:
    """(malli tai None, syy). None = fittaa livena."""
    p = path or PATH
    if not p.exists():
        return None, "artefaktia ei ole"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"artefakti ei aukea: {type(e).__name__}"
    meta = d.get("meta") or {}
    ok, syy = is_fresh(meta, tournament=tournament, season_pair=season_pair,
                       decay=decay, now=now)
    if not ok:
        return None, syy
    if not d.get("attack"):
        return None, "artefaktissa ei ole yhtaan seuraa"
    class _Kuori:  # validate lukee vain .attack
        attack = d.get("attack") or {}
    ok, syy2 = validate(_Kuori(), list(meta.get("calibrated_leagues") or []))
    if not ok:
        return None, syy2
    dc = DixonColesModel(
        attack=d["attack"],
        defence=d["defence"],
        home_advantage=d["home_advantage"],
        home_advantage_per_team=d["home_advantage_per_team"],
        rho=d["rho"],
        teams_=d["teams_"],
        per_team_home_adv=d.get("per_team_home_adv", False),
        model_type_=d.get("model_type_", "dc"),
    )
    return dc, syy
