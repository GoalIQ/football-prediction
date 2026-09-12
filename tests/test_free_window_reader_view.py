# -*- coding: utf-8 -*-
"""Ilmaisikkunan portti: lupaus ei saa jaada elamaan EIKA portti saa olla
vihrea sellaisessa tilassa.

MITATTU 12.9.2026 klo 08:30 UTC, nelja tuntia ennen ikkunan sulkeutumista.
`check_free_window.py` oli sokea kolmelle lupaukselle viidesta. Se olisi
tulostanut ikkunan sulkeuduttua

    "OK: ilmaisikkuna on kiinni eika yksikaan pinta lupaa ilmaista Premiumia."

samalla kun goaliq.app naytti napin *Get Premium free* ja hintalapun
*Free until 12 Sept*, ja goaliq.app/predictions koko lupauslauseen. Vihrea
portti olisi ollut todiste vaarasta asiasta (muisti:
`portti-punastuu-vasta-kun-vika-on-jo-servattu`).

Kaksi juurisyyta, molemmat tunnettuja:
  1. RIVI EI OLE SKANNAUSYKSIKKO. `predictions.html` taittoi lupauksen
     kahdelle riville; `index.html` katkaisi sen tagilla
     (`Free<span> until 12 Sept</span>`).
  2. VAITEPERHE OLI VAJAA: nappiteksti ja hintalappu ovat lupauksia siina
     missa lauseetkin.

Ja kolmas, joka syntyi vasta korjauksesta ja loytyi synteettisella kellolla
ennen CI:ta: laajennettu kuvio osui `Hero.svelte`in merkkijonoliteraaliin, ja
lausepoisto olisi jattanyt sinne syntaksivirheen.
"""
from __future__ import annotations

import datetime as dt
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scripts.check_free_window as C  # noqa: E402
from src import free_window as FW  # noqa: E402

AUKI = dt.datetime(2026, 9, 12, 6, 0, tzinfo=dt.timezone.utc)
KIINNI = dt.datetime(2026, 9, 12, 13, 0, tzinfo=dt.timezone.utc)


# ---------------------------------------------------------------------------
# 1. Lukijan nakyma: tagi ja rivinvaihto eivat saa katkaista lupausta
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lahde,odotettu", [
    # Mitattu predictions.html:sta 12.9: lupaus kahdella rivilla.
    ("<p>Premium is free on the web\n        until the GW4 deadline on "
     "12 September.</p>", True),
    # Mitattu index.html:sta 12.9: lupaus katkaistu tagilla.
    ('<span class="price-tag">Free<span> until 12 Sept</span></span>', True),
    # Nappiteksti on lupaus siina missa lausekin.
    ('<a class="btn" data-cta="hero-freewindow">Get Premium free &#9656;</a>',
     True),
    # Hakutuloksen kuvaus on lukijalle nakyvaa tekstia.
    ('<meta name="description" content="Premium is free on the web until '
     '12 September.">', True),
    # Ei osu: pysyva ilmaistaso, ei ikkunalupaus.
    ("<p>Free on the web and in the app. Expected goals for every match.</p>",
     False),
    ("<p>Create a free account to save your team.</p>", False),
])
def test_lukijan_nakyma_loytaa_lupauksen(lahde, odotettu):
    nakyma, _ = C.luettava_teksti(lahde)
    assert bool(C.CLAIM_RE.search(nakyma)) is odotettu, nakyma


def test_raaka_lahde_ei_olisi_loytanyt_naita():
    """KONTROLLI: naytetaan etta korjaus oli tarpeen, ei kosmetiikkaa."""
    taittunut = "Premium is free on the web\n        until the GW4 deadline"
    tagilla = "Free<span> until 12 Sept</span>"
    assert not C.CLAIM_RE.search(taittunut)
    assert not C.CLAIM_RE.search(tagilla)
    for lahde in (taittunut, tagilla):
        nakyma, _ = C.luettava_teksti(lahde)
        assert C.CLAIM_RE.search(nakyma)


def test_rivinumero_sailyy_nakyman_lapi():
    lahde = ("rivi1\nrivi2\n<p>Premium is free on the web\n"
             "  until the GW4 deadline</p>\n")
    osumat = C._osumat(lahde, C.CLAIM_RE)
    assert osumat, "osumaa ei loytynyt"
    assert osumat[0][0] == 3, osumat


