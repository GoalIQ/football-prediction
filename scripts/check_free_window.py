#!/usr/bin/env python
"""ILMAISIKKUNA-PORTTI: lupaus ilmaisesta Premiumista ei saa jaada elamaan.

TAUSTA (30.8.2026). "Premium is free on the web until the GW4 deadline on
12 September" oli kovakoodattuna vahintaan kahdeksaan paikkaan, joista vain
YKSI on generoitu. Loput ovat kasin yllapidettyja (faq.html 4 mainintaa,
creators.html, llms.txt, viisi SPA-komponenttia), eika mikaan poista niita.
12.9.2026 klo 12:30 UTC jokainen niista alkaa vaittaa Premiumin olevan
ilmainen kun se ei ole. Vaite koskee tulopuolta ja kytkeytyy paalle itsestaan.

Portti tekee kaksi asiaa:
  1. Ikkunan SULJETTUA: kaatuu jos yksikaan julkinen pinta yha lupaa ilmaista.
     Tama on se hetki jolloin kukaan ei muista katsoa.
  2. Ikkunan ollessa AUKI: tulostaa missa lupaus elaa, jotta blast radius on
     tiedossa ENNEN kuin ikkuna sulkeutuu.

Generoiduilla pinnoilla lause johdetaan `src.free_window`:sta ja katoaa
itsestaan; tama portti on kasin yllapidettyja pintoja varten, joita koodi ei
voi korjata puolestaan.

ITSESTAAN SULKEUTUVA LOHKO (17.9.2026, ILMAISIKKUNA-SULKEUTUU-ITSE).
Paistetun sivun lupaus elaa nyt `<template data-free-window-open=KEY
data-until=ISO>`-elementissa, jonka inline-skripti nayttaa vain kun
selaimen `Date.now() < data-until`. Suljettu teksti on staattinen oletus.
Portin lukija (`luettava_teksti`) arvioi templaten SAMALLA predikaatilla
(`src.free_window.open_at`) sivun OMASTA `data-until`-arvosta: sisalto
lasketaan nakyvaksi tasan silloin kun selain nayttaisi sen. Ilman tata
portti raportoisi ikkunan sulkeuduttua vaaran positiivisen jokaisesta
templatesta - ja paivittain punainen portti tulee ohitetuksi. Kaanteinen
vika on sama: jos lukija pyyhkisi templaten aina, se olisi sokea sille
mita JS-lukija nakee ennen deadlinea.

Kaytto:
    python scripts/check_free_window.py
"""
from __future__ import annotations

import datetime as _dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.free_window import (  # noqa: E402
    END_ATTR, FREE_PREMIUM_UNTIL, OPEN_ATTR, UNTIL_ATTR, day_label, is_open,
    open_at)

#: Hetki jolla jokainen template on auki: rajaustarkistus lukee templaten
#: sisallon kellosta riippumatta (rajaus on lauseen ominaisuus).
_AINA_AUKI = _dt.datetime(1970, 1, 1, tzinfo=_dt.timezone.utc)

#: Julkiset pinnat joilla lupaus voi elaa. Glob, ei kasin nimetty lista:
#: kasin nimetty lista vanhenee heti kun uusi pinta syntyy
#: (muisti: portin-sanalista-vanhenee).
SURFACE_GLOBS = ("*.html", "fpl/**/*.html", "llms.txt",
                 "web/pro-spa/src/**/*.svelte", "web/pro-spa/src/**/*.ts")

#: Lupaus tunnistetaan MERKITYKSESTA, ei yhdesta merkkijonosta: sama vaite on
#: kirjoitettu useassa sanamuodossa (muisti: sama-vaite-monessa-sanamuodossa).
#:
#: 🔴 MITATTU 12.9.2026 AAMULLA, 4 h ennen ikkunan sulkeutumista. Portti oli
#: SOKEA kolmelle lupaukselle viidesta, ja olisi tulostanut ikkunan
#: sulkeuduttua "OK: ... eika yksikaan pinta lupaa ilmaista Premiumia" samalla
#: kun goaliq.app naytti yha napin "Get Premium free" ja hintalapun
#: "Free until 12 Sept", ja goaliq.app/predictions koko lupauslauseen. Vihrea
#: portti olisi ollut todiste vaarasta asiasta.
#:
#: Kaksi eri syyta, molemmat tunnettuja vikaluokkia:
#:   (1) RIVI EI OLE SKANNAUSYKSIKKO. `predictions.html` kirjoittaa lupauksen
#:       kahdelle riville (rivi 1 "Premium is free on the web", rivi 2 "until the GW4 deadline"), joten yhtenainen kuvio ei osu. Sama katkaisu syntyy
#:       TAGISTA: `Free<span> until 12 Sept</span>`.
#:   (2) PERHE OLI VAJAA. Nappitekstit ja hintalaput ovat lupauksia siina
#:       missa lauseetkin (muisti: vaiteperhe-ei-tyhjene-greppaamalla).
#:
#: Korjaus: kuviot ajetaan LUKIJAN NAKYMAAN (tagit ja rivinvaihdot yhdeksi
#: valilyonniksi, `luettava_teksti`), eika raakaan lahteeseen.
CLAIM_RE = re.compile(
    r"(free on the web until|Premium is free until|"
    r"free until the GW4 deadline|nothing to pay for GW1|"
    r"Free until 12 Sept|Get Premium free|That is GW1 to GW3)", re.I)

