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


def season_monthly_cap() -> str:
    """Vuosihinta kuukautta kohden, pyoristettynä YLOS kymmenykseen.

    "under EUR 2.10 a month" oli kovakoodattu kahteen paikkaan. Se on
    JOHDETTU luku: jos vuosihinta muuttuu eika tata muuteta, sivu vaittaa
    vaaraa. Pyoristys on ylos, jotta "under" pysyy totena.
    """
    import math
    kuukausi = float(SEASON) / 12.0
    return f"{math.ceil(kuukausi * 10) / 10:.2f}"
