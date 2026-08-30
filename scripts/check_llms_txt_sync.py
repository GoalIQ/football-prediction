#!/usr/bin/env python
"""LLMS-TXT-SYNC-PORTTI: jokainen /fpl-sivun sisaltolohko on kuvattava llms.txt:ssa.

TAUSTA (29.8.2026): llms.txt kuvasi /fpl-sivua yha pelkalla lauseella "clean
sheet probability and fixture difficulty", vaikka sivulle oli 28.-29.8 lisatty
gw-calls-loki, EO-by-tier ja xP-tarkkuuslohko. Tama on tunnettu sokea piste:
copy-sync-tarkistukset kaydaan sivuilta ja SPA:sta, ja llms.txt jaa valiin
koska se ei nayta sivulta. Sama unohdus on toistunut aiemminkin.

MIKSI ANKKURI EIKA SANALISTA: sanalistaportti vanhenee (uusi lohko keksii uudet
sanat, portti pysyy vihreana) ja substring-osuma on sokea. Tama portti vertaa
generoidun fpl.html:n ANKKURI-ID:ita llms.txt:n syvalinkkeihin
(https://goaliq.app/fpl#<ankkuri>). Uusi lohko tuo uuden ankkurin, ja portti
kaatuu kunnes joku joko kuvaa sen llms.txt:ssa tai lisaa sen alla olevaan
EXEMPT-listaan perusteluineen. Fail-closed: uusi lohko ei voi liukua ohi
hiljaisuudella.

Kaytto:
    python -m scripts.check_llms_txt_sync
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "fpl.html"
LLMS = ROOT / "llms.txt"

#: Ankkurit joita EI vaadita llms.txt:hen, jokainen perusteluineen. Lisays
#: tanne on tietoinen paatos, ei oletus.
EXEMPT: dict[str, str] = {
    "about": "yritysesittely, ei sivun omaa sisaltoa",
    "faq": "toistaa muiden lohkojen vaitteet, ei uutta dataa",
    "methodology": "kuvattu llms.txt:n omassa metodologia-osiossa",
    "creators": "yhteydenottokehote, ei dataa",
    "tools": "linkkilista muihin sivuihin jotka llms.txt kuvaa erikseen",
    "pro": "Premium-myyntilohko, ei ilmaispinnan dataa",
    "elite-transfers": "eo-by-tier-lohkon alaotsikko, kuvataan samassa rivissa",
}

ANCHOR_RE = re.compile(r'id="([a-z0-9][a-z0-9-]*)"')
LINK_RE = re.compile(r"goaliq\.app/fpl#([a-z0-9][a-z0-9-]*)")

#: ALASIVUJEN syvalinkit, esim. goaliq.app/fpl/expected-points#gw-xp.
#: 🔴 30.8: lukuvahti luki VAIN fpl.html:aa, joten alasivun ankkuriin
#: osoittava rivi ohitettiin aanettomasti (`block_text` palautti tyhjan ->
#: `continue`). Se on sama sokea piste kuin koko portin syntysyy, vain
#: yhta tasoa syvemmalla: uusi ilmaispinta sai luvata luvun jota mikaan
#: ei tarkista. Nyt jokainen alasivurivi mitataan SEN sivun lohkosta.
SUB_LINK_RE = re.compile(r"goaliq\.app/(fpl/[a-z0-9][a-z0-9/-]*)#([a-z0-9][a-z0-9-]*)")


def page_anchors(html: str) -> set[str]:
    return set(ANCHOR_RE.findall(html))


def llms_anchors(text: str) -> set[str]:
    return set(LINK_RE.findall(text))


def missing_anchors(html: str, llms: str, exempt: dict[str, str] | None = None) -> list[str]:
    """Ankkurit jotka sivulla on mutta joita llms.txt ei kuvaa."""
    ex = EXEMPT if exempt is None else exempt
    return sorted(page_anchors(html) - llms_anchors(llms) - set(ex))


def stale_anchors(html: str, llms: str) -> list[str]:
    """llms.txt:n syvalinkit jotka eivat enaa osoita mihinkaan sivulla.

    Sama vikaluokka toiseen suuntaan: lohko poistetaan sivulta, llms.txt jaa
    lupaamaan sita LLM-lukijoille.
    """
    return sorted(llms_anchors(llms) - page_anchors(html))


# ---------------------------------------------------------------------------
# VAITEPORTTI (30.8.2026, LLMS-SYNC-CLAIM-GATE)
#
# Ankkuriportti yllä mittaa etta lohko on KUVATTU. Se ei mittaa etta kuvaus on
# TOSI. 29.8 julkaisutarkistaja loysi llms.txt:n /fpl-osiosta viisi vikaa
# (liioiteltu gradauskattavuus, sivun oman varauksen vastainen parafraasi,
# vanheneva luku "all 20 teams", "logged and scored" ilman yhtaan gradattua
# rivia, kielletty "rather than") ja KAIKKI menivat ankkuriportin lapi
# vihreana. Portti mittasi eri asiaa kuin se vaitti mittaavansa.
#
# Tama osa vertaa syvalinkkirivin LUKUJA sivun vastaavaan lohkoon.

#: Luvut 1-9 ovat proosaa ("1 to 5", "three free"), eivat dataväitteitä.
#: Portti katsoo lukuja jotka lukija lukisi mittaustuloksena: >= 10, tai
#: desimaaliluku, tai prosentti.
CLAIM_NUM_RE = re.compile(r"\b(\d+\.\d+|\d{2,})\s*%?")

#: Sanat joiden kayttö on aiemmin hylätty portissa. Lista vanhenee (muisti:
#: portin-sanalista-vanhenee), joten se on lisäportti eikä ainoa portti.
BANNED_PHRASES = ("rather than",)

H2_RE = re.compile(r'<h2 id="([a-z0-9][a-z0-9-]*)"')
#: 🔴 30.8: lohkon LOPPU on mika tahansa seuraava <h2>, ei vain sellainen jolla
#: on id. `/fpl`-sivulla lahes jokaisella h2:lla on id, joten ero ei nakynyt;
#: alasivulla ei ole, ja #gw-xp-lohko nieli koko loppusivun - 12 496 merkkia ja
#: 387 lukua, eli lukuvahti olisi hyvaksynyt kaytannossa mita tahansa. Portti
#: joka lapaisee liian isolla lohkolla on sama vika kuin portti joka lapaisee
#: tyhjana (muisti: kontrolli-lapaisi-tyhjana, gate-substring-osuma-on-sokea).
H2_ANY_RE = re.compile("<h2[ >]")


def block_text(html: str, anchor: str) -> str:
    """Ankkurin lohko tekstina: sen h2:sta SEURAAVAAN h2:een (id tai ei)."""
    starts = [(m.group(1), m.start()) for m in H2_RE.finditer(html)]
    for i, (a, pos) in enumerate(starts):
        if a != anchor:
            continue
        nxt = H2_ANY_RE.search(html, pos + 1)
        end = nxt.start() if nxt else len(html)
        chunk = html[pos:end]
        chunk = re.sub(r"(?is)<(script|style)[^>]*>.*?</>", " ", chunk)
        return re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", chunk))
    return ""


def llms_lines_by_anchor(llms: str) -> dict:
    """Ankkuri -> se llms.txt-rivi joka siihen syvalinkittaa."""
    out = {}
    for line in llms.splitlines():
        for a in LINK_RE.findall(line):
            out.setdefault(a, []).append(line.strip())
    return out


def sub_lines_by_page(llms: str) -> dict:
    """(sivupolku, ankkuri) -> ne llms.txt-rivit jotka siihen syvalinkittavat."""
    out: dict = {}
    for line in llms.splitlines():
        for path, a in SUB_LINK_RE.findall(line):
            out.setdefault((path, a), []).append(line.strip())
    return out


def sub_page_html(path: str) -> str:
    """Alasivun HTML levylta. Puuttuva sivu -> "" (ankkuriportti ei kata
    alasivuja, joten tassa ei kaadeta puuttuvasta tiedostosta; luvut vain
    jaavat tarkistamatta ja se sanotaan ääneen kutsujassa)."""
    f = ROOT / (path + ".html")
    return f.read_text(encoding="utf-8") if f.exists() else ""


def _nums(text: str) -> set:
    return {m.group(1) for m in CLAIM_NUM_RE.finditer(text)}


def unsupported_numbers(html: str, llms: str) -> list:
    """Luvut joita syvalinkkirivi vaittaa mutta joita lohkossa ei ole.

    Tama on se vika jonka "all 20 teams" oli: luku joka oli kerran tosi ja
    jonka sivu on sittemmin jattanyt sanomatta.
    """
    bad = []
    for a, lines in llms_lines_by_anchor(llms).items():
        block = block_text(html, a)
        if not block:
            continue  # ankkuriportti hoitaa puuttuvat lohkot
        have = _nums(block)
        for line in lines:
            for n in sorted(_nums(line) - have):
                bad.append((a, n, line[:90]))
    return bad


def unsupported_numbers_subpages(llms: str) -> list:
    """Sama lukuvahti alasivujen syvalinkeille (esim. #gw-xp).

    Palauttaa myos rivit joiden sivua EI loytynyt levylta: tarkistamaton
    vaite ei saa nayttaa tarkistetulta (muisti: kontrolli-lapaisi-tyhjana).
    """
    bad = []
    for (path, a), lines in sorted(sub_lines_by_page(llms).items()):
        html = sub_page_html(path)
        if not html:
            for line in lines:
                bad.append((f"{path}#{a}", "?", f"sivua {path}.html ei ole - "
                            f"lukuja ei voitu tarkistaa: {line[:70]}"))
            continue
        block = block_text(html, a)
        if not block:
            for line in lines:
                bad.append((f"{path}#{a}", "-", f"sivulla {path} ei ole lohkoa "
                            f"#{a}: {line[:70]}"))
            continue
        have = _nums(block)
        for line in lines:
            for n in sorted(_nums(line) - have):
                bad.append((f"{path}#{a}", n, line[:90]))
    return bad


def banned_phrases(llms: str) -> list:
    """Hylatty sanamuoto /fpl-syvalinkkiriveilla (BLOKKAA).

    Rajattu tasan siihen mita LLMS-SYNC-CLAIM-GATE pyysi: syvalinkkirivien
    vaitteet. Koko tiedoston kattava kielto olisi tehnyt portista punaisen
    heti syntymassa kolmen vanhan rivin takia, ja paivittain punainen portti
    tulee ohitetuksi (muisti: pysyvasti-punainen-putki-nielee-regression).
    Muut osumat raportoidaan noottina, ks. `banned_phrases_elsewhere`.
    """
    out = []
    for a, lines in llms_lines_by_anchor(llms).items():
        for line in lines:
            for ph in BANNED_PHRASES:
                if ph in line.lower():
                    out.append((a, ph))
    return sorted(set(out))


def banned_phrases_elsewhere(llms: str) -> list:
    """Samat sanamuodot muualla tiedostossa: NOOTTI, ei blokkaus.

    Nakyy jotta loydos ei katoa; korjaus on oma copy-rivinsa jonossa
    (QUEUE: LLMS-RATHER-THAN) koska se on julkista tekstia -> portti.
    """
    anchored = {ln for lines in llms_lines_by_anchor(llms).values() for ln in lines}
    out = []
    for i, line in enumerate(llms.splitlines(), 1):
        if line.strip() in anchored:
            continue
        for ph in BANNED_PHRASES:
            if ph in line.lower():
                out.append((i, ph))
    return out


def free_claim_gating(html: str, llms: str) -> list:
    """`Free`-vaite edellyttaa etta lohko renderoityy ilman premium-ehtoa.

    fpl.html on kokonaan ilmainen eika siina ole premium-gatetusta (mitattu
    30.8: nolla osumaa). Tama vahti on siksi fail-closed TULEVAISUUTTA
    varten: jos gatetus joskus ilmestyy sivulle samalla kun llms.txt yha
    lupaa Free, portti kaatuu.
    """
    gated = re.findall(r'class="[^"]*\bis-premium\b[^"]*"|data-premium', html)
    if not gated:
        return []
    claims = [a for a, lines in llms_lines_by_anchor(llms).items()
              if any("free" in ln.lower() for ln in lines)]
    return sorted(claims)




# ---------------------------------------------------------------------------
# SIVULUOKKAPORTTI (30.8.2026)
#
# Ankkuriportti kattaa /fpl-sivun lohkot. Se ei nae kokonaisia SIVUTYYPPEJA:
# 30.8 mitattiin etta sitemapissa on 401 URLia ja /faq ei ollut kuvattu
# lainkaan, vaikka se on kuudella kysymyksella ja FAQPage-skeemalla juuri se
# sivutyyppi jota tekoalykoneet siteeraavat.
#
# Portti EI vaadi jokaista URLia: 349 ottelusivua kuvataan kuviona, ja niin
# kuuluukin. Se vaatii etta jokaisella sivuLUOKALLA on maininta. Uusi
# sivutyyppi ei siis voi jaada nakymattomaksi.

SITEMAP_GLOB = "sitemap*.xml"
LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
#: Luokat joita ei vaadita kuvattavaksi, perusteluineen.
CLASS_EXEMPT = {
    "/privacy": "lakisivu, ei tuotesisaltoa",
    "/delete-account": "lomake, ei sisaltoa jota siteerata",
    "/sitemap-core.xml": "sitemap itse",
    "/sitemap-fpl.xml": "sitemap itse",
    "/sitemap-predictions.xml": "sitemap itse",
    "/fpl/note/<x>": ("indeksisivu /fpl/notes on kuvattu ja linkitetty, ja se "
                      "listaa jokaisen muistion; yksittaisten slugien "
                      "linkittaminen vanhenisi joka julkaisussa"),
}


def sitemap_urls() -> list:
    out = []
    for f in sorted(ROOT.glob(SITEMAP_GLOB)):
        try:
            out += LOC_RE.findall(f.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    return out


def url_class(path: str) -> str:
    """Sivutyyppi polusta. /fpl/club/arsenal -> /fpl/club/<x>."""
    p = path.rstrip("/")
    osat = [x for x in p.split("/") if x]
    if not osat:
        return "/"
    if osat[0] == "predictions" and len(osat) >= 3:
        return "/predictions/<liiga>/<ottelu>"
    if osat[:2] == ["fpl", "club"] and len(osat) == 3:
        return "/fpl/club/<x>"
    if osat[:2] == ["fpl", "note"] and len(osat) == 3:
        return "/fpl/note/<x>"
    return "/" + "/".join(osat)


def undescribed_classes(llms: str, urls: list) -> list:
    """Sivuluokat joista llms.txt ei mainitse yhtaan esimerkkia."""
    low = llms.lower()
    luokat = {}
    for u in urls:
        polku = u.replace("https://goaliq.app", "").replace("http://goaliq.app", "")
        luokat.setdefault(url_class(polku), []).append(polku)
    puuttuu = []
    for luokka, esimerkit in sorted(luokat.items()):
        if luokka in CLASS_EXEMPT:
            continue
        # riittaa etta YKSI luokan polku mainitaan jossain muodossa
        if any(e.rstrip("/").lower() in low for e in esimerkit if e.rstrip("/")):
            continue
        if luokka == "/" and "goaliq.app/" in low:
            continue
        puuttuu.append((luokka, len(esimerkit), esimerkit[0]))
    return puuttuu



def main() -> int:
    if not PAGE.exists():
        print(f"FAIL: {PAGE} puuttuu - porttia ei voi todentaa (fail-closed).")
        return 1
    if not LLMS.exists():
        print(f"FAIL: {LLMS} puuttuu - porttia ei voi todentaa (fail-closed).")
        return 1

    html = PAGE.read_text(encoding="utf-8")
    llms = LLMS.read_text(encoding="utf-8")

    missing = missing_anchors(html, llms)
    stale = stale_anchors(html, llms)
    nums = unsupported_numbers(html, llms)
    subnums = unsupported_numbers_subpages(llms)
    luokat = undescribed_classes(llms, sitemap_urls())
    banned = banned_phrases(llms)
    gated = free_claim_gating(html, llms)

    for a, n, line in nums:
        print(f"FAIL: llms.txt vaittaa luvun {n} lohkosta #{a}, mutta sivun "
              f"lohkossa ei ole sita lukua. Rivi: {line}")
    for a, n, line in subnums:
        print(f"FAIL: llms.txt vaittaa luvun {n} alasivun lohkosta {a}, mutta "
              f"sita ei ole siella. Rivi: {line}")
    for a, ph in banned:
        print(f"FAIL: /fpl#{a} -rivi sisaltaa aiemmin hylatyn sanamuodon {ph!r} "
              f"(AI-TELL-CHECKLIST: negatiivinen parallelismi).")
    for ln, ph in banned_phrases_elsewhere(llms):
        print(f"NOTE: llms.txt rivi {ln} sisaltaa {ph!r} (ei /fpl-rivi, ei "
              f"blokkaa; QUEUE: LLMS-RATHER-THAN).")
    for luokka, n, esim in luokat:
        print(f"FAIL: sivuluokkaa {luokka} ({n} sivua, esim. {esim}) ei mainita "
              f"llms.txt:ssa. Kuvaa luokka KERRAN kuviona, tai lisaa "
              f"CLASS_EXEMPT-listaan perusteluineen.")
    for a in gated:
        print(f"FAIL: llms.txt lupaa lohkon #{a} ilmaiseksi, mutta sivulla on "
              f"premium-gatetusta. Tarkista kumpi on oikein.")

    if not (missing or stale or nums or subnums or banned or gated or luokat):
        described = sorted(page_anchors(html) - set(EXEMPT))
        n_sub = len(sub_lines_by_page(llms))
        print(f"OK: llms.txt kuvaa kaikki {len(described)} /fpl-sisaltolohkoa "
              f"({n_sub} alasivuankkuria lukutarkistettu).")
        return 0

    for a in missing:
        print(
            f"FAIL: /fpl-sivulla on lohko #{a} jota llms.txt ei kuvaa. "
            f"Lisaa rivi joka linkittaa https://goaliq.app/fpl#{a}, "
            f"tai lisaa ankkuri EXEMPT-listaan perusteluineen."
        )
    for a in stale:
        print(
            f"FAIL: llms.txt linkittaa /fpl#{a}, mutta sivulla ei ole sita ankkuria. "
            f"Poista tai korjaa rivi."
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