#: TOINEN PERHE: paivamaaraan sidottu HINTAVAITE. Se ei lupaa ilmaista
#: Premiumia, joten CLAIM_RE ei nae sita - mutta se vanhenee tasan samalla
#: hetkella, ja menneessa se lukee oudosti ("After 12 September it is EUR3.99"
#: kun 12. syyskuuta on eilen).
#:
#: MITATTU 12.9.2026: Ville loysi tasan taman LIVENA sen jalkeen kun
#: `--live` oli sanonut 0 kohtaa. `index.html`in heron CTA-nappi oli
#: GEN-lohkossa ja vaihtui oikein 12:30, mutta hintanootti heti sen ALLA oli
#: markkerien ULKOPUOLELLA ja kovakoodattu. Osittainen GEN-kate on pahempi
#: kuin ei katetta: se saa pinnan nayttamaan hoidetulta.
#:
#: Perhe on kirjoitettu VAITTEEN MUODOSTA eika sanalistasta: "after/from/then
#: <ikkunan paivamaara>" + hinta, sekä "then EUR..." -muoto ilman paivaa.
DATED_PRICE_RE = re.compile(
    r"(?:after|from|starting)\s+(?:the\s+)?"
    r"(?:1?2(?:th)?\s+Sept(?:ember)?|Sept(?:ember)?\s+1?2(?:th)?|"
    r"the\s+GW4\s+deadline)"
    r"[^.]{0,60}?(?:&euro;|€|EUR)\s?\d"
    r"|then\s{0,3}(?:&euro;|€|EUR)\s?\d", re.I)

#: RAJAUSTARKISTUKSEN perhe on SUPPEAMPI kuin selviytymistarkistuksen, ja se
#: on tietoinen valinta eika unohdus. Rajaus ("on the web") on LAUSEEN
#: ominaisuus: nelisanaiselta napilta ei voi vaatia sivulausetta, ja jos
#: vaatisi, portti olisi punainen tanaan asiasta joka on tanaan tosi -
#: ja paivittain punainen portti tulee ohitetuksi.
SCOPED_CLAIM_RE = re.compile(
    r"(free on the web until|Premium is free until|"
    r"free until the GW4 deadline|nothing to pay for GW1)", re.I)


#: LUPAUKSEN LAAJUUS. Ilmaisikkuna koskee VAIN webia: mobiilissa Premium on
#: kaupan tilaus koko ajan. Lupaus ilman "on the web" -rajausta on siis
#: eri vaite kuin lupaus sen kanssa, ja se on epatosi puhelimessa lukevalle.
#:
#: 🔴 MITATTU 7.9.2026: `index.html`in ilmaisikkunabandi - sivun ENSIMMAINEN
#: elementti navin alla - luki *"Premium is free until the 12 September
#: deadline"* ilman rajausta, kun seitseman muuta pintaa (faq x3,
#: creators, fpl, predictions, api) sanoivat "on the web". Landing on niista
#: se jolla on eniten liikennetta.
#:
#: Vanha portti ei voinut nahda tata: se kysyy "elaako lupaus viela ikkunan
#: sulkeuduttua", ei "onko lupaus oikein rajattu". Sama vaite, kaksi eri
#: kysymysta (muisti: portti-joka-etsii-merkkijonoa-ei-mittaa-arvoa).
SCOPE_RE = re.compile(r"(on the web|web only|pro\.goaliq\.app)", re.I)

#: Rajaus saa asua enintaan taman verran merkkeja lupauksen ymparilla. Sama
#: kappale kylla, mutta ei "jossain samalla sivulla" - varaus kaukana
#: luvusta ei tavoita lukijaa (muisti: varoitus-kaukana-luvusta).
SCOPE_IKKUNA = 200


def nakyva_teksti(pala: str) -> str:
    """Poista linkkien kohteet: rajaus on luettava, ei koodissa.

    🔴 TAMA REIKA MITATTIIN MUTAATIOTESTILLA 7.9.2026, ja ilman sita koko
    rajausportti oli inertti juuri silla sivulla jota varten se kirjoitettiin.
    `index.html`in ilmaisikkunabandissa lupauksen 120 merkin paassa on
    `href="https://pro.goaliq.app/"`, joten `SCOPE_RE` osui URLiin ATTRIBUUTIN
    SISALLA ja portti oli vihrea vaikka nakyva teksti ei rajannut mitaan.
    Lukija ei lue hrefia (muisti: kaavion rajaus on NAKYVASSA tekstissa).

    Mutta tageja EI poisteta kokonaan: `faq.html`in oma rajaus asuu
    `<meta name="description" content="... free on the web until ...">`
    -attribuutissa, joka nakyy hakutuloksessa. Tagien pyyhkiminen olisi
    vaihtanut yhden vaaran positiivisen toiseen - portti olisi kaatunut
    rivilta joka on oikein. Poistetaan siis tasan se mika ei ole luettavaa:
    linkkien kohteet ja paljaat URLit.
    """
    ilman_linkkeja = re.sub(
        r"""\s(?:href|src|action|data-href)\s*=\s*(["'])[^"']*\1""",
        " ", pala, flags=re.I)
    ilman_urleja = re.sub(r"https?://\S+", " ", ilman_linkkeja)
    return re.sub(r"\s+", " ", ilman_urleja)


