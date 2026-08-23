#!/usr/bin/env python3
"""Copy-tyyliportti web-pinnalle: em dash (U+2014) kielletty copyssa.

Pari mobiilin `scripts/check-copy-style.js`:lle. Villen saanto 27.7:
korjaukset AINA web + mobiili, joten myos portin on oltava molemmilla.

MITA SKANNATAAN JA MIKSI JUURI TATA
-----------------------------------
1. JULKAISTUT HTML-sivut (goaliq.app: juuri + fpl/ + predictions/).
   Naista <script>- ja <style>-lohkot ja <!-- --> -kommentit leikataan pois:
   ne eivat ole copya.
2. pro-SPA:n Svelte-markup (script- ja style-lohkojen ULKOPUOLINEN teksti).
3. pro-SPA:n .ts-tiedostojen MERKKIJONOLITERAALIT (8.8: roast.ts, shareCard.ts
   ja fantasyTools.ts sisaltavat kayttajalle nakyvaa tekstia .ts-puolella,
   joka oli portin katvealueessa). Kommentit ohitetaan tokenisoimalla, ei
   regexilla: '//' merkkijonon sisalla (esim. https://...) ei ole kommentti,
   eika kommentin heittomerkki (don't) aloita merkkijonoa.

GENERAATTOREITA (build_*.py) EI skannata suoraan, ja se on tietoinen valinta.
Ensimmainen versio skannasi ne ja tuotti 30 vaaraa osumaa: Python-docstringit
ja suomenkieliset koodikommentit ovat taynna em dasheja, eivatka ne ole copya.
Generaattorin tuotos on committattuna repossa, joten generaattorin lisaama em
dash nakyy kohdassa 1 seuraavalla ajolla. Portti osoittaa silloin HTML-riviin;
korjaus kuuluu silti generaattoriin, koska CI kirjoittaa nama sivut yli
<= 3 h valein (vrt. 27.7: sivuille tehty korjaus katosi hiljaa).

Rajaus:
  - Yksinainen '—' lainausmerkkien valissa = puuttuvan arvon merkki, sallitaan.
  - &mdash; on sama merkki HTML-entiteettina, joten se lasketaan mukaan.

Aja: python scripts/check_copy_style.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EM = "—"
# 9.8 (Villen havainto): portti kattoi VAIN em dashin, joten en dash (–) eli
# sivujen <title>-erotin ("Free FPL Tools – Rate My Team") lapaisi sen. Se
# nakyy selaimen valilehdessa, hakutuloksissa ja X:n/Blueskyn linkkikortissa
# eli kaikkialla missa copy nakyy. Sama sallinta kuin em dashille: yksinainen
# merkki lainausmerkkien valissa on puuttuvan arvon merkki.
EN = "–"
DASHES = (EM, EN)
ENTITIES = ("&mdash;", "&ndash;")

HTML_GLOBS = ["*.html", "fpl/*.html", "predictions/*.html", "predictions/**/*.html"]
SPA_DIR = ROOT / "web" / "pro-spa" / "src"
# 28.7: versioidut CSV-inputit joiden tekstikentat paatyvat API-payloadiin ja
# sielta UI:hin (esim. fpl_player_overrides.csv:n `reason` nakyy pelaajakortilla).
# Nama eivat ole koodia eivatka HTML:aa, joten ne jaivat portin ulkopuolelle ja
# yksi em dash paasi lapi kayttajalle asti.
COPY_CSV = ["data/fpl_player_overrides.csv", "data/fpl_manual_overrides.csv"]

PLACEHOLDER = re.compile(r"(['\"`>])[" + EM + EN + r"](['\"`<])")


def _blank(m: re.Match) -> str:
    """Korvaa osuma valilyonnein niin etta rivinumerot sailyvat."""
    return re.sub(r"[^\n]", " ", m.group(0))


def _mask_non_copy(text: str) -> str:
    """Nollaa kaikki mika ei ole kayttajalle nakyvaa tekstia."""
    text = re.sub(r"<!--.*?-->", _blank, text, flags=re.DOTALL)
    text = re.sub(r"<script\b.*?</script>", _blank, text, flags=re.DOTALL | re.I)
    text = re.sub(r"<style\b.*?</style>", _blank, text, flags=re.DOTALL | re.I)
    return text


def _ts_string_literals_only(text: str) -> str:
    """Sailyta vain .ts-tiedoston merkkijonoliteraalit; blankkaa koodi ja
    kommentit rivinumerot sailyttaen. Copy elaa string-literaleissa;
    koodikommentit (taynna em dasheja) eivat ole copya."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append(re.sub(r"[^\n]", " ", text[i:j]))
            i = j
        elif c in "\"'`":
            quote = c
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == quote:
                    j += 1
                    break
                if quote != "`" and text[j] == "\n":
                    break
                j += 1
            out.append(text[i:j])
            i = j
        else:
            out.append(c if c == "\n" else " ")
            i += 1
    return "".join(out)


