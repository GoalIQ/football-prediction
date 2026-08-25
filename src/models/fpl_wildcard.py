"""Wildcard-suunnitelma: kannattaako, MIHIN joukkueeseen ja MIKSI (25.8.2026).

Villen ohje: *"paranna toi wildcard et jos se ehdottaa nii pitaa perustella
miksi ja mihin joukkueeseen (ottaen huomioon pitemman aikavalin pelit kans)"*.

🔴 KOLME VIKAA JOTKA TAMA KORJAA. Kaikki mitattu tuotannosta 25.8, Villen
rivilta 1186244.

1. `chip-ev`:n `wc_ev`-rivit EIVAT OLE VERTAILUKELPOISIA, mutta `best` otti
   niista maksimin. Luvut: GW2 38,00 · GW3 33,55 · GW4 25,71 · GW5 20,22 ·
   GW6 15,95 · GW7 10,37. Monotoninen lasku nayttaa ajoitussignaalilta, mutta
   se on IKKUNAN PITUUS: rivin ikkuna on `[x for x in covered if x >= g]`, eli
   GW2:n luku on kuuden kierroksen summa ja GW7:n yhden. Per kierros jarjestys
   KAANTYY: 6,33 · 6,71 · 6,43 · 6,74 · 7,97 · **10,37**. Tyokalu suositteli
   aikaisinta kierrosta rakenteesta eika ansiosta.
   -> Ranking tehdaan `ev_per_gw`:lla ja `window_gws` kerrotaan rivilla.

2. EHDOTETTU JOUKKUE LASKETTIIN JA HEITETTIIN POIS. `fantasy_edge.py` rakensi
   `wc_xi`:n, summasi siita luvun eika koskaan palauttanut rivistoa. Kayttaja
   sai numeron jonka perustetta ei voinut nahda mistaan pinnalta.
   -> Palautetaan koko 15 (XI + penkki) ja `in`/`out` nimelta.

3. VERTAILU OLI 11 vs 15. `_greedy_budget_xi` rakentaa XI:n, mutta wildcard
   rakentaa 15 pelaajaa. Penkki maksaa rahaa jota XI ei silloin saa kayttoon,
   joten 11:n vertaaminen 15:een yliarvioi wildcardia jarjestelmallisesti.
   -> `build_optimal_squad` rakentaa laillisen 15:n samalla budjetilla.

🔴 PITKAN AIKAVALIN NAKYMA ON ERI PERUSTA, JOTEN SE PIDETAAN ERILLAAN.
xP-projektio yltaa 6 kierrosta. Sen yli menevat ottelut luetaan
`data/fpl_cs_fdr.json`:n 380 fixturesta (per puoli `att_fdr` / `def_fdr`). Se on
JOUKKUETASON vaikeusarvio eika pelaajatason xP, joten sita EI lisata xP-lukuun:
se raportoidaan omana lohkonaan `long_view` omalla basiksellaan. Kahden eri
perustan summaaminen tekisi luvusta sellaisen jota kukaan ei voi tarkistaa.
"""
from __future__ import annotations

from src.models import fpl_rate_team as rt

# Kuinka pitkalle fixture-nakyma ulottuu xP-horisontin YLI.
LONG_VIEW_GWS = 6

# 🔴 Kynnys suositukselle. Wildcard on kertakaytto — sen polttaminen pienesta
# erosta on huonompi kuin pito, koska sama chip olisi myohemmin arvokkaampi
# (loukkaantumiset, hinnannousut, tuplakierrokset). Luku on PER KIERROS, jotta
# se ei riipu ikkunan pituudesta (vika 1).
MIN_EV_PER_GW = 1.5

# 🔴 FPL:n bootstrap-nimet ja `fpl_cs_fdr.json`:n mallinimet eroavat KUUDESSA
# kohdassa 20:sta. Mitattu 25.8 ennen kytkentaa: ilman tata karttaa 6/20
# joukkuetta olisi pudonnut pitkan aikavalin nakymasta HILJAA, ja pudonnut
# pelaaja nayttaisi vain silta ettei hanella ole fixture-lukua.
# Vrt. sama vikaluokka `src/data/fpl_match_xg.py`:ssa.
FPL_TO_MODEL = {
    "Ipswich Town": "Ipswich",
    "Man City": "Manchester City",
    "Man Utd": "Manchester United",
    "Newcastle": "Newcastle United",
    "Nott'm Forest": "Nottingham Forest",
    "Spurs": "Tottenham",
}


