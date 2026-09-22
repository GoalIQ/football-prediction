"""Portti: sivun kuvaviittaukset osoittavat olemassa oleviin kuviin, ja kortti
on samalta kierrokselta kuin data.

🔴 TAUSTA (4.9.2026, Villen tilaus). Laskeutumissivulla oli **0 kuvaa** ja
2 559 sanaa proosaa, jossa kavijaa pyydetaan kuvittelemaan tyokalut joita
myymme. Kortit ovat olleet olemassa koko ajan, mutta ne kirjoitetaan
`outputs/`-kansioon joka on gitignoressa.

Kaksi asiaa voi mennä hiljaa rikki, ja tama portti estaa molemmat:

1. **Rikkinainen viittaus.** Sivu osoittaa tiedostoon jota ei ole. Tumma
   sivupohja piilottaa puuttuvan kuvan lahes taysin - kavija nakee tyhjan
   laatikon eika mikaan huuda.
2. **Vanhentunut kuva.** Nimi on tarkoituksella vakio
   (`gameweek-card.webp`), jotta sivun ei tarvitse tietaa kierrosnumeroa.
   Sama vakionimi tarkoittaa etta VANHA kortti nayttaa tuoreelta:
   GW3:n kortti GW7:n aikana on nakymatta vaara.

🔴 22.9.2026: KOHTA 2 OLI SOKEA CI:SSA. Se mittasi tiedoston mtimea
(`MAX_IKA_VRK = 16`). CI:n tuore checkout antaa jokaiselle tiedostolle
mtimeksi checkout-hetken, joten ika oli aina 0 vrk ja portti vihrea, kun
etusivu naytti GW3:n kortteja GW6:n aikana (18 vrk GW3:n deadlinesta).
Mitattu samana paivana: tuore worktree -> `25 passed` vanhoilla korteilla.
Nyt portti ei lue aikaa tiedostosta lainkaan: se vertaa `assets/cards/
cards.json`:n kierrosta samaan lukijaan jolla renderoijat nimeavat kortin
(`actionable_gameweek`, `publish_cards_to_site.kortin_tila`), ja sama
funktio ajetaan alla jokaisessa kierroksen vaiheessa (CLAUDE.md 6a kohta 3).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import publish_cards_to_site as P  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SIVUT = ["index.html", "fpl.html", "career.html", "faq.html", "creators.html"]

# Vakionimet joita sivut kayttavat. Uusi kortti lisataan tanne KASIN, jotta
# rikkinainen viittaus loytyy ennen julkaisua.
# 5.9: /fpl-tyokaluhakemiston 8 pikkukuvaa (og-kuvista, assets/cards/tools/).
TOOLS = ["expected-points", "best-captain", "differentials", "model-xi",
         "predicted-lineups", "price-changes", "team-news", "points"]
ODOTETUT = {"gameweek-card.webp", "projected-xi-card.webp"} | {
    f"tools/{t}.webp" for t in TOOLS}

RE_SRC = re.compile(r'src="(/assets/cards/[^"]+)"')
RE_SRCSET = re.compile(r'srcset="([^"]+)"')
UTC = dt.timezone.utc


def _viittaukset() -> set[str]:
    ulos = set()
    for nimi in SIVUT:
        p = ROOT / nimi
        if not p.exists():
            continue
        ulos |= set(RE_SRC.findall(p.read_text(encoding="utf-8")))
    return ulos


def _srcset_viittaukset() -> set[str]:
    ulos = set()
    for nimi in SIVUT:
        p = ROOT / nimi
        if not p.exists():
            continue
        for arvo in RE_SRCSET.findall(p.read_text(encoding="utf-8")):
            for osa in arvo.split(","):
                url = osa.strip().split(" ")[0]
                if url.startswith("/assets/cards/"):
                    ulos.add(url)
    return ulos


def test_sivut_viittaavat_kortteihin():
    """Tyhjyyskontrolli: jos yksikaan sivu ei viittaa korttiin, koko portti
    mittaa tyhjaa ja kuvat ovat kadonneet huomaamatta."""
    v = _viittaukset()
    assert v, "yksikaan sivu ei viittaa /assets/cards/-kuvaan"
    nimet = {x.replace("/assets/cards/", "", 1) for x in v}
    assert nimet == ODOTETUT, (nimet, ODOTETUT)


def test_jokainen_viittaus_osoittaa_olemassa_olevaan_tiedostoon():
    puuttuu = []
    for src in _viittaukset() | _srcset_viittaukset():
        p = ROOT / src.lstrip("/")
        if not p.exists() or p.stat().st_size == 0:
            puuttuu.append(src)
    assert not puuttuu, (
        "sivu viittaa kuvaan jota ei ole; tumma pohja piilottaa taman "
        "kavijalta: %s" % puuttuu)


def test_srcset_viittaukset_loytyvat():
    """Tyhjyyskontrolli srcsetille: 450 px -variantit ovat index.html:ssa
    (5.9). Jos tama on tyhja, yllaoleva testi ei mittaa variantteja."""
    v = _srcset_viittaukset()
    assert {P.pieni_nimi(n) for n in P.NIMET} <= {
        x.replace("/assets/cards/", "", 1) for x in v}, v


# ---------------------------------------------------------------------------
# KIERROSPORTTI (22.9): kortti vs data, ei tiedoston aika
# ---------------------------------------------------------------------------

def _tarkista(manifesti: dict, meta: dict, now: dt.datetime) -> list[str]:
    """Repon tila -testin JA negatiivisen kontrollin yhteinen kutsupaikka."""
    viat = []
    for nimi in P.NIMET:
        ok, syy = P.kortin_tila(manifesti.get(nimi), meta, now)
        if not ok:
            viat.append(f"{nimi}: {syy}")
    return viat


def test_etusivun_kortit_ovat_datan_kierrokselta():
    viat = _tarkista(P.lue_manifesti(), P.lue_meta(), dt.datetime.now(UTC))
    assert not viat, (
        "Etusivun kortti on eri kierrokselta kuin data. Vakionimi saa vanhan "
        "kortin nayttamaan tuoreelta:\n  " + "\n  ".join(viat))


def test_negatiivinen_kontrolli_22_9_tilanne_kaatuu():
    """Tasan se tila joka loytyi 22.9: GW3:n kortti, data GW6:ssa."""
    meta = {"deadline_gameweek": 6, "deadline_utc": "2026-10-10T10:00:00+00:00",
            "next_gameweek": 6}
    gw3 = {"gw": 3, "deadline_utc": "2026-09-04T17:30:00+00:00"}
    viat = _tarkista({n: gw3 for n in P.NIMET}, meta,
                     dt.datetime(2026, 9, 22, 8, 0, tzinfo=UTC))
    assert len(viat) == 2 and all("GW3" in v and "GW6" in v for v in viat), viat


@pytest.mark.parametrize("nimi", P.NIMET)
def test_manifesti_kuvaa_sivun_tiedostot(nimi):
    """cards.json:n kierros koskee VAIN sita kuvaa jonka tiiviste siina on.
    Kasin vaihdettu kuva (ohi publish_cards_to_site:n) kaataa taman, joten
    kierrosmerkinta ei voi jaada kuvaamaan eri kuvaa."""
    entry = P.lue_manifesti().get(nimi) or {}
    tiivisteet = entry.get("sha256") or {}
    for tiedosto in (nimi, P.pieni_nimi(nimi)):
        p = P.CARDS_OUT / tiedosto
        assert p.exists(), f"{tiedosto} puuttuu"
        assert tiivisteet.get(tiedosto) == P.sha256(p), (
            f"{tiedosto} ei ole se kuva jonka cards.json kuvaa. Julkaise "
            "`python -m scripts.publish_cards_to_site`illa, ala kopioi kasin.")


@pytest.mark.parametrize("nimi", P.NIMET)
def test_450_variantti_on_450_levea(nimi):
    Image = pytest.importorskip("PIL.Image")
    for tiedosto, leveys in ((nimi, P.LEVEYS), (P.pieni_nimi(nimi), P.LEVEYS_PIENI)):
        w, h = Image.open(P.CARDS_OUT / tiedosto).size
        assert w == leveys and abs(h - round(675 * leveys / 1200)) <= 1, (tiedosto, w, h)


# ---------------------------------------------------------------------------
# ARMONAIKA: miksi 24 h (Villen paatos pyydetty perustelemaan 22.9)
# ---------------------------------------------------------------------------
# Sallittu: kortti = actionable GW, tai actionable - 1 enintaan 24 h sen oman
# deadlinen jalkeen.
#
# ALARAJA. Kortti vaihtuu ensimmaisessa fpl-data-refresh-ajossa deadlinen
# jalkeen, samassa committissa kuin data joka kaantaa actionable GW:n. Ajo on
# 3 h valein (cron "0 */3"). Taman workflow'n oma drift on mitattu ~50 min
# (workflow'n kommentti 29.8), mutta GitHubin ajastin on mitattu 5-12 h
# myohassa (CLAUDE.md saanto 0, 27.-31.8). Pahin ensimmainen yritys ~15 h
# deadlinen jalkeen; 24 h antaa sen lisaksi kaksi uusintayritysta.
#
# YLARAJA. Lyhin vali kahden PL-deadlinen valilla on keskiviikkokierroksilla
# yli 2 vrk, joten 24 h ei koskaan salli kahden kierroksen takaista korttia.
# Armonajan aikana sivulla on juuri pelattavan kierroksen kortti, jonka luvut
# julkaistiin ennen sen deadlinea: figcaption "posts its picks with the
# numbers behind them, before the deadline" on silloinkin tosi.
#
# MIKSI EI 0. Renderoinnin transientti vika (Chrome, FPL-API) nakyy jo
# samassa ajossa fpl-data-refreshin Step healthissa punaisena. Tama portti
# ajetaan tests.yml:ssa jokaisella pushilla ja on ESKALAATIO: se punastuu
# vasta kun uusintayritykset eivat ole korjanneet tilaa. 0 h tekisi jokaisesta
# transientista viasta kahden workflow'n punaisen, ja vilkkuva portti
# opitaan ohittamaan.
#
# MIKSI EI ENEMMAN. 22 vrk:n maaotteluvalilla (GW5 18.9 -> GW6 10.10) mika
# tahansa aikaraja olisi ollut joko turhan pitka tai vaara vaihe: mtime-portin
# 16 vrk olisi hyvaksynyt GW5:n kortin 16 vrk GW6-kierroksen aikana.

def test_armonaika_on_perusteltu_arvo():
    assert P.ARMONAIKA == dt.timedelta(hours=24)


# Todelliset 2026/27 deadlinet (data/gw_calls.json + meta 22.9) + synteettinen
# jatko jossa on keskiviikkokierros (GW7 la -> GW8 ti -> GW9 la).
DEADLINES = {
    2: "2026-08-28T17:30:00+00:00", 3: "2026-09-04T17:30:00+00:00",
    4: "2026-09-12T12:30:00+00:00", 5: "2026-09-18T17:30:00+00:00",
    6: "2026-10-10T10:00:00+00:00", 7: "2026-10-17T10:00:00+00:00",
    8: "2026-10-20T17:30:00+00:00", 9: "2026-10-24T10:00:00+00:00",
}


def _t(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s)


def _meta_at(t: dt.datetime) -> dict:
    """Mita refresh-ajo hetkella t kirjoittaa metaan (kuten build_fpl_phase0:
    deadline_gw = pienin kierros jonka deadline on tulevaisuudessa)."""
    tulevat = [(_t(d), gw) for gw, d in DEADLINES.items() if _t(d) > t]
    if not tulevat:  # kauden tauko: ei tulevaa deadlinea
        return {"deadline_gameweek": None, "deadline_utc": None,
                "next_gameweek": None}
    d, gw = min(tulevat)
    kesken = [g for g, s in DEADLINES.items() if _t(s) <= t < _t(s) + dt.timedelta(days=4)]
    return {"deadline_gameweek": gw, "deadline_utc": d.isoformat(),
            "next_gameweek": kesken[-1] if kesken else gw,
            "completed_gameweeks": [g for g, s in DEADLINES.items()
                                    if _t(s) + dt.timedelta(days=4) <= t]}


def _kortti(gw: int) -> dict:
    return {"gw": gw, "deadline_utc": DEADLINES[gw]}


# (vaihe, kortin GW, hetki jolloin portti ajetaan, hetki jolloin data
# viimeksi kirjoitettiin, odotus)
VAIHEET = [
    ("ennen deadlinea, kortti ajan tasalla", 5,
     "2026-09-17T12:00:00+00:00", "2026-09-17T12:00:00+00:00", True),
    ("ennen deadlinea, kortti edelliselta kierrokselta", 4,
     "2026-09-17T12:00:00+00:00", "2026-09-17T12:00:00+00:00", False),
    ("deadline meni, refresh ei viela ajanut (data vanha)", 5,
     "2026-09-18T19:00:00+00:00", "2026-09-18T16:00:00+00:00", True),
    ("kesken kierroksen, data kaantyi, renderointi kaatui (armonaika)", 5,
     "2026-09-19T12:00:00+00:00", "2026-09-19T12:00:00+00:00", True),
    ("kesken kierroksen, renderointi kaatunut yli 24 h", 5,
     "2026-09-19T18:00:00+00:00", "2026-09-19T18:00:00+00:00", False),
    ("kesken kierroksen, renderointi onnistui", 6,
     "2026-09-19T12:00:00+00:00", "2026-09-19T12:00:00+00:00", True),
    ("gradauksen jalkeen, kortti ajan tasalla", 6,
     "2026-09-22T09:00:00+00:00", "2026-09-22T09:00:00+00:00", True),
    ("gradauksen jalkeen, edellinen kierros", 5,
     "2026-09-22T09:00:00+00:00", "2026-09-22T09:00:00+00:00", False),
    ("pitka tauko (22 vrk), kortti ajan tasalla", 6,
     "2026-10-09T09:00:00+00:00", "2026-10-09T09:00:00+00:00", True),
    ("pitka tauko, 22.9 loydetty tila (GW3 kortti)", 3,
     "2026-09-22T08:00:00+00:00", "2026-09-22T08:00:00+00:00", False),
    ("keskiviikkokierros, armonaika", 7,
     "2026-10-18T09:00:00+00:00", "2026-10-18T09:00:00+00:00", True),
    ("keskiviikkokierros, kaksi kierrosta jaljessa", 6,
     "2026-10-20T18:00:00+00:00", "2026-10-20T18:00:00+00:00", False),
    ("kortti datan edella (eri data kuin sivulla)", 7,
     "2026-09-22T09:00:00+00:00", "2026-09-22T09:00:00+00:00", False),
    ("kauden tauko: ei tulevaa deadlinea", 9,
     "2026-11-30T09:00:00+00:00", "2026-11-30T09:00:00+00:00", True),
]


@pytest.mark.parametrize("vaihe,gw,nyt,data_at,odotus",
                         VAIHEET, ids=[v[0] for v in VAIHEET])
def test_kortin_tila_joka_vaiheessa(vaihe, gw, nyt, data_at, odotus):
    ok, syy = P.kortin_tila(_kortti(gw), _meta_at(_t(data_at)), _t(nyt))
    assert ok is odotus, f"{vaihe}: {syy}"


def test_puuttuva_merkinta_kaatuu():
    ok, syy = P.kortin_tila(None, _meta_at(_t("2026-09-22T09:00:00+00:00")),
                            _t("2026-09-22T09:00:00+00:00"))
    assert not ok and "cards.json" in syy


def _aja_refresh(alku: str, loppu: str, kaatuu=lambda t: False):
    """Simuloi fpl-data-refreshia 3 h valein: liipaisin + renderointi samassa
    ajossa kuin data. Palauttaa (renderointien maara, portin tulokset)."""
    t, loppu_t = _t(alku), _t(loppu)
    manifesti: dict = {}
    renderoinnit, tulokset = 0, []
    while t <= loppu_t:
        meta = _meta_at(t)
        if P.tarvitsee_renderoinnin(manifesti, meta) and not kaatuu(t):
            act = meta["deadline_gameweek"]
            manifesti = {n: {"gw": act, "deadline_utc": meta["deadline_utc"]}
                         for n in P.NIMET}
            renderoinnit += 1
        # Portti ajetaan milla tahansa hetkella ennen seuraavaa ajoa, samaa
        # committoitua dataa vasten.
        for viive in (dt.timedelta(0), dt.timedelta(hours=2, minutes=59)):
            ok = not _tarkista(manifesti, meta, t + viive)
            tulokset.append((t + viive, ok))
        t += dt.timedelta(hours=3)
    return renderoinnit, tulokset


def test_automaatio_pitaa_portin_vihreana_koko_kauden_ja_renderoi_kerran_per_gw():
    """6a kohta 3: invariantti mitataan joka vaiheessa, ei nykyhetkessa.
    29.8 -> 26.10: GW3..GW9 = 7 kierrosta -> tasan 7 renderointia (ei churnia),
    ja portti on vihrea jokaisena hetkena."""
    n, tulokset = _aja_refresh("2026-08-29T00:00:00+00:00",
                               "2026-10-26T00:00:00+00:00")
    punaiset = [t for t, ok in tulokset if not ok]
    assert not punaiset, punaiset[:3]
    assert n == 7, n


def test_kaatuva_renderointi_punastuu_tasan_armonajan_jalkeen():
    """Renderointi kaatuu GW5:n deadlinesta eteenpain: portti on vihrea
    24 h ja punainen sen jalkeen, ei aiemmin eika myohemmin."""
    dl5 = _t(DEADLINES[5])
    _, tulokset = _aja_refresh("2026-09-13T00:00:00+00:00",
                               "2026-09-22T00:00:00+00:00",
                               kaatuu=lambda t: t >= dl5)
    for hetki, ok in tulokset:
        odotus = hetki <= dl5 + P.ARMONAIKA
        assert ok is odotus, (hetki, ok)


def test_liipaisin_ei_renderoi_uudelleen_samalla_kierroksella():
    meta = _meta_at(_t("2026-09-22T09:00:00+00:00"))
    ajan_tasalla = {n: _kortti(6) for n in P.NIMET}
    assert P.tarvitsee_renderoinnin(ajan_tasalla, meta) == []
    assert P.tarvitsee_renderoinnin({}, meta) == P.NIMET
    osittain = {"gameweek-card.webp": _kortti(6),
                "projected-xi-card.webp": _kortti(5)}
    assert P.tarvitsee_renderoinnin(osittain, meta) == ["projected-xi-card.webp"]


# ---------------------------------------------------------------------------
# Muut kuvaportit (4.9)
# ---------------------------------------------------------------------------

def test_kortit_ovat_webpia_eivat_pngta():
    """Mitattu 4.9: sama kortti on PNG:na 192 kB ja WebP:na 32 kB, ja
    laskeutumissivu on pakattuna 26 kB. Kaksi PNG:ta olisi
    kuusinkertaistanut sivun painon."""
    for src in _viittaukset():
        assert src.endswith(".webp"), src


@pytest.mark.parametrize("nimi", sorted(ODOTETUT))
def test_kortti_on_kohtuullisen_kokoinen(nimi):
    p = ROOT / "assets" / "cards" / nimi
    if not p.exists():
        pytest.skip("%s puuttuu" % nimi)
    kb = p.stat().st_size / 1024
    assert kb < 120, "%s on %.0f kB, liikaa laskeutumissivulle" % (nimi, kb)


def test_kuvilla_on_mitat_ja_alt():
    """Ilman width/height sivu hyppaa kun kuva latautuu (CLS); ilman altia
    kuva ei ole olemassa ruudunlukijalle."""
    puutteet = []
    for nimi in SIVUT:
        p = ROOT / nimi
        if not p.exists():
            continue
        teksti = p.read_text(encoding="utf-8")
        for tagi in re.findall(r"<img[^>]*/assets/cards/[^>]*>", teksti):
            if 'width="' not in tagi or 'height="' not in tagi:
                puutteet.append(("mitat", nimi, tagi[:70]))
            # 5.9 portti: tooldir-kuva toistaa kortin oman tekstin -> alt=""
            # (koristeellinen) on oikein; muilla korteilla alt kuvaa sisallon.
            if "/assets/cards/tools/" in tagi:
                if 'alt=""' not in tagi:
                    puutteet.append(("alt-tools", nimi, tagi[:70]))
            elif not re.search(r'alt="[^"]{15,}"', tagi):
                puutteet.append(("alt", nimi, tagi[:70]))
    assert not puutteet, puutteet


def test_julkaisuskripti_ei_kovakoodaa_kierrosta():
    """Skriptin on poimittava uusin kierros, ei osoitettava tiettyyn.

    Mitataan VAIN `re.compile(r"...")`-kuvioista. Ensimmainen versio luki
    koko tiedoston ja osui omaan docstringiinsa ("gw10:n ennen gw9:aa") -
    kolmas kerta samana paivana kun portti mittasi selittavaa tekstiaan
    koodin sijaan.
    """
    src = (ROOT / "scripts" / "publish_cards_to_site.py").read_text(
        encoding="utf-8")
    kuviot = re.findall(r're\.compile\(r"([^"]+)"\)', src)
    assert kuviot, "yhtaan re.compile-kuviota ei loytynyt"
    for k in kuviot:
        assert r"gw(\d+)" in k, k
        assert not re.search(r"gw\d", k.replace(r"gw(\d+)", "")), k


def test_julkaisu_kieltaytyy_eri_kierroksen_lahteesta(tmp_path, monkeypatch):
    """outputs/:iin jaanyt vanha PNG ei saa paatya sivulle tuoreen nimella."""
    Image = pytest.importorskip("PIL.Image")
    src, out = tmp_path / "in", tmp_path / "out"
    src.mkdir()
    Image.new("RGB", (1200, 675), "black").save(src / "goaliq_standouts_gw3.png")
    monkeypatch.setattr(P, "CARDS_IN", src)
    monkeypatch.setattr(P, "CARDS_OUT", out)
    monkeypatch.setattr(P, "MANIFEST", out / "cards.json")
    meta = _meta_at(_t("2026-09-22T09:00:00+00:00"))
    assert P.julkaise(meta, _t("2026-09-22T09:00:00+00:00")) == 0
    assert not (out / "gameweek-card.webp").exists()
    # Negatiivinen kontrolli: oikean kierroksen lahde julkaistaan.
    Image.new("RGB", (1200, 675), "black").save(src / "goaliq_standouts_gw6.png")
    assert P.julkaise(meta, _t("2026-09-22T09:00:00+00:00")) == 1
    m = json.loads((out / "cards.json").read_text(encoding="utf-8"))
    assert m["gameweek-card.webp"]["gw"] == 6
    assert (out / "gameweek-card-450.webp").exists()