def test_kontrolli_lukija_ei_ole_inertti():
    """Ilman tata `luettava_teksti` voisi palauttaa tyhjaa ja kaikki ylla
    olevat `False`-tapaukset menisivat lapi tyhjana."""
    nakyma, kartta = C.luettava_teksti("<p>abc def</p>")
    assert "abc def" in nakyma
    assert len(kartta) == len(nakyma)


# ---------------------------------------------------------------------------
# 2. Rajaustarkistuksen perhe on TARKOITUKSELLA suppeampi
# ---------------------------------------------------------------------------

def test_rajausta_ei_vaadita_nappitekstilta():
    """Nelisanaiselta napilta ei voi vaatia 'on the web' -sivulausetta.

    Jos vaadittaisiin, portti olisi punainen tanaan asiasta joka on tanaan
    tosi, ja paivittain punainen portti tulee ohitetuksi."""
    nappi = "Get Premium free"
    assert C.CLAIM_RE.search(nappi)
    assert not C.SCOPED_CLAIM_RE.search(nappi)


def test_rajaus_vaaditaan_yha_lauseelta():
    lause = "Premium is free on the web until the GW4 deadline"
    assert C.SCOPED_CLAIM_RE.search(lause)


# ---------------------------------------------------------------------------
# 3. Ikkunan molemmat tilat: renderoijat
# ---------------------------------------------------------------------------

def test_kiinni_ei_jata_tyhjaa_nappia_eika_tyhjaa_hintaa():
    """Rakenteesta ei saa tulla tyhjaa: napista jaa nappi, hinnasta hinta."""
    assert FW.band_html(KIINNI) == ""
    cta = FW.hero_cta_html(KIINNI)
    assert "Get Premium" in cta and "free" not in cta.lower()
    hinta = FW.price_tag_html(KIINNI)
    assert "3.99" in hinta and "Free" not in hinta
    pred = FW.predictions_price_html(KIINNI)
    assert "3.99" in pred and "free" not in pred.lower()


def test_auki_sanoo_lupauksen_ja_rajaa_sen_webiin():
    band = FW.band_html(AUKI)
    assert "free on the web until" in band
    assert C.SCOPE_RE.search(band)


@pytest.mark.parametrize("renderoija", list(FW.SURFACE_BLOCKS.values()))
def test_yksikaan_renderoija_ei_lupaa_ilmaista_kiinni(renderoija):
    nakyma, _ = C.luettava_teksti(renderoija(KIINNI))
    assert not C.CLAIM_RE.search(nakyma), renderoija.__name__


# ---------------------------------------------------------------------------
# 4. GEN-lohkot ovat sivuilla, ja puuttuva markkeri kaataa ajon
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tiedosto,avain", list(FW.SURFACE_BLOCKS.keys()))
def test_gen_lohko_on_sivulla(tiedosto, avain):
    txt = (ROOT / tiedosto).read_text(encoding="utf-8")
    assert f"<!-- GEN:{avain}-START" in txt, (tiedosto, avain)
    assert f"<!-- GEN:{avain}-END -->" in txt, (tiedosto, avain)


def test_puuttuva_markkeri_kaataa_ajon(tmp_path, monkeypatch):
    """Hiljainen ohitus tarkoittaisi etta lupaus jaa sivulle (fail-closed)."""
    for tiedosto, _ in FW.SURFACE_BLOCKS:
        (tmp_path / tiedosto).write_text("<html>ei markkereita</html>",
                                         encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", tmp_path)
    with pytest.raises(SystemExit) as e:
        C.render_blocks(KIINNI)
    assert "GEN:" in str(e.value)


# ---------------------------------------------------------------------------
# 5. PAAPORTTI: synteettinen kello, koko pintajoukko
# ---------------------------------------------------------------------------

def _kopioi_pinnat(tmp_path: Path) -> Path:
    for p in C.surfaces():
        kohde = tmp_path / p.relative_to(ROOT)
        kohde.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, kohde)
    return tmp_path


def test_ikkunan_sulkeuduttua_yksikaan_tekstipinta_ei_lupaa_ilmaista(
        tmp_path, monkeypatch):
    """DoD. Ajetaan KOPIOLLE, ei repolle.

    `fpl.html` on poikkeuslistalla perusteluineen: sen molemmat tilat
    renderoi `build_fpl_page.upsell_block()`, ja page-refresh bakeaa sen
    ENNEN taman ajoa."""
    juuri = _kopioi_pinnat(tmp_path)
    monkeypatch.setattr(C, "ROOT", juuri)
    C.fix(now=KIINNI)
    jaljella = [h for h in C.hits()
                if h[0].replace("\\", "/") not in C.FIX_OHITETAAN]
    assert not jaljella, jaljella


