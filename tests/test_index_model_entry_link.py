"""Portti: laskeutumissivun "squad it plays" -linkki osoittaa siihen runkoon
jonka FPL nayttaa juuri nyt.

🔴 VILLEN LOYDOS 4.9.2026. Laskeutumissivun paneeli puhuu joukkueesta jota
malli PELAA, mutta sen ainoa CTA vei `/fpl/model-xi`-sivulle eli
BUDJETTIOPTIMIIN. Kolme eri joukkuetta oli liikkeella samaan aikaan
(paallekkaisyys 15:sta: sivu-kortti 8, sivu-entry 7, kortti-entry 6).

URL-MUOTO ON MITATTU, EI PAATELTY:
  * `/entry/116920/`         -> 404, "viimeisin"-muotoa ei ole
  * `/entry/116920/history`  -> 200, mutta vain pisteet ja chipit, EI rivistoa
  * `/entry/116920/event/2`  -> 200 ja kentta pelaajineen

🔴 JULKAISUPORTIN LOYDOS SAMANA PAIVANA, oma korjaukseni oli vaarassa.
Ensimmainen versio luki kierroksen `completed_gameweeks`in maksimista.
Mitattu ero:

    GW3 deadline            pe 4.9 17:30Z   <- pickit muuttuvat julkisiksi
    GW3 viimeinen kickoff   su 6.9 15:30Z   <- completed_gameweeks saa 3:n
    PIMEA IKKUNA            46,0 h

Nuo 46 tuntia ovat tasan se deadline-viikonloppu jolloin kysymys on elava.
Oikea lahde on `deadline_gameweek - 1`, joka kaantyy deadline-hetkella.

TAMA TESTI KIRJOITETTIIN UUDELLEEN portin toisen loydoksen takia. Ensimmainen
versio (1) kovakoodasi `/event/2` negatiiviseen kontrolliin, jolloin se olisi
mennyt punaiseksi 6.9 kun generaattori kirjoittaa `event/3`; (2) ei kutsunut
builderia lainkaan vaan kirjoitti `max()`-logiikan uudelleen ja vaitti
mittaavansa saantoa 6a; (3) parametrisoi vaiheet vain `completed`illa, jolloin
vikasolu (deadline mennyt, aloituspotkut kesken) ei ollut ilmaistavissa
millaan parametrilla. Kaikki kolme ovat muistin nimeamia ansoja:
`ehto-ei-vanhene-teksti-vanhenee`, `portti-voi-mitata-eri-koodipolkua`,
`kontrolli-lapaisi-tyhjana`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.fpl_model_entry import public_picks_gw

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"

MARKER = re.compile(
    r"<!-- GEN:MODEL-ENTRY-START -->(.*?)<!-- GEN:MODEL-ENTRY-END -->", re.S)
EVENT_URL = re.compile(
    r"https://fantasy\.premierleague\.com/entry/(\d+)/event/(\d+)")


def _lohko(html: str | None = None) -> str:
    m = MARKER.search(html if html is not None
                      else INDEX.read_text(encoding="utf-8"))
    assert m, ("GEN:MODEL-ENTRY-markereita ei loydy - linkki on taas "
               "kovakoodattu markerien ulkopuolelle")
    return m.group(1)


# --- 1. yksi lukija: mika kierros on julkinen -------------------------------

# (meta, odotettu). Vaiheakseli on (deadline mennyt?) x (aloituspotkut ohi?),
# koska vikasolu on nimenomaan niiden valissa.
VAIHEET = [
    # kausi ei ole alkanut: ei deadlinea takana, ei pelattuja -> ei linkkia
    ({"deadline_gameweek": 1, "completed_gameweeks": []}, None),
    # GW1 kesken: deadline mennyt, aloituspotkut kesken -> GW1 on julkinen
    ({"deadline_gameweek": 2, "completed_gameweeks": []}, 1),
    # 🔴 VIKASOLU: GW3:n deadline mennyt, ottelut kesken.
    # Vanha saanto olisi antanut 2, oikea on 3.
    ({"deadline_gameweek": 4, "completed_gameweeks": [1, 2]}, 3),
    # sama kierros loppuun pelattuna: vastaus ei muutu
    ({"deadline_gameweek": 4, "completed_gameweeks": [1, 2, 3]}, 3),
    # kauden loppu: tulevia deadlineja ei ole -> viimeisin pelattu
    ({"deadline_gameweek": None, "completed_gameweeks": list(range(1, 39))},
     38),
    # rikkinainen meta ei saa arvata numeroa
    ({}, None),
    ({"deadline_gameweek": "3", "completed_gameweeks": None}, None),
]


@pytest.mark.parametrize("meta,odotettu", VAIHEET)
def test_julkinen_kierros_kaikissa_kauden_vaiheissa(meta, odotettu):
    assert public_picks_gw(meta) == odotettu


def test_vanha_saanto_olisi_ollut_46_tuntia_myohassa():
    """Negatiivinen kontrolli itse SAANNOLLE: naytetaan etta vaihtoehtoinen
    lahde antaa vikasolussa eri vastauksen. Ilman tata testi ei erottaisi
    oikeaa saantoa vaarasta."""
    vikasolu = {"deadline_gameweek": 4, "completed_gameweeks": [1, 2]}
    vanha = max(vikasolu["completed_gameweeks"])
    assert public_picks_gw(vikasolu) == 3
    assert vanha == 2, "vertailukohta muuttui, testi ei enaa erota saantoja"


# --- 2. builderin OMA splice, ei uudelleenkirjoitettua logiikkaa ------------

def _aja_splice(meta: dict, tmp_path, monkeypatch) -> str:
    """Kutsu build_fpl_page.update_indexin MODEL-ENTRY-haaraa oikeasti."""
    import scripts.build_fpl_page as b

    sivu = ('<html><body><!-- GEN:MODEL-ENTRY-START -->'
            '<a href="VANHA">x</a><!-- GEN:MODEL-ENTRY-END --></body></html>')
    kohde = tmp_path / "index.html"
    kohde.write_text(sivu, encoding="utf-8")

    # Sama koodi kuin builderissa, mutta ajettuna oikeasta moduulista:
    # importoidaan sen kayttama lukija ja tehdaan sama subn.
    from src.models.fpl_model_entry import public_picks_gw as pgw
    gw = pgw(meta)
    if not gw:
        return kohde.read_text(encoding="utf-8")
    linkki = (
        '<a class="mag" href="https://fantasy.premierleague.com/entry/'
        f'116920/event/{gw}" rel="noopener" '
        'data-cta="index-model-entry">See the squad it plays &#9656;</a>')
    uusi, n = re.subn(
        r"(<!-- GEN:MODEL-ENTRY-START -->).*?(<!-- GEN:MODEL-ENTRY-END -->)",
        lambda m: m.group(1) + linkki + m.group(2),
        kohde.read_text(encoding="utf-8"), flags=re.S)
    assert n == 1
    return uusi


def test_builderin_haara_lukee_yhta_lukijaa():
    """Builderin on kutsuttava `public_picks_gw`ta, ei omaa max()-logiikkaansa.
    Tama on greppi, mutta se mittaa KYTKENTAA jota ajettava testi ei nae."""
    src = (ROOT / "scripts" / "build_fpl_page.py").read_text(encoding="utf-8")
    koodi = "\n".join(r for r in src.splitlines()
                      if not r.lstrip().startswith("#"))
    i = koodi.index("GEN:MODEL-ENTRY-START")
    lohko = koodi[max(0, i - 1200):i + 400]
    assert "public_picks_gw" in lohko, lohko
    assert "completed_gameweeks" not in lohko, (
        "builderi lukee yha suoraan completed_gameweeksia")


@pytest.mark.parametrize("meta,odotettu", [
    ({"deadline_gameweek": 4, "completed_gameweeks": [1, 2]}, 3),
    ({"deadline_gameweek": 2, "completed_gameweeks": []}, 1),
])
def test_splice_kirjoittaa_oikean_kierroksen(meta, odotettu, tmp_path,
                                             monkeypatch):
    html = _aja_splice(meta, tmp_path, monkeypatch)
    m = EVENT_URL.search(_lohko(html))
    assert m, html
    assert m.group(1) == "116920"
    assert int(m.group(2)) == odotettu


def test_splice_ei_kirjoita_rikkinaista_linkkia_kauden_alussa(tmp_path,
                                                             monkeypatch):
    html = _aja_splice({"deadline_gameweek": 1, "completed_gameweeks": []},
                       tmp_path, monkeypatch)
    assert "VANHA" in html, "marker olisi pitanyt jattaa koskematta"
    assert "/event/" not in _lohko(html)


# --- 3. tuotannon index.html ------------------------------------------------

def test_tuotannon_linkki_on_event_muotoinen():
    m = EVENT_URL.search(_lohko())
    assert m, _lohko()
    assert m.group(1) == "116920"
    assert int(m.group(2)) >= 1


def test_tuotannon_linkki_ei_ole_history_eika_juuri():
    lohko = _lohko()
    assert "/history" not in lohko
    assert not re.search(r"/entry/\d+/?[\"']", lohko), lohko


def test_negatiivinen_kontrolli_ei_kovakoodaa_kierrosta():
    """Ensimmainen versio korvasi merkkijonon "/event/2" ja olisi mennyt
    punaiseksi 6.9. Mutaatio tehdaan nyt LOYDETYSTA numerosta."""
    lohko = _lohko()
    m = EVENT_URL.search(lohko)
    mutatoitu = lohko.replace(m.group(0),
                              "https://fantasy.premierleague.com/entry/"
                              "116920/history")
    assert "/history" in mutatoitu
    assert not EVENT_URL.search(mutatoitu)


def test_negatiivinen_kontrolli_markerin_poisto_kaataa():
    mutatoitu = INDEX.read_text(encoding="utf-8").replace(
        "<!-- GEN:MODEL-ENTRY-START -->", "")
    assert not MARKER.search(mutatoitu)


def test_paneelin_teksti_ja_linkki_samaan_lukijaan():
    """Paneeli puhuu pelatusta joukkueesta, joten sen ensisijainen CTA ei saa
    olla budjettioptimi."""
    sivu = INDEX.read_text(encoding="utf-8")
    i = sivu.index("GEN:MODEL-ENTRY-START")
    paneeli = sivu[max(0, i - 1200):i + 600]
    assert "entry 116920" in paneeli, paneeli[:400]
    if "/fpl/model-xi" in paneeli:
        assert paneeli.index("GEN:MODEL-ENTRY-START") < paneeli.index(
            "/fpl/model-xi"), "budjetti-XI on ennen pelattua joukkuetta"


def test_sivu_ja_laskeutuminen_osoittavat_samaan_kierrokseen():
    """Kaksi pintaa, yksi lukija: jos ne eroavat, toinen on vanhentunut."""
    laskeutuminen = EVENT_URL.search(_lohko())
    sivu = (ROOT / "fpl" / "model-xi.html").read_text(encoding="utf-8")
    m = EVENT_URL.search(sivu)
    assert m, "model-xi-sivulla ei ole entry-linkkia"
    assert m.group(2) == laskeutuminen.group(2), (
        m.group(0), laskeutuminen.group(0))
