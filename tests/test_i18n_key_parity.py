"""PORTTI: mobiilin kolme lokaalia kantavat SAMAT avaimet.

🔴 TAMA ON TOINEN KERTA KUN i18n-PARITEETTI JAI KIINNI VASTA JALKIKATEEN.

25.8.2026 mitattiin nelja avainta joita oli vain englanniksi:
    fantasy.xp.goal_outlook · fantasy.xp.source_override
    fantasy.xp.source_price_blend · fantasy.xp.source_price_prior

`lib/i18n.ts:152` on `dicts[locale]?.[key] ?? dicts.en[key] ?? key`, eli
puuttuva avain PUTOAA ENGLANTIIN. Se ei kaada mitaan: espanjan- ja
portugalinkielinen kayttaja nakee neljä englanninkielista riviä keskella
kaannettya nakymaa, eika mikaan kerro siita. Sama vikaluokka kuin 10.8 loydetty
suomenkielinen caveat englanninkielisella sivulla, vain toiseen suuntaan.

🔴 JA OMA TARKISTUKSENI EI NAHNYT SITA. Ajoin pariteettivertailun regexilla
`fantasy\\.(?:chips|wildcard)\\.[a-z_]+` ja raportoin "ei eroja". Mittaus oli
oikea omalle rajaukselleen; TIIVISTYS oli laajempi kuin mittaus. Jos ero olisi
osunut chip-avaimiin, sama tarkistus olisi kertonut sen — mutta se ei olisi
kertonut tasta. Portti lukee nyt KAIKKI avaimet.
"""
from __future__ import annotations

import re
from pathlib import Path

I18N = Path(__file__).resolve().parents[1].parent / "goaliq-app" / "lib" / "i18n"
LOKAALIT = ("en", "es", "pt")

# Avain on rivin alussa lainausmerkeissa ja sita seuraa merkkijonoarvo.
AVAIN = re.compile(r'"([a-z][a-zA-Z0-9_.]+)":\s*"')


def _avaimet(loc: str) -> set[str] | None:
    p = I18N / f"{loc}.ts"
    if not p.exists():
        return None
    return set(AVAIN.findall(p.read_text(encoding="utf-8")))


def test_kaikilla_lokaaleilla_on_samat_avaimet():
    """🔴 Puuttuva avain ei kaada mitaan — se putoaa englantiin ja renderoityy
    keskella kaannettya nakymaa. Siksi tama tarvitsee portin eika arvostelua."""
    perus = _avaimet("en")
    if perus is None:
        return  # mobiilirepo ei ole mountattu
    virheet = []
    for loc in LOKAALIT[1:]:
        muut = _avaimet(loc)
        if muut is None:
            continue
        puuttuu = sorted(perus - muut)
        yli = sorted(muut - perus)
        if puuttuu:
            virheet.append(f"{loc}: puuttuu {len(puuttuu)} — {puuttuu[:6]}")
        if yli:
            # Ylimaarainen avain on eri vika: se on kaannos jota mikaan ei
            # kayta, ja se jaa elamaan kun englanninkielinen poistetaan.
            virheet.append(f"{loc}: ylimaaraisia {len(yli)} — {yli[:6]}")
    assert not virheet, "i18n-avainpariteetti rikki:\n" + "\n".join(virheet)


def test_portti_lukee_oikeasti_avaimia():
    """🔴 Portti joka ei loyda avaimia lapaisee tyhjana. Sama vikaluokka kuin
    "kontrolli lapaisi tyhjana": nolla verrattua rivia nayttaa onnistumiselta.
    """
    perus = _avaimet("en")
    if perus is None:
        return
    assert len(perus) > 500, (
        f"vain {len(perus)} avainta — onko AVAIN-regex rikki?")


def test_regex_nakee_myos_pistein_erotetut_avaimet():
    """🔴 NEGATIIVINEN KONTROLLI OMALLE VIRHEELLENI. Aiempi tarkistukseni
    rajasi avaimet kahteen etuliitteeseen eika siksi nahnyt `fantasy.xp.*`
    -avaimia lainkaan. Tama pinnaa sen etta regex kattaa mielivaltaiset
    pisteelliset avaimet.
    """
    otos = '  "fantasy.xp.source_price_blend": "Part model, part price",\n'
    assert AVAIN.findall(otos) == ["fantasy.xp.source_price_blend"]
    # ...eika osu kommentteihin tai muihin merkkijonoihin
    assert AVAIN.findall('  // "ei.avain": ei ole arvoa\n') == []