def nimikartta_aukot(fpl_teams: list[dict], mallinimet: set[str]) -> list[str]:
    """FPL-nimet jotka eivat osu mallinimiin edes kartan jalkeen.

    Kutsuja kaataa ajon tasta: uuden kauden uudelleennimeaminen pudottaisi
    joukkueen muuten aanettomasti.
    """
    aukot = []
    for t in fpl_teams:
        nimi = FPL_TO_MODEL.get(t["name"], t["name"])
        if nimi not in mallinimet:
            aukot.append(f'{t["name"]!r} -> {nimi!r}')
    return sorted(aukot)


def _xp_gw(p: dict, gw: int) -> float:
    for g in (p.get("gameweeks") or []):
        if g.get("gw") == gw:
            return float(g.get("xp") or 0.0)
    return 0.0


def _xp_window(p: dict, gws: list[int]) -> float:
    return sum(_xp_gw(p, g) for g in gws)


def team_outlook(fixtures: list[dict], gws: set[int]) -> dict[str, dict]:
    """Per joukkue: hyokkays- ja puolustusvaikeus annetuilla kierroksilla.

    🔴 Otteluiden MAARA kerrotaan erikseen: tuplakierros on kaksi ottelua
    samalla kierroksella, ja pelkka keskiarvo piilottaisi sen taysin.
    Pienempi FDR = helpompi.
    """
    acc: dict[str, dict] = {}
    for f in fixtures:
        if f.get("gameweek") not in gws:
            continue
        for puoli in ("home", "away"):
            nimi = f.get(f"{puoli}_model") or f.get(puoli)
            a = f.get(f"att_fdr_{puoli}")
            d = f.get(f"def_fdr_{puoli}")
            if not nimi or a is None or d is None:
                continue
            r = acc.setdefault(nimi, {"att": [], "def": []})
            r["att"].append(float(a))
            r["def"].append(float(d))
    return {k: {"att_fdr": round(sum(v["att"]) / len(v["att"]), 2),
                "def_fdr": round(sum(v["def"]) / len(v["def"]), 2),
                "fixtures": len(v["att"])}
            for k, v in acc.items() if v["att"]}


def _rivi(p: dict, gws: list[int]) -> dict:
    n = max(1, len(gws))
    total = _xp_window(p, gws)
    return {
        "id": p["id"], "web_name": p["web_name"],
        "pos": rt.POS_NAME.get(p["element_type"], "?"),
        "team_short": p.get("team_short"),
        "price": round(p["price"] / 10, 1),
        "xp_window": round(total, 2),
        "xp_per_gw": round(total / n, 2),
        "chance_next": p.get("chance_next"),
    }


def _optimi(pool: list[dict], gws: list[int]) -> dict | None:
    """Paras laillinen 15 annetulle ikkunalle.

    🔴 `build_optimal_squad` pisteyttaa `xp_horizon_total`-kentasta, joka kattaa
    KOKO horisontin. Jos ikkuna on lyhyempi, optimointi valmiilla kentalla
    vastaisi eri kysymykseen kuin se jota kysytaan, joten score lasketaan tasta
    ikkunasta. Alkuperaisia rivejä ei muteta — kopio per pelaaja.
    """
    pisteytetty = []
    for p in pool:
        q = dict(p)
        q["xp_horizon_total"] = _xp_window(p, gws)
        pisteytetty.append(q)
    try:
        res = rt.build_optimal_squad(pisteytetty)
    except Exception:
        return None
    return res if res and res.get("xi") else None


