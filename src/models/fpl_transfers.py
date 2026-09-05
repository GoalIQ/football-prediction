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

🔴 3.9: paino on nyt MITATTU ja arvo on 1.0 (ks. LOW_CONFIDENCE_WEIGHT).
Alla oleva teksti kuvaa tilannetta ENNEN mittausta ja jaa historiaksi.
Painon arvo 0.75 oli OLETUS, ei mittaus: `data/fpl_xp_gw_accuracy.json`
kirjaa GW1:n MAE:n vain positioittain (DEF 1.92 .. GKP 1.35), ei
promoted-vs-muut-jakoa, joten kalibrointiin ei viela ole dataa.
TODO(kalibrointi): kun 3+ kierrosta on gradattu, laske MAE erikseen
price-prior-pelaajille ja aseta paino niiden yliarvioinnin suhteessa.
"""
from __future__ import annotations

import itertools

from src.models.fpl_rate_team import (
    DECISION_BAR_XP_PER_GW, HIT_COST_XP, MAX_PER_CLUB, POS_NAME, RateTeamError,
    _best_split, _gw_xp, hold_threshold_for,
)

# ---------------------------------------------------------------------------
# PAATOSKYNNYKSET (3.9.2026, Villen GO — `cos-reports/siirtomoottorin-
# paatoskynnykset.md` sisaltaa kaikki mittaukset)
#
# 🔴 MITATTU, EI VALITTU. Entry 116920, suunnittelu GW3:sta, ft=1:
#     kynnys 0.5 -> 4 siirtoa, +3.27 xP     kynnys 1.0 -> 3 siirtoa, +3.53 xP
# Vahemman siirtoja JA enemman hyotya moottorin omalla mittarilla. Syy nakyy
# sisallossa: 0.5 osti Mosqueran GW4 (+0.70) ja myi hanet GW8 (+0.66), eli
# kaksi siirtoa paatyakseen sinne minne olisi paassyt suoraan.
# 🔴 JOHDETTU, ei oma vakio (spec kohta 5): sama per-kierros-luku kuin
# hero-verdiktin `HOLD_THRESHOLD_XP`, kerrottuna LAHI-ikkunalla. Naita kahta
# ei voi enaa asettaa toisistaan riippumatta — se oli koko kohdan 5 vika.
MIN_GAIN_PER_TRANSFER = round(DECISION_BAR_XP_PER_GW * 2, 2)
# Hitti on ERI PAATOS kuin vapaa siirto, joten sille on oma vakio. Vanha saanto
# oli `netto = hyoty - 4.0 >= 0.5` eli hyoty >= 4.5 — mutta kahden pelaajan
# erotuksen keskihajonta YHDELLA kierroksella on +-4.34 p (mitattu GW1+GW2,
# n=607). Tuote otti varman -4:n kolikonheitosta.
MIN_GAIN_FOR_HIT = 6.0
# Lahi-ikkuna: paatos tehdaan seuraavista kierroksista, ei kuuden summasta.
# Jos pelaaja on parempi vasta GW7:ssa, hanet voi ostaa GW6:ssa ja pitaa
# siirron siihen asti — horisonttisumma kohtelee "osta nyt" ja "osta myohemmin"
# samana vaikka jalkimmainen sailyttaa option. Horisontti jaa RANKKAUKSEEN.
NEAR_WINDOW_GWS = 2
# Hitille ei riita etta lahi-ikkuna on positiivinen: -4 maksetaan nyt, joten
# valtaosan hyodysta on tultava nyt.
NEAR_SHARE_FOR_HIT = 0.5
# FPL:n saanto, ei malliparametri: vapaasiirtopankin katto.
FT_CARRY_MAX = 5
# Pankki katossa: kayttamatta jattaminen HUKKAA seuraavan kertymän, joten
# siirron marginaalihinta on nolla -> ota mika tahansa aito parannus.
BAR_BANK_FULL = 0.01
# 3-4 siirtoa pankissa: jousto ei ole niukkaa, rima puolittuu.
BAR_BANK_DEEP_FACTOR = 0.5
# Korjaus ei ole optimointi: pelaaja jota ei voi pelata on 0 xP joka kierros.
BAR_REPAIR = 0.01
MAX_TRANSFERS_PER_GW = 2
TOP_CANDIDATES_PER_POS = 12
# 🔴 MITATTU 3.9.2026 (Villen GO), oli 0.75 OLETUKSENA.
#
# Paino on olemassa koska nousijaseurojen pelaajien xP nojaa joukkuetason
# ratingiin jolla ei ole mittaushistoriaa, ja 28.8 juuri he nousivat plannerin
# karkeen. Huoli oli aito. SUUNTA EI OLLUT.
#
# `scripts/measure_promoted_bias.py`, GW1+GW2 deadline-freeze vs FPL:n
# toteuma, pelanneet (min > 0):
#     nousijaseurat  n= 90  bias +1.059  se 0.334  MAE 2.185
#     muut           n=517  bias +0.516  se 0.134  MAE 2.033
#     ero +0.543, z +1.51 (EI merkitseva)
# bias = toteuma - ennuste, eli POSITIIVINEN = malli aliarvioi. Malli
# aliarvioi nousijaseuroja enemman kuin muita — 0.75 painoi alaspain tasan
# sita ryhmaa jonka se jo arvioi liian matalaksi.
#
# Mitattu ero ei ole merkitseva (n=90, kaksi kierrosta), joten oikea luku ei
# ole 1.25 vaan 1.0: alennusta jolle ei ole mittausta ei pideta yllä. Mekanismi
# jaa paikalleen, jotta mitattu kerroin voidaan asettaa kun dataa on enemman —
# mutta `tests/test_promoted_weight_measured.py` vaatii silloin mittauksen
# tahan tiedostoon, ei uutta oletusta.
#
# Vaikutus entry 116920:lle: ykkosehdotus oli "Tzolakis ulos" jonka
# PAINOTTAMATON hyoty oli -0.87 xP. Painolla 1.0 se siirto katoaa ja jokaisen
# jaljelle jaavan siirron painottamaton hyoty on positiivinen.
LOW_CONFIDENCE_WEIGHT = 1.0
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


def placeholder_player(pid: int, bootstrap: dict) -> dict | None:
    """Rungon pelaaja JOLLE EI OLE PROJEKTIOTA, poolin muodossa ja 0 xP:lla.

    🔴 MIKSI TAMA ON OLEMASSA (3.9.2026, spec kohta 6b). xP-artefakti pudottaa
    pelaajan jonka FPL-saatavuus on i/s/u/n, ja `plan_transfers` rakensi
    rungon poolista — eli loukkaantunut tai liigasta lahtenyt pelaaja EI OLLUT
    RUNGOSSA moottorin silmissa lainkaan. Silloin moottori ei voinut ehdottaa
    hanen myymistaan: se myi jonkun muun. Korjaus jonka pitaisi olla helpoin
    suositus koko tuotteessa oli rakenteellisesti mahdoton.

    Placeholder tuo hanet takaisin rungon jasenena arvolla 0 (mika han on):
    hanta ei koskaan valita XI:hin, ja hanen korvaamisensa saa `transfer_bar`in
    korjausriman (`needs_repair`).
    """
    el = {e["id"]: e for e in (bootstrap.get("elements") or [])}.get(pid)
    if not el:
        return None
    teams = {int(t["id"]): (t.get("short_name") or t.get("name") or "")
             for t in (bootstrap.get("teams") or [])}
    return {
        "id": pid,
        "web_name": el.get("web_name") or str(pid),
        "team_short": teams.get(int(el.get("team") or 0), ""),
        "element_type": el.get("element_type"),
        "club": el.get("team"),
        "price": el.get("now_cost") or 0,
        "owned_pct": 0.0,
        "xp_per_gw": 0.0,
        "xp_horizon_total": 0.0,
        "gameweeks": [],
        "status": el.get("status"),
        "chance_next": el.get("chance_of_playing_next_round"),
        "news": el.get("news"),
        # Lippu jonka `needs_repair` lukee. EI `status`in varassa: FPL voi
        # merkita pelaajan "a":ksi ja artefakti pudottaa hanet silti (xP alle
        # min_xp_total), ja hanen korvaamisensa on silti korjaus.
        "no_projection": True,
    }


def near_gws(gws: list[int] | None) -> list[int] | None:
    """Lahi-ikkuna: kierrokset joista paatos tehdaan (None = ei ikkunaa)."""
    if not gws:
        return None
    return list(gws[:NEAR_WINDOW_GWS])


def needs_repair(p: dict) -> bool:
    """Onko lahtija pelaaja jota EI VOI PELATA (korjaus, ei optimointi).

    Kolme lahdetta: (1) rungon pelaaja jolle ei ole projektiota lainkaan
    (`no_projection`, ks. `placeholder_player`) — FPL:n saatavuusportti on
    pudottanut hanet artefaktista; (2) projektiohetken status muu kuin "a";
    (3) `chance_next == 0`. Kaikissa hanen xP:nsa on nolla joka kierros, eika
    haneen verrattua "hyotya" kuulu mitata samalla rimalla kuin toimivaan
    pelaajaan.
    """
    if p.get("no_projection"):
        return True
    if (p.get("status") or "a") != "a":
        return True
    if p.get("chance_next") == 0:
        return True
    return False


def transfer_bar(ft_left: int, *, entry_known: bool = True,
                 repair: bool = False,
                 near_len: int = NEAR_WINDOW_GWS) -> dict:
    """🔴 YKSI LUKIJA paatoskynnykselle. Kaikki siirtopaatokset lukevat taman.

    Palauttaa `min_net` (verrataan siirron `net`-lukuun), `min_gain` (sama
    rima ennen hitin vahennysta, naytolle) ja `reason` (miksi tama rima).

    KYNNYS ON ENTRY-KOHTAINEN (Villen lisays 3.9). Sama +0.8 xP:n siirto on
    eri paatos eri managerille, ja ero on laskettavissa entryn omasta tilasta
    eika ole makuasia:

      ft = 0      hitti — oma rima (MIN_GAIN_FOR_HIT), eri paatos
      ft >= 5     pankki katossa: kayttamatta jattaminen hukkaa kertyman,
                  marginaalihinta 0 -> ota mika tahansa aito parannus
      ft = 3-4    jousto ei ole niukkaa -> rima puolittuu
      ft = 1-2    siirto on ainoa jousto ensi viikkoon -> taysi rima
      korjaus     pelaaja jota ei voi pelata -> matalin rima (ei koske
                  hittia: -4 maksetaan silti nyt)

    NEGATIIVINEN KONTROLLI: `entry_known=False` (manual/draft-moodi, ei
    `ft`-tietoa) palauttaa AINA moduulivakion. Kynnys ei saa muuttua siella
    missa entryn tilaa ei tunneta.

    `near_len` on ikkunan pituus kierroksina. Rima on YKSI luku per kierros
    (`DECISION_BAR_XP_PER_GW`), joten se kerrotaan ikkunalla — lyhyella
    horisontilla sama vakio olisi ollut kaksi kertaa tiukempi kuin miksi se
    on kirjoitettu.
    """
    n = max(1, int(near_len or 1))
    full = round(DECISION_BAR_XP_PER_GW * n, 4)
    if ft_left <= 0:
        return {"min_gain": MIN_GAIN_FOR_HIT,
                "min_net": round(MIN_GAIN_FOR_HIT - HIT_COST_XP, 4),
                "hit": True, "reason": "hit"}
    if not entry_known:
        return {"min_gain": full, "min_net": full,
                "hit": False, "reason": "default"}
    if repair:
        return {"min_gain": BAR_REPAIR, "min_net": BAR_REPAIR,
                "hit": False, "reason": "repair"}
    if ft_left >= FT_CARRY_MAX:
        return {"min_gain": BAR_BANK_FULL, "min_net": BAR_BANK_FULL,
                "hit": False, "reason": "bank_full"}
    if ft_left >= 3:
        v = round(full * BAR_BANK_DEEP_FACTOR, 4)
        return {"min_gain": v, "min_net": v, "hit": False, "reason": "bank_deep"}
    return {"min_gain": full, "min_net": full,
            "hit": False, "reason": "default"}


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


def _move(out_p: dict, in_p: dict, gain: float, gain_w: float, hit: float,
          gain_near: float | None = None,
          gain_near_weighted: float | None = None) -> dict:
    """🔴 3.9 ILTA (Villen loydos): rivi ei ollut luettavissa.

    Rivi nayttti `gain -0.87`, `gain_weighted +4.84` ja `confidence_weight 1.0`,
    eika lukija voinut mitenkaan paatella miksi siirto suositellaan vaikka se
    HAVIAA mallin omilla luvuilla. Syy oli LAHTIJAN paino (Tzolakis, HUL,
    0.75), mutta rivilla nakyva paino oli TULIJAN (Trafford 1.0). Moduulin oma
    sopimus sanoo "paatosluvut nakyviin, ei piiloon" — paatosluku nakyi, sen
    syy ei.

    Molemmat painot nimetaan nyt erikseen. `confidence_weight` jaa tulijan
    painoksi (taaksepain yhteensopiva, klientit lukevat sita).
    """
    w_in = confidence_weight(in_p)
    w_out = confidence_weight(out_p)
    return {
        "out": out_p, "in": in_p,
        "gain": round(gain, 4),              # painottamaton XI-hyoty (naytto)
        "gain_weighted": round(gain_w, 4),   # paatosluku
        "hit": hit,
        "net": round(gain_w - hit, 4),
        # Lahi-ikkunan hyoty (NEAR_WINDOW_GWS ensimmaista kierrosta). Tama on
        # se luku josta paatos tehdaan; `gain` on horisontti eli rankkaus.
        # None = ikkunaa ei annettu (rate-teamin lista, ei paatos).
        "gain_near": None if gain_near is None else round(gain_near, 4),
        "gain_near_weighted": (None if gain_near_weighted is None
                               else round(gain_near_weighted, 4)),
        # Paatosluku VAPAALLE siirrolle: lahi-ikkunan hyoty hitin jalkeen.
        # Hitti paattaa horisontista (`net`) + lahi-ikkunan osuusehdosta, koska
        # -4 on kertakustannus koko horisontille — ks. `transfer_bar`.
        "net_near": (None if gain_near_weighted is None
                     else round(gain_near_weighted - hit, 4)),
        "confidence_weight": w_in,
        "confidence_weight_in": w_in,
        "confidence_weight_out": w_out,
        # True kun paatos ja naytto eroavat merkin verran: siirto suositellaan
        # vaikka painottamaton hyoty on <= 0. Klientti nayttaa silloin syyn.
        "weighting_decided": bool(gain <= 0 < gain_w),
        "pos": POS_NAME[out_p["element_type"]],
    }


def single_moves(squad: list[dict], pool: list[dict], bank_tenths: int,
                 gws: list[int] | None, *, top_k: int = 5,
                 top_per_pos: int = TOP_CANDIDATES_PER_POS,
                 near: list[int] | None = None,
                 near_min_share: float = 0.0) -> list[dict]:
    """Parhaat yksittaiset siirrot painotetulla XI-hyodylla, laskevasti.

    Eksakti kandidaattijoukon sisalla: raakaerotus on XI-hyodyn ylaraja
    (uusi XI:n tulokas voidaan aina korvata lahtijalla -> vanha laillinen
    XI), joten listaa taydennetaan raakaerotuksen jarjestyksessa ja
    lopetetaan kun ylaraja alittaa listan heikoimman todellisen hyodyn.
    Kandidaatit per lahtija: saman position top_per_pos parasta
    painotetulla ikkuna-xP:lla joihin budjetti riittaa (bank + lahtijan
    hinta), max 3/klubi vaihdon jalkeen.

    `near` (3.9): lahi-ikkuna josta PAATOS tehdaan. Kun se annetaan, siirto
    kelpaa vain jos se parantaa joukkuetta jo siella — horisontti jaa
    rankkaukseen. `near_min_share` vaatii lisaksi ettei hyoty ole horisontin
    hannassa (hitille NEAR_SHARE_FOR_HIT). Ilman `near`ia kaytos on entinen:
    tama funktio on myos rate-teamin LISTA, eika lista ole paatos.
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
        gain_near = gain_near_w = None
        if near:
            gain_near_w = (xi_value(new_squad, near, weighted=True)
                           - xi_value(squad, near, weighted=True))
            if gain_near_w <= 0:
                continue
            if near_min_share > 0 and gain_near_w < near_min_share * gain_w:
                continue
            gain_near = (xi_value(new_squad, near, weighted=False)
                         - xi_value(squad, near, weighted=False))
        scored.append(_move(out_p, in_p, gain, gain_w, 0.0,
                            gain_near, gain_near_w))
        scored.sort(key=lambda m: m["gain_weighted"], reverse=True)
        del scored[top_k:]
    return scored


