"""FPL-deadlinet iCalendar-muodossa: paluusyy jota meidan ei tarvitse operoida.

MITATTU 20.9.2026: web-kavijoista **1 520 / 1 540 kavi tasan yhtena paivana**
(30 vrk). Sivulla ei ole mitaan syyta palata, eika sita voi korjata
sisallolla joka vaatii etta lukija muistaa tulla takaisin.

FPL-kayttajan luonnollinen paluuhetki on deadline. Tama tiedosto laittaa sen
lukijan OMAAN kalenteriin: ei sahkopostilistaa, ei lahetyksia, ei
henkilotietoja, ei ylläpidettavaa jonoa - ja muistutus laukeaa vaikka emme
tekisi mitaan. Tapahtumassa on URL takaisin ilmaissivulle.

KAKSI ASIAA JOTKA TEKEVAT VAARASTA AJASTA MAHDOTTOMAN:

1. **Aika on aina UTC (`Z`).** FPL julkaisee deadlinet UTC:na ja kalenteri
   muuntaa sen lukijan omaan vyohykkeeseen. Jos kirjoittaisimme paikallista
   aikaa ilman vyohyketta, muistutus olisi vaarassa kohdassa puolella
   maailmaa - ja kalenterimerkinta on pysyva kuten jakokortti: sita ei voi
   korjata jalkikateen.

2. **Lahde on sama artefakti jonka sivu nayttaa.** `meta.deadlines` tulee
   FPL:n bootstrapista phase0-builderin kautta. Jos .ics rakennettaisiin eri
   lahteesta, sivu ja kalenteri voisivat sanoa eri aikaa (muisti:
   `jakopinta-lukee-eri-tiedostoa-kuin-sivu`).
"""
from __future__ import annotations

import datetime as dt

PRODID = "-//GoalIQ//FPL deadlines//EN"
#: Muistutus taman verran ennen deadlinea. Kaksi tuntia on sama ikkuna jonka
#: mobiilin muistutusteksti lupaa ("24 h and 2 h before"), eli pinnat eivat
#: lupaa eri asiaa.
ALARM_MINUTES = 120

#: DTSTAMP on KIINTEA, ei rakennushetki.
#:
#: 🔴 MITATTU 21.9.2026: `fpl-data-refresh` (ajo 35558945289) heitti koko
#: kolmen tunnin datarakennuksen pois, koska push-askeleen rebase kaatui
#: viidesti samaan konfliktiin tiedostossa `fpl/deadlines.ics`. Syy:
#: `DTSTAMP:{now}` muutti kaikki 33 tapahtumaa JOKAISESSA rakennuksessa, ja
#: sivun rakentavat rinnakkain ainakin fpl-data-refresh, fpl-page-refresh ja
#: accuracy-log. Kaksi rakennusta samasta datasta tuotti kaksi eri tiedostoa,
#: eli konflikti oli taattu aina kun ne osuivat paallekkain.
#:
#: Nyt sama syote tuottaa saman tavujonon riippumatta siita milloin se
#: rakennetaan (portti: test_sama_syote_tuottaa_saman_tiedoston). `now`
#: vaikuttaa vain siihen mitka deadlinet ovat jo menneet. RFC 5545 vaatii
#: DTSTAMPin mutta ei sita etta se on rakennushetki; kalenteriohjelmat
#: tunnistavat tapahtuman UID:sta. Arvo = FPL 26/27 -kauden aikataulun
#: julkaisun jalkeinen hetki, eli menneisyydessa kaikkiin tapahtumiin nahden.
DTSTAMP_KIINTEA = "20260801T000000Z"


def _stamp(d: dt.datetime) -> str:
    return d.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,")


def ics(deadlines, now: dt.datetime, url: str = "https://goaliq.app/fpl") -> str:
    """iCalendar-teksti annetuista deadlineista.

    `deadlines` = [{"gw": int, "utc": "2026-10-10T10:00:00+00:00"}, ...].
    Menneet ja rikkinaiset rivit jataan pois: kalenteriin ei kirjoiteta
    tapahtumaa jonka aikaa ei tiedeta.
    """
    rivit = [
        "BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        "X-WR-CALNAME:FPL deadlines (GoalIQ)",
    ]
    n = 0
    for d in deadlines or []:
        gw = (d or {}).get("gw")
        raaka = (d or {}).get("utc")
        if not isinstance(gw, int) or not isinstance(raaka, str):
            continue
        try:
            hetki = dt.datetime.fromisoformat(raaka)
        except ValueError:
            continue
        if hetki.tzinfo is None:
            hetki = hetki.replace(tzinfo=dt.timezone.utc)
        if hetki <= now:
            continue
        n += 1
        rivit += [
            "BEGIN:VEVENT",
            f"UID:fpl-gw{gw}-deadline@goaliq.app",
            f"DTSTAMP:{DTSTAMP_KIINTEA}",
            f"DTSTART:{_stamp(hetki)}",
            f"DTEND:{_stamp(hetki)}",
            f"SUMMARY:{_esc(f'FPL GW{gw} deadline')}",
            f"DESCRIPTION:{_esc('Clean sheet chances and expected points are free at ' + url)}",
            f"URL:{url}",
            "BEGIN:VALARM", "ACTION:DISPLAY",
            f"TRIGGER:-PT{ALARM_MINUTES}M",
            f"DESCRIPTION:{_esc(f'FPL GW{gw} deadline in 2 hours')}",
            "END:VALARM",
            "END:VEVENT",
        ]
    rivit.append("END:VCALENDAR")
    # CRLF on iCalendarin (RFC 5545) rivinvaihto, ei tyylivalinta.
    return "\r\n".join(rivit) + "\r\n" if n else ""
