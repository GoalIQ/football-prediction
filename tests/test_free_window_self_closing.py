# -*- coding: utf-8 -*-
"""Paistettu sivu sulkee ilmaisikkunan ITSE (17.9.2026, ILMAISIKKUNA-SULKEUTUU-ITSE).

MITATTU 12.9.2026. Ikkuna sulkeutui 12:30 UTC. Livena lupaus eli 19 kohdassa
6 sivulla, ja se katosi vasta kun ihminen dispatchasi `fpl-page-refresh`in
12:31 (valmis 12:41). Ajastettua sivuajoa ei ollut 12:30-15:00 valilla:
tuntislotti on deadline-vahdittu ja skippasi, seuraava 3 h -ajo oli 15:00.
Ilman ihmista lupaus olisi elanyt 2,5 h yli lupauksensa. SPA ja mobiili
sulkeutuivat itse, koska ne lukevat aikaleiman AJOSSA; paistettu sivu luki
sen PAISTOSSA.

Korjaus (saanto 6a): `src.free_window.self_closing_block`. Suljettu teksti
on lohkon staattinen oletus; avoin teksti elaa inertissa `<template>`-
elementissa ja inline-skripti nayttaa sen vain kun selaimen
`Date.now() < data-until`. Ilman JavaScriptia nakyy suljettu teksti.

Kolme mekanismia, kolme porttia tassa tiedostossa:
  (1) YKSI LUKIJA: `open_at()` on sama predikaatti Pythonissa ja skriptissa
      (`Date.now()<u`), ja portin template-lukija kayttaa sita.
  (2) YKSI LAHDE: `data-until` on `FREE_PREMIUM_UNTIL`, `api/premium.py`
      (oikeuden portti) TUO saman hetken, ja jokainen muu tiedosto joka
      nimeaa ikkunan saa kantaa vain samaksi HETKEKSI jasentyvia
      aikaleimoja. 18.9.2026: tassa luki ennen "aikaleima on kirjoitettu
      tasan yhteen tiedostoon" - se oli epatosi, ja sita vartioi testi joka
      skannasi kolme kasin nimettya tiedostoa neljasta pinnasta.
  (3) INVARIANTTI JOKA VAIHEESSA: jokainen lohko renderoidaan synteettisella
      kellolla ennen / tasan / jalkeen, ja jokaisessa vaiheessa staattinen
      HTML on ilman lupausta. Skripti ajetaan Nodessa samoilla vaiheilla.

Ja KUTSUPAIKKA: testi lukee `build_fpl_page.py`:n lahteen ja vaatii etta
`free_window_block` kulkee `self_closing_block`in kautta eika haaraudu
`is_open()`:lla paistohetkella - se oli tasan 12.9:n vika.
"""
from __future__ import annotations

import datetime as dt
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.check_free_window as C  # noqa: E402
from scripts.build_fpl_page import free_window_block  # noqa: E402
from src import free_window as FW  # noqa: E402

UNTIL = FW.until()
ENNEN = UNTIL - dt.timedelta(hours=1)
TASAN = UNTIL
JALKEEN = UNTIL + dt.timedelta(hours=1)
VAIHEET = [("ennen", ENNEN), ("tasan", TASAN), ("jalkeen", JALKEEN)]

#: Kaikki paistetut lohkot joissa lupaus on elanyt: index.html x4,
#: predictions.html x1 (GEN-lohkot) ja fpl.html (builderin lohko).
LOHKOT = {f"{f}:{k}": r for (f, k), r in FW.SURFACE_BLOCKS.items()}
LOHKOT["fpl.html:FREE-UPSELL"] = free_window_block


def _js_nakyma(html: str, now) -> str:
    """Mita JS-lukija nakee hetkella `now` (sama lukija kuin portilla)."""
    return C.luettava_teksti(html, now)[0]


def _staattinen_nakyma(html: str) -> str:
    """Mita JS:ton lukija nakee: template ei nay koskaan."""
    return C.luettava_teksti(html, ilman_js=True)[0]


def _lupaa(nakyma: str) -> bool:
    return bool(C.CLAIM_RE.search(nakyma) or C.DATED_PRICE_RE.search(nakyma))


# ---------------------------------------------------------------------------
# 1. DoD: staattinen HTML ei lupaa MISSAAN vaiheessa
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nimi,renderoija", list(LOHKOT.items()))
@pytest.mark.parametrize("vaihe,kello", VAIHEET)
def test_staattinen_html_ei_lupaa_missaan_vaiheessa(nimi, renderoija,
                                                    vaihe, kello):
    """Ilman JavaScriptia lupaus ei ole DOM:ssa nakyvana, paistettiinpa sivu
    ennen deadlinea, tasan silla tai sen jalkeen. Tama on se ominaisuus
    joka tekee 12.9:n vian mahdottomaksi: sivu ei voi jaada lupaamaan."""
    html = renderoija(kello)
    nakyma = _staattinen_nakyma(html)
    assert not _lupaa(nakyma), f"{nimi} @ {vaihe}: {nakyma!r}"


