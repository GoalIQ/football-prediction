# -*- coding: utf-8 -*-
"""Portti: kontrollimerkit lahdekoodissa tekevat regexista INERTIN.

🔴 TAUSTA (7.9.2026). Kirjoitin regexeja heredocien lapi, ja `\\b` paatyi
tiedostoon LITERAALINA BACKSPACENA (0x08). Regex nayttaa oikealta editorissa
ja grepissa, mutta se ei osu koskaan - eli portti on vihrea vaarasta syysta.
Siita on jo muisti (`regexin-b-muuttuu-backspaceksi`), ja se toistui silti
saman paivan aikana nelja kertaa.

Ensimmainen versio tasta portista loysi heti kaksi VANHAA tapausta:

  tests/test_share_card_server_rows.py:420
      re.search(r"\\x08XG\\x08", arvo)   <- piti olla \\bXG\\b
      -> `assert not re.search(...)` oli aina tosi, portti inertti

  scripts/check_llms_txt_sync.py:119
      re.sub(r"...</\\x01>", ...)        <- piti olla </\\1>
      -> script/style-lohkoja ei poistettu koskaan

🔴 JA SE OLI ITSE VAJAA (portin 23. kierros, B5). Paatelistalla oli
`.svelte` ja `.html`, mutta hakemistolista oli `("src","scripts","tests",
"api")` - joissa on **0 svelte-tiedostoa ja 1 html**. Julkinen sivusto
(28 juuritason `.html`) ja SPA (65 `.svelte`) olivat skannauksen
ulkopuolella, ja kaksi paatetta listalla eivat voineet osua mihinkaan.
Portti NAYTTI kattavammalta kuin oli.

Siksi alla on `test_kontrolli_jokainen_pate_ja_juuri_todella_skannataan`,
joka istuttaa tavun jokaiseen (juuri x pate) -yhdistelmaan ja vaatii etta
jokainen raportoidaan. Uusi pate ei voi jaada kuolleeksi.

Sallitut kontrollimerkit ovat tab, LF ja CR.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 🔴 PORTIN 24. KIERROS (B5): TASSA OLI KASIN YLLAPIDETTY JUURILISTA, ja
# sen validoiva kontrolli enumeroi SAMAN listan - puuttuva juuri oli sokea
# piste maaritelman nojalla. Mitattu: 2 820 tiedostoa listan ulkopuolella,
# mukaan lukien kaikki `fpl/*.html` ja `fpl/club/*.html` eli julkisia
# sivuja, samaa tiedostoluokkaa kuin `fpl.html` jonka vika juuri loytyi.
#
# Nyt kavellaan koko repo ja ohitetaan nimetyt hakemistot. Puuttuva
# hakemisto ei voi enaa olla sokea piste, ja kontrolli vertaa
# EHDOKASJOUKKOON eika omaan listaansa.
PAATTEET = (".py", ".js", ".mjs", ".cjs", ".ts", ".svelte", ".html", ".yml",
            ".yaml")
OHITA = {"node_modules", ".venv", "__pycache__", ".git", "build", "dist",
         ".svelte-kit", ".pytest_cache", ".mypy_cache", "htmlcov"}
SALLITUT = {9, 10, 13}


def _tiedostot():
    for f in ROOT.rglob("*"):
        if not f.is_file() or f.suffix not in PAATTEET:
            continue
        if OHITA & set(f.parts):
            continue
        yield f


def _osumat(data) -> list[tuple[int, int]]:
    """[(rivi, koodipiste)] kontrollimerkeista.

    🔴 PORTIN 25. KIERROS (B3): tama luki TAVUJA, ja C1-alue (U+0080-U+009F)
    koodautuu UTF-8:ssa `0xC2 0x8x` - kumpikaan tavu ei ole alle 32, joten
    portti oli sokea juuri sille muodolle jonka todennakoisimmin
    kirjoittaisimme:

        content:"\\2014"   ->  U+0081 + "4"     (em dashin CSS-escape)
        _osumat(...)      ->  []  eli VIHREA

    `\\25B8` jai kiinni vain koska 0o25 = 0x15 sattui olemaan alle 32.
    Mitataan siis MERKKEJA, ei tavuja, ja C1 lasketaan mukaan.
    """
    teksti = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
    ulos, rivi = [], 1
    for ch in teksti:
        k = ord(ch)
        if k == 10:
            rivi += 1
        elif (k < 32 or 127 <= k <= 159) and k not in SALLITUT:
            ulos.append((rivi, k))
    return ulos


def _skannaa() -> tuple[list[str], int]:
    ongelmat, n = [], 0
    for f in _tiedostot():
        n += 1
        for rivi, b in _osumat(f.read_bytes()):
            ongelmat.append(
                f"{f.relative_to(ROOT).as_posix()}:{rivi} 0x{b:02x}")
    return ongelmat, n


def test_lahteessa_ei_ole_kontrollimerkkeja():
    ongelmat, skannattu = _skannaa()
    assert skannattu > 300, f"skanneri loysi vain {skannattu} tiedostoa"
    assert not ongelmat, (
        "kontrollimerkkeja lahteessa - yleisin syy on regexin \\b joka on "
        "kirjoitettu heredocin lapi ja muuttunut backspaceksi (0x08). Regex "
        "nayttaa oikealta mutta EI OSU KOSKAAN:\n  " + "\n  ".join(ongelmat))


def test_kontrolli_havaitsin_loytaa_backspacen():
    """NEGATIIVINEN KONTROLLI: ilman tata portti voisi olla vihrea siksi
    ettei `_osumat` loyda mitaan."""
    assert _osumat(b'r"\\bXG\\b"') == []          # oikea, escapattu
    assert _osumat(b'r"\x08XG\x08"') == [(1, 8), (1, 8)]
    assert _osumat(b"rivi1\nrivi2\x01") == [(2, 1)]
    assert _osumat(b"\trivi\r\n") == []           # tab, CR, LF sallittuja


def test_kontrolli_skannaus_kattaa_kaikki_ehdokkaat():
    """🔴 PORTIN 24. KIERROS (B5). Edellinen versio istutti tavun jokaiseen
    (juuri x pate) -yhdistelmaan - mutta enumeroi SEN SAMAN kasin
    yllapidetyn listan jota sen piti validoida. Puuttuva juuri oli siis
    sokea piste maaritelman nojalla, ja mittaus paljasti 2 820 tiedostoa
    listan ulkopuolella.

    Nyt kontrolli laskee EHDOKASJOUKON (koko repo, ohituslista poislukien)
    ja vaatii etta skannaus kattaa sen taysin.
    """
    ehdokkaat = set()
    for f in ROOT.rglob("*"):
        if not f.is_file() or f.suffix not in PAATTEET:
            continue
        if OHITA & set(f.parts):
            continue
        ehdokkaat.add(f.resolve())
    skannatut = {f.resolve() for f in _tiedostot()}
    puuttuu = sorted(str(x.relative_to(ROOT)) for x in ehdokkaat - skannatut)
    assert not puuttuu, (
        f"{len(puuttuu)} ehdokastiedostoa jaa ulkopuolelle: {puuttuu[:15]}")
    assert len(skannatut) > 1000, (
        f"skanneri loysi vain {len(skannatut)} tiedostoa - ohituslista "
        "on liian laaja tai kavely ei toimi")


def test_kontrolli_istutettu_tavu_loytyy_jokaisesta_patteesta(tmp_path):
    """Istutetaan tavu jokaiseen PAATTEET-arvoon repojuureen ja vaaditaan
    etta jokainen raportoidaan. Uusi pate ei voi jaada kuolleeksi."""
    istutetut = []
    try:
        for pate in PAATTEET:
            f = ROOT / f"_kontrollimerkki_koe{pate}"
            f.write_bytes(b"x = 1  " + bytes([8]) + bytes([10]))
            istutetut.append(f)
        ongelmat, _ = _skannaa()
        loytyi = {o.split(":")[0] for o in ongelmat}
        puuttuu = [f.name for f in istutetut if f.name not in loytyi]
        assert not puuttuu, f"naita patteita ei skannata: {puuttuu}"
    finally:
        for f in istutetut:
            f.unlink(missing_ok=True)
    ongelmat, _ = _skannaa()
    assert not ongelmat, ongelmat


def test_sivugeneraattorien_css_ei_sisalla_kontrollimerkkeja():
    """🔴 PORTIN 24. KIERROS: LAHDESKANNAUS EI RIITA GENEROIDULLE SIVULLE.

    23. kierroksella loysin `fpl.html`:sta 0x15-merkkeja ja paattelin etta
    generaattori on oikein ja artefakti on ajautunut. **Paattely oli vaara**,
    ja CI todisti sen: seuraava refresh-ajo regeneroi sivun ja toi merkit
    takaisin. Syy oli `CSS`-vakiossa: ei-raaka merkkijono, joten CSS-escape
    luetaan OKTAALINA.

    🔴 PORTIN 25. KIERROS (B3): ensimmainen versio tasta portista ohitti
    kolme asiaa. Kaikki kolme korjattu tassa:
      1. `len(arvo) < 40` ohitti juuri sen tapauksen - `'content:"\\25B8"'`
         on 13 merkkia, eli alkuperainen bugi omana vakionaan olisi mennyt
         lapi.
      2. Vain moduulitason `str` skannattiin; dict/list/tuple-vakiot olivat
         sokeita.
      3. `MODUULIT` oli kasin yllapidetty kahden mittainen lista, vaikka
         `scripts/`issa on 27 `build_*.py`:ta.
    """
    import importlib

    # Moduulilista JOHDETAAN globista, ei yllapideta kasin.
    tiedostot = sorted((ROOT / "scripts").glob("build_*.py"))
    assert len(tiedostot) >= 20, f"vain {len(tiedostot)} builderia loytyi"

    def kavele(arvo, polku, ulos):
        if isinstance(arvo, str):
            for rivi, k in _osumat(arvo):
                ulos.append((polku, rivi, k))
        elif isinstance(arvo, dict):
            for k2, v in arvo.items():
                kavele(k2, f"{polku}.<key>", ulos)
                kavele(v, f"{polku}[{k2!r}]", ulos)
        elif isinstance(arvo, (list, tuple, set, frozenset)):
            for n, v in enumerate(arvo):
                kavele(v, f"{polku}[{n}]", ulos)

    ongelmat, tarkistettu, ohitettu = [], 0, []
    for f in tiedostot:
        nimi = f"scripts.{f.stem}"
        try:
            m = importlib.import_module(nimi)
        except Exception as e:
            # Importvirhe ei ole kontrollimerkkivika; kirjataan ja jatketaan,
            # mutta maara mitataan alla jottei lista voi tyhjentya hiljaa.
            ohitettu.append((nimi, repr(e)[:60]))
            continue
        for attr in dir(m):
            if attr.startswith("_"):
                continue
            arvo = getattr(m, attr, None)
            if isinstance(arvo, (str, dict, list, tuple, set, frozenset)):
                tarkistettu += 1
                kavele(arvo, f"{nimi}.{attr}", ongelmat)

    assert not ongelmat, (
        "generaattorin vakiossa on kontrollimerkkeja - yleisin syy on "
        "CSS-escape ei-raa'assa merkkijonossa (oktaali). Kirjoita kaksi "
        f"kenoviivaa: {ongelmat[:5]}")
    assert tarkistettu >= 100, f"vain {tarkistettu} vakiota tarkistettu"
    assert len(ohitettu) <= len(tiedostot) // 2, (
        f"yli puolet buildereista ei importtaudu: {ohitettu[:5]}")


def test_kontrolli_oktaaliescape_havaitaan():
    """NEGATIIVINEN KONTROLLI: juuri se muoto joka paasi lapi kahdesti."""
    # Ei-raaka merkkijono: Python tulkitsee \25 oktaaliksi.
    paha = 'content:"\25B8  "'
    assert _osumat(paha.encode("utf-8")) == [(1, 0x15)]
    # Oikea muoto: kaksi kenoviivaa lahteessa -> yksi tuloksessa.
    hyva = 'content:"\\25B8  "'
    assert _osumat(hyva.encode("utf-8")) == []
