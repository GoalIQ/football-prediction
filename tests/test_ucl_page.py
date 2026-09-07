# -*- coding: utf-8 -*-
"""Portit /ucl-osion sivuille."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UCL = ROOT / "ucl"
SIVUT = ("index.html", "prices.html", "team-news.html")


def _html(nimi: str) -> str:
    p = UCL / nimi
    if not p.exists():
        pytest.skip(f"{nimi} ei ole viela generoitu")
    return p.read_text(encoding="utf-8")


@pytest.mark.parametrize("nimi", SIVUT)
def test_sivun_luokat_ovat_olemassa_tyyliarkissa(nimi):
    """🔴 TAMA VIKA TEHTIIN JA MITATTIIN RENDEROIDYSTA KUVASTA 7.9.2026.

    Ensimmainen versio kirjoitti `<div class="tablewrap">` ja
    `<table class="sortable">`. Kumpaakaan luokkaa ei ole olemassa - oikeat
    ovat `tblwrap` ja `lb`. Yhden kirjaimen ero maksoi KOLME asiaa
    kerralla, eika mikaan huutanut:

        - taulukon tyylit (padding, erotinviivat, otsikkorivi)
        - lajittelu       (`scripts/table_tools.py` sitoo sen `table.lb`:hen)
        - positiosuodatin (sama tiedosto, sama valitsin)

    Keksitty luokkanimi on validia HTML:aa. Ainoa tapa havaita se on
    verrata sivun luokkia siihen CSS:aan joka sivulla oikeasti on.
    """
    h = _html(nimi)
    tyyli = "\n".join(re.findall(r"<style>(.*?)</style>", h, re.S))
    assert len(tyyli) > 2000, "sivulla ei ole tyyliarkkia"

    # CSS:ssa maaritellyt luokat + JS:n lisaamat (ne eivat ole HTML:ssa).
    maaritellyt = set(re.findall(r"\.([a-zA-Z][\w-]*)", tyyli))
    kaytetyt = set()
    for m in re.findall(r'class="([^"]+)"', h):
        kaytetyt.update(m.split())

    puuttuvat = sorted(kaytetyt - maaritellyt)
    assert not puuttuvat, (
        f"{nimi}: luokkia joita tyyliarkissa EI OLE: {puuttuvat}. "
        "Keksitty luokkanimi on validia HTML:aa ja saa nolla tyylia - "
        "tarkista oikea nimi lahteesta, ala arvaa.")


@pytest.mark.parametrize("nimi", SIVUT)
def test_taulukko_saa_lajittelun_ja_suodattimen(nimi):
    """`table_tools.js` sitoo molemmat valitsimeen `table.lb`. Muu luokka
    tuottaa taulukon joka nayttaa oikealta eika reagoi klikkiin."""
    h = _html(nimi)
    assert '<table class="lb">' in h, (
        f"{nimi}: taulukko ei ole luokkaa `lb`, joten lajittelu ja "
        "suodatin eivat kytkeydy")


@pytest.mark.parametrize("nimi", SIVUT)
def test_sivulla_on_kaavio(nimi):
    """Villen kysymys 7.9: 'Grafiikoita?'. Mitattu vastaus oli silloin: ei
    yhtaan kaaviota koko sivustolla."""
    h = _html(nimi)
    kaaviot = re.findall(r'<svg viewBox="0 0 \d+ \d+"', h)
    assert kaaviot, f"{nimi}: ei yhtaan kaaviota"
    assert 'class="chart-scroll"' in h, f"{nimi}: kaavio ilman vieritinta"


def test_hub_kaaviot_ovat_kaikki_kolme():
    h = _html("index.html")
    for otsikko in ("Ownership by price", "Price range by position",
                    "Injuries, suspensions and doubts by club"):
        assert f'aria-label="{otsikko}' in h, f"puuttuu kaavio: {otsikko}"


@pytest.mark.parametrize("nimi", SIVUT)
def test_pistesarake_kertoo_kaudesta_jos_luvut_ovat_viime_kaudelta(nimi):
    """Sarakeotsikko ja kentta tulevat `ucl_phase.pistekentta()`sta samasta
    kutsusta. Jos artefaktissa ei ole `points`-kenttaa, otsikon ON
    sanottava 'last season'."""
    import json
    from src.models import ucl_phase as up
    d = ROOT / "data" / "ucl_fantasy.json"
    if not d.exists():
        pytest.skip("artefaktia ei ole")
    doc = json.loads(d.read_text(encoding="utf-8"))
    kentta, otsikko = up.pistekentta(doc)
    h = _html(nimi)
    if kentta == "prev_season_points":
        assert "Pts (last season)" in h, (
            f"{nimi}: luvut ovat viime kaudelta mutta sarake ei sano sita")
        assert "xP" not in h, (
            f"{nimi}: sivulla on xP-sarake vaikka kautta ei ole pelattu")


def test_hub_ei_lupaa_taman_kauden_lukuja_esikaudella():
    """Muisti: honest-data-labels. Copy ei saa luvata dataa jota ei ole."""
    import json
    from src.models import ucl_phase as up
    d = ROOT / "data" / "ucl_fantasy.json"
    if not d.exists():
        pytest.skip("artefaktia ei ole")
    doc = json.loads(d.read_text(encoding="utf-8"))
    if up.vaihe(doc) != up.ESIKAUSI:
        pytest.skip("kausi on alkanut")
    h = _html("index.html")
    assert "No matchday of this season has been played" in h, (
        "hub ei sano etta kautta ei ole pelattu")


def test_saatavuuskaavion_jarjestys_vastaa_copyn_lupausta():
    """🔴 MITATTU KUVASTA. Ensimmainen versio lajitteli poissaolojen
    SUMMALLA, jolloin karkeen nousi klubi jolla oli eniten rekisteroimatta
    jatettyja pelaajia - ei eniten loukkaantumisia. Copy sanoi 'clubs with
    the most', ja lukija luki sen loukkaantumisiksi.

    Jarjestys ja naytetty luku vastaavat samaan kysymykseen (muisti:
    uusi-sorttiulottuvuus-muuttaa-sarakkeen).
    """
    import json
    from collections import Counter, defaultdict
    d = ROOT / "data" / "ucl_fantasy.json"
    if not d.exists():
        pytest.skip("artefaktia ei ole")
    doc = json.loads(d.read_text(encoding="utf-8"))

    per_klubi = defaultdict(Counter)
    for p in doc["players"]:
        if p["status"] in ("injured", "suspended", "doubtful", "not_in_squad"):
            per_klubi[p["team_code"]][p["status"]] += 1

    h = _html("index.html")
    # Kaavion rivijarjestys: klubikoodit y-jarjestyksessa.
    # HUOM: aria-label esiintyy KAHDESTI (figure-kaarija + svg), joten
    # `split(...)[1]` osui 117 merkin valifragmenttiin ja loysi 0 klubia.
    # Luetaan svg-elementti eksplisiittisesti.
    m = re.search(r'<svg [^>]*aria-label="Injuries, suspensions and doubts by club"'
                  r'[^>]*>(.*?)</svg>', h, re.S)
    assert m, "saatavuuskaaviota ei loytynyt sivulta"
    lohko = m.group(1)
    koodit = re.findall(r'text-anchor="end">([A-Z]{2,4})</text>', lohko)
    assert len(koodit) >= 8, f"kaaviossa vain {len(koodit)} klubia"

    def toimittava(k: str) -> int:
        c = per_klubi[k]
        return c["injured"] + c["suspended"] + c["doubtful"]

    arvot = [toimittava(k) for k in koodit]
    assert arvot == sorted(arvot, reverse=True), (
        f"kaavio ei ole jarjestetty toimittavien poissaolojen mukaan: "
        f"{list(zip(koodit, arvot))}")
    assert all(v > 0 for v in arvot), (
        "kaaviossa on klubi jolla ei ole yhtaan loukkaantunutta, "
        "pelikieltoa tai kyseenalaista - se on rekisterointikirjanpitoa")

    assert "injured, suspended or doubtful" in h, (
        "copy ei kerro mita kaavio laskee")


@pytest.mark.parametrize("nimi", SIVUT)
def test_ei_em_dashia(nimi):
    """Muisti: em-dash-ja-pinta-pariteetti."""
    h = _html(nimi)
    runko = h.split("<body>", 1)[-1]
    assert "—" not in runko, f"{nimi}: em dash julkisessa tekstissa"


@pytest.mark.parametrize("nimi", SIVUT)
def test_sivu_sanoo_ettei_ole_uefan(nimi):
    """Virallisen syotteen kayttaminen ei tee meista virallista lahdetta."""
    h = _html(nimi)
    assert "not affiliated" in h or "GoalIQ is an independent" in h or \
        "statistical estimates" in h, f"{nimi}: ei erottautumislausetta"


@pytest.mark.parametrize("nimi", SIVUT)
def test_og_kortti_ei_ole_toisen_osion_kortti(nimi):
    """🔴 JULKAISUPORTTI LOYSI TAMAN 7.9, JA SE ON JULKISIN MAHDOLLINEN VIKA.

    `_og_image` johti tiedostonimen canonicalin VIIMEISESTA palasta, joten
    `/ucl/team-news` ja `/fpl/team-news` osuivat samaan korttiin. UCL-sivun
    jakaminen antoi kortin jossa lukee isolla "goaliq.app/fpl/team-news":
    vaarasta kilpailusta kertova kortti, jota kukaan meista ei nae ennen
    kuin joku jakaa linkin (muisti: kortin-teksti-on-julkista-tekstia).

    Vaara kortti on huonompi kuin ei korttia lainkaan.
    """
    h = _html(nimi)
    m = re.search(r'<meta property="og:image" content="([^"]+)"', h)
    assert m, f"{nimi}: og:image puuttuu"
    kuva = m.group(1)
    assert "/fpl/" not in kuva and "/fpl-" not in kuva, (
        f"{nimi}: og-kortti tulee FPL-osiosta: {kuva}")
    # Kortin nimi ei saa olla paljas slug jonka jokin toinen osio omistaa.
    tiedosto = kuva.rsplit("/", 1)[-1].split("?")[0]
    kielletyt = {f"{p.stem}.png" for p in (ROOT / "fpl").glob("*.html")}
    assert tiedosto.replace("-1200x630", "") not in kielletyt, (
        f"{nimi}: og-kortti {tiedosto} on FPL-sivun kortti")


def test_saatavuuskaavio_kattaa_kaiken_minka_otsikko_lupaa():
    """🔴 JULKAISUPORTIN LOYDOS: otsikko lupasi enemman kuin kaavio naytti.

    Otsikko oli "Players unavailable by club" ja sen ylla luki "171 of
    1162", mutta kaavio piirsi 111 pelaajaa ja 16 klubia 32:sta - loput
    putosivat suodattimeen ja `[:16]`-katkaisuun. 35 % puuttui kaaviosta
    jonka otsikko lupasi ne (muisti: honest-data-labels).

    Nyt otsikko ja sisalto ovat sama joukko, ja tama portti mittaa sen.
    """
    import json
    from collections import Counter
    d = ROOT / "data" / "ucl_fantasy.json"
    if not d.exists():
        pytest.skip("artefaktia ei ole")
    doc = json.loads(d.read_text(encoding="utf-8"))
    TOIM = ("injured", "suspended", "doubtful")
    odotetut = Counter(p["team_code"] for p in doc["players"]
                       if p["status"] in TOIM)

    h = _html("index.html")
    m = re.search(r'<svg [^>]*aria-label="Injuries, suspensions and doubts '
                  r'by club"[^>]*>(.*?)</svg>', h, re.S)
    assert m, "kaaviota ei loytynyt"
    koodit = re.findall(r'text-anchor="end">([A-Z]{2,4})</text>', m.group(1))

    puuttuu = sorted(set(odotetut) - set(koodit))
    assert not puuttuu, (
        f"kaaviosta puuttuu {len(puuttuu)} klubia joilla on tapauksia: "
        f"{puuttuu}. Otsikko lupaa ne.")
    # 🔴 MOLEMPIIN SUUNTIIN. Yksisuuntainen portti sanoo "kaikki luvattu on
    # mukana" muttei "vain luvattu on mukana": ylijoukko lapaisee. Mitattu
    # 7.9 mutaatiolla - kun kaavioon lisattiin 122 rekisteroimatonta
    # pelaajaa, TAMA portti pysyi vihreana ja vian nappasi vain
    # jarjestysportti.
    ylimaaraiset = sorted(set(koodit) - set(odotetut))
    assert not ylimaaraiset, (
        f"kaaviossa on {len(ylimaaraiset)} klubia joilla EI ole yhtaan "
        f"tapausta: {ylimaaraiset}. Otsikko ei lupaa niita.")

    # Ja pylvaiden summa on koko joukko, ei osa siita.
    palkit = re.findall(r'<rect x="[0-9.]+" y="\d+" width="[0-9.]+"',
                        m.group(1))
    assert len(palkit) >= len(odotetut), (
        f"pylvaita {len(palkit)}, klubeja {len(odotetut)}")


def test_kaavion_jarjestys_ja_pituus_mittaavat_samaa():
    """🔴 v2:N VIKA: jarjestys oli I+S+D mutta PITUUS sisalsi myos
    `not_in_squad`in. MCI ja AVL olivat 10 pelaajan pylvailla sijoilla
    11-12 ja BAR 4 pelaajan pylvaalla sijalla 13, eli kaavio nayttti
    jarjestamattomalta. Lukija lukee pituuden.

    Mitataan pylvaiden PITUUDET sivulta ja vaaditaan laskeva jarjestys.
    """
    h = _html("index.html")
    m = re.search(r'<svg [^>]*aria-label="Injuries, suspensions and doubts '
                  r'by club"[^>]*>(.*?)</svg>', h, re.S)
    assert m, "kaaviota ei loytynyt"

    # Rivi = y-koordinaatti; pituus = saman y:n rect-leveyksien summa.
    per_y = {}
    for y, w in re.findall(r'<rect x="[0-9.]+" y="(\d+)" width="([0-9.]+)"',
                           m.group(1)):
        per_y[int(y)] = per_y.get(int(y), 0.0) + float(w)
    pituudet = [per_y[y] for y in sorted(per_y)]
    assert len(pituudet) >= 8, f"vain {len(pituudet)} pylvasta"
    assert pituudet == sorted(pituudet, reverse=True), (
        "pylvaiden pituudet eivat ole laskevassa jarjestyksessa - "
        f"jarjestys ja pituus mittaavat eri asiaa: "
        f"{[round(x) for x in pituudet]}")


DATA_JSON = ROOT / "data" / "ucl_fantasy.json"


def test_pistesarake_on_tyhja_eika_nolla():
    """🔴 MUTAATIO 7.9 PALJASTI ETTA TALLE EI OLLUT PORTTIA: solun
    palautus nollaksi lapaisi 26 testia.

    Blankin ja nollan ero ON koko korjaus. 762 pelaajalla 1 162:sta
    `prev_season_points` on 0 ja kaikilla myos minuutit, eli he eivat
    olleet kilpailussa. "0" luetaan huonoksi kaudeksi, ei puuttumiseksi.

    Assertio on YHTASUURUUS eika "ei nollia": liian moni tyhja on yhta
    lailla vaarin, ja se olisi eri vika samassa sarakkeessa.
    """
    import json
    if not DATA_JSON.exists():
        pytest.skip("artefaktia ei ole")
    P = json.loads(DATA_JSON.read_text(encoding="utf-8"))["players"]
    if any("points" in p for p in P):
        pytest.skip("kausi on alkanut, sarake on taman kauden")
    odotettu = sum(1 for p in P if not p.get("prev_season_minutes"))

    h = _html("prices.html")
    rivit = re.findall(r"<tr><td>(?:(?!</tr>)[\s\S])*?</tr>", h)
    assert len(rivit) > 1000, f"vain {len(rivit)} rivia"
    tyhjia = sum(1 for r in rivit
                 if re.match(r"^<tr>(<td>[^<]*</td>){5}<td></td>", r))
    nollia = sum(1 for r in rivit
                 if re.match(r"^<tr>(<td>[^<]*</td>){5}<td>0</td>", r))
    assert nollia == 0, f"{nollia} riville jai 0 tyhjan tilalle"
    assert tyhjia == odotettu, f"{tyhjia} tyhjaa, datassa {odotettu}"


KADENSSI = re.compile(r"\bupdated\b[^.]{0,40}\bevery\b[^.]{0,25}"
                      r"\b(hour|hours|day|days|minute|minutes)\b", re.I)


@pytest.mark.parametrize("nimi", SIVUT)
def test_ei_kadenssilupausta(nimi):
    """🔴 MUTAATIO 7.9: "every six hours" heroon lapaisi 26 testia.

    Kadenssi on lupaus ajastimesta jota emme hallitse: mitattu 27.8
    alkaen GitHubin ajastin on ollut 5-12 h myohassa. Sivu saa kertoa
    MILLOIN syote luettiin, ei kuinka usein se luetaan.
    """
    teksti = re.sub(r"<[^>]+>", " ", _html(nimi))
    osuma = KADENSSI.search(teksti)
    assert not osuma, f"{nimi}: kadenssilupaus '{osuma.group(0)}'"


def test_kontrolli_kadenssihavaitsin_loytaa_lupauksen():
    """NEGATIIVINEN KONTROLLI: ilman tata portti voisi olla vihrea siksi
    ettei regex osu mihinkaan (muisti: kontrolli-lapaisi-tyhjana)."""
    assert KADENSSI.search("Updated from the official feed every six hours.")
    assert KADENSSI.search("updated every day")
    assert not KADENSSI.search("last update 07 Sep 2026, 15:12 UTC")


@pytest.mark.parametrize("nimi", SIVUT)
def test_tuoreusleima_on_nakyvissa(nimi):
    """Kadenssin tilalla on oltava jotain tarkistettavaa, ei tyhjaa."""
    assert "last update" in _html(nimi).lower(), f"{nimi}: ei aikaleimaa"


def test_kaavion_rajaus_on_NAKYVASSA_tekstissa():
    """🔴 `svg_charts.otsikko` menee VAIN aria-labeliin.

    Julkaisuportti mittasi: `/ucl/prices`-sivun koko nakyva leipateksti
    lupasi 1 162 pelaajaa ja kaavio piirsi 172. Rajaus oli olemassa,
    mutta vain ruudunlukijalle. Kattavuusportti vertasi aria-labeliin,
    eli se ei suojannut sita vaitetta jonka nakeva lukija lukee.
    """
    for nimi in ("index.html", "prices.html"):
        h = _html(nimi)
        nakyva = re.sub(r"<svg[\s\S]*?</svg>", " ", h)
        nakyva = re.sub(r"<[^>]+>", " ", nakyva)
        assert "2% or more" in nakyva, (
            f"{nimi}: kaavion rajausta ei lue nakyvassa tekstissa")
    # Ja aria-label kayttaa SAMAA sanamuotoa, ei toista (muisti:
    # sama-vaite-monessa-sanamuodossa).
    h = _html("index.html")
    assert "owned by more than 1%" not in h, (
        "aria-label ja runkoteksti sanovat saman rajauksen eri tavalla")


def test_deadline_valitaan_lukuhetkella():
    """🔴 Deadline on sivun ainoa luku joka vanhenee ilman etta data
    muuttuu. Se laskettiin buildhetkella; nyt kaikki kierrokset ovat
    sivulla ja oikea valitaan lukijan kellosta."""
    h = _html("index.html")
    assert 'id="ucl-dl"' in h, "deadline-lauseella ei ole tunnistetta"
    assert "Date.parse" in h, "deadlinea ei valita lukuhetkella"
    m = re.search(r"<script>\(function\(\)\{var D=(\[.*?\]),", h, re.S)
    assert m, "deadline-taulukkoa ei loytynyt sivulta"
    import json
    D = json.loads(m.group(1))
    doc = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    odotetut = [k["md"] for k in doc["matchdays"] if k.get("deadline_utc")]
    assert [d["md"] for d in D] == sorted(odotetut), (
        "sivulla ei ole kaikkia kierroksia, joten se ei voi vaihtaa "
        "seuraavaan ilman uutta buildia")