@pytest.mark.parametrize("nimi,renderoija", list(LOHKOT.items()))
def test_js_lukija_nakee_lupauksen_vain_ennen_deadlinea(nimi, renderoija):
    """KONTROLLI + invariantti. Lohko paistettu ennen deadlinea: JS-lukija
    nakee lupauksen ENNEN, ei TASAN eika JALKEEN. Ilman ENNEN-haaraa
    edellinen testi lapaisisi lohkolla joka ei lupaa koskaan mitaan
    (muisti: kontrolli-lapaisi-tyhjana)."""
    html = renderoija(ENNEN)
    assert _lupaa(_js_nakyma(html, ENNEN)), f"{nimi}: lupaus puuttuu ennen deadlinea"
    assert not _lupaa(_js_nakyma(html, TASAN)), f"{nimi}: lupaus nakyy tasan deadlinella"
    assert not _lupaa(_js_nakyma(html, JALKEEN)), f"{nimi}: lupaus nakyy deadlinen jalkeen"


@pytest.mark.parametrize("nimi,renderoija", list(LOHKOT.items()))
def test_kiinni_paistettu_lohko_ei_kanna_avointa_haaraa(nimi, renderoija):
    """Kun ikkuna on kiinni jo paistohetkella, avointa tekstia ei voi enaa
    koskaan tarvita: sita ei jateta lahdekoodiin naiivin raapijan
    luettavaksi. Lohko on pelkka suljettu HTML."""
    for kello in (TASAN, JALKEEN):
        html = renderoija(kello)
        assert not C.TEMPLATE_RE.search(html), nimi
        assert "data-free-window" not in html, nimi
        assert "<script" not in html, nimi


@pytest.mark.parametrize("nimi,renderoija", list(LOHKOT.items()))
def test_lohkon_rakenne_ja_jarjestys(nimi, renderoija):
    """Avoin template ENSIN, suljettu HTML, paatemarkkeri, skripti. Skripti
    irrottaa solmut kahden templaten valista, joten jarjestys on osa
    mekanismia eika kosmetiikkaa."""
    html = renderoija(ENNEN)
    m = C.TEMPLATE_RE.search(html)
    assert m, f"{nimi}: avoin template puuttuu"
    avain = m.group(1)
    loppu = html.find(f'<template {FW.END_ATTR}="{avain}"></template>')
    skripti = html.find("<script>")
    assert m.end() < loppu < skripti, (nimi, m.end(), loppu, skripti)
    # Suljettu HTML on templatejen valissa - ja se on tasan se mita
    # suljettu paisto tuottaa.
    valissa = html[m.end():loppu].strip()
    assert valissa == renderoija(JALKEEN).strip(), nimi
    # Skripti on sidottu SAMAAN avaimeen.
    assert html.endswith(f"({json.dumps(avain)});</script>"), nimi


# ---------------------------------------------------------------------------
# 2. Koko sivu synteettisella kellolla (render_blocks -> index/predictions)
# ---------------------------------------------------------------------------

def _kopioi_gen_sivut(tmp_path: Path) -> Path:
    for tiedosto in {f for f, _ in FW.SURFACE_BLOCKS}:
        shutil.copy2(ROOT / tiedosto, tmp_path / tiedosto)
    return tmp_path


def test_koko_sivu_synteettisella_kellolla(tmp_path, monkeypatch):
    """DoD sivutasolla. Paistetaan index.html ja predictions.html ENNEN
    deadlinea ja luetaan ne kolmella kellolla.

    12.9 livena: goaliq.app/ 5 lupausta, /predictions 2. Samat luvut
    vaaditaan JS-lukijalta ennen deadlinea - ja nolla staattiselta lukijalta
    ja JS-lukijalta deadlinen jalkeen."""
    juuri = _kopioi_gen_sivut(tmp_path)
    monkeypatch.setattr(C, "ROOT", juuri)
    muuttuneet = C.render_blocks(ENNEN)
    assert len(muuttuneet) == len(FW.SURFACE_BLOCKS), muuttuneet
    sivut = [juuri / f for f in sorted({f for f, _ in FW.SURFACE_BLOCKS})]

    # Staattinen HTML: ei lupausta, riippumatta kellosta.
    assert C.static_hits(sivut) == []
    # JS-lukija ennen deadlinea: samat luvut kuin livena 12.9.
    ennen = C.hits(sivut, now=ENNEN)
    per_sivu = {}
    for f, _ln, _t in ennen:
        per_sivu[f] = per_sivu.get(f, 0) + 1
    assert per_sivu == {"index.html": 5, "predictions.html": 2}, per_sivu
    # JS-lukija tasan ja jalkeen: nolla - myos paivamaarahintavaite.
    assert C.hits(sivut, now=TASAN) == []
    assert C.hits(sivut, now=JALKEEN) == []
    # Aikaleima on lahteesta.
    assert C.until_mismatches(sivut) == []
    # Rajaus: templaten lupaus on rajattu webiin.
    assert C.scope_misses(sivut) == []

    # Ja paisto deadlinen JALKEEN pyyhkii avoimen haaran kokonaan.
    C.render_blocks(JALKEEN)
    for p in sivut:
        assert not C.TEMPLATE_RE.search(p.read_text(encoding="utf-8")), p.name
    assert C.hits(sivut, now=ENNEN) == [], "kiinni paistettu sivu ei lupaa edes menneella kellolla"


