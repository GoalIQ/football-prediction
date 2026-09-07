"""THE MODEL SAYS: luonnollinen kieli lukujen VIERESSA (25.8.2026).

Team Manager / FM-silmukka, vaihe 1. Mockupin "The model says" -paneeli.

🔴 JOKAINEN LAUSE ON JOHDETTU, EI VAPAAMUOTOINEN. Nama merkkijonot ovat
JULKISTA ENGLANNINKIELISTA TEKSTIA jotka renderoidaan kayttajalle, eli niita
koskee sama portti kuin sivucopya. Siksi:

  - Jokainen lause rakennetaan mallista tulleesta LUVUSTA, ja luku on lauseessa
    nakyvissa. Lukija voi verrata lausetta viereiseen numeroon.
  - Ei yhtaan lausetta joka VAITTAA jotain mita luku ei sano. "Captain let you
    down" on tulkinta; "your captain returned 4 against a projected 11.4" on
    havainto.
  - Ei superlatiiveja joita ei ole mitattu. "biggest miss" on sallittu VAIN kun
    se on tosiasiassa listan minimi.

🔴 EI EM DASHIA. Kielletty koko projektin copyssa.

🔴 EI KEHUA MALLIA. Paneeli kertoo myos kun malli oli vaarassa, ja se on
saannon tarkein puoli: "the model says" jonka kaikki lauseet imartelevat mallia
on mainos eika paneeli.
"""
from __future__ import annotations


def _pts(n: float | int) -> str:
    """Pistemuotoilu: aina yksi desimaali projektioille.

    🔴 F5 (portin 7. kierros): muoto pudotti desimaalin kun luku oli lahella
    kokonaista, ja viereinen rivi ei. Mitattu: **10,0 % kaikista
    kierrostotaaleista**. Silloin paneeli renderoi "72 scored against 71.0
    projected +1.0" ja SAMAN nakyman alla "scored 72 against a projected 71.
    You beat the model by 1." Sama luku, kaksi esitysta, sama silmayksella -
    sama vikaluokka kuin U2/B3/C5/D1, mutta luku ei ole vaara.

    Toteutuneet pisteet ovat kokonaislukuja ja renderoityvat sellaisina;
    projektiot saavat aina desimaalin.
    """
    # Vain KOKONAISLUKUTYYPPI renderoityy ilman desimaalia. Float 71.0 on
    # projektio joka sattuu osumaan tasan, ja viereinen rivi nayttaa siita
    # "71.0" - juuri se ero oli F5.
    if isinstance(n, int) and not isinstance(n, bool):
        return str(n)
    return f"{float(n):.1f}"


def _nimi(rivi: dict | None) -> str | None:
    return (rivi or {}).get("web_name")


