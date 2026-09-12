"""Beat the Model V2 vaihe c: Season race -datan kokoaminen (13.8).

Yhdistää mallin gradatut kierrospisteet (data/model_squad_gw_scores.json,
vaihe b) ja käyttäjän oman FPL-historian kumulatiiviseksi eroksi.

MIKSI PALVELIMELLA EIKÄ KLIENTISSÄ (poikkeus speciin, tietoinen):
spec ehdotti kumulatiivisen eron laskemista klientissä, mutta V1-tuloskortin
oma linjaus on *"klientti ei laske pisteitä — se summaa backend-graderin
immutable-tulokset"*, ja klientteja on kaksi (web + mobiili). Sama kaava
kahtena toteutuksena on tasan se rakenne josta 28.7 syntyi kaksi eri lukua
mallin "parhaasta joukkueesta". Yksi lähde, kaksi rendererää.

REHELLISYYS (V1-linja säilyy):
  - Ennen ensimmäistä gradausta ei arvata: available=False + selite siitä
    milloin luvut tulevat.
  - Kierros joka on gradattu mallille mutta puuttuu käyttäjän historiasta
    (esim. liittyi kesken kauden) jätetään eroon laskematta — sitä EI
    tulkita nollaksi, koska nolla olisi väite jota ei tehty.
  - Malli ei pelaa chippejä; se kerrotaan datassa asti (`model_plays_chips`),
    jotta paneelin ei tarvitse päätellä sitä copysta.
"""
from __future__ import annotations

NOTE_NOT_STARTED = ("The model's first squad is locked before the GW1 "
                    "deadline. First scores land once GW1 finishes.")
NOTE_NO_ENTRY = ("Add your FPL team ID to see your own line against the "
                 "model.")

# BACKEND-EN-VUOTAA-ES-PT (23.8): jokaisella kayttajalle nakyvalla proosalla on
# vakaa tunniste, jotta es/pt-klientti voi kaantaa sen omasta i18n:staan. Proosa
# jaa paikalleen varakielena - tama on additiivinen eika riko yhtaan klienttia.
CODE_NOT_STARTED = "model_race.note.not_started"
CODE_NO_ENTRY = "model_race.note.no_entry"
CODE_NO_OVERLAP = "model_race.note.no_overlap"


def model_points_net(row: dict) -> int:
    """Mallin kierrospistemaara NETTONA rivin omista kentista.

    🔴 Portin 16. kierros: `points_net`iin nojaaminen oli fail-open. Samaan
    artefaktiin kirjoittaa kaksi eri skriptia eri skeemalla, ja jo
    julkaistut rivit eivat saa kentta koskaan (`build()` ohittaa lopulliset).
    Netto johdetaan siksi lukuhetkella: `points - transfer_cost`, ja
    puuttuva kustannus on 0 (FPL:n oma oletus).

    Miksi netto: malli ei tavallisesti ota hitteja, joten brutto antaisi
    sille oman hittinsa verran etumatkaa kayttajaa vastaan - ja mallin
    entry on julkinen, joten lukija voi tarkistaa.
    """
    if not isinstance(row, dict):
        return 0
    pisteet = row.get("points_net")
    if isinstance(pisteet, int):
        return pisteet
    return int(row.get("points") or 0) - int(row.get("transfer_cost") or 0)


def _user_points_by_gw(entry_history: dict | None) -> dict[int, dict]:
    """FPL entry/{id}/history/ → {gw: {"points": int, "bench": int}}.

    🔴 PREMISSI OLI VÄÄRIN (mitattu 7.9.2026, portin 10. kierros).
    `points` on FPL:n oma kierrospistemäärä **ENNEN** siirtokustannusta, ei
    sen jälkeen. Verifioitu FPL:n omasta API:sta: entry 12345 GW3
    `points: 70`, `event_transfers_cost: 8`, ja kausisumma kasvoi
    87 -> 149 eli **62 = 70 - 8**. Käyttäjän oma FPL-sivu näyttää netto.

    Tämä lohko ei siis vertaa sitä lukua jonka käyttäjä näkee, vaan
    hittiä edeltävää lukua — eli hittiviikolla käyttäjä näyttää meillä
    4 tai 8 pistettä paremmalta kuin omalla sivullaan.

    KORJATTU 7.9 (portin 11. kierros) mittauksen jälkeen: kaikilla
    seuratuilla entryillä (116920, 4089628, 895045) on **0 hittikierrosta**
    tällä kaudella, joten netto-vertailuun siirtyminen ei liikuta yhtäkään
    julkaistua lukua. Se estää väärän väitteen vasta silloin kun joku ottaa
    hitin — eli ennen kuin vika ehtii syntyä.
    """
    out: dict[int, dict] = {}
    for row in (entry_history or {}).get("current") or []:
        gw = row.get("event")
        if gw is None:
            continue
        kustannus = int(row.get("event_transfers_cost") or 0)
        # 🔴 KONVENTIO (portin 13. kierros): `points` on FPL:n oma kentta
        # SELLAISENAAN eli brutto, ja `points_net` on se luku jonka lukija
        # nakee. Sama nimeaminen kuin `fpl_rate_team` ja `fpl_gw_review`.
        #
        # Aiemmin tama moduuli teki painvastoin (`points` = netto), ja se oli
        # RAKENTEELLINEN SYY sille etta jakokortti jai bruttoon 13. kierrokseen
        # asti: kirjoittajan piti muistaa kummassa moduulissa han on.
        out[int(gw)] = {
            "points": int(row.get("points") or 0),
            "points_net": int(row.get("points") or 0) - kustannus,
            "bench": int(row.get("points_on_bench") or 0),
            "transfer_cost": kustannus,
        }
    return out


