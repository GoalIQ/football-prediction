"""FPL value/consistency + GK rotation pairs (#114 = #107:n kohta 1).

Kaksi työkalua olemassa olevan datan päälle (EI uutta dataputkea):

  value_list        xP/£-ranking: xp_horizon_total / hinta(M£) + fixture-swing
                    (per-GW-xP:n keskihajonta). REHELLISYYS: swing mittaa
                    OTTELUOHJELMAN heiluntaa, ei pelaajan pistetuoton
                    stokastista varianssia (aito konsistenssi = V2, vaatisi
                    element-summary-historian). Caption kulkee payloadissa.

  gk_rotation_pairs Paras 2-vahdin rotaatio: per-GW max(CS%) kahdesta eri
                    seurasta (CS% jo fpl_projections_phase0:ssa), rankattu
                    keskiarvolla + yhteishinta. Starter-GK per seura =
                    korkein predicted_starts (fallback xmins).

Molemmat nojaavat fpl_rate_team.build_context()-pooliin (xP + bootstrap-
hinta/omistus jo joinattuna) → sama fail-safe: projektio puuttuu → 503
RateTeamError, ei kaatumista.
"""

from __future__ import annotations

from src.models.fpl_gameweek import actionable_gameweek

from statistics import pstdev

from src.models.fpl_my_team import squad_context, squad_meta
from src.models.fpl_phase0 import load_phase0
from src.models.fpl_rate_team import (
    AVAILABILITY_GATE_NOTE, POS_NAME, RateTeamError, apply_availability_gate,
    build_context,
)

# Fixture-swing-luokittelu (per-GW-xP:n keskihajonta, pisteissä). Rajat valittu
# nykyjakaumasta: mediaanipelaajan swing ~0.3-0.6, raskas DGW/kalenteriheilunta
# nostaa >1.0. Vain näyttölabel — raaka arvo kulkee aina mukana.
SWING_STEADY_MAX = 0.6
SWING_HIGH_MIN = 1.2

VALUE_NOTE = (
    "Value = model expected points over the horizon per million. Fixture swing "
    "= spread of per-gameweek xP (schedule volatility, not scoring variance). "
    "Rate and minutes are shown separately: xP/90 is the scoring rate while on "
    "the pitch, expected minutes is how much of a gameweek the model expects "
    "the player to be on it. A high rate on low minutes is a bench risk, not a "
    "bargain. "
    "Powered by the match model behind our published track record."
)

def _fixture_swing(gameweeks: list[dict]) -> float:
    xs = [float(g["xp"]) for g in (gameweeks or []) if g.get("xp") is not None]
    if len(xs) < 2:
        return 0.0
    return round(pstdev(xs), 3)


def _swing_label(swing: float) -> str:
    if swing <= SWING_STEADY_MAX:
        return "steady"
    if swing >= SWING_HIGH_MIN:
        return "swingy"
    return "moderate"


