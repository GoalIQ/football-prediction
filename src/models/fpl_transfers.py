"""Yksi siirtomoottori kaikille pinnoille (PLANNER-FREEZE-DIVERGENCE, 28.8.2026).

Mitattu 28.8 livesta samalla 15:lla (entry 116920, pankki 0.0, ft 0):
  - freeze (`transfer_suggestions`, 6 GW, hit jos hyoty > 4.0):
        Senesi -> White (4.34, hit), Kadioglu -> De Cuyper (8.94, hit)
  - /api/fantasy/plan (`fpl_planner._best_transfer`, oma greedy, RAAKAEROTUS
    eika XI-hyoty, horizon 3, TOP 8): horizon 3 -> "holding is the play",
    horizon 6 -> Kadioglu -> Mendy + Steele -> Tzolakis (HUL price-prior)
  - rate-team naytti GW1-rungon (FPL piilottaa siirrot deadlineen).
Kolme pintaa, kolme eri vastausta samaan kysymykseen. Freeze-skriptin
docstring vaitti kayttavansa "tasmalleen samaa funktiota jolla tuote
suosittelee siirtoja" - se piti paikkansa rate-teamille mutta ei plannerille.

Tama moduuli on se yksi funktio. Saannot, samat kaikille:
  1. Hyotymitta = AVAUSKOKOONPANON xP-muutos (optimal XI ennen/jalkeen)
     jaljella olevalle horisontille. Ei pelaajien raakaerotus (28.7-oppi:
     penkkivahdin vaihto ei tuota pisteita vaikka raakaero on 17).
  2. Hit-saanto: netto = hyoty - 4.0 kun vapaita siirtoja ei ole. Siirto
     kelpaa kun netto >= MIN_GAIN_PER_TRANSFER (0.5). Sama kynnys vapaalle
     siirrolle: alle 0.5 xP:n siirto ei ole vaivan arvoinen.
  3. Yhdistelmahaku: greedy ei nae "vapauta rahaa ensin" -paria (De Cuyper
     4.6 ei mahdu Kadioglun 4.5 tilalle ennen kuin Senesi -> White vapauttaa
     0.5). Kahden siirron parit haetaan erikseen ja pari voittaa kun sen
     netto ylittaa parhaan yksittaisen siirron neton vahintaan MIN_GAIN:lla.
  4. Luottamuspaino: pelaaja jonka projektio nojaa hintaprioriin tai
     yhden ottelun joukkueratingiin (`data_basis == "no_history"`,
     `minutes_source == "price_prior"` tai nousijaseura, ks.
     `confidence_weight`) saa PAATOKSISSA kertoimen LOW_CONFIDENCE_WEIGHT.
     Nayttoluvut (delta_xp_*) ovat painottamattomia, ja kerroin kerrotaan
     vastauksessa kenttana `confidence_weight`, ei piilotettuna.
     `minutes_confidence` EI kelpaa ehdoksi: 28.8 artefaktissa se on "low"
     kaikilla 516 pelaajalla (kausi on yhden kierroksen vanha), joten se ei
     erottele ketaan.

Painon arvo 0.75 on OLETUS, ei mittaus: `data/fpl_xp_gw_accuracy.json`
kirjaa GW1:n MAE:n vain positioittain (DEF 1.92 .. GKP 1.35), ei
promoted-vs-muut-jakoa, joten kalibrointiin ei viela ole dataa.
TODO(kalibrointi): kun 3+ kierrosta on gradattu, laske MAE erikseen
price-prior-pelaajille ja aseta paino niiden yliarvioinnin suhteessa.
"""
from __future__ import annotations

import itertools

from src.models.fpl_rate_team import (
    HIT_COST_XP, MAX_PER_CLUB, POS_NAME, RateTeamError, _best_split, _gw_xp,
)

MIN_GAIN_PER_TRANSFER = 0.5
MAX_TRANSFERS_PER_GW = 2
TOP_CANDIDATES_PER_POS = 12
LOW_CONFIDENCE_WEIGHT = 0.75
# Yhdistelmahaun XI-arviointien katto per kutsu: bracketing pudottaa lahes
# kaikki parit, mutta katto pitaa API:n vasteajan ennustettavana.
MAX_PAIR_EVALS = 2500