#: Attribuutit joiden sisalto ON lukijalle nakyvaa tekstia vaikka se asuu
#: tagin sisalla: hakutuloksen kuvaus ja jakokortin otsikko.
_ATTR_TEXT_RE = re.compile(
    r"""<[^>]*?\b(?:content|alt|aria-label|title)\s*=\s*("|')(.*?)\1[^>]*>""",
    re.I | re.S)

#: Itsestaan sulkeutuvan lohkon avoin haara (src.free_window.self_closing_block).
#: Ryhmat: avain, data-until, sisalto. Attribuuttien nimet tulevat samasta
#: moduulista joka ne kirjoittaa, jotta lukija ja kirjoittaja eivat ajaudu.
TEMPLATE_RE = re.compile(
    r"<template\s+" + re.escape(OPEN_ATTR) + r'="([^"]*)"\s+'
    + re.escape(UNTIL_ATTR) + r'="([^"]*)"\s*>(.*?)</template>',
    re.S | re.I)


def _ilman_templatea(txt: str, now=None, *, aina: bool = False) -> str:
    """Pyyhi avoimen haaran templatet valilyonneiksi (pituus sailyy, joten
    indeksikartta ja rivinumerot pysyvat suorina).

    `aina=True` on JS:TON LUKIJA: `<template>` on inertti eika koskaan
    nay. Muuten sisalto pidetaan tasan silloin kun selaimen skripti
    nayttaisi sen: `open_at(data-until, now)`. Sama predikaatti kuin
    `is_open()`, luettuna sivun OMASTA aikaleimasta - se on se mita
    selain oikeasti kayttaa, ei se mita repo nyt sanoo.
    """
    def _pyyhi(m):
        if aina or not open_at(m.group(2), now):
            return " " * len(m.group(0))
        return m.group(0)
    return TEMPLATE_RE.sub(_pyyhi, txt)


def templates(txt: str) -> list[tuple[str, str, int]]:
    """(avain, data-until, rivinumero) jokaisesta avoimesta haarasta."""
    return [(m.group(1), m.group(2), txt.count("\n", 0, m.start()) + 1)
            for m in TEMPLATE_RE.finditer(txt)]


def luettava_teksti(txt: str, now=None, *,
                    ilman_js: bool = False) -> tuple[str, list[int]]:
    """(lukijan nakyma, indeksikartta alkuperaiseen tekstiin).

    Tagit ja rivinvaihdot romahtavat YHDEKSI valilyonniksi, jolloin sama
    lupaus loytyy riippumatta siita miten se on taitettu lahteessa.
    Indeksikartta sailyttaa rivinumeron: nakymasta loytynyt osuma osataan
    raportoida siina kohdassa jossa se oikeasti on.

    Mita EI heiteta pois: `content=`, `alt=`, `aria-label=` ja `title=`
    -attribuuttien sisalto, koska se on lukijalle nakyvaa (hakutulos,
    ruudunlukija). `faq.html`in oma lupaus asuu juuri `<meta description>`issa,
    ja tagien pyyhkiminen olisi tehnyt portista sokean silla sivulla.

    `now`: hetki jolla itsestaan sulkeutuvan lohkon `<template>` arvioidaan
    (oletus: nyt). `ilman_js=True`: JS:ton lukija, template ei nay koskaan.
    """
    # 0) Itsestaan sulkeutuvan lohkon avoin haara: nakyy vain kun selain
    #    nayttaisi sen. Ennen attribuuttikasittelya, koska templaten sisalla
    #    on omia tageja (nappi, hintalappu) joiden teksti muuten vuotaisi.
    txt = _ilman_templatea(txt, now, aina=ilman_js)

    # 1) Attribuuttiteksti ulos tagista, sen omalle paikalleen.
    def _attr(m):
        sisalto = m.group(2)
        # Sama pituus kuin alkuperainen, jotta indeksikartta pysyy suorana:
        # taytetaan valilyonnilla.
        return (" " + sisalto + " ").ljust(len(m.group(0)))[:len(m.group(0))]
    esikasitelty = _ATTR_TEXT_RE.sub(_attr, txt)
    # 2) Linkkien kohteet ja paljaat URLit pois (sama syy kuin nakyva_teksti).
    esikasitelty = re.sub(
        r"""\s(?:href|src|action|data-href)\s*=\s*("|')[^"']*\1""",
        lambda m: " " * len(m.group(0)), esikasitelty, flags=re.I)

    ulos: list[str] = []
    kartta: list[int] = []
    i, n = 0, len(esikasitelty)
    while i < n:
        c = esikasitelty[i]
        if c == "<":
            j = esikasitelty.find(">", i)
            j = n - 1 if j == -1 else j
            if ulos and ulos[-1] != " ":
                ulos.append(" ")
                kartta.append(i)
            i = j + 1
            continue
        if c.isspace():
            if ulos and ulos[-1] != " ":
                ulos.append(" ")
                kartta.append(i)
            i += 1
            continue
        ulos.append(c)
        kartta.append(i)
        i += 1
    return "".join(ulos), kartta