def value_list(top_n: int = 20) -> dict:
    """xP/£-ranking koko poolista. Nostaa RateTeamErrorin jos projektio puuttuu."""
    xp_data, bootstrap, pool, _by_id = build_context()
    meta = xp_data.get("meta", {})
    # Addendum 2: serve-time-portti — juuri loukkaantunut ei ole "value pick".
    pool, dropped = apply_availability_gate(pool, bootstrap)

    rows = []
    for p in pool:
        price_m = p["price"] / 10.0
        if price_m <= 0:
            continue
        swing = _fixture_swing(p.get("gameweeks"))
        rows.append({
            "id": p["id"],
            "web_name": p["web_name"],
            "team_short": p["team_short"],
            "pos": POS_NAME.get(p["element_type"], "?"),
            "price": round(price_m, 1),
            "owned_pct": p["owned_pct"],
            "xp_horizon_total": round(p["xp_horizon_total"], 2),
            "value": round(p["xp_horizon_total"] / price_m, 3),
            "fixture_swing": swing,
            "swing_label": _swing_label(swing),
            # 5.8: vauhti ja minuutit erikseen. xp_per_gw kertoo nämä yhteen,
            # ja se on juuri se yhdistetty luku jossa pettävä oletus (minuutit)
            # jää piiloon. Vauhti LUETAAN putken kentästä eikä lasketa täällä:
            # oma derivaatio oli väärä (ks. fpl_xp.xp_full_90) ja kahdennettu
            # kaava on juuri se rakenne joka päästi virheen kahdelle pinnalle.
            "xmins": (round(float(p["xmins"]), 1)
                      if p.get("xmins") is not None else None),
            "xp_per_90": p.get("xp_per_90"),
        })
    rows.sort(key=lambda r: r["value"], reverse=True)

    return {
        "meta": {
            "available": True,
            "season": meta.get("season"),
            # 25.8: actionable eika next_gameweek. Arvolista on ENNUSTE, ja
            # kesken kierroksen next_gameweek osoittaa jo lukittuun
            # kierrokseen. Ks. src/models/fpl_gameweek.py.
            "gw": actionable_gameweek(meta),
            "horizon_gw": meta.get("horizon_gw"),
            "generated_at": meta.get("generated_at"),
            "note": VALUE_NOTE,
            "availability_gate": {"checked": True, "dropped": dropped,
                                  "note": AVAILABILITY_GATE_NOTE},
        },
        "players": rows[:top_n],
    }


def _starter_gk_by_club(pool: list[dict]) -> dict[str, dict]:
    """Todennäköisin ykkösvahti per seura (team_short): korkein
    predicted_starts, tasatilanteessa xmins."""
    best: dict[str, dict] = {}
    for p in pool:
        if p["element_type"] != 1:
            continue
        key = p["team_short"]
        cur = best.get(key)
        rank = (float(p.get("predicted_starts") or 0.0), float(p.get("xmins") or 0.0))
        if cur is None or rank > cur["_rank"]:
            best[key] = {**p, "_rank": rank}
    return best


GK_PAIRS_NOTE = (
    "Best rotating goalkeeper duo: each gameweek you field the keeper with "
    "the higher model clean sheet probability. Pairs are ranked by that "
    "average scaled by how many of the horizon gameweeks both clubs have a "
    "projection for, so a pair that only lines up for two of six weeks "
    "cannot outrank a pair that lines up for all six."
)
GK_OWN_NOTE = (
    "Your pair is scored with the same formula as the list. Transfers needed "
    "counts how many of the pair you do not own. Affordable means the pair "
    "costs no more than your two keepers plus your bank at current prices."
)


def _pair_split(cs_a: dict[int, float], cs_b: dict[int, float], a: str, b: str
                ) -> tuple[list[dict], float]:
    """Yhteisten kierrosten per-GW max(CS%) + keskiarvo. Sama kaava listalle
    ja omalle parille (yksi lahde kahdelle luvulle)."""
    common = sorted(set(cs_a) & set(cs_b))
    split = []
    for gw in common:
        ca, cb = cs_a[gw], cs_b[gw]
        pick = a if ca >= cb else b
        split.append({"gw": gw, "team_short": pick,
                      "cs_pct": round(max(ca, cb), 1)})
    if not split:
        return [], 0.0
    return split, sum(x["cs_pct"] for x in split) / len(split)


def _pair_row(ga: dict, gb: dict, a: str, b: str, split: list[dict],
              avg_best: float) -> dict:
    return {
        "avg_best_cs_pct": round(avg_best, 1),
        "combined_price": round((ga["price"] + gb["price"]) / 10.0, 1),
        "gk_a": {"id": ga["id"], "web_name": ga["web_name"],
                 "team_short": a, "price": round(ga["price"] / 10.0, 1)},
        "gk_b": {"id": gb["id"], "web_name": gb["web_name"],
                 "team_short": b, "price": round(gb["price"] / 10.0, 1)},
        "gw_split": split,
    }