def test_fix_kiinni_poistaa_avoimen_haaran_gen_lohkosta(tmp_path, monkeypatch):
    """`--fix` page-refreshissa: ikkunan sulkeuduttua avoin haara poistuu
    lahdekoodista JA staattinen sivu on ollut oikein koko ajan."""
    juuri = _kopioi_gen_sivut(tmp_path)
    monkeypatch.setattr(C, "ROOT", juuri)
    C.render_blocks(ENNEN)
    sivut = [juuri / f for f in sorted({f for f, _ in FW.SURFACE_BLOCKS})]
    assert C.static_hits(sivut) == []
    muutetut = C.fix(now=JALKEEN)
    assert muutetut, "fix ei renderoinut lohkoja uudelleen"
    for p in sivut:
        assert "data-free-window" not in p.read_text(encoding="utf-8"), p.name
    assert C.hits(sivut, now=JALKEEN) == []


# ---------------------------------------------------------------------------
# 3. YKSI LAHDE: aikaleima
# ---------------------------------------------------------------------------

def test_data_until_on_lahteesta():
    for nimi, r in LOHKOT.items():
        for _avain, until, _rivi in C.templates(r(ENNEN)):
            assert until == FW.FREE_PREMIUM_UNTIL, (nimi, until)


_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})")


#: Tiedostot joita skannaus EI lue, ja miksi. Kaksi perustelua, ei kolmatta:
#:   - `tests/`: testit kirjoittavat synteettisia aikaleimoja (2099-01-01,
#:     freeze-fikstuurit) tarkoituksella, ja niiden PITAA erota.
#:   - `node_modules/`, `.git/`, `__pycache__/`: ei meidan koodia.
_SKANNAUKSEN_ULKOPUOLELLA = ("tests", "node_modules", ".git", "__pycache__")


def _ikkunan_kirjoittajat(juuri: Path | None = None) -> dict[str, list[str]]:
    """{polku: [ISO-aikaleimat]} jokaisesta tiedostosta joka NIMEAA ikkunan.

    Joukko johdetaan NIMESTA (`FREE_PREMIUM_UNTIL`), ei kasin nimetysta
    listasta: uusi pinta joka kirjoittaa ikkunan hetken joutuu skannauksen
    piiriin kayttamalla samaa nimea kuin kolme olemassa olevaa. Kasin
    nimetty lista oli tasan se vika joka 18.9 loydettiin.
    """
    juuri = juuri or ROOT
    ulos: dict[str, list[str]] = {}
    for kansio, alikansiot, tiedostot in os.walk(juuri):
        # Karsitaan paikan paalla: `rglob` kavelisi node_modulesin lapi.
        alikansiot[:] = [d for d in alikansiot
                         if d not in _SKANNAUKSEN_ULKOPUOLELLA]
        for nimi in tiedostot:
            if not nimi.endswith((".py", ".ts", ".svelte")):
                continue
            p = Path(kansio) / nimi
            teksti = p.read_text(encoding="utf-8", errors="ignore")
            if "FREE_PREMIUM_UNTIL" not in teksti:
                continue
            leimat = _ISO_RE.findall(teksti)
            if leimat:
                ulos[p.relative_to(juuri).as_posix()] = leimat
    return ulos