def scan(path: Path) -> list[tuple[int, str]]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if not any(d in raw for d in DASHES) and not any(
            e in raw for e in ENTITIES):
        return []
    # CSV-inputeissa #-rivit ovat dokumentaatiota (suomeksi, taynna em dasheja),
    # eivat copya. Vain datarivien tekstikentat paatyvat kayttajalle.
    is_csv = path.suffix.lower() == ".csv"
    if is_csv:
        masked = raw
    elif path.suffix.lower() == ".ts":
        masked = _ts_string_literals_only(raw)
    else:
        masked = _mask_non_copy(raw)
    raw_lines = raw.split("\n")
    hits: list[tuple[int, str]] = []
    for i, line in enumerate(masked.split("\n")):
        if is_csv and line.lstrip().startswith("#"):
            continue
        probe = PLACEHOLDER.sub("  ", line)
        if any(d in probe for d in DASHES) or any(
                e in probe for e in ENTITIES):
            hits.append((i + 1, raw_lines[i].strip()[:200]))
    return hits


# 16.8: mallilupausportti. Copy vaitti viidella pinnalla "Dixon-Coles +
# LightGBM ensemble", vaikka /api/predict importoi vain DixonColesModelin
# (api/main.py:43). Repo on julkinen, eli vaite oli tarkistettavissa ja kaatui
# tarkistuksessa.
#
# 17.8. PAIVITYS: tuotanto fittaa nyt maaleilla JA xG:lla
# (config.DIXON_COLES_XG_WEIGHT = 0.5, mitattu walk-forwardilla). Se ei muuta
# tata listaa yhtaan: xG-painotus on neliöity sakko SAMASSA Dixon-Colesin
# uskottavuusfunktiossa, ei toinen malli eika oppiva komponentti. "Ensemble",
# "machine learning" ja "AI model" ovat siis yha yhta vaaria kuin ennenkin.
# Muuttunut vaite koskee DATASYOTETTA ("fitted on goals" -> "goals and xG"),
# ja se korjattiin samassa committissa jossa kytkenta tehtiin.
#
# Loysin sen kasin NELJASSA eri sanamuodossa perakkain, joka kerta luullen
# edellista viimeiseksi: "machine learning" -> "expected-goals ensemble" ->
# lyhenne "+ ML" -> "AI model". Jokainen greppi oli sokea seuraavalle. Tama
# lista on olemassa siksi ettei viidetta etsita taas kasin.
#
# EI kiella sanaa AI yleisesti: llms.txt:n "Drafted with AI assistance" on
# tosi ja se JAA (AI-kayttoa ei kiisteta). Kielletty on vain vaite ETTA
# ENNUSTEET tulevat jostain muusta kuin Dixon-Colesista.
#
# Jos ensemble joskus kytketaan tuotantopolkuun, tama lista paivitetaan
# SAMASSA committissa jossa se kytketaan, ei aiemmin.
# PORTTI ON SOKEA KIELTOLAUSEELLE, ja se on tietoinen valinta (17.8).
# Se osui lauseeseen joka KIISTI ML:n ("It is not a machine-learning model"),
# eli oikeaan asiaan vaarasta syysta. Negaatiotunnistusta ei lisatty: se olisi
# hauras ja huijattavissa ("not just a machine-learning model"), ja portin arvo
# on nimenomaan siina ettei sita voi selittaa ohi. Kaytannon seuraus: jos
# haluat SANOA ettei ennuste tule ML:sta, sano se ilman naita sanoja
# ("no second model in the prediction path"). Ks. llms.txt "Notes for AI engines".
MODEL_CLAIM_PATTERNS = [
    (re.compile(r"machine[- ]learning", re.I), "machine learning"),
    (re.compile(r"\bLightGBM\b", re.I), "LightGBM"),
    (re.compile(r"\bensemble\b", re.I), "ensemble"),
    (re.compile(r"\+\s*ML\b"), "+ ML"),
    (re.compile(r"\bML[- ](model|ensemble)\b", re.I), "ML model"),
    (re.compile(r"\bAI[- ](model|powered|driven)\b"), "AI model / AI-powered"),
]