def wildcard_plan(squad: list[dict], pool: list[dict], gws: list[int],
                  fixtures: list[dict], id_to_name: dict[int, str],
                  xi_fn) -> dict:
    """Paras wildcard-kierros, sen joukkue ja perustelut.

    `gws`   = kierrokset joille chipin voi VIELA pelata (deadline ei mennyt).
    `xi_fn` = (squad, key) -> paras laillinen XI. Annetaan ulkoa, jotta tama
              moduuli ei tuo tuontikeha `api.fantasy_edge`:n kanssa.
    """
    if not gws:
        return {"available": False,
                "note": "No gameweek left in the projection horizon."}

    def _paras_xi_xp(rivisto: list[dict], gw: int) -> float:
        """Rungon OMA optimi talle kierrokselle.

        🔴 Vertailukohta on oma optimi eika nykyinen XI: wildcardia ei saa
        kehua hyodysta jonka kayttaja saisi pelkalla penkkijarjestyksella.
        """
        xi = xi_fn(rivisto, lambda p: _xp_gw(p, gw))
        return sum(_xp_gw(p, gw) for p in xi)

    # --- 1. Uusi runko rakennetaan KERRAN, pisimmalle ikkunalle ------------
    # Wildcardin jalkeen runko jaa voimaan, joten sita ei optimoida yhdelle
    # kierrokselle.
    pisin = list(gws)
    uusi = _optimi(pool, pisin)
    if not uusi:
        return {"available": False,
                "note": "Could not build a legal squad from the current pool."}
    uusi_15 = uusi["xi"] + uusi["bench"]

    # --- 2. Kandidaattikierrokset YHTEISELLA arviointi-ikkunalla -----------
    # 🔴 KORJASIN TAMAN KERRAN VAARIN JA AJO NAYTTI SEN. Ensimmainen versio
    # normalisoi per kierros ja valitsi GW7:n eli MYOHAISIMMAN — vanhan bugin
    # peilikuva. Per-kierros-luku vastaa kysymykseen "kuinka paljon parempi
    # uusi runko on silla aikaa kun se on pelissa", eika se ole ajoitusmittari:
    # se ei nae etta GW7:aan odottaminen HEITTAA POIS viisi kierrosta hyotya.
    #
    # Ajoituspaatos on vertailtava vain YHTEISELLA ikkunalla, jossa vaihtuu
    # pelkka kytkentahetki: kierrokset ennen g pelataan vanhalla rungolla ja
    # kierrokset g:sta eteenpain uudella. Silloin
    #     ev(g) = summa_{x >= g} (uusi(x) - vanha(x))
    # ja kaikki rivit mitataan samasta kokonaisuudesta. Aritmetiikka on sama
    # kuin alkuperaisessa `wc_ev`:ssa — vika oli TULKINNASSA, ei laskussa:
    # rivit esitettiin ajoitusvertailuna kertomatta etta ne kattavat eri
    # maaran kierroksia.
    kaikki = list(gws)
    vanha_per_gw = {x: _paras_xi_xp(squad, x) for x in kaikki}
    uusi_per_gw = {x: _paras_xi_xp(uusi_15, x) for x in kaikki}
    kandidaatit = []
    for g in gws:
        ikkuna = [x for x in kaikki if x >= g]
        ev = sum(uusi_per_gw[x] - vanha_per_gw[x] for x in ikkuna)
        kandidaatit.append({
            "gw": g, "window_gws": len(ikkuna),
            "base_xp": round(sum(vanha_per_gw[x] for x in ikkuna), 2),
            "new_xp": round(sum(uusi_per_gw[x] for x in ikkuna), 2),
            # Ajoitusmittari: hyoty YHTEISELLA ikkunalla, kytkenta kohdassa g.
            "ev_total": round(ev, 2),
            # Toissijainen: kuinka paljon parempi runko on silla aikaa kun se
            # on pelissa. EI ajoitusmittari — ks. yllä.
            "ev_per_gw": round(ev / len(ikkuna), 2),
            "window": ikkuna,
        })

    paras = max(kandidaatit, key=lambda k: k["ev_total"])
    # Kynnys mitataan PER KIERROS vaikka ranking on kokonaishyodylla: "onko
    # runko tarpeeksi parempi" ei saa riippua siita montako kierrosta sattuu
    # olemaan jaljella.
    suosita = paras["ev_per_gw"] >= MIN_EV_PER_GW
    ikkuna = paras["window"]

    # --- 3. Ketka lahtevat, ketka tulevat ----------------------------------
    vanhat = {p["id"]: p for p in squad}
    uudet = {p["id"]: p for p in uusi_15}
    ulos = [_rivi(vanhat[i], ikkuna) for i in vanhat if i not in uudet]
    sisaan = [_rivi(uudet[i], ikkuna) for i in uudet if i not in vanhat]
    ulos.sort(key=lambda r: r["xp_per_gw"])
    sisaan.sort(key=lambda r: -r["xp_per_gw"])

    # --- 4. Pitkan aikavalin nakyma (ERI PERUSTA, EI SUMMATA xP:hen) -------
    raja = max(gws)
    yli = sorted({f["gameweek"] for f in fixtures
                  if isinstance(f.get("gameweek"), int)
                  and raja < f["gameweek"] <= raja + LONG_VIEW_GWS})
    outlook = team_outlook(fixtures, set(yli)) if yli else {}

    def _keski(rivit, kentta):
        arvot = []
        for r in rivit:
            p = uudet.get(r["id"]) or vanhat.get(r["id"])
            o = outlook.get(id_to_name.get(p.get("club"), "")) if p else None
            if o:
                arvot.append(o[kentta])
        return round(sum(arvot) / len(arvot), 2) if arvot else None

    long_view = None
    if yli:
        long_view = {
            "gws": yli,
            "basis": "team_fdr_full_season_fixtures",
            "incoming_att_fdr": _keski(sisaan, "att_fdr"),
            "outgoing_att_fdr": _keski(ulos, "att_fdr"),
            "incoming_def_fdr": _keski(sisaan, "def_fdr"),
            "outgoing_def_fdr": _keski(ulos, "def_fdr"),
            "note": ("Team-level fixture difficulty from the full-season "
                     "fixture file, not player xP. Lower is easier. It sits "
                     "next to the xP number and is never added to it."),
        }

    return {
        "available": True,
        "recommend": suosita,
        "gw": paras["gw"],
        "ev_per_gw": paras["ev_per_gw"],
        "ev_total": paras["ev_total"],
        "window_gws": paras["window_gws"],
        "threshold_per_gw": MIN_EV_PER_GW,
        "basis": "player_xp",
        "squad": {
            "xi": [_rivi(p, ikkuna) for p in uusi["xi"]],
            "bench": [_rivi(p, ikkuna) for p in uusi["bench"]],
            "changes": len(sisaan),
            "proven": bool(uusi.get("proven")),
        },
        "out": ulos, "in": sisaan,
        "candidates": [{k: v for k, v in c.items() if k != "window"}
                       for c in kandidaatit],
        "long_view": long_view,
        "reasons": _reasons(paras, ulos, sisaan, squad, suosita, long_view,
                            len(kaikki)),
    }


