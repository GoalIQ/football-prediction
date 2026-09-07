"""POST-GW-KATSAUS: mita malli sanoi, mita tapahtui, mita seuraavaksi.

Villen paatos 26.7: *"team manager + fm silmukka / peli tehdaan ja mielestani
mita nopeammin sen parempi etta erottaudutaan"*. Tama on vaiheen 1 ydin.

Teesi: FPL:n oma sovellus on TRANSAKTIOTYOKALU - tee siirto, aseta kapteeni,
sulje. Kukaan ei omista hetkea *"peliviikko meni, mita nyt"*. Se on
kalenteriongelma eika taito-ongelma.

🔴 LUKEE HISTORIALLISIA LAHTEITA, EI `rate_team`ia. Ensimmainen versio kokosi
katsauksen `rate_team`in ulostulosta ja se EI TOIMINUT: projektiotiedosto
pudottaa pelatun kierroksen (builderi ottaa vain `not finished` -fixturet),
joten `clamp_gw_to_projections` siirsi pyynnon GW1 -> GW2 ja katsauksella ei
ollut mitaan vertailtavaa. Katsaus on HISTORIALLINEN nakyma: sen lahteet ovat
deadline-freeze ja toteutuneet pisteet, samat kuin my-team-ledgerilla.

🔴 VERTAILUKOHTA ON DEADLINE-FREEZE. Elava xP liikkuu kohti toteumaa
kierroksen aikana, joten elavaa vastaan vertaaminen saisi mallin nayttamaan
tarkemmalta kuin se on (kirjattu vika, korjattu 22.8).

🔴 MALLIN HUTIT OVAT OSA TUOTETTA. `worst_call` on payloadissa yhta nakyvasti
kuin `best_call`: rehellisyys on kayttoliittyma, ei alaviite. Mitattu
ensimmaisella ajolla etta mallin OMA joukkue yliennustettiin 14,6 pisteella -
jos se ei nay tuotteessa, tuote valehtelee.

🔗 SAMA VAITE TOISESTA LAHTEESTA: `fpl_rate_team.last_finished_block` laskee
saman kierroksen tuloksen pitch-nakymaa ja jakokorttia varten. Muoto eroaa
tarkoituksella (siella rivit ovat KERTOIMETTOMIA, jotta tuomiomerkki lasketaan
pelaajan omasta suorituksesta eika kapteeninauhasta), mutta SUMMAT eivat saa
erota: `tests/test_luck_review_agreement.py` kaatuu jos ne erkanevat.
"""
from __future__ import annotations

from src.models import fpl_actuals
from src.models.fpl_model_says import _shown_1dp

NOTE_NOT_PLAYED = (
    "The review opens once a gameweek has been played with a projection "
    "frozen before its deadline."
)
CODE_NOT_PLAYED = "gw_review.note.not_played"

# Alle taman prosentin pelaaja on lippu jonka lukija joutuu ratkaisemaan.
AVAILABILITY_FLAG_PCT = 100


def _rivi(pick: dict, frozen: dict[int, float], points: dict[int, int],
          info: dict) -> dict | None:
    """Yhden pelaajan katsausrivi, tai None jos vertailtavaa ei ole.

    🔴 Kerroin mukaan MOLEMMILLE puolille: penkki 0, kapteeni 2, TC 3. Sama
    kohtelu kuin FPL:n omissa kierrospisteissa.
    """
    pid = pick.get("element")
    xp = frozen.get(pid)
    pts = points.get(pid)
    if xp is None or pts is None:
        # 🔴 Toinen puoli yksin ei ole vertailu. None EI nollaudu.
        return None
    mult = int(pick.get("multiplier", 0))
    proj = round(float(xp) * mult, 2)
    act = int(pts) * mult
    e = info.get(pid) or {}
    return {
        "id": pid,
        "web_name": e.get("web_name"),
        "team_short": e.get("team_short"),
        "pos": e.get("pos"),
        "projected": proj,
        "actual": act,
        "diff": round(act - proj, 2),
        # 🔴 B2 (portin 7. kierros): KERTOIMETTOMAT LUVUT ERIKSEEN.
        # `diff` on kerroinpainotettu, ja `best_call`/`worst_call` valittiin
        # siita - eli KAPTEENINAUHA paatti mika oli "mallin pahin kutsu".
        # Repon oma saanto sanoo painvastoin (`fpl_rate_team.
        # last_finished_block`: rivit ovat kertoimettomia "jotta tuomiomerkki
        # lasketaan pelaajan omasta suorituksesta eika kapteeninauhasta"),
        # joten kaksi pintaa vastasi samaan kysymykseen eri saannolla.
        # Mitattu GW3: Haalandin raakaero +1.08, kolminkertaistettuna +3.24.
        "projected_raw": round(float(xp), 2),
        "actual_raw": int(pts),
        "diff_raw": round(int(pts) - float(xp), 2),
        "multiplier": mult,
        "in_xi": mult > 0,
        "is_captain": bool(pick.get("is_captain")),
    }


