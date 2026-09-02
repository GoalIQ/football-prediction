"""#35 Transfer Planner -suite: monen GW:n siirtosuunnittelu + captain-picker +
differential finder + pelaajavertailu.

Kaikki nojaa OLEMASSA OLEVAAN xP-projektioon (/api/fantasy/xp, #33
predicted-minutes mukana) ja #34-rate-teamin jaettuun infraan (build_context,
resolve_squad, optimal_xi) — xP-malliin EI kosketa.

PLANNER-HEURISTIIKKA (dokumentoitu rajaus, EI globaali optimoija — scope-kuri
CoS-linjauksen mukaan; greedy + rajattu kandidaattijoukko riittää GW1-arvoon):
  - Käydään horisontin GW:t järjestyksessä. Per GW arvioidaan yhden siirron
    kandidaatit: ulos kuka tahansa rungon 15:stä, sisään saman position
    TOP_CANDIDATES_PER_POS parasta poolipelaajaa (jäljellä olevan horisontin
    xP:llä), budjetti (bank + lähtevän hinta) + max 3/klubi vaihdon jälkeen.
  - Siirron arvo = sisään tulevan ja lähtevän xP-ero JÄLJELLÄ OLEVALLE
    horisontille (ei koko kaudelle) − hit-kustannus (HIT_COST jos free
    transferit loppu). Tehdään ahneesti niin kauan kuin paras arvo ylittää
    MIN_GAIN_PER_TRANSFER:in, max MAX_TRANSFERS_PER_GW/GW.
  - Free transferit: alussa `ft`-parametri (oletus 1), +1 per GW, katto
    FT_CARRY_MAX (FPL 2024- säännöt: 5). "Roll transfer" kirjataan kun optimi
    on säästää siirto.
  - Gate: suunnitelman netto-xP (kumulatiivinen xP − hitit) ei koskaan alita
    ei-siirtoja-baselinea — muuten palautetaan hold-suunnitelma (testattu).
"""
from __future__ import annotations

from src.models.fpl_rate_team import (
    AVAILABILITY_GATE_NOTE, HIT_COST_XP, HOLD_THRESHOLD_XP, POS_NAME,
    MAX_PER_CLUB, RateTeamError, apply_availability_gate, build_context,
    build_hold_verdict, captain_suggestion, clamp_gw_to_projections, planning_start_gw,
    optimal_xi, picks_outdated, resolve_squad, _gw_xp,
)
from src.models import fpl_transfers as _engine

HIT_COST = HIT_COST_XP  # FPL:n -4; sama lähde kuin rate-teamin hold_verdict
FT_CARRY_MAX = 5
# 28.8 (PLANNER-FREEZE-DIVERGENCE): siirtologiikka asuu fpl_transfers-moottorissa
# jota myös rate-team ja freeze käyttävät. Vakiot re-exportataan täältä, jotta
# vanhat kutsujat (testit, fantasy_edge) näkevät saman arvon kuin moottori.
MAX_TRANSFERS_PER_GW = _engine.MAX_TRANSFERS_PER_GW
TOP_CANDIDATES_PER_POS = _engine.TOP_CANDIDATES_PER_POS
MIN_GAIN_PER_TRANSFER = _engine.MIN_GAIN_PER_TRANSFER
DEFAULT_HORIZON = 6  # sama kuin xP-artefakti ja freeze; oli 3 (divergenssin syy #2)
DIFFERENTIAL_MAX_OWNERSHIP = 10.0
DIFFERENTIAL_TOP_N = 20
CAPTAIN_DIFFERENTIAL_EO = 10.0
# #71 malli-vs-joukko: delta = mallin xP-persentiili − EO-persentiili (positio-
# sisäisesti, jotta GKP/DEF eivät vertaudu hyökkääjien xP-tasoon). Listalle
# vaaditaan aito erimielisyys (|delta| ≥ kynnys) JA riittävä taso omalla
# akselilla — template-pelaajat joista malli on samaa mieltä eivät kuulu
# kumpaankaan listaan (rehellisyys > listan täyttäminen).
MODEL_VS_CROWD_TOP_N = 10
MODEL_VS_CROWD_DELTA_MIN = 15.0
MODEL_VS_CROWD_MIN_MODEL_PCT = 60.0
MODEL_VS_CROWD_MIN_CROWD_PCT = 60.0


def _horizon_gws(pool: list[dict], start_gw: int, horizon: int) -> list[int]:
    """Sama laskenta kuin rate-teamilla (29.8: kaksi moottoria antoi kaksi eri
    horisonttia samalle entrylle). `transfer_horizon_gws` on yksi lahde;
    tama sailyttaa plannerin oman 503-virheen tyhjalle ikkunalle."""
    covered = sorted({g.get("gw") for p in pool
                      for g in (p.get("gameweeks") or [])
                      if g.get("gw") is not None})
    gws = [g for g in covered if g >= start_gw][:horizon]
    if not gws:
        raise RateTeamError(503, "No projected gameweeks in range.")
    return gws