def _osumat(txt: str, kuvio: re.Pattern, now=None,
            *, ilman_js: bool = False) -> list[tuple[int, str, int, int]]:
    """(rivinumero, osuman teksti, nakyman alku, nakyman loppu) lukijan nakymasta."""
    nakyma, kartta = luettava_teksti(txt, now, ilman_js=ilman_js)
    ulos = []
    for m in kuvio.finditer(nakyma):
        alku = kartta[m.start()] if m.start() < len(kartta) else 0
        ulos.append((txt.count(chr(10), 0, alku) + 1, m.group(0), m.start(), m.end()))
    return ulos


def scope_misses(paths=None, now=None) -> list[tuple[str, int, str]]:
    """Lupaukset joilta puuttuu web-rajaus lahietaisyydelta.

    Ajetaan LUKIJAN NAKYMAAN, jotta rivinvaihto tai tagi lupauksen keskella ei
    tee portista sokeaa (12.9.2026).

    Templaten avoin haara arvioidaan PAISTOHETKEN sijaan hetkella jolloin se
    on auki: rajaus on lauseen ominaisuus eika riipu kellosta, joten
    templaten sisalto tarkistetaan aina (`now` = templaten oma alku, ts.
    sisalto pidetaan). Muuten rajaamaton lupaus voisi elaa templatessa
    ikkunan ollessa kiinni ja avautua rajaamattomana seuraavassa ikkunassa.
    """
    ulos = []
    for p in (paths if paths is not None else surfaces()):
        try:
            txt = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if is_guarded_source(p, txt):
            continue
        # Rajaus tarkistetaan templaten sisallosta riippumatta kellosta:
        # arvioidaan "kaikki templatet auki" -hetkella.
        hetki = now if now is not None else _AINA_AUKI
        nakyma, _ = luettava_teksti(txt, hetki)
        for rivi, osuma, a0, b0 in _osumat(txt, SCOPED_CLAIM_RE, hetki):
            a = max(0, a0 - SCOPE_IKKUNA)
            b = min(len(nakyma), b0 + SCOPE_IKKUNA)
            if not SCOPE_RE.search(nakyma[a:b]):
                ulos.append((str(p.relative_to(ROOT)), rivi, osuma))
    return ulos


def surfaces() -> list[Path]:
    out: list[Path] = []
    for g in SURFACE_GLOBS:
        out.extend(sorted(ROOT.glob(g)))
    return [p for p in out if p.is_file()]


#: SPA renderoi lupauksen ehdollisesti ({#if freePremiumWindowActive()}),
#: joten sen lahdekoodissa oleva teksti EI ole vanheneva vaite. Portti greppaa
#: raakaa lahdekoodia eika nae ehtoa, joten ilman tata rajausta se antaisi
#: vaaran positiivisen 12.9 ja menisi punaiseksi tiedostoista jotka ovat
#: kunnossa - ja paivittain punainen portti tulee ohitetuksi.
GUARD_RE = re.compile(r"freePremiumWindowActive")


def is_guarded_source(path: Path, txt: str) -> bool:
    """Onko tama SPA-tiedosto joka vartioi lupauksen ajassa."""
    return path.suffix in (".svelte", ".ts") and bool(GUARD_RE.search(txt))


def hits(paths=None, now=None) -> list[tuple[str, int, str]]:
    """Elossa olevat lupaukset LUKIJAN NAKYMASTA (ei raa'asta lahteesta).

    `now` on synteettinen kello: itsestaan sulkeutuvan lohkon template
    lasketaan nakyvaksi vain jos selain nayttaisi sen talla hetkella.
    """
    found = []
    for p in (paths if paths is not None else surfaces()):
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if is_guarded_source(p, txt):
            continue
        for rivi, osuma, _a, _b in _osumat(txt, CLAIM_RE, now):
            found.append((str(p.relative_to(ROOT)), rivi, osuma))
        # Paivamaaraan sidottu hintavaite on vanhentunut VAIN kun ikkuna on
        # kiinni; auki se on tosi ja kuuluu sivulle. 12.9: tama perhe puuttui,
        # ja Ville loysi lauseen livena sen jalkeen kun portti sanoi 0.
        if not is_open(now):
            for rivi, osuma, _a, _b in _osumat(txt, DATED_PRICE_RE, now):
                found.append((str(p.relative_to(ROOT)), rivi, osuma))
    return found


#: STAATTISEN LUPAUKSEN POIKKEUSLISTA (17.9.2026, CLAUDE.md 6a mekanismi 2).
#: Pinta jolla ilmaislupaus SAA olla staattisessa HTML:ssa/tekstissa, ja
#: PERUSTELU miksi se ei voi kulkea `self_closing_block`in kautta. Tyhja
#: tanaan: 12.9:n 19 lupauksesta 9 oli kasin kirjoitettuna (faq 6, creators 1,
#: llms.txt 2) ja ne sulkeutuivat vasta ihmisen dispatchilla - se on tasan
#: se vika jota tama portti vartioi. Uusi rivi tanne kaataa
#: `tests/test_free_window_self_closing.py`:n odotuksen, joten lisays nakyy
#: diffissa perusteluineen eika synny vahingossa. Avain on repo-suhteellinen
#: polku kauttaviivoin.
STATIC_ALLOWED: dict[str, str] = {}