# Julkiset pinnat joilla mallilupaus voi esiintya. api/main.py on mukana koska
# sen OpenAPI-kuvaus servataan osoitteessa api.goaliq.app/openapi.json ja
# linkitetaan juuresta (/docs) - se oli yksi neljasta sokeasta pisteesta.
MODEL_CLAIM_EXTRA = ["llms.txt", "api/main.py"]


def scan_model_claims(path: Path) -> list[tuple[int, str, str]]:
    """Palauta (rivinumero, osunut_kuvio, rivi) jokaiselle mallilupaukselle."""
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    if path.suffix.lower() == ".html":
        masked = _mask_non_copy(raw)
    else:
        masked = raw
    raw_lines = raw.split("\n")
    hits: list[tuple[int, str, str]] = []
    for i, line in enumerate(masked.split("\n")):
        for pattern, nimi in MODEL_CLAIM_PATTERNS:
            if pattern.search(line):
                hits.append((i + 1, nimi, raw_lines[i].strip()[:200]))
                break
    return hits


def scan_openapi() -> list[tuple[str, str]]:
    """Palauta (polku_spekissa, teksti) jokaiselle vuotaneelle merkkijonolle.

    16.8. mitattiin etta `api.goaliq.app/openapi.json` sisalsi 44 em dashia ja
    126 suomenkielista sanamuotoa englanninkielisella JULKISELLA pinnalla.
    Portilla oli oma sokea piste: se skannasi `api/main.py`:n mallilupausten
    varalta, muttei koskaan sita mita FastAPI generoi docstringeista ja
    Field-kuvauksista. Docstring paatyy spekkiin, koodikommentti ei, joten
    kohde on nimenomaan generoitu spekki eika lahdetiedoston teksti.

    Fail-closed: jos spekkia ei saada generoitua, se on portin virhe eika
    lupa jatkaa (poikkeus on huono todiste "ei vuotoja").
    """
    import json

    sys.path.insert(0, str(ROOT))
    from api.main import app  # noqa: E402  (raskas import, vain portin ajossa)

    spec = app.openapi()
    osumat: list[tuple[str, str]] = []

    def walk(o, polku: str = "") -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{polku}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{polku}/{i}")
        elif isinstance(o, str):
            if any(d in o for d in DASHES) or re.search(r"[äöåÄÖÅ]", o):
                osumat.append((polku, " ".join(o.split())[:160]))

    walk(spec)
    return osumat


