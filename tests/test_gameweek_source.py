"""PORTTI: ennustepinta ei saa lukea `next_gameweek`:ia suoraan (25.8.2026).

🔴 MIKSI TAMA PORTTI ON OLEMASSA
Sama vikaluokka on loytynyt NELJASTI kolmessa viikossa, joka kerta eri
tiedostosta ja joka kerta vasta tuotannosta:

    22.8  siirtosuunnittelu ehdotti siirtoa kierrokselle joka oli jo lukittu
    24.8  chip-EV tarjosi chip-ikkunaa kierrokselle jonka deadline oli mennyt
    25.8  jakokortin oletus osui jo pelattuun kierrokseen
    25.8  /fpl-sivu naytti nollapeliprojektiot jo pelatuille otteluille

Yksittaisten korjausten sijaan vastaus on nyt yhdessa moduulissa
(`src/models/fpl_gameweek.py`), ja tama portti estaa viidennen esiintyman:
uusi kutsupaikka joka lukee `meta.get("next_gameweek")` suoraan kaataa ajon,
ellei se ole ALLOWLISTilla perusteluineen.

🔴 PORTTI EI OLE MIELIPIDE VAAN MITATTU: `next_gameweek` johdetaan FPL:n
`is_current`/`is_next`-lipuista jotka laahaavat tunteja. Mitattu 25.8 klo
09:05 UTC: GW1 pelattiin 21.-24.8, kaikki 10 ottelua `finished`, mutta
`event.finished` False, `data_checked` False ja `is_current` YHA True.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Tiedostot joissa `next_gameweek`:in suora luku on OIKEIN. Jokaisella on syy.
# 🔴 Ala lisaa tanne uutta riviä ilman etta kirjoitat syyn viereen - koko
# portin arvo on siina etta poikkeus vaatii perustelun.
SALLITUT = {
    # Moduuli joka MAARITTELEE vastauksen.
    "src/models/fpl_gameweek.py": "helper itse",
    # Lukee kentan mutta EI kierroksen valintaan.
    "src/models/fpl_fit.py": "emittoi kentan (echo payloadiin)",
    "scripts/build_spl_phase0.py": "emittoi kentan (SPL)",
    # Kayttaa TARKOITUKSELLA kuluvaa kierrosta: "Team xP, GW1" kesken
    # kierroksen on oikein, se on mita joukkue juuri nyt keraa (Villen
    # linjaus 22.8).
    "src/models/fpl_rate_team.py": "current on oikea vastaus pistepinnalla",
    # Vertaa dl > next havaitakseen KESKEN olevan kierroksen - se on
    # legitiimi kaytto, ei kierroksen valintaa.
    "scripts/build_fpl_longtail.py": "in_progress-havainnointi (dl > next)",
    "api/main.py": "echo payloadiin + horisontti kayttaa actionablea",
}

# Hakee vain KULUTUKSEN (`.get("next_gameweek")`), ei emissiota
# (`"next_gameweek": x`). Ilman tata erottelua portti punaisi jokaisen
# builderin joka kirjoittaa kentan, ja se houkuttelisi loysentamaan sen.
KULUTUS = re.compile(r'\.get\(\s*["\']next_gameweek["\']')


def _skannaa() -> dict[str, list[int]]:
    osumat: dict[str, list[int]] = {}
    for hakemisto in ("api", "src", "scripts"):
        for f in sorted((ROOT / hakemisto).rglob("*.py")):
            rel = f.relative_to(ROOT).as_posix()
            rivit = [i for i, ln in
                     enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
                     if KULUTUS.search(ln)]
            if rivit:
                osumat[rel] = rivit
    return osumat


def _luvattomat(osumat: dict, sallitut) -> dict:
    """Erotettu omaksi funktiokseen jotta sita voi TESTATA synteettisella
    syotteella.

    🔴 Mutaatiotesti paljasti taman: kun vertailu korvattiin tyhjalla dictilla
    (`luvattomat = {}`), portti lapaisi eika yksikaan testi kaatunut. Portilla
    ei siis ollut kontrollia omalle paavaitteelleen - se olisi voinut olla
    kuollut kuukausia ja nayttanyt vihrealta.
    """
    return {k: v for k, v in osumat.items() if k not in sallitut}


def test_vertailu_nappaa_luvattoman_tiedoston():
    """Negatiivinen kontrolli portin OMALLE logiikalle synteettisella
    syotteella - ei repon todellisella tilalla, joka on (toivottavasti)
    puhdas eika siksi todista mitaan."""
    osumat = {"src/models/fpl_gameweek.py": [1], "scripts/uusi_pinta.py": [42]}
    tulos = _luvattomat(osumat, {"src/models/fpl_gameweek.py": "helper itse"})
    assert tulos == {"scripts/uusi_pinta.py": [42]}, tulos
    # ...ja tyhja allowlist nappaa kaiken
    assert len(_luvattomat(osumat, {})) == 2
    # ...ja taysi allowlist ei mitaan
    assert _luvattomat(osumat, dict.fromkeys(osumat, "syy")) == {}


def test_ennustepinta_ei_lue_next_gameweekia_suoraan():
    osumat = _skannaa()
    luvattomat = _luvattomat(osumat, SALLITUT)
    assert not luvattomat, (
        "Nama tiedostot lukevat `next_gameweek`:ia suoraan:\n"
        + "\n".join(f"  {k}: rivit {v}" for k, v in luvattomat.items())
        + "\n\nKierrosvalinta asuu src/models/fpl_gameweek.py:ssa:\n"
          "  actionable_gameweek(meta)  = mihin voi VIELA vaikuttaa "
          "(ennuste-, suunnittelu- ja jakopinnat)\n"
          "  current_gameweek(meta)     = mita joukkue juuri nyt keraa "
          "(pistepinnat)\n"
          "  display_gameweek(meta, fx) = sivu; siirtyy kun kierros on "
          "kokonaan alkanut\n"
          "Jos suora luku on oikein, lisaa tiedosto SALLITUT-listaan JA "
          "kirjoita syy."
    )


def test_allowlist_ei_sisalla_kuollutta_rivia():
    """🔴 Vanhentunut poikkeus on huonompi kuin ei porttia: se nayttaa
    harkitulta silloin kun se on vain jaanne. Jos tiedosto ei enaa lue
    kenttaa, rivi kuuluu poistaa."""
    osumat = _skannaa()
    kuolleet = sorted(set(SALLITUT) - set(osumat))
    assert not kuolleet, (
        f"SALLITUT sisaltaa rivin tiedostolle joka ei enaa lue "
        f"`next_gameweek`:ia: {kuolleet}. Poista rivi."
    )


def test_portti_nakee_oikean_kuvion():
    """Negatiivinen kontrolli: portti EI saa olla sokea sille kuviolle jota
    se vahtii. Ilman tata `KULUTUS`-regex voisi olla rikki ja portti
    lapaisisi tyhjana (vrt. kontrolli-lapaisi-tyhjana)."""
    assert KULUTUS.search('gw = meta.get("next_gameweek")')
    assert KULUTUS.search("gw = meta.get('next_gameweek')")
    assert KULUTUS.search('x = (meta or {}).get( "next_gameweek" )')
    # ...eika saa osua emissioon
    assert not KULUTUS.search('"next_gameweek": next_gw,')
    assert not KULUTUS.search('meta["next_gameweek"] = 3')


def test_skannaus_ei_ole_tyhja():
    """Portti joka ei skannaa mitaan lapaisee aina. Repossa ON legitiimeja
    kayttoja, joten tyhja tulos tarkoittaa rikkinaista skannausta."""
    osumat = _skannaa()
    assert len(osumat) >= 3, f"skannaus loysi vain {len(osumat)} tiedostoa"
