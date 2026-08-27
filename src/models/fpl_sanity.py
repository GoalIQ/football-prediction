# -*- coding: utf-8 -*-
"""Rakenteellinen sanity-gate CS%/FDR-artefakteille (27.8.2026).

MIKSI TAMA ON OLEMASSA. Molempien builderien (build_fpl_phase0,
build_fpl_cs_fdr) vanha portti oli esikauden sanalista: "kärki (MCI/ARS/LIV)
vs nousijat": nousijoiden FDR >= 3.5, kärjen CS% >= nousijat + 8 pp. Se päti
niin kauan kuin nousijat ajoivat jäädytetyllä promoted-baselinella. GW1:n
jälkeen malli ajaa live-historialla (Ipswich voitti Sunderlandin) ja
`data/fpl_cs_fdr.json` meni livenä tilaan `sanity_gate: FAIL` vaikka data oli
kunnossa - portti mittasi oletusta, ei dataa ([[portin-sanalista-vanhenee]]).

Tämä portti ei nimeä yhtään joukkuetta. Se mittaa:
  1. joukkueiden määrä (20),
  2. CS%:n ja FDR:n arvoalueet ja hajonnan (ei litteä, ei roskaa),
  3. suunnan: FDR ja CS% ovat vastakkaissuuntaiset yli joukkueiden
     (Spearman <= -0.6),
  4. mallin OMAT tasot: fitin vahvin kolmikko (attack - defence) saa
     pienemmän FDR:n ja suuremman CS%:n kuin heikoin kolmikko.
Kohta 4 korvaa "nousijat": heikoin kolmikko tulee samasta fitistä josta
luvut lasketaan, joten se on tosi joka kierroksella riippumatta siitä kuka
nousi.

Ei tyhjää läpimenoa ([[kontrolli-lapaisi-tyhjana]]): tyhjä joukkuelista,
puuttuvat vahvuudet tai NaN kaatavat portin nimetyllä syyllä.
"""
from __future__ import annotations

import math

MIN_TEAMS = 20
CS_RANGE = (3.0, 75.0)       # yksittäinen joukkue, horisontin keskiarvo
CS_MEAN_RANGE = (12.0, 45.0)  # liigan keskiarvo
FDR_RANGE = (1.0, 5.0)
FDR_MIN_SPREAD = 1.0
SPEARMAN_MAX = -0.6
TIER_N = 3
TIER_FDR_MARGIN = 0.8
TIER_CS_MARGIN_PP = 6.0


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = r
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or len(x) < 3:
        return float("nan")
    rx, ry = _rank(x), _rank(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx == 0 or dy == 0:
        return float("nan")
    return num / (dx * dy)


def _finite(v) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def structural_checks(teams: dict[str, dict], strength: dict[str, float],
                      fdr_key: str, cs_key: str,
                      n_expected: int = MIN_TEAMS) -> list[tuple[str, bool, str]]:
    """Palauttaa [(label, passed, detail)]. Kaikki tarkistukset ajetaan aina,
    jotta loki kertoo koko kuvan eikä vain ensimmäistä kaatumista."""
    out: list[tuple[str, bool, str]] = []
    names = sorted(teams)
    out.append((f"joukkueita == {n_expected}", len(names) == n_expected,
                f"{len(names)}"))

    fdr = [teams[t].get(fdr_key) for t in names]
    cs = [teams[t].get(cs_key) for t in names]
    finite = all(_finite(v) for v in fdr + cs) and bool(names)
    out.append(("FDR ja CS% ovat lukuja jokaisella joukkueella", finite,
                "" if finite else "NaN/None/tyhjä"))
    if not finite:
        # Loput tarkistukset eivät ole mielekkäitä; merkitään FAIL eikä
        # hypätä yli, jotta tyhjä data ei näytä läpimenolta.
        for label in ("CS% arvoalue", "CS% keskiarvo", "FDR arvoalue + hajonta",
                      "FDR ja CS% vastakkaissuuntaiset", "mallin tasot erottuvat"):
            out.append((label, False, "ei dataa"))
        return out

    fdr = [float(v) for v in fdr]
    cs = [float(v) for v in cs]
    lo, hi = CS_RANGE
    out.append((f"CS% jokaisella {lo:.0f}-{hi:.0f}",
                all(lo <= v <= hi for v in cs),
                f"min {min(cs):.1f} max {max(cs):.1f}"))
    mlo, mhi = CS_MEAN_RANGE
    mean_cs = sum(cs) / len(cs)
    out.append((f"CS% keskiarvo {mlo:.0f}-{mhi:.0f}", mlo <= mean_cs <= mhi,
                f"{mean_cs:.1f}"))
    flo, fhi = FDR_RANGE
    spread = max(fdr) - min(fdr)
    out.append((f"FDR jokaisella {flo:.0f}-{fhi:.0f} ja hajonta >= {FDR_MIN_SPREAD}",
                all(flo <= v <= fhi for v in fdr) and spread >= FDR_MIN_SPREAD,
                f"min {min(fdr):.2f} max {max(fdr):.2f}"))
    rho = spearman(fdr, cs)
    out.append((f"FDR ja CS% vastakkaissuuntaiset (Spearman <= {SPEARMAN_MAX})",
                _finite(rho) and rho <= SPEARMAN_MAX,
                f"rho {rho:.2f}" if _finite(rho) else "rho NaN"))

    rated = [t for t in names if _finite(strength.get(t))]
    if len(rated) < 2 * TIER_N:
        out.append(("mallin tasot erottuvat", False,
                    f"vahvuus vain {len(rated)} joukkueella"))
        return out
    rated.sort(key=lambda t: float(strength[t]), reverse=True)
    top, bottom = rated[:TIER_N], rated[-TIER_N:]
    top_fdr = sum(teams[t][fdr_key] for t in top) / TIER_N
    bot_fdr = sum(teams[t][fdr_key] for t in bottom) / TIER_N
    top_cs = sum(teams[t][cs_key] for t in top) / TIER_N
    bot_cs = sum(teams[t][cs_key] for t in bottom) / TIER_N
    out.append((f"mallin vahvin {TIER_N} vs heikoin {TIER_N}: FDR ero >= "
                f"{TIER_FDR_MARGIN} ja CS% ero >= {TIER_CS_MARGIN_PP:.0f} pp",
                (bot_fdr - top_fdr) >= TIER_FDR_MARGIN
                and (top_cs - bot_cs) >= TIER_CS_MARGIN_PP,
                f"vahvin {', '.join(top)} FDR {top_fdr:.2f} CS {top_cs:.1f} | "
                f"heikoin {', '.join(bottom)} FDR {bot_fdr:.2f} CS {bot_cs:.1f}"))
    return out


def print_checks(checks: list[tuple[str, bool, str]]) -> bool:
    ok = True
    for label, passed, detail in checks:
        print(f"  [{'OK ' if passed else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))
        ok = ok and passed
    return ok


def model_strength(dc) -> dict[str, float]:
    """attack - defence samasta fitistä josta CS%/FDR lasketaan."""
    return {t: float(dc.attack[t]) - float(dc.defence.get(t, 0.0)) for t in dc.attack}
