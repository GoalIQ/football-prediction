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
    """Pistemuotoilu: kokonaisluku ilman desimaaleja, muuten yksi."""
    f = float(n)
    return str(int(f)) if abs(f - round(f)) < 0.05 else f"{f:.1f}"


def _nimi(rivi: dict | None) -> str | None:
    return (rivi or {}).get("web_name")


def review_lines(review: dict | None) -> list[dict]:
    """Katsauslohkon lauseet. Palauttaa [{code, text}] jarjestyksessa.

    `code` on vakaa tunniste jota klientti voi kayttaa lokalisointiin ja
    testi ankkurina; `text` on englanninkielinen oletus.
    """
    out: list[dict] = []
    if not review:
        return out

    proj, act = review.get("projected"), review.get("actual")
    if proj is not None and act is not None:
        d = round(act - proj, 1)
        if abs(d) < 1.0:
            out.append({
                "code": "review.total.level",
                "text": (f"Your eleven scored {_pts(act)} against a projected "
                         f"{_pts(proj)}. About where the model had you."),
            })
        elif d > 0:
            out.append({
                "code": "review.total.over",
                "text": (f"Your eleven scored {_pts(act)} against a projected "
                         f"{_pts(proj)}. You beat the model by {_pts(d)}."),
            })
        else:
            # 🔴 Alisuoritus sanotaan yhta suoraan kuin ylisuoritus.
            out.append({
                "code": "review.total.under",
                "text": (f"Your eleven scored {_pts(act)} against a projected "
                         f"{_pts(proj)}, so {_pts(abs(d))} short."),
            })

    cap = review.get("captain")
    if cap and cap.get("projected") is not None and cap.get("actual") is not None:
        out.append({
            "code": "review.captain",
            "text": (f"Your captain {_nimi(cap)} returned "
                     f"{_pts(cap['actual'])} against a projected "
                     f"{_pts(cap['projected'])}."),
        })

    # 🔴 MALLIN HUTI ENNEN MALLIN OSUMAA. Jarjestys on tarkoituksellinen:
    # paneeli joka avaa omalla onnistumisellaan on mainos.
    worst = review.get("worst_call")
    if worst and worst.get("diff") is not None and worst["diff"] < 0:
        out.append({
            "code": "review.worst",
            "text": (f"The model's worst call was {_nimi(worst)}: "
                     f"{_pts(worst['projected'])} projected, "
                     f"{_pts(worst['actual'])} scored."),
        })
    best = review.get("best_call")
    if best and best.get("diff") is not None and best["diff"] > 0:
        out.append({
            "code": "review.best",
            # "It" jatti epaselvaksi kuka - subjekti nimetaan.
            # "furthest under" jatti auki KUMPI oli alle: pelaaja vai malli.
            # Ja viereinen rivi on "worst call" (substantiivi), joten lukija
            # lukee ne parina - rinnakkaisuus rikkoutui.
            "text": (f"The model's biggest underestimate was {_nimi(best)}: "
                     f"{_pts(best['projected'])} projected, "
                     f"{_pts(best['actual'])} scored."),
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
               f" after a {hits * 4} point hit" if hits > 1
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
