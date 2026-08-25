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
   -> Ranking tehdaan `ev_total`:lla YHTEISELLA ikkunalla (vain kytkentahetki
      liikkuu), ja `window_gws` kerrotaan rivilla.

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
                  xi_fn, mode: str = "entry") -> dict:
    """Paras wildcard-kierros, sen joukkue ja perustelut.

    `gws`   = kierrokset joille chipin voi VIELA pelata (deadline ei mennyt).
    `mode`  = "entry" kun rivisto on LUKIJAN, muuten mallin oma. 🔴 Copy sanoo
              "your 15" vain ensimmaisessa: mallin rungosta puhuminen lukijan
              omistusmuodossa on vaite jota lukija ei voi tarkistaa.
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
                "note": "Could not build a full 15 from the current pool."}
    uusi_15 = uusi["xi"] + uusi["bench"]
    oma_rivisto = mode == "entry"

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

    # 🔴 TAUTOLOGIA ON ERI ASIA KUIN TULOS. Ilman entrya rivisto on mallin oma
    # optimi, ja sita verrataan mallin omaan optimiin: 0 muutosta, 0.0 pistetta,
    # "hold". Mitattu ilmaispinnalta 25.8. Se ei ole vastaus vaan sama luku
    # kahdesti, ja ensikavijan ilmaiskokemus olisi paneeli joka sanoo ettei se
    # muuta mitaan. Kerrotaan mita puuttuu sen sijaan etta esitettaisiin
    # nollatulos loydoksena.
    if not oma_rivisto and paras["ev_total"] <= 0.01:
        return {"available": False,
                "note": ("Add your FPL team ID above to see whether a wildcard "
                         "is worth playing. Without one this compares the "
                         "model's own squad against itself.")}
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
            # 🔴 VARAUS SANOTAAN KERRAN. Sama asia oli 25.8 kolmessa
            # paikassa samassa nakymassa (tama, `long_view`-lause ja
            # meta.notes[2]). Toistettu varaus on AI-tunnusmerkki ja se myos
            # laimentaa itseaan: kolmesti sanottu kuulostaa puolustelulta.
            # Jaljella oleva kopio on meta.notes-lohkossa.
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
                            len(kaikki), oma_rivisto, min(gws),
                            {x: uusi_per_gw[x] - vanha_per_gw[x]
                             for x in kaikki}),
    }


def _reasons(paras: dict, ulos: list[dict], sisaan: list[dict],
             squad: list[dict], suosita: bool, long_view: dict | None,
             horisontti_gws: int, oma_rivisto: bool,
             aikaisin_gw: int, deltat: dict[int, float]) -> list[dict]:
    """Perustelulauseet. Jokainen kantaa OMAN lukunsa.

    🔴 Lause jonka luku puuttuu jatetaan pois, ei arvata. Ja KUSTANNUS sanotaan
    ennen hyotya: paneeli joka avaa omalla voitollaan on mainos.

    🔴 `oma_rivisto=False` -> EI omistusmuotoa. Ilman entrya rivisto on mallin
    oma, ja "your 15" olisi vaite jota lukija ei voi tarkistaa mistaan.
    """
    out: list[dict] = []
    n = paras["window_gws"]
    ikkuna = (f"GW{paras['gw']}" if n == 1
              else f"GW{paras['gw']}–{paras['gw'] + n - 1}")
    # Jalkimmainen omistusmuoto vaihdetaan: "the model's own 15" ->
    # "the model's own best lineup" kolisi kahdessa perakkaisessa
    # lauseessa.
    kenen = "your" if oma_rivisto else "that squad's"
    rivisto = "your 15" if oma_rivisto else "the model's own 15"

    out.append({"code": "cost",
                "text": f"A wildcard here changes {len(sisaan)} of {rivisto}."})

    if suosita:
        out.append({"code": "ev", "text":
                    f"The rebuilt squad projects {paras['ev_per_gw']} points "
                    f"per gameweek more than {kenen} best lineup over "
                    f"{ikkuna}, {paras['ev_total']} in total."})
    else:
        out.append({"code": "hold", "text":
                    f"That's worth {paras['ev_per_gw']} points per gameweek, "
                    f"under the {MIN_EV_PER_GW} the model wants before you burn "
                    f"a chip you only get once. It says hold."})

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

    liputetut = [q for q in squad
                 if isinstance(q.get("chance_next"), int)
                 and q["chance_next"] < 100]
    if liputetut:
        omistus = "your current 15" if oma_rivisto else "the current 15"
        out.append({"code": "flags", "text":
                    f"{len(liputetut)} of {omistus} carry an FPL availability "
                    f"flag right now."})

    if long_view and long_view.get("incoming_att_fdr") is not None             and long_view.get("outgoing_att_fdr") is not None:
        yli = long_view["gws"]
        # 🔴 Loppuvaraus ("that is a team-level read, not xP") on POISTETTU
        # tasta. Sama asia sanottiin 25.8 kolmessa paikassa samassa nakymassa;
        # se on AI-tunnusmerkki ja kolmesti sanottuna se kuulostaa
        # puolustelulta. Varaus elaa nyt vain meta.notes-lohkossa.
        out.append({"code": "long_view", "text":
                    f"Past the projection horizon, over GW{min(yli)}–"
                    f"{max(yli)}, the incoming players' teams average "
                    f"{long_view['incoming_att_fdr']} attack difficulty "
                    f"against {long_view['outgoing_att_fdr']} for the ones "
                    f"leaving."})

    # 🔴 TAMA LAUSE VALEHTELI, JA JULKAISUPORTTI RAKENSI VASTAESIMERKIN.
    # Vanha versio sanoi ehdoitta "Waiting can only lose points here". Suositus
    # on `max(ev_total)`, joten jos uusi runko on jollain kierroksella nykyista
    # HUONOMPI, odottaminen kasvattaa hyotya. Ajettu vastaesimerkki:
    #     GW2 ev 33,00 · GW3 ev 66,00 · GW4 ev 33,00  -> valinta GW3
    # eli paneeli olisi tulostanut "Play it in GW3", taulukon jossa odottaminen
    # tuotti +33, ja niiden viereen lauseen ettei odottaminen voi tuottaa. Sama
    # nakyma kumosi itsensa.
    #
    # Korjaus ei ole pehmentaminen vaan universaalin vaitteen POISTO: lause
    # kertoo mita TASSA datassa tapahtui, ja erikseen sen mita malli ei nae.
    # 🔴 KORJASIN TAMAN KERRAN JA LOIN SAMAN VIAN UUDESSA MUODOSSA.
    # Toinen versio haarautti ehdolla `paras["gw"] == aikaisin_gw` ja sanoi
    # silloin "the rebuilt squad is ahead in every round". Ehto EI implikoi
    # sita: aikaisin voittaa jos SUFFIKSISUMMAT pysyvat pienempina, ja
    # yksittainen kierros saa silti olla tappiollinen. Portin vastaesimerkki,
    # jonka ajoin itse:
    #     deltat  GW2 +33,00 · GW3 -11,00 · GW4 +22,00  -> valinta GW2
    #     taulukko GW2 44,00 · GW3 11,00 · GW4 22,00
    # Myohempi rivi ei voi olla korkeampi ellei jokin kierros ole tappiollinen,
    # eli lukija kumoaa vaitteen suoraan viereisesta taulukosta — tasan sama
    # vikaluokka kuin ensimmaisessa versiossa.
    #
    # Ja OMA testini kattoi vain else-haaran, joten se meni lapi. Vaite
    # johdetaan nyt DELTOISTA eika `gw`-vertailusta.
    # 🔴 TAPPIOLLISET LUETAAN KOKO HORISONTISTA, EI VALITUSTA IKKUNASTA.
    # Ensimmainen yritykseni suodatti `paras["window"]`:iin, jolloin
    # else-tapaus (voittaja ei ole aikaisin) nakyi "ei tappiollisia" -haarana:
    # ikkuna alkaa vasta voittajasta, joten se EI sisalla sita kierrosta jonka
    # takia voittaja siirtyi myohemmaksi. Lause olisi silloin sanonut
    # "Playing it at the first chance..." kierroksesta joka ei ole aikaisin.
    # Ehto "yhtaan tappiollista kierrosta ei ole" implikoi `gw == aikaisin`
    # vain koko horisontin yli laskettuna.
    tappiolliset = sorted(x for x, d in deltat.items() if d < 0)
    if not tappiolliset:
        miksi = ("Playing it at the first chance scores highest here, because "
                 "the rebuilt squad is ahead in every round of the window.")
    elif paras["gw"] == aikaisin_gw:
        miksi = (f"GW{paras['gw']} still scores highest, even though the "
                 f"current squad is ahead in {len(tappiolliset)} of those "
                 f"rounds.")
    else:
        # 🔴 "ahead in the rounds before it" luki KIERROSKOHTAISENA, mutta ehto
        # on summa. "taken together" tekee lauseesta toden.
        miksi = (f"GW{paras['gw']} scores highest here, because the current "
                 f"squad outscores it in the rounds before that, taken "
                 f"together.")
    # 🔴 Viimeinen virke ("That's the case for waiting...") on POISTETTU:
    # edellinen virke sanoi jo saman, ja koristeellinen yhteenveto lopussa on
    # AI-tunnusmerkki.
    out.append({"code": "timing", "text":
                f"Every switch point is scored over the same {horisontti_gws}"
                f"-gameweek window, so the only thing moving is when you play "
                f"it. {miksi} The model can't price what hasn't happened yet, "
                f"so injuries and price moves that land later aren't in this "
                f"number."})
    return out
