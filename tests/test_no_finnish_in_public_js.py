# -*- coding: utf-8 -*-
"""KIELIPORTTI: suomea ei shipata julkisille englanninkielisille sivuille.

TAMA PORTTI ON OLLUT SOKEA KAHDESTI, molemmat kerrat samasta syysta:
mittari oli LISTA, ja lista oli lyhyempi kuin kieli.

  1. Sanalista (["kortti","rajaus","lukee","eika",...]). Yksikaan ei
     esiintynyt riveilla jotka oikeasti shippasivat. Portti vihrea, suomi ulos.
  2. Morfologia ilman -ssa-paatetta (mukana vain ssaan/staan). Rivi
     "// tekstina. Sama sopimus kuin SPA:ssa." meni lapi ja shippasi NELJALLE
     julkiselle sivulle portin ollessa vihrea.

Kolmas versio ei ole lista vaan KAKSIPORTAINEN MITTARI, koska pelkka
sijapaate on liian heikko yksin: "Villa", "Costa", "Marseille" ja "delta"
paattyvat suomen sijapaatteisiin (lla/sta/lle/lta), ja FPL-koodikannassa
joukkueen nimi kommentissa on lahempana varmaa kuin epatodennakoista.

  VAHVA   skandi tai suomen funktiosana        -> yksi riittaa
  HEIKKO  sijapaate PIENELLA alkukirjaimella   -> kaksi samalla rivilla
          (isolla alkava on erisnimi eika taivutusmuoto)

SAANTO: jokainen muutos mittariin on istutettava molempiin kontrolleihin.
Ilman istutusta et tieda korjasitko reian vai listan.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SIVUT = ["points", "expected-points", "xg-leaders", "stats", "defence",
         "defcon", "differentials", "price-changes", "team-news",
         "best-captain", "club-best", "minutes-accuracy", "model-xi",
         "notes", "predicted-lineups"]

# 🔴 VERBIPAATTEET OVAT VAHVOJA, EIVAT HEIKKOJA. Kolmas versio siirsi
# ttaa/taan/tiin heikoiksi ja portti muuttui HEIKOMMAKSI kuin edellinen:
# 15/20 realistisesta suomenkielisesta rivista meni lapi, koska yksi verbi
# ei riita kahdeksi heikoksi osumaksi. Vaarat positiivit joita pelattiin
# olivat kuvitteellisia - kiinni jaivat vain "vanilla umbrella" ja
# "chinchilla, guerrilla", ei yhtaan joukkue- tai pelaajanimea.
# Vaihtokauppa oli vaarin pain, ja se on nyt purettu.
_VAHVA = re.compile(
    r"[äöÄÖ]"
    r"|\b(?:eika|vaan|jotta|koska|mutta|silla|joten|vaikka|ilman|jokainen"
    r"|olisi|oli|onko|nayttaa|lukee|kertoo|antaa|tekee|tulee|pitaa"
    r"|kuin|sama|samat|tama|tuo|nama|siksi|nyt|vain|myos|viela|enaa"
    r"|tekstina|sopimus|rivi|rivit|sivu|arvo|luku|kesken|taulukosta|tasan"
    r"|nolla|vaite|ettei|han|lukuja|loytyi|vasta|yksi|kaksi|kortti|kortin"
    r"|taulukko|nappi|kentta|jos|ei|jotka|joka)\b"
    # Verbipaatteet: naita ei esiinny englannin sanan lopussa.
    r"|\b\w*(?:ttaa|ttaisi|taan|tiin|isesti|vat|isivat)\b",
    re.IGNORECASE)

# Sijapaatteet PIENELLA alkukirjaimella: isolla alkava on erisnimi
# ("Villa", "Costa", "Marseille"), joten se ei kelpaa signaaliksi.
_HEIKKO = re.compile(
    r"\b[a-z]\w*(?:ksessa|ssaan|staan|ssa|lla|lta|lle|sta|ksi|ista|isiin|iden)\b")


def _suomea(rivi: str) -> str | None:
    """Osuma jos rivi on suomea, muuten None."""
    m = _VAHVA.search(rivi)
    if m:
        return m.group(0)
    heikot = _HEIKKO.findall(rivi)
    return " + ".join(heikot[:2]) if len(heikot) >= 2 else None


def _kommenttirivit(html: str) -> list[str]:
    out = []
    for rivi in html.split(chr(10)):
        t = rivi.strip()
        if t.startswith("//") or t.startswith("/*") or t.startswith("*"):
            out.append(t)
    return out


def _sivu(nimi: str) -> str:
    p = ROOT / "fpl" / f"{nimi}.html"
    if not p.exists():
        pytest.skip(f"{p.name} ei ole rakennettu")
    return p.read_text(encoding="utf-8", errors="replace")


@pytest.mark.parametrize("sivu", SIVUT)
def test_no_finnish_in_shipped_js(sivu):
    for t in _kommenttirivit(_sivu(sivu)):
        osuma = _suomea(t)
        assert not osuma, (
            f"{sivu}: suomea shipatussa JS:ssa ({osuma!r}): {t[:90]!r}")


def test_gate_catches_planted_finnish():
    """Negatiivinen kontrolli. Jokainen rivi tassa on OIKEASTI shipannut tai
    lapaissyt jonkin aiemman version portista. Ala poista rivia vaikka se
    nayttaisi turhalta - se on todiste siita etta portti nakee sen luokan."""
    istutetut = [
        # sanalistaversion lapi menneet
        "// nolla olisi vaite ettei han laukonut kertaakaan.",
        "// lukuja GW-otsikon alla, loytyi vasta livesivulta",
        # ensimmaisen morfologiaversion lapi mennyt, shippasi 4 sivulle
        "// tekstina. Sama sopimus kuin SPA:ssa.",
        # oma uusi kommenttini, portti nappasi sen heti
        "// Tasan yksi spec per sivu. Kahdella taulukolla querySelector ottaisi",
        "// sama kuin ennen",
        "// tama on kesken",
        "// kortti lukee taulukosta",
        "// tama rivi kertoo mika sarake on lajiteltu",
        "// jokainen kortti nayttaa saman rajauksen",
        # kaksi heikkoa signaalia, ei yhtaan vahvaa
        "// haetaan listalta ja kirjoitetaan tiedostoon",
        # 🔴 Nama SEITSEMAN menivat lapi kolmannesta versiosta, joka oli
        # yhdelle luokalle heikompi kuin toinen. Portti mittasi sen itse.
        "// palauttaa null jos dataa ei ole",
        "// kortin rivit tulevat palvelimelta",
        "// huom: FPL:n API palauttaa nollan",
        "// yksi kortti per taulukko",
    ]
    for rivi in istutetut:
        assert _suomea(rivi), f"portti ei nae istutettua suomea: {rivi!r}"


def test_gate_does_not_flag_english():
    """Vaara positiivinen olisi yhta paha: portti hylkaisi kelvollisen rivin.

    Mukana joukkueiden ja pelaajien nimia, koska ne ovat FPL-koodikannassa
    kommenteissa lahempana varmaa kuin epatodennakoista."""
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
    ]
    for rivi in englanti:
        osuma = _suomea(rivi)
        assert not osuma, f"portti hylkasi englannin ({osuma!r}): {rivi!r}"
