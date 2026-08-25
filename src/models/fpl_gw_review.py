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
"""
from __future__ import annotations

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
        "multiplier": mult,
        "in_xi": mult > 0,
        "is_captain": bool(pick.get("is_captain")),
    }


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
    paras = max(pohja, key=lambda r: r["diff"])
    huonoin = min(pohja, key=lambda r: r["diff"])
    kapteeni = next((r for r in vertailtavat if r["is_captain"]), None)

    proj_xi = round(sum(r["projected"] for r in xi), 2) if xi else None
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

    return {
        "meta": {
            "available": True,
            "reviewed_gw": gw,
            "provisional": gw in set(provisional_gws or []),
            "players_compared": len(vertailtavat),
            "basis": ("projection frozen before the deadline, never the live "
                      "one"),
            "note": None,
            "note_code": None,
        },
        "review": {
            "projected": proj_xi,
            "actual": act_xi,
            "diff": (round(act_xi - proj_xi, 2)
                     if proj_xi is not None and act_xi is not None else None),
            # 🔴 Molemmat yhta nakyvasti. Huti ei ole alaviite.
            "best_call": paras,
            "worst_call": huonoin,
            "captain": kapteeni,
            "players": sorted(vertailtavat, key=lambda r: -r["diff"]),
        },
        "flags": {
            "availability": sorted(
                saatavuus, key=lambda r: (r["chance_next"]
                                          if r["chance_next"] is not None
                                          else 101)),
            "price": sorted(hinta, key=lambda r: -(r["progress_pct"] or 0)),
        },
    }
