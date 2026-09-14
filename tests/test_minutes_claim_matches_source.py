"""Portti: minuuttiharhaa koskeva luku on sidottu MITTAUKSEEN, ei toiseen pintaan.

TAUSTA (12.9.2026, I18N-MINUUTTIVAITE-DRIFT). Vaite "players we projected at
80+ minutes came in about 14 minutes lower than we said" eli SEITSEMALLA
pinnalla: `lib/i18n/{en,es,pt}.ts` kahdella avaimella kussakin, ja pro-SPA:n
`XpTable.svelte`. Jokainen kasin kirjoitettu, eli jokainen voi eriytya.

Jonorivin alkuperainen premissi (web korjasi, mobiili ei) oli VAARIN -- kaikki
sanoivat 14. Uusintamittaus paljasti oikean vian:

    n=132   keskiarvo +13.8 min   MEDIAANI +0.0 min
    39 % osuu viiden minuutin sisaan, 21 % on yli 30 min pielessa

Luku 14 oli siis oikein, mutta LAUSE oli vaara: se luki keskiarvon
TYYPILLISENA tapauksena, ja tyypillinen 80+ pelaaja osuu kohdalleen.
Keskiarvon tekee hanta.

MEKANISMI. Kaksi ehtoa, molemmat LUKUUN sidottuja eivatka sanalistaan
(sanalista vanhenisi ja se on kolmella kielella):

  (1) Jokaisella pinnalla on sama luku kuin artefaktissa. Jos mittaus
      muuttuu, copy on stale ja tama kaatuu.
  (2) Jos keskiarvo ja mediaani eroavat olennaisesti, keskiarvoa EI SAA
      julkaista yksin: pinnan on kannettava myos hannan luku. Tama on
      rakenteellinen ehto, ei sanamuoto -- se pitaa millä tahansa kielella.

REIKA TUKITTU (14.9.2026, MINUUTTIPORTTI-TYYPILLINEN). Ehto (2) vaati vain
etta hannan LUKU on lasna (`\b30\b`), ei etta tyypillinen tapaus sanotaan.
Teksti saattoi kantaa seka 10:n etta 30:n kertomatta koskaan etta nelja
kymmenesta osuu kohdalleen, ja lapaista: "came in about 10 minutes lower,
and a few were 30 minutes out" (muisti: portti-joka-etsii-merkkijonoa-ei-
mittaa-arvoa). Kolmas ehto alla (`test_typical_case_fraction_is_bound_to_
measured_share`) ei enaa etsi lukua vaan LUKUSUHDETTA: se poimii jokaisesta
pinnasta kaikki "<luku> in/of <luku>" (+ es "de cada" / pt "em cada")
-murteet, muuntaa ne osuuksiksi ja vaatii etta yksi osuu lahelle
`share_within_5`:tta (tyypillinen tapaus) ja toinen lahelle `share_over_30`:tta
(hanta) — MOLEMMAT artefaktista, ei sanalistasta. Murre ei ole sidottu
tiettyihin sanoihin ("four"/"ten"): jos mittaus muuttuu 0,4:sta 0,3:aan,
teksti jonka pitaa lukea "three in ten" mutta lukee yha "four in ten" ei
enaa osu toleranssiin ja portti kaatuu — sama rakenne kuin ehdolla (1).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LAHDE = ROOT / "data" / "preseason_minutes_bias.json"
SPA = ROOT / "web" / "pro-spa" / "src" / "lib" / "components" / "XpTable.svelte"
APP = ROOT.parent / "goaliq-app" / "lib" / "i18n"
AVAIMET = ("fantasy.xp.minutes_note", "fantasy.xp.method_note")

# Kynnys jonka yli keskiarvo ja mediaani "eroavat olennaisesti".
ERO_KYNNYS_MIN = 5.0

# Kynnys tulee MITTARISTA. Kovakoodattu 30 jaisi voimaan vaikka mittari
# vaihtaisi rajan (portti vaatisi lukua jota artefakti ei enaa kanna).
from scripts.measure_preseason_minutes_bias import (  # noqa: E402
    HANTA_RAJA, OSUMA_RAJA,
)


def _mittaus() -> dict:
    assert LAHDE.exists(), (
        f"{LAHDE.relative_to(ROOT)} puuttuu. Aja "
        "scripts/measure_preseason_minutes_bias.py. Artefakti on repossa "
        "(.gitignore-poikkeus), jotta tama testi ei ohita itseaan CI:ssa."
    )
    return json.loads(LAHDE.read_text(encoding="utf-8"))


def _vaadi_molemmat_repot() -> None:
    """goaliq-app on privaatti eika ole fp:n CI-checkoutissa; mobiiliportti
    ajetaan lokaalisti. Skip on EKSPLISIITTINEN, ei hiljainen lapaisy -- sama
    konventio kuin tests/test_chip_ev_render_claims.py:204. Ilman tata
    `assert len(pinnat) == 7` kaataisi tests.yml:n JOKAISESSA ajossa."""
    if not APP.exists():
        pytest.skip("goaliq-app ei ole mountattu (CI): mobiilipinnat lokaalisti")


def _pinnat() -> dict[str, str]:
    """Kaikki seitseman pintaa. Puuttuva pinta kaataa, ei ohita."""
    ulos: dict[str, str] = {}
    if SPA.exists():
        teksti = SPA.read_text(encoding="utf-8")
        # vain nakyva kappale, ei kommentteja
        teksti = re.sub(r"<!--.*?-->", " ", teksti, flags=re.S)
        ulos["pro-spa/XpTable.svelte"] = teksti
    if APP.exists():
        for kieli in ("en", "es", "pt"):
            p = APP / f"{kieli}.ts"
            if not p.exists():
                continue
            s = p.read_text(encoding="utf-8")
            for avain in AVAIMET:
                m = re.search(rf'"{re.escape(avain)}":\s*"([^"]*)"', s)
                assert m, f"{kieli}.ts: avainta {avain} ei loytynyt"
                ulos[f"{kieli}.ts:{avain}"] = m.group(1)
    return ulos


# Vaite paattyy tahan lauseeseen kaikilla kolmella kielella.
_LOPPU = ("results arrive", "resultados de 2026/27")


def _vaiteosa(teksti: str) -> str:
    """Vain se kappale jossa minuuttivaite on.

    12.9 portti mittasi etta `teksti[i:]` palautti SPA:lla 13 585 merkkia
    tiedoston loppuun asti: mika tahansa myohempi `30` (CSS 30px, colspan,
    tooltip) olisi tayttanyt hannan vaatimuksen. Fail-open rakenteeltaan
    (muisti: rivi-ei-ole-skannausyksikko).
    """
    for ankkuri in ("three summers", "tres veranos", "três verões"):
        i = teksti.find(ankkuri)
        if i == -1:
            continue
        osa = teksti[i:]
        loppu = min((j for j in (osa.find(x) for x in _LOPPU) if j != -1),
                    default=-1)
        return osa[:loppu + 40] if loppu != -1 else osa[:600]
    return ""


def test_pintoja_on_seitseman():
    """Ilman tata koko tiedosto voisi olla vihrea nollalla pinnalla."""
    _vaadi_molemmat_repot()
    pinnat = _pinnat()
    assert len(pinnat) == 7, f"loydetty {len(pinnat)} pintaa: {sorted(pinnat)}"


def test_jokainen_pinta_sanoo_saman_luvun_kuin_mittaus():
    _vaadi_molemmat_repot()
    pinnat = _pinnat()
    ka = round(_mittaus()["mean"])
    viat = [n for n, t in pinnat.items()
            if not re.search(rf"\b{ka}\b", _vaiteosa(t))]
    assert not viat, (
        f"nama pinnat eivat sano mitattua keskiarvoa ({ka} min): {viat}. "
        "Mittaus: data/preseason_minutes_bias.json "
        "(scripts/measure_preseason_minutes_bias.py)."
    )


# --------------------------------------------------------------------------
# MINUUTTIPORTTI-TYYPILLINEN: luku EI riita, murteen on ilmaistava OSUUS.
# --------------------------------------------------------------------------

# Lukusanat 1-10 kolmella kielella. SPA on aina englantia; mobiilin kolme
# kielta kayttavat omaa sanamuotoaan ("X in Y" / "X de cada Y" / "X em cada Y").
_LUKUSANAT = {
    "en": {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
           "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10},
    "es": {"uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
           "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10},
    "pt": {"um": 1, "dois": 2, "tres": 3, "três": 3, "quatro": 4, "cinco": 5,
           "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10},
}
_LIITOS = {"en": r"in", "es": r"de\s+cada", "pt": r"em\s+cada"}


def _fractions_in_text(teksti: str) -> list[float]:
    """Poimii kaikki '<luku> in/de cada/em cada <luku>' -murteet ja palauttaa
    niiden numeeriset osuudet (esim. "four in ten" -> 0.4).

    EI sido tiettyihin sanoihin: mika tahansa kahden lukusanan pari samalla
    liitoksella kelpaa, joten testi joka kayttaa tata mittaa OSUUTTA eika
    hae kiinteaa sanajonoa. Kaikki kolme kielta tarkistetaan aina, koska
    SPA ja i18n-tiedostot voivat molemmat paatya samaan tekstiin.
    """
    t = teksti.lower()
    out: list[float] = []
    for kieli, sanat in _LUKUSANAT.items():
        sana_regex = "|".join(sorted(sanat, key=len, reverse=True))
        pattern = re.compile(
            rf"\b({sana_regex})\b\s+{_LIITOS[kieli]}\s+\b({sana_regex})\b")
        for m in pattern.finditer(t):
            a, b = sanat[m.group(1)], sanat[m.group(2)]
            if b:
                out.append(a / b)
    return out


def test_typical_case_fraction_is_bound_to_measured_share():
    """MINUUTTIPORTTI-TYYPILLINEN: 30 (hannan luku) LASNA ei riita — pinnan
    on kannettava lukusuhde joka on LAHELLA mitattua share_within_5:tta
    (tyypillinen tapaus) JA lukusuhde lahella share_over_30:tta (hanta).
    Kumpikaan raja ei ole sanalista: molemmat tulevat artefaktista, joten
    jos mittaus muuttuu eika teksti seuraa, tama kaatuu."""
    _vaadi_molemmat_repot()
    pinnat = _pinnat()
    m = _mittaus()
    ero = abs(m["mean"] - m["median"])
    if ero < ERO_KYNNYS_MIN:
        pytest.skip(f"keskiarvo ja mediaani eroavat vain {ero:.1f} min")
    within5, over30 = m["share_within_5"], m["share_over_30"]
    TOL = 0.05
    viat = []
    for nimi, teksti in pinnat.items():
        osat = _fractions_in_text(_vaiteosa(teksti))
        if not any(abs(f - within5) <= TOL for f in osat):
            viat.append(f"{nimi}: ei lukusuhdetta lahella tyypillista "
                        f"osumaa ({within5:.0%}), loydetyt: {osat}")
        if not any(abs(f - over30) <= TOL for f in osat):
            viat.append(f"{nimi}: ei lukusuhdetta lahella hantaa "
                        f"({over30:.0%}), loydetyt: {osat}")
    assert not viat, (
        f"share_within_5={within5:.0%}, share_over_30={over30:.0%} "
        "(data/preseason_minutes_bias.json). Nama pinnat eivat kanna "
        "kumpaakin lukusuhdetta:\n  " + "\n  ".join(viat))


def test_kontrolli_luku_ilman_lukusuhdetta_ei_riita():
    """NEGATIIVINEN KONTROLLI: moduulin docstringin oma esimerkkilause
    ("came in about 10 minutes lower, and a few were 30 minutes out")
    kantaa hannan LUVUN (30) muttei yhtaan lukusuhdetta. VANHA portti
    (pelkkaa lukua etsiva `\\b30\\b`) olisi paastanyt taman lapi; uusi
    `_fractions_in_text` nakee etta murre puuttuu kokonaan."""
    huono = ("Across the last three summers, players we projected at 80+ "
             "minutes came in about 10 minutes lower, and a few were 30 "
             "minutes out. The gap closes as 2026/27 results arrive.")
    osa = _vaiteosa(huono)
    assert re.search(r"\b30\b", osa), "kontrolli: hannan luku loytyy tekstista"
    assert _fractions_in_text(osa) == [], (
        "kontrolli: taman lauseen PITAA olla ilman lukusuhdetta — jos tama "
        "loytaa jotain, tunnistin on liian salliva")


def test_keskiarvoa_ei_julkaista_yksin_kun_tyypillinen_eroaa():
    """TAMA on portin ydin.

    Kun keskiarvo ja mediaani eroavat olennaisesti, keskiarvo yksin LUKEE
    tyypillisena tapauksena vaikka se ei ole sellainen. Ehto ei ole
    sanamuoto: pinnan on kannettava myos hannan luku, jolloin lukija nakee
    mista keskiarvo tulee. Pitaa milla tahansa kielella.
    """
    _vaadi_molemmat_repot()
    pinnat = _pinnat()
    m = _mittaus()
    ero = abs(m["mean"] - m["median"])
    if ero < ERO_KYNNYS_MIN:
        pytest.skip(f"keskiarvo ja mediaani eroavat vain {ero:.1f} min")
    hanta = HANTA_RAJA
    viat = [n for n, t in pinnat.items()
            if not re.search(rf"\b{hanta}\b", _vaiteosa(t))]
    assert not viat, (
        f"keskiarvo {m['mean']:+} ja mediaani {m['median']:+} eroavat "
        f"{ero:.1f} min, joten keskiarvoa ei saa julkaista yksin. Nama "
        f"pinnat eivat kerro hantaa ({hanta} min): {viat}."
    )


def test_kontrolli_vanha_lause_kaatuisi():
    """Fikstuuri on se teksti joka oli livena 12.9 asti."""
    vanha = ("Across the last three summers, players we projected at 80+ "
             "minutes came in about 14 minutes lower than we said, and the "
             "gap closes as 2026/27 results arrive.")
    osa = _vaiteosa(vanha)
    assert re.search(r"\b14\b", osa), "kontrolli: luku loytyy"
    assert not re.search(r"\b30\b", osa), (
        "kontrolli: vanha lause EI kerro hantaa, joten ehdon 3 pitaa kaatua "
        "siihen. Jos tama assertio kaatuu, ehto on fail-open."
    )
