"""Ilmaisen Premium-ikkunan YKSI lähde (30.8.2026, Villen huomio).

TAUSTA. Lause "Premium is free on the web until the GW4 deadline on
12 September" oli kovakoodattuna vähintään kahdeksaan paikkaan: sivu-
generaattoriin, viiteen SPA-komponenttiin, `creators.html`:ään,
`faq.html`:ään (4 mainintaa) ja `llms.txt`:ään. Näistä vain yksi on
generoitu; loput ovat käsin ylläpidettyjä eikä mikään poista niitä.

🔴 Se tarkoittaa, että 12.9.2026 klo 12:30 UTC jokainen niistä alkaa
väittää Premiumin olevan ilmainen kun se ei ole. Väite on tulopuolta
koskeva ja se kytkeytyy päälle itsestään ilman että kukaan tekee mitään
(muisti: ehto-ei-vanhene-teksti-vanhenee).

Mobiilissa vastine on ollut olemassa koko ajan
(`goaliq-app/lib/freePremiumWindow.ts`); tämä on sen backend-pari, sama
aikaleima.

Käyttö generaattorissa:
    from src.free_window import note
    ...
    {note()}          # tyhjä merkkijono kun ikkuna on kiinni
"""
from __future__ import annotations

import datetime as _dt

#: Sama arvo kuin goaliq-app/lib/freePremiumWindow.ts FREE_PREMIUM_UNTIL.
#: Jos tätä muutetaan, muuta myös se — `check_free_window.py` vertaa niitä.
FREE_PREMIUM_UNTIL = "2026-09-12T12:30:00Z"

#: Ihmisluettava päivä lauseeseen. Johdetaan yllä olevasta, ei kirjoiteta
#: erikseen: kaksi kirjoitettua päivämäärää ajautuisi erilleen.
_UNTIL = _dt.datetime.fromisoformat(FREE_PREMIUM_UNTIL.replace("Z", "+00:00"))


def until() -> _dt.datetime:
    return _UNTIL


def is_open(now: _dt.datetime | None = None) -> bool:
    """Onko ilmaisikkuna auki juuri nyt."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_dt.timezone.utc)
    return now < _UNTIL


def day_label() -> str:
    """'12 September' — sama muoto kuin sivuilla ennestään."""
    return _UNTIL.strftime("%d %B").lstrip("0")


def note(now: _dt.datetime | None = None) -> str:
    """Ilmaisikkunan lause, tai TYHJÄ kun ikkuna on kiinni.

    Tyhjä on tarkoituksellinen: kutsupaikka upottaa paluuarvon suoraan
    sivulle, joten ikkunan sulkeutuminen poistaa lauseen ilman että
    kenenkään tarvitsee muistaa poistaa se.
    """
    if not is_open(now):
        return ""
    return (f"Premium is free on the web until the GW4 deadline on "
            f"{day_label()}, so GW1 to GW3. Create a free account and "
            f"it's on. No card, nothing to cancel.")
