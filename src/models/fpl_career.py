"""#55 FPL Career / Season Review — urahistoria jakokorttia varten.

Hakee managerin urahistorian JULKISELLA entry-ID:llä (ei kirjautumista, ei
salasanoja) FPL-API:n entry/{id}/ + entry/{id}/history/ -endpointeista ja
tiivistää sen jakokortin tarvitsemaan muotoon: past_seasons + summary +
viimeisimmän kauden GW-erittely + GoalIQ-malliteaser (#34 rate-team,
#50 opti-baseline — EI satunnaisotos).

Uudelleenkäyttää fpl_rate_team-infran (_fetch_fpl: 10 min TTL-cache +
#52 stale-fallback, RateTeamError, rate_team) — EI duplikoi hakua/cachea.

Esikausi-degradaatio (kriittinen, Hub-oppi #52): past_seasons + summary
palautuvat ympäri vuoden (past-data on aina olemassa); current voi olla
tyhjä 26/27-resetin jälkeen ennen GW1:tä → latest_season palautuu
available=False + selite, EI blank/virhe. Kesän välitila huomioitu:
FPL näyttää juuri päättyneen kauden SEKÄ current- ETTÄ past-listassa →
dedup ettei kausi tuplaannu summaryssä.

Malliteaser on best-effort-kääre: jos squadia ei voi tuoda tai projektio
puuttuu, teaser jätetään pois (ei placeholderia) — urahistoria palautuu silti.

Ei kirjoita mitään; rate-team/xP-polut jäävät bittitarkasti koskemattomiksi.
"""
from __future__ import annotations

import src.models.fpl_rate_team as rt
from src.models.fpl_rate_team import RateTeamError

__all__ = ["career", "RateTeamError"]


def _season_start_year(season_name: str | None) -> int | None:
    """'2025/26' → 2025."""
    if not season_name:
        return None
    try:
        return int(str(season_name).split("/")[0])
    except (ValueError, IndexError):
        return None


def _fetch_history(entry: int) -> tuple[dict, dict]:
    """(entry-root, history). Erottelee 'entry ei ole olemassa' selkeästi."""
    try:
        root = rt._fetch_fpl(f"/entry/{entry}/")
    except RateTeamError as e:
        if e.status_code == 404:
            raise RateTeamError(
                404, f"FPL entry {entry} was not found. Check the ID "
                     "(it is the number in your FPL points-page URL).")
        raise
    history = rt._fetch_fpl(f"/entry/{entry}/history/")
    return root, history


def kausi_alkanut(events) -> bool:
    """Onko kausi alkanut: yksikin kierros on merkitty pelatuksi.

    🔴 PORTIN 18. KIERROS (B2). "Kausi ei ole alkanut" oli paatelty KAYTTAJAN
    tyhjasta `current`-listasta. Se on eri kysymys: lista on tyhja myos
    kesken kautta liittyneella managerilla. Mitattu 7.9.2026 kahdella
    oikealla entryllä (10462380, 10542666): `current == []`, ja kortti sanoi
    *"The new FPL season has not started yet"* silla hetkella kun GW3 oli
    pelattavana. Kolmas perakkainen kierros samasta haarasta.

    Kausi on maailman tila, ei kayttajan; se luetaan bootstrapista.
    """
    for e in (events or []):
        if e.get("finished") or e.get("is_current"):
            return True
    return False


