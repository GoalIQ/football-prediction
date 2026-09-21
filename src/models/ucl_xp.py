# -*- coding: utf-8 -*-
"""UCL Fantasy xP (expected points) - puhtaat funktiot.

Sama periaate kuin src/models/fpl_xp.py: takatesti ja tuotanto kutsuvat
TASMALLEEN samaa kaavaa. Kolme kerrosta:

  1. Joukkue: maaliodotus, nollapeli ja paastettyjen jakauma ottelulle
     CL-yhteismallista (data/uefa_joint_model.json, 36 seuraa samalla
     asteikolla). Tama oli se mika puuttui ennen 21.9:aa.
  2. Pelaaja: OSUUS oman joukkueen maaleista ja syotoista per 90 min
     (kotiliigasta, Understat) ja odotetut minuutit. Osuus on
     kilpailutasosta riippumaton: jos Lautaro tekee 30 % Interin xG:sta
     Serie A:ssa, hanelle kuuluu ~30 % Interin maaliodotuksesta myos
     CL-ottelussa. Kotiliigan taso ei vaaristaa osuutta.
  3. Pisteet: UCL Fantasyn saannot, JOHDETTU syotteen omista pisteista
     (ks. SAANNOT) eika muistista.

Seurat joilla ei ole Understat-dataa (Porto, PSV, Sabah ...): osuus ja
minuutit UEFA-otteluista (maalintekijat + avauskokoonpanot), kutistettuna
pelipaikan prioriin. Niiden rivit merkitaan `data_basis`-kentalla, jotta
pinta ei esita ohutta arviota samalla varmuudella.
"""
from __future__ import annotations

import math

import numpy as np

POS = ("GK", "DEF", "MID", "FWD")

# ---------------------------------------------------------------------------
# Saannot. JOHDETTU 21.9.2026 UEFAn syotteesta (players_90_en_2.json, MD1):
# kokonaislukukertoimet selittivat kaikkien 557 pelanneen pelaajan pisteet
# TASMALLEEN (GK 38/38, DEF 186/186, MID 252/252, FWD 81/81).
# `tarkista_saannot` ajaa saman tarkistuksen jokaisella buildilla: jos UEFA
# muuttaa saantoja, build kaatuu eika julkaise vanhoilla saannoilla laskettua.
# Kertoimet joita MD1 ei havainnut (esim. GK:n maali) ovat None - niita ei
# kayteta ennusteessa ennen kuin data on nahnyt ne.
# ---------------------------------------------------------------------------
SAANNOT: dict[str, dict[str, float | None]] = {
    "GK":  {"app1": 1, "app2": 2, "maali": None, "syotto": None, "cs": 4, "gc2": -1,
            "keltainen": -1, "punainen": None, "torjunta3": 1, "riisto3": None,
            "kaukaa": None, "mom": None, "rp_ansaittu": None, "rp_aiheutettu": None,
            "oma_maali": None},
    "DEF": {"app1": 1, "app2": 2, "maali": 6, "syotto": 3, "cs": 4, "gc2": -1,
            "keltainen": -1, "punainen": -3, "torjunta3": None, "riisto3": 1,
            "kaukaa": 1, "mom": 3, "rp_ansaittu": None, "rp_aiheutettu": -1,
            "oma_maali": -2},
    "MID": {"app1": 1, "app2": 2, "maali": 5, "syotto": 3, "cs": 1, "gc2": None,
            "keltainen": -1, "punainen": -3, "torjunta3": None, "riisto3": 1,
            "kaukaa": 1, "mom": 3, "rp_ansaittu": None, "rp_aiheutettu": None,
            "oma_maali": None},
    "FWD": {"app1": 1, "app2": 2, "maali": 4, "syotto": 3, "cs": None, "gc2": None,
            "keltainen": -1, "punainen": None, "torjunta3": None, "riisto3": 1,
            "kaukaa": 1, "mom": 3, "rp_ansaittu": 2, "rp_aiheutettu": None,
            "oma_maali": -2},
}
SKILL = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


def _s(pos: str, k: str) -> float:
    v = SAANNOT[pos].get(k)
    return 0.0 if v is None else float(v)


