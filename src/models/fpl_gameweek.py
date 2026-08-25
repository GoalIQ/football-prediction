"""Kierrosvalinta: mita kierrosta mikakin pinta nayttaa (25.8.2026).

🔴 MIKSI TAMA MODUULI ON OLEMASSA
Sama vikaluokka on loytynyt NELJASTI kolmessa viikossa:

    22.8  siirtosuunnittelu ehdotti siirtoa kierrokselle joka oli jo lukittu
    24.8  chip-EV tarjosi chip-ikkunaa kierrokselle jonka deadline oli mennyt
    25.8  jakokortin oletus osui jo pelattuun kierrokseen
    25.8  /fpl-sivu naytti nollapeliprojektiot jo pelatuille otteluille
          (Arsenal 53 % kotona Coventrya vastaan, kun GW2:n luku on 38 %
          vieraissa Aston Villaa vastaan)

Juurisyy on joka kerta sama: `meta.next_gameweek` johdetaan FPL:n
`is_current`/`is_next`-lipuista, ja FPL kaantaa ne TUNTIEN viiveella. Mitattu
25.8 klo 09:05 UTC: GW1 pelattiin 21.-24.8, sen kaikki 10 ottelua olivat
`finished`, mutta `event.finished` oli False, `data_checked` False ja
`is_current` YHA True. `deadline_gameweek` oli koko ajan oikein (2).

🔴 JA SYVEMPI SYY: YKSI KENTTA, KAKSI KYSYMYSTA
`next_gameweek` on vastannut molempiin, ja siksi kutsupaikat ovat valinneet
vaarin huomaamattaan:

    "mita kierrosta joukkueeni juuri nyt keraa?"   -> current_gameweek()
    "mihin kierrokseen voin viela vaikuttaa?"      -> actionable_gameweek()

Kesken kierroksen nama EROAVAT, ja se on tasan se hetki jolloin virhe syntyy.
Taman moduulin tarkoitus on pakottaa kutsupaikka SANOMAAN kumpaa se tarkoittaa
sen sijaan etta se lukee kenttaa jonka merkitys vaihtuu kellonajan mukaan.
"""
from __future__ import annotations

import datetime as _dt


def current_gameweek(meta: dict) -> int | None:
    """Kierros jota joukkue juuri nyt keraa.

    Tama on oikea vastaus PISTEITA nayttaville pinnoille: "Team xP, GW1" kesken
    kierroksen on oikein, koska se on mita joukkue on juuri nyt keraamassa
    (Villen 22.8 linjaus rate_teamin target_gw:sta). Ala kayta tata
    ennustepinnoilla.
    """
    gw = (meta or {}).get("next_gameweek")
    return gw if isinstance(gw, int) else None


def actionable_gameweek(meta: dict) -> int | None:
    """Ensimmainen kierros johon lukija voi VIELA vaikuttaa.

    Tama on oikea vastaus kaikille ENNUSTE- ja SUUNNITTELUpinnoille:
    nollapeli-%, xP-projektiot, chip-ikkunat, siirtosuunnittelu, jakokortit.
    Projektio kierrokselle jonka deadline on mennyt ei ole ennuste vaan
    historiaa vaarassa asussa.

    Lahde on `meta.deadline_gameweek`, joka tulee FPL:n deadline-aikaleimoista
    eika `is_current`-lipusta, ja on siksi oikein myos silloin kun FPL laahaa.

    Kentta puuttuu (vanha payload) -> `current_gameweek`, eli kaytos
    bittitarkasti entinen.
    """
    dl = (meta or {}).get("deadline_gameweek")
    if isinstance(dl, int):
        return dl
    return current_gameweek(meta)