def static_hits(paths=None) -> list[tuple[str, int, str]]:
    """Lupaukset JS:TTOMAN lukijan nakymasta: template ei nay koskaan.

    Tama on se nakyma jonka pitaa olla tyhja riippumatta kellosta: ilman
    JavaScriptia sivu nayttaa suljetun tekstin, joten jos lupaus loytyy
    taalta, se on staattisessa HTML:ssa eika skriptin takana - eli se jaa
    roikkumaan tasan kuten 12.9.

    Myos paivamaaraan sidottu hintavaite lasketaan: se ei lupaa ilmaista,
    mutta staattisena se vanhenee samalla hetkella (12.9: heron hintanootti
    "After 12 September it is EUR3.99" jai roikkumaan GEN-markkerien
    ulkopuolelle). Kysymys on "mika jaa roikkumaan", ei "mika on tanaan
    tosi", joten kelloa ei kysyta.
    """
    found = []
    for p in (paths if paths is not None else surfaces()):
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if is_guarded_source(p, txt):
            continue
        for kuvio in (CLAIM_RE, DATED_PRICE_RE):
            for rivi, osuma, _a, _b in _osumat(txt, kuvio, ilman_js=True):
                found.append((str(p.relative_to(ROOT)), rivi, osuma))
    return found


def static_hits_outside_allowlist(paths=None) -> list[tuple[str, int, str]]:
    """Staattiset lupaukset joilla EI ole perusteltua poikkeusta."""
    return [h for h in static_hits(paths)
            if Path(h[0]).as_posix() not in STATIC_ALLOWED]


def until_mismatches(paths=None) -> list[tuple[str, int, str]]:
    """Templatet joiden `data-until` ei ole `src.free_window.FREE_PREMIUM_UNTIL`.

    Aikaleimalla on yksi lahde. Sivulle upotettu eri arvo tarkoittaisi etta
    selain sulkee ikkunan eri hetkella kuin API, SPA ja mobiili - ja
    myohempi arvo olisi lupaus jota mikaan muu pinta ei pida.
    """
    ulos = []
    for p in (paths if paths is not None else surfaces()):
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for avain, until, rivi in templates(txt):
            if until != FREE_PREMIUM_UNTIL:
                ulos.append((str(p.relative_to(ROOT)), rivi,
                             f"{avain}: data-until={until!r} != "
                             f"FREE_PREMIUM_UNTIL={FREE_PREMIUM_UNTIL!r}"))
    return ulos


def guarded_files(paths=None) -> list[str]:
    """SPA-tiedostot jotka mainitsevat lupauksen JA vartioivat sen."""
    out = []
    for p in (paths if paths is not None else surfaces()):
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if CLAIM_RE.search(txt) and is_guarded_source(p, txt):
            out.append(str(p.relative_to(ROOT)))
    return out


#: Lauseen raja. JSON-LD:ssa ja meta-attribuutissa lupaus on osa pidempaa
#: merkkijonoa, joten sita ei voi kaaria HTML-kommenttiin: ainoa turvallinen
#: primitiivi on poistaa LAUSE joka kantaa vaitteen.
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _template_rivit(text: str) -> set[int]:
    """Rivi-indeksit (0-alkuiset) jotka kuuluvat avoimen haaran templateen."""
    rivit: set[int] = set()
    for m in TEMPLATE_RE.finditer(text):
        alku = text.count("\n", 0, m.start())
        loppu = text.count("\n", 0, m.end())
        rivit.update(range(alku, loppu + 1))
    return rivit


def strip_claim(text: str) -> tuple[str, int]:
    """Poista lupauksen kantavat lauseet. Palauttaa (uusi_teksti, montako).

    Itsestaan sulkeutuvan lohkon `<template>` ohitetaan: sen sisalto on
    skriptin vartioima eika roiku, ja lausepoisto sen sisalla jattaisi
    orvon tagin. Lohkon oikea kirjoittaja on `render_blocks`.
    """
    out, poistettu = [], 0
    suojatut = _template_rivit(text)
    for i, chunk in enumerate(text.split("\n")):
        if i in suojatut or not CLAIM_RE.search(chunk):
            out.append(chunk)
            continue
        lauseet = _SENT_SPLIT.split(chunk)
        pidetyt = [l for l in lauseet if not CLAIM_RE.search(l)]
        poistettu += len(lauseet) - len(pidetyt)
        out.append(" ".join(pidetyt))
    return "\n".join(out), poistettu


#: GEN-lohkot renderoidaan JOKA ajossa, myos ikkunan ollessa auki. Silloin se
#: on no-op - ja juuri se on pointti: sivu on oikein molemmissa tiloissa eika
#: sulkeutuminen vaadi ketaan muistamaan mitaan. Yksi lukija (src.free_window)
#: paattaa sisallon, sivu vain kantaa sen.
_GEN_RE_TMPL = (r"(<!-- GEN:{key}-START[^>]*-->\n)(.*?)(\n<!-- GEN:{key}-END -->)")