def _tyhjan_kauden_note(events) -> tuple[str, str, str, dict]:
    """(season_state, note) tyhjalle `current`-listalle. Kaksi eri tilaa.

    Bootstrap-haun failaus ei saa kaataa career-vastausta (fail-safe).
    """
    seuraava = None
    for e in (events or []):
        if e.get("is_next") and e.get("deadline_time"):
            seuraava = (e["id"], str(e["deadline_time"])[:10])
            break

    if kausi_alkanut(events):
        # Kausi on kaynnissa, mutta talla managerilla ei ole yhtaan
        # pisteytettya kierrosta. Ei vaitetta kaudesta, vaite managerista.
        if seuraava:
            return ("no_gameweeks_yet",
                    f"No scored gameweeks yet for this team - "
                    f"GW{seuraava[0]} deadline is {seuraava[1]}.",
                    "fantasy.career.note.no_gameweeks_deadline",
                    {"gw": seuraava[0], "day": seuraava[1]})
        return ("no_gameweeks_yet", "No scored gameweeks yet for this team.",
                "fantasy.career.note.no_gameweeks", {})

    if seuraava:
        return ("not_started",
                f"The new FPL season has not started yet - "
                f"GW{seuraava[0]} deadline is {seuraava[1]}.",
                "fantasy.career.note.preseason_deadline",
                {"gw": seuraava[0], "day": seuraava[1]})
    return ("not_started",
            "The new FPL season has not started yet - GW1 is coming up.",
            "fantasy.career.note.preseason", {})