def test_ikkunan_hetki_on_sama_jokaisella_pinnalla():
    """🔴 18.9.2026: TASSA OLI VAARA VAITE JA SITA VARTIOIVA VAARA TESTI.

    Testin nimi oli `test_aikaleima_on_kirjoitettu_tasan_yhteen_tiedostoon`
    ja se skannasi KOLME kasin nimettya tiedostoa. Hetki oli tosiasiassa
    kirjoitettu neljaan paikkaan ja kahdessa eri muodossa:

        src/free_window.py                       "2026-09-12T12:30:00Z"
        api/premium.py                           "2026-09-12T12:30:00+00:00"
        web/pro-spa/src/lib/auth.svelte.ts       '2026-09-12T12:30:00Z'
                                                 (23.9 alkaen freeWindow.ts)
        goaliq-app/lib/freePremiumWindow.ts      (ERI REPO)

    `api/premium.py` on OIKEUDEN portti - se ratkaisee kuka oikeasti saa
    premiumin. Seuraava ikkuna olisi voitu avata `src/free_window.py`:sta ja
    unohtaa `api/premium.py`: paistetut sivut olisivat luvanneet ilmaista
    Premiumia siihen asti kun API ei enaa anna sita. `until_mismatches`
    vertaa sivun `data-until`-arvoa vain `src.free_window`:iin, `static_hits`
    olisi tyhja (lupaus on templatessa, oikein), ja koko portti exit 0.

    Korjaus on kaksiosainen:
      (1) `api/premium.py` TUO hetken `src.free_window`:sta - kaksi
          kirjoittajaa yhdeksi lukijaksi (mekanismi 1).
      (2) TypeScript ei voi importata Pythonia, joten se vartioidaan
          HETKENA eika merkkijonona: jokainen tiedosto joka nimeaa
          `FREE_PREMIUM_UNTIL`:in saa kantaa vain aikaleimoja jotka
          jasentyvat samaksi hetkeksi.
    """
    import api.premium as prem  # noqa: E402

    hetki = FW.until()

    # (1) Oikeuden portti lukee saman hetken - ei omaa literaalia.
    assert prem.free_premium_window_end() == hetki, (
        "api/premium.py antaa premiumin eri hetkeen kuin sivut lupaavat")
    prem_lahde = (ROOT / "api" / "premium.py").read_text(encoding="utf-8")
    prem_koodi = re.sub(r'^\s*#.*$|"""[\s\S]*?"""', "", prem_lahde, flags=re.M)
    assert not _ISO_RE.search(prem_koodi), (
        "api/premium.py kirjoittaa aikaleiman itse - se on toinen kirjoittaja")

    # (2) Jokainen ikkunan nimeava tiedosto kantaa SAMAA HETKEA.
    kirjoittajat = _ikkunan_kirjoittajat()
    assert "src/free_window.py" in kirjoittajat, kirjoittajat
    # 23.9: SPA:n hetki siirtyi auth.svelte.ts:sta freeWindow.ts:aan
    # (SPA-IKKUNAN-PAIVA-KIRJOITETTU-AUKI), auth vie sen eteenpain.
    assert "web/pro-spa/src/lib/freeWindow.ts" in kirjoittajat, (
        "SPA:n aikaleimaa ei enaa loydy - skannaus on sokea, ei tyhja")
    for polku, leimat in kirjoittajat.items():
        for leima in leimat:
            assert FW.parse_until(leima) == hetki, (
                f"{polku} kirjoittaa ikkunan hetkeksi {leima!r}, "
                f"mutta lahde on {FW.FREE_PREMIUM_UNTIL!r} ({hetki}). "
                "Sivut ja API sulkisivat ikkunan eri hetkella.")

    # (3) Portti ja builderi eivat kirjoita aikaleimaa lainkaan.
    for muu in ("scripts/check_free_window.py", "scripts/build_fpl_page.py"):
        teksti = (ROOT / muu).read_text(encoding="utf-8")
        koodi = re.sub(r'^\s*#.*$|"""[\s\S]*?"""', "", teksti, flags=re.M)
        assert not _ISO_RE.search(koodi), f"{muu} kirjoittaa aikaleiman itse"


def test_skannaus_nakee_eri_hetken_myos_eri_muodossa(tmp_path):
    """EROTTELEVUUS. Vika jota vastaan (2) on kirjoitettu ei ole "eri
    merkkijono" vaan ERI HETKI, ja se saapuu ERI MUODOSSA (`+00:00` vs `Z`).
    Sama hetki eri muodossa EI saa kaataa, eri hetki saa - muuten testi
    vartioisi muotoa eika vaitetta."""
    hetki = FW.until()
    assert FW.parse_until("2026-09-12T12:30:00+00:00") == hetki
    assert FW.parse_until("2026-09-12T12:30:00Z") == hetki
    assert FW.parse_until("2026-10-03T17:30:00Z") != hetki

    # Skannaus loytaa eriavan hetken tiedostosta joka NIMEAA ikkunan -
    # myos syvalta puusta ja tiedostosta jota ei ole kasin nimetty.
    lib = tmp_path / "web" / "pro-spa" / "src" / "lib"
    lib.mkdir(parents=True)
    (lib / "auth.svelte.ts").write_text(
        "export const FREE_PREMIUM_UNTIL = '2026-10-03T17:30:00Z';",
        encoding="utf-8")
    loydot = _ikkunan_kirjoittajat(tmp_path)
    assert loydot == {"web/pro-spa/src/lib/auth.svelte.ts":
                      ["2026-10-03T17:30:00Z"]}, loydot
    assert any(FW.parse_until(x) != hetki
               for leimat in loydot.values() for x in leimat), loydot

    # Ja tiedosto joka EI nimea ikkunaa jaa ulos: skannaus ei kaadu
    # satunnaisesta aikaleimasta (esim. kausifikstuurista).
    (tmp_path / "muu.py").write_text('KAUSI = "2026-10-03T17:30:00Z"',
                                     encoding="utf-8")
    assert "muu.py" not in _ikkunan_kirjoittajat(tmp_path)