def _remaining_xp(player: dict, gws: list[int]) -> float:
    return sum(_gw_xp(player, g) for g in gws)


def _club_counts(squad: list[dict]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for p in squad:
        counts[p["club"]] = counts.get(p["club"], 0) + 1
    return counts


def plan_transfers(entry: int | None = None, gw: int | None = None,
                   players: list[int] | None = None, bank: float | None = None,
                   horizon: int = DEFAULT_HORIZON, ft: int = 1) -> dict:
    """Monen GW:n siirtosuunnitelma yhteisellä siirtomoottorilla.

    Per GW: `fpl_transfers.plan_gw` (XI-hyöty jäljellä olevalle horisontille,
    hit -4 ilman vapaata siirtoa, netto >= 0.5, kahden siirron yhdistelmähaku,
    luottamuspaino hintapriori-pelaajille). Sama funktio kuin rate-teamin
    suosituksissa ja mallin oman rungon freezessä."""
    if not 2 <= horizon <= 6:
        raise RateTeamError(400, "horizon must be between 2 and 6.")
    if not 0 <= ft <= FT_CARRY_MAX:
        raise RateTeamError(400, f"ft must be between 0 and {FT_CARRY_MAX}.")
    xp_data, bootstrap, pool, pool_by_id = build_context()
    squad_ids, _cap, bank_tenths, picks_gw = resolve_squad(
        bootstrap, entry, gw, players, None, bank)
    start_gw = planning_start_gw(picks_gw, pool, xp_data)
    gws = _horizon_gws(pool, start_gw, horizon)

    squad = [pool_by_id[i] for i in squad_ids if i in pool_by_id]
    if len(squad) < 11:
        raise RateTeamError(422, "Too few of the squad's players have xP "
                                 f"projections ({len(squad)}/15 matched).")
    missing = [i for i in squad_ids if i not in pool_by_id]

    # Baseline: ei siirtoja — sama XI-valinta per GW (penkkirotaatio sallittu)
    def _gw_score(sq: list[dict], g: int) -> float:
        xi = optimal_xi(sq)
        cap = max(xi, key=lambda p: _gw_xp(p, g))
        return sum(_gw_xp(p, g) for p in xi) + _gw_xp(cap, g)

    baseline_total = sum(_gw_score(squad, g) for g in gws)
    original_squad = list(squad)

    plan = []
    fts = ft
    bank_now = bank_tenths
    total_hits = 0.0
    for idx, g in enumerate(gws):
        gws_left = gws[idx:]
        step = _engine.plan_gw(squad, pool, bank_now, gws_left, fts,
                               max_moves=MAX_TRANSFERS_PER_GW)
        moves = []
        for m in step["moves"]:
            if m["hit"] > 0:
                total_hits += HIT_COST
            moves.append({
                "out": {"id": m["out"]["id"],
                        "web_name": m["out"]["web_name"],
                        "team_short": m["out"]["team_short"]},
                "in": {"id": m["in"]["id"],
                       "web_name": m["in"]["web_name"],
                       "team_short": m["in"]["team_short"]},
                "pos": m["pos"],
                # Painottamaton XI-hyöty jäljellä olevalle horisontille (näyttö).
                "gain_xp_remaining": round(m["gain"], 2),
                "hit": m["hit"],
                # 28.8: päätösluvut näkyviin, ei piiloon. confidence_weight < 1
                # = tulijan projektio nojaa hintaprioriin tai nousijaseuran
                # yhden ottelun ratingiin; pair = siirto on osa kahden siirron
                # yhdistelmää jonka hyöty on laskettu yhdessä.
                "gain_xp_weighted": round(m["gain_weighted"], 2),
                "confidence_weight": m["confidence_weight"],
                "pair": bool(m.get("pair")),
            })
        squad = step["squad"]
        bank_now = step["bank_tenths"]
        fts = step["ft_left"]
        xi = optimal_xi(squad)
        cap = max(xi, key=lambda p: _gw_xp(p, g))
        gw_xp_val = sum(_gw_xp(p, g) for p in xi) + _gw_xp(cap, g)
        plan.append({
            "gw": g,
            "transfers": moves,
            "roll_transfer": not moves,
            "captain": {"id": cap["id"], "web_name": cap["web_name"],
                        "gw_xp": round(_gw_xp(cap, g), 2)},
            "gw_xp": round(gw_xp_val, 2),
            "free_transfers_left": fts,
            "bank": round(bank_now / 10.0, 1),
        })
        fts = min(FT_CARRY_MAX, fts + 1)  # +1 FT seuraavaan GW:hen

    plan_total = sum(p["gw_xp"] for p in plan) - total_hits
    # Gate: suunnitelma ei koskaan alita ei-siirtoja-baselinea → hold-fallback
    # (rakenteellisesti epätodennäköinen koska jokainen siirto vaatii
    # MIN_GAIN-ylityksen hitin jälkeen, mutta vahditaan silti eksplisiittisesti)
    if plan_total < baseline_total:
        plan = []
        fts_h = ft
        for g in gws:
            xi = optimal_xi(original_squad)
            cap = max(xi, key=lambda p: _gw_xp(p, g))
            plan.append({
                "gw": g, "transfers": [], "roll_transfer": True,
                "captain": {"id": cap["id"], "web_name": cap["web_name"],
                            "gw_xp": round(_gw_xp(cap, g), 2)},
                "gw_xp": round(sum(_gw_xp(p, g) for p in xi)
                               + _gw_xp(cap, g), 2),
                "free_transfers_left": fts_h,
                "bank": round(bank_tenths / 10.0, 1),
            })
            fts_h = min(FT_CARRY_MAX, fts_h + 1)
        plan_total = baseline_total
        total_hits = 0.0

    # #63: hero-verdikti — suunnitelman netto (hitit jo vähennetty) vs kynnys.
    # Ei koskaan suosittele siirtoketjua jonka hyöty on kynnyksen alle.
    n_moves = sum(len(p["transfers"]) for p in plan)
    net_gain = round(plan_total - baseline_total, 2)
    # 29.8 k7: copy nimeaa kierrokset eika lukua, jotta samalla ruudulla ei ole
    # kahta eri lukua joita molempia kutsutaan sanalla "the horizon".
    _span = f"GW{gws[0]}-GW{gws[-1]}" if len(gws) > 1 else f"GW{gws[0]}"
    if n_moves == 0:
        hv_message = (f"No move the model checked improves your team over "
                      f"{_span}.")
    elif net_gain < HOLD_THRESHOLD_XP:
        hv_message = (f"Your best plan gains only {net_gain:+.1f} xP over "
                      f"{_span} (hits included) - holding is the play.")
    else:
        plural = "s" if n_moves != 1 else ""
        hv_message = (f"Recommended: {n_moves} transfer{plural} for "
                      f"{net_gain:+.1f} xP net over {_span}.")
    hold_verdict = {
        "verdict": ("hold" if n_moves == 0 or net_gain < HOLD_THRESHOLD_XP
                    else "transfer"),
        "best_move_gain_xp": net_gain if n_moves else None,
        "horizon_gws": len(gws),
        "gw_from": gws[0],
        "gw_to": gws[-1],
        "threshold_xp": HOLD_THRESHOLD_XP,
        "transfers_planned": n_moves,
        # HOLD-VERDICT-BEST-PLAN-COPY (portti 29.8): hittien MAARA koko
        # suunnitelmassa. Uusi kentta, ei rate-teamin hit_applied_xp (se on
        # aina 0 tai tasan 4.0 = yksi hitti); vanhat klientit tulostaisivat
        # siita "-4" kun oikea on -8 tai -12.
        "hits_taken": int(round(total_hits / HIT_COST)) if HIT_COST else 0,
        "message": hv_message,
    }

    # 28.8: entry-moodissa FPL näyttää edellisen kierroksen rungon deadlineen
    # asti. Kerrotaan se rakenteisena, jotta klientti voi ohjata
    # manuaalisyöttöön sen sijaan että käyttäjä päättelee tuotteen olevan rikki.
    _dl_gw = xp_data["meta"].get("deadline_gameweek")
    _stale = (players is None and picks_outdated(picks_gw, _dl_gw))
    # Vakaat kentat, ei proosaa (linjaus 23.8: klientti renderoi i18n:sta).
    # `deadline_gw` on sama lahde kuin rate-teamin picks_outdated, jotta
    # "GW{n+1}" ei ole klientin arvaus.
    squad_source = {
        "mode": "manual" if players else "entry",
        "gw": picks_gw,
        "deadline_gw": _dl_gw if isinstance(_dl_gw, int) else None,
        "stale": bool(_stale),
    }

    return {
        "meta": {
            "entry": entry, "start_gw": gws[0], "horizon": len(gws),
            "generated_at": xp_data["meta"].get("generated_at"),
            # Julkaisuportti 28.8: kolme painotusehtoa auki (vastaa
            # fpl_transfers.confidence_weight() rivi rivilta), luvun status
            # sanottu (oletus, ei kalibroitu), naytetyt luvut painottamattomia.
            # "optimum" on ratkaisijasanastoa jonka Ville torjui 28.7.
            "heuristic": ("gain measured on the starting XI over the remaining "
                          f"horizon, max {MAX_TRANSFERS_PER_GW} transfers/GW, "
                          "single moves and two-move swaps both checked, hit -4 "
                          "without a free transfer, FT carry max "
                          f"{FT_CARRY_MAX}. For each player you could sell it "
                          f"only looks at the {_engine.TOP_CANDIDATES_PER_POS} "
                          "best projected replacements in that position your "
                          "budget allows, so it doesn't try every possible plan. "
                          "When it compares moves it counts "
                          "three groups at "
                          f"{_engine.LOW_CONFIDENCE_WEIGHT:.2f} of their "
                          "projection: players with no Premier League history, "
                          "players whose minutes are still estimated from price, "
                          "and everyone at a promoted club. The xP numbers shown "
                          f"are undiscounted, and the {_engine.LOW_CONFIDENCE_WEIGHT:.2f} "
                          "is a fixed default, not calibrated against results "
                          "yet."),
            # HEURISTIC-I18N (29.8): vakaat parametrit klientin i18n:lle
            # (linjaus 23.8: proosa klientista, parametrit backendista).
            # `heuristic`-proosa jaa vanhoille klienteille ja SPA:lle.
            "heuristic_params": {
                "max_transfers_per_gw": MAX_TRANSFERS_PER_GW,
                "hit_cost": 4,
                "ft_carry_max": FT_CARRY_MAX,
                "top_candidates_per_pos": _engine.TOP_CANDIDATES_PER_POS,
                "low_confidence_weight": round(float(_engine.LOW_CONFIDENCE_WEIGHT), 2),
                "calibrated": False,
            },
            "note": "GoalIQ model projections - for fun and planning, "
                    "not betting advice.",
            "engine": "transfers.v2",
            "squad_source": squad_source,
        },
        "hold_verdict": hold_verdict,
        "plan": plan,
        "totals": {
            "plan_xp": round(plan_total, 2),
            "baseline_xp_no_transfers": round(baseline_total, 2),
            "net_gain": round(plan_total - baseline_total, 2),
            "hits_taken": int(total_hits / HIT_COST),
        },
        "missing_ids": missing,
    }


def captain_picker(entry: int | None = None, gw: int | None = None,
                   players: list[int] | None = None) -> dict:
    """Top-3 kapteeniehdokasta + differential-kapteeni (EO ≤ 10 %)."""
    xp_data, bootstrap, pool, pool_by_id = build_context()
    squad_ids, _cap, _bank, picks_gw = resolve_squad(
        bootstrap, entry, gw, players, None, None)
    target_gw = clamp_gw_to_projections(picks_gw, pool, xp_data)
    squad = [pool_by_id[i] for i in squad_ids if i in pool_by_id]
    if len(squad) < 11:
        raise RateTeamError(422, "Too few projected players in the squad.")
    xi = optimal_xi(squad)
    # Addendum 2: serve-time-portti. XI:n valinta pysyy ennallaan (runko on
    # kayttajan oma), mutta LIVE-lipulla sivussa oleva ei kelpaa kapteeniksi.
    # Jos portti tyhjentaisi listan (ei kaytannossa mahdollista), palataan
    # suodattamattomaan XI:hin — vastaus ei koskaan katoa.
    dropped = apply_availability_gate(xi, bootstrap)[1]
    dropped_ids = {r["id"] for r in dropped}
    gated_xi = [p for p in xi if p["id"] not in dropped_ids] or xi
    ranked = sorted(gated_xi, key=lambda p: _gw_xp(p, target_gw), reverse=True)

    def _fmt(p):
        return {"id": p["id"], "web_name": p["web_name"],
                "team_short": p["team_short"],
                "gw_xp": round(_gw_xp(p, target_gw), 2),
                "owned_pct": p.get("owned_pct")}

    top3 = [_fmt(p) for p in ranked[:3]]
    for i, t in enumerate(top3):
        t["gap_to_top"] = round(top3[0]["gw_xp"] - t["gw_xp"], 2) if i else 0.0
    diff = next((p for p in ranked
                 if (p.get("owned_pct") or 100.0) <= CAPTAIN_DIFFERENTIAL_EO),
                None)
    return {
        "meta": {"gw": target_gw,
                 "generated_at": xp_data["meta"].get("generated_at"),
                 "availability_gate": {
                     "checked": True,
                     "dropped": dropped,
                     "note": AVAILABILITY_GATE_NOTE,
                 }},
        "top3": top3,
        "differential": (_fmt(diff) if diff and diff["id"] not in
                         {t["id"] for t in top3[:1]} else None),
    }


def _pct_ranks(values: list[float]) -> list[float]:
    """Persentiililuvut 0–100 keskiarvotetuin tasapelein (ilman numpyä)."""
    n = len(values)
    if n == 1:
        return [50.0]
    order = sorted(range(n), key=lambda i: values[i])
    pct = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        p = 100.0 * ((i + j) / 2.0) / (n - 1)
        for k in range(i, j + 1):
            pct[order[k]] = p
        i = j + 1
    return pct


def _model_vs_crowd(pool: list[dict]) -> dict[int, tuple[float, float, float]]:
    """#71: pelaaja-id → (model_pct, crowd_pct, delta), positio-sisäisesti.

    model_pct = xp_horizon_total-persentiili oman position sisällä,
    crowd_pct = owned_pct-persentiili samoin. delta = model − crowd:
    positiivinen = malli arvostaa korkeammalle kuin joukko omistaa.
    """
    out: dict[int, tuple[float, float, float]] = {}
    for etype in {p["element_type"] for p in pool}:
        grp = [p for p in pool if p["element_type"] == etype]
        model = _pct_ranks([p["xp_horizon_total"] for p in grp])
        crowd = _pct_ranks([(p.get("owned_pct") or 0.0) for p in grp])
        for p, m, c in zip(grp, model, crowd):
            m, c = round(m, 1), round(c, 1)
            out[p["id"]] = (m, c, round(m - c, 1))
    return out


def differential_finder(max_ownership: float = DIFFERENTIAL_MAX_OWNERSHIP,
                        pos: str | None = None) -> dict:
    """Matala EO × korkea xP -listaus koko poolista (ei vaadi entryä).

    #71: mukana myös model_vs_crowd-osio — missä malli on ERI mieltä kuin
    joukko (käänteinen "seuraa eliittiä": model_backs = malli edellä joukkoa,
    crowd_backs = template-pelaajat joita malli ei rankkaa omistuksen tasolle).
    """
    if not 0 < max_ownership <= 100:
        raise RateTeamError(400, "max_ownership must be in (0, 100].")
    pos_by_name = {v: k for k, v in POS_NAME.items()}
    if pos is not None and pos not in pos_by_name:
        raise RateTeamError(400, f"pos must be one of {sorted(pos_by_name)}.")
    xp_data, bootstrap, pool, _by_id = build_context()
    # Persentiilit lasketaan TAYDESTA poolista (vertailukohta ei saa heilua
    # yksittaisen loukkaantumisen mukana), vasta listat suodatetaan.
    mvc = _model_vs_crowd(pool)
    pool, dropped = apply_availability_gate(pool, bootstrap)

    def _row(p):
        m, c, d = mvc[p["id"]]
        return {
            "id": p["id"], "web_name": p["web_name"],
            "team_short": p["team_short"], "pos": POS_NAME[p["element_type"]],
            "price": p["price"] / 10.0, "owned_pct": p["owned_pct"],
            "xp_per_gw": round(p["xp_per_gw"], 2),
            "xp_horizon_total": round(p["xp_horizon_total"], 2),
            "model_pct": m, "crowd_pct": c, "model_vs_crowd_delta": d,
        }

    cands = [p for p in pool
             if (p.get("owned_pct") or 0.0) <= max_ownership
             and (pos is None or p["element_type"] == pos_by_name[pos])]
    cands.sort(key=lambda p: p["xp_horizon_total"], reverse=True)

    # #71: model-vs-crowd-listat EIVÄT noudata max_ownership-filtteriä
    # (crowd_backs on määritelmällisesti korkea-EO), pos-filtteri noudatetaan.
    scoped = [p for p in pool
              if pos is None or p["element_type"] == pos_by_name[pos]]
    backs = sorted(
        (p for p in scoped
         if mvc[p["id"]][2] >= MODEL_VS_CROWD_DELTA_MIN
         and mvc[p["id"]][0] >= MODEL_VS_CROWD_MIN_MODEL_PCT),
        key=lambda p: mvc[p["id"]][2], reverse=True)
    fades = sorted(
        (p for p in scoped
         if mvc[p["id"]][2] <= -MODEL_VS_CROWD_DELTA_MIN
         and mvc[p["id"]][1] >= MODEL_VS_CROWD_MIN_CROWD_PCT),
        key=lambda p: mvc[p["id"]][2])

    return {
        "meta": {"max_ownership": max_ownership, "pos": pos,
                 "generated_at": xp_data["meta"].get("generated_at"),
                 "horizon_gw": xp_data["meta"].get("horizon_gw"),
                 "availability_gate": {"checked": True, "dropped": dropped,
                                       "note": AVAILABILITY_GATE_NOTE}},
        "players": [_row(p) for p in cands[:DIFFERENTIAL_TOP_N]],
        "model_vs_crowd": {
            "note": ("delta = model xP percentile minus ownership percentile, "
                     "within position. Positive: the model rates the player "
                     "higher than the crowd owns him. Ignores max_ownership."),
            "model_backs": [_row(p) for p in backs[:MODEL_VS_CROWD_TOP_N]],
            "crowd_backs": [_row(p) for p in fades[:MODEL_VS_CROWD_TOP_N]],
        },
    }


def compare_players(player_ids: list[int]) -> dict:
    """2–4 pelaajan rinnakkaisvertailu + suora kanta xP-erolla.

    28.7: katto 3 -> 4. Neljä on realistinen kun mietit kahta siirtoa samalla
    kertaa, ja se on myös se lupaus jolla kilpailijat myyvät vertailutyökalua.
    Verdict on aina kahden kärjen välinen ero, joten laajennus ei muuta
    olemassa olevien 2:n ja 3:n vastauksia millään tavalla.
    """
    if not 2 <= len(player_ids) <= 4:
        raise RateTeamError(400, "compare takes 2 to 4 player IDs.")
    if len(set(player_ids)) != len(player_ids):
        raise RateTeamError(400, "compare IDs must be distinct.")
    xp_data, _bootstrap, _pool, pool_by_id = build_context()

    # 6.8 compare-V2 (Villen idea): pelipaikkarelevantit RAAKAstatit xP-osuuksien
    # rinnalle — DEF saa SAMAN DefCon hit-raten jota leaders-lista käyttää
    # (rank_defcon_season, nimittäjä = startit), hyökkääjät xG/xA per 90
    # edelliskaudelta. Defensiivinen: artefaktin puute ei kaada vertailua,
    # mutta puute näkyy metassa (ei hiljaista katoamista).
    dc_by_id: dict[int, dict] = {}
    dc_basis_season = None
    try:
        from src.models.fpl_leaders import load_defcon_gw, rank_defcon_season
        _dc = rank_defcon_season(load_defcon_gw(), pos=None, top_n=400)
        dc_by_id = {r["id"]: r for r in _dc.get("players", [])}
        dc_basis_season = _dc.get("meta", {}).get("basis_season")
    except Exception:
        pass

    rows = []
    for pid in player_ids:
        p = pool_by_id.get(pid)
        if p is None:
            raise RateTeamError(404, f"Player {pid} has no xP projection.")
        row = {
            "id": p["id"], "web_name": p["web_name"],
            "team_short": p["team_short"], "pos": POS_NAME[p["element_type"]],
            "price": p["price"] / 10.0, "owned_pct": p["owned_pct"],
            "xmins": p.get("xmins"),
            "predicted_starts": p.get("predicted_starts"),
            # 29.8 COMPARE-START-PCT: p_start (0..1) on Start%:n ainoa lahde
            # kaikilla pinnoilla (27.8 start_pct = floor(p_start*100+0.5)).
            # predicted_starts on jo kerran pyoristetty (91.5) -> SPA/mobiilin
            # Math.round siita antoi 92 kun sivut nayttivat 91.
            "p_start": p.get("p_start"),
            "minutes_confidence": p.get("minutes_confidence"),
            "xp_per_gw": round(p["xp_per_gw"], 2),
            "xp_horizon_total": round(p["xp_horizon_total"], 2),
            "components": p.get("components"),
            "components_gw": p.get("components_gw"),
        }
        ls = p.get("last_season") or {}
        mins = ls.get("minutes") or 0
        # 450 min alaraja: alle viiden pelin per-90 on kohinaa eikä sitä
        # esitetä vertailulukuna (sama henki kuin leaders-poolisäännöissä).
        if mins >= 450 and ls.get("xg") is not None:
            row["xg90_prev"] = round(float(ls["xg"]) * 90.0 / mins, 2)
            row["xa90_prev"] = round(float(ls.get("xa") or 0.0) * 90.0 / mins, 2)
            row["prev_season"] = ls.get("season")
        d = dc_by_id.get(p["id"])
        if d is not None:
            row["defcon_hit_rate_pct"] = d.get("hit_rate_pct")
            row["defcon_dc_per_game"] = d.get("dc_per_game")
        rows.append(row)
    ranked = sorted(rows, key=lambda r: r["xp_horizon_total"], reverse=True)
    margin = round(ranked[0]["xp_horizon_total"] - ranked[1]["xp_horizon_total"], 2)
    verdict = {
        "pick": {"id": ranked[0]["id"], "web_name": ranked[0]["web_name"]},
        "margin_xp_horizon": margin,
        "text": (f"{ranked[0]['web_name']} projects {margin} xP more than "
                 f"{ranked[1]['web_name']} over the horizon."
                 if margin >= 0.5 else
                 f"Too close to call - {ranked[0]['web_name']} edges it by "
                 f"{margin} xP over the horizon."),
    }
    return {
        "meta": {"generated_at": xp_data["meta"].get("generated_at"),
                 "horizon_gw": xp_data["meta"].get("horizon_gw"),
                 # V2: mistä raakastatit tulevat — frontend näyttää katteen
                 # eikä myy edelliskauden lukua nykykauden mittauksena.
                 "defcon_basis_season": dc_basis_season,
                 "defcon_available": bool(dc_by_id)},
        "players": rows,
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# ROWAN-REPLACEMENTS (2.9.2026): "who replaces X"
# ---------------------------------------------------------------------------
# Luojan (Rowan, 74k katselua GoalIQ:n 5 GW:n xPts-ketjulla 1.9) itse
# maarittelema muoto: Player -> same price bracket -> next 5 GWs -> top 5
# replacements, with xP, ownership and a quick reason for each.
#
# Syy on YKSI projektiosta luettu asia per nimi, ei generoitua tekstia.
# Kolme lajia, tassa jarjestyksessa (ensimmainen joka tayttyy).
# PORTTI 2.9: mitattu koko poolista 5 GW:n ikkunalla: fixture_peak laukeaa
# 4/513 pelaajalle ja minutes vaatii lahtijan p_start <= 0.70, joten xp_gap
# on kaytannossa oletustila. Silla EI ole tekstia: `vs`-sarake kantaa saman
# luvun jo, ja sama luku kahdesti rivilla oli portin blokki. Copy ei saa
# luvata "kolmea syyta" (tasavertainen lista kuolleista haaroista).
#   minutes       korvaaja on projektiossa selvasti varmempi aloittaja kuin
#                 lahtija (p_start >= 0.85 ja lahtijan p_start <= 0.70)
#   fixture_peak  yksi kierros ikkunassa on selvasti muita parempi
#                 (>= 1.3 x korvaajan oma ikkunakeskiarvo ja >= 4.0 xP)
#   xp_gap        ikkunan xP-ero lahtijaan (aina laskettavissa, myos
#                 negatiivinen: lista on hintahaarukan paras viisikko, ei
#                 lupaus etta jokainen on lahtijaa parempi)
# Jokainen rivi kantaa lisaksi xp_gap_vs_target:in erikseen, jotta ketjun
# kirjoittaja voi kayttaa eroa vaikka syy olisi toinen.
REPLACEMENTS_TOP_N = 5
REPLACEMENTS_MAX_TOP_N = 10
REPLACEMENTS_DEFAULT_GWS = 5
REPLACEMENTS_DEFAULT_BRACKET = 0.5   # miljoonaa, +-
REPLACEMENTS_MAX_BRACKET = 3.0
REASON_MINUTES_MIN_P_START = 0.85
REASON_MINUTES_MAX_TARGET_P_START = 0.70
REASON_MARGIN_XP = 0.1   # esitystarkkuus: alle taman ero ei nay yhdella desimaalilla


def _gw_opponents_text(player: dict, gw: int) -> str:
    """'COV (H)' / 'MUN (A), IPS (H)' / 'blank'. Sama sisalto kuin
    gameweeks[].opponents, vain tekstiksi tiivistettyna."""
    for g in player.get("gameweeks") or []:
        if g.get("gw") == gw:
            opps = g.get("opponents") or []
            if not opps:
                return "blank"
            return ", ".join(
                "{} ({})".format(o.get("opp") or "?", o.get("venue") or "?")
                for o in opps)
    return "blank"


def _replacement_reason(cand: dict, target: dict, gws: list[int]) -> dict:
    n = len(gws)
    cp, tp = cand.get("p_start"), target.get("p_start")
    if (isinstance(cp, (int, float)) and isinstance(tp, (int, float))
            and cp >= REASON_MINUTES_MIN_P_START
            and tp <= REASON_MINUTES_MAX_TARGET_P_START):
        # PORTTI 2.9 k3: 100 % on varmuusvaite jaettavassa kuvassa (6 pelaajaa
        # poolissa p_start == 1.0) -> katto 99. "of starts" erottaa luvun
        # FPL:n "75% chance of playing" -lipusta joka on samalla ruudulla.
        c_pct, t_pct = min(99, int(cp * 100 + 0.5)), int(tp * 100 + 0.5)
        return {
            "kind": "minutes",
            "value": c_pct,
            "text": "projected to start {}% of games, {} {}% of starts".format(
                c_pct, target["web_name"], t_pct),
        }
    # Ville 2.9 ilta: syy nakyi vasta 6 GW:n ikkunalla, koska xp_gap-haara
    # (lahes joka rivi) ei kantanut tekstia. Rowan pyysi syyn JOKA riville.
    # Ratkaisu joka ei toista vs-saraketta: rivin paras kierros ikkunassa
    # (vastustaja, koti/vieras, xP) on aina eri fakta kuin ero lahtijaan.
    # `peak` kertoo onko se selvasti muita parempi (entinen fixture_peak).
    per_gw = sorted(((_gw_xp(cand, g), -g) for g in gws), reverse=True)
    best_xp, neg_gw = per_gw[0]
    best_gw = -neg_gw
    second = per_gw[1][0] if len(per_gw) > 1 else 0.0
    # PORTTI 2.9 k3: mitattu poolista (513 rivia, GW3-7): 7 %:lla paras viikko on
    # TASAN toisen kanssa ja 32 %:lla ero on alle esitystarkkuuden (0,1 xP).
    # "the biggest week" ei silloin pida naytetyilla luvuilla -> kaksi haaraa.
    if best_xp - second >= REASON_MARGIN_XP:
        return {
            "kind": "fixture",
            "value": round(best_xp, 2),
            "gw": best_gw,
            "text": "best week GW{} {}, {:.1f} xP".format(
                best_gw, _gw_opponents_text(cand, best_gw), best_xp),
        }
    lo = min(x for x, _ in per_gw)
    return {
        "kind": "flat",
        "value": round(best_xp, 2),
        "gw": best_gw,
        "text": "no standout week, {:.1f}-{:.1f} xP".format(lo, best_xp),
    }


def replacements(player_id: int, gws: int = REPLACEMENTS_DEFAULT_GWS,
                 bracket: float = REPLACEMENTS_DEFAULT_BRACKET,
                 top_n: int = REPLACEMENTS_TOP_N) -> dict:
    """Top-N korvaajaa samasta pelipaikasta ja hintahaarukasta (+-bracket m),
    ikkunan xP:lla jarjestettyna. Ei vaadi entrya: kysymys on "kuka korvaa
    X:n", ei "kuka korvaa X:n minun rungossani" (se on planner)."""
    if not 1 <= gws <= 6:
        raise RateTeamError(400, "gws must be between 1 and 6.")
    if not 0 <= bracket <= REPLACEMENTS_MAX_BRACKET:
        raise RateTeamError(400, "bracket must be between 0 and {}.".format(
            REPLACEMENTS_MAX_BRACKET))
    if not 1 <= top_n <= REPLACEMENTS_MAX_TOP_N:
        raise RateTeamError(400, "top must be between 1 and {}.".format(
            REPLACEMENTS_MAX_TOP_N))
    xp_data, bootstrap, pool, by_id = build_context()
    target = by_id.get(player_id)
    if target is None:
        raise RateTeamError(404, "Player {} has no xP projection.".format(player_id))
    # Ikkuna = kierrokset joihin siirto voi VIELA vaikuttaa (sama lahde kuin
    # rate-team ja planner 29.8 lahtien). Kesken olevaa kierrosta ei lasketa.
    from src.models.fpl_rate_team import _resolve_gw, transfer_horizon_gws
    window = transfer_horizon_gws(pool, xp_data, _resolve_gw(bootstrap, None), cap=gws)
    if not window:
        raise RateTeamError(503, "No projected gameweeks in range.")
    # Serve-time saatavuusportti: elavassa bootstrapissa sivuun merkitty ei
    # ole korvaaja. Lahtijaa ei portiteta — hanen sivussaolonsa on usein juuri
    # kysymyksen syy.
    live_pool, dropped = apply_availability_gate(pool, bootstrap)
    same_pos = [p for p in live_pool
                if p["id"] != target["id"]
                and p["element_type"] == target["element_type"]]

    def _in_bracket(b: float) -> tuple[int, int, list[dict]]:
        lo_ = target["price"] - int(round(b * 10))
        hi_ = target["price"] + int(round(b * 10))
        return lo_, hi_, [p for p in same_pos if lo_ <= p["price"] <= hi_]

    # Hintahaarukan levennys: hintaskaalan paassa (Bruno 12.0m, Haaland
    # 15.5m) +-0.5m on tyhja. Levennetaan 0.5m askelin kunnes kandidaatteja
    # on vahintaan top_n tai katto tulee vastaan, ja meta kertoo REHELLISESTI
    # seka pyydetyn etta kaytetyn haarukan. Ei tehda hiljaa.
    bracket_used = bracket
    lo, hi, cands = _in_bracket(bracket_used)
    while len(cands) < top_n and bracket_used < REPLACEMENTS_MAX_BRACKET:
        bracket_used = min(REPLACEMENTS_MAX_BRACKET, round(bracket_used + 0.5, 1))
        lo, hi, cands = _in_bracket(bracket_used)
    scored = sorted(((_remaining_xp(p, window), p) for p in cands),
                    key=lambda t: (-t[0], t[1]["price"], t[1]["web_name"]))
    target_total = _remaining_xp(target, window)

    def _row(total: float, p: dict) -> dict:
        return {
            "id": p["id"], "web_name": p["web_name"],
            "team_short": p["team_short"], "pos": POS_NAME[p["element_type"]],
            "price": p["price"] / 10.0, "owned_pct": p["owned_pct"],
            "xp_window": round(total, 2),
            "xp_gap_vs_target": round(total - target_total, 2),
            "gameweeks": [{"gw": g, "opponents": _gw_opponents_text(p, g),
                           "xp": round(_gw_xp(p, g), 2)} for g in window],
            "p_start": p.get("p_start"),
            "status": p.get("status") or "a",
            "chance_next": p.get("chance_next"),
            "news": (p.get("news") or "")[:140],
            "reason": _replacement_reason(p, target, window),
        }

    return {
        "meta": {
            "generated_at": xp_data["meta"].get("generated_at"),
            "gws": window,
            "bracket_requested": bracket, "bracket": bracket_used,
            "bracket_widened": bracket_used != bracket,
            "price_min": lo / 10.0, "price_max": hi / 10.0,
            "candidates_in_bracket": len(cands),
            "availability_gate": {"checked": True, "dropped": dropped,
                                  "note": AVAILABILITY_GATE_NOTE},
            "reason_note": ("Reason is the row's best week in the window, or "
                            "the range when no week stands out, or the starts "
                            "gap when the player going out is a minutes doubt. "
                            "Ownership is FPL's selected-by percentage. xP is "
                            "the GoalIQ projection over GW{}-GW{}, not a single "
                            "gameweek.".format(window[0], window[-1])),
        },
        "target": {
            "id": target["id"], "web_name": target["web_name"],
            "team_short": target["team_short"],
            "pos": POS_NAME[target["element_type"]],
            "price": target["price"] / 10.0, "owned_pct": target["owned_pct"],
            "xp_window": round(target_total, 2),
            "p_start": target.get("p_start"),
            "status": target.get("status") or "a",
            "chance_next": target.get("chance_next"),
            "news": (target.get("news") or "")[:140],
        },
        "players": [_row(total, p) for total, p in scored[:top_n]],
    }
