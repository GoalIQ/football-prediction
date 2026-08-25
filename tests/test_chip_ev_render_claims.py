"""PORTTI: chip-EV:n selitteet vastaavat sita mita PINTA oikeasti renderoi.

🔴 MIKSI TAMA ON ERI TIEDOSTO KUIN `test_chip_ev_comparability.py`.
Se mittaa PAYLOADIA: onko `wc_window_gws` vastauksessa, poimitaanko `best`
oikeilta riveilta. Kaikki 8 testia menivat lapi — ja julkaisuportti loysi silti
kaksi vaaraa vaitetta samasta shipista:

  note 2: "Each Wildcard row says how many rounds it covers"
     -> SPA renderoi merkinnan VAIN `best`-lohkossa, ja maski tyhjentaa
        `best`:n, joten ilmaiskayttajalle se ei renderoitynyt kertaakaan.
        Top3-ranking-lista — se paikka jossa vertailu oikeasti tehdaan —
        tulosti pelkan luvun.

  note 4: "The rougher estimate is reported separately"
     -> `best_estimate` rakennettiin ja palautettiin, mutta kumpikaan pinta ei
        renderoinut sita. Se eli vain API-vastauksessa, ja raaka JSON ei ole
        tarkistusreitti vaan este.

Kentta vastauksessa ja merkinta ruudulla ovat eri asia. Nama testit lukevat
komponenttien LAHDEKOODIA, koska Svelte-komponenttitestiajuria ei tassa repossa
ole: karkea portti joka kaataa poiston on parempi kuin ei porttia.
"""
from __future__ import annotations


import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPA = ROOT / "web" / "pro-spa" / "src" / "lib" / "components" / "ChipEv.svelte"
MOBILE = ROOT.parent / "goaliq-app" / "components" / "FantasyEdge.tsx"
I18N = ROOT.parent / "goaliq-app" / "lib" / "i18n"


def _lue(p: Path) -> str | None:
    return p.read_text(encoding="utf-8") if p.exists() else None


# ---------------------------------------------------------------------------
# C1: ikkunan pituus JOKAISELLA wildcard-rivilla, ei vain karkiluvussa
# ---------------------------------------------------------------------------
def test_spa_nayttaa_ikkunan_ranking_listassa():
    """🔴 Vertailu tehdaan top3-listassa: 38,0 (6 kierrosta) ylimpana ja 25,7
    (4 kierrosta) alimpana nayttaa ajoitussignaalilta ja on ikkunan pituus.
    Merkinta pelkassa `best`-lohkossa ei riita, koska maski tyhjentaa sen."""
    s = _lue(SPA)
    if s is None:
        return
    i = s.index("chip-top3")
    j = s.index("</table>", i)
    taulukko = s[i:j]
    # 🔴 PELKKA MERKKIJONON ETSIMINEN OLI SOKEA. Mutaatio joka korvasi EHDON
    # (`chip.key === 'wc' && w.wc_window_gws != null`) arvolla `false` lapaisi
    # testin, koska `{w.wc_window_gws}` jai spanin sisalle renderoitymatta.
    # Portti vaatii nyt seka vahdin etta arvon.
    assert "w.wc_window_gws != null" in taulukko, (
        "top3-listasta puuttuu vahti sille onko ikkunaa olemassa")
    assert "chip.key === 'wc'" in taulukko, (
        "ikkunamerkinta ei ole rajattu wildcardiin — muut chipit ovat yhden "
        "kierroksen lukuja, joten merkinta niissa olisi vaara vaite")


def test_mobiili_nayttaa_ikkunan_vaihtoehtoriveilla():
    s = _lue(MOBILE)
    if s is None:
        return
    i = s.index("const alts")
    j = s.index(".join(", i)
    lohko = s[i:j]
    assert "w.wc_window_gws != null" in lohko, (
        "mobiilin vaihtoehtoriveilta puuttuu vahti sille onko ikkunaa")
    assert "chip === 'wc'" in lohko, (
        "ikkunamerkinta ei ole rajattu wildcardiin")


