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

PAISTETTU SIVU SULKEUTUU ITSE (17.9.2026, ILMAISIKKUNA-SULKEUTUU-ITSE).
Mitattu 12.9: ikkunan sulkeutuminen paistetuilla hub-sivuilla riippui
siitä että ihminen dispatchaa `fpl-page-refresh`in. Ajastettua sivuajoa ei
ollut 12:30–15:00 välillä, joten 19 lupausta 6 sivulla olisi elänyt 2,5 h
yli lupauksensa ellei joku ole paikalla. SPA ja mobiili sulkeutuivat itse,
koska ne lukevat aikaleiman AJOSSA. Paistettu sivu luki sen PAISTOSSA.

Korjaus (sääntö 6a): `self_closing_block()`. Lohkon staattinen oletus on
SULJETTU teksti. Avoin teksti elää inertissä `<template>`-elementissä ja
inline-skripti näyttää sen vain kun selaimen `Date.now() < data-until`,
ja palauttaa suljetun tekstin tasan deadlinella jos sivu on silloin auki.
Ilman JavaScriptiä näkyy suljettu teksti. Lupaus ei voi jäädä roikkumaan:
sivu ei enää tarvitse ketään sulkeutuakseen.
"""
from __future__ import annotations


import datetime as _dt
import json as _json
from src import price_copy as PC

#: IKKUNAN HETKI. Tama on backendin ja jokaisen paistetun sivun LAHDE:
#: `api/premium.py` tuo taman (ei kirjoita omaa), ja sivun `data-until`,
#: `is_open()`, `day_label()` seka portin template-lukija johdetaan tasta.
#:
#: 🔴 EI "AINOA PAIKKA" - NELJA PINTAA, JOISTA KAKSI ON TAMAN ULOTTUVILLA.
#: 18.9.2026 adversariaalinen tarkistaja mittasi, etta tahan tiedostoon oli
#: kirjoitettu vaite "tama on ainoa paikka jossa aikaleima kirjoitetaan" ja
#: sen vartijaksi testi joka skannasi KOLME kasin nimettya tiedostoa - eli
#: tasan se vikaluokka (kasin nimetty lista) jonka saanto 6a kieltaa. Hetki
#: eli tosiasiassa neljassa paikassa ja eri muodoissa:
#:   1. tama (`...Z`)
#:   2. `api/premium.py` (`...+00:00`) - OIKEUDEN portti, eli kuka oikeasti
#:      saa premiumin. 18.9 tehty lukijaksi: se tuo taman arvon.
#:   3. `web/pro-spa/src/lib/auth.svelte.ts` (TypeScript, ei voi importata)
#:   4. mobiilirepo `goaliq-app/lib/freePremiumWindow.ts` (ERI REPO)
#: Ilman korjausta seuraava ikkuna olisi voitu avata tasta tiedostosta ja
#: unohtaa `api/premium.py`: sivut olisivat luvanneet ilmaista siihen asti
#: kun API ei enaa anna sita, ja jokainen portti olisi ollut vihrea.
#: Mitattu 18.9 palauttamalla kutsupaikka: portti tulosti "OK: ilmaisikkuna
#: on auki 3 October asti", exit 0, samalla kun API sulki sen 12.9.
#:
#: 3. ja 4. eivat voi importata Pythonia, joten ne vartioidaan HETKENA eika
#: merkkijonona: `tests/test_free_window_self_closing.py` skannaa jokaisen
#: tiedoston joka nimeaa `FREE_PREMIUM_UNTIL`:in ja vaatii, etta jokainen
#: sen ISO-aikaleima jasentyy SAMAKSI hetkeksi kuin tama. Skannaus ei ole
#: kasin nimetty lista: uusi pinta joutuu listalle nimen kautta.
FREE_PREMIUM_UNTIL = "2026-09-12T12:30:00Z"


def parse_until(iso: str) -> _dt.datetime | None:
    """ISO-aikaleima -> aware datetime, tai None jos ei jäsenny.

    None on tarkoituksellinen: selaimessa `Date.parse` palauttaa NaN:in ja
    `Date.now() < NaN` on epätosi, eli lohko jää SULJETUKSI. Pythonin on
    vastattava samoin, muuten portti ja selain olisivat eri mieltä
    rikkinäisestä attribuutista.
    """
    try:
        d = _dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=_dt.timezone.utc)
    return d


def open_at(until_iso: str, now: _dt.datetime | None = None) -> bool:
    """YKSI LUKIJA: onko ikkuna auki hetkellä `now`, kun se sulkeutuu
    `until_iso`:na. Sama predikaatti kuin inline-skriptin
    `Date.now() < Date.parse(until)`: raja on aikaleima, ei päivä, ja tasan
    rajalla ikkuna on kiinni.

    Sekä `is_open()` (moduulin vakio) että portin template-lukija (sivun
    `data-until`) kulkevat tästä, jotta kysymykseen "näkyykö lupaus" on
    yksi vastaus eikä kaksi.
    """
    until = parse_until(until_iso)
    if until is None:
        return False
    now = now or _dt.datetime.now(_dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_dt.timezone.utc)
    return now < until


#: Ihmisluettava päivä lauseeseen. Johdetaan yllä olevasta, ei kirjoiteta
#: erikseen: kaksi kirjoitettua päivämäärää ajautuisi erilleen.
_UNTIL = parse_until(FREE_PREMIUM_UNTIL)
assert _UNTIL is not None, "FREE_PREMIUM_UNTIL ei jäsenny"


def until() -> _dt.datetime:
    return _UNTIL


def is_open(now: _dt.datetime | None = None) -> bool:
    """Onko ilmaisikkuna auki juuri nyt."""
    return open_at(FREE_PREMIUM_UNTIL, now)


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
    return note_text()


def note_text() -> str:
    """Lupauslause ilman ajan ehtoa. Kutsutaan vain sieltä missä ehto on
    jo ratkaistu (template-haara); julkinen pinta käyttää `note()`:a."""
    return (f"Premium is free on the web until the GW4 deadline on "
            f"{day_label()}, so GW1 to GW3. Create a free account and "
            f"it's on. No card, nothing to cancel.")


# ---------------------------------------------------------------------------
# ITSESTÄÄN SULKEUTUVA LOHKO (17.9.2026)
#
# Rakenne sivulla, kun ikkuna on auki paistohetkellä:
#
#   <template data-free-window-open="KEY" data-until="…Z">AVOIN HTML</template>
#   SULJETTU HTML                                    <- staattinen oletus
#   <template data-free-window-end="KEY"></template>
#   <script>(function(k){…})("KEY");</script>
#
# Skripti: jos Date.now() < data-until, se irrottaa solmut kahden templaten
# välistä (suljettu tila) ja liittää avoimen templaten sisällön tilalle.
# Se ajastaa itselleen paluun deadlinelle, joten sivu joka on auki 12:29
# näyttää suljetun tekstin 12:30 ilman latausta. Ilman JavaScriptiä
# `<template>` on inertti: ei renderöidy, ei saavutettavuuspuussa, ei
# hakukoneen tekstissä. Suljettu HTML on se mitä kaikki näkevät oletuksena.
#
# Kun ikkuna on jo kiinni paistohetkellä, lohko on PELKKÄ suljettu HTML:
# avointa tekstiä ei voi enää koskaan tarvita, joten vanhentunutta
# tarjousta ei jätetä lähdekoodiin tekstiksi jonka naiivi raapija lukisi.
# Kummassakin tapauksessa: lupaus näkyy vain kun se on tosi, ja sulkeutuminen
# ei tarvitse yhtään ajoa.
# ---------------------------------------------------------------------------

#: Attribuutit joilla portti (`check_free_window.py`) tunnistaa rakenteen.
#: Nimet elävät täällä, jotta skripti ja lukija eivät kirjoita niitä erikseen.
OPEN_ATTR = "data-free-window-open"
END_ATTR = "data-free-window-end"
UNTIL_ATTR = "data-until"

#: Inline-skripti, ES5 jotta vanha WebView ei kaadu. `%s` on JSON-koodattu
#: avain. Predikaatti `Date.now()<u` on sama kuin `open_at()`: tasan rajalla
#: kiinni. `Math.min(…, 2147483647)`: setTimeout ei kestä yli 24,8 vrk:n
#: viivettä, joten kaukainen deadline tarkistetaan uudelleen erissä.
INLINE_SCRIPT_TMPL = (
    "(function(k){"
    "var d=document,"
    "o=d.querySelector('template[" + OPEN_ATTR + "=\"'+k+'\"]'),"
    "e=d.querySelector('template[" + END_ATTR + "=\"'+k+'\"]');"
    "if(!o||!e||!o.content)return;"
    "var u=Date.parse(o.getAttribute('" + UNTIL_ATTR + "'));"
    "if(!(Date.now()<u))return;"
    "var p=o.parentNode,c=[],n=o.nextSibling,i;"
    "while(n&&n!==e){c.push(n);n=n.nextSibling;}"
    "for(i=0;i<c.length;i++)p.removeChild(c[i]);"
    "var f=d.importNode(o.content,true),a=[].slice.call(f.childNodes);"
    "p.insertBefore(f,e);"
    "function back(){"
    "if(Date.now()<u){setTimeout(back,Math.min(u-Date.now(),2147483647));return;}"
    "for(i=0;i<a.length;i++)if(a[i].parentNode)a[i].parentNode.removeChild(a[i]);"
    "for(i=0;i<c.length;i++)p.insertBefore(c[i],e);"
    "}"
    "setTimeout(back,Math.min(u-Date.now(),2147483647));"
    "})(%s);"
)


def inline_script(key: str) -> str:
    return INLINE_SCRIPT_TMPL % _json.dumps(key)


def self_closing_block(key: str, closed_html: str, open_html: str,
                       now: _dt.datetime | None = None) -> str:
    """Lohko jonka staattinen oletus on SULJETTU teksti.

    `key` on lohkon tunniste sivulla (yksi per sivu). `closed_html` näkyy
    ilman JavaScriptiä ja aina kun `Date.now() >= FREE_PREMIUM_UNTIL`.
    `open_html` näkyy vain skriptin kautta ja vain sitä ennen.

    Paistohetken `now` ratkaisee vain sen, kirjoitetaanko avoin haara
    lähdekoodiin lainkaan. Se ei ratkaise mitä lukija näkee: sen ratkaisee
    lukijan kello. Paistoaika ei siis voi enää jättää lupausta roikkumaan.
    """
    if not is_open(now):
        return closed_html
    return (
        f'<template {OPEN_ATTR}="{key}" {UNTIL_ATTR}="{FREE_PREMIUM_UNTIL}">'
        f'{open_html}</template>\n'
        f'{closed_html}\n'
        f'<template {END_ATTR}="{key}"></template>\n'
        f'<script>{inline_script(key)}</script>')


# ---------------------------------------------------------------------------
# PINTAKOHTAISET LOHKOT (12.9.2026, itsestään sulkeutuviksi 17.9.2026)
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
# Jokaisella lohkolla on KAKSI tilaa. Sivulla lohko elaa GEN-markkereiden
# valissa kuten muu generoitu sisalto tassa repossa, ja
# `check_free_window.py --fix` renderoi sen joka page-refresh-ajossa.
# 17.9 alkaen tilan valitsee lukijan selain (`self_closing_block`), ei
# paistoajo: ajo vain kirjoittaa molemmat tilat sivulle.
# ---------------------------------------------------------------------------

PRO_URL = "https://pro.goaliq.app/"


def band_open_html() -> str:
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


def band_html(now: _dt.datetime | None = None) -> str:
    """index.html: navin alla oleva ilmaisikkunabandi. Kiinni = ei bandia."""
    return self_closing_block("FREE-BAND", "", band_open_html(), now)


def hero_cta_open_html() -> str:
    return (f'<a class="btn btn-primary" href="{PRO_URL}" '
            'data-cta="hero-freewindow">Get Premium free &#9656;</a>')


def hero_cta_closed_html() -> str:
    """22.9.2026 (web-audit T4): hinta nappiin ja nappi hinnastoon.

    Ennen nappi sanoi vain "Get Premium" ja vei pron juureen, josta ostoon oli
    kaksi klikkausta ja vieritys. Hinta nakyi ensimmaisen kerran pienena
    versaalirivina napin alla, ja landingin suorat hintanapit saivat 0
    klikkausta 30 vrk:ssa. `?tab=premium` avaa pron hinnastonakyman.
    """
    return (f'<a class="btn btn-primary" href="{PRO_URL}?tab=premium" '
            f'data-cta="hero-premium">Get Premium &middot; &euro;{PC.SEASON} '
            'a year &#9656;</a>')


def hero_cta_html(now: _dt.datetime | None = None) -> str:
    """index.html: heron ensimmainen nappi. Kiinni = nappi jaa, lupaus lahtee."""
    return self_closing_block("FREE-CTA", hero_cta_closed_html(),
                              hero_cta_open_html(), now)


def hero_price_note_open_html() -> str:
    return (f'<p class="cta-note">After {day_label()} it is &euro;3.99 '
            f'a month or <a href="{PRO_URL}checkout?plan=season" '
            'data-cta="hero">&euro;25 a year</a>.</p>')


def hero_price_note_closed_html() -> str:
    return (f'<p class="cta-note">&euro;{PC.MONTHLY} a month, or '
            f'<a href="{PRO_URL}checkout?plan=season" data-cta="hero">'
            f'&euro;{PC.SEASON} a year</a>. {PC.LOCAL_NOTE}</p>')


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
    return self_closing_block("FREE-HERO-PRICE", hero_price_note_closed_html(),
                              hero_price_note_open_html(), now)


def price_tag_open_html() -> str:
    return ('<h3><span class="price-tag">Free<span> until 12 Sept</span>'
            '</span> <span class="price-alt">then &euro;25 / year or '
            '&euro;3.99 / month</span></h3>')


def price_tag_closed_html() -> str:
    return ('<h3><span class="price-tag">&euro;3.99 / month</span> '
            '<span class="price-alt">or &euro;25 / year</span></h3>')


def price_tag_html(now: _dt.datetime | None = None) -> str:
    """index.html: Premium-sarakkeen hintalappu.

    Hinnat pysyvat NAKYVISSA molemmissa tiloissa: kumppaneita on ohjeistettu
    tarkistamaan oma provisionsa talta sivulta ilman tilia (sivun oma
    kommentti). Vain ilmaisuuslupaus vaihtuu.
    """
    return self_closing_block("FREE-PRICE", price_tag_closed_html(),
                              price_tag_open_html(), now)


def predictions_price_open_html() -> str:
    return (
        '<div class="price">Free<span> until 12 Sept</span></div>\n'
        '      <p style="border-left:3px solid var(--amber);'
        'padding-left:10px;">' + note_text() + '</p>\n'
        '      <p style="color:var(--muted);">After that it is '
        f'€{PC.SEASON} a year or €{PC.MONTHLY} a month. '
        f'{PC.LOCAL_NOTE}\n'
        '        Go deeper on every prediction.</p>')


def predictions_price_closed_html() -> str:
    return (
        f'<div class="price">€{PC.MONTHLY} / month</div>\n'
        f'      <p style="color:var(--muted);">Or €{PC.SEASON} a year. '
        f'{PC.LOCAL_NOTE}\n'
        '        Go deeper on every prediction.</p>')


def predictions_price_html(now: _dt.datetime | None = None) -> str:
    """predictions.html: Premium-kortin hinta ja sen alla oleva lupaus.

    Auki: ilmaisilmoitus on hinnan YLAPUOLELLA tarkoituksella (sivun oma
    kommentti) - toisin pain sivu naytti hintalapun suoraan sen lauseen
    ylapuolella joka sanoo ettei tarvitse maksaa.
    """
    return self_closing_block("FREE-PRICE", predictions_price_closed_html(),
                              predictions_price_open_html(), now)


#: (tiedosto, GEN-avain) -> renderoija. Yksi taulukko, jotta uusi pinta
#: lisataan tasan yhteen paikkaan eika kahteen.
SURFACE_BLOCKS = {
    ("index.html", "FREE-BAND"): band_html,
    ("index.html", "FREE-CTA"): hero_cta_html,
    ("index.html", "FREE-HERO-PRICE"): hero_price_note_html,
    ("index.html", "FREE-PRICE"): price_tag_html,
    ("predictions.html", "FREE-PRICE"): predictions_price_html,
}