def _shown_1dp(x: float) -> float:
    """Sama pyoristys kuin klientin `Number.toFixed(1)`.

    🔴 D1 (portin 5. kierros). Python `f"{x:.1f}"` pyoristaa tasatilanteessa
    PARILLISEEN (half-even), JS `toFixed(1)` SUUREMPAAN (half-up). Tasatilanne
    syntyy aina kun raaka summa on tasan x.25 tai x.75 - ja se on tavallista,
    koska rivien `xp` on pyoristetty kahteen desimaaliin. Portin brute force
    200 000 kierroksella: **2 021 eroavaa tapausta (1,0 %)**, ja summausjarjestys
    ei aiheuttanut yhtaan (vika on tasan saannossa).

    Mitattu tapaus: raaka summa 39.25 -> kortti "39.3", lause "39.2", ja
    erotukset 15.7 vs 15.8 allekkain samassa nakymassa.

    `Decimal(float)` ottaa doublen TARKAN binaariarvon, joten quantize
    ROUND_HALF_UP vastaa toFixedia myos silloin kun desimaaliesitys on
    harhaanjohtava.
    """
    from decimal import Decimal, ROUND_HALF_UP
    return float(Decimal(float(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _raw(rivi: dict, kentta: str):
    """Kertoimeton arvo. Vanha payload ilman `_raw`-kenttia palauttaa
    kerroinpainotetun, jotta lause ei kaadu."""
    return rivi.get(f"{kentta}_raw", rivi.get(kentta))


def _kapteenilause(cap: dict) -> str:
    """Kapteenin rivi niin etta MOLEMMAT luvut loytyvat.

    Raakaluku on se jonka lukija nakee FPL:sta; kerroinpainotettu on se joka
    on kortilla ja summassa. Ilman siltaa lause julkaisi vain jalkimmaisen.
    """
    mult = int(cap.get("multiplier") or 1)
    raw_act = _raw(cap, "actual")
    raw_proj = _raw(cap, "projected")
    nimi = _nimi(cap)
    if mult >= 2:
        sana = "tripled" if mult >= 3 else "doubled"
        return (f"Your captain {nimi} scored {_pts(raw_act)}, {sana} to "
                f"{_pts(cap['actual'])} against a projected {_pts(raw_proj)}.")
    return (f"Your captain {nimi} scored {_pts(raw_act)} against a projected "
            f"{_pts(raw_proj)}.")


def review_lines(review: dict | None, rows: int | None = None,
                 provisional: bool = False,
                 chip: str | None = None) -> list[dict]:
    """Katsauslohkon lauseet. Palauttaa [{code, text}] jarjestyksessa.

    `code` on vakaa tunniste jota klientti voi kayttaa lokalisointiin ja
    testi ankkurina; `text` on englanninkielinen oletus.

    `rows` = montako riviä pinta oikeasti nayttaa (multiplier > 0).

    🔴 KAKSI PORTIN LOYDOSTA 7.9.2026, molemmat TASSA lauseessa:

    B3  Erotus laskettiin PYORISTAMATTOMASTA projektiosta samalla kun
        viereinen totaalirivi renderoi pyoristetyn. Brute force 2000
        projektiolla: 20 tapausta eroaa, esim. projected 69.25, actual 72 ->
        rivi sanoo "72 vs 69.3 (+2.7)" ja tama lause sen ALLA "You beat the
        model by 2.8". Erotus lasketaan nyt NAYTETYSTA luvusta, samoin kuin
        kortissa (`reviewTotals`).
    B4  "Your eleven" oli kovakoodattu. Bench boostilla sama summa kattaa
        15 pelaajaa. Rivimaara tulee nyt kutsujalta.
    """
    out: list[dict] = []
    if not review:
        return out

    proj, act = review.get("projected"), review.get("actual")
    if proj is not None and act is not None:
        # C10 (7.9): lause kulkee payloadissa itsenaisena ja renderoityy
        # missa tahansa `model_says` renderoidaan - myos ilman viereista
        # provisional-varausta. Arviota ("about where the model had you") ei
        # saa tehda kesken olevasta luvusta ilman merkintaa.
        _so_far = " so far" if provisional else ""
        # C5 (7.9): erotus lasketaan RAAASTA summasta samalla tavalla kuin
        # klientti sen laskee (`sum(rows).toFixed(1)`), ei jo kertaalleen
        # pyoristetusta `projected`ista. Kaksoispyoristys tuotti 1102
        # tapausta 200 000:sta joissa lause ja viereinen rivi nayttivat eri
        # luvun.
        raw = review.get("projected_raw")
        proj_shown = _shown_1dp(raw if raw is not None else proj)
        d = round(act - proj_shown, 1)
        # C6 (7.9): "who played" oli vaite jota payload ei mittaa. Rivi
        # putoaa kun JAADYTETTY xP puuttuu (esim. freezen jalkeen ostettu
        # pelaaja), ei siksi etta pelaaja ei pelannut - ja bench boostilla
        # FPL antaa multiplier 1 myos 0 minuutin penkkilaiselle. Sanotaan
        # se mita joukko oikeasti on.
        # 🔴 D4 (5. kierros): "Your eleven" oli fail-open chipin suhteen.
        # Bench boostilla jossa nelja pickkia putoaa `rows == 11` ja lause
        # vaittaa avaavaa yhdettatoista. Sama vika kuin U4 kortilla, joka
        # korjattiin antamalla `chip` - lause ei saanut sita lainkaan.
        #
        # 🔴 D2 (5. kierros): "picks with both numbers" oli SAMA SANAMUOTO
        # kuin paneelin kattavuuslauseella, mutta ERI JOUKKO:
        # `players_compared` = pickit joilla on molemmat luvut (14), `rows` =
        # rivit joilla multiplier > 0 (10). Kaksi lukua samalla sanamuodolla
        # samalla ruudulla. Nyt eri sanat eri mittareille.
        bboost = (chip or "").lower() == "bboost"
        kuka = ("Your eleven" if rows in (None, 11) and not bboost
                else f"Your {rows} counted picks")
        if abs(d) < 1.0:
            out.append({
                "code": "review.total.level",
                "text": (f"{kuka} scored {_pts(act)}{_so_far} against a projected "
                         f"{_pts(proj_shown)}. About where the model had you."),
            })
        elif d > 0:
            out.append({
                "code": "review.total.over",
                "text": (f"{kuka} scored {_pts(act)}{_so_far} against a projected "
                         f"{_pts(proj_shown)}. You beat the model by {_pts(d)}."),
            })
        else:
            # 🔴 Alisuoritus sanotaan yhta suoraan kuin ylisuoritus.
            out.append({
                "code": "review.total.under",
                "text": (f"{kuka} scored {_pts(act)}{_so_far} against a projected "
                         f"{_pts(proj_shown)}, so {_pts(abs(d))} short."),
            })

    cap = review.get("captain")
    if cap and cap.get("projected") is not None and cap.get("actual") is not None:
        out.append({
            "code": "review.captain",
            # 🔴 B1 (7. kierros): lause julkaisi KERROINPAINOTETUT luvut
            # ilman kerroinmerkintaa. Mitattu GW3: teksti sanoi "returned 27"
            # kun FPL:n oma live-syote sanoo Haalandista 9. Lukija ei loyda
            # 27:aa mistaan. Kortti sanoo kertoimen (TC-badge +
            # "captain tripled"), paneeli ei - ja tama on paneelin ainoa
            # tekstipinta. Nyt molemmat luvut ja silta niiden valilla.
            "text": _kapteenilause(cap),
        })

    # 🔴 MALLIN HUTI ENNEN MALLIN OSUMAA. Jarjestys on tarkoituksellinen:
    # paneeli joka avaa omalla onnistumisellaan on mainos.
    worst = review.get("worst_call")
    # Vartija SAMASTA kentasta kuin teksti (portin 9. kierros).
    if worst and _raw(worst, "diff") is not None and _raw(worst, "diff") < 0:
        out.append({
            "code": "review.worst",
            # B2: kertoimettomat luvut - vaite koskee MALLIN virhetta
            # pelaajasta, ei kayttajan kapteenivalintaa.
            "text": (f"The model's worst call was {_nimi(worst)}: "
                     f"{_pts(_raw(worst, 'projected'))} projected, "
                     f"{_pts(_raw(worst, 'actual'))} scored."),
        })
    best = review.get("best_call")
    if best and _raw(best, "diff") is not None and _raw(best, "diff") > 0:
        out.append({
            "code": "review.best",
            # "It" jatti epaselvaksi kuka - subjekti nimetaan.
            # "furthest under" jatti auki KUMPI oli alle: pelaaja vai malli.
            # Ja viereinen rivi on "worst call" (substantiivi), joten lukija
            # lukee ne parina - rinnakkaisuus rikkoutui.
            # 🔴 Portin 8. kierros: tama rivi luki yha kerroinpainotettuja
            # lukuja samalla kun `review.worst` luki `_raw`:ta - eli B2 oli
            # korjattu yhta rivia myohemmin. Kapteenin ollessa paras kutsu
            # kaksi perakkaista lausetta antoi saman pelaajan kahdella
            # lukuparilla, ja "23.8 projected" ei ole missaan FPL:ssa.
            "text": (f"The model's biggest underestimate was {_nimi(best)}: "
                     f"{_pts(_raw(best, 'projected'))} projected, "
                     f"{_pts(_raw(best, 'actual'))} scored."),
        })
    return out


def flag_lines(flags: dict | None, next_gw: int | None = None) -> list[dict]:
    """Lippulohkon lauseet. Maara ensin, sitten nimet."""
    out: list[dict] = []
    av = (flags or {}).get("availability") or []
    pr = (flags or {}).get("price") or []

    if av:
        # 🔴 Luku on lauseessa, ja se on listan pituus - ei arvio.
        kpl = "one flag" if len(av) == 1 else f"{len(av)} flags"
        gw = f" before GW{next_gw}" if next_gw else ""
        out.append({
            "code": "flags.availability.count",
            "text": f"You have {kpl} to clear{gw}.",
        })
        for f in av[:3]:
            c = f.get("chance_next")
            # FPL:n oma uutisteksti sellaisenaan, ei tulkintaa.
            if c is not None:
                out.append({
                    "code": "flags.availability.player",
                    "text": (f"{f.get('web_name')} is at {int(c)}% to play, "
                             f"per FPL."),
                })
            elif f.get("news"):
                out.append({
                    "code": "flags.availability.news",
                    "text": f"{f.get('web_name')}: {f['news']}",
                })

    for f in pr[:3]:
        p = f.get("progress_pct")
        if p is None:
            continue
        # 🔴 PUUTTUVA SUUNTA OHITETAAN, EI ARVATA. `else "fall"` julkaisi
        # nousevan pelaajan laskevana jos `direction` puuttui - ja
        # /api/fantasy/price-watch palauttaa risers-riveilla `direction: null`.
        # Talla hetkella gw_review asettaa suunnan itse listan avaimesta, joten
        # vika ei laukea, mutta oletusarvo oli vaara suunta.
        suunta = f.get("direction")
        if suunta not in ("rise", "fall"):
            continue
        eta = f.get("eta_days")
        # 🔴 "Voi nousta" eika "nousee". Hintamuutos on ennuste eika tapahtuma,
        # ja `progress_pct` on edistyma kynnysta kohti eika varmuus.
        # 🔴 AIKAVAITE ON EHDOLLINEN, JA EHTO SANOTAAN. "68% of the way to a
        # price rise tonight" lupaa ajankohdan tapahtumalle joka ei ole varma;
        # "tonight if it gets there" sanoo saman ilman lupausta. Ja aikasana
        # esiintyy VAIN kun `eta_days` tukee sita - mutaatiotesti joka liitti
        # "tonight":in kolmen paivan etaan meni muuten lapi.
        kun = ""
        if isinstance(eta, (int, float)):
            if eta < 1:
                kun = ", tonight if it gets there"
            elif eta <= 1:
                kun = ", within a day if it gets there"
        out.append({
            "code": f"flags.price.{suunta}",
            "text": (f"{f.get('web_name')} is {int(p)}% of the way to a price "
                     f"{suunta}{kun}."),
        })
    return out


def plan_lines(plans: list[dict] | None,
               baseline_xp: float | None = None) -> list[dict]:
    """Suunnitelmalohkon lauseet, HAVIAJA MUKAAN LUKIEN.

    🔴 Designin oma saanto (TASKS 26.7): *argumentoi haviavaa vastaan, ala
    piilota sita*. Kolmesta suunnitelmasta heikoin saa oman lauseensa jossa
    sanotaan MIKSI se havisi, mitattuna erona parhaaseen.
    """
    out: list[dict] = []
    kelpo = [p for p in (plans or []) if p.get("net_ev_vs_hold") is not None]
    if not kelpo:
        return out

    paras = max(kelpo, key=lambda p: p["net_ev_vs_hold"])
    ev = round(float(paras["net_ev_vs_hold"]), 1)
    hits = int(paras.get("hits_taken") or 0)

    if ev <= 0:
        # 🔴 Hold on tulos eika "ei suositusta".
        out.append({
            "code": "plans.hold",
            "text": ("No move clears the hold. The model has your current "
                     "squad ahead over this horizon."),
        })
        return out

    hitteja = ("" if not hits else
               f" after a hit of {hits * 4} points" if hits > 1
               else " after a 4 point hit")
    out.append({
        "code": "plans.best",
        "text": (f"The best plan is worth {_pts(ev)} points over holding"
                 f"{hitteja}."),
    })

    if len(kelpo) > 1:
        huonoin = min(kelpo, key=lambda p: p["net_ev_vs_hold"])
        ero = round(float(paras["net_ev_vs_hold"])
                    - float(huonoin["net_ev_vs_hold"]), 1)
        if ero >= 0.1:
            out.append({
                "code": "plans.worst",
                # 🔴 "of the three" oli KOVAKOODATTU vaikka vartija on
                # `len(kelpo) > 1`: kahdella suunnitelmalla teksti vaitti
                # kolmea. Tiedoston oma saanto kieltaa superlatiivit joita ei
                # ole mitattu. Loppuosa ("shown so you can argue with the
                # model rather than take the top line") oli lisaksi ainoa lause
                # koko setissa joka ei kanna lukua vaan selittaa paneelin oman
                # designperiaatteen kayttajalle.
                "text": f"The weakest plan is {_pts(ero)} points behind it.",
            })
    if baseline_xp is not None:
        out.append({
            "code": "plans.baseline",
            "text": (f"Holding projects {_pts(baseline_xp)} over the same "
                     f"horizon."),
        })
    return out