# ---------------------------------------------------------------------------
# JULKISET JSON-ARTEFAKTIT (23.8.2026, BACKEND-FI-JULKISESSA-PAYLOADISSA)
# ---------------------------------------------------------------------------
# Portilla oli sama sokea piste kuin 16.8 openapi.jsonin kanssa: se skannasi
# HTML:n ja SPA:n, muttei sita mita API palauttaa `data/`-artefakteista
# SELLAISENAAN. Mitattu 23.8 tuotannosta:
#
#   /api/fantasy/rate-team -> meta.projection_accuracy.meta.population
#       = "pelanneet (minuutit > 0)"
#   ...                    -> meta.projection_accuracy.meta.minutes_path
#       = suomenkielinen sisainen huomautus + em dash
#
# Naita ei renderoinut mikaan pinta viela, mutta `RivalPanel.tsx` tulostaa jo
# `meta.method`in raakana — ensimmainen vastaava komponentti olisi vuotanut
# suomen ulos. Sama vikaluokka kuin openapi 17.8.
#
# HUOM: aiempi saanto (em dash + aou-umlautit) EI olisi napannut merkkijonoa
# "pelanneet (minuutit > 0)" — siina ei ole kumpaakaan. Siksi tassa on myos
# suomen sanalista. Sanalista vanhenee (kirjattu ansa), joten se on pidettava
# kapeana ja korkean tarkkuuden sanoissa, ja negatiivinen kontrolli ajetaan.
PUBLIC_JSON = [
    "data/accuracy.json",
    "data/fpl_defcon_gw.json",
    "data/fpl_player_leaders.json",
    "data/fpl_price_watch.json",
    "data/fpl_projections_phase0.json",
    "data/fpl_why.json",
    "data/fpl_xp_accuracy.json",
    "data/fpl_xp_projections.json",
    "data/fpl_price_accuracy.json",
    "data/fpl_minutes_validation.json",
    "data/spl_projections_phase0.json",
    "data/spl_xp_projections.json",
    "data/wc_model.json",
]

_FI_SANAT = re.compile(
    r"\b(pelanneet|pelattu|pelaaja\w*|joukkue\w*|kierros\w*|ottelu\w*|kausi|"
    r"kaude\w*|minuutit|tuotannon|sisalla|sisällä|kumpaakaan|historiallisena|"
    r"saatavuuslippu|syvyyskorjaus|vahintaan|vähintään|selkeasti|selkeästi|"
    r"keskiarvo|puuttuu|vanhentunut|paivittyy|päivittyy|lahde|lähde|ennuste\w*|"
    r"arvio|jokainen|kaikki)\b",
    re.IGNORECASE,
)


# Kopio-kentat: naissa arvo on TEKSTIA jonka kayttaja lukee. Muissa kentissa
# arvo on DATAA (pelaajien ja seurojen nimia), ja niissa skandinaaviset merkit
# ovat oikein: Lindelöf, Schär, Röhl, Abdülkadir Ömür. Ensimmainen versio
# tasta portista huusi niista 200 kertaa — sanalista ilman kohdennusta on
# hyodyton portti.
_COPY_AVAIMET = re.compile(
    r"\.(meta|note|notes|method|methodology|description|desc|disclaimer|caveat|"
    r"population|product|label|text|title|summary|explanation|why|reason|"
    r"minutes_path|criteria|baseline|footnote|source_note)",
    re.IGNORECASE,
)


def _json_syy(teksti: str, polku: str = "") -> str | None:
    """Miksi tama merkkijono ei kelpaa julkiselle englanninkieliselle pinnalle?

    Em dash ja suomen sanat tarkistetaan KAIKISTA kentista (kumpikaan ei esiinny
    pelaajanimissa). Skandinaaviset merkit vain kopio-kentista, koska nimissa ne
    ovat oikein.
    """
    if any(d in teksti for d in DASHES):
        return "em/en dash"
    m = _FI_SANAT.search(teksti)
    if m:
        return f"suomenkielinen sana '{m.group(0)}'"
    if _COPY_AVAIMET.search(polku) and re.search(r"[äöåÄÖÅ]", teksti):
        return "skandinaaviset merkit kopio-kentassa"
    return None


def scan_public_json(root: Path | None = None) -> list[tuple[str, str, str]]:
    """(tiedosto, polku_dokumentissa, syy) jokaiselle vuotaneelle merkkijonolle.

    Puuttuva tiedosto ei ole vika (kaikkia artefakteja ei ole joka koneella),
    mutta RIKKINAINEN on: fail-closed, koska poikkeus on huono todiste
    "ei vuotoja".
    """
    import json as _json

    root = root or ROOT
    osumat: list[tuple[str, str, str]] = []
    for rel in PUBLIC_JSON:
        f = root / rel
        if not f.exists():
            continue
        try:
            doc = _json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            osumat.append((rel, "<tiedosto>", f"ei luettavissa: {type(e).__name__}"))
            continue

        def walk(o, polku: str = "") -> None:
            if isinstance(o, dict):
                for k, v in o.items():
                    walk(v, f"{polku}.{k}")
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, f"{polku}[{i}]")
            elif isinstance(o, str):
                syy = _json_syy(o, polku)
                if syy:
                    osumat.append((rel, polku, f"{syy}: {' '.join(o.split())[:120]}"))

        walk(doc)
    return osumat


