# -*- coding: utf-8 -*-
"""KIELIPORTTI: suomea ei shipata julkisille englanninkielisille sivuille.

TAMA PORTTI ON OLLUT SOKEA KOLMESTI, joka kerta samasta syysta: mittari
oli kapeampi kuin pinta.

  1. Sanalista (["kortti","rajaus","lukee","eika",...]). Yksikaan ei
     esiintynyt riveilla jotka oikeasti shippasivat. Portti vihrea, suomi ulos.
  2. Morfologia ilman -ssa-paatetta (mukana vain ssaan/staan). Rivi
     "// tekstina. Sama sopimus kuin SPA:ssa." meni lapi ja shippasi NELJALLE
     julkiselle sivulle portin ollessa vihrea.
  3. (27.8) Portti luki vain rivit jotka ALKAVAT `//`, `/*` tai `*`, ja vain
     fpl/-sivut. Se ei nahnyt: HTML-kommentteja, CSS-kommentteja, perassa
     olevia kommentteja (`x=1; // suomea`), JS-merkkijonoja, nakyvaa tekstia,
     eika juurisivuja lainkaan. Mitattu 27.8: 40 suomenkielista rivia
     yhdeksalla juurisivulla (career 8, reset-password 8, predictions 8,
     index 5, ...) portin ollessa vihrea.

Mittari on KAKSIPORTAINEN, koska pelkka sijapaate on liian heikko yksin:
"Villa", "Costa", "Marseille" ja "delta" paattyvat suomen sijapaatteisiin.

  VAHVA   skandi tai suomen funktiosana        -> yksi riittaa
  HEIKKO  sijapaate PIENELLA alkukirjaimella   -> kaksi ERI sanaa samalla rivilla

Poikkeus (27.8): NAKYVASSA tekstissa ja JS-merkkijonoissa skandi yksin EI
ole signaali, koska pelaajien nimet (Gyökeres, Guéhi, Šeško) ovat siella
oikein. Niissa vaaditaan funktiosana, verbipaate tai kaksi heikkoa.

SAANTO: jokainen muutos mittariin on istutettava molempiin kontrolleihin,
ja jokaiselle LUOKALLE on oma istutus. Ilman istutusta et tieda korjasitko
reian vai listan.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FPL_SIVUT = ["points", "expected-points", "xg-leaders", "stats", "defence",
             "defcon", "differentials", "price-changes", "team-news",
             "best-captain", "club-best", "minutes-accuracy", "model-xi",
             "notes", "predicted-lineups"]

# 🔴 VERBIPAATTEET OVAT VAHVOJA, EIVAT HEIKKOJA. Kolmas versio siirsi
# ttaa/taan/tiin heikoiksi ja portti muuttui HEIKOMMAKSI kuin edellinen:
# 15/20 realistisesta suomenkielisesta rivista meni lapi.
_FUNKTIOSANAT = (
    r"\b(?:eika|vaan|jotta|koska|mutta|silla|joten|vaikka|ilman|jokainen"
    r"|olisi|oli|onko|nayttaa|lukee|kertoo|antaa|tekee|tulee|pitaa|asettaa"
    r"|kuin|sama|samat|tama|tuo|nama|siksi|nyt|vain|myos|viela|enaa"
    r"|tekstina|sopimus|rivi|rivit|sivu|arvo|luku|kesken|taulukosta|tasan"
    r"|nolla|vaite|ettei|jottei|han|lukuja|loytyi|vasta|yksi|kaksi|kortti|kortin"
    r"|taulukko|nappi|kentta|jos|ei|jotka|joka|tila|tausta|siivoa|tunnista"
    r"|uudelle|jaettu|vanhentunut|kosmetiikkaa|konventio|sailyvat)\b"
    # Verbipaatteet: naita ei esiinny englannin sanan lopussa.
    r"|\b\w*(?:ttaa|ttaisi|taan|tiin|isesti|vat|isivat)\b"
)
_SKANDI = r"[äöÄÖ]"
_VAHVA = re.compile(_SKANDI + "|" + _FUNKTIOSANAT, re.IGNORECASE)
_VAHVA_ILMAN_SKANDIA = re.compile(_FUNKTIOSANAT, re.IGNORECASE)

# Sijapaatteet PIENELLA alkukirjaimella: isolla alkava on erisnimi
# ("Villa", "Costa", "Marseille"), joten se ei kelpaa signaaliksi.
_HEIKKO = re.compile(
    r"\b[a-z]\w*(?:ksessa|ssaan|staan|ssa|lla|lta|lle|sta|ksi|ista|isiin|iden)\b")

# Luokat joissa skandi yksin ei riita (pelaajanimet ovat oikein).
NIMILUOKAT = {"visible_text", "js_string"}


def _suomea(rivi: str, luokka: str = "js_line_comment") -> str | None:
    """Osuma jos rivi on suomea, muuten None."""
    vahva = _VAHVA_ILMAN_SKANDIA if luokka in NIMILUOKAT else _VAHVA
    m = vahva.search(rivi)
    if m:
        return m.group(0)
    heikot = _HEIKKO.findall(rivi)
    # 27.8: kaksi ERI sanaa. "villa + villa" (Aston Villa kahdesti rivilla)
    # ja "celta + lille" olivat vaaria positiiveja; jalkimmainen poistuu
    # kun attribuutit (href/slug) eivat ole skannattavaa tekstia.
    eri = []
    for h in heikot:
        if h.lower() not in [e.lower() for e in eri]:
            eri.append(h)
    return " + ".join(eri[:2]) if len(eri) >= 2 else None


def _segmentit(html: str):
    """(luokka, teksti) -pareja: HTML-kommentit, CSS-kommentit, JS-lohko- ja
    rivikommentit (myos perassa olevat), JS-merkkijonot ja nakyva teksti.
    Attribuutit (href, class, src) EIVAT ole tekstia: slugit ("aston-villa",
    "celta") eivat saa laukaista heikkoa signaalia."""
    for m in re.finditer(r"<!--(.*?)-->", html, re.S):
        yield ("html_comment", m.group(1))
    for m in re.finditer(r"<style\b[^>]*>(.*?)</style>", html, re.S | re.I):
        for c in re.finditer(r"/\*(.*?)\*/", m.group(1), re.S):
            yield ("css_comment", c.group(1))
    for m in re.finditer(r"<script\b([^>]*)>(.*?)</script>", html, re.S | re.I):
        if re.search(r"application/(ld\+)?json", m.group(1), re.I):
            continue  # data, ei koodia eika copya
        js = m.group(2)
        for c in re.finditer(r"/\*(.*?)\*/", js, re.S):
            yield ("js_block_comment", c.group(1))
        for line in js.splitlines():
            mm = re.search(r"(?<![:\w/'\"])//(.*)$", line)
            if mm:
                yield ("js_line_comment", mm.group(1))
        for s in re.finditer(
                r"'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"|`((?:[^`\\]|\\.)*)`",
                js, re.S):
            txt = s.group(1) or s.group(2) or s.group(3) or ""
            if len(txt) >= 12:
                yield ("js_string", txt)
    body = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    body = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    for line in body.splitlines():
        t = " ".join(line.split())
        if t:
            yield ("visible_text", t)


def _osumat(html: str) -> list[tuple[str, str, str]]:
    out = []
    for luokka, seg in _segmentit(html):
        for rivi in seg.splitlines():
            t = rivi.strip()
            if not t:
                continue
            m = _suomea(t, luokka)
            if m:
                out.append((luokka, m, t[:90]))
    return out


def _kommenttirivit(html: str) -> list[str]:
    """Vanha API (rivit jotka alkavat //, /* tai *). Sailytetty muille
    testeille; itse portti kayttaa _segmentit()-jakoa."""
    out = []
    for rivi in html.split(chr(10)):
        t = rivi.strip()
        if t.startswith("//") or t.startswith("/*") or t.startswith("*"):
            out.append(t)
    return out


def _julkiset_sivut() -> list[Path]:
    sivut = [ROOT / "fpl" / f"{n}.html" for n in FPL_SIVUT]
    sivut += sorted(ROOT.glob("*.html"))
    sivut.append(ROOT / "web" / "pro-spa" / "src" / "app.html")
    return [p for p in sivut if p.exists()]


@pytest.mark.parametrize("sivu", [p.name for p in _julkiset_sivut()])
def test_no_finnish_on_public_pages(sivu):
    """Jokainen julkinen sivu, jokainen luokka."""
    matches = [p for p in _julkiset_sivut() if p.name == sivu]
    for p in matches:
        html = p.read_text(encoding="utf-8", errors="replace")
        osumat = _osumat(html)
        assert not osumat, (
            f"{p.relative_to(ROOT)}: suomea julkisella sivulla: "
            + "; ".join(f"[{l}] {m!r}: {t!r}" for l, m, t in osumat[:6]))


def test_gate_catches_planted_finnish_per_class():
    """Negatiivinen kontrolli PER LUOKKA. Jokainen istutus on oikeasti
    shipannut (27.8 mittaus) tai lapaissyt jonkin aiemman version."""
    html = """<html><head>
<!-- Ref-silta myos taalla: luojan linkki voi osoittaa vanhentuneeseen -->
<style>/* teal TEKSTINÄ vaalealla pohjalla: syvennetty sävy */
.a{color:red} /* 26.7 CLASSIC: magentatayttö -> gold outline, sama konventio kuin */</style>
</head><body>
<p>Tama rivi kertoo mika sarake on lajiteltu</p>
<script>
var x = 1; // Tunnista recovery-session. Supabase tukee kahta linkkityyppiä:
}).catch(function () { /* trust-rivi jaa yleiseksi */ });
btn.textContent = 'Ei jaettavaa viela, kortti puuttuu';
// tekstina. Sama sopimus kuin SPA:ssa.
</script></body></html>"""
    luokat = {l for l, _, _ in _osumat(html)}
    for odotettu in ("html_comment", "css_comment", "visible_text",
                     "js_line_comment", "js_block_comment", "js_string"):
        assert odotettu in luokat, f"portti ei nae luokkaa {odotettu}"


def test_gate_catches_planted_finnish():
    """Rivitason istutukset aiemmista versioista (ala poista)."""
    istutetut = [
        "// nolla olisi vaite ettei han laukonut kertaakaan.",
        "// lukuja GW-otsikon alla, loytyi vasta livesivulta",
        "// tekstina. Sama sopimus kuin SPA:ssa.",
        "// Tasan yksi spec per sivu. Kahdella taulukolla querySelector ottaisi",
        "// sama kuin ennen",
        "// tama on kesken",
        "// kortti lukee taulukosta",
        "// tama rivi kertoo mika sarake on lajiteltu",
        "// jokainen kortti nayttaa saman rajauksen",
        "// haetaan listalta ja kirjoitetaan tiedostoon",
        "// palauttaa null jos dataa ei ole",
        "// kortin rivit tulevat palvelimelta",
        "// huom: FPL:n API palauttaa nollan",
        "// yksi kortti per taulukko",
        # 27.8: juurisivuilta shipanneet
        "Siivoa session jottei selaimeen jää recovery-token roikkumaan",
        "Implicit-flow: detectSessionInUrl asettaa session hashista.",
        "coral-teksti vaalealla: syvennetty (AA 4.8:1 kermalla)",
        "Tila: lomake uudelle salasanalle",
    ]
    for rivi in istutetut:
        assert _suomea(rivi), f"portti ei nae istutettua suomea: {rivi!r}"


def test_gate_does_not_flag_english():
    """Vaara positiivinen olisi yhta paha: portti hylkaisi kelvollisen rivin."""
    englanti = [
        "// null = the player was not matched to shot data.",
        "// The card must not fail on a missing asset: draw the wordmark.",
        "// Mins and Starts are windowable: without raw() they showed season",
        "// The price picker's default is the upper bound (99), not a filter.",
        "// Each window names its own season: different sources.",
        "// Same rule as on the server: goalkeepers out by default.",
        "// Aston Villa and Crystal Palace kits share a base shape.",
        "// delta is the gap to the model, not a rank change",
        "// Costa plays for Wolves now",
        "// Exactly one spec per page. With two tables querySelector would",
        # 27.8: samaa sanaa kahdesti ei ole kaksi heikkoa signaalia
        "villa: Aston Villa fixture list, villa again",
    ]
    for rivi in englanti:
        osuma = _suomea(rivi)
        assert not osuma, f"portti hylkasi englannin ({osuma!r}): {rivi!r}"
    # Nakyva teksti ja JS-merkkijonot: pelaajanimet skandeilla ovat oikein.
    for rivi in ("Gyökeres #17 · ARS · 0.40 xG", "Guéhi leads at 5.19 xP",
                 "Šeško FWD MUN 7.0", "Kroupi.Jr and Ndiaye start"):
        for luokka in ("visible_text", "js_string"):
            assert not _suomea(rivi, luokka), f"nimi hylattiin: {rivi!r}"
    # ...mutta kommentissa skandi on yha vahva signaali.
    assert _suomea("// Linkki sisälsi virheen", "js_line_comment")


def test_attributes_are_not_scanned():
    """Slugit ja href:t eivat ole tekstia: 'celta' + 'lille' samassa
    taulukkorivissa oli vaara positiivi 27.8."""
    html = ('<table><tr><td><a href="/predictions/celta-vs-lille" class="lille">'
            'Celta v Lille</a></td></tr></table>')
    assert not _osumat(html)