def _ennen_deadlinea(fmeta: dict) -> bool:
    """Onko freeze TODISTETTAVASTI ennen deadlinea (B7, 7.9).

    Puuttuva tai rikkinainen aikaleima -> False, eli vaitetta ei tehda.
    Fail-closed samoin kuin `fpl_gw_finality`.
    """
    import datetime as _dt
    try:
        f = _dt.datetime.fromisoformat(str(fmeta.get("frozen_at")).replace("Z", "+00:00"))
        d = _dt.datetime.fromisoformat(str(fmeta.get("deadline")).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return f < d


def build_review(gw: int | None, picks: dict | None,
                 frozen: dict[int, float] | None,
                 points: dict[int, int] | None,
                 info: dict | None = None,
                 price_watch: dict | None = None,
                 provisional_gws: list[int] | None = None) -> dict:
    """Freeze + toteumat + valinnat -> katsauspayload. Ei verkkokutsuja."""
    info = info or {}
    if not gw or not picks or not frozen or not points:
        return {
            "meta": {"available": False, "reviewed_gw": gw,
                     "note": NOTE_NOT_PLAYED, "note_code": CODE_NOT_PLAYED},
            "review": None,
            "flags": {"availability": [], "price": []},
        }

    rivit = [_rivi(p, frozen, points, info) for p in (picks.get("picks") or [])]
    vertailtavat = [r for r in rivit if r is not None]
    if not vertailtavat:
        return {
            "meta": {"available": False, "reviewed_gw": gw,
                     "note": NOTE_NOT_PLAYED, "note_code": CODE_NOT_PLAYED},
            "review": None,
            "flags": {"availability": [], "price": []},
        }

    xi = [r for r in vertailtavat if r["in_xi"]]
    pohja = xi or vertailtavat
    # B2: valinta RAAKAEROLLA - vaite koskee mallin virhetta pelaajasta, ei
    # kayttajan kapteenivalintaa.
    paras = max(pohja, key=lambda r: r["diff_raw"])
    huonoin = min(pohja, key=lambda r: r["diff_raw"])
    # 🔴 E3 (6. kierros): KAPTEENIRIVI LUETTIIN LIPUSTA. FPL jattaa
    # `is_captain: true` PELAAMATTOMALLE ja siirtaa kertoimen
    # varakapteenille, jolloin `_rivi` laskee proj = xp * 0 = 0.0 ja act = 0
    # -> `model_says` julkaisi "Your captain X returned 0 against a
    # projected 0." Sama korjaus kuin kortilla (U5): luetaan silta rivilta
    # jolla kerroin OIKEASTI on. Ilman kerrointa lausetta ei ole.
    kapteeni = max((r for r in vertailtavat if r["multiplier"] >= 2),
                   key=lambda r: r["multiplier"], default=None)

    # 🔴 C5 (portin 4. kierros): KAKSOISPYORISTYS. `projected` pyoristettiin
    # kahteen desimaaliin, ja `fpl_model_says` muotoili siita yhteen - samalla
    # kun klientti laskee saman summan RAAKANA ja tekee `toFixed(1)`. Brute
    # force 200 000 summalla: 1102 tapausta joissa lause ja viereinen rivi
    # nayttavat eri luvun (raaka 54,4499... -> lause "54.5", rivi "54.4").
    # Raaka summa kulkee nyt erikseen, ja lause laskee siita.
    # 🔴 E1 (6. kierros): summa SADASOSINA, jotta jarjestys ei voi muuttaa
    # naytettya lukua. Liukuluvun yhteenlasku ei ole assosiatiivinen, ja
    # kolme pintaa summasi samat rivit eri jarjestyksessa - mitattu
    # tuotannon GW3:sta 7.9: 71.15 vs 71.14999999999999, eli "71.2" ja
    # "71.1" samassa nakymassa. Rivien `projected` on 2 desimaalia.
    # 🔴 Portin 10. kierros: summa NAYTETYISTA riveista. Sadasosasumma teki
    # summasta jarjestysriippumattoman (E1) mutta jatti xP-sarakkeen ja
    # alaotsikon eri luvuiksi: mitattu drift 0,6 ja **etumerkin kaantyminen**
    # (`62 pts vs 61.9 xP (+0.1)` kun sarakkeet antavat -0,2). Rivit
    # renderoidaan yhdella desimaalilla, joten summataan se mita nakyy.
    # Sama saanto kuin klientilla: `_shown_1dp` on `toFixed(1)`:n vastine
    # (ROUND_HALF_UP doublen tarkasta arvosta), verifioitu 204 000 arvolla.
    # Pythonin `round(x, 1)` on half-even ja erkanisi tasatilanteessa.
    proj_xi_raw = (round(sum(_shown_1dp(r["projected"]) for r in xi), 1)
                   if xi else None)
    proj_xi = round(proj_xi_raw, 2) if proj_xi_raw is not None else None
    act_xi = sum(r["actual"] for r in xi) if xi else None

    # --- liput seuraavaan kierrokseen (nykytila, ei kierroksen aikainen)
    omat = [p.get("element") for p in (picks.get("picks") or [])]
    saatavuus = []
    for pid in omat:
        e = info.get(pid) or {}
        c = e.get("chance_next")
        news = (e.get("news") or "").strip()
        if (c is not None and c < AVAILABILITY_FLAG_PCT) or news:
            saatavuus.append({
                "id": pid, "web_name": e.get("web_name"),
                "team_short": e.get("team_short"),
                "chance_next": c,
                # 🔴 FPL:n oma uutisteksti sellaisenaan. Emme tulkitse sita
                # omaksi arvioksi - se olisi vaite jota emme voi puolustaa.
                "news": news or None,
            })

    omat_set = set(omat)
    hinta = []
    for suunta in ("risers", "fallers"):
        for r in ((price_watch or {}).get(suunta) or []):
            if r.get("id") in omat_set:
                hinta.append({
                    "id": r.get("id"), "web_name": r.get("web_name"),
                    "direction": "rise" if suunta == "risers" else "fall",
                    "progress_pct": r.get("progress_pct"),
                    "eta_days": r.get("eta_days"),
                    "confidence": r.get("confidence"),
                })

    _fmeta = fpl_actuals.frozen_meta(gw) or {}
    _hist = picks.get("entry_history") or {}

    return {
        "meta": {
            "available": True,
            "reviewed_gw": gw,
            "provisional": gw in set(provisional_gws or []),
            "players_compared": len(vertailtavat),
            # 🔴 7.9 (portti U3): kattavuus tarvitsee NIMITTAJAN. Kortti sanoi
            # "12 of 15 compared" jossa 15 oli kovakoodattu, ja rivit olivat
            # eri joukkoa (XI). Nyt molemmat luvut tulevat samasta paikasta.
            "total_picks": len(picks.get("picks") or []),
            # U4/U5: chip muuttaa sen MITA rivit ovat. Bench boostilla
            # jokaisella 15:sta on multiplier > 0, eli "starting XI" olisi
            # vaara otsikko. Kortti ei saa paatella tata itse.
            "chip": picks.get("active_chip"),
            # 🔴 B4 (7. kierros): autosubin jalkeen `multiplier > 0` -joukko
            # sisaltaa penkilta nousseen, jolloin "starting XI" on vaara.
            # Kentta on FPL:n omassa picks-vastauksessa, eli vaite oli
            # fail-open yhden rivin paassa olevasta mittauksesta.
            "auto_subs": len(picks.get("automatic_subs") or []),
            # A3: freeze-vaite on JOHDETTAVA, ei rakenteellinen. Ilman naita
            # kortti sanoi "frozen before the deadline" myos silloin kun
            # freeze olisi myohassa - vaite jota se ei voi mitata.
            "frozen_at": _fmeta.get("frozen_at"),
            "deadline": _fmeta.get("deadline"),
            # 🔴 B1 (7.9, portti): FPL:N OMA KIERROSPISTEMAARA payloadiin.
            # Kortti ja paneeli nayttivat MEIDAN live-XI:n summan (72) ja
            # attribuoivat sen FPL:lle, samalla kun lukijan oma FPL-sovellus
            # sanoi 58. Mitattu 7.9: GW3:n 10 ottelua olivat
            # `finished_provisional` muttei `finished`, ja live-syotteessa oli
            # 15 kerroinpainotettua bonuspistetta joita `entry_history` ei
            # ollut viela kirjoittanut. Luku ei ole vaara, mutta se on ERI
            # LUKU, ja se on sanottava nimeltaan eika pehmennettava lauseella.
            "fpl_points": (_hist.get("points")
                           if isinstance(_hist.get("points"), int) else None),
            # 🔴 Portin 10. kierros korjasi 9. kierroksen VAARAN PREMISSIN.
            # `entry_history.points` on **BRUTTO**, ei netto. Verifioitu
            # FPL:n omasta API:sta 7.9 (entry 12345 GW3: points 70,
            # event_transfers_cost 8, ja kausisumma kasvoi 87 -> 149 eli
            # 62 = 70 - 8). Kirjoitin 9. kierroksella painvastoin viiteen
            # paikkaan kolmella kielella.
            #
            # Lukijan oma FPL-nakyma nayttaa NETON, joten se on se luku jonka
            # saa nimeta "FPL:n omaksi totaaliksi". Molemmat kentat
            # payloadiin, jotta pinta ei laske sita itse.
            "transfer_cost": (_hist.get("event_transfers_cost")
                              if isinstance(_hist.get("event_transfers_cost"), int)
                              else None),
            "fpl_points_net": (
                _hist["points"] - (_hist.get("event_transfers_cost") or 0)
                if isinstance(_hist.get("points"), int) else None),
            # B7 (7.9): `basis` oli EHDOTON lause ("frozen before the
            # deadline") vaikka mikaan ei mitannut sita. Sama vaite kuin
            # kortin `freezeNote()`, joten sama saanto: vaite tehdaan vain
            # kun aikaleimat todistavat sen.
            "basis": (
                "projection frozen before the deadline, never the live one"
                if _ennen_deadlinea(_fmeta)
                else "projection frozen for this gameweek, never the live one"),
            "note": None,
            "note_code": None,
        },
        "review": {
            "projected": proj_xi,
            # C5: pyoristamaton summa lauseen laskentaa varten. Klientti
            # laskee saman rivien summasta, joten lukija on sama.
            "projected_raw": proj_xi_raw,
            "actual": act_xi,
            "diff": (round(act_xi - proj_xi, 2)
                     if proj_xi is not None and act_xi is not None else None),
            # 🔴 Molemmat yhta nakyvasti. Huti ei ole alaviite.
            "best_call": paras,
            "worst_call": huonoin,
            "captain": kapteeni,
            # Portin 8. kierros: sama jarjestyssaanto kuin kortilla ja
            # best/worst-valinnalla. Kerroinpainotettu jarjestys teki
            # payloadista KOLMANNEN saannon samasta kysymyksesta.
            "players": sorted(vertailtavat, key=lambda r: -r["diff_raw"]),
        },
        "flags": {
            "availability": sorted(
                saatavuus, key=lambda r: (r["chance_next"]
                                          if r["chance_next"] is not None
                                          else 101)),
            "price": sorted(hinta, key=lambda r: -(r["progress_pct"] or 0)),
        },
    }
