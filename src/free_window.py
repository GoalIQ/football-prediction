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


# ---------------------------------------------------------------------------
# PINTAKOHTAISET LOHKOT (12.9.2026)
#
# TAUSTA. `note()` riitti niille pinnoille joilla lupaus on LAUSE: kun ikkuna
# sulkeutuu, lause katoaa ja sivu on oikein. Mutta kolmella pinnalla lupaus ei
# ole lause vaan RAKENNE - bandi, ostonappi ja hintalappu - ja niista ei saa
# tulla tyhjaa: napista pitaa jaada nappi ja hintalapusta hinta.
#
# Mitattu 12.9 klo 08:30 UTC, 4 h ennen sulkeutumista: `index.html` olisi
# jaanyt nayttamaan napin "Get Premium free" ja hintalapun "Free until
# 12 Sept", ja `predictions.html` koko lupauslauseen, koska niita ei poista
# mikaan. Molemmat ovat tulopuolen vaitteita ja molemmat kytkeytyvat paalle
# itsestaan (muisti: ehto-ei-vanhene-teksti-vanhenee).
#
# Ratkaisu on sama kuin `fpl.html`illa jo on: lohkolla on KAKSI tilaa, ja
# `is_open()` valitsee. Sivulla lohko elaa GEN-markkereiden valissa kuten muu
# generoitu sisalto tassa repossa, ja `check_free_window.py --fix` renderoi
# sen joka page-refresh-ajossa - myos ikkunan ollessa auki, jolloin se on
# no-op. Ikkunan sulkeutuminen ei siis vaadi ketaan muistamaan mitaan.
# ---------------------------------------------------------------------------

PRO_URL = "https://pro.goaliq.app/"


def band_html(now: _dt.datetime | None = None) -> str:
    """index.html: navin alla oleva ilmaisikkunabandi. Kiinni = ei bandia."""
    if not is_open(now):
        return ""
    return (
        '<div class="free-band">\n'
        '  <div class="wrap free-band-in">\n'
        '    <p class="free-band-txt">\n'
        f'      <strong>Premium is free on the web until the {day_label()} '
        'deadline</strong>\n'
        '      <span>That is GW1 to GW3. Create a free account and it is on. '
        'No card, nothing to cancel.</span>\n'
        '    </p>\n'
        f'    <a class="btn-band" href="{PRO_URL}" data-cta="band-freewindow">'
        'Get Premium free &#9656;</a>\n'
        '  </div>\n'
        '</div>')


def hero_cta_html(now: _dt.datetime | None = None) -> str:
    """index.html: heron ensimmainen nappi. Kiinni = nappi jaa, lupaus lahtee."""
    if is_open(now):
        return (f'<a class="btn btn-primary" href="{PRO_URL}" '
                'data-cta="hero-freewindow">Get Premium free &#9656;</a>')
    return (f'<a class="btn btn-primary" href="{PRO_URL}" '
            'data-cta="hero-premium">Get Premium &#9656;</a>')


def hero_price_note_html(now: _dt.datetime | None = None) -> str:
    """index.html: heron hintanootti heti CTA-napin alla.

    12.9.2026: TAMA JAI. `hero_cta_html` vaihtoi napin oikein 12:30, mutta
    sen ALLA oleva rivi oli GEN-markkerien ULKOPUOLELLA ja kovakoodattu:
    "After 12 September it is EUR3.99 a month or EUR25 a year." Ville huomasi
    sen livena. Lause ei ole ilmaislupaus, joten `check_free_window.py`:n
    vaiteperhe ei nahnyt sita — se on **paivamaaraan sidottu hintavaite**,
    joka muuttuu oudoksi sina hetkena kun paiva menee. Sama luokka kuin
    `build_fpl_page.free_window_block`:n hoitama lause, eri pinnalla.

    Osittainen GEN-kate on pahempi kuin ei katetta: se saa nakyttamaan silta
    etta pinta on hoidettu.
    """
    if is_open(now):
        return (f'<p class="cta-note">After {day_label()} it is &euro;3.99 '
                f'a month or <a href="{PRO_URL}checkout?plan=season" '
                'data-cta="hero">&euro;25 a year</a>.</p>')
    return (f'<p class="cta-note">&euro;3.99 a month, or '
            f'<a href="{PRO_URL}checkout?plan=season" data-cta="hero">'
            '&euro;25 a year</a>.</p>')


def price_tag_html(now: _dt.datetime | None = None) -> str:
    """index.html: Premium-sarakkeen hintalappu.

    Hinnat pysyvat NAKYVISSA molemmissa tiloissa: kumppaneita on ohjeistettu
    tarkistamaan oma provisionsa talta sivulta ilman tilia (sivun oma
    kommentti). Vain ilmaisuuslupaus vaihtuu.
    """
    if is_open(now):
        return ('<h3><span class="price-tag">Free<span> until 12 Sept</span>'
                '</span> <span class="price-alt">then &euro;25 / year or '
                '&euro;3.99 / month</span></h3>')
    return ('<h3><span class="price-tag">&euro;3.99 / month</span> '
            '<span class="price-alt">or &euro;25 / year</span></h3>')


def predictions_price_html(now: _dt.datetime | None = None) -> str:
    """predictions.html: Premium-kortin hinta ja sen alla oleva lupaus.

    Auki: ilmaisilmoitus on hinnan YLAPUOLELLA tarkoituksella (sivun oma
    kommentti) - toisin pain sivu naytti hintalapun suoraan sen lauseen
    ylapuolella joka sanoo ettei tarvitse maksaa.
    """
    if is_open(now):
        return (
            '<div class="price">Free<span> until 12 Sept</span></div>\n'
            '      <p style="border-left:3px solid var(--amber);'
            'padding-left:10px;">' + note(now) + '</p>\n'
            '      <p style="color:var(--muted);">After that it is '
            '\u20ac25 a year or \u20ac3.99 a month.\n'
            '        Go deeper on every prediction.</p>')
    return (
        '<div class="price">\u20ac3.99 / month</div>\n'
        '      <p style="color:var(--muted);">Or \u20ac25 a year.\n'
        '        Go deeper on every prediction.</p>')


#: (tiedosto, GEN-avain) -> renderoija. Yksi taulukko, jotta uusi pinta
#: lisataan tasan yhteen paikkaan eika kahteen.
SURFACE_BLOCKS = {
    ("index.html", "FREE-BAND"): band_html,
    ("index.html", "FREE-CTA"): hero_cta_html,
    ("index.html", "FREE-HERO-PRICE"): hero_price_note_html,
    ("index.html", "FREE-PRICE"): price_tag_html,
    ("predictions.html", "FREE-PRICE"): predictions_price_html,
}