def gk_rotation_pairs(top_n: int = 10, squad: dict | None = None) -> dict:
    """Paras 2-vahdin pari: per-GW max(CS%) kahdesta eri seurasta.

    Nostaa RateTeamErrorin jos xP-pooli puuttuu; CS-data puuttuu ->
    available=False-runko (ei kaatumista).

    MY-TEAM-CONTEXT (3.9): `squad` = fpl_my_team.squad_context(). Kun se on
    saatavilla, vastaus saa `own_pair`-lohkon (kayttajan kaksi vahtia samalla
    kaavalla), ja jokainen pari `transfers_needed` (0/1/2) + `affordable`
    (combined_price <= omien vahtien hinta + bank). Ilman squadia vastaus on
    entinen: ei uusia avaimia riveilla eika metassa.

    Rankkaus (3.9): avg_best_cs_pct * common_gws / horizon_gws. Aiemmin pari
    jolla oli 2 yhteista kierrosta rankattiin samoin kuin 6:n pari, ja lyhyt
    hyva patka voitti koko horisontin. `common_gws` naytetaan rivilla vain
    kun se on horisonttia lyhyempi (muuten se olisi sama luku joka rivilla).
    """
    _xp, bootstrap, pool, pool_by_id = build_context()
    # Sivussa oleva vahti ei kelpaa rotaatioparin puolikkaaksi (serve-time).
    live_pool, _dropped = apply_availability_gate(pool, bootstrap)
    phase0 = load_phase0()
    p0_meta = phase0.get("meta", {})
    if not p0_meta.get("available") or not phase0.get("teams"):
        return {"meta": {"available": False,
                         "note": "Clean sheet projections are not available yet."},
                "pairs": []}

    # CS% per seura per GW (short-koodi = join-avain xP-pooliin)
    cs_by_short: dict[str, dict[int, float]] = {}
    for t in phase0["teams"]:
        short = t.get("short")
        if not short:
            continue
        cs_by_short[short] = {
            f["gw"]: float(f["cs_pct"]) for f in (t.get("fixtures") or [])
            if f.get("gw") is not None and f.get("cs_pct") is not None
        }

    # 29.7 (Villen havainto): horizon_gw kertoo mita TASSA vastauksessa on, ei
    # mita tiedoston metassa lukee. Pari lasketaan vain kierroksista joilla
    # MOLEMMILLA seuroilla on cs_pct, eli lahihorisontista. Sama vikaluokka
    # kuin muistin `honest-data-labels`: leima lupasi kattavuutta jota ei ole.
    cs_gws = {gw for per_gw in cs_by_short.values() for gw in per_gw}
    next_gw = actionable_gameweek(p0_meta)
    horizon_actual = (
        max(cs_gws) - next_gw + 1 if cs_gws and next_gw is not None else None
    )
    # Painotuksen nimittaja: horisontin kierrosmaara. Jos sita ei voi johtaa,
    # kayta laajinta CS-kattavuutta (silloin taysi pari saa painon 1.0).
    horizon_n = horizon_actual if horizon_actual and horizon_actual > 0 else (
        max((len(v) for v in cs_by_short.values()), default=0))

    def _weighted(avg_best: float, n_common: int) -> float:
        if not horizon_n:
            return avg_best
        return avg_best * min(n_common, horizon_n) / horizon_n

    gks = _starter_gk_by_club(live_pool)
    shorts = sorted(s for s in gks if s in cs_by_short)

    own_ids = set(squad["ids"]) if squad and squad.get("available") else set()
    own_gks = [pool_by_id[i] for i in own_ids
               if i in pool_by_id and pool_by_id[i]["element_type"] == 1]
    own_gks.sort(key=lambda p: p["id"])
    # Omien vahtien hinta: pool (=bootstrap now_cost joinattuna); jos vahdilla
    # ei ole projektiota, hinta luetaan suoraan bootstrapista.
    own_gk_tenths = 0
    if own_ids:
        boot_by_id = {e["id"]: e for e in (bootstrap.get("elements") or [])}
        for pid in own_ids:
            row = pool_by_id.get(pid) or boot_by_id.get(pid)
            if row is None or row.get("element_type") != 1:
                continue
            own_gk_tenths += int(row["price"] if "price" in row
                                 else row.get("now_cost") or 0)
    own_budget_tenths = own_gk_tenths + (squad["bank_tenths"] if own_ids else 0)

    pairs = []
    for i, a in enumerate(shorts):
        for b in shorts[i + 1:]:
            split, avg_best = _pair_split(cs_by_short[a], cs_by_short[b], a, b)
            if not split:
                continue
            ga, gb = gks[a], gks[b]
            row = _pair_row(ga, gb, a, b, split, avg_best)
            if horizon_n and len(split) < horizon_n:
                row["common_gws"] = len(split)
            row["_score"] = _weighted(avg_best, len(split))
            if own_ids:
                pair_ids = {ga["id"], gb["id"]}
                row["transfers_needed"] = len(pair_ids - own_ids)
                row["affordable"] = (ga["price"] + gb["price"]) <= own_budget_tenths
            pairs.append(row)
    # Paras rotaatio ensin; sama painotettu CS% -> halvempi pari voittaa
    pairs.sort(key=lambda r: (-r["_score"], r["combined_price"]))
    scores = [r.pop("_score") for r in pairs]

    meta = {
        "available": True,
        "gw": actionable_gameweek(p0_meta),
        "horizon_gw": horizon_actual,
        "note": GK_PAIRS_NOTE,
    }
    out = {"meta": meta, "pairs": pairs[:top_n]}

    if squad is not None:
        meta["squad"] = squad_meta(squad)
        own_pair = None
        if len(own_gks) >= 2:
            ga, gb = own_gks[0], own_gks[1]
            a, b = ga["team_short"], gb["team_short"]
            if a in cs_by_short and b in cs_by_short:
                split, avg_best = _pair_split(cs_by_short[a], cs_by_short[b], a, b)
                if split:
                    own_pair = _pair_row(ga, gb, a, b, split, avg_best)
                    own_pair["common_gws"] = len(split)
                    own_pair["transfers_needed"] = 0
                    own_pair["affordable"] = True
                    # Sijoitus listalla samalla painotuksella (1 = paras).
                    own_score = _weighted(avg_best, len(split))
                    own_pair["rank"] = sum(1 for sc in scores if sc > own_score) + 1
                    own_pair["of"] = len(pairs)
        if squad.get("available"):
            meta["own_budget"] = round(own_budget_tenths / 10.0, 1)
            meta["own_note"] = GK_OWN_NOTE
            if own_pair is None:
                meta["own_pair_note"] = (
                    "Could not score your pair: fewer than two of your "
                    "keepers have a clean sheet projection.")
        out["own_pair"] = own_pair
    return out


