"""Per-GW xP-gradaus luokittain ja vertailu FPL:n ep_next:iin (29.8.2026).

IDEA-2026-08-29-xp-graded-public: Onside Arena vaittaa olevansa ainoa tyokalu
joka jaadyttaa jokaisen pelaajan xP:n ennen deadlinea ja julkaisee gradatun
tuloksen. Meilla freeze ja gradaus olivat jo olemassa (freeze_fpl_xp_gw +
grade_fpl_xp_gw), mutta gradaus oli yksi MAE-luku positioittain eika sita
verrattu mihinkaan. Tama moduuli on PUHDAS logiikka (ei IO:ta):

  * classify_outcome: toteuman luokka (DNP / blank / ticker / haul)
  * grade_players: GoalIQ-MAE kaikilla jaadytetyilla riveilla + by_class, ja
    vertailulohko (GoalIQ vs FPL ep_next vs form-baseline) SAMALLA rivijoukolla
  * pool_groups: usean GW:n ryhmalukujen yhdistaminen n-painotettuna (MAE on
    keskiarvo, joten n*mae summautuu tarkasti)

Vertailun saanto: rivi otetaan vertailuun vain jos KAIKKI kolme lukua on
jaadytetty. Puuttuva ep_next EI ole 0 (0 olisi "FPL ennusti nollaa" ja
tekisi FPL:sta huonomman kuin se on). GW1 ja GW2 jaadytettiin ennen tata
riviä ilman ep_next-kenttaa -> niilta vertailu on None, ei nolla.
"""
from __future__ import annotations

CLASS_DNP = "dnp"
CLASS_BLANK = "blank"
CLASS_TICKER = "ticker"
CLASS_HAUL = "haul"
CLASSES = (CLASS_DNP, CLASS_BLANK, CLASS_TICKER, CLASS_HAUL)

# Rajat toteutuneen mukaan. Blank = 2 p tai alle PELANNEENA; DNP erotetaan
# minuuteista, koska 0 min on minuuttimallin virhe eika pistemallin.
BLANK_MAX_PTS = 2
TICKER_MAX_PTS = 9
HAUL_MIN_PTS = 10

CLASS_LABELS = {
    CLASS_DNP: "Did not play (0 minutes)",
    # 29.8 portti k2: EI "Blank (...)" alkuun. Samalla sivulla #gw-calls
    # viittaa ilmaisen xP-sivun Blankiin, joka on DIST_BLANK_PTS = 2
    # "esiintyminen tai ei mitaan" eli SISALTAA pelaamattomat. Sama sana,
    # kaksi nimittajaa samalla sivulla: tassa 192/490, siella mukana myos
    # 190 DNP:ta. Sanajarjestys erottaa ne heti.
    CLASS_BLANK: "Played, blank (2 points or fewer)",
    CLASS_TICKER: "Ticker (3 to 9 points)",
    CLASS_HAUL: "Haul (10 or more points)",
}

PRED_GOALIQ = "goaliq"
PRED_EP_NEXT = "fpl_ep_next"
PRED_FORM = "form_baseline"
PREDICTORS = (PRED_GOALIQ, PRED_EP_NEXT, PRED_FORM)

METHOD_CODE = "fpl_xp_gw_accuracy.comparison.v1"
METHOD = (
    "Each frozen player is scored against official FPL points for the "
    "gameweek. MAE is the mean absolute error in points. by_class groups "
    "players by what actually happened (dnp = 0 minutes, blank = 2 points or "
    "fewer with minutes, ticker = 3 to 9 points, haul = 10 or more). The "
    "comparison block scores GoalIQ xP, the FPL ep_next field and the FPL "
    "form field on the same players; a player is included only when all "
    "three numbers were frozen before the deadline. A missing ep_next is "
    "skipped, never treated as 0."
)


def classify_outcome(points: float, minutes: float | None) -> str:
    """Toteuman luokka. DNP ennen pisteita: 0 min on aina DNP."""
    if minutes is None or minutes <= 0:
        return CLASS_DNP
    if points <= BLANK_MAX_PTS:
        return CLASS_BLANK
    if points <= TICKER_MAX_PTS:
        return CLASS_TICKER
    return CLASS_HAUL


def mae(pred: list[float], actual: list[float]) -> float | None:
    if not pred or len(pred) != len(actual):
        return None
    return sum(abs(float(a) - float(p)) for p, a in zip(pred, actual)) / len(pred)


def _as_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _group_stats(diffs: list[float]) -> dict:
    n = len(diffs)
    return {"n": n,
            "mae": round(sum(abs(d) for d in diffs) / n, 3) if n else None,
            "bias": round(sum(diffs) / n, 3) if n else None}


