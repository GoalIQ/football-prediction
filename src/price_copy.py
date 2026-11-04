"""YKSI LUKIJA: Premiumin listahinta julkisessa tekstissa.

MITATTU 20.9.2026. Sama hintalause oli kovakoodattuna VIIDESSA paikassa
neljassa tiedostossa (`build_fpl_page.py` x2, `build_fpl_longtail.py`,
`build_prediction_pages.py`, `free_window.py` x2), jokainen omalla
kirjoitusasullaan: "3.99 EUR a month", "3.99 €/month", "€3.99 a month".
Hinnanmuutos olisi pitanyt muistaa viidesta paikasta, ja unohtunut paikka
olisi jaanyt vaittamaan vanhaa hintaa maaramattomaksi ajaksi - juuri se
vikaluokka jota vastaan `data/rejected_phrases.json` ja copy-sync-gate ovat
olemassa.

Numerot tulevat nyt taalta. Kirjoitusasu jaa kunkin pinnan omaksi, koska
rekisterit eroavat (hero, FAQ-proosa, alatunniste) eika niita kannata
pakottaa samaan muottiin - mutta LUKU on yksi.

`tests/test_price_copy_discipline.py` kaataa buildin jos luku ilmestyy
takaisin kasin kirjoitettuna.

ALUEHINTA POISTUI 17.10.2026. 20.9 alkaen yhdeksan markkinaa sai verkossa
halvemman hinnan, ja sivut sanoivat "Prices are lower in some countries."
17.10 alkaen verkko-osto on auki vain `src/regional_pricing.py`:n
WEB_CHECKOUT_COUNTRIES-maissa, eika yhdellakaan niista ole aluehintaa, joten
lause olisi epatosi. Se on `data/rejected_phrases.json`:ssa, jotta se ei palaa.
"""
from __future__ import annotations

#: Listahinta. EI kirjoiteta kasin muualle.
MONTHLY = "3.99"
SEASON = "25"


def monthly(symbol: str = "€", *, before: bool = True) -> str:
    """'€3.99' tai '3.99 €'."""
    return f"{symbol}{MONTHLY}" if before else f"{MONTHLY} {symbol}"


def season(symbol: str = "€", *, before: bool = True) -> str:
    return f"{symbol}{SEASON}" if before else f"{SEASON} {symbol}"


# --- WP6 kausipassi (4.11.2026) -------------------------------------------
#
# Villen paatos 1.11: verkon vuosipaketti on KERTAMAKSU (25 €, Premium
# 30.5.2027 asti, ei uusiudu). Ennen sita se oli tilaus, ja hubin pinnat
# sanoivat "€25 a year", "25 €/year", "Cancel anytime" ja "One subscription
# covers ..." kukin omin sanoin (free_window, build_fpl_page x3,
# build_fpl_longtail, build_prediction_pages x2, index.html, faq.html).
# Passitilassa ne olisivat epatosia, joten vuosipaketin sanat tulevat nyt
# TAALTA ja loppupaiva `src.season_pass`ista (sama lahde kuin webhook ja
# API:n Premium-portti).
#
# Hub on staattinen, joten se ei voi lukea Renderin kytkinta
# (STRIPE_PRICE_SEASON_PASS_2026_27) ajossa kuten SPA. Tama muutos mergetaan
# VASTA kun kytkin on paalla ja /api/stripe-config price_lookup.season_pass
# .ok == true; goaliq-appin ground_truth vertaa sen jalkeen elavaa
# hintavastausta etusivun tekstiin. Portti: tests/test_season_pass_copy.py.

_KUUKAUDET = ("January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December")


def pass_end() -> str:
    """Passin loppupaiva lukijan sanoin: '30 May 2027' (UTC-paiva, sama kuin
    SPA:n formatPassEnd). Kuukauden nimi taulukosta, ei strftime %B:sta:
    se seuraa koneen localea."""
    from src.season_pass import SEASON_PASS_END
    d = SEASON_PASS_END
    return f"{d.day} {_KUUKAUDET[d.month - 1]} {d.year}"


def season_cta(symbol: str = "€", *, before: bool = True) -> str:
    """Ostonapin hinta: '€25 for the season'."""
    return f"{season(symbol, before=before)} for the season"


def season_once(symbol: str = "€", *, before: bool = True) -> str:
    """Hintalauseen vuosiosa: '25 € once for the season (until 30 May 2027)'."""
    return f"{season(symbol, before=before)} once for the season (until {pass_end()})"


#: Kattavuus: yksi TILI, ei "one subscription" (passi ei ole tilaus).
COVERAGE = "One Premium account covers web, iOS and Android."

#: Lyhyt ehto ostonapin alle. Kuukausipaketti on yha tilaus.
TERMS_SHORT = "Season pass: one payment, nothing renews. Monthly: cancel anytime."


def season_monthly_cap() -> str:
    """Vuosihinta kuukautta kohden, pyoristettynä YLOS kymmenykseen.

    "under EUR 2.10 a month" oli kovakoodattu kahteen paikkaan. Se on
    JOHDETTU luku: jos vuosihinta muuttuu eika tata muuteta, sivu vaittaa
    vaaraa. Pyoristys on ylos, jotta "under" pysyy totena.
    """
    import math
    kuukausi = float(SEASON) / 12.0
    return f"{math.ceil(kuukausi * 10) / 10:.2f}"