def value_and_gk(top_n_value: int = 20, top_n_pairs: int = 10,
                 entry: int | None = None,
                 players: list[int] | None = None) -> dict:
    """Yhdistetty payload /api/fantasy/value-endpointille.

    MY-TEAM-CONTEXT (3.9): `entry` (tai `players` = 15 id:ta) -> sama
    resolve_squad kuin rate-teamissa. Value-rivit saavat `owned`-lipun ja
    GK-parit oman parin + siirto-/budjettimerkinnat. Ilman kumpaakaan
    vastaus on tasmalleen entinen. Entry-virhe ei kaada: meta.squad kertoo.
    """
    value = value_list(top_n=top_n_value)
    squad = None
    if entry is not None or players:
        _xp, bootstrap, _pool, _by_id = build_context()
        squad = squad_context(bootstrap, entry, players)
        value["meta"]["squad"] = squad_meta(squad)
        if squad and squad["available"]:
            for r in value["players"]:
                r["owned"] = r["id"] in squad["ids"]
    try:
        gk = gk_rotation_pairs(top_n=top_n_pairs, squad=squad)
    except RateTeamError:
        gk = {"meta": {"available": False, "note": "GK data unavailable."},
              "pairs": []}
    return {"meta": value["meta"], "players": value["players"], "gk": gk}
