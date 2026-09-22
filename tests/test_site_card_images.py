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
Nyt portti ei lue aikaa tiedostosta lainkaan. Julkaisuportin 22.9
blokkauksen jalkeen se ei myoskaan vertaa pelkkaa kierrosta: se vertaa
`assets/cards/cards.json`:n SISALTOTIIVISTETTA siihen mita kortti nykyisesta
projektiosta nayttaisi (`publish_cards_to_site.kortin_tila`,
`nykyiset_tiivisteet`), ja sama funktio ajetaan alla jokaisessa kierroksen
vaiheessa (CLAUDE.md 6a kohta 3).
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
# SISALTOPORTTI (22.9): kortti vs nykyinen projektio, ei kierros eika aika
# ---------------------------------------------------------------------------
# Ensimmainen versio vertasi kortin KIERROSTA dataan. Julkaisuportti blokkasi
# sen 22.9: GW6:n kortti olisi ollut "ajan tasalla" koko 22 vrk:n
# maaotteluvalin, vaikka /fpl/expected-points paivittyy 3 h valein ja kortin
# prosentit tarkistetaan sielta. Nyt vertailtava on kortin NAKYVAN sisallon
# tiiviste (`card_shot.content_signature`), laskettuna samalla funktiolla
# jolla kortti renderoidaan (`current_card_html`).

def _tarkista(manifesti: dict, nykyiset: dict, meta: dict,
              now: dt.datetime) -> list[str]:
    """Repon tila -testin JA negatiivisten kontrollien yhteinen kutsupaikka."""
    viat = []
    for nimi in P.NIMET:
        ok, syy = P.kortin_tila(manifesti.get(nimi), nykyiset.get(nimi), meta, now)
        if not ok:
            viat.append(f"{nimi}: {syy}")
    return viat


def test_etusivun_kortit_vastaavat_nykyista_projektiota():
    now = dt.datetime.now(UTC)
    viat = _tarkista(P.lue_manifesti(), P.nykyiset_tiivisteet(now),
                     P.lue_meta(), now)
    assert not viat, (
        "Etusivun kortti ei nayta sita mita nykyinen projektio sanoo. "
        "Vakionimi saa vanhan kortin nayttamaan tuoreelta:\n  " + "\n  ".join(viat))


META6 = {"deadline_gameweek": 6, "deadline_utc": "2026-10-10T10:00:00+00:00",
         "next_gameweek": 6}


def test_negatiivinen_kontrolli_22_9_tilanne_kaatuu():
    """Tasan se tila joka loytyi 22.9: GW3:n kortti, data GW6:ssa. GW3:n
    kortin sisalto on eri kuin GW6:n, eika renderointia ole yritetty."""
    gw3 = {"gw": 3, "signature": "gw3-kortti"}
    viat = _tarkista({n: gw3 for n in P.NIMET},
                     {n: "gw6-kortti" for n in P.NIMET}, META6,
                     dt.datetime(2026, 9, 22, 8, 0, tzinfo=UTC))
    assert len(viat) == 2 and all("ei ole yritetty" in v for v in viat), viat


def _standouts_data(p_haul_b: float = 0.30, xp_b: float = 6.0) -> dict:
    """Pienin syote jolla OIKEA standouts-pohja renderoituu (4 tiilta)."""
    def p(pid, name, club, xp, haul, blank, p90):
        return {"id": pid, "web_name": name, "pos": "MID", "team_short": club,
                "team": club, "price": 7.5, "status": "a", "p_start": 0.9,
                "xp_horizon_total": xp * 6, "xp_per_gw": xp,
                "gameweeks": [{"gw": 6, "xp": xp}],
                "xp_dist": {"gw": 6, "n": 2000, "mean": xp, "p_haul": haul,
                            "p_blank": blank, "p10": 1, "median": 4,
                            "p90": p90, "haul_pts": 10, "blank_pts": 2}}
    return {"meta": dict(META6, available=True,
                         generated_at="2026-09-22T08:07:47+00:00"),
            "players": [p(1, "Bee", "AAA", xp_b, p_haul_b, 0.10, 13),
                        p(2, "Cee", "BBB", 5.0, 0.28, 0.30, 15),
                        p(3, "Dee", "CCC", 4.5, 0.10, 0.12, 9),
                        p(4, "Eff", "DDD", 3.0, 0.20, 0.45, 12)]}