def best_pair(squad: list[dict], pool: list[dict], bank_tenths: int,
              gws: list[int] | None, *,
              top_per_pos: int = TOP_CANDIDATES_PER_POS,
              near: list[int] | None = None,
              near_min_share: float = 0.0) -> dict | None:
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
    base_near = xi_value(squad, near, weighted=True) if near else 0.0
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
        # Lahi-ikkunan ehto (3.9): sama saanto kuin yksittaiselle siirrolle.
        # Ilman tata pari olisi ollut portti jonka lapi horisontin hannan
        # liikkeet olisivat palanneet takaisin.
        gain_near_w = None
        if near:
            gain_near_w = xi_value(new_squad, near, weighted=True) - base_near
            if gain_near_w <= 0:
                continue
            if near_min_share > 0 and gain_near_w < near_min_share * gain_w:
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
                    "gain_weighted": round(gain_w, 4), "evals": evals,
                    "gain_near_weighted": (None if gain_near_w is None
                                           else round(gain_near_w, 4))}
    return best


def best_move_summary(squad: list[dict], pool: list[dict], bank_tenths: int,
                      gws: list[int] | None, ft: int, *,
                      entry_known: bool = True,
                      top_per_pos: int = TOP_CANDIDATES_PER_POS) -> dict | None:
    """Paras TARJOLLA oleva siirto — SAMALLA lukijalla jolla paatos tehdaan.

    🔴 MIKSI TAMA ON OMA FUNKTIO (julkaisuportti 3.9, loydokset B1-B3).
    Ensimmainen versio haki taman luvun `single_moves`illa ILMAN lahi-ikkunaa
    ja vertasi sita moduulivakioon, kun taas paatos tehtiin lahi-ikkunalla ja
    entry-kohtaisella rimalla. Lause "under the 0.50 bar" saattoi siis
    tulostua luvulle 1.33 — tuote olisi kertonut kayttajalle etta 1,33 on
    alle 0,50. Portti rakensi tapauksen ja ajoi sen.

    Palauttaa `case`n joka on PAATELTY vertailusta, ei muotoiltu lauseeseen:
      "below_bar" paras siirto jai oman rimansa alle
      "over_bar"  paras siirto ylittaa riman (suunnitelma ottaa sen)
      "later"     lahi-ikkunassa ei ole hyotya, horisontissa on
      None        mikaan siirto ei paranna joukkuetta
    Arvo ja rima ovat AINA samassa yksikossa ja samasta ikkunasta.
    """
    near = near_gws(gws)
    win = near if near else (gws or [])
    n_win = max(1, len(win))
    bar = transfer_bar(ft, entry_known=entry_known, near_len=n_win)
    # Hitti on horisonttipaatos (-4 maksetaan kerran koko horisontille),
    # vapaa siirto lahi-ikkunapaatos. Ikkuna valitaan riman mukaan, ei
    # toisin pain — muuten luku ja rima olisivat eri ikkunasta.
    if bar["hit"]:
        win = list(gws or [])
        n_win = max(1, len(win))
    best = single_moves(squad, pool, bank_tenths, gws, top_k=1,
                        top_per_pos=top_per_pos,
                        near=None if bar["hit"] else near)
    if best:
        m = best[0]
        value = (m["gain_weighted"] - HIT_COST_XP if bar["hit"]
                 else (m["gain_near_weighted"] if m["gain_near_weighted"] is not None
                       else m["gain_weighted"]))
        return {
            "case": "below_bar" if value < bar["min_net"] else "over_bar",
            "value_xp": round(value, 2),
            "value_xp_per_gw": round(value / n_win, 2),
            "bar_xp": round(bar["min_net"], 2),
            "bar_xp_per_gw": round(bar["min_net"] / n_win, 2),
            "window_gws": list(win),
            "bar_reason": bar["reason"],
            "out": m["out"], "in": m["in"],
        }
    # Lahi-ikkuna tyhjeni: onko hyotya myohemmin?
    later = single_moves(squad, pool, bank_tenths, gws, top_k=1,
                         top_per_pos=top_per_pos)
    if later:
        return {"case": "later", "value_xp": None, "value_xp_per_gw": None,
                "bar_xp": round(bar["min_net"], 2),
                "bar_xp_per_gw": round(bar["min_net"] / n_win, 2),
                "window_gws": list(near or gws or []),
                "bar_reason": bar["reason"],
                "out": later[0]["out"], "in": later[0]["in"]}
    return None