def confidence_weight(p: dict) -> float:
    """1.0 todistetulle pelaajalle, LOW_CONFIDENCE_WEIGHT hintapriorille.

    Ehto (mika tahansa riittaa): ei Valioliigahistoriaa (`data_basis ==
    "no_history"`), minuutit puhtaasta hintapriorista (`minutes_source ==
    "price_prior"`) tai nousijaseura (`is_promoted`, poolin annotaatio
    xP-artefaktin team_confidence-lohkosta: rating on sovitettu yhteen
    otteluun). Mendy ja Tzolakis (HUL) osuvat viimeiseen: heidan xP:nsa
    rakentuu joukkuetason CS-todennakoisyydesta jolla ei ole viela
    mittaushistoriaa, ja juuri he nousivat vanhan plannerin karkeen.
    """
    if p.get("data_basis") == "no_history":
        return LOW_CONFIDENCE_WEIGHT
    if p.get("minutes_source") == "price_prior":
        return LOW_CONFIDENCE_WEIGHT
    if p.get("is_promoted"):
        return LOW_CONFIDENCE_WEIGHT
    return 1.0


def optimal_xi_by_key(squad: list[dict], key) -> list[dict]:
    """Paras laillinen XI mielivaltaisella avainfunktiolla (esim. yhden
    kierroksen xP). Sama muodostelmalogiikka kuin `_best_split`."""
    scored = []
    for p in squad:
        q = dict(p)
        q["xp_horizon_total"] = float(key(p))
        scored.append(q)
    split = _best_split(scored)
    if split is None:
        raise RateTeamError(
            400, "Squad cannot form a legal XI (need 1 GKP, 3+ DEF, 2+ MID, "
                 "1+ FWD from 15 players).")
    ids = [p["id"] for p in split[0]]
    by_id = {p["id"]: p for p in squad}
    return [by_id[i] for i in ids]


def window_xp(p: dict, gws: list[int] | None) -> float:
    """Pelaajan xP annetulle ikkunalle; None = koko horisontti (artefaktin
    valmis summa, jotta rate-teamin luvut eivat liiku pyoristyksesta)."""
    if gws is None:
        return float(p.get("xp_horizon_total") or 0.0)
    return sum(_gw_xp(p, g) for g in gws)


def _scored(players: list[dict], gws: list[int] | None, weighted: bool) -> list[dict]:
    out = []
    for p in players:
        q = dict(p)
        v = window_xp(p, gws)
        if weighted:
            v *= confidence_weight(p)
        q["xp_horizon_total"] = v
        out.append(q)
    return out


def xi_value(squad: list[dict], gws: list[int] | None, weighted: bool = False) -> float:
    """Parhaan laillisen XI:n xP annetulla ikkunalla (ja painolla)."""
    split = _best_split(_scored(squad, gws, weighted))
    if split is None:
        raise RateTeamError(
            400, "Squad cannot form a legal XI (need 1 GKP, 3+ DEF, 2+ MID, "
                 "1+ FWD from 15 players).")
    return sum(p["xp_horizon_total"] for p in split[0])