def display_gameweek(meta: dict, fixtures: list[dict] | None = None) -> int | None:
    """Kierros jonka SIVU nayttaa. Siirtyy vasta kun kierros on kokonaan alkanut.

    Valimuoto kahden yllaolevan valilla, ja se on tarkoituksellinen:

    - Kesken kierroksen sivu nayttaa KULUVAA kierrosta. Lukijan joukkue keraa
      pisteita juuri nyt, ja kierroksen vaihtaminen alta kesken pelien olisi
      hammentavaa.
    - Kun kierroksen JOKAINEN ottelu on alkanut, kierros on ohi lukijan
      kannalta ja sivu siirtyy siihen johon voi viela vaikuttaa.

    🔴 EHTO ON `all` EIKA `any`. Yksikin alkamaton ottelu pitaa sivun
    paikallaan. `any` siirtaisi sivun heti ensimmaisen ottelun alettua, eli
    kesken kierroksen.

    🔴 EI NOJAA FPL:N `finished`-LIPPUUN. Mitattu 25.8: `event.finished` oli
    False 14 h viimeisen ottelun jalkeen. Kickoff-aika ei voi laahata.

    `fixtures` puuttuu -> `actionable_gameweek` (ei voida tarkistaa
    kesken-oloa, ja ennustepinnalla actionable on turvallisempi oletus).
    """
    cur = current_gameweek(meta)
    act = actionable_gameweek(meta)
    if cur is None or act is None or act <= cur:
        return cur if cur is not None else act
    if fixtures is None:
        return act
    fx = [f for f in fixtures
          if f.get("gameweek") == cur and f.get("kickoff_ms")]
    if not fx:
        return cur
    now_ms = _dt.datetime.now(_dt.timezone.utc).timestamp() * 1000
    return act if all(f["kickoff_ms"] < now_ms for f in fx) else cur


def actionable_gameweeks(meta: dict, gws) -> list[int]:
    """Suodata kierroslista niihin joihin voi viela vaikuttaa.

    🔴 MIKSI SUODATIN EIKA PUDOTUS LAHTEESSA: projektiotiedostot kantavat
    tarkoituksella myos jo pelattua kierrosta, koska rate_team ("Team xP, GW1"
    kesken kierroksen) ja Model vs actual TARVITSEVAT sen. Lahteesta
    pudottaminen rikkoisi ne. Sen sijaan jokainen ENNUSTEpinta suodattaa.

    Mitattu 25.8: `fpl_xp_projections.json` kantoi kierrokset 1-6 samalla kun
    GW1 oli pelattu ja `deadline_gameweek` oli 2. Ilman suodatinta ikkunateksti
    lupasi "GW1-6" ja summat laskivat mukaan kierroksen jota ei voi enaa
    pelata - kokonaisen kierroksen verran vaarin.
    """
    act = actionable_gameweek(meta)
    # 🔴 KAKSI MUOTOA REPOSSA. `gameweeks` on osassa projektioita dict-lista
    # ({"gw": 2, "xp": ...}) ja osassa pelkka int-lista. Kutsupaikan ei kuulu
    # tietaa kumpi - se tieto on hajallaan kymmenessa tiedostossa. Mitattu
    # 25.8: oletin dict-muodon ja kaadoin 12 team-news-testia.
    out: list[int] = []
    for g in gws or []:
        if isinstance(g, dict):
            g = g.get("gw")
        if g is None:
            continue
        try:
            out.append(int(g))
        except (TypeError, ValueError):
            continue
    if act is None:
        return sorted(out)
    return sorted(g for g in out if g >= act)


def window_label(meta: dict, gws, fallback_n: int | None = None) -> str:
    """Ikkunateksti ("GW2-6") JOHDETTUNA todellisista kierroksista.

    🔴 EI `first + n - 1`. Se kaava oli kaytossa neljalla longtail-sivulla ja se
    valehtelee heti kun lista ja aloituskierros ovat eri mielta: jos data
    kattaa GW1-6 ja aloitus siirtyy GW2:een, kaava tuottaa "GW2-7" eli
    kierroksen jota listalla ei ole. Johdetaan min:sta ja max:sta.
    """
    act = actionable_gameweeks(meta, gws)
    if not act:
        return f"the next {fallback_n} GWs" if fallback_n else "the next GWs"
    if len(act) == 1:
        return f"GW{act[0]}"
    return f"GW{act[0]}-{act[-1]}"