def render_blocks(now=None) -> list[tuple[str, str]]:
    """Kirjoita pintakohtaiset GEN-lohkot. Palauttaa muuttuneet (tiedosto, avain).

    Kaataa ajon jos markkeria ei loydy: hiljainen ohitus tarkoittaisi etta
    lupaus jaa sivulle eika kukaan huomaa (fail-closed).
    """
    from src.free_window import SURFACE_BLOCKS
    muuttuneet = []
    for (tiedosto, avain), renderoija in SURFACE_BLOCKS.items():
        p = ROOT / tiedosto
        txt = p.read_text(encoding="utf-8")
        pat = re.compile(_GEN_RE_TMPL.format(key=re.escape(avain)), re.S)
        m = pat.search(txt)
        if not m:
            raise SystemExit(
                f"check_free_window: {tiedosto} ei sisalla GEN:{avain}-lohkoa. "
                "Ilmaisikkunan lupaus jaisi sivulle eika mikaan poistaisi sita.")
        uusi_sisalto = renderoija(now)
        if m.group(2) == uusi_sisalto:
            continue
        txt = txt[:m.start()] + m.group(1) + uusi_sisalto + m.group(3) + txt[m.end():]
        p.write_text(txt, encoding="utf-8")
        muuttuneet.append((tiedosto, avain))
    return muuttuneet


#: Generoidut pinnat joita `--fix` EI saa koskea: niiden lupaus katoaa
#: seuraavassa bakessa oikein muotoiltuna, ja lausepoisto jattaisi niihin
#: orvon tagin. Poikkeuslistassa on perustelu, ja testi kaatuu jos uusi
#: tiedosto lisataan tanne ilman sellaista (CLAUDE.md 6a, mekanismi 2).
FIX_OHITETAAN = {
    "fpl.html": "build_fpl_page.free_window_block() renderoi lohkon "
                "self_closing_block():lla joka bakessa (suljettu teksti "
                "staattisena, avoin <template>+skriptin takana). Sivu "
                "sulkeutuu selaimen kellolla; lausepoisto jattaisi "
                "<b></b>-orvon eika sita tarvita.",
}


#: `--fix` EI SAA KOSKEA LAHDEKOODIIN. Lausepoisto on tekstiprimitiivi: se
#: osaa poistaa lauseen kappaleesta, mutta koodissa lause on merkkijonoliteraali
#: jonka poisto jattaa syntaksivirheen.
#:
#: 🔴 MITATTU 12.9.2026 synteettisella kellolla ennen kuin tama paasi CI:hin:
#: laajennettu CLAIM_RE osui `Hero.svelte`in riviin
#: `? 'Premium, free until 12 September'`, ja `--fix` jatti tilalle `?` ilman
#: haaraa - SPA:n kaannos olisi kaatunut ensimmaisessa page-refresh-ajossa
#: ikkunan sulkeuduttua. Vanha, suppeampi kuvio ei osunut siihen, joten riski
#: syntyi tasan tassa muutoksessa.
#:
#: Lahdekoodi RAPORTOIDAAN silti (`hits`), koska vanhentunut lupaus koodissa on
#: yha vanhentunut lupaus - se vain korjataan kasin.
FIX_EI_LAHDEKOODIA = (".svelte", ".ts", ".js", ".py")


def fix(paths=None, now=None) -> list[tuple[str, int]]:
    """Siivoa lupaus kasin yllapidetyilta pinnoilta.

    Kaksi vaihetta:
      1. GEN-lohkot renderoidaan AINA (myos ikkunan ollessa auki, jolloin
         no-op). Nain rakenteelliset lupaukset - bandi, nappi, hintalappu -
         vaihtuvat oikeaan sisaltoon eivatka katoa tyhjaan.
      2. Lausepoisto muilta kasin yllapidetyilta TEKSTIPINNOILTA vain ikkunan
         sulkeuduttua. Generoidut sivut (`FIX_OHITETAAN`) ja lahdekoodi
         (`FIX_EI_LAHDEKOODIA`) ohitetaan.

    Kutsutaan sivubuildista, joten ensimmainen ajo 12.9 12:30 UTC jalkeen
    siivoaa tiedostot itse eika siivous jaa kenenkaan muistin varaan.
    """
    muutetut: list[tuple[str, int]] = []
    # GEN-lohkot vain TUOTANTOPOLULLA (paths is None). Kun kutsuja antaa
    # eksplisiittisen listan, se tarkoittaa "tasan nama" - yksikkotesti antaa
    # yhden tmp-tiedoston, eika silla ole index.htmlia ymparillaan.
    if paths is None:
        for tiedosto, avain in render_blocks(now):
            muutetut.append((f"{tiedosto} (GEN:{avain})", 1))
    if is_open(now):
        return muutetut
    for p in (paths if paths is not None else surfaces()):
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        if rel in FIX_OHITETAAN or p.suffix in FIX_EI_LAHDEKOODIA:
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if is_guarded_source(p, txt) or not CLAIM_RE.search(txt):
            continue
        uusi, n = strip_claim(txt)
        if n:
            # 🔴 LEIMA SAMASSA KIRJOITUKSESSA (12.9.2026). Ilman tata rivia
            # tama funktio muuttaa sivun nakyvaa copyta ja jattaa sen
            # tuoreusleiman jalkeen: `faq.html`in `data-copy-hash` oli
            # `834e4eca8357` kun sisalto sanoi `6a25db3a1dbb`, ja
            # `tests/test_faq_freshness.py` punastui vaikka kukaan ei ollut
            # koskenut sivuun. Portti oli oikeassa — se vain oletti
            # tekijaksi ihmisen. Leima on osa copya, joten sen paivittaminen
            # kuuluu samaan kirjoitukseen kuin copyn muutos.
            from src.copy_stamp import paivita_leima
            uusi, _leima = paivita_leima(uusi, now=now)
            p.write_text(uusi, encoding="utf-8")
            muutetut.append((rel, n))
    return muutetut