def test_ikkunan_ollessa_auki_fix_ei_poista_lupausta(tmp_path, monkeypatch):
    """KONTROLLI: ilman tata edellinen menisi lapi myos silla etta fix()
    tyhjentaisi kaiken aina (muisti: kontrolli-lapaisi-tyhjana)."""
    juuri = _kopioi_pinnat(tmp_path)
    monkeypatch.setattr(C, "ROOT", juuri)
    C.fix(now=AUKI)
    assert C.hits(), "ikkunan ollessa auki lupauksen PITAA elaa"


def test_fix_ei_koske_lahdekoodiin(tmp_path, monkeypatch):
    """MUTAATIO: lausepoisto koodissa jattaa syntaksivirheen.

    Mitattu 12.9: `Hero.svelte`in `? 'Premium, free until 12 September'`
    olisi muuttunut muotoon `?` ilman haaraa."""
    juuri = _kopioi_pinnat(tmp_path)
    koodi = juuri / "web/pro-spa/src/lib/components/Keksitty.svelte"
    koodi.parent.mkdir(parents=True, exist_ok=True)
    alkuperainen = ("const label = cond\n"
                    "  ? 'Premium, free until 12 September'\n"
                    "  : 'Free';\n")
    koodi.write_text(alkuperainen, encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", juuri)
    # Kontrolli: portti NAKEE sen...
    assert any(h[0].endswith("Keksitty.svelte") for h in C.hits()), \
        "portti ei nae lahdekoodin lupausta - mutaatio olisi inertti"
    C.fix(now=KIINNI)
    # ...mutta ei muokkaa sita.
    assert koodi.read_text(encoding="utf-8") == alkuperainen


# ---------------------------------------------------------------------------
# 6. LIVE-tarkistus: mita oikeasti servataan, ei mita aiomme servata
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, body: str):
        self._b = body.encode("utf-8")

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_live_hits_lukee_lukijan_nakymaa(monkeypatch):
    """Sama lukija kuin repotarkistuksella: taittunut lupaus loytyy."""
    sivut = {
        "https://goaliq.app/": "<p>Premium is free on the web\n  until the GW4 deadline</p>",
        "https://goaliq.app/fpl": "<p>Nothing to see here.</p>",
    }
    monkeypatch.setattr(C, "LIVE_URLS", tuple(sivut))

    import urllib.request

    def _fake(req, timeout=None):
        return _FakeResp(sivut[req.full_url])

    monkeypatch.setattr(urllib.request, "urlopen", _fake)
    osumat, virheet = C.live_hits()
    assert not virheet
    assert len(osumat) == 1, osumat
    assert osumat[0][0] == "https://goaliq.app/"


def test_live_hakuvirhe_on_fail_closed(monkeypatch):
    """MUTAATIO: hakuvirhe EI saa nayttaa tyhjalta tulokselta.

    Tyhja lista tarkoittaisi "yksikaan pinta ei lupaa ilmaista" - eli portti
    olisi vihrea juuri silloin kun se ei tieda mitaan
    (muisti: nolla-ei-ole-sama-kuin-ei-tietoa)."""
    monkeypatch.setattr(C, "LIVE_URLS", ("https://goaliq.app/",))
    import urllib.error
    import urllib.request

    def _kaada(req, timeout=None):
        raise urllib.error.URLError("verkko poikki")

    monkeypatch.setattr(urllib.request, "urlopen", _kaada)
    osumat, virheet = C.live_hits()
    assert osumat == []
    assert virheet and "verkko poikki" in virheet[0][1]
    assert C.main_live() == 1, "hakuvirheen pitaa kaataa portti"


def test_live_urlit_kattavat_samat_pinnat_kuin_repotarkistus():
    """Jos uusi kasin yllapidetty pinta lisataan repoon, live-lista vanhenee
    hiljaa. Tama ei voi tarkistaa kaikkea, mutta se vaatii etta jokainen
    live-URL on tunnistettavissa repon pinnasta."""
    tiedostot = {p.name for p in C.surfaces()}
    odotetut = {"index.html", "fpl.html", "predictions.html", "faq.html",
                "creators.html", "llms.txt"}
    assert odotetut <= tiedostot, odotetut - tiedostot
    assert len(C.LIVE_URLS) == len(odotetut), (C.LIVE_URLS, odotetut)
