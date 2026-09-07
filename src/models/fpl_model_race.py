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
            "meta": {"available": False, "graded_gws": 0, "masked": False,
                     "model_plays_chips": False, "note": NOTE_NOT_STARTED,
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
        if not stale:
            model_total += mp
        row = {
            "gw": gw,
            "model_points": mp,
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
        u = user.get(gw)
        if u is not None:
            row["your_points"] = u["points_net"]
            if stale:
                # Kaksi eri hetkea ei ole vertailu. Luku nakyy, ero ei.
                row["diff"] = None
                row["cumulative_diff"] = None
            else:
                you_total += u["points_net"]
                cum += u["points_net"] - mp
                compared += 1
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

    return {
        "meta": {
            "available": True,
            "graded_gws": len(rows),
            "compared_gws": compared,
            "masked": not premium,
            "model_plays_chips": False,
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
        # Molemmat summat kattavat TASAN samat kierrokset. Jos jonkin rivin
        # mallipuoli on vanhentunut, rivi jaa pois molemmilta puolilta - ei
        # vain erosta. Muuten paneeli nayttaisi "malli 207 / sina 221 /
        # ero 0", eli kaksi lukua ja niiden kanssa ristiriitaisen eron
        # (muisti: varoitus-kaukana-luvusta).
        "totals": {
            "model": model_total,
            "you": you_total if compared else None,
            "diff": cum if compared else None,
            # Kierrokset jotka jaivat pois koska puolet olivat eri hetkesta.
            "stale_gws": [x["gw"] for x in out_rows
                          if x.get("stale_model_points")],
        },
        "gameweeks": out_rows,
    }