def _sig(data: dict) -> str:
    from scripts.card_shot import content_signature
    from scripts.render_standouts_card import build_html
    return content_signature(build_html(data, log=None)[0])


def test_projektiomuutos_saman_kierroksen_sisalla_kaatuu_ilman_renderointia():
    """Julkaisuportin vaatimus 22.9: GW ei vaihdu, mutta kortin nakyva luku
    muuttuu (Bee 30 % -> 25 % 10+). Kortti jota ei renderoitu kaatuu."""
    ennen = _sig(_standouts_data(p_haul_b=0.30))
    jalkeen = _sig(_standouts_data(p_haul_b=0.25))
    assert ennen != jalkeen
    entry = {"gw": 6, "signature": ennen}
    now = dt.datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
    ok, syy = P.kortin_tila(entry, jalkeen, META6, now)
    assert not ok and "ei ole yritetty" in syy, syy
    # Renderoitu uudelleen -> vihrea.
    assert P.kortin_tila({"gw": 6, "signature": jalkeen}, jalkeen, META6, now)[0]


def test_nakymaton_muutos_ei_renderoi():
    """Ei churnia: xP 6.00 -> 6.01 ei muuta yhtaan kortilla nakyvaa merkkia
    (kortti ei nayta standouts-pelaajan xP:ta), joten tiiviste pysyy."""
    assert _sig(_standouts_data(xp_b=6.0)) == _sig(_standouts_data(xp_b=6.01))


def test_projektion_aikaleima_ei_kuulu_tiivisteeseen():
    a = _standouts_data()
    b = _standouts_data()
    b["meta"]["generated_at"] = "2026-09-22T11:07:47+00:00"
    assert _sig(a) == _sig(b)


def test_kaatunut_yritys_saa_armonajan_ja_vain_sen():
    now = dt.datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
    entry = {"gw": 6, "signature": "vanha",
             "stale_since": "2026-09-25T00:00:00+00:00"}
    assert P.kortin_tila(entry, "uusi", META6, now)[0]              # 12 h
    assert not P.kortin_tila(entry, "uusi", META6,
                             now + dt.timedelta(hours=13))[0]        # 25 h
    # Korttia ei voi muodostaa nykyisesta datasta: sama armonaika.
    assert P.kortin_tila(entry, None, META6, now)[0]
    assert not P.kortin_tila({"gw": 6, "signature": "vanha"}, None, META6, now)[0]


def test_puuttuva_merkinta_kaatuu():
    ok, syy = P.kortin_tila(None, "x", META6, dt.datetime(2026, 9, 22, tzinfo=UTC))
    assert not ok and "cards.json" in syy
    ok, _ = P.kortin_tila({"gw": 6}, "x", META6, dt.datetime(2026, 9, 22, tzinfo=UTC))
    assert not ok, "kierros ilman tiivistetta ei riita"


def test_kauden_tauko_ei_vertaa():
    meta = {"deadline_gameweek": None, "deadline_utc": None, "next_gameweek": None}
    assert P.kortin_tila(None, None, meta, dt.datetime(2026, 6, 1, tzinfo=UTC))[0]
    assert P.tarvitsee_renderoinnin({}, {n: None for n in P.NIMET}, meta) == []


