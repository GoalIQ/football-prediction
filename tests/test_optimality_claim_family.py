"""Portti: optimaalisuusvaite on YHDESSA paikassa, ei jokaisella pinnalla.

🔴 MIKSI TAMA ON OLEMASSA (4.9.2026). Julkaisuportti ajoi saman sivun yli
NELJA kierrosta ja loysi joka kerta uutta, koska jokainen kierros greppasi
ERI merkkijonoa:

    kierros 1  "budget optimum"        -> nakyva copy
    kierros 2  "highest-scoring"       -> <head> x6, llms.txt
    kierros 3  "best possible"         -> career.html:n jakokortti
    kierros 4  "the rules allow"       -> career.html:354, ChipEv, roast.ts

Viides greppaus olisi loytanyt viidennen sanamuodon. **Lista ei tyhjene
greppaamalla.** Se tyhjenee vasta kun vaiteperhe on yhdessa paikassa ja yksi
testi ajaa sen kaikkien julkisten pintojen yli, perusteltu poikkeuslista
mukana (saanto 6a mekanismit 1 ja 2).

MITA VAITE TARKOITTAA. `optimal_xi_proven()` on tuotannossa **False**: haku on
paikallinen eika todistettu optimi. Mitattu entryn 116920 rungolla:
`team_xp_horizon_no_captain` **322,42** vs `optimal_team_xp` **310,77**, eli
kayttajan oma joukkue voittaa vertailukohdan 11,65 xP:lla ja
`beats_benchmark` on True. Julkinen teksti ei siis saa vaittaa optimia eika
kayvan joukon maksimia.

🔴 TAMA TIEDOSTO KIRJOITETTIIN UUDELLEEN saman portin VIIDENNELLA kierroksella,
joka loysi kolme vikaa portista itsestaan:

  1. **Punainen CI vaarasta syysta.** `goaliq-app` on eri repo eika sita
     checkoutata missaan workflow'ssa, joten kuolleet-rivit-tarkistus kaatui
     siella viidesta rivista. Pahempaa: mobiilipinnat putosivat skannauksesta
     HILJAA ja tyhjyyskontrolli lapaisi silti, koska sen pakolliset nimet
     olivat kaikki tassa repossa. Nyt poissaolo on eksplisiittinen skip.
  2. **Kolmen rivin sallivuusikkuna oli liian valja.** Yksi hedge ikkunassa
     vaiensi kaikki vaitteet siina ikkunassa. `career.html`:ssa
     `optimal_proven` on riveilla 529 ja 546, joten koko korttilohko oli
     automaattisesti sallittu — juuri se alue jota muokattiin nelja kertaa.
     Ikkuna on nyt MERKKIPOHJAINEN (mitattu: portitettu ternaari
     `RateTeam.svelte:1227-1229` pitaa lipun 137 merkin paassa vaitteesta).
  3. **`#`-kommenttien riisuminen soi llms.txt:n Markdown-otsikot.** Siina on
     11 `#`-alkuista rivia, ja kielletty vaite otsikossa olisi ollut
     nakymaton. Kommenttikuviot valitaan nyt TIEDOSTOTYYPIN mukaan.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FP = Path(__file__).resolve().parent.parent
APP = FP.parent / "goaliq-app"

# ---------------------------------------------------------------------------
# VAITEPERHE. Kuviot etsivat vaitteen MUOTOA eivatka yksittaisia lauseita:
# "paras/vahvin" + "mahdollinen/sallittu/optimi". Lista laajennettiin
# viidennella kierroksella 14 vaihtoehtoisella muotoilulla joihin alkuperainen
# ei osunut — mukana `mejor equipo posible` ja `melhor time possivel`, joita
# LAHETAMME jo (oikein portitettuina), eli portti oli sokea juuri sille
# muodolle jota es/pt-kaannos todennakoisimmin kayttaisi.
# ---------------------------------------------------------------------------
KUVIOT = [
    r"best possible",
    r"budget optimum",
    r"proven optim(?:um|al)",
    r"the rules allow",
    r"highest[- ]scoring",
    r"highest expected",
    r"optimal (?:squad|team|XI|lineup)",
    r"paras mahdollinen",
    r"\boptimum\b",
    r"maximum (?:possible )?points",
    r"nothing better",
    r"unbeatable",
    r"the (?:theoretical|mathematical) (?:best|maximum)",
    # "available" YKSIN oli liian valja: se osui "the best available
    # player in the same position" -tekstiin kolmella sivulla, mika on
    # korvaajasuositus eika vaite budjettioptimista. Vaadi apuverbi.
    r"(?:best|strongest) (?:\w+ ){0,2}(?:you can|money can)",
    r"the perfect (?:XI|squad|team)",
    r"cannot do better",
    r"no squad scores more",
    # es/pt
    r"plantilla óptima",
    r"equipo óptimo",
    r"elenco ótimo",
    r"esquadr[aã]o ótim",
    r"mejor \w+ posible",
    r"melhor \w+ poss[ií]vel",
]
RE_KUVIO = re.compile("|".join(KUVIOT), re.I)

# Kieltomuodot ja lipun takana olevat haarat ovat OK. "not a GLOBAL optimum"
# (PlanChains.svelte:351) on aito varaus, joten maare kiellon ja sanan valissa
# on sallittu — kapeampi kuvio olisi pakottanut poistamaan oikean varauksen.
RE_SALLITTU = re.compile(
    r"(?:not (?:a |the )?(?:\w+ ){0,2}optim(?:um|al)"
    r"|is not proven optimal"
    r"|(?:our search|we) (?:found|finds)"
    r"|best effort"
    r"|_unproven"
    r"|optimal_proven"
    r"|optimal_xi_proven)", re.I)

# Sallivuus on MERKKIPOHJAINEN, ei riveissa. Mitattu 4.9: oikein portitettu
# ternaari pitaa lipun 137 merkin paassa vaitteesta, joten 220 kattaa sen.
# Rivipohjainen ikkuna vapautti generoidussa HTML:ssa koko sivun, koska runko
# on usein yhtena pitkana rivina.
SALLIVUUS_MERKKIA = 220

# Kommenttikuviot TIEDOSTOTYYPIN mukaan. "Kaikki kuviot kaikkeen" soi
# llms.txt:n Markdown-otsikot.
KOMMENTIT: dict[str, list[re.Pattern]] = {
    # HTML: myos <script>- ja <style>-lohkojen kommentit. career.html:n
    # JS-kommentti (joka SELITTAA taman portin) osui muuten itseensa.
    ".html": [re.compile(r"(?s)<!--.*?-->"),
              re.compile(r"(?s)/\*.*?\*/")],
    ".svelte": [re.compile(r"(?s)<!--.*?-->"), re.compile(r"(?s)/\*.*?\*/"),
                re.compile(r"(?m)^\s*//.*$")],
    ".ts": [re.compile(r"(?s)/\*.*?\*/"), re.compile(r"(?m)^\s*//.*$"),
            re.compile(r"(?m)^\s*\*.*$")],
    ".tsx": [re.compile(r"(?s)/\*.*?\*/"), re.compile(r"(?m)^\s*//.*$"),
             re.compile(r"(?m)^\s*\*.*$")],
    ".py": [re.compile(r"(?m)^\s*#.*$")],
    # .txt ja .json: EI riisumista. llms.txt on Markdownia, ei koodia.
}

# ---------------------------------------------------------------------------
# PINNAT
# ---------------------------------------------------------------------------
APP_RIVIT = {"store.config.json", "FantasyShareCard.tsx",
             "en.ts", "es.ts", "pt.ts"}


def _pinnat() -> list[Path]:
    ulos: list[Path] = []
    for kuvio in ("*.html", "llms.txt", "fpl/*.html", "fpl/note/*.html",
                  "fpl/club/*.html"):
        ulos += sorted(FP.glob(kuvio))
    for kuvio in ("web/pro-spa/src/lib/**/*.svelte",
                  "web/pro-spa/src/lib/**/*.ts",
                  "web/pro-spa/src/routes/**/*.svelte"):
        ulos += sorted(FP.glob(kuvio))
    if APP.exists():
        for kuvio in ("lib/i18n/*.ts", "components/*.tsx",
                      "store.config.json"):
            ulos += sorted(APP.glob(kuvio))
    return ulos


PINNAT = _pinnat()

# ---------------------------------------------------------------------------
# POIKKEUSLISTA: rivi paasee tanne VAIN perustelun kanssa.
# ---------------------------------------------------------------------------
SALLITUT: dict[str, str] = {
    "store.config.json":
        "🔒 Store-listaukset eivat ole hotfixattavissa (arvostelusykli). Kaksi "
        "kohtaa sanoo 'the strongest squad the rules allow'. Korjataan "
        "seuraavan submitin yhteydessa; Villen GO tarvitaan siihen joka "
        "tapauksessa. Jonossa OPTIMAL-VAITE-MOBIILISSA-JA-STORESSA.",
    "en.ts":
        "Nappiteksti 'Optimal lineup' jarjestaa KAYTTAJAN OMAN 15:n parhaaksi "
        "XI:ksi. Se on 11-of-15 -valinta eli lahtokohtaisesti eksakti, toisin "
        "kuin 100.0m budjettihaku joka on paikallinen. Sama perustelu kuin "
        "TeamPitchManager.sveltella. VARAUS: eksaktius on oletettu koodin "
        "muodosta, EI mitattu.",
    "TeamPitchManager.svelte":
        "Sama 'Optimal lineup' -nappi webissa. Ks. en.ts.",
}


def _riisu_kommentit(polku: Path, teksti: str) -> str:
    """Korvaa kommentit valilyonneilla niin etta indeksit sailyvat."""
    for re_k in KOMMENTIT.get(polku.suffix, []):
        teksti = re_k.sub(
            lambda m: re.sub(r"[^\n]", " ", m.group(0)), teksti)
    return teksti


def _osumat(polku: Path) -> list[str]:
    try:
        raaka = polku.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    teksti = _riisu_kommentit(polku, raaka)
    ulos = []
    for m in RE_KUVIO.finditer(teksti):
        a = max(0, m.start() - SALLIVUUS_MERKKIA)
        b = min(len(teksti), m.end() + SALLIVUUS_MERKKIA)
        if RE_SALLITTU.search(teksti[a:b]):
            continue
        rivi = teksti.count("\n", 0, m.start()) + 1
        ulos.append("%s:%d %s" % (polku.name, rivi,
                                  teksti[m.start():m.start() + 90].strip()))
    return ulos


# --- tyhjyyskontrollit ------------------------------------------------------

def test_pintalista_ei_ole_tyhja():
    """Testi joka ei skannaa mitaan lapaisee aina."""
    assert len(PINNAT) >= 30, len(PINNAT)
    nimet = {p.name for p in PINNAT}
    for pakollinen in ("career.html", "llms.txt", "model-xi.html",
                       "index.html", "fpl.html"):
        assert pakollinen in nimet, pakollinen


def test_mobiilipinnat_skannataan_tai_skipataan_aanekkaasti():
    """🔴 CI ei checkouta goaliq-appia, ja aiempi versio pudotti mobiilipinnat
    HILJAA samalla kun tyhjyyskontrolli lapaisi (sen pakolliset nimet olivat
    kaikki tassa repossa). Skip on eri asia kuin lapaisy."""
    if not APP.exists():
        pytest.skip("goaliq-app ei ole checkoutattu, mobiilipinnat "
                    "skannaamatta (odotettua CI:ssa, ei paikallisesti)")
    nimet = {p.name for p in PINNAT}
    puuttuu = sorted(APP_RIVIT - nimet)
    assert not puuttuu, puuttuu


# --- kuvion omat kontrollit -------------------------------------------------

def test_kuvio_osuu_tunnettuihin_vikoihin():
    """Jos kuvio ei osu naihin mitattuihin sanamuotoihin, portti ei mittaa
    mitaan."""
    tunnetut = [
        "This is a budget optimum, not our team.",
        "The highest-scoring XI inside the 100.0m budget",
        "100% of the best possible budget squad",
        "the best squad the rules allow inside the 100.0m budget",
        "Based on the model's optimal squad",
        "the highest expected-points squad",
        # viidennella kierroksella lisatyt, joihin alkuperainen ei osunut
        "the best team you can build",
        "nothing better exists",
        "the maximum points available",
        "unbeatable squad",
        "the best XI money can buy",
        "the perfect XI",
        "el mejor equipo posible",
        "o melhor time possivel",
    ]
    for t in tunnetut:
        assert RE_KUVIO.search(t), t
        assert not RE_SALLITTU.search(t), t


def test_kuvio_ei_osu_korvaajasuosituksiin():
    """Negatiivinen kontrolli kuviolle: liian valja kuvio on yhta paha kuin
    liian kapea. "best available player" on korvaajasuositus, ei vaite
    budjettioptimista, ja se esiintyy kolmella sivulla."""
    ei_vaitteita = [
        "the best available player in the same position",
        "we show the best available replacement",
        "picks the best available option",
    ]
    for t in ei_vaitteita:
        assert not RE_KUVIO.search(t), t


def test_sallittu_kuvio_ei_kaada_hedgattuja_muotoja():
    hedgatut = [
        "the best XI our search found inside the 100.0m budget",
        "The search is not proven optimal, so this is a best effort",
        "the strongest squad our search finds",
        "not a proven optimum. RSL rules: 100.0 budget",
        "Beam search, not a global optimum.",
        "Half the projected points of the strongest squad we found.",
    ]
    for t in hedgatut:
        assert RE_SALLITTU.search(t), t


def test_kommenttien_riisuminen_ei_syo_markdown_otsikoita():
    """🔴 `#`-riisuminen soi llms.txt:n 11 Markdown-otsikkoa, ja kielletty
    vaite otsikossa olisi ollut nakymaton."""
    llms = next(p for p in PINNAT if p.name == "llms.txt")
    myrkytetty = llms.read_text(encoding="utf-8") + \
        "\n## The best possible squad the rules allow\n"
    riisuttu = _riisu_kommentit(llms, myrkytetty)
    assert "The best possible squad" in riisuttu
    assert RE_KUVIO.search(riisuttu.splitlines()[-1])


def test_kommentti_ei_ole_copya_koodipinnoilla():
    """Vastasuunta: koodipinnalla kommentti EI saa laukaista porttia, muuten
    portin oma selittava kommentti kaataisi sen itsensa."""
    kortti = next(p for p in PINNAT if p.name == "career.html")
    riisuttu = _riisu_kommentit(
        kortti, '<p>ok</p><!-- best possible squad, selitys -->')
    assert not RE_KUVIO.search(riisuttu)


# --- sallivuuden laajuus ----------------------------------------------------

def test_hedge_ei_vapauta_koko_lohkoa():
    """🔴 Kolmen rivin ikkuna vapautti `career.html`:n korttilohkon riveilta
    529-546 kokonaan, eli tasan sen alueen jota muokattiin nelja kertaa."""
    teksti = ("x" * 400 + "our search found\n"
              + "y" * (SALLIVUUS_MERKKIA + 200)
              + "\nThe best possible squad the rules allow.\n")
    osumat = [m for m in RE_KUVIO.finditer(teksti)
              if not RE_SALLITTU.search(
                  teksti[max(0, m.start() - SALLIVUUS_MERKKIA):
                         m.end() + SALLIVUUS_MERKKIA])]
    assert osumat, "kaukainen hedge vapautti vaitteen"


def test_portitettu_ternaari_lapaisee():
    """Vastasuunta: oikein portitettu Svelte-ternaari EI saa kaatua. Lippu on
    mitattuna 137 merkin paassa vaitteesta."""
    polku = next((p for p in PINNAT if p.name == "RateTeam.svelte"), None)
    if polku is None:
        pytest.skip("RateTeam.svelte ei ole pintalistalla")
    osumat = [o for o in _osumat(polku) if "the rules allow" in o]
    assert not osumat, osumat


# --- itse invariantti -------------------------------------------------------

def test_yksikaan_julkinen_pinta_ei_vaita_optimia():
    loydot: list[str] = []
    for polku in PINNAT:
        if polku.name in SALLITUT:
            continue
        loydot += _osumat(polku)
    assert not loydot, (
        "Ehdoton optimaalisuusvaite julkisella pinnalla, vaikka "
        "optimal_xi_proven() on tuotannossa False (mitattu 4.9: oma runko "
        "voittaa vertailukohdan 11,65 xP:lla). Hedgaa vaite tai kirjoita "
        "perustelu SALLITUT-listaan:\n  " + "\n  ".join(loydot))


# --- poikkeuslistan kunto ---------------------------------------------------

def test_poikkeuslistalla_ei_ole_kuolleita_riveja():
    nimet = {p.name for p in PINNAT}
    odotetut = set(SALLITUT) if APP.exists() else set(SALLITUT) - APP_RIVIT
    kuolleet = sorted(odotetut - nimet)
    assert not kuolleet, kuolleet


def test_jokaisella_poikkeuksella_on_perustelu():
    tyhjat = [k for k, v in SALLITUT.items() if len((v or "").strip()) < 30]
    assert not tyhjat, tyhjat


def test_poikkeuslistalla_olevat_oikeasti_osuvat():
    """Poikkeus jolla ei ole osumaa on kuollut painolasti."""
    turhat = [p.name for p in PINNAT
              if p.name in SALLITUT and not _osumat(p)]
    assert not turhat, (
        "Naita ei tarvitse enaa vapauttaa, poista SALLITUT-listalta: %s"
        % sorted(set(turhat)))


@pytest.mark.parametrize("nimi", ["career.html", "llms.txt"])
def test_mutaatio_kaataa_portin(nimi):
    polku = next(p for p in PINNAT if p.name == nimi)
    teksti = polku.read_text(encoding="utf-8", errors="replace")
    myrkytetty = teksti + "\n" + "z" * 600 + \
        "\nThe best possible squad the rules allow.\n"
    riisuttu = _riisu_kommentit(polku, myrkytetty)
    osumat = [m for m in RE_KUVIO.finditer(riisuttu)
              if not RE_SALLITTU.search(
                  riisuttu[max(0, m.start() - SALLIVUUS_MERKKIA):
                           m.end() + SALLIVUUS_MERKKIA])]
    assert osumat, nimi