def test_mobiilirepon_aikaleima_kun_se_on_saatavilla():
    """NELJAS PINTA on ERI REPOSSA (`goaliq-app/lib/freePremiumWindow.ts`)
    eika CI nae sita: fp-checkoutissa ei ole sisarrepoa, eika sita voi
    vaatia olemaan. Tama on siksi PAIKALLINEN lisatarkistus, EI portti - ja
    se on kirjattu auki, jotta puuttuva kate nakyy eika nayta hoidetulta
    (muisti: osittainen kate on pahempi kuin ei katetta).

    Mobiilipuolen oma portti asuu `goaliq-app`-repossa; tama kertoo Villen
    koneella heti jos ne ajautuvat erilleen.
    """
    mob = ROOT.parent / "goaliq-app" / "lib" / "freePremiumWindow.ts"
    if not mob.is_file():
        pytest.skip(f"mobiilirepoa ei ole talla koneella: {mob}")
    leimat = _ISO_RE.findall(mob.read_text(encoding="utf-8"))
    assert leimat, "mobiilin aikaleimaa ei loytynyt - tiedosto muuttui"
    for leima in leimat:
        assert FW.parse_until(leima) == FW.until(), (
            f"mobiili sulkee ikkunan hetkella {leima!r}, "
            f"web {FW.FREE_PREMIUM_UNTIL!r}")