def _latest_season(current: list[dict], past: list[dict],
                   pudotettu: list[int] | None = None,
                   vahvistettu: bool = True, events=None) -> dict:
    """Viimeisimmän kauden GW-erittely current-listasta.

    Kesävälitila: juuri päättynyt kausi näkyy myös past-listassa → nimetään
    sieltä ja merkitään finished (ei tuplalaskentaa summaryssä; ks. career()).
    """
    if not current:
        # 🔴 PORTIN 16. KIERROS: FAIL-CLOSED TUOTTI VAARAN LAUSEEN.
        # 15. kierroksella suodatin kesken olevat kierrokset pois, ja tyhja
        # `current` osui tahan haaraan - jonka teksti on kirjoitettu ERI
        # kysymykseen ("kausi ei ole alkanut"). Mitattu: GW1-viikolla
        # kortti sanoi *"The new FPL season has not started yet"* ja
        # deadlinen MENNEISYYDESSA tulevana, vaikka lukijalla oli pisteet
        # taulussa. Bootstrap alhaalla kesken kauden sama teksti nakyi
        # managerille jolla oli 20 kierrosta pelattuna.
        #
        # Kolmas tila: kausi on alkanut mutta yhtaan kierrosta ei ole
        # todistetusti gradattu.
        # 🔴 PORTIN 17. KIERROS: KAKSI TILAA OLI YHDISTETTY YHDEKSI LAUSEEKSI.
        # "GW20 is under way" on VAITE kierroksen tilasta, ja se vaatii
        # todisteen. Kun bootstrap ei aukea, `final_gws` on fail-closed ja
        # palauttaa tyhjan - jolloin JOKAINEN kierros putoaa "kesken
        # olevana", myos ne jotka gradattiin viikkoja sitten. Kortti
        # ilmoitti silloin lukijalle etta hanen jo pisteytetty kierroksensa
        # on kesken. Emme tienneet sita; emme saaneet vastausta.
        #
        # Tila 1: saimme tapahtumat, eli TIEDAMME etta viimeisin on kesken.
        # Tila 2: emme saaneet mitaan, eli emme voi sanoa kierroksesta
        # yhtaan mitaan. Tila 2 ei saa lainata tilan 1 sanamuotoa.
        # 🔴 Sama vika viela kerran, kolmannessa muodossa (loysin taman
        # portin 18. kierroksen invarianttitestia kirjoittaessani): jos
        # bootstrap ei auennut EIKA kayttajalla ole yhtaan kierrosta, emme
        # tieda onko kausi alkanut - `_tyhjan_kauden_note` olisi vastannut
        # "The new FPL season has not started yet". Vaite kaudesta vaatii
        # tiedon kaudesta.
        if not vahvistettu:
            # 🔴 Portin 18. kierros (B5): edellinen sanamuoto oli
            # *"Try again in a moment"* - sanatarkka kopio sivun VIRHETEKSTISTA
            # (`career.html:733`), siirrettyna tilaan joka ei ole kayttajan
            # virhe, ja kehottaen toimintoon jota ruudulla ei ole (career-lohko
            # latautuu automaattisesti, retry-nappia ei ole). Lisaksi "in a
            # moment" lupaa aikaskaalan jonka FPL:n katkos maaraa, ei me.
            return {
                "available": False,
                "season_state": "unconfirmed",
                "provisional_gws": sorted(pudotettu or []),
                "note": ("FPL is not answering right now, so this season "
                         "is left out."),
                # 🔴 Portin 18. kierros (lisaloydos): `note` renderoitiin
                # mobiilissa RAAKANA, ja se on vain englanniksi - es/pt-lukija
                # sai englanninkielisen lauseen keskelle kaannettya nakymaa.
                # Avain + parametrit, jotta klientti voi kaantaa; `note` jaa
                # varapoluksi vanhoille klienteille.
                "note_key": "fantasy.career.note.unconfirmed",
                "note_params": {},
            }
        if pudotettu:
            # 🔴 Portin 18. kierros (B6): *"GW{n} is under way"* on VAARA
            # ikkunassa `finished=True, data_checked=False` - kaikki ottelut on
            # pelattu, kierros ei ole "kesken". Sama tila putoaa tahan
            # haaraan. "still being scored" on tosi MOLEMMISSA ikkunoissa, ja
            # se on jo kortin oma sanamuoto - yksi rekisteri, ei kahta.
            return {
                "available": False,
                "season_state": "no_final_gw_yet",
                "provisional_gws": sorted(pudotettu),
                "note": (f"GW{max(pudotettu)} is still being scored. Your "
                         f"season numbers appear here when FPL confirms it."),
                "note_key": "fantasy.career.note.still_scoring",
                "note_params": {"gw": max(pudotettu)},
            }
        tila, note, avain, parametrit = _tyhjan_kauden_note(events)
        return {"available": False, "season_state": tila, "note": note,
                "note_key": avain, "note_params": parametrit}

    last = current[-1]
    finished = bool(past) and past[-1].get("total_points") == last.get(
        "total_points") and len(current) >= 38
    season = past[-1].get("season_name") if finished else None

    # 🔴 PORTIN 14. KIERROS: `points` on BRUTTO (verifioitu FPL:n API:sta
    # 7.9). `total_points` sen sijaan on NETTO, ja `career.html:558`
    # renderoi ne SAMALLE RIVILLE ilmaisella julkisella jakokortilla:
    # "This season 149 pts, best GW: 70 pts" kun lukijan oma FPL-sivu
    # sanoo siita kierroksesta 62. Sama rivi, kaksi eri yksikkoa.
    #
    # Ja VALINTA tehtiin bruttolla, joten `best_gw` saattoi nimeta eri
    # kierroksen kuin lukijan oma paras.
    def _netto(g: dict) -> int:
        return int(g.get("points") or 0) - int(g.get("event_transfers_cost") or 0)

    played = [g for g in current if g.get("points") is not None]
    best = max(played, key=_netto) if played else None
    worst = min(played, key=_netto) if played else None
    return {
        "available": True,
        "season_state": "available",
        "season": season,
        "finished": finished,
        "total_points": last.get("total_points"),
        "overall_rank": last.get("overall_rank"),
        "best_gw": ({"gw": best["event"], "points": best["points"],
                     "points_net": _netto(best)} if best else None),
        "worst_gw": ({"gw": worst["event"], "points": worst["points"],
                      "points_net": _netto(worst)} if worst else None),
        "total_hits": sum(int(g.get("event_transfers_cost") or 0)
                          for g in current),
        "bench_points": sum(int(g.get("points_on_bench") or 0)
                            for g in current),
        "gws": [{"gw": g.get("event"), "points": g.get("points"),
                 "points_net": _netto(g),
                 "overall_rank": g.get("overall_rank")} for g in current],
    }


def _xp_vs_benchmark(rating: dict) -> float | None:
    """Joukkueen XI-summa miinus vertailukohta, kapteeniton molemmilta.

    None jos kumpikaan puuttuu — kortti putoaa silloin prosenttiin eika
    keksi lukua.
    """
    oma = rating.get("team_xp_horizon_no_captain")
    vertailu = rating.get("optimal_team_xp")
    if not isinstance(oma, (int, float)) or not isinstance(
            vertailu, (int, float)):
        return None
    return round(float(oma) - float(vertailu), 1)