# ---------------------------------------------------------------------------
# KAANNETTAVUUS: proosakentta ilman vakaata tunnistetta (BACKEND-EN-VUOTAA-ES-PT)
# ---------------------------------------------------------------------------
# Mitattu 23.8: `meta.note`, `meta.disclaimer`, `meta.method`, `meta.caveat` ja
# `meta.excluded_note` renderoidaan RAAKANA yhdessatoista paikassa mobiilissa ja
# SPA:ssa (esim. `PriceWatch.svelte:192`, `RivalPanel.tsx:157`,
# `FantasyTools.tsx:4981`). Espanjan- tai portugalinkielinen kayttaja saa siis
# kaannetyn otsikon ja englanninkielisen alaviitteen.
#
# Oikea korjaus on kaannokset, mutta ne ovat UUTTA JULKISTA TEKSTIA ja kuuluvat
# julkaisuporttiin. Valivaihe joka ei vaadi yhtaan uutta lausetta: backend
# lahettaa proosan rinnalle VAKAAN tunnisteen, jolloin klientti voi kaantaa sen
# omasta i18n-tiedostostaan ja proosa jaa varakieleksi.
#
# Tama portti pitaa huolen siita ettei velka kasva: uusi proosakentta ilman
# tunnistetta punaa ajon. Ilman porttia seuraava kentta lisattaisiin taas
# pelkkana englantina, eika kukaan huomaisi ennen kuin kayttaja valittaa.
PROSE_META_KEYS = ("note", "disclaimer", "caveat", "method", "excluded_note")

# Tunniste on TUNNISTE eika lause: piste-erotellut sanat, ei valilyonteja.
_CODE_MUOTO = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


def scan_meta_codes(root: Path | None = None) -> list[tuple[str, str, str]]:
    """(tiedosto, kentta, syy) jokaiselle proosakentalle ilman kelvollista koodia."""
    import json as _json

    root = root or ROOT
    puutteet: list[tuple[str, str, str]] = []
    for rel in PUBLIC_JSON:
        f = root / rel
        if not f.exists():
            continue
        try:
            doc = _json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # scan_public_json raportoi rikkinaisen tiedoston
        meta = doc.get("meta") if isinstance(doc, dict) else None
        if not isinstance(meta, dict):
            continue
        for avain in PROSE_META_KEYS:
            arvo = meta.get(avain)
            if not isinstance(arvo, str) or not arvo.strip():
                continue
            koodi = meta.get(f"{avain}_code")
            if not koodi:
                puutteet.append((rel, f"meta.{avain}",
                                 f"proosa ilman {avain}_code-paria"))
            elif not (isinstance(koodi, str) and _CODE_MUOTO.match(koodi)):
                puutteet.append((rel, f"meta.{avain}_code",
                                 f"ei ole tunniste: {str(koodi)[:60]!r}"))
    return puutteet