def pisteet_tilastoista(pos: str, p: dict) -> float:
    """Syotteen pelaajarivin pisteet saannoilla (tarkistusta varten)."""
    m = p.get("minsPlyd") or 0
    if not m:
        return 0.0
    return (
        (_s(pos, "app2") if m >= 60 else _s(pos, "app1"))
        + _s(pos, "maali") * p.get("gS", 0) + _s(pos, "syotto") * p.get("assist", 0)
        + _s(pos, "cs") * p.get("cS", 0) + _s(pos, "gc2") * (p.get("gC", 0) // 2)
        + _s(pos, "keltainen") * p.get("yC", 0) + _s(pos, "punainen") * p.get("rC", 0)
        + _s(pos, "torjunta3") * (p.get("saves", 0) // 3)
        + _s(pos, "riisto3") * (p.get("bR", 0) // 3)
        + _s(pos, "kaukaa") * p.get("gOB", 0) + _s(pos, "mom") * p.get("mOM", 0)
        + _s(pos, "rp_ansaittu") * p.get("pE", 0) + _s(pos, "rp_aiheutettu") * p.get("pC", 0)
        + _s(pos, "oma_maali") * p.get("oG", 0)
    )


def tarkista_saannot(pelaajat: list[dict]) -> tuple[int, int, list[str]]:
    """(selitetyt, pelanneet, esimerkit selittamattomista). Ks. SAANNOT."""
    ok, n, huonot = 0, 0, []
    for p in pelaajat:
        if not p.get("minsPlyd"):
            continue
        pos = SKILL.get(p.get("skill"))
        if pos is None:
            continue
        n += 1
        if abs(pisteet_tilastoista(pos, p) - float(p.get("totPts", 0))) < 1e-9:
            ok += 1
        elif len(huonot) < 5:
            huonot.append(f"{p.get('pDName')} {pos}: syote {p.get('totPts')} "
                          f"vs saannot {pisteet_tilastoista(pos, p)}")
    return ok, n, huonot


# ---------------------------------------------------------------------------
# Joukkuekerros
# ---------------------------------------------------------------------------

def joukkue_odotus(dc, koti: str, vieras: str) -> dict:
    """Ottelun maalijakauma CL-mallista. Palauttaa kummallekin puolelle
    maaliodotuksen, nollapelin todennakoisyyden ja E[floor(paastetyt/2)]."""
    lam, mu = dc.expected_goals(koti, vieras)
    rho = max(getattr(dc, "rho", 0.0) or 0.0, -0.9)
    M = dc._bp_score_matrix(lam, mu, rho, 10)
    M = M / M.sum()
    koti_maalit = M.sum(axis=1)   # P(koti tekee i)
    vieras_maalit = M.sum(axis=0)
    k = np.arange(len(koti_maalit))
    return {
        koti: {"xg": float(lam), "xga": float(mu), "cs": float(vieras_maalit[0]),
               "gc2": float((vieras_maalit * (k // 2)).sum()), "koti": True},
        vieras: {"xg": float(mu), "xga": float(lam), "cs": float(koti_maalit[0]),
                 "gc2": float((koti_maalit * (k // 2)).sum()), "koti": False},
    }


def _poisson_floor3(m: float) -> float:
    """E[floor(S/3)] kun S ~ Poisson(m)."""
    if m <= 0:
        return 0.0
    tot, p = 0.0, math.exp(-m)
    for s in range(0, 40):
        if s > 0:
            p *= m / s
        tot += p * (s // 3)
    return tot


# ---------------------------------------------------------------------------
# Pelaajakerros
# ---------------------------------------------------------------------------

M_PRIOR_OSUUS = 450.0
"""Minuuttipaino jolla pelaajan osuus kutistuu pelipaikan prioriin. Sama
kuin FPL:n M_PRIOR_ATTACK (fpl_xp.py) - ei viritetty UCL:lle."""
EDELLINEN_KAUSI_PAINO = 0.5
"""Edellisen kauden kertyman paino. Sama kuin FPL:n PREV_SEASON_CARRY."""


def shrink90(kertyma: float, minuutit: float, prior90: float, m: float = M_PRIOR_OSUUS) -> float:
    return 90.0 * (kertyma + prior90 / 90.0 * m) / (minuutit + m)


# Aloittajan ja vaihtajan minuutit seka P(60+ | aloitus): SAMAT vakiot kuin
# FPL-mallissa (fpl_xp.START_FALLBACK_MIN / SUB_FALLBACK_MIN /
# P60_GIVEN_START_FALLBACK), jotka on mitattu PL-datasta. EI sovitettu UCL:n
# MD1:een: 21.9 ensimmainen versio oletti etta vakiopelaaja pelaa 90 min,
# ja MD1:ssa osuusluokan 0,8-1,0 pelaajat pelasivat keskimaarin 65 min
# (ennuste 89). Syy on rakenteellinen (vaihdot, kierratys), ei MD1:n oma.
MIN_ALOITUS = 78.0
MIN_VAIHTO = 18.0
P60_ALOITUS = 0.85
P_ALOITUS_TUNTEMATON = 0.05
"""Pelaaja josta ei ole kotiliigan eika UEFA-otteluiden dataa: kaytannossa
reservi. Rakenteellinen, ei sovitettu."""
P_VAIHTO_TUNTEMATON = 0.10


def aloitukset_minuuteista(minuutit: float, esiintymiset: float) -> tuple[float, float]:
    """(aloitukset, vaihtoonnot) kertymista kun aloituksia ei ole erikseen:
    minuutit = aloitukset * MIN_ALOITUS + vaihdot * MIN_VAIHTO."""
    if esiintymiset <= 0:
        return 0.0, 0.0
    a = (minuutit - MIN_VAIHTO * esiintymiset) / (MIN_ALOITUS - MIN_VAIHTO)
    a = max(0.0, min(esiintymiset, a))
    return a, esiintymiset - a


ALOITTAJIA = 11.0
VAIHTOJA = 4.0
"""Keskimaarin kaytetyt vaihdot (UEFA sallii viisi). Rakenteellinen."""
KATTO_ALOITUS = 0.95
KATTO_VAIHTO = 0.6


def tayta(arvot: dict[str, float], tavoite: float, katto: float) -> dict[str, float]:
    """Skaalaa arvot niin etta summa = tavoite, yksittainen arvo <= katto
    (vesitaytto: katon saavuttaneet jaadytetaan ja loput skaalataan).

    Miksi: 21.9 MD1-takatestissa joukkueen aloitustodennakoisyydet
    summautuivat 6,2-11,7:aan, vaikka avauksessa on aina tasan 11. Vaje
    syntyy seuran jattaneiden pelaajien aloituksista ja datattomista
    uusista hankinnoista."""
    out = {k: max(0.0, v) for k, v in arvot.items()}
    for _ in range(50):
        vapaat = {k: v for k, v in out.items() if v < katto - 1e-12}
        lukitut = sum(v for k, v in out.items() if k not in vapaat)
        s = sum(vapaat.values())
        if s <= 0:
            break
        kerroin = (tavoite - lukitut) / s
        if kerroin <= 0:
            break
        uusi = {k: min(katto, v * kerroin) for k, v in vapaat.items()}
        muuttui = any(abs(uusi[k] - out[k]) > 1e-12 for k in uusi)
        out.update(uusi)
        if not muuttui or abs(sum(out.values()) - tavoite) < 1e-9:
            break
    return out


def minuuttiarvio(p_aloitus: float, p_vaihto: float, saatavuus: float) -> dict:
    """Odotetut minuutit ja esiintymistodennakoisyydet.

    `saatavuus` 0..1 (loukkaantunut 0, epavarma 0.5) skaalaa molemmat."""
    s = max(0.0, min(1.0, saatavuus))
    pa = max(0.0, min(1.0, p_aloitus)) * s
    pv = max(0.0, min(1.0 - pa, p_vaihto * s))
    return {"min": pa * MIN_ALOITUS + pv * MIN_VAIHTO, "p60": pa * P60_ALOITUS,
            "p1_59": pa * (1 - P60_ALOITUS) + pv, "p_aloitus": pa}


def xp_pelaajalle(pos: str, *, joukkue: dict, minuutit: dict, g90: float, a90: float,
                  yc90: float, riisto3_90: float, kaukaa_osuus: float,
                  torjunnat_per_paastetty: float, p_mom: float) -> dict:
    """Yhden pelaajan xP komponenteittain yhdelle ottelulle.

    g90/a90 = osuus joukkueen maaliodotuksesta per 90 min kentalla."""
    f = minuutit["min"] / 90.0
    e_maalit = joukkue["xg"] * g90 * f
    e_syotot = joukkue["xg"] * a90 * f
    komp = {
        "esiintyminen": minuutit["p60"] * _s(pos, "app2") + minuutit["p1_59"] * _s(pos, "app1"),
        "maalit": e_maalit * (_s(pos, "maali") + _s(pos, "kaukaa") * kaukaa_osuus),
        "syotot": e_syotot * _s(pos, "syotto"),
        "nollapeli": minuutit["p60"] * joukkue["cs"] * _s(pos, "cs"),
        "paastetyt": minuutit["p60"] * joukkue["gc2"] * _s(pos, "gc2"),
        "torjunnat": (minuutit["p60"] * _s(pos, "torjunta3")
                      * _poisson_floor3(torjunnat_per_paastetty * joukkue["xga"])),
        "riistot": f * riisto3_90 * _s(pos, "riisto3"),
        "kortit": f * yc90 * _s(pos, "keltainen"),
        "ottelun_pelaaja": p_mom * _s(pos, "mom"),
    }
    return {"xp": float(sum(komp.values())), "komponentit": komp,
            "e_maalit": e_maalit, "e_syotot": e_syotot}


def mom_todennakoisyydet(painot: dict[str, float]) -> dict[str, float]:
    """Ottelun pelaaja: tasan yksi per ottelu. Paino = odotettu maali- ja
    syottopanos + pieni minuuttipohja (rakenteellinen, ei sovitettu)."""
    s = sum(painot.values())
    return {k: (v / s if s > 0 else 0.0) for k, v in painot.items()}
