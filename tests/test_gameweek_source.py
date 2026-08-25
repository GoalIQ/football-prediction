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


# ---------------------------------------------------------------------------
# completed_gameweeks: payload kertoo mika kierros on ohi
# ---------------------------------------------------------------------------
from src.models.fpl_gameweek import (  # noqa: E402
    completed_gameweeks, display_gameweek)


def _f(gw, ms):
    return {"gameweek": gw, "kickoff_ms": ms}


def _nyt_ms():
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc).timestamp() * 1000


def test_completed_vaatii_ETTA_JOKAINEN_ottelu_on_alkanut():
    """🔴 `all` eika `any`. Yksikin alkamaton ottelu tarkoittaa etta kierros
    on kesken, ja silloin pinnan kuuluu pysya siina."""
    now = _nyt_ms()
    ohi = [_f(1, now - 86400000) for _ in range(10)]
    kesken = [_f(2, now - 3600000)] * 9 + [_f(2, now + 3600000)]
    assert completed_gameweeks(ohi + kesken) == [1]


def test_completed_ei_nojaa_fpl_finished_lippuun():
    """🔴 Mitattu 25.8: FPL:n `finished` oli False 14 h viimeisen ottelun
    jalkeen, ja aiemmin samana paivana ottelut olivat `finished: False`
    vaikka ne oli pelattu. Kickoff-aika ei voi laahata."""
    now = _nyt_ms()
    fx = [{"gameweek": 1, "kickoff_ms": now - 86400000, "finished": False}]
    assert completed_gameweeks(fx) == [1], "lippu ei saa vaikuttaa"


def test_completed_ohittaa_kickoffittomat():
    """Kickoffiton ottelu (siirretty, TBD) ei saa tehda kierroksesta
    'paattynytta' eika estaa muita kierroksia."""
    now = _nyt_ms()
    assert completed_gameweeks([{"gameweek": 3}]) == []
    assert completed_gameweeks([_f(1, now - 1000), {"gameweek": 1}]) == [1]


def test_display_kayttaa_completed_listaa_ilman_fixtureita():
    """🔴 rate_teamin payloadissa EI ole kickoff-aikoja lainkaan, joten se ei
    voisi paatella kierroksen paattymista. Siksi builderi emitoi listan."""
    kesken = {"next_gameweek": 1, "deadline_gameweek": 2,
              "completed_gameweeks": []}
    ohi = {"next_gameweek": 1, "deadline_gameweek": 2,
           "completed_gameweeks": [1]}
    assert display_gameweek(kesken) == 1, "kesken kierroksen pysytaan"
    assert display_gameweek(ohi) == 2, "kierros ohi -> siirrytaan"


def test_display_vanha_payload_ei_kaadu():
    """Kentta puuttuu -> entinen kaytos, ei poikkeusta."""
    assert display_gameweek({"next_gameweek": 1, "deadline_gameweek": 2}) == 2
    assert display_gameweek({"next_gameweek": 1}) == 1