def grade_players(players: list[dict], actual: dict[int, tuple[float, float | None]]) -> dict:
    """Jaadytetyt rivit + toteuma {id: (points, minutes)} -> gradauslohkot.

    Palauttaa:
      n, mae, bias, mae_by_pos     GoalIQ, kaikki rivit joilla on xp
      by_class                     GoalIQ luokittain, kaikki rivit
      by_pos_stats                 GoalIQ positioittain {n, mae, bias}, kaikki
                                   rivit (mae_by_pos ilman n:aa ei poolaudu)
      comparison                   kolmen ennustajan MAE samalla rivijoukolla
                                   (rivit joilla xp, ep_next JA form) tai None
    Pelaaja jota ei loydy toteumasta on 0 p / 0 min (aito DNP-miss, kuten
    vanhassa gradauksessa).
    """
    diffs: list[float] = []
    by_pos: dict[str, list[float]] = {}
    by_class: dict[str, list[float]] = {c: [] for c in CLASSES}
    cmp_rows: list[tuple[str, str, float, float, float, float]] = []
    for p in players or []:
        xp = _as_float(p.get("xp"))
        if xp is None:
            continue
        pts, mins = actual.get(int(p["id"]), (0.0, 0.0))
        pts = float(pts or 0.0)
        d = pts - xp
        diffs.append(d)
        pos = p.get("pos") or "?"
        by_pos.setdefault(pos, []).append(d)
        cls = classify_outcome(pts, mins)
        by_class[cls].append(d)
        ep = _as_float(p.get("ep_next"))
        form = _as_float(p.get("form"))
        if ep is None or form is None:
            continue
        cmp_rows.append((cls, pos, pts, xp, ep, form))

    n = len(diffs)
    out = {
        "n": n,
        "mae": round(sum(abs(d) for d in diffs) / n, 3) if n else None,
        "bias": round(sum(diffs) / n, 3) if n else None,
        "mae_by_pos": {pos: round(sum(abs(d) for d in ds) / len(ds), 3)
                       for pos, ds in sorted(by_pos.items()) if ds},
        "by_class": {c: _group_stats(by_class[c]) for c in CLASSES},
        "by_pos_stats": {pos: _group_stats(ds) for pos, ds in sorted(by_pos.items()) if ds},
        "comparison": _comparison(cmp_rows),
    }
    return out


def _mae_triplet(rows: list[tuple]) -> dict:
    """rows: (cls, pos, actual, xp, ep_next, form)."""
    act = [r[2] for r in rows]
    return {
        PRED_GOALIQ: round(mae([r[3] for r in rows], act), 3),
        PRED_EP_NEXT: round(mae([r[4] for r in rows], act), 3),
        PRED_FORM: round(mae([r[5] for r in rows], act), 3),
    }


def _comparison(rows: list[tuple]) -> dict | None:
    if not rows:
        return None
    by_class: dict[str, list] = {c: [] for c in CLASSES}
    by_pos: dict[str, list] = {}
    for r in rows:
        by_class[r[0]].append(r)
        by_pos.setdefault(r[1], []).append(r)
    return {
        "n": len(rows),
        "predictors": list(PREDICTORS),
        "mae": _mae_triplet(rows),
        "by_class": {c: {"n": len(rs), "mae": _mae_triplet(rs) if rs else None}
                     for c, rs in by_class.items()},
        "by_pos": {pos: {"n": len(rs), "mae": _mae_triplet(rs)}
                   for pos, rs in sorted(by_pos.items()) if rs},
    }


def pool_groups(groups: list[dict]) -> dict | None:
    """Yhdista usean GW:n ryhmalohkot {n, mae} tai {n, mae:{pred: mae}}.

    MAE on keskiarvo -> n-painotettu keskiarvo on tarkalleen yhdistetyn
    joukon MAE. Tyhja syote tai n=0 -> None.
    """
    total = 0
    sums: dict[str, float] | float = {}
    scalar = None
    for g in groups:
        if not g or not g.get("n") or g.get("mae") is None:
            continue
        n = int(g["n"])
        m = g["mae"]
        if isinstance(m, dict):
            for k, v in m.items():
                if v is None:
                    continue
                sums[k] = sums.get(k, 0.0) + n * float(v)   # type: ignore[union-attr]
        else:
            scalar = (scalar or 0.0) + n * float(m)
        total += n
    if not total:
        return None
    if scalar is not None:
        return {"n": total, "mae": round(scalar / total, 3)}
    return {"n": total, "mae": {k: round(v / total, 3) for k, v in sums.items()}}  # type: ignore[union-attr]