def _club_counts(squad: list[dict]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for p in squad:
        counts[p["club"]] = counts.get(p["club"], 0) + 1
    return counts


def _clubs_ok_after(clubs: dict[int, int], outs: list[dict], ins: list[dict]) -> bool:
    """Klubiraja vaihdon JALKEEN, tarkistettuna vain tulijoiden seuroille:
    rungossa jo oleva rike (entry-moodissa mahdollinen, FPL sallii yli 3 vain
    virhetilanteessa) ei saa estaa kaikkia siirtoja."""
    c = dict(clubs)
    for o in outs:
        c[o["club"]] = c.get(o["club"], 0) - 1
    for i in ins:
        c[i["club"]] = c.get(i["club"], 0) + 1
    return all(c.get(i["club"], 0) <= MAX_PER_CLUB for i in ins)


def _apply(squad: list[dict], outs: list[dict], ins: list[dict]) -> list[dict]:
    out_ids = {o["id"] for o in outs}
    return [p for p in squad if p["id"] not in out_ids] + list(ins)


def _move(out_p: dict, in_p: dict, gain: float, gain_w: float, hit: float) -> dict:
    return {
        "out": out_p, "in": in_p,
        "gain": round(gain, 4),              # painottamaton XI-hyoty (naytto)
        "gain_weighted": round(gain_w, 4),   # paatosluku
        "hit": hit,
        "net": round(gain_w - hit, 4),
        "confidence_weight": confidence_weight(in_p),
        "pos": POS_NAME[out_p["element_type"]],
    }


def single_moves(squad: list[dict], pool: list[dict], bank_tenths: int,
                 gws: list[int] | None, *, top_k: int = 5,
                 top_per_pos: int = TOP_CANDIDATES_PER_POS) -> list[dict]:
    """Parhaat yksittaiset siirrot painotetulla XI-hyodylla, laskevasti.

    Eksakti kandidaattijoukon sisalla: raakaerotus on XI-hyodyn ylaraja
    (uusi XI:n tulokas voidaan aina korvata lahtijalla -> vanha laillinen
    XI), joten listaa taydennetaan raakaerotuksen jarjestyksessa ja
    lopetetaan kun ylaraja alittaa listan heikoimman todellisen hyodyn.
    Kandidaatit per lahtija: saman position top_per_pos parasta
    painotetulla ikkuna-xP:lla joihin budjetti riittaa (bank + lahtijan
    hinta), max 3/klubi vaihdon jalkeen.
    """
    squad_ids = {p["id"] for p in squad}
    clubs = _club_counts(squad)
    base = xi_value(squad, gws, weighted=True)
    base_plain = xi_value(squad, gws, weighted=False)
    wval = {p["id"]: window_xp(p, gws) * confidence_weight(p) for p in pool}
    for p in squad:
        wval.setdefault(p["id"], window_xp(p, gws) * confidence_weight(p))
    by_pos: dict[int, list[dict]] = {1: [], 2: [], 3: [], 4: []}
    for p in pool:
        if p["id"] not in squad_ids:
            by_pos[p["element_type"]].append(p)
    for t in by_pos:
        by_pos[t].sort(key=lambda p: wval[p["id"]], reverse=True)

    cands: list[tuple[float, dict, dict]] = []
    for out_p in squad:
        budget = bank_tenths + out_p["price"]
        n = 0
        for in_p in by_pos[out_p["element_type"]]:
            if in_p["price"] > budget:
                continue
            if not _clubs_ok_after(clubs, [out_p], [in_p]):
                continue
            raw = wval[in_p["id"]] - wval[out_p["id"]]
            if raw <= 0:
                break  # lista on laskeva -> loput eivat paranna
            cands.append((raw, out_p, in_p))
            n += 1
            if n >= top_per_pos:
                break
    cands.sort(key=lambda c: c[0], reverse=True)

    scored: list[dict] = []
    for raw, out_p, in_p in cands:
        if len(scored) >= top_k and raw <= min(m["gain_weighted"] for m in scored):
            break
        new_squad = _apply(squad, [out_p], [in_p])
        gain_w = xi_value(new_squad, gws, weighted=True) - base
        if gain_w <= 0:
            continue
        gain = xi_value(new_squad, gws, weighted=False) - base_plain
        scored.append(_move(out_p, in_p, gain, gain_w, 0.0))
        scored.sort(key=lambda m: m["gain_weighted"], reverse=True)
        del scored[top_k:]
    return scored


def best_pair(squad: list[dict], pool: list[dict], bank_tenths: int,
              gws: list[int] | None, *,
              top_per_pos: int = TOP_CANDIDATES_PER_POS) -> dict | None:
    """Paras kahden siirron yhdistelma (painotettu XI-hyoty), tai None.

    Budjettiehto on YHDISTELMALLE: bank + lahtijoiden hinnat >= tulijoiden
    hinnat. Nain "vapauta rahaa ensin" -pari loytyy vaikka kumpikaan
    siirto ei yksin mahtuisi. Ylaraja = raakaerotusten summa; parit
    arvioidaan ylarajan jarjestyksessa ja haku paattyy kun ylaraja alittaa
    parhaan loydetyn hyodyn (tai MAX_PAIR_EVALS tayttyy).
    """
    squad_ids = {p["id"] for p in squad}
    clubs = _club_counts(squad)
    base = xi_value(squad, gws, weighted=True)
    base_plain = None
    wval = {p["id"]: window_xp(p, gws) * confidence_weight(p) for p in pool}
    for p in squad:
        wval.setdefault(p["id"], window_xp(p, gws) * confidence_weight(p))
    max_out_price = max(p["price"] for p in squad)
    by_pos: dict[int, list[dict]] = {1: [], 2: [], 3: [], 4: []}
    for p in pool:
        if p["id"] not in squad_ids:
            by_pos[p["element_type"]].append(p)
    for t in by_pos:
        by_pos[t].sort(key=lambda p: wval[p["id"]], reverse=True)

    # Per lahtija: kandidaatit joihin budjetti VOI riittaa kun toinen
    # lahtija vapauttaa enintaan max_out_price.
    per_out: list[tuple[dict, list[tuple[float, dict]]]] = []
    for out_p in squad:
        budget = bank_tenths + out_p["price"] + max_out_price
        lst = []
        for in_p in by_pos[out_p["element_type"]]:
            if in_p["price"] > budget:
                continue
            raw = wval[in_p["id"]] - wval[out_p["id"]]
            if raw <= 0:
                break
            lst.append((raw, in_p))
            if len(lst) >= top_per_pos:
                break
        if lst:
            per_out.append((out_p, lst))

    pairs: list[tuple[float, dict, dict, dict, dict]] = []
    for (o1, l1), (o2, l2) in itertools.combinations(per_out, 2):
        for r1, i1 in l1:
            for r2, i2 in l2:
                if i1["id"] == i2["id"]:
                    continue
                if i1["price"] + i2["price"] > bank_tenths + o1["price"] + o2["price"]:
                    continue
                if not _clubs_ok_after(clubs, [o1, o2], [i1, i2]):
                    continue
                pairs.append((r1 + r2, o1, i1, o2, i2))
    pairs.sort(key=lambda c: c[0], reverse=True)

    best: dict | None = None
    evals = 0
    for bound, o1, i1, o2, i2 in pairs:
        if best is not None and bound <= best["gain_weighted"]:
            break
        if evals >= MAX_PAIR_EVALS:
            break
        evals += 1
        new_squad = _apply(squad, [o1, o2], [i1, i2])
        gain_w = xi_value(new_squad, gws, weighted=True) - base
        if gain_w <= 0:
            continue
        if best is None or gain_w > best["gain_weighted"]:
            if base_plain is None:
                base_plain = xi_value(squad, gws, weighted=False)
            gain = xi_value(new_squad, gws, weighted=False) - base_plain
            # Rahaa vapauttava siirto ensin, jotta pankki ei kay miinuksella
            # kun siirrot tehdaan jarjestyksessa.
            first, second = ((o1, i1), (o2, i2))
            if (o1["price"] - i1["price"]) < (o2["price"] - i2["price"]):
                first, second = second, first
            best = {"moves": [first, second], "gain": round(gain, 4),
                    "gain_weighted": round(gain_w, 4), "evals": evals}
    return best


def plan_gw(squad: list[dict], pool: list[dict], bank_tenths: int,
            gws: list[int] | None, ft: int, *,
            max_moves: int = MAX_TRANSFERS_PER_GW,
            top_per_pos: int = TOP_CANDIDATES_PER_POS) -> dict:
    """Yhden kierroksen siirrot samoilla saannoilla kaikille pinnoille.

    Palauttaa {"moves": [...], "squad", "bank_tenths", "ft_left", "hits"}.
    Jokainen move: out, in, gain (painottamaton XI-hyoty), gain_weighted,
    hit, net, confidence_weight, pos, pair (bool).
    """
    squad = list(squad)
    bank = bank_tenths
    fts = max(0, ft)
    moves: list[dict] = []
    hits = 0

    def _hit_for(n_free_used: int) -> float:
        return 0.0 if fts - n_free_used > 0 else HIT_COST_XP

    while len(moves) < max_moves:
        singles = single_moves(squad, pool, bank, gws, top_k=1,
                               top_per_pos=top_per_pos)
        best_single = None
        if singles:
            s = singles[0]
            hit = _hit_for(0)
            s = _move(s["out"], s["in"], s["gain"], s["gain_weighted"], hit)
            if s["net"] >= MIN_GAIN_PER_TRANSFER:
                best_single = s

        chosen: list[dict] = []
        if max_moves - len(moves) >= 2:
            pr = best_pair(squad, pool, bank, gws, top_per_pos=top_per_pos)
            if pr is not None:
                hit_a = _hit_for(0)
                hit_b = _hit_for(1)
                net_pair = pr["gain_weighted"] - hit_a - hit_b
                floor = (best_single["net"] + MIN_GAIN_PER_TRANSFER
                         if best_single is not None
                         else 2 * MIN_GAIN_PER_TRANSFER)
                if net_pair >= floor:
                    (o1, i1), (o2, i2) = pr["moves"]
                    # Parin hyoty jaetaan nayttoon siirroittain: ensimmainen
                    # saa oman yksittaisen XI-hyotynsa, toinen loput.
                    mid = _apply(squad, [o1], [i1])
                    try:
                        g1 = xi_value(mid, gws, False) - xi_value(squad, gws, False)
                        g1w = xi_value(mid, gws, True) - xi_value(squad, gws, True)
                    except RateTeamError:
                        g1, g1w = 0.0, 0.0
                    m1 = _move(o1, i1, g1, g1w, hit_a)
                    m2 = _move(o2, i2, pr["gain"] - g1, pr["gain_weighted"] - g1w, hit_b)
                    m1["pair"] = m2["pair"] = True
                    chosen = [m1, m2]
        if not chosen and best_single is not None:
            best_single["pair"] = False
            chosen = [best_single]
        if not chosen:
            break
        for m in chosen:
            bank += m["out"]["price"] - m["in"]["price"]
            squad = _apply(squad, [m["out"]], [m["in"]])
            if fts > 0:
                fts -= 1
            else:
                hits += 1
            moves.append(m)
    return {"moves": moves, "squad": squad, "bank_tenths": bank,
            "ft_left": fts, "hits": hits}
