# -*- coding: utf-8 -*-
"""Hylatty chip-vaite ei palaa yhdellekaan pinnalle (12.9.2026).

🔴 MIKSI TAMA ON OLEMASSA. `tests/test_chip_vaite_mitataan_riveista.py` vahtii
etta PYTHON-lippu `model_plays_chips` johdetaan riveista. Mutta **yksikaan
testi ei vahtinut merkkijonoa kumallakaan klientilla**, eli sama vaite saattoi
palata copyyn ilman etta mikaan huutaisi (muisti:
`tekstikorjaus-jaa-ilman-porttia`, `hylatty-sanamuoto-palaa-uudessa-generaattorissa`).

🔴 JA PAINAVAMPI SYY: PERHE OLI VAJA. Nimesin kuusi pintaa ja greppasin
sanamuodoilla `"no juega comodines"` ja `"nao joga chips"` (paneelin muodot).
Julkaisutarkistaja loysi **nelja pintaa lisaa**, koska jakokortti sanoo saman
asian ERI SANOILLA:

    es.ts:388-389   "el modelo no usa chips"     <- kortti, EI "no juega comodines"
    pt.ts:388-389   "o modelo não usa chips"     <- kortti, EI "nao joga chips"

Pintoja on siis kymmenen, ei kuusi, ja neljä niistä on KUVASSA jota ei voi
korjata jalkikateen (muisti: `sama-vaite-monessa-sanamuodossa`,
`kortin-teksti-on-julkista-tekstia`).

Portti listaa kiellettyja MUOTOJA eika yhta merkkijonoa, ja se skannaa
molemmat repot. Uusi kielto lisataan tahan; unohduksesta syntyva vika muuttuu
kaatuvaksi testiksi.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

FP = Path(__file__).resolve().parents[1]
APP = FP.parent / "goaliq-app"

#: Kiellettyja muotoja. Jokainen on OIKEASTI ollut tuotannossa 12.9.2026.
#: Muoto, ei merkkijono: `plays? no chips` nappaa myos "play no chips".
KIELLETYT = (
    (r"plays?\s+no\s+chips", "en: habituaalinen preesens = politiikkavaite"),
    (r"no\s+juega\s+comodines", "es paneeli"),
    (r"no\s+usa\s+chips", "es kortti (eri sanamuoto kuin paneelissa)"),
    (r"n[aã]o\s+joga\s+chips", "pt paneeli"),
    (r"n[aã]o\s+usa\s+chips", "pt kortti (eri sanamuoto kuin paneelissa)"),
)

#: Pinnat joilla vaite on elanyt. Lista on portin KATTAVUUS: jos uusi pinta
#: alkaa puhua chipeista, se on lisattava tanne TAI portti ei nae sita.
PINNAT = (
    FP / "web" / "pro-spa" / "src" / "lib" / "components" / "SeasonRace.svelte",
    FP / "faq.html",
    FP / "llms.txt",
    FP / "index.html",
    FP / "fpl.html",
    FP / "scripts" / "grade_model_squad_gw.py",
    APP / "lib" / "i18n" / "en.ts",
    APP / "lib" / "i18n" / "es.ts",
    APP / "lib" / "i18n" / "pt.ts",
    APP / "components" / "SeasonRace.tsx",
    APP / "store.config.json",
)


def _luettava(txt: str) -> str:
    """Lukijan nakyma: tagit ja rivinvaihdot yhdeksi valilyonniksi.

    Ilman tata riville taittunut lupaus jaisi huomaamatta — tasan se reika
    joka ilmaisikkunan portissa mitattiin 12.9 (muisti:
    `rivi-ei-ole-skannausyksikko`).
    """
    t = re.sub(r"<[^>]+>", " ", txt)
    return re.sub(r"\s+", " ", t)


@pytest.mark.parametrize("polku", PINNAT, ids=lambda p: p.name)
def test_pinta_ei_vaita_ettei_chippeja_pelata(polku):
    if not polku.exists():
        pytest.skip(f"{polku.name} puuttuu tassa ymparistossa")
    nakyma = _luettava(polku.read_text(encoding="utf-8", errors="ignore"))
    osumat = [(kuvio, syy) for kuvio, syy in KIELLETYT
              if re.search(kuvio, nakyma, re.I)]
    assert not osumat, (
        f"{polku.name}: hylatty chip-vaite palasi — {osumat}. Malli pelasi "
        f"wildcardin GW2:ssa ja triple captainin GW3:ssa, ja ne ovat kauden "
        f"kaksi isointa lukua. Kayta `chips_played`ista johdettua lausetta."
    )


def test_kiellettyjen_kuvioiden_kate_on_mitattu():
    """Negatiivinen kontrolli: kuviot OSUVAT niihin muotoihin jotka olivat
    tuotannossa. Ilman tata lista voisi liukua kuvioiksi jotka eivat nappaa
    mitaan, ja portti olisi vihrea tyhjana."""
    olivat_tuotannossa = (
        "The model's squad is locked before every deadline and plays no chips.",
        "model {model}, you {you}, FPL points, model plays no chips",
        "El equipo del modelo se bloquea antes de cada cierre y no juega comodines.",
        "modelo {model}, tú {you}, puntos FPL, el modelo no usa chips",
        "A equipa do modelo e fixada antes de cada fecho e nao joga chips.",
        "modelo {model}, você {you}, pontos FPL, o modelo não usa chips",
    )
    for teksti in olivat_tuotannossa:
        assert any(re.search(k, teksti, re.I) for k, _ in KIELLETYT), (
            f"yksikaan kuvio ei nappaa tuotannossa ollutta muotoa: {teksti!r}")


def test_hyvaksytyt_sanamuodot_lapaisevat():
    """Ja portti ei saa olla aina punainen: julkaisutarkistajan hyvaksymat
    muodot menevat lapi."""
    hyvaksytyt = (
        "The model's squad is locked before every deadline and has played no "
        "chips so far.",
        "The model's squad is locked before every deadline. So far it has "
        "played a Wildcard in GW2 and a Triple Captain in GW3.",
        "El equipo del modelo se bloquea antes de cada cierre y hasta ahora "
        "no ha usado comodines.",
        "A equipa do modelo é fixada antes de cada fecho e até agora não "
        "usou chips.",
        "model {model} vs FPL average, official FPL points",
        "modelo {model} vs média FPL, pontos FPL oficiais",
    )
    for teksti in hyvaksytyt:
        osumat = [k for k, _ in KIELLETYT if re.search(k, teksti, re.I)]
        assert not osumat, f"hyvaksytty muoto {teksti!r} osui kuvioon {osumat}"


def test_pt_lause_ei_ole_rikki_diakriiteista():
    """🔴 Julkaisutarkistajan loydos: `pt.ts:787` luki "A equipa do modelo **e**
    fixada", ja "e" on konjunktio kun "é" on verbi — lause luki "Mallin joukkue
    JA kiinnitetty". Sama vika oli myos omissa ehdotuksissani.

    Mekaaninen tarkistus: pt:n chip-lauseissa ei saa olla muotoa " e fixada"
    eika sanaa "ate agora" ilman diakriittia.
    """
    p = APP / "lib" / "i18n" / "pt.ts"
    if not p.exists():
        pytest.skip("pt.ts puuttuu")
    txt = p.read_text(encoding="utf-8")
    rivit = [r for r in txt.split("\n") if "fantasy.race" in r]
    assert rivit, "pt.ts:sta ei loydy fantasy.race-avaimia"
    for r in rivit:
        assert " e fixada" not in r, f'"e fixada" pitaa olla "é fixada": {r}'
        assert "ate agora" not in r, f'"ate agora" pitaa olla "até agora": {r}'
        assert "nao " not in r, f'"nao" pitaa olla "não": {r}'


def test_es_chip_lause_on_mittausmuodossa():
    """es: perfekti ("hasta ahora no ha usado"), ei habituaalinen preesens.

    🔴 SIVULOYDOS JOTA EN KORJANNUT TASSA. Laajempi skannaus samalla
    kuviolla loysi `fantasy.race.premium_hint` -rivilta muodon **"capitania"**
    (oikea: "capitanía"), ja samalta rivilta myos "de donde" (oikea:
    "de dónde"). Ne ovat aitoja vikoja mutta eri perhetta kuin chip-vaite, ja
    es-copyn diakriitit kannattaa kayda YHTENA pyyhkaisyna eika yhden avaimen
    korjauksina — muuten korjaan sen mita satun katsomaan ja loput jaavat.
    -> QUEUE ES-PT-DIAKRIITTIPYYHKAISY

    Tama testi rajautuu siksi chip-avaimiin.
    """
    p = APP / "lib" / "i18n" / "es.ts"
    if not p.exists():
        pytest.skip("es.ts puuttuu")
    rivit = {k: r for r in p.read_text(encoding="utf-8").split("\n")
             for k in ("fantasy.race.no_chips", "fantasy.race.chips_played")
             if k in r}
    assert "fantasy.race.no_chips" in rivit, "es: chip-avain puuttuu"
    assert "hasta ahora" in rivit["fantasy.race.no_chips"], (
        "es: 'hasta ahora' puuttuu — lause lukisi politiikkavaitteena")
    assert "comodines" in rivit["fantasy.race.no_chips"]


def test_chip_nayttonimet_ovat_kanonissa():
    """Kanoni on isolla kirjaimella ja kaantamattomana kaikissa kielissa.
    Jos SPA:n ja mobiilin kartat erkanevat, sama chip saa kaksi nimea."""
    svelte = (FP / "web" / "pro-spa" / "src" / "lib" / "components"
              / "SeasonRace.svelte")
    tsx = APP / "components" / "SeasonRace.tsx"
    for p in (svelte, tsx):
        if not p.exists():
            pytest.skip(f"{p.name} puuttuu")
        txt = p.read_text(encoding="utf-8")
        for koodi, nimi in (("wildcard", "Wildcard"), ("bboost", "Bench Boost"),
                            ("3xc", "Triple Captain"), ("freehit", "Free Hit")):
            assert nimi in txt, f"{p.name}: chipin {koodi} nayttonimi puuttuu"