def main() -> int:
    targets: list[Path] = []
    for g in HTML_GLOBS:
        targets += sorted(ROOT.glob(g))
    if SPA_DIR.exists():
        targets += sorted(SPA_DIR.rglob("*.svelte"))
        targets += sorted(SPA_DIR.rglob("*.ts"))
    targets += [ROOT / c for c in COPY_CSV if (ROOT / c).exists()]
    targets = sorted(set(targets))

    all_hits = [(p, n, t) for p in targets for n, t in scan(p)]

    # Mallilupaus: samat HTML-pinnat + llms.txt + API:n OpenAPI-kuvaus.
    claim_targets = [p for p in targets if p.suffix.lower() == ".html"]
    claim_targets += [ROOT / c for c in MODEL_CLAIM_EXTRA if (ROOT / c).exists()]
    claim_hits = [
        (p, n, nimi, t) for p in claim_targets for n, nimi, t in scan_model_claims(p)
    ]

    if claim_hits:
        print(
            f"check_copy_style FAIL - {len(claim_hits)} mallilupausta jotka "
            f"tuotannon ennustepolku ei kata:\n"
        )
        for path, line_no, nimi, text in claim_hits:
            print(f"  {path.relative_to(ROOT)}:{line_no}  [{nimi}]\n    {text}\n")
        print(
            "/api/predict ajaa vain Dixon-Colesin (api/main.py:43 importoi vain "
            "DixonColesModelin; :975 fittaa maaleilla ja xG:lla, xg_weight 0.5, "
            "mika on yha SAMA malli eika ensemble). Repo on julkinen, joten "
            "vaite ensemblesta tai ML:sta on tarkistettavissa ja kaatuu. Kuvaa "
            "se mika on katetta: tau-korjaus, aikapainotus, Bayes-kutistus, "
            "kilpailupainot, ja julkinen ennakkoon lokattu track record."
        )
        return 1

    try:
        openapi_hits = scan_openapi()
    except Exception as e:  # fail-closed, ks. scan_openapi-docstring
        print(f"check_copy_style FAIL - openapi-spekkia ei saatu generoitua: "
              f"{type(e).__name__}: {e}")
        return 1

    if openapi_hits:
        print(
            f"check_copy_style FAIL - {len(openapi_hits)} em dashia tai "
            f"suomenkielista merkkijonoa openapi.jsonissa:\n"
        )
        for polku, teksti in openapi_hits:
            print(f"  {polku}\n    {teksti}\n")
        print(
            "api.goaliq.app/openapi.json on JULKINEN englanninkielinen pinta. "
            "FastAPI kopioi sinne endpointin docstringin ja Field-kuvaukset. "
            "Korjaus: anna reitille `description=\"...\"` dekoraattorissa "
            "(se korvaa docstringin spekissa) tai kirjoita kuvaus englanniksi. "
            "Sisainen suomenkielinen selitys kuuluu #-kommenttiin, joka ei vuoda."
        )
        return 1

    code_gaps = scan_meta_codes()
    if code_gaps:
        print(f"check_copy_style FAIL - {len(code_gaps)} kaannettavaa "
              f"proosakenttaa ilman vakaata tunnistetta:")
        for tiedosto, kentta, syy in code_gaps:
            print(f"  {tiedosto} {kentta}  <- {syy}")
        return 1

    json_hits = scan_public_json()
    if json_hits:
        print(f"check_copy_style FAIL - {len(json_hits)} suomenkielista tai "
              f"em dash -merkkijonoa JULKISISSA JSON-artefakteissa "
              f"({len(PUBLIC_JSON)} tiedostoa skannattu):")
        for tiedosto, polku, syy in json_hits[:20]:
            print(f"  {tiedosto}{polku}  <- {syy}")
        return 1

    if not all_hits:
        print(
            f"check_copy_style OK - 0 em dashia copyssa ({len(targets)} tiedostoa), "
            f"0 kattamatonta mallilupausta ({len(claim_targets)} pintaa), "
            f"0 vuotoa openapi.jsonissa, "
            f"0 vuotoa {len(PUBLIC_JSON)}:ssa julkisessa JSON-artefaktissa, "
            f"0 proosakenttaa ilman kaannostunnistetta"
        )
        return 0

    print(
        f"check_copy_style FAIL - {len(all_hits)} em dashia kayttajalle "
        f"nakyvassa tekstissa:\n"
    )
    for path, line_no, text in all_hits:
        print(f"  {path.relative_to(ROOT)}:{line_no}\n    {text}\n")
    print(
        "Em dash on kielletty GoalIQ-copyssa. Kayta pistetta, pilkkua tai "
        "kaksoispistetta. Jos rivi on generoitu, korjaa GENERAATTORI: CI "
        "kirjoittaa nama sivut yli <= 3 h valein."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
