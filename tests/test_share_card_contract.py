# -*- coding: utf-8 -*-
"""Jakokorttien sopimus: kortti ei saa kertoa muuta kuin mita lista kertoo.

Tausta (3.9.2026, Villen havainto + sen jalkeinen auditointi). Ville sortasi
xP-listan GW3:n mukaan, otti jakokuvan, ja kuvassa nimet ja jarjestys olivat
oikein mutta LUKU oli kuuden kierroksen summa. Auditointi loysi saman luokan
vian yhdeksasta muusta kortista: arvosarake, ikkuna tai alatunniste ei
seurannut listan tilaa.

Nama testit vahtivat MOOTTORIN invariantteja (yksi paikka, kaikki kortit
perivat) ja niita yksittaisia korjauksia joissa vika oli mitattu. Ne lukevat
lahdetta, koska canvas-renderia ei voi ajaa pytestista — sama linja kuin
`test_luck_parity.py`:ssa ja `test_luck_gw_scope.py`:ssa.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPA = ROOT / "web" / "pro-spa" / "src"
ENGINE = SPA / "lib" / "shareCard.ts"
COMPONENTS = SPA / "lib" / "components"


def _src(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Moottori: yksi vahti kaikille kutsujille
# ---------------------------------------------------------------------------

def test_kortti_kieltaytyy_liian_lyhyesta_listasta():
    """Tyhja suodatus tuotti kortin jossa on vain otsikko ja alatunniste.

    Webilla ei ollut vahtia lainkaan (kuusi kutsupaikkaa saattoi tuottaa
    tyhjan kortin); mobiilissa se on ollut `useListShareCard`issa 27.8 alkaen.
    Vahti on `shareCard`issa eika kutsujissa, jotta jokainen uusi kortti perii
    sen kirjoittamatta rivia."""
    s = _src(ENGINE)
    assert "export const CARD_MIN_ROWS = 3;" in s
    assert "if (spec.rows.length < CARD_MIN_ROWS) return 'too_few_rows';" in s
    # Vahdin on oltava ENNEN renderointia, ei sen jalkeen.
    guard = s.index("if (spec.rows.length < CARD_MIN_ROWS)")
    render = s.index("const blob = await renderCard(spec);")
    assert guard < render, "vahti on renderoinnin jalkeen — kortti ehtii syntya"


def test_tyhja_tagi_ei_piirra_kehysta():
    """`tag: ''` strokasi 16x30 px:n tyhjan laatikon JOKA riville.

    Osui Standingsiin (tag aina tyhja) ja Season raceen (tag vain osalla
    riveista -> repaleinen sekoitus laatikoita ja tyhjaa)."""
    s = _src(ENGINE)
    i = s.index("const pw = ctx.measureText(r.tag).width + 16;")
    edelta = s[max(0, i - 400):i]
    assert "if (r.tag) {" in edelta, (
        "tagilaatikko piirretaan ilman tyhjatarkistusta")


def test_alatunnisteen_molemmat_rivit_ovat_ylikirjoitettavissa():
    """Toinen alarivi oli kovakoodattu 'model projections, not betting advice'.

    Kortilla joka nayttaa TOTEUTUNEITA lukuja (sarjataulukko, pelatut pisteet,
    live-syote) se on kaksi valhetta perakkain. Mobiilissa `footNote2` on ollut
    27.8 alkaen; web jai ilman."""
    s = _src(ENGINE)
    assert "footNote2?: string;" in s
    assert ("ctx.fillText(spec.footNote2 ?? 'model projections, not betting "
            "advice', MX, H - 54);") in s


# ---------------------------------------------------------------------------
# Kortit joiden luvut EIVAT ole projektioita
# ---------------------------------------------------------------------------

TOTEUMAKORTIT = {
    "Standings.svelte": "official table via football-data.org",
    "BeatTheModel.svelte": "official FPL points",
    "SeasonRace.svelte": "official FPL points",
    "DefConLive.svelte": "live FPL match feed",
}


@pytest.mark.parametrize("tiedosto,odotettu", sorted(TOTEUMAKORTIT.items()))
def test_toteumakortti_ei_vaita_olevansa_projektio(tiedosto, odotettu):
    s = _src(COMPONENTS / tiedosto)
    assert "footNote:" in s, f"{tiedosto}: ei omaa lahderivia"
    assert odotettu in s, f"{tiedosto}: lahderivi ei nimea oikeaa lahdetta"
    assert "footNote2:" in s, (
        f"{tiedosto}: toinen alarivi jaa oletukseen 'model projections', "
        f"vaikka kortin luvut ovat toteutuneita")


# FPL:n omat sarakkeet attribuoidaan. Vain nama nelja ovat listalla, koska
# muissa korteissa `mid` on mallin oma luku — poikkeuslista, jolle on syy.
FPL_SARAKEKORTIT = ["XpTable.svelte", "Value.svelte", "Differentials.svelte",
                    "Watchlist.svelte", "Replacements.svelte"]


@pytest.mark.parametrize("tiedosto", FPL_SARAKEKORTIT)
def test_fpl_omistama_sarake_attribuoidaan(tiedosto):
    s = _src(COMPONENTS / tiedosto)
    assert "footNote:" in s and "from FPL" in s, (
        f"{tiedosto}: kortilla on FPL:n oma sarake (PRICE/OWNED) ilman "
        f"attribuutiota")


# ---------------------------------------------------------------------------
# Mitatut yksittaiset viat
# ---------------------------------------------------------------------------

def test_price_watch_kortti_ei_jaa_hintaa_kahdesti():
    """`build_fpl_price_watch.py` kirjoittaa `now_cost`in JO miljoonina, ja
    saman naytön taulukko renderoi sen suoraan. Kortti jakoi kymmenella
    uudelleen -> 0.6 siina missa taulukko sen vieressa sanoi 5.5."""
    builder = _src(ROOT / "scripts" / "build_fpl_price_watch.py")
    assert '"now_cost": (e.get("now_cost") or 0) / 10.0' in builder, (
        "builderin yksikko vaihtui — tarkista kortti uudelleen")
    s = _src(COMPONENTS / "PriceWatch.svelte")
    assert "r.now_cost / 10" not in s, "kortti jakaa hinnan toisen kerran"
    assert "mid: typeof r.now_cost === 'number' ? r.now_cost.toFixed(1) : ''" in s


def test_defcon_live_kortti_ei_pudota_osuneita():
    """Kentalla jo osuneet ovat listan HANNILLA (niissa ei ole seurattavaa),
    ja `slice(0, 10)` pudotti siis tasan ne rivit joista alaotsikko puhuu:
    "2 of 12 at the threshold" ja kuvassa nolla. Sama vika oli korjattu
    mobiilissa; web jai."""
    s = _src(COMPONENTS / "DefConLive.svelte")
    kortti = s[s.index("async function share()"):]
    kortti = kortti[:kortti.index("capture('xp_card_shared'")]
    assert "rows: [...rows]" in kortti, "kortti jakaa naytön jarjestyksen"
    assert "return a.hit ? -1 : 1;" in kortti, (
        "osuneet eivat ole kortilla ensin")
    assert "p.hit ? ' ✓' : ''" in kortti, "osumaa ei merkita kortille"


def test_xp_kortti_seuraa_kierrossorttia():
    """Villen alkuperainen havainto: GW3-sortti, kortissa GW3-GW8:n summa."""
    s = _src(COMPONENTS / "XpTable.svelte")
    kortti = s[s.index("async function share()"):]
    kortti = kortti[:kortti.index("capture('xp_card_shared'")]
    assert "const cardGw = sortGw;" in kortti
    assert "gwXp(p, cardGw).toFixed(2)" in kortti, (
        "kortin arvosarake ei lue valittua kierrosta")
    assert "`GW${cardGw} xP`" in kortti, "arvosarakkeen otsikko ei nimea kierrosta"
    assert "const windowLabel = cardGw != null ? `GW${cardGw}` : horizonLabel;" in kortti


def test_spl_value_kortti_ei_myy_kierroslukua_horisonttilukuna():
    """`vpm` on xP per KIERROS per miljoona; kortti otsikoi sen kuuden
    kierroksen luvuksi, eli luku oli noin kuudesosa lupauksesta."""
    s = _src(SPA / "routes" / "spl" / "+page.svelte")
    assert "'xP per gameweek per million, GoalIQ model'" in s
    assert "xP per million, next" not in s


def test_kausilabel_luetaan_riveilta_ei_kovakoodata():
    """Kovakoodattu '2025/26' vanhenisi hiljaa. 🔴 JA ENSIMMAINEN KORJAUS
    OLI PAHEMPI: `meta.season` on KULUVA kausi, mutta rivit ovat
    `last_season`ia. Label ja luku samasta lahteesta."""
    s = _src(SPA / "routes" / "spl" / "+page.svelte")
    assert "'2025/26 season points" not in s
    assert "leadersSeason" in s
    assert "p.last_season?.season" in s, (
        "kausi luetaan muualta kuin niilta riveilta joita kortti nayttaa")
