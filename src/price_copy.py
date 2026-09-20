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

ALUEHINTA. 20.9 alkaen yhdeksan mitattua markkinaa saa halvemman hinnan
(`src/regional_pricing.py`). Staattinen sivu ei voi nayttaa kavijakohtaista
lukua, joten se kertoo LISTAhinnan ja `LOCAL_NOTE` sanoo etta se voi olla
alempi. Vaittamatta mitaan tiettya lukua: 25 EUR on tosi valtaosalle, ja
se jolle se ei ole, nakee oikean luvun maksumuurilla (`/api/web/pricing`).
"""
from __future__ import annotations

#: Listahinta. EI kirjoiteta kasin muualle.
MONTHLY = "3.99"
SEASON = "25"

#: Aluehinnan varaus. Tarkistettavissa niille joita se koskee: he nakevat
#: oikean luvun maksumuurilla ja Checkoutissa.
LOCAL_NOTE = "Prices are lower in some countries."


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