# Kolme tilaa, yksi lukija. `provisional` yksin on tosi kahdessa taysin eri
# tilanteessa, ja `fantasy.race.provisional_note` nimesi molemmissa syyksi
# bonuksen. Mitattu 7.9.2026: GW3 oli `is_current` ja `finished` False - eli
# otteluita oli KESKEN - ja teksti sanoi lukijalle "FPL hasn't confirmed bonus
# points yet". Lukija joka laskee omat bonuksensa ei paase lukuun.
#
# `unknown` on tarkoituksellinen kolmas haara eika virhe: kun rivilla ei ole
# `finished`-kenttaa (vanhat rivit, toinen kirjoittaja), emme voi sanoa
# KUMMASTA tilasta on kyse. Silloin teksti ei nimea mekanismia lainkaan.
# Vrt. muisti `mekanismin-nimeaminen-on-vaite`.
ROW_FINAL = "final"
ROW_IN_PROGRESS = "in_progress"      # otteluita kesken
ROW_AWAITING_CHECK = "awaiting_check"  # pelattu, FPL ei ole vahvistanut
ROW_UNKNOWN = "unknown"


def row_state(row: dict) -> str:
    """Kierroksen tila rivin omista kentista. Ei kutsu mitaan ulkoista.

    🔴 PORTIN 21. KIERROS: ehto luki `finished`ia, joka on FPL:n
    TAPAHTUMALIPPU ja kaantyy vasta bonusten jalkeen. Mitattu 7.9: GW3:n
    `events[3].finished` oli False kun kaikki 10 ottelua oli pelattu, eli
    teksti olisi sanonut "still being played" pelatusta kierroksesta.
    Kentta on nyt `all_fixtures_played`, jonka gradaaja laskee otteluista.
    """
    if not isinstance(row, dict):
        return ROW_UNKNOWN
    if not row.get("provisional"):
        return ROW_FINAL
    pelattu = row.get("all_fixtures_played")
    if pelattu is True:
        return ROW_AWAITING_CHECK
    if pelattu is False:
        return ROW_IN_PROGRESS
    return ROW_UNKNOWN