def _model_teaser(entry: int) -> dict | None:
    """GoalIQ-kääre-kiila: nykyisen squadin projektio #34-rate-teamilla
    (#50: percentile = % of the best possible budget team, EI satunnaisotos).
    Best-effort: mikä tahansa failure → None (teaser pois, ei placeholderia)."""
    try:
        rated = rt.rate_team(entry=entry)
    except Exception:
        return None
    rating = rated.get("rating") or {}
    if not rating.get("team_xp_gw"):
        return None
    return {
        "gw": rated["meta"].get("gw"),
        "team_xp_gw": rating.get("team_xp_gw"),
        "team_xp_horizon": rating.get("team_xp_horizon"),
        "percentile": rating.get("percentile"),
        # 🔴 4.9.2026, julkaisuportin loydos. Jakokortti (career.html) kirjoitti
        # "% of the best possible budget squad" LUKEMATTA `optimal_proven`ia,
        # koska tama teaser ei valittanyt lippua eteenpain. SPA lukee sen
        # oikein (RateTeam.svelte: `optimal_proven === false`), joten sama
        # vaite kulki kahta polkua ja vain toinen oli portin takana.
        #
        # Mitattu samalla entrylla 116920: `team_xp_horizon_no_captain` 322,42
        # vs `optimal_team_xp` 310,77 -> oma joukkue VOITTAA vertailukohdan
        # 11,65 xP:lla, `beats_benchmark` True, ja `percentile` leikataan
        # sataan. Kortti olisi siis tulostanut "100% of the best possible
        # budget squad" vertailukohdasta joka ei ole paras mahdollinen.
        # Tasan se ontto imartelu jota fpl_rate_team.py:666 varoittaa.
        "optimal_proven": rating.get("optimal_proven"),
        "beats_benchmark": rating.get("beats_benchmark"),
        # Ylijaama vertailukohtaan. `gap_to_optimal_xp` on `max(0, ...)` eli
        # NOLLA juuri voittajille, joten se ei kelpaa: kortti tarvitsee luvun
        # eika taputusta selkaan. Vertailu tehdaan ILMAN kapteenia, koska
        # `optimal_team_xp` on kapteeniton XI-summa — kapteenillinen 356,7
        # vastaan kapteeniton 310,77 olisi luku vaarasta sarakkeesta.
        "xp_vs_benchmark": _xp_vs_benchmark(rating),
        "horizon_gw": rated["meta"].get("horizon_gw"),
        "rating_method": rated["meta"].get("rating_method"),
        "note": ("Projected with the same match model behind GoalIQ's "
                 "public pre-match-logged track record."),
    }


