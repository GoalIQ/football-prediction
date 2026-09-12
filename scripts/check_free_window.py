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

Kaytto:
    python scripts/check_free_window.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.free_window import day_label, is_open  # noqa: E402

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


def luettava_teksti(txt: str) -> tuple[str, list[int]]:
    """(lukijan nakyma, indeksikartta alkuperaiseen tekstiin).

    Tagit ja rivinvaihdot romahtavat YHDEKSI valilyonniksi, jolloin sama
    lupaus loytyy riippumatta siita miten se on taitettu lahteessa.
    Indeksikartta sailyttaa rivinumeron: nakymasta loytynyt osuma osataan
    raportoida siina kohdassa jossa se oikeasti on.

    Mita EI heiteta pois: `content=`, `alt=`, `aria-label=` ja `title=`
    -attribuuttien sisalto, koska se on lukijalle nakyvaa (hakutulos,
    ruudunlukija). `faq.html`in oma lupaus asuu juuri `<meta description>`issa,
    ja tagien pyyhkiminen olisi tehnyt portista sokean silla sivulla.
    """
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


def _osumat(txt: str, kuvio: re.Pattern) -> list[tuple[int, str, int, int]]:
    """(rivinumero, osuman teksti, nakyman alku, nakyman loppu) lukijan nakymasta."""
    nakyma, kartta = luettava_teksti(txt)
    ulos = []
    for m in kuvio.finditer(nakyma):
        alku = kartta[m.start()] if m.start() < len(kartta) else 0
        ulos.append((txt.count(chr(10), 0, alku) + 1, m.group(0), m.start(), m.end()))
    return ulos


def scope_misses(paths=None) -> list[tuple[str, int, str]]:
    """Lupaukset joilta puuttuu web-rajaus lahietaisyydelta.

    Ajetaan LUKIJAN NAKYMAAN, jotta rivinvaihto tai tagi lupauksen keskella ei
    tee portista sokeaa (12.9.2026).
    """
    ulos = []
    for p in (paths if paths is not None else surfaces()):
        try:
            txt = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if is_guarded_source(p, txt):
            continue
        nakyma, _ = luettava_teksti(txt)
        for rivi, osuma, a0, b0 in _osumat(txt, SCOPED_CLAIM_RE):
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


def hits(paths=None) -> list[tuple[str, int, str]]:
    """Elossa olevat lupaukset LUKIJAN NAKYMASTA (ei raa'asta lahteesta)."""
    found = []
    for p in (paths if paths is not None else surfaces()):
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if is_guarded_source(p, txt):
            continue
        for rivi, osuma, _a, _b in _osumat(txt, CLAIM_RE):
            found.append((str(p.relative_to(ROOT)), rivi, osuma))
    return found


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


def strip_claim(text: str) -> tuple[str, int]:
    """Poista lupauksen kantavat lauseet. Palauttaa (uusi_teksti, montako)."""
    out, poistettu = [], 0
    for chunk in text.split("\n"):
        if not CLAIM_RE.search(chunk):
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
    "fpl.html": "build_fpl_page.upsell_block() renderoi molemmat tilat itse "
                "(auki: nootti + 'Get Premium free'; kiinni: 'Get Premium' + "
                "hinta preesensissa). Lausepoisto jattaisi <b></b>-orvon.",
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
            p.write_text(uusi, encoding="utf-8")
            muutetut.append((rel, n))
    return muutetut


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
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
    if is_open():
        print(f"OK: ilmaisikkuna on auki {day_label()} asti. "
              f"Lupaus elaa {len(found)} kohdassa {len({f[0] for f in found})} "
              f"tiedostossa:")
        for f, ln, _ in found:
            print(f"     {f}:{ln}")
        g = guarded_files(paths)
        if g:
            print(f"     lisaksi {len(g)} SPA-tiedostoa mainitsee lupauksen "
                  f"mutta VARTIOI sen ajassa: {', '.join(g)}")
        print("     (generoidut ja vartioidut pinnat siivoutuvat itse; kasin "
              "yllapidetyt eivat - aja `--fix` tai portti kaatuu 12.9)")
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