#: LIVE-PINNAT. Repotarkistus kertoo mita AIOMME servata; tama kertoo mita
#: oikeasti servataan. Ne eivat ole sama asia: bottikommitti ei kaynnista
#: hub-deployta, ja CF Pages on direct upload (muisti:
#: botin-push-ei-kaynnista-workflowta, deployn-ehto-on-mittaus).
#:
#: Sivut ovat tasan ne joilla lupaus elaa kasin yllapidettyna.
LIVE_URLS = (
    "https://goaliq.app/",
    "https://goaliq.app/fpl",
    "https://goaliq.app/predictions",
    "https://goaliq.app/faq.html",
    "https://goaliq.app/creators",
    "https://goaliq.app/llms.txt",
)


def live_hits(urls=None, timeout: int = 20, now=None) -> tuple[list, list]:
    """(osumat, virheet). Osuma = (url, rivinumero, teksti) lukijan nakymasta.

    Hakuvirhe EI ole tyhja tulos: se palautetaan erikseen, jotta portti voi
    olla fail-closed (muisti: nolla-ei-ole-sama-kuin-ei-tietoa).

    Itsestaan sulkeutuvan lohkon template arvioidaan sivun OMASTA
    `data-until`-arvosta (`luettava_teksti`): se on se mita lukijan selain
    kayttaa. Paistettu sivu joka kantaa mennytta aikaleimaa ei siis lupaa
    mitaan, vaikka sita ei olisi paistettu uudelleen sulkeutumisen jalkeen -
    ja se on koko mekanismin pointti. Osuma raportoidaan myos silloin kun
    sivun aikaleima on myohempi kuin repon: silloin selain nayttaa lupauksen
    jota mikaan muu pinta ei enaa pida.
    """
    import urllib.error
    import urllib.request
    # Oletus luetaan KUTSUHETKELLA eika maarittelyhetkella, jotta lista on
    # yhdessa paikassa ja testi voi vaihtaa sen.
    urls = LIVE_URLS if urls is None else urls
    osumat, virheet = [], []
    for url in urls:
        try:
            pyynto = urllib.request.Request(
                url, headers={"User-Agent": "GoalIQ-FreeWindowCheck/1.0"})
            with urllib.request.urlopen(pyynto, timeout=timeout) as r:
                txt = r.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError, ValueError) as e:
            virheet.append((url, str(e)[:120]))
            continue
        for rivi, teksti, _a, _b in _osumat(txt, CLAIM_RE, now):
            osumat.append((url, rivi, teksti))
        for avain, until, rivi in templates(txt):
            if until != FREE_PREMIUM_UNTIL:
                # Ei FAIL sinallaan (lupaus on jo osuma jos se nakyy), mutta
                # operaattorin on nahtava etta sivu ja lahde ovat eri mielta.
                osumat.append((url, rivi,
                               f"HUOM {avain}: sivun data-until={until!r}, "
                               f"lahde {FREE_PREMIUM_UNTIL!r}"
                               if open_at(until, now) else
                               f"(info) {avain}: sivun data-until={until!r} "
                               f"on mennyt, lahde {FREE_PREMIUM_UNTIL!r}"))
    return osumat, virheet