def career(entry: int) -> dict:
    """Urahistoria + summary + viimeisin kausi + malliteaser entry-ID:llä."""
    root, history = _fetch_history(entry)
    past = list(history.get("past") or [])
    current = list(history.get("current") or [])
    # 🔴 PORTIN 15. KIERROS: KESKEN OLEVA KIERROS EI SAA PAATYA KORTILLE
    # LOPULLISENA. `_latest_season`in `finished` koskee KAUTTA, ei kierrosta,
    # eika tama moduuli tuonut `fpl_gw_finality`a lainkaan.
    #
    # Mitattu tuotannosta 7.9 (entry 116920, GW3 finished=False,
    # data_checked=False): kortti sanoi "Best overall rank 659,556" ja
    # "This season 207 pts" GW3:n provisionaalisesta rivista, samalla kun
    # SAMAN TUOTTEEN Season target -rivi sanoi "After GW2: 2,090,418
    # overall" - koska `season_rank_block` vaatii `finished AND
    # data_checked`. Sama kayttaja, sama hetki, kerroin 3,2. Ja `207`
    # liikkuu kun GW3:n bonukset laskeutuvat.
    #
    # Sama yksi lukija kuin muualla: kesken oleva kierros pudotetaan.
    # FAIL-CLOSED kuten `fpl_gw_finality`: jos emme saa bootstrapia, emme voi
    # todistaa yhtaan kierrosta lopulliseksi, joten kesken oleva ei paady
    # kortille. Mieluummin yksi kierros pois kuin vaara luku kuvaan.
    from src.models.fpl_gw_finality import final_gws
    try:
        _events = (rt.get_bootstrap() or {}).get("events")
    except Exception:
        _events = None
    # Saimmeko tapahtumat lainkaan. Tama EI ole sama kuin "onko lopullisia
    # kierroksia": tyhja `_lopulliset` syntyy molemmista, ja vain toisessa
    # meilla on oikeus sanoa kierroksesta jotain.
    vahvistettu = isinstance(_events, list) and bool(_events)
    _lopulliset = final_gws(_events)
    provisional_dropped = sorted(
        int(g["event"]) for g in current
        if isinstance(g.get("event"), int) and g["event"] not in _lopulliset)
    # 🔴 Portin 16. kierros: kausi ON alkanut vaikka yhtaan kierrosta ei
    # olisi gradattu. Kausilaskurit lukevat siksi SUODATTAMATONTA listaa.
    kausi_alkanut = bool(current)
    # 🔴 PORTIN 17. KIERROS: `all_time_points` LASKI GRADAAMATTOMIA PISTEITA.
    # `kausi_summa` luettiin SUODATTAMATTOMASTA listasta, joten kun yhtaan
    # kierrosta ei ollut vahvistettu, kortti nayttti silti kuluvan kauden
    # pisteet uran summassa - samalla kun viereinen solu sanoi "Not final
    # yet". Sama luku, kaksi vastausta samassa kuvassa.
    #
    # Kauden panos uran summaan lasketaan VAHVISTETUISTA kierroksista.
    # Jos mikaan ei ole lopullinen, panos on 0 - mutta kausi on silti
    # pelattu, joten `seasons_played` +1 (ks. `in_progress` alla).
    _vahvistetut = [g for g in current
                    if isinstance(g.get("event"), int)
                    and g["event"] in _lopulliset]
    # Kesan dedup: juuri paattynyt kausi on JO past-listassa, eika sita saa
    # laskea kahdesti. Tama paatos on tehtava suodattamattomasta datasta -
    # muuten se muuttuisi sen mukaan saimmeko bootstrapin.
    kausi_paattynyt = bool(
        past and current
        and past[-1].get("total_points") == current[-1].get("total_points")
        and len(current) >= 38)
    current = _vahvistetut
    chips = [c for c in (history.get("chips") or [])
             if not isinstance(c.get("event"), int)
             or c["event"] in _lopulliset]  # sama suodatin kuin luvuilla:
    # vastaus ei saa sanoa "3xc GW3" samalla kun luvut pysahtyvat GW2:een.

    latest = _latest_season(current, past, provisional_dropped,
                            vahvistettu, _events)
    if latest.get("available"):
        latest["chips_used"] = [{"name": c.get("name"), "gw": c.get("event")}
                                for c in chips]

    past_seasons = [{
        "season": s.get("season_name"),
        "points": s.get("total_points"),
        "rank": s.get("rank"),
    } for s in past]

    # Summary koko uralta. Kesävälitila: finished current on JO past-listassa
    # → ei lisätä toiseen kertaan. Keskeneräinen current lasketaan mukaan.
    # 🔴 Portin 16. kierros: kausi lasketaan mukaan kun se on ALKANUT, ei kun
    # se on gradattu. Aiemmin `available` oli ehtona, ja 15. kierroksen
    # suodatin teki siita False:n aina kun yhtaan kierrosta ei ollut
    # todistetusti valmis - jolloin `all_time_points` menetti koko kuluvan
    # kauden hiljaa (mitattu bootstrap alhaalla: 3300 -> 2100, 2 -> 1 kautta).
    in_progress = kausi_alkanut and not kausi_paattynyt
    all_time = sum(int(s.get("total_points") or 0) for s in past)
    seasons_played = len(past)
    all_time_provisional = False
    # Viimeisin kierros joka on mukana luvuissa. Tama on se mita pinnan on
    # sanottava: "All-time points to GW2" on tarkistettavissa lukijan omalta
    # FPL-sivulta, "(confirmed)" ei ole - se kuvaa FPL:n `data_checked`-lippua
    # jota lukija ei tieda olevan olemassa (portin 18. kierros, kysymys A).
    all_time_through_gw = (max(int(g["event"]) for g in current)
                           if current else None)
    if in_progress:
        # `available` on TASAN "kaudesta on vahintaan yksi vahvistettu
        # kierros" (`_latest_season` palauttaa False vain tyhjalle
        # suodatetulle listalle). Siksi tassa ei ole toista, vaihtoehtoista
        # summaa jota voisi vahingossa muuttaa: joko luku on vahvistettu tai
        # panos on 0. Erillinen `kausi_summa`-varapolku poistettiin 7.9,
        # koska se oli tasan se paikka jossa gradaamattomat pisteet paativat
        # uran summaan.
        # 🔴 PORTIN 18. KIERROS (B1). Lippu oli `not available`, eli se
        # laukesi VAIN kun yhtaan kierrosta ei ole vahvistettu. Se on
        # harvinainen tila. Tavallinen tila on "osa kierroksista pudotettu",
        # ja siina lippu oli False vaikka summa oli vajaa. Mitattu
        # tuotannosta 7.9 (entry 116920): kortti nayttti 149 paljaalla
        # labelilla "All-time points" kun lukijan oma FPL-sivu sanoi 221.
        #
        # Ehto on nyt SUMMAN oma ehto, ei haaran: onko kuluvasta kaudesta
        # jotain jatetty pois.
        if latest.get("available"):
            all_time += int(latest.get("total_points") or 0)
        all_time_provisional = (not latest.get("available")
                                or bool(provisional_dropped))
        seasons_played += 1

    best_season = None
    if past:
        b = max(past, key=lambda s: int(s.get("total_points") or 0))
        best_season = {"season": b.get("season_name"),
                       "points": b.get("total_points"),
                       "rank": b.get("rank")}
    ranks = [int(s["rank"]) for s in past if s.get("rank")]
    if in_progress and latest.get("overall_rank"):
        ranks.append(int(latest["overall_rank"]))

    since = _season_start_year(past[0].get("season_name")) if past else None
    if since is None:
        joined = str(root.get("joined_time") or "")
        since = int(joined[:4]) if joined[:4].isdigit() else None

    first = (root.get("player_first_name") or "").strip()
    last_n = (root.get("player_last_name") or "").strip()

    result = {
        "meta": {
            "entry": entry,
            "source": "FPL public entry API (no login)",
            "note": ("Career history from the official FPL API. "
                     "For fun, not betting advice."),
        },
        "manager": {
            "name": " ".join(x for x in (first, last_n) if x) or None,
            "team_name": root.get("name"),
            "since": since,
        },
        "past_seasons": past_seasons,
        "summary": {
            # Kesken olevat kierrokset jotka jatettiin POIS luvuista, jotta
            # pinta voi sanoa sen eika lukija ihmettele miksi luku eroaa
            # hanen omasta FPL-sivustaan.
            "provisional_gws_excluded": provisional_dropped,
            "seasons_played": seasons_played,
            "all_time_points": all_time,
            # True = kuluvasta kaudesta ei ole yhtaan vahvistettua kierrosta,
            # joten sen panos on 0. Pinnan on sanottava se.
            "all_time_provisional": all_time_provisional,
            # Viimeisin kierros joka on luvussa mukana; None = ei yhtaan.
            "all_time_through_gw": all_time_through_gw,
            "best_season": best_season,
            "best_rank": min(ranks) if ranks else None,
            "avg_rank": round(sum(ranks) / len(ranks)) if ranks else None,
            "since": since,
        },
        "latest_season": latest,
    }
    teaser = _model_teaser(entry)
    if teaser:
        result["model_teaser"] = teaser
    return result
