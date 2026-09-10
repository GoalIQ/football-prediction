"""Suosikin nimeämisen marginaali: milloin 1X2-ennuste on "too close to call".

Tausta (Villen havainto 8.9.2026, QUEUE `SUOSIKKI-VAIN-KUN-ERO-YLITTAA-VIRHEEN`):
tuotanto antoi Club Brugge 40,5 / tasa 24,0 / Aston Villa 35,5 ja pinta
esitti Bruggen suosikkina. Ero oli 5 pp, mallin oma virhe suurempi. Kun ero
on virhettä pienempi, "suosikki" on tietoa jota meillä ei ole. Mallia EI
säädetä osumaan markkinaan (jälkifittaus); korjaus on tuotepuolella.

Marginaali mitataan OMASTA track recordista (`scripts/measure_call_margin.py`
-> `data/call_margin.json`): pienin koti-vieras-ero jonka yläpuolella nimetty
voittaja osuu ratkenneissa otteluissa selvästi kolikonheittoa paremmin.
Mittaus 10.9.2026 (n=407 gradattua, 8 pp:n luokat): ero < 16 pp -> 45-48 %
osumaa ratkenneissa, ero >= 16 pp -> 65-89 %.

SUUNNITTELUSÄÄNTÖ (CLAUDE.md 6a):
(1) Tämä on AINOA lukija joka saa sanoa "suosikki" ihmiselle. Pinnat eivät
    laske argmaxia itse. `named_winner()` (accuracy.py) säilyy track recordin
    kirjauslogiikkana - se on julkaistu metodologia ("the model always names
    the more likely winner") eikä sitä muuteta kesken kauden.
(2) Artefaktin puuttuminen on FAIL-CLOSED: ilman mitattua marginaalia
    suosikkia ei nimetä (favourite=None, reason="margin_unavailable").
(3) `tests/test_call_margin.py` mittaa säännön synteettisillä eroilla
    molemmin puolin marginaalia, ei nykyisellä datalla.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MARGIN_PATH = PROJECT_ROOT / "data" / "call_margin.json"

# Mittauksen parametrit. Samat luvut skriptissä ja testissä; muutos tähän
# muuttaa julkaistua marginaalia ja näkyy diffissä.
# PERUSTELU (10.9.2026, portin sivuhuomio, CLAUDE.md 6a mek. 2): luokkaleveys
# valittiin SEN JÄLKEEN kun 4 pp antoi marginaaliksi 28. Herkkyys samasta
# lokista (n=407, kokonaislukuero): 4 pp -> 28, 6 pp -> 18, 8 pp -> 16,
# 10 pp -> 20, 12 pp -> 24. Julkaistu 16 on haarukan matalin. Se on
# perusteltu koska 4 pp:n luokissa (n~30, keskivirhe ~9 pp) ainoa 60 %:n
# ehdon kaatava luokka oli 24-28 pp (11/19 = 58 %, pieni otos), ja kaikki
# 16 pp:n alapuoliset viipaleet ovat 37-55 % ja ylapuoliset 58-86 % kummallakin
# ruudukolla. 8 pp:n luokissa n~45 ja marginaali ei heilu refreshien valilla.
# tests/test_call_margin.py::test_bucket_parameters_are_justified kaatuu jos
# naita muutetaan ilman etta tama perustelu paivittyy.
BUCKET_PP = 8          # eron luokkaväli prosenttiyksikköinä
MIN_BUCKET_N = 25      # luokka jossa on tätä vähemmän otteluita ei ratkaise
DECISIVE_HIT_FLOOR = 0.60   # "selvästi kolikonheittoa parempi" ratkenneissa
MARGIN_FLOOR_PP = 4    # marginaali ei koskaan alle tämän (pyöristys/kohina)
MARGIN_CAP_PP = 40     # eikä yli tämän (jos data ei tue, sanotaan ettei tiedetä)

_UNSET = object()
_cache: object = _UNSET


def pct_int(p: float) -> int:
    """Todennäköisyys kokonaisprosentiksi, puoli ylöspäin (= JS Math.round).

    Portin löydös 10.9: näytetty prosentti ja päätetty ero tulivat eri
    pyöristyspolusta, ja 25 % riveistä lukijan vähennyslasku ei täsmännyt
    lauseeseen. Nyt ero lasketaan SAMOISTA kokonaisluvuista jotka näytetään,
    ja pyöristys on sama kuin selaimen/appin Math.round (Pythonin round on
    banker's rounding, muisti: pyoristyssaanto-eroaa).
    """
    return int(math.floor(float(p) * 100.0 + 0.5))


def measure_margin(graded: list[dict]) -> dict:
    """Laske marginaali gradatuista lokiriveistä.

    `graded`: rivit joilla on p_home, p_away ja result.actual_outcome/hit_1x2.
    Palauttaa dictin jossa `margin_pp` on int tai None (data ei tue mitään
    marginaalia -> lukija ei nimeä suosikkia), sekä luokkataulukon jotta
    luku on johdettavissa artefaktista eikä muistista.
    """
    buckets: dict[int, list[int]] = {}
    n_used = 0
    for e in graded:
        res = e.get("result") or {}
        ph, pa = e.get("p_home"), e.get("p_away")
        if ph is None or pa is None or res.get("voided"):
            continue
        actual = res.get("actual_outcome")
        if actual not in ("home", "away", "draw"):
            continue
        gap_pp = abs(pct_int(ph) - pct_int(pa))
        k = min(int(gap_pp // BUCKET_PP) * BUCKET_PP, MARGIN_CAP_PP)
        b = buckets.setdefault(k, [0, 0, 0])
        b[0] += 1
        b[1] += 1 if res.get("hit_1x2") else 0
        b[2] += 1 if actual == "draw" else 0
        n_used += 1

    rows = []
    for k in sorted(buckets):
        n, hit, draw = buckets[k]
        decisive = n - draw
        rows.append({
            "gap_from_pp": k,
            # cap-luokka kokoaa kaikki sen ylapuoliset erot (lokissa 87 pp:hen
            # asti): ylaraja on None, ei k+BUCKET_PP, ettei kentta valehtele.
            "gap_to_pp": None if k >= MARGIN_CAP_PP else k + BUCKET_PP,
            "open_ended": k >= MARGIN_CAP_PP,
            "n": n,
            "hit_pct": round(100.0 * hit / n, 1) if n else None,
            "draw_pct": round(100.0 * draw / n, 1) if n else None,
            # ratkenneet (ei tasapeli) ja niista nimetyn puolen voitot:
            # lukumaarat artefaktiin, jotta prosentti on johdettavissa
            "decisive_n": decisive,
            "decisive_won": hit,
            "decisive_hit_pct": round(100.0 * hit / decisive, 1) if decisive else None,
        })

    # Marginaali = pienin luokan alaraja josta ylöspäin JOKAINEN riittävän
    # iso luokka osuu ratkenneissa vähintään DECISIVE_HIT_FLOOR. Pienet
    # luokat (n < MIN_BUCKET_N) eivät kaada ehtoa mutta eivät myöskään täytä sitä.
    margin: Optional[int] = None
    edges = [r["gap_from_pp"] for r in rows]
    for edge in edges:
        above = [r for r in rows if r["gap_from_pp"] >= edge]
        big = [r for r in above if r["n"] >= MIN_BUCKET_N]
        if not big:
            continue
        if all((r["decisive_hit_pct"] or 0) / 100.0 >= DECISIVE_HIT_FLOOR for r in big):
            margin = max(edge, MARGIN_FLOOR_PP)
            break
    if margin is not None and margin > MARGIN_CAP_PP:
        margin = None

    below = [r for r in rows if margin is not None and r["gap_from_pp"] < margin]
    above = [r for r in rows if margin is not None and r["gap_from_pp"] >= margin]
    n_below = sum(r["n"] for r in below)
    hit_below = sum(r["n"] * (r["hit_pct"] or 0) / 100.0 for r in below)
    dec_below_n = sum(r["decisive_n"] for r in below)
    dec_below_won = sum(r["decisive_won"] for r in below)
    dec_above_n = sum(r["decisive_n"] for r in above)
    dec_above_won = sum(r["decisive_won"] for r in above)
    return {
        "margin_pp": margin,
        # Lauseiden luvut tulevat NAISTA kentista, ei proosasta (portti 10.9):
        # "under N points the named side won X% of matches that had a winner".
        "decisive_below_n": dec_below_n,
        "decisive_below_won": dec_below_won,
        "decisive_below_pct": (round(100.0 * dec_below_won / dec_below_n)
                               if dec_below_n else None),
        "decisive_above_n": dec_above_n,
        "decisive_above_won": dec_above_won,
        "decisive_above_pct": (round(100.0 * dec_above_won / dec_above_n)
                               if dec_above_n else None),
        "method": (
            f"|p_home - p_away| in {BUCKET_PP} pp buckets over graded rows; margin = "
            f"lowest bucket edge above which every bucket with n >= {MIN_BUCKET_N} "
            f"has named-winner hit rate >= {int(DECISIVE_HIT_FLOOR * 100)} % among "
            f"decisive (non-draw) matches. Floor {MARGIN_FLOOR_PP} pp, cap {MARGIN_CAP_PP} pp."
        ),
        "n_graded": n_used,
        "n_below_margin": n_below,
        "hit_pct_below_margin": round(100.0 * hit_below / n_below, 1) if n_below else None,
        "measured_at": None,
        "buckets": rows,
    }


def load_margin(path: Path = MARGIN_PATH) -> Optional[dict]:
    """Lue mitattu marginaali. Puuttuva tai rikkinäinen artefakti -> None.

    Välimuisti prosessin elinajaksi (API). Testit antavat oman polun.
    """
    global _cache
    if path is MARGIN_PATH and _cache is not _UNSET:
        return _cache  # type: ignore[return-value]
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        m = doc.get("margin_pp")
        out = doc if isinstance(m, int) and m > 0 else None
    except Exception:
        out = None
    if path is MARGIN_PATH:
        _cache = out
    return out


def reset_cache() -> None:
    global _cache
    _cache = _UNSET


def call_state(
    p_home: float,
    p_draw: float,
    p_away: float,
    margin: object = _UNSET,
) -> dict:
    """Ainoa lukija: saako pinta nimetä suosikin, ja kumman.

    Palauttaa:
      favourite: "home" | "away" | None
      too_close: bool  (True kun ero < marginaali)
      gap_pp: int      (|pct_int(p_home) - pct_int(p_away)|, SAMA luku jonka
                        pinta näyttää: ero lasketaan näytetyistä prosenteista)
      margin_pp: int | None
      below_hit_pct: int | None  (nimetyn puolen voitto-% ratkenneissa kun
                        ero < marginaali; lause lukee tämän, ei "about half")
      measured_at: str | None    (artefaktin mittaushetki, YYYY-MM-DD)
      reason: "gap_above_margin" | "gap_below_margin" | "margin_unavailable"

    `margin`: dict artefaktista, None (ei artefaktia) tai jätä antamatta ->
    luetaan levyltä. Tasapeli ei ole koskaan "favourite" - tämä vastaa track
    recordin metodologiaa (named_winner), mutta pinta saa sanoa "too close".
    """
    m = load_margin() if margin is _UNSET else margin
    gap_pp = abs(pct_int(p_home) - pct_int(p_away))
    if not m or not isinstance(m.get("margin_pp"), int):
        return {
            "favourite": None, "too_close": None, "gap_pp": gap_pp,
            "margin_pp": None, "below_hit_pct": None, "measured_at": None,
            "reason": "margin_unavailable",
        }
    margin_pp = int(m["margin_pp"])
    below = m.get("decisive_below_pct")
    measured = (m.get("measured_at") or "")[:10] or None
    common = {"gap_pp": gap_pp, "margin_pp": margin_pp,
              "below_hit_pct": below if isinstance(below, int) else None,
              "measured_at": measured}
    if gap_pp < margin_pp:
        return {"favourite": None, "too_close": True,
                "reason": "gap_below_margin", **common}
    return {
        "favourite": "home" if float(p_home) >= float(p_away) else "away",
        "too_close": False, "reason": "gap_above_margin", **common,
    }