def main_live(timeout: int = 20, now=None) -> int:
    """`--live`: elaako lupaus julkisilla sivuilla JUURI NYT."""
    osumat, virheet = live_hits(timeout=timeout, now=now)
    if virheet:
        print("FAIL: sivua ei saatu haettua - porttia ei voi todentaa "
              "(fail-closed):")
        for url, err in virheet:
            print(f"     {url}  {err}")
        return 1
    # Pelkka info-rivi (sivun mennyt aikaleima eroaa lahteesta) ei ole
    # lupaus: se tulostetaan mutta ei kaada.
    infot = [o for o in osumat if o[2].startswith("(info)")]
    osumat = [o for o in osumat if not o[2].startswith("(info)")]
    for url, rivi, teksti in infot:
        print(f"     {url}:{rivi}  {teksti}")
    if is_open(now):
        print(f"OK: ilmaisikkuna on auki {day_label()} asti. Lupaus elaa "
              f"livena {len(osumat)} kohdassa "
              f"{len({u for u, _, _ in osumat})} sivulla:")
        for url, rivi, teksti in osumat:
            print(f"     {url}:{rivi}  {teksti!r}")
        return 0
    if not osumat:
        print(f"OK: ilmaisikkuna on kiinni ({day_label()} mennyt) eika "
              f"yksikaan LIVE-sivu lupaa ilmaista Premiumia.")
        return 0
    print(f"FAIL: ikkuna sulkeutui {day_label()}, mutta lupaus elaa yha "
          f"livena {len(osumat)} kohdassa:")
    for url, rivi, teksti in osumat:
        print(f"     {url}:{rivi}  {teksti!r}")
    print("     Lupaus on STAATTISESSA HTML:ssa tai templaten aikaleima on "
          "myohempi kuin lahteen. Itsestaan sulkeutuva lohko ei tuota tata; "
          "etsi kasin kirjoitettu lupaus ja aja `--fix` + page-refresh.")
    return 1


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--live" in argv:
        return main_live()
    if "--fix" in argv:
        muutetut = fix()
        if not muutetut:
            print("fix: ei muutettavaa (ikkuna auki tai pinnat jo puhtaat).")
            return 0
        for f, n in muutetut:
            print(f"fix: {f} - {n} lupauslausetta poistettu")
        return 0
    paths = surfaces()
    if not paths:
        print("FAIL: yhtaan julkista pintaa ei loytynyt - porttia ei voi "
              "todentaa (fail-closed).")
        return 1
    found = hits(paths)
    # RAJAUSTARKISTUS AJETAAN AINA, myos ikkunan ollessa auki. Vaarin rajattu
    # lupaus on epatosi juuri silloin kun ikkuna on auki, ei sen jalkeen.
    puuttuva_rajaus = scope_misses(paths)
    if puuttuva_rajaus:
        print("FAIL: ilmaisikkunan lupaus ilman 'on the web' -rajausta. "
              "Ikkuna koskee vain webia; mobiilissa Premium on kaupan tilaus.")
        for f, ln, teksti in puuttuva_rajaus:
            print(f"     {f}:{ln}  {teksti!r}")
        return 1
    # AIKALEIMALLA ON YKSI LAHDE. Sivulle upotettu eri `data-until` sulkisi
    # ikkunan eri hetkella kuin API, SPA ja mobiili.
    eri_leima = until_mismatches(paths)
    if eri_leima:
        print("FAIL: itsestaan sulkeutuvan lohkon aikaleima eroaa lahteesta "
              "(src.free_window.FREE_PREMIUM_UNTIL). Renderoi lohko uudelleen "
              "(`--fix`), ala kirjoita aikaleimaa sivulle kasin.")
        for f, ln, teksti in eri_leima:
            print(f"     {f}:{ln}  {teksti}")
        return 1
    if is_open():
        # 🔴 STAATTINEN LUPAUS ON SE VIKA (17.9.2026, ILMAISIKKUNA-SULKEUTUU-ITSE).
        # Lupaus staattisessa HTML:ssa sulkeutuu vasta kun joku ajaa `--fix`in
        # JA sivun paiston JA deployn. 12.9 se oli ihmisen dispatch, ja ilman
        # sita 9 kasin kirjoitettua lupausta kolmella sivulla olisi elanyt
        # 2,5 h yli deadlinen. Itsestaan sulkeutuva lohko ei tuota staattista
        # lupausta, joten sellainen kaataa portin JO IKKUNAN OLLESSA AUKI:
        # silloin kirjoittaja on paikalla ja korjaa; sulkeutumisen jalkeen
        # kukaan ei ole. Poikkeus vain STATIC_ALLOWED-listalla perusteluineen.
        staattiset = static_hits_outside_allowlist(paths)
        if staattiset:
            print("FAIL: ilmaisikkunan lupaus on STAATTISESSA HTML:ssa ikkunan "
                  "ollessa auki. Se sulkeutuu vain ihmisen ajamalla sivuajolla "
                  "(12.9: 2,5 h yli deadlinen ilman dispatchia). Renderoi lupaus "
                  "`src.free_window.self_closing_block`illa, tai lisaa pinta "
                  "STATIC_ALLOWED-listalle perusteluineen.")
            for f, ln, teksti in staattiset:
                print(f"     STAATTINEN {f}:{ln}  {teksti!r}")
            return 1
        print(f"OK: ilmaisikkuna on auki {day_label()} asti. "
              f"Lupaus elaa {len(found)} kohdassa {len({f[0] for f in found})} "
              f"tiedostossa, kaikki itsestaan sulkeutuvassa lohkossa "
              f"(selain sulkee deadlinella):")
        for f, ln, _ in found:
            print(f"     {f}:{ln}")
        g = guarded_files(paths)
        if g:
            print(f"     lisaksi {len(g)} SPA-tiedostoa mainitsee lupauksen "
                  f"mutta VARTIOI sen ajassa: {', '.join(g)}")
        sallitut = static_hits(paths)
        if sallitut:
            print(f"     ja {len(sallitut)} staattista lupausta "
                  f"STATIC_ALLOWED-poikkeuksella:")
            for f, ln, _ in sallitut:
                print(f"     STAATTINEN (poikkeus) {f}:{ln}")
        return 0
    if not found:
        print(f"OK: ilmaisikkuna on kiinni ({day_label()} mennyt) eika "
              f"yksikaan pinta lupaa ilmaista Premiumia.")
        return 0
    for f, ln, txt in found:
        print(f"FAIL: {f}:{ln} lupaa yha ilmaista Premiumia ({txt!r}), "
              f"mutta ikkuna sulkeutui {day_label()}.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