@pytest.mark.parametrize("nimi", P.NIMET)
def test_manifesti_kuvaa_sivun_tiedostot(nimi):
    """cards.json:n tiiviste koskee VAIN sita kuvaa jonka sha256 siina on.
    Kasin vaihdettu kuva (ohi publish_cards_to_site:n) kaataa taman, joten
    merkinta ei voi jaada kuvaamaan eri kuvaa."""
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
# ARMONAIKA: miksi 24 h
# ---------------------------------------------------------------------------
# Poikkeama kortin ja nykyisen projektion valilla sallitaan VAIN kun
# renderointia on yritetty ja se kaatui, ja enintaan 24 h ensimmaisesta
# kaatumisesta (cards.json `stale_since`, jota myohemmat yritykset eivat
# siirra). Ilman yritysta poikkeama kaatuu heti.
#
# MIKSI POIKKEAMA VOI OLLA OLEMASSA LAINKAAN. Kortti renderoidaan samassa
# fpl-data-refresh-ajossa kuin data joka sen muuttaa, ja molemmat
# committoidaan samaan committiin. Committoitu tila voi siis erota vain jos
# renderointi kaatui (Chrome, asetteluportti, loki eroaa kortista ennen
# deadlinea). Ajastimen myohastyminen EI tuota poikkeamaa: jos refresh ei
# aja, dataakaan ei paivity.
#
# MIKSI 24 H. Refresh ajaa 3 h valein, joten 24 h = noin kahdeksan
# uusintayritysta. Kaatuminen nakyy jo samassa ajossa Step healthissa
# punaisena; tama portti on tests.yml:n ESKALAATIO joka punastuu vasta kun
# uusinnat eivat ole korjanneet tilaa. 0 h tekisi jokaisesta transientista
# viasta kahden workflow'n punaisen, ja vilkkuva portti opitaan ohittamaan.
# Ylaraja: keskiviikkokierroksilla deadlineiden vali on yli 2 vrk, joten
# kaatunut kortti ei voi jaada kahden kierroksen taakse armonajan sisalla.

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
# Projektiomuutokset jotka nakyvat kortilla SAMAN kierroksen sisalla
# (loukkaantuminen maaotteluvalilla, pressit ennen deadlinea jne.).
MUUTOKSET = ["2026-09-25T12:00:00+00:00", "2026-10-03T15:00:00+00:00",
             "2026-10-09T13:00:00+00:00", "2026-10-19T12:00:00+00:00"]


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
    return {"deadline_gameweek": gw, "deadline_utc": d.isoformat(),
            "next_gameweek": gw}


def _nykyinen_at(t: dt.datetime) -> str | None:
    """Kortin nakyva sisalto hetkella t: kierros + saman kierroksen versio."""
    gw = _meta_at(t)["deadline_gameweek"]
    if gw is None:
        return None
    versio = sum(1 for m in MUUTOKSET if _t(m) <= t)
    return f"GW{gw}-v{versio}"


def _aja_refresh(alku: str, loppu: str, kaatuu=lambda t: False):
    """Simuloi fpl-data-refreshia 3 h valein: liipaisin + renderointi +
    stale_since samassa ajossa kuin data. Palauttaa (renderoinnit, tulokset)."""
    t, loppu_t = _t(alku), _t(loppu)
    manifesti: dict = {}
    renderoinnit, tulokset = 0, []
    while t <= loppu_t:
        meta, nyk = _meta_at(t), _nykyinen_at(t)
        nykyiset = {n: nyk for n in P.NIMET}
        vanhat = P.tarvitsee_renderoinnin(manifesti, nykyiset, meta)
        if vanhat and not kaatuu(t):
            for n in vanhat:
                manifesti[n] = {"gw": meta["deadline_gameweek"], "signature": nyk}
            renderoinnit += 1
        elif vanhat:
            for n in vanhat:  # kuten merkitse_vanhaksi: ensimmainen kaatuminen jaa
                manifesti.setdefault(n, {}).setdefault("stale_since", t.isoformat())
        # Portti ajetaan milla tahansa hetkella ennen seuraavaa ajoa, samaa
        # committoitua dataa vasten.
        for viive in (dt.timedelta(0), dt.timedelta(hours=2, minutes=59)):
            ok = not _tarkista(manifesti, nykyiset, meta, t + viive)
            tulokset.append((t + viive, ok))
        t += dt.timedelta(hours=3)
    return renderoinnit, tulokset


def test_automaatio_pitaa_portin_vihreana_ja_renderoi_vain_muutoksesta():
    """6a kohta 3: invariantti mitataan joka vaiheessa, ei nykyhetkessa.
    29.8 -> 26.10: 7 kierrosta (GW3..GW9) + 4 saman kierroksen muutosta =
    tasan 11 renderointia (ei churnia 3 h valein), portti vihrea joka hetki,
    myos 22 vrk:n maaotteluvalilla ja kauden tauolla."""
    n, tulokset = _aja_refresh("2026-08-29T00:00:00+00:00",
                               "2026-10-26T00:00:00+00:00")
    punaiset = [t for t, ok in tulokset if not ok]
    assert not punaiset, punaiset[:3]
    assert n == 11, n