def test_ikkunamerkinta_on_kolmella_lokaalilla():
    for loc in ("en", "es", "pt"):
        s = _lue(I18N / f"{loc}.ts")
        if s is None:
            continue
        assert '"fantasy.chips.over_gws"' in s, loc


# ---------------------------------------------------------------------------
# C2: karkea arvio renderoidaan, ei vain palauteta
# ---------------------------------------------------------------------------
def test_karkea_arvio_renderoidaan_molemmilla_pinnoilla():
    """🔴 Selite lupasi etta arvio "raportoidaan erikseen". Lupaus pinnasta jota
    ei ole on sama kuin vaite jota ei voi tarkistaa."""
    puuttuu = []
    for nimi, p in (("SPA", SPA), ("mobiili", MOBILE)):
        s = _lue(p)
        if s is not None and "best_estimate" not in s:
            puuttuu.append(nimi)
    assert not puuttuu, (
        f"`best_estimate` palautetaan mutta {puuttuu} ei renderoi sita")


def test_arviorivilla_on_oma_teksti_kolmella_lokaalilla():
    for loc in ("en", "es", "pt"):
        s = _lue(I18N / f"{loc}.ts")
        if s is None:
            continue
        assert '"fantasy.chips.rough_estimate"' in s, loc


# ---------------------------------------------------------------------------
# C3: alaviite ei saa luvata wildcardille rivejä joita ei ole
# ---------------------------------------------------------------------------
def test_alaviite_nimeaa_chipit_eika_lupaa_wildcardille_riveja():
    """🔴 Vanha alaviite vaitti KAIKISTA horisontin ulkopuolisista kierroksista
    etta ne kayttavat joukkuetason arviota. Wildcardille se on epatosi: rivi on
    `null` ja `top3()` suodattaa sen pois, joten lukija nakisi Wildcard-kortin
    ilman yhtaan tahdellista rivia ja alaviitteen joka lupaa niita olevan."""
    s = _lue(SPA)
    if s is not None:
        i = s.index("basis-note")
        kappale = s[i:s.index("</p>", i)]
        assert "Bench Boost" in kappale, "alaviite ei nimea chippeja"
        assert "Wildcard" in kappale, "alaviite ei kerro wildcardin poikkeusta"

    for loc in ("en", "es", "pt"):
        t = _lue(I18N / f"{loc}.ts")
        if t is None:
            continue
        m = re.search(r'"fantasy\.chips\.basis_note": "([^"]*)"', t)
        assert m, loc
        teksti = m.group(1)
        assert "Bench Boost" in teksti, (loc, "chippeja ei nimetty")
        assert "Wildcard" in teksti, (loc, "wildcardin poikkeus puuttuu")


def test_kuollutta_fallback_copya_ei_ole():
    """🔴 `ChipEv.svelte`ssa oli haara joka renderoityi vain jos `meta.notes` on
    tyhja — mita se ei koskaan ole — ja se sanoi yha vanhentunutta. Lipun takana
    oleva copy nayttaa hoidetulta eika vanhene kenenkaan silmissa."""
    s = _lue(SPA)
    if s is None:
        return
    i = s.index("<MethodNote")
    lohko = s[i:s.index("</MethodNote>", i)]
    assert "{:else}" not in lohko, (
        "MethodNotessa on yha fallback-haara joka ei koskaan renderoidy")


# ---------------------------------------------------------------------------
# Portin oma kontrolli
# ---------------------------------------------------------------------------
def test_portti_lukee_oikeat_tiedostot():
    """Portti joka ei loyda tiedostojaan lapaisee tyhjana."""
    assert _lue(SPA), "ChipEv.svelte ei loydy — portti olisi lapaissyt tyhjana"
    assert _lue(MOBILE), "FantasyEdge.tsx ei loydy"
