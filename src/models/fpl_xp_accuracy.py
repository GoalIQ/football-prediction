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

22.9.2026 (D5: track record vs FPL:n oma projektio):
  * frozen_players / grade_frozen: AINOA reitti jolla gradaus lukee
    jaadytetyn ep_next:n. Se palauttaa ep_next/form-kentat vain jos freezen
    meta todistaa niiden olevan kierroksen deadline-arvo (haettu ennen
    deadlinea, is_next = kierros). Muuten kentat riisutaan ja vertailu on
    None. Vahti: tests/test_ep_next_reader_discipline.py.
  * vs_fpl_ep_next: kahden ennustajan vertailu (GoalIQ xP vs FPL ep_next)
    riveilla joilla on xp, ep_next JA toteuma, jaettuna minuuttiehdolla
    (pelasi / ei pelannut). Ei vaadi form-kenttaa kuten `comparison`.
"""
from __future__ import annotations

import datetime as _dt

# Freezen FPL-referenssin tila (meta.fpl_reference_status). Kirjoittaja
# (scripts/freeze_fpl_xp_gw.fpl_reference_gate) ja lukija (frozen_players)
# kayttavat samoja koodeja.
REF_OK = "ok"
REF_FETCH_TIME_UNKNOWN = "fetch_time_unknown"
REF_FETCHED_AFTER_DEADLINE = "fetched_at_or_after_deadline"
REF_OTHER_GW = "ep_next_refers_to_other_gw"
REF_KEYS = ("ep_next", "form")

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
      vs_fpl_ep_next               GoalIQ vs FPL ep_next, kaikki / pelasi /
                                   ei pelannut (ks. vs_fpl_ep_next) tai None
    Kutsu jaadytetylla tiedostolla grade_frozen():n kautta, ei suoraan: vain
    se tarkistaa etta ep_next on deadline-arvo.
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
        "vs_fpl_ep_next": vs_fpl_ep_next(players, actual),
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


VS_FPL_METHOD_CODE = "fpl_xp_gw_accuracy.vs_fpl_ep_next.v1"


def _parse_utc(v) -> _dt.datetime | None:
    if not v:
        return None
    try:
        d = _dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)


def ep_next_is_deadline_value(meta: dict) -> bool:
    """Todistaako freezen meta etta jaadytetty ep_next on kierroksen gw
    deadline-arvo?

    22.9 alkaen (meta.fpl_reference_status olemassa): status ok, is_next-
    kierros (ep_next_gw) == gw ja hakuhetki < deadline.

    29.8-rakenne (GW3-GW5, ei statusta): meta.fpl_reference olemassa ja
    frozen_at < deadline. Riittaa, koska bootstrap haettiin ENNEN frozen_at:ia
    (valimuisti on aina lukuhetkea vanhempi) ja freeze valitsi kierroksen
    jonka deadline oli tulevaisuudessa, eli FPL:n is_next-kierroksen.
    Kaikki muu (GW1/GW2 ilman kenttaa, puuttuva deadline) -> False."""
    meta = meta or {}
    gw = meta.get("gw")
    deadline = _parse_utc(meta.get("deadline"))
    if gw is None or deadline is None:
        return False
    if "fpl_reference_status" in meta:
        if meta.get("fpl_reference_status") != REF_OK:
            return False
        if meta.get("ep_next_gw") != gw:
            return False
        fetched = _parse_utc(meta.get("fpl_reference_fetched_at"))
        return fetched is not None and fetched < deadline
    if "fpl_reference" not in meta:
        return False
    frozen_at = _parse_utc(meta.get("frozen_at"))
    return frozen_at is not None and frozen_at < deadline


def frozen_players(frozen: dict) -> list[dict]:
    """Ainoa lukija jaadytetyille riveille gradausta varten. ep_next/form
    palautetaan vain jos ep_next_is_deadline_value(meta); muuten ne
    riisutaan, jolloin comparison ja vs_fpl_ep_next ovat None eivatka
    vertaa deadlinen jalkeen haettua lukua."""
    players = (frozen or {}).get("players") or []
    if ep_next_is_deadline_value((frozen or {}).get("meta") or {}):
        return list(players)
    return [{k: v for k, v in p.items() if k not in REF_KEYS} for p in players]


def grade_frozen(frozen: dict, actual: dict[int, tuple[float, float | None]]) -> dict:
    """grade_players jaadytetylle tiedostolle frozen_players():n kautta."""
    return grade_players(frozen_players(frozen), actual)


def _pair_stats(rows: list[tuple[float, float, float]]) -> dict:
    """rows: (xp, ep_next, actual). goaliq_minus_fpl lasketaan
    pyoristamattomista MAE:ista (ei kahden pyoristetyn luvun erotus);
    negatiivinen = GoalIQ:n virhe pienempi."""
    if not rows:
        return {"n": 0, "mae": None, "goaliq_minus_fpl": None}
    act = [r[2] for r in rows]
    g = mae([r[0] for r in rows], act)
    e = mae([r[1] for r in rows], act)
    return {"n": len(rows),
            "mae": {PRED_GOALIQ: round(g, 3), PRED_EP_NEXT: round(e, 3)},
            "goaliq_minus_fpl": round(g - e, 3)}


def vs_fpl_ep_next(players: list[dict],
                   actual: dict[int, tuple[float, float | None]]) -> dict | None:
    """D5: GoalIQ xP vs FPL ep_next samoilla pelaajilla.

    Rivi mukaan vain kun xp, ep_next JA toteuma ovat olemassa. Toisin kuin
    grade_players, toteumasta puuttuvaa EI oleteta 0 p / 0 min:ksi: vertailu
    koskee pelaajia joilla molemmat ennusteet ja toteuma on, ja puuttuvat
    lasketaan erikseen (n_missing_*). Jako: played = minuutteja > 0,
    did_not_play = 0 min (sama raja kuin classify_outcome:n DNP). Pelaamaton
    rivi mittaa minuuttiennustetta, pelannut pisteennustetta, joten reilu
    vertailu raportoi molemmat erikseen eika vain summaa.
    Ei yhtaan vertailukelpoista rivia -> None (ei nollarivia)."""
    played: list[tuple[float, float, float]] = []
    dnp: list[tuple[float, float, float]] = []
    n_no_ep = n_no_actual = 0
    for p in players or []:
        xp = _as_float(p.get("xp"))
        if xp is None:
            continue
        ep = _as_float(p.get("ep_next"))
        if ep is None:
            n_no_ep += 1
            continue
        a = actual.get(int(p["id"]))
        if a is None:
            n_no_actual += 1
            continue
        pts, mins = a
        row = (xp, ep, float(pts or 0.0))
        (played if (mins is not None and mins > 0) else dnp).append(row)
    if not played and not dnp:
        return None
    return {"method_code": VS_FPL_METHOD_CODE,
            "n_missing_ep_next": n_no_ep,
            "n_missing_actual": n_no_actual,
            "all": _pair_stats(played + dnp),
            "played": _pair_stats(played),
            "did_not_play": _pair_stats(dnp)}


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