# 🔴 PORTIN 22. KIERROS: JULKAISTU LUKU OLI VAARIN TUOTANNOSSA.
#
# Mitattu 7.9.2026 12:08 UTC ilmaispinnalta:
#   /api/fantasy/model-race?entry=116920 -> GW3 malli 58, sina 72, ero 14
#   /entry/116920/history/               -> GW3 points 72
# Sama entry, sama kierros, kaksi eri lukua. Mallin puoli luettiin
# **jaadytetysta artefaktista** (`generated_at` 6.9 20:25, 15 h 43 min
# vanha; edellinen vali oli 5 vrk) ja kayttajan puoli **pyyntohetkella**
# FPL:sta. GW3 oli provisionaalinen, bonukset olivat sittemmin tulleet, ja
# lukija nakemassa "olet mallia edella 14 pisteella" kun tosiasiallinen ero
# oli 0. Koko ero oli vanhentumista.
#
# SAANTO (6a kohta 1): provisionaalisen kierroksen KUMPIKIN puoli on
# luettava samasta hetkesta. Jos mallin puolta ei saada elavana, riviltä
# EI TUOTETA EROA lainkaan - vertailu kahden eri hetken valilla ei ole
# vertailu. Mieluummin puuttuva luku kuin vaara luku.
def build_race(scores_log: dict | None, entry_history: dict | None,
               premium: bool = True,
               model_history: dict | None = None) -> dict:
    """Puhdas ydin: mallin loki + käyttäjän historia → race-payload.

    `model_history` = mallin oma `entry/{id}/history/` PYYNTOHETKELTA.
    Provisionaaliset kierrokset luetaan siita; ilman sita ne eivat tuota
    eroa (ks. lohkokommentti yllä).
    """
    rows = list((scores_log or {}).get("gameweeks") or [])
    rows.sort(key=lambda r: int(r.get("gw") or 0))

    if not rows:
        return {
            # Ei gradattuja kierroksia: lippu on False koska chippeja EI OLE
            # pelattu, ei koska niita ei pelata. `chips_played` tyhjana
            # kertoo saman ilman oletusta.
            "meta": {"available": False, "graded_gws": 0, "masked": False,
                     "model_plays_chips": False, "chips_played": [],
                     "note": NOTE_NOT_STARTED,
                     "note_code": CODE_NOT_STARTED},
            "totals": {"model": 0, "you": None, "diff": None},
            "gameweeks": [],
        }

    user = _user_points_by_gw(entry_history)
    has_entry = entry_history is not None
    # Mallin elavat luvut samalta hetkelta kuin kayttajan.
    model_live = _user_points_by_gw(model_history)

    out_rows = []
    model_total = 0
    model_season = 0
    you_total = 0
    cum = 0
    compared = 0
    for r in rows:
        gw = int(r.get("gw") or 0)
        # Portin 15. kierros: MALLIN puoli myos netosta. Kayttajan puoli
        # korjattiin 11. kierroksella, mallin jai bruttoon - eli malli
        # olisi voittanut oman hittinsa verran.
        mp = model_points_net(r)
        # Provisionaalinen rivi: mallin luku elavasta lahteesta, tai rivi ei
        # vertaa mihinkaan. `stale` kertoo pinnalle kumpi tapaus on kyseessa.
        stale = False
        if r.get("provisional"):
            elava = model_live.get(gw)
            if elava is not None:
                mp = elava["points_net"]
            else:
                stale = True

        u = user.get(gw)
        # 🔴 PORTIN 23. KIERROS (B1+B2): YKSI PAATOS, EI KAHTA EHTOA.
        # 22. kierros lisasi stale-haaran mutta jatti alkuperaisen
        # epasymmetrian: `model_total` kasvoi joka ei-stale-rivilla ja
        # `you_total` vain kun kayttajalla oli rivi. Kesken kautta liittynyt
        # manageri sai *"Model 149 - You 100"* ja sen alle lauseen *"the
        # model is 8 points ahead"*. Lukija nakee 49 pisteen kuilun ja
        # lauseen joka sanoo 8. Ja kommentti summien vieressa VAITTI etta
        # ne kattavat samat kierrokset.
        #
        # Rivi ja summa tulevat nyt SAMASTA paatoksesta: rivi lasketaan
        # mukaan tasan silloin kun se vertaa.
        vertaa = (u is not None) and not stale
        if not stale:
            # Mallin OMA kausisumma, riippumatta vertailujoukosta. Tama on
            # eri luku kuin `totals.model`, ja siksi eri nimella: paneeli saa
            # nayttaa mallin kauden, muttei sita "sinua" vastaan.
            model_season += mp
        if vertaa:
            model_total += mp
            you_total += u["points_net"]
            cum += u["points_net"] - mp
            compared += 1

        row = {
            "gw": gw,
            # 🔴 Stale-rivilta EI julkaista mallin lukua lainkaan. 22. kierros
            # jatti eron pois mutta jatti VANHENTUNEEN LUVUN ruudulle
            # kayttajan luvun viereen ("you 72 - model 58"): lukija vahentaa
            # itse, ja 14 pisteen vaara vaite on yha naytolla - vain ilman
            # etta me kirjoitamme sen. Fail-closed ei ole fail-closed jos
            # vaara luku jaa ruudulle.
            "model_points": None if stale else mp,
            "fpl_average": r.get("fpl_average"),
            # Rivikohtainen lippu, jotta klientti voi merkita YHDEN kierroksen
            # ilman etta sen tarvitsee ristiinlukea meta.provisional_gws.
            "provisional": bool(r.get("provisional")),
            # Pinta ei saa paatella syyta `provisional`ista: ks. `row_state`.
            "state": row_state(r),
            # True = mallin luku on jaadytetysta artefaktista ja kayttajan
            # elavasta lahteesta, eli eri hetkesta. Rivi ei tuota eroa.
            "stale_model_points": stale,
            "your_points": None,
            "diff": None,
            "cumulative_diff": None,
        }
        if u is not None:
            row["your_points"] = u["points_net"]
        if vertaa:
            row["diff"] = u["points_net"] - mp
            row["cumulative_diff"] = cum
        if premium:
            # "Missä ero syntyi" — nämä ovat premiumin erittely, eivät
            # kilpailun tulos (free näkee eron, premium sen syyn).
            row["model_captain_id"] = r.get("captain_id")
            row["model_captain_reason"] = r.get("captain_reason")
            row["model_captain_points"] = r.get("captain_points_added")
            row["model_bench_points"] = r.get("bench_points")
            row["model_autosubs"] = r.get("autosubs") or []
            if u is not None:
                row["your_bench_points"] = u["bench"]
                row["your_transfer_cost"] = u["transfer_cost"]
        out_rows.append(row)

    note = None
    note_code = None
    if not has_entry:
        note = NOTE_NO_ENTRY
        note_code = CODE_NO_ENTRY
    elif compared == 0:
        # 23.8: em dash pois. Julkinen API-payload on copy-pintaa siina missa
        # HTML, ja em dash on kielletty copyssa.
        note = ("No overlapping gameweeks yet: your history starts after "
                "the model's first graded round.")
        note_code = CODE_NO_OVERLAP

    # 25.8: provisionaaliset kierrokset kannetaan metaan asti. FPL kaantaa
    # `data_checked`:in vasta tuntien viiveella viimeisen ottelun jalkeen, ja
    # gradaaja kirjoittaa rivin heti kun kaikki ottelut on pelattu. Luku nakyy
    # siis heti, mutta 🔴 se ei saa esiintya lopullisena: klientin on
    # merkittava nama kierrokset. Tyhja lista = kaikki luvut ovat lopullisia.
    # 🔴 Portin 20. kierros: `int(r.get("gw") or 0)` teki puuttuvasta
    # kierroksesta nollan, ja pinta olisi piirtanyt "GW0".
    provisional_gws = [int(r["gw"]) for r in rows
                       if r.get("provisional") and r.get("gw")]

    # 🔴 LIPPU MITATAAN RIVEISTA, EI KOVAKOODATA (12.9.2026).
    # Tama oli `False` vakiona kahdessa kohdassa, ja SPA renderoi sen varassa
    # lauseen "The model's squad is locked before every deadline and plays no
    # chips." Mitattu `data/model_squad_gw_scores.json`:sta:
    #   GW1 41 p  active_chip None
    #   GW2 108 p active_chip 'wildcard'
    #   GW3 72 p  active_chip '3xc'
    # Eli **kauden kaksi isointa lukua ovat chip-lukuja**, ja lause niiden
    # alla sanoi ettei chippeja pelata. Moduulin oma docstring perusteli
    # kentan sanomalla "jotta paneelin ei tarvitse paatella sita copysta" —
    # mutta kentta ei lukenut mitaan, joten se oli nimi eika mittaus
    # (muisti: `portti-joka-etsii-merkkijonoa-ei-mittaa-arvoa`).
    # `chips_played` on mukana jotta pinta voi kertoa TOTUUDEN eika pelkkaa
    # vaikenemista.
    chips_played = sorted({str(r["active_chip"]) for r in rows
                           if r.get("active_chip")})
    return {
        "meta": {
            "available": True,
            "graded_gws": len(rows),
            "compared_gws": compared,
            "masked": not premium,
            "model_plays_chips": bool(chips_played),
            "chips_played": chips_played,
            # 🔴 Portin 21. kierros: mallin oma puoli on eri perusteella
            # kahdella julkisella pinnalla. TASSA vertailu on malli vs
            # KAYTTAJA, ja molemmat ovat nettoja (symmetria). `gw_recap`in
            # track record vertaa mallia FPL:n julkaisemaan keskiarvoon,
            # jonka perustaa emme tieda, ja kayttaa siella bruttoa. Tanaan
            # sama luku (hitit 0), mutta ensimmaisella hittikierroksella ne
            # eroavat - joten kumpikin pinta sanoo perusteensa.
            "model_points_basis": "net: model points after its own transfer "
                                  "hits, compared with your points on the "
                                  "same basis",
            "provisional_gws": provisional_gws,
            "provisional_states": {str(x["gw"]): x["state"] for x in out_rows
                                   if x["state"] != ROW_FINAL},
            "note": note,
            "note_code": note_code,
        },
        # Summat kattavat TASAN vertailujoukon (`compared_gws`) kun
        # kayttajalla on entry. Ilman entrya vertailujoukkoa ei ole, ja
        # `model` on mallin oma kausisumma - `you` ja `diff` ovat silloin
        # None, joten epasymmetriaa ei paase syntymaan.
        "totals": {
            # Vertailujoukon summa: sama kierrosjoukko kuin `you` ja `diff`.
            "model": model_total if (has_entry and compared) else model_season,
            # Mallin koko kausi. ERI LUKU kuin `model` heti kun kayttajan
            # historia ei kata kaikkia kierroksia - siksi omalla nimellaan,
            # jotta pinta ei voi nayttaa sita "sinua" vastaan.
            "model_season": model_season,
            "you": you_total if compared else None,
            "diff": cum if compared else None,
            # Kierrokset jotka jaivat pois koska puolet olivat eri hetkesta.
            "stale_gws": [x["gw"] for x in out_rows
                          if x.get("stale_model_points")],
        },
        "gameweeks": out_rows,
    }