def plan_gw(squad: list[dict], pool: list[dict], bank_tenths: int,
            gws: list[int] | None, ft: int, *,
            max_moves: int = MAX_TRANSFERS_PER_GW,
            top_per_pos: int = TOP_CANDIDATES_PER_POS,
            entry_known: bool = True,
            acquired: dict[int, float] | None = None) -> dict:
    """Yhden kierroksen siirrot samoilla saannoilla kaikille pinnoille.

    Palauttaa {"moves": [...], "squad", "bank_tenths", "ft_left", "hits"}.
    Jokainen move: out, in, gain (painottamaton XI-hyoty), gain_weighted,
    gain_near (lahi-ikkuna, paatosluku), hit, net, confidence_weight, pos,
    pair (bool), bar (kynnys josta paatos tehtiin), decide (paatokseen
    kaytetty luku — talteen `acquired`-sanakirjaa varten, ei julkiseen
    payloadiin).

    3.9: paatos tehdaan LAHI-IKKUNASTA (`near_gws`) ja kynnys tulee
    `transfer_bar`ista, joka on entry-kohtainen (ft + rungon tila).
    `entry_known=False` = manual/draft-moodi -> moduulivakio, kayttaytyminen
    tasmalleen entinen.

    SIIRTOSUUNNITELMA-CHURN (5.9.2026): `acquired` on {pelaaja_id: paatosluku}
    saman MONEN GW:n suunnitelman AIEMMIN tekemista ostoista (fpl_planner
    yllapitaa tata koko horisontin ylitse, ei vain taman kutsun sisalla).
    Mitattu tuotannosta 3.9: sama suunnitelma osti Wissan GW5:ssa (+0.66) ja
    myi hanet GW8:ssa (+0.77) — kaksi siirtoa paatyakseen sinne minne olisi
    paassyt suoraan. Ahne kierros-kerrallaan-haku ei nae etta se peruu oman
    aiemman paatoksensa, koska jokainen GW arvioidaan itsenaisesti.
    Vartija: askettain ostettua ei myyda ellei uuden siirron paatosluku
    ylita alkuperaisen oston paatoslukua SELVASTI (vahintaan yhden taman
    kierroksen kynnyksen verran) — sama "selvasti" jota kaytetaan muuallakin
    tassa moduulissa (esim. yhdistelmahaun floor). `needs_repair`-lahtija
    (loukkaantunut/poissa) EI kuulu vartijan piiriin: se on korjaus, ei
    optimointi (sama rajaus kuin `transfer_bar`in repair-haara).
    """
    squad = list(squad)
    bank = bank_tenths
    fts = max(0, ft)
    moves: list[dict] = []
    hits = 0

    def _hit_for(n_free_used: int) -> float:
        return 0.0 if fts - n_free_used > 0 else HIT_COST_XP

    near = near_gws(gws)
    while len(moves) < max_moves:
        # Hitin lahi-ikkunavaatimus on tiukempi: -4 maksetaan nyt.
        share = NEAR_SHARE_FOR_HIT if fts <= 0 else 0.0
        # top_k=3 eika 1: paras horisonttisiirto voi kaatua omaan kynnykseensa
        # (esim. optimointi taydella rimalla) kun seuraava lapaisisi omansa
        # (korjaus matalalla rimalla). Yhdella kandidaatilla korjaus ei olisi
        # koskaan loytynyt.
        singles = single_moves(squad, pool, bank, gws, top_k=3,
                               top_per_pos=top_per_pos,
                               near=near, near_min_share=share)
        best_single = None
        for cand in singles:
            hit = _hit_for(0)
            m = _move(cand["out"], cand["in"], cand["gain"],
                      cand["gain_weighted"], hit,
                      cand.get("gain_near"), cand.get("gain_near_weighted"))
            bar = transfer_bar(fts, entry_known=entry_known,
                               repair=needs_repair(cand["out"]),
                               near_len=len(near) if near else 1)
            # 🔴 IKKUNA JA KYNNYS SAMASTA YKSIKOSTA. Vapaan siirron rima on
            # LAHI-ikkunan luku (1.0 = 0.5/GW x 2 GW); horisontin summaan
            # verrattuna sama luku olisi 0.17/GW eli loysempi kuin miksi se
            # on kirjoitettu. Hitti on eri paatos: -4 maksetaan kerran koko
            # horisontille, joten sen rima on horisontissa (`net`) ja
            # lahi-ikkunan osuusehto hoidetaan hakuvaiheessa.
            decide = m["net"] if bar["hit"] else (
                m["net_near"] if m["net_near"] is not None else m["net"])
            # CHURN-VARTIJA (SIIRTOSUUNNITELMA-CHURN): tama lahtija ostettiin
            # AIEMMIN samassa suunnitelmassa. Myynti kelpaa vain jos uusi
            # paatosluku ylittaa alkuperaisen oston paatosluvun selvasti
            # (vahintaan taman kierroksen oman kynnyksen verran) — muuten
            # kandidaatti ohitetaan, ei vain hylata koko hakua.
            out_id = cand["out"]["id"]
            if (acquired and out_id in acquired
                    and not needs_repair(cand["out"])
                    and decide < acquired[out_id] + bar["min_net"]):
                continue
            if decide >= bar["min_net"]:
                m["bar"] = bar
                m["decide"] = decide
                best_single = m
                break

        chosen: list[dict] = []
        if max_moves - len(moves) >= 2:
            pr = best_pair(squad, pool, bank, gws, top_per_pos=top_per_pos,
                           near=near, near_min_share=share)
            if pr is not None:
                hit_a = _hit_for(0)
                hit_b = _hit_for(1)
                net_pair = pr["gain_weighted"] - hit_a - hit_b
                if not (hit_a or hit_b) and pr.get("gain_near_weighted") is not None:
                    net_pair = pr["gain_near_weighted"]
                (_o1, _i1), (_o2, _i2) = pr["moves"]
                pair_bar = transfer_bar(
                    fts, entry_known=entry_known,
                    repair=needs_repair(_o1) or needs_repair(_o2),
                    near_len=len(near) if near else 1)
                # CHURN-VARTIJA parille: sama saanto kuin yksittaisella
                # siirrolla, molemmille lahtijoille erikseen. Ei osa-arvoa
                # per jalka (pari arvioidaan yhtena paatoksena), joten koko
                # pari hylataan jos kumpi tahansa lahtija on askettain
                # ostettu ilman selvaa etua.
                pair_blocked = any(
                    acquired and leg["id"] in acquired
                    and not needs_repair(leg)
                    and net_pair < acquired[leg["id"]] + pair_bar["min_net"]
                    for leg in (_o1, _o2))
                _bs = None
                if best_single is not None:
                    _bs = (best_single["net"] if pair_bar["hit"]
                           else (best_single["net_near"]
                                 if best_single["net_near"] is not None
                                 else best_single["net"]))
                floor = (_bs + pair_bar["min_net"] if _bs is not None
                         else 2 * pair_bar["min_net"])
                if not pair_blocked and net_pair >= floor:
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
                    # Pari arvioitiin YHTENA paatoksena: lahi-ikkunan luku ja
                    # kynnys ovat parin omat, ei kummankaan siirron erikseen.
                    m1["bar"] = m2["bar"] = pair_bar
                    m1["gain_near_weighted"] = m2["gain_near_weighted"] = (
                        pr.get("gain_near_weighted"))
                    m1["decide"] = m2["decide"] = net_pair
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
