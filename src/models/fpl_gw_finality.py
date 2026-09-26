# -*- coding: utf-8 -*-
"""YKSI LUKIJA sille onko kierroksen pistemaara LOPULLINEN.

MIKSI (7.9.2026, julkaisutarkistajan loydos A1). Kaksi pintaa (`gw-review`,
`my-team-ledger`) lukivat `provisional`-lipun johdetusta artefaktista
`data/model_squad_gw_scores.json` -> `meta.provisional_gws`. Se on
POSITIIVINEN LISTA, ja siksi sen puuttuminen kaantyi vaitteeksi:

    prov = meta.provisional_gws or []          # GW3 ei ole listalla
    "provisional": gw in set(prov)             # -> False = "lopullinen"

Mitattu 7.9: artefakti oli generoitu 1.9 ja kattoi GW1-2. GW3:sta FPL sanoi
`finished=False`, `data_checked=False` — kierros oli KESKEN — ja payload
vaitti silti `provisional=false`. Kierros jota grader ei ole viela
kirjoittanut ei voi olla lopullinen; puuttuva tieto muuttui julkiseksi
vaitteeksi lopullisuudesta.

INVARIANTTI: LOPULLISUUS ON TODISTETTAVA, EI OLETETTAVA. Tama lukija on
fail-closed: kierros on provisionaalinen aina paitsi jos FPL:n oma
`events`-rivi sanoo `finished AND data_checked`. Tuntematon kierros,
puuttuva bootstrap ja rikkinainen artefakti tuottavat kaikki
"provisionaalinen", koska jokainen niista on tila jossa emme tieda.

`data_checked` on mukana `finished`in lisaksi siksi etta bonukset ja BPS
ratkeavat vasta sen kanssa: `finished=True, data_checked=False` on ikkuna
jossa pisteet viela liikkuvat.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Iterable


def final_gws(events: Iterable[dict[str, Any]] | None) -> set[int]:
    """Kierrokset joiden pisteet FPL sanoo lopullisiksi.

    Vain `finished AND data_checked`. Tyhja tai puuttuva syote -> tyhja
    joukko, jolloin kaikki on provisionaalista.
    """
    out: set[int] = set()
    for e in events or []:
        if not isinstance(e, dict):
            continue
        gw = e.get("id")
        if not isinstance(gw, int) or isinstance(gw, bool):
            continue
        if e.get("finished") and e.get("data_checked"):
            out.add(gw)
    return out


def provisional_gws(events: Iterable[dict[str, Any]] | None,
                    gws: Iterable[Any],
                    artifact_gws: Iterable[Any] | None = None) -> list[int]:
    """Ne `gws`:n kierrokset jotka on merkittava provisionaalisiksi.

    `artifact_gws` on vanha johdettu lista. Se otetaan mukaan UNIONINA eika
    korvaajana: se voi lisata epavarmuutta (grader tietaa jotain mita
    bootstrap ei kerro) mutta se ei voi koskaan POISTAA sita. Juuri se
    suunta oli vika A1:ssa.
    """
    lopulliset = final_gws(events)
    extra: set[int] = set()
    for g in artifact_gws or []:
        try:
            extra.add(int(g))
        except (TypeError, ValueError):
            continue
    out: set[int] = set()
    for g in gws:
        try:
            gw = int(g)
        except (TypeError, ValueError):
            continue
        if gw not in lopulliset or gw in extra:
            out.add(gw)
    return sorted(out)


def is_provisional(events: Iterable[dict[str, Any]] | None,
                   gw: Any,
                   artifact_gws: Iterable[Any] | None = None) -> bool:
    """Yhden kierroksen muoto. Tuntematon -> True."""
    try:
        g = int(gw)
    except (TypeError, ValueError):
        return True
    return bool(provisional_gws(events, [g], artifact_gws))


# 26.9.2026 (MP-14): siirretty scripts/grade_model_squad.py:_gw_status -funktiosta
# sellaisenaan, jotta my-team-ledger lukee kierroksen tilan SAMASTA lukijasta
# kuin gradaaja ja model-race (saanto 6a). Gradaajan nimi on alias tahan.
def gw_fixture_status(boot: dict, fixtures: list[dict]) -> dict[int, dict]:
    """Per kierros: onko se gradattavissa ja onko luku viela provisionaalinen.

    `finished_provisional` per ottelu on tarkempi kuin `event.finished`, joka
    kaantyy vasta kun FPL on kayn ut bonukset lapi. Kierros on gradattavissa
    kun jokainen sen ottelu on pelattu.
    """
    by_gw: dict[int, list[dict]] = {}
    for f in fixtures:
        gw = f.get("event")
        if gw is not None:
            by_gw.setdefault(int(gw), []).append(f)

    out: dict[int, dict] = {}
    for ev in boot.get("events") or []:
        gw = int(ev["id"])
        fx = by_gw.get(gw) or []
        if not fx:
            continue
        all_played = all(f.get("finished_provisional") for f in fx)
        # 🔴 PORTIN 22. KIERROS (C): SIIRRETTY OTTELU EI OLE "KESKEN".
        # Jos ottelu siirretaan mutta jaa samaan kierrokseen myohemmalla
        # kickoffilla - tai ilman kickoffia lainkaan - `all_played` on False
        # VIIKKOJA, ja pinta sanoisi "GW N: still being played" kierroksesta
        # jonka muut ottelut on pelattu. Se on sama vaarin nimetty mekanismi
        # kuin 21. kierroksen `event.finished`, vain toisinpain.
        #
        # Emme keksi uutta julkista lausetta: kun kierros nayttaa siirretylta,
        # `all_fixtures_played` on None, `row_state` palauttaa `unknown`, ja
        # teksti sanoo vain ettei kierrosta ole vahvistettu. Se on tosi
        # molemmissa tapauksissa.
        # 🔴 PORTIN 23. KIERROS (B4): ensimmainen versio tunnisti vain
        # MENNEEN kickoffin. FPL antaa uudelleenaikataulutetulle ottelulle
        # TULEVAN kickoffin, jolloin `now - t` on negatiivinen, `siirretty`
        # jai Falseksi, ja pinta sanoi paivakausia *"GW N: still being
        # played"* kierroksesta jonka muut ottelut oli pelattu. Commit-viesti
        # lupasi kattavansa juuri sen tapauksen; koodi ei kattanut.
        #
        # Erotin: kierros on KESKEN vain jos pelaamaton ottelu alkaa pian
        # (tai on juuri alkanut). Jos yksikin pelaamaton ottelu on selvasti
        # muiden ULKOPUOLELLA - kaukana tulevaisuudessa, kaukana
        # menneisyydessa tai ilman kickoffia - kierros on siirretty, emmeka
        # sano siita mitaan.
        nyt = _dt.datetime.now(_dt.timezone.utc)
        ALKU = 3 * 3600          # olisi pitanyt olla ohi
        TULEVA = 3 * 24 * 3600   # alkaa vasta yli 3 vrk paasta
        siirretty = False
        for f in fx:
            if f.get("finished_provisional"):
                continue
            ko = f.get("kickoff_time")
            if not ko:
                siirretty = True   # ei kickoffia = ei aikataulua
                break
            try:
                t = _dt.datetime.fromisoformat(str(ko).replace("Z", "+00:00"))
            except ValueError:
                continue
            ero = (nyt - t).total_seconds()
            if ero > ALKU or ero < -TULEVA:
                siirretty = True
                break
        out[gw] = {
            "gradable": all_played,
            # data_checked = FPL on vahvistanut bonukset ja dubious goalsit
            "provisional": not bool(ev.get("data_checked")),
            # 🔴 PORTIN 21. KIERROS: `event.finished` EI KELPAA TAHAN.
            # 20. kierroksella haaroitin pinnan tekstin siita - ja se on
            # tasan se kentta jonka TAMAN funktion oma docstring sanoo
            # kaantyvan vasta bonusten jalkeen. Mitattu 7.9: GW3:n
            # `events[3].finished` oli False samalla kun `fixtures/?event=3`
            # sanoi 10/10 `finished`. Teksti olisi kertonut lukijalle etta
            # otteluita on kesken, kun ne oli kaikki pelattu.
            #
            # Oikea kentta on sama `all_played` jolla gradattavuus jo
            # ratkaistaan: kaikki ottelut pelattu.
            "all_fixtures_played": None if siirretty else all_played,
            "fpl_average": ev.get("average_entry_score"),
            "n_fixtures": len(fx),
        }
    return out