def test_eri_aikaleima_sivulla_kaataa_portin(tmp_path, monkeypatch):
    """MUTAATIO: kasin kirjoitettu myohempi `data-until` = lupaus jota
    mikaan muu pinta ei pida. Portti kaatuu."""
    f = tmp_path / "index.html"
    f.write_text(
        f'<template {FW.OPEN_ATTR}="X" {FW.UNTIL_ATTR}="2099-01-01T00:00:00Z">'
        "<p>Premium is free on the web until the GW4 deadline.</p></template>\n"
        f"<p>Get Premium</p>\n<template {FW.END_ATTR}=\"X\"></template>",
        encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", tmp_path)
    monkeypatch.setattr(C, "surfaces", lambda: [f])
    assert C.until_mismatches([f]), "eri aikaleimaa ei havaittu"
    assert C.main() == 1


def test_negatiivinen_kontrolli_lahteen_aikaleima_lapaisee(tmp_path, monkeypatch):
    f = tmp_path / "index.html"
    f.write_text(FW.hero_cta_html(ENNEN), encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", tmp_path)
    monkeypatch.setattr(C, "surfaces", lambda: [f])
    assert C.until_mismatches([f]) == []


# ---------------------------------------------------------------------------
# 4. YKSI LUKIJA: Python-predikaatti == skriptin predikaatti
# ---------------------------------------------------------------------------

def test_open_at_on_aikaleima_ei_paiva():
    """Tasan rajalla kiinni - sama kuin `Date.now()<u`."""
    assert FW.open_at(FW.FREE_PREMIUM_UNTIL, UNTIL - dt.timedelta(seconds=1))
    assert not FW.open_at(FW.FREE_PREMIUM_UNTIL, UNTIL)
    assert not FW.open_at(FW.FREE_PREMIUM_UNTIL, UNTIL + dt.timedelta(seconds=1))
    # Rikkinainen aikaleima = kiinni, kuten selaimessa Date.parse -> NaN.
    assert not FW.open_at("ensi viikolla", ENNEN)
    assert not FW.open_at("", ENNEN)


def test_is_open_kulkee_open_atin_kautta():
    """Kaksi predikaattia samaan kysymykseen olisi 12.9:n vikaluokka."""
    src = inspect.getsource(FW.is_open)
    assert "open_at(FREE_PREMIUM_UNTIL, now)" in src, src


def test_skripti_kayttaa_samaa_predikaattia_ja_lukee_data_untilin():
    """Lahdeskanni sitoo skriptin: `Date.now()<u` jossa u = Date.parse(data-until).
    Ei `<=`, ei paivavertailua, ei kovakoodattua aikaleimaa."""
    js = FW.inline_script("X")
    assert "Date.now()<u" in js
    assert "Date.now()<=u" not in js
    assert f"getAttribute('{FW.UNTIL_ATTR}')" in js
    assert "Date.parse(" in js
    assert not _ISO_RE.search(js), "skripti kovakoodaa aikaleiman"
    assert "2147483647" in js, "setTimeout-katto puuttuu: yli 24,8 vrk deadline laukeaisi heti"


# ---------------------------------------------------------------------------
# 5. DoD: inline-skripti ajetaan Nodessa synteettisella kellolla
# ---------------------------------------------------------------------------

STUB = ROOT / "tests" / "fixtures" / "free_window_dom_stub.js"


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("CI"):
            pytest.fail("node puuttuu CI:sta - skriptiportti ei aja (fail-closed)")
        pytest.skip("node ei ole PATHissa")
    return node


def _aja_skripti(html: str, now_ms: int) -> dict:
    m = C.TEMPLATE_RE.search(html)
    assert m, "avoin template puuttuu"
    js = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
    cfg = {
        "script": js, "key": m.group(1), "until": m.group(2),
        "untilMs": int(UNTIL.timestamp() * 1000), "nowMs": now_ms,
        "openMarker": "[AVOIN]", "closedMarker": "[SULJETTU]",
    }
    r = subprocess.run([_node(), str(STUB), json.dumps(cfg)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _ms(d: dt.datetime) -> int:
    return int(d.timestamp() * 1000)


def test_skripti_ennen_deadlinea_nayttaa_avoimen_ja_palaa_suljettuun():
    """Ennen deadlinea: suljettu pois, avoin sisaan, ja ajastin joka
    palauttaa suljetun tasan deadlinella ilman sivun latausta."""
    out = _aja_skripti(FW.hero_cta_html(ENNEN), _ms(ENNEN))
    assert "[AVOIN]" in out["afterLoad"] and "[SULJETTU]" not in out["afterLoad"], out
    assert out["timers"] == [_ms(UNTIL) - _ms(ENNEN)], out
    assert "[SULJETTU]" in out["atDeadline"] and "[AVOIN]" not in out["atDeadline"], out
    assert out["timersAfter"] == 0, out


@pytest.mark.parametrize("vaihe,kello", [("tasan", TASAN), ("jalkeen", JALKEEN)])
def test_skripti_deadlinella_ja_sen_jalkeen_ei_koske_dom_iin(vaihe, kello):
    out = _aja_skripti(FW.hero_cta_html(ENNEN), _ms(kello))
    assert "[SULJETTU]" in out["afterLoad"] and "[AVOIN]" not in out["afterLoad"], (vaihe, out)
    assert out["timers"] == [], (vaihe, out)


def test_skripti_kaukainen_deadline_ei_laukea_heti():
    """setTimeout ei kesta yli 2^31-1 ms: ilman kattoa 30 vrk:n paassa oleva
    deadline laukeaisi HETI ja sulkisi ikkunan valittomasti."""
    kaukana = UNTIL - dt.timedelta(days=40)
    out = _aja_skripti(FW.hero_cta_html(ENNEN), _ms(kaukana))
    assert "[AVOIN]" in out["afterLoad"], out
    assert out["timers"] == [2147483647], out
    assert "[SULJETTU]" in out["atDeadline"], out


def test_skriptin_mutaatio_predikaatissa_havaitaan():
    """MUTAATIO: `<` -> `<=` nayttaisi lupauksen tasan deadlinella."""
    html = FW.hero_cta_html(ENNEN).replace("Date.now()<u", "Date.now()<=u")
    out = _aja_skripti(html, _ms(TASAN))
    assert "[AVOIN]" in out["afterLoad"], "mutaatio ei purrut - harness ei mittaa predikaattia"


# ---------------------------------------------------------------------------
# 6. Portti ymmartaa rakenteen (ei vaaraa positiivista, ei sokeutta)
# ---------------------------------------------------------------------------

def test_portti_ei_raportoi_templatea_ikkunan_sulkeuduttua(tmp_path, monkeypatch):
    """Sivu paistettu ennen deadlinea, luettu sen jalkeen: 0 osumaa. Ilman
    tata `--live` olisi FAIL jokaisesta templatesta ja portti ohitettaisiin."""
    f = tmp_path / "index.html"
    f.write_text(FW.band_html(ENNEN), encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", tmp_path)
    monkeypatch.setattr(C, "surfaces", lambda: [f])
    assert C.hits([f], now=JALKEEN) == []
    monkeypatch.setattr(C, "is_open", lambda now=None: False)
    assert C.main() == 0


def test_portti_nakee_templaten_ennen_deadlinea(tmp_path, monkeypatch):
    """KONTROLLI: lukija ei ole sokea templatelle. Muuten edellinen
    lapaisisi lukijalla joka pyyhkii templaten aina."""
    f = tmp_path / "index.html"
    f.write_text(FW.band_html(ENNEN), encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", tmp_path)
    osumat = C.hits([f], now=ENNEN)
    assert len(osumat) == 3, osumat  # lause, "That is GW1 to GW3", nappi


def test_strip_claim_ei_koske_templaten_sisaltoon():
    html = FW.predictions_price_html(ENNEN)
    uusi, n = C.strip_claim(html)
    assert n == 0 and uusi == html


def test_strip_claim_poistaa_yha_staattisen_lauseen_templaten_vierelta():
    """KONTROLLI: suojaus koskee templatea, ei koko tiedostoa."""
    html = ("<p>Premium is free on the web until the GW4 deadline.</p>\n"
            + FW.hero_cta_html(ENNEN))
    uusi, n = C.strip_claim(html)
    assert n == 1
    assert C.TEMPLATE_RE.search(uusi), "template katosi"


class _FakeResp:
    def __init__(self, body: str):
        self._b = body.encode("utf-8")

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_live(monkeypatch, sivut: dict):
    import urllib.request
    monkeypatch.setattr(C, "LIVE_URLS", tuple(sivut))
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(sivut[req.full_url]))


def test_live_0_ilman_dispatchia(monkeypatch):
    """DoD: sivu paistettu ennen deadlinea ja EI paistettu uudelleen.
    `--live` deadlinen jalkeen: 0 kohtaa, OK."""
    _fake_live(monkeypatch, {
        "https://goaliq.app/": "<html>" + FW.band_html(ENNEN) + FW.hero_cta_html(ENNEN) + "</html>",
        "https://goaliq.app/fpl": "<html>" + free_window_block(ENNEN) + "</html>",
    })
    osumat, virheet = C.live_hits(now=JALKEEN)
    assert not virheet and osumat == [], osumat
    assert C.main_live(now=JALKEEN) == 0
    # KONTROLLI: sama sivu ennen deadlinea LUPAA (4 + 2 kohtaa).
    osumat, _ = C.live_hits(now=ENNEN)
    assert len(osumat) == 6, osumat


def test_live_myohempi_aikaleima_sivulla_on_lupaus(monkeypatch):
    """Sivu kantaa myohempaa `data-until`ia kuin lahde: selain nayttaa
    lupauksen jota mikaan muu pinta ei pida. Portti kaatuu sina aikana."""
    myohempi = FW.hero_cta_html(ENNEN).replace(
        FW.FREE_PREMIUM_UNTIL, (UNTIL + dt.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    _fake_live(monkeypatch, {"https://goaliq.app/": myohempi})
    osumat, _ = C.live_hits(now=JALKEEN)
    assert osumat, "myohempi aikaleima ei nakynyt"
    assert C.main_live(now=JALKEEN) == 1


# ---------------------------------------------------------------------------
# 7. KUTSUPAIKAT: lohkot kulkevat self_closing_blockin kautta
# ---------------------------------------------------------------------------

def test_kutsupaikka_fpl_html_kulkee_self_closing_blockin_kautta():
    """Lahdeportti. `free_window_block` haarautui 12.9 `is_open()`:lla
    paistohetkella ja palautti avoimen HTML:n staattisena - se oli vika.
    Vanhaan muotoon palautus kaataa taman."""
    src = inspect.getsource(free_window_block)
    assert "self_closing_block(" in src, "fpl.html:n lohko ei kayta self_closing_blockia"
    assert "if is_open(" not in src, "paistohetken haarautuminen palasi"
    assert "note()" not in src, "note() palauttaa tyhjan kiinni - avoin haara katoaisi templatesta"


@pytest.mark.parametrize("nimi,renderoija", list(LOHKOT.items()))
def test_kutsupaikka_jokainen_lohko_kutsuu_self_closing_blockia(nimi, renderoija):
    src = inspect.getsource(renderoija)
    assert "self_closing_block(" in src, nimi
    assert "if is_open(" not in src, nimi


def test_kutsupaikka_toiminnallinen_fpl_html():
    """Sama asia mitattuna: ennen deadlinea paistettu fpl.html-lohko ei
    lupaa staattisesti mutta lupaa JS-lukijalle. Vanha koodi olisi
    laittanut lupauksen staattiseen HTML:aan."""
    html = free_window_block(ENNEN)
    assert not _lupaa(_staattinen_nakyma(html))
    assert C.CLAIM_RE.search(_js_nakyma(html, ENNEN))
    assert "fpl-freewindow" in html and "fpl-premium" in html


# ---------------------------------------------------------------------------
# 8. Oikea selain, jos sellainen on (ei portti CI:ssa - Node-harness on)
# ---------------------------------------------------------------------------

def _chrome() -> str | None:
    for p in (os.environ.get("CHROME_BIN"),
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              "/usr/bin/google-chrome", "/usr/bin/chromium-browser",
              "/usr/bin/chromium"):
        if p and Path(p).exists():
            return p
    return None


@pytest.mark.parametrize("vaihe,kello,odotus", [
    ("ennen", ENNEN, True), ("tasan", TASAN, False), ("jalkeen", JALKEEN, False)])
def test_oikea_selain_dump_dom(tmp_path, vaihe, kello, odotus):
    """Headless Chrome, `--dump-dom` skriptin jalkeen, `Date.now` ylikirjoitettu
    sivun alussa. Ei CI-portti (Chrome ei ole taattu); Villen koneella ajaa."""
    chrome = _chrome()
    if chrome is None:
        pytest.skip("Chromea ei loydy")
    ms = int(kello.timestamp() * 1000)
    sivu = tmp_path / "sivu.html"
    sivu.write_text(
        "<!doctype html><html><body>\n"
        f"<script>Date.now=function(){{return {ms}}};</script>\n"
        + FW.hero_cta_html(ENNEN) + "\n</body></html>", encoding="utf-8")
    r = subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
         "--dump-dom", sivu.as_uri()],
        capture_output=True, text=True, timeout=120, encoding="utf-8",
        errors="replace")
    assert r.returncode == 0, r.stderr[-500:]
    dom = _staattinen_nakyma(r.stdout)  # template-sisalto ei ole DOM:ssa
    assert ("Get Premium free" in dom) is odotus, (vaihe, dom[-300:])


# ---------------------------------------------------------------------------
# 9. KASIN YLLAPIDETYT PINNAT: staattinen lupaus kaatuu JO ikkunan ollessa auki
#
# 12.9:n 19 lupauksesta 9 oli paistetuissa lohkoissa (index 5, fpl 2,
# predictions 2) ja 9 kasin kirjoitettuna staattisena tekstina (faq 6,
# creators 1, llms.txt 2). Jalkimmaiset siivosi `--fix` - mutta vasta kun
# ihminen dispatchasi sivuajon. Itsestaan sulkeutuva lohko ei tuota
# staattista lupausta; jos sellainen on sivulla, se on tasan 12.9:n vika
# odottamassa seuraavaa ikkunaa. Portti kaatuu siita silloin kun kirjoittaja
# on paikalla (ikkuna auki), ei silloin kun kukaan ei ole (ikkuna kiinni).
# Poikkeus vain `STATIC_ALLOWED`-listalla perusteluineen (CLAUDE.md 6a, 2).
# ---------------------------------------------------------------------------

def _auki(monkeypatch):
    monkeypatch.setattr(C, "is_open", lambda now=None: True)


def test_staattinen_lupaus_kaataa_portin_myos_ikkunan_ollessa_auki(tmp_path, monkeypatch):
    """EROTTELEVA: vanha portti tulosti 'STAATTINEN faq.html:1' ja palautti 0."""
    f = tmp_path / "faq.html"
    f.write_text("<p>Premium is free on the web until the GW4 deadline on "
                 "12 September.</p>", encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", tmp_path)
    monkeypatch.setattr(C, "surfaces", lambda: [f])
    _auki(monkeypatch)
    assert C.static_hits([f]), "staattinen lupaus ei nakynyt"
    assert C.main() == 1


def test_staattinen_paivamaarahinta_kaataa_portin_ikkunan_ollessa_auki(tmp_path, monkeypatch):
    """12.9:n heron hintanootti: ei ilmaislupaus, mutta vanhenee samalla
    hetkella. Staattisena se roikkuu tasan samoin."""
    f = tmp_path / "index.html"
    f.write_text('<p class="cta-note">After 12 September it is &euro;3.99 '
                 'a month.</p>', encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", tmp_path)
    monkeypatch.setattr(C, "surfaces", lambda: [f])
    _auki(monkeypatch)
    assert C.static_hits([f]), "staattinen paivamaarahinta ei nakynyt"
    assert C.main() == 1


def test_itsestaan_sulkeutuva_lohko_lapaisee_ikkunan_ollessa_auki(tmp_path, monkeypatch):
    """KONTROLLI: tiukka portti ei hylkaa oikeaa muotoa. Sama lupaus
    templatessa = 0 staattista osumaa, portti OK."""
    f = tmp_path / "index.html"
    f.write_text(FW.band_html(ENNEN) + "\n" + FW.hero_price_note_html(ENNEN),
                 encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", tmp_path)
    monkeypatch.setattr(C, "surfaces", lambda: [f])
    _auki(monkeypatch)
    assert C.static_hits([f]) == []
    assert C.main() == 0


def test_poikkeuslistalla_oleva_staattinen_lupaus_lapaisee(tmp_path, monkeypatch):
    """Poikkeus on mahdollinen mutta nakyy diffissa perusteluineen."""
    f = tmp_path / "llms.txt"
    f.write_text("Premium is free on the web until the GW4 deadline.",
                 encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", tmp_path)
    monkeypatch.setattr(C, "surfaces", lambda: [f])
    monkeypatch.setattr(C, "STATIC_ALLOWED", {
        "llms.txt": "testin perustelu: tekstitiedosto ei voi ajaa skriptia"})
    _auki(monkeypatch)
    assert C.main() == 0


def test_poikkeuslista_on_tyhja_ja_jokaisella_rivilla_olisi_perustelu():
    """Mekanismi 2: uusi pinta ei paase listalle vahingossa. Lisays kaataa
    taman testin ja kirjoittaja paivittaa odotuksen JA perustelun - kumpikin
    nakyy diffissa. Tanaan lista on tyhja: jokainen paistettu lupaus kulkee
    `self_closing_block`in kautta, eika llms.txt/faq/creators lupaa mitaan."""
    assert C.STATIC_ALLOWED == {}, C.STATIC_ALLOWED
    for rel, syy in C.STATIC_ALLOWED.items():
        assert (ROOT / rel).is_file(), rel
        assert len(syy.strip()) >= 40, (rel, syy)


def test_repon_pinnat_eivat_kanna_staattista_lupausta():
    """Mitattu nykyisesta puusta: 0 staattista lupausta 6 sivulla. Tama on
    se luku jonka pitaa olla 0 riippumatta kellosta."""
    assert C.static_hits() == []


def test_fix_ohitetaan_poikkeuslistalla_on_perustelu_ja_tiedosto():
    """Mekanismi 2 myos `--fix`in ohituslistalle: `check_free_window.py`
    lupaa docstringissaan etta testi kaatuu jos uusi tiedosto lisataan ilman
    perustelua - tama on se testi. Odotus on eksplisiittinen joukko, joten
    lisays nakyy diffissa kahdessa paikassa."""
    assert set(C.FIX_OHITETAAN) == {"fpl.html"}, set(C.FIX_OHITETAAN)
    for rel, syy in C.FIX_OHITETAAN.items():
        assert (ROOT / rel).is_file(), rel
        assert len(syy.strip()) >= 40, (rel, syy)
        assert "self_closing_block" in syy, (rel, "perustelun on nimettava mekanismi")