def _reasons(paras: dict, ulos: list[dict], sisaan: list[dict],
             squad: list[dict], suosita: bool,
             long_view: dict | None, horisontti_gws: int) -> list[dict]:
    """Perustelulauseet. Jokainen kantaa OMAN lukunsa.

    🔴 Lause jonka luku puuttuu jatetaan pois, ei arvata. Ja KUSTANNUS sanotaan
    ennen hyotya: paneeli joka avaa omalla voitollaan on mainos.
    """
    out: list[dict] = []
    n = paras["window_gws"]
    ikkuna_teksti = (f"GW{paras['gw']}" if n == 1
                     else f"GW{paras['gw']}-{paras['gw'] + n - 1}")

    out.append({"code": "cost",
                "text": f"A wildcard here changes {len(sisaan)} of your 15."})

    if suosita:
        out.append({"code": "ev", "text":
                    f"The rebuilt squad projects {paras['ev_per_gw']} points "
                    f"per gameweek more than your own best lineup over "
                    f"{ikkuna_teksti}, {paras['ev_total']} in total."})
    else:
        out.append({"code": "hold", "text":
                    f"That is worth {paras['ev_per_gw']} points per gameweek, "
                    f"below the {MIN_EV_PER_GW} the model asks before burning "
                    f"a chip you only get once. The model says hold."})

    if ulos:
        w = ulos[0]
        out.append({"code": "worst_out", "text":
                    f"The weakest player it drops is {w['web_name']} at "
                    f"{w['xp_per_gw']} points per gameweek."})
    if sisaan:
        b = sisaan[0]
        out.append({"code": "best_in", "text":
                    f"The strongest it brings in is {b['web_name']} at "
                    f"{b['xp_per_gw']}."})

    liputetut = [p for p in squad
                 if isinstance(p.get("chance_next"), int)
                 and p["chance_next"] < 100]
    if liputetut:
        out.append({"code": "flags", "text":
                    f"{len(liputetut)} of your current 15 carry an FPL "
                    f"availability flag right now."})

    if long_view and long_view.get("incoming_att_fdr") is not None \
            and long_view.get("outgoing_att_fdr") is not None:
        yli = long_view["gws"]
        out.append({"code": "long_view", "text":
                    f"Past the projection horizon, over GW{min(yli)}-"
                    f"{max(yli)}, the incoming players' teams average "
                    f"{long_view['incoming_att_fdr']} attack difficulty "
                    f"against {long_view['outgoing_att_fdr']} for the ones "
                    f"leaving. That is a team-level fixture read, not xP."})

    # 🔴 MIKSI AIKAISIN VOITTAA. Ilman tata lausetta tyokalu nayttaisi
    # "loytaneen" parhaan viikon, vaikka se ei voi tietaa tulevaa. Malli ei
    # hinnoittele odottamisen ainoaa oikeaa perustetta (uutta tietoa), joten
    # se sanotaan aareen sen sijaan etta annettaisiin vaikutelma valinnasta.
    out.append({"code": "timing", "text":
                f"Every gameweek is compared over the same "
                f"{horisontti_gws}-gameweek window, with only the switch "
                f"point moving. Waiting can only lose points here, because "
                f"the model prices no information it does not have yet: "
                f"injuries, price moves and fixture swings that arrive later "
                f"are exactly why a human waits."})
    return out