def test_kaatuva_renderointi_punastuu_tasan_armonajan_jalkeen():
    """Renderointi kaatuu 25.9 12:00 muutoksesta eteenpain (saman kierroksen
    sisalla): portti on vihrea 24 h ensimmaisesta kaatuneesta ajosta ja
    punainen sen jalkeen, ei aiemmin eika myohemmin."""
    raja = _t(MUUTOKSET[0])
    _, tulokset = _aja_refresh("2026-09-22T00:00:00+00:00",
                               "2026-09-28T00:00:00+00:00",
                               kaatuu=lambda t: t >= raja)
    for hetki, ok in tulokset:
        assert ok is (hetki <= raja + P.ARMONAIKA), (hetki, ok)


def test_merkitse_vanhaksi_ei_siirra_ensimmaista_kaatumista(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "MANIFEST", tmp_path / "cards.json")
    eka = _t("2026-09-25T12:00:00+00:00")
    P.merkitse_vanhaksi(["gameweek-card.webp"], eka)
    tavut = (tmp_path / "cards.json").read_bytes()
    P.merkitse_vanhaksi(["gameweek-card.webp"], eka + dt.timedelta(hours=3))
    assert (tmp_path / "cards.json").read_bytes() == tavut, "ei tiedostomuutosta"
    assert P.lue_manifesti(tmp_path / "cards.json")["gameweek-card.webp"][
        "stale_since"] == "2026-09-25T12:00:00+00:00"


def test_liipaisin_renderoi_vain_muuttuneen_kortin():
    meta = _meta_at(_t("2026-09-22T09:00:00+00:00"))
    nykyiset = {"gameweek-card.webp": "a", "projected-xi-card.webp": "b"}
    ajan_tasalla = {"gameweek-card.webp": {"signature": "a"},
                    "projected-xi-card.webp": {"signature": "b"}}
    assert P.tarvitsee_renderoinnin(ajan_tasalla, nykyiset, meta) == []
    assert P.tarvitsee_renderoinnin({}, nykyiset, meta) == P.NIMET
    osittain = dict(ajan_tasalla, **{"projected-xi-card.webp": {"signature": "vanha"}})
    assert P.tarvitsee_renderoinnin(osittain, nykyiset, meta) == ["projected-xi-card.webp"]
    # Korttia ei voi muodostaa -> yritetaan (ja kaatuminen kirjataan).
    assert P.tarvitsee_renderoinnin(ajan_tasalla, dict(nykyiset, **{
        "gameweek-card.webp": None}), meta) == ["gameweek-card.webp"]


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


def test_julkaisu_kieltaytyy_lahteesta_joka_ei_vastaa_projektiota(tmp_path, monkeypatch):
    """outputs/:iin jaanyt vanha PNG ei saa paatya sivulle tuoreen nimella:
    lahteen HTML:n tiivisteen on oltava nykyinen."""
    Image = pytest.importorskip("PIL.Image")
    from scripts.card_shot import content_signature
    src, out = tmp_path / "in", tmp_path / "out"
    src.mkdir()
    Image.new("RGB", (1200, 675), "black").save(src / "goaliq_standouts_gw6.png")
    (src / "goaliq_standouts_gw6.html").write_text(
        "<div class='card'>GW6 vanha</div>", encoding="utf-8")
    monkeypatch.setattr(P, "CARDS_IN", src)
    monkeypatch.setattr(P, "CARDS_OUT", out)
    monkeypatch.setattr(P, "MANIFEST", out / "cards.json")
    now = _t("2026-09-22T09:00:00+00:00")
    uusi = content_signature("<div class='card'>GW6 uusi</div>")
    nykyiset = {"gameweek-card.webp": uusi, "projected-xi-card.webp": None}
    assert P.julkaise(nykyiset, META6, now) == 0
    assert not (out / "gameweek-card.webp").exists()
    # Negatiivinen kontrolli: nykyista vastaava lahde julkaistaan.
    (src / "goaliq_standouts_gw6.html").write_text(
        "<div class='card'>GW6 uusi</div>", encoding="utf-8")
    assert P.julkaise(nykyiset, META6, now) == 1
    m = json.loads((out / "cards.json").read_text(encoding="utf-8"))
    assert m["gameweek-card.webp"]["signature"] == uusi
    assert m["gameweek-card.webp"]["gw"] == 6
    assert "stale_since" not in m["gameweek-card.webp"]
    assert (out / "gameweek-card-450.webp").exists()
