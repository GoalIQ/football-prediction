"""Portti: DefCon-leaderboard on premium, top 3 on ilmainen.

TAUSTA (DEFCON-LEADERS-PALVELINRAJA, mitattu 12.9 ja 17.9.2026). "Full DefCon
leaderboard" on myyty premiumina vahintaan viidella pinnalla (fpl.html,
build_fpl_page.py, llms.txt, mobiilin paywall-bulletit, SPA:n Leaders-
teaser), mutta `/api/fantasy/defcon-leaders?basis=season&top_n=400`
palautti anonyymille 182 rivia ja `window=5` 377 rivia, molemmat
`meta.masked=None`. Raja oli VAIN selaimessa: Leaders.svelte (FREE_ROWS) ja
mobiilin FantasyTools.tsx (LEADERS_FREE_ROWS) leikkasivat listan kolmeen.
Kuudes kerta samaa vikaluokkaa (captain 15.8, replacements 2.9, value +
differentials 4.9, rate-team 5.9).

Raja on nyt tasmalleen se mita klientit jo nayttivat:
    FREE     top 3 palvelinjarjestyksessa + meta.masked/free_rows/total_rows
    PREMIUM  koko lista
Copya ei tarvinnut muuttaa: koodi siirtyi vastaamaan copya, ei toisin pain.

KAKSI TODISTUSTA (muisti 12.9: testi kutsuu funktiota, ei kutsupaikkaa):
  (a) yksikkotestit kutsuvat mask_defcon_leaders_payloadia suoraan; sen
      mutaatio (palauta payload sellaisenaan) punastaa ne.
  (b) lahdeportti lukee api/main.py:n handlerin ja vaatii etta MOLEMMAT
      basis-haarat kulkevat maskin kautta. Vanha muoto
      `return rank_defcon_season(...)` / `return rank_defcon_leaders(...)`
      punastaa sen vaikka maskifunktio olisi paikallaan ja (a) vihrea.
  Toiminnallinen pari (TestClient molemmilla basiksilla) on
  tests/test_premium_enforcement.py:ssa.

SAMA LUKU YHDESTA VAKIOSTA: FREE_LEADERS_ROWS kulkee vastauksen metassa
(`free_rows`), ja klienttien fallback-vakiot (SPA FREE_ROWS, mobiili
LEADERS_FREE_ROWS) sidotaan siihen alla. Jos joku muuttaa yhta, tama kaatuu.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.premium import FREE_LEADERS_ROWS, mask_defcon_leaders_payload  # noqa: E402

MAIN = ROOT / "api" / "main.py"
LEADERS_SVELTE = (ROOT / "web" / "pro-spa" / "src" / "lib" / "components"
                  / "Leaders.svelte")
# goaliq-app on rinnakkainen repo. Paatyopuussa se on ROOT.parent alla,
# worktreessa (Documents/fp-wt/<nimi>) yhta tasoa ylempana; otetaan
# ensimmainen joka on olemassa, muuten skip (ei CI:ssa).
APP_TOOLS = next(
    (p for p in (ROOT.parent / "goaliq-app" / "components" / "FantasyTools.tsx",
                 ROOT.parent.parent / "goaliq-app" / "components"
                 / "FantasyTools.tsx")
     if p.exists()),
    ROOT.parent / "goaliq-app" / "components" / "FantasyTools.tsx")

N = 6


def _payload(n: int = N) -> dict:
    """Rivit palvelinjarjestyksessa (hit_rate desc), kaikki kentat mukana."""
    return {
        "meta": {"window": "season", "basis_season": "2025/26",
                 "generated_at": "2026-09-17T00:00:00"},
        "players": [
            {"id": i, "web_name": f"P{i}", "team_short": "TST", "pos": "DEF",
             "price": 5.0, "owned_pct": 1.0, "games": 38, "basis": "2025/26",
             "threshold": 10, "dc_per_game": 9.0 - i,
             "hit_rate_pct": float(100 - 10 * i), "hit_rate_basis": "starts",
             "starts": 38, "defcon_points_window": 2 * (38 - i), "hits": 38 - i}
            for i in range(1, n + 1)
        ],
    }


# --------------------------------------------------------------------------
# (a) maskifunktio
# --------------------------------------------------------------------------


def test_fikstuuri_on_erotteleva():
    """Ilman tata mutaatiotesti voisi lapaista tyhjana: jos syotteessa olisi
    korkeintaan free_rows rivia, maskaamaton paluu nayttaisi maskatulta."""
    assert N > FREE_LEADERS_ROWS


def test_free_saa_kolme_rivia_palvelinjarjestyksessa():
    out = mask_defcon_leaders_payload(_payload())
    assert [p["id"] for p in out["players"]] == [1, 2, 3]
    assert len(out["players"]) == FREE_LEADERS_ROWS


def test_meta_kertoo_maskin_rajan_ja_kokonaismaaran():
    out = mask_defcon_leaders_payload(_payload())
    m = out["meta"]
    assert m["masked"] is True
    assert m["free_rows"] == FREE_LEADERS_ROWS
    assert m["total_rows"] == N
    assert f"top {FREE_LEADERS_ROWS} of {N}" in m["mask"]
    # Alkuperainen meta sailyy (typistys on additiivinen).
    assert m["window"] == "season" and m["basis_season"] == "2025/26"


def test_rivit_pysyvat_taysina():
    """Maski on typistys, ei null-korvaus: klientti renderoi
    hit_rate_pct/dc_per_game suoraan, eika typistetty rivi saa menettaa
    yhtaan kenttaa."""
    src = _payload()
    out = mask_defcon_leaders_payload(src)
    for got, orig in zip(out["players"], src["players"]):
        assert got == orig


def test_lyhyt_lista_ei_kasva_eika_kaadu():
    out = mask_defcon_leaders_payload(_payload(2))
    assert len(out["players"]) == 2
    assert out["meta"]["masked"] is True
    assert out["meta"]["total_rows"] == 2
    tyhja = mask_defcon_leaders_payload({"meta": {}, "players": []})
    assert tyhja["players"] == [] and tyhja["meta"]["total_rows"] == 0


def test_maski_ei_muuta_syotetta():
    src = _payload()
    mask_defcon_leaders_payload(src)
    assert len(src["players"]) == N
    assert "masked" not in src["meta"]


# --------------------------------------------------------------------------
# (b) kutsupaikka: molemmat basis-haarat kulkevat maskin kautta
# --------------------------------------------------------------------------


def _handler_body(src: str, route: str) -> str:
    m = re.search(rf'@app\.get\(\s*"{re.escape(route)}"', src)
    assert m, f"{route} ei loydy api/main.py:sta"
    rest = src[m.start():]
    nxt = re.search(r"\n@app\.(?:get|post)\(", rest[10:])
    return rest[: nxt.start() + 10] if nxt else rest


def _kutsupaikan_ongelma(body: str) -> str | None:
    """Mika vanhassa muodossa on vialla, tai None jos kutsupaikka on kunnossa.

    Vaatii kolme asiaa: (1) gate kysytaan, (2) maskifunktiota kutsutaan,
    (3) kumpaakaan rankkeria ei palauteta suoraan. Kohta 3 on se joka
    erottaa vanhan muodon: `return rank_defcon_season(...)` ohittaa maskin
    vaikka (1) ja (2) olisivat runkoon jaaneet muualle.
    """
    if "is_premium_request(request)" not in body:
        return "handleri ei kysy is_premium_requestia"
    if "mask_defcon_leaders_payload(" not in body:
        return "handleri ei kutsu mask_defcon_leaders_payloadia"
    suora = re.findall(r"return\s+rank_defcon_\w+\(", body)
    if suora:
        return f"rankkerin tulos palautetaan suoraan maskin ohi: {suora}"
    for fn in ("rank_defcon_season(", "rank_defcon_leaders("):
        if fn not in body:
            return f"{fn} puuttuu handlerista — toinen basis katosi?"
    return None


def test_kutsupaikka_maskaa_molemmat_basikset():
    body = _handler_body(MAIN.read_text(encoding="utf-8"),
                         "/api/fantasy/defcon-leaders")
    ongelma = _kutsupaikan_ongelma(body)
    assert ongelma is None, (
        f"{ongelma}. 'Full DefCon leaderboard' on myyty premiumina; UI:n "
        "leikkaus ei ole portti, endpoint on julkinen.")


def test_negatiivinen_kontrolli_vanha_kutsupaikka_punastuu():
    """Portin on erotettava tasan se muoto joka oli tuotannossa 12.9:
    rankkerin tulos palautetaan suoraan. Rakennetaan se nykyisesta
    handlerista, jotta kontrolli ei vanhene kun runko muuttuu muualta."""
    body = _handler_body(MAIN.read_text(encoding="utf-8"),
                         "/api/fantasy/defcon-leaders")
    vanha = body.replace("payload = rank_defcon_season(",
                         "return rank_defcon_season(")
    assert vanha != body, "kontrollin lahtomuoto ei osu runkoon enaa"
    assert _kutsupaikan_ongelma(vanha) is not None
    vanha2 = body.replace("payload = rank_defcon_leaders(",
                          "return rank_defcon_leaders(")
    assert vanha2 != body
    assert _kutsupaikan_ongelma(vanha2) is not None
    # ...ja gaten poisto yksinaan riittaa punaiseen.
    assert _kutsupaikan_ongelma(
        body.replace("is_premium_request(request)", "False")) is not None


# --------------------------------------------------------------------------
# Sama luku yhdesta vakiosta: klienttien fallbackit == palvelimen raja
# --------------------------------------------------------------------------


def test_spa_fallback_vakio_on_sama_kuin_palvelimen():
    src = LEADERS_SVELTE.read_text(encoding="utf-8")
    m = re.search(r"const FREE_ROWS = (\d+);", src)
    assert m, "Leaders.svelte: FREE_ROWS-vakio ei loydy"
    assert int(m.group(1)) == FREE_LEADERS_ROWS, (
        "SPA:n fallback ja palvelimen raja eroavat: nakyva sisalto vaihtuisi "
        "deployn jarjestyksesta riippuen")


def test_spa_teaser_lukee_palvelimen_maskilippua():
    """Palvelinmaski antaa ilmaiskayttajalle TASAN free_rows rivia, joten
    `dcAll.length > FREE_ROWS` on aina epatosi ja teaser katoaisi tasan
    silta kayttajalta jolle se on tarkoitettu (sama vika on Value.svelte:ssa
    ollut 4.9 alkaen). Teaser-ehto lukee meta.masked + total_rows."""
    src = LEADERS_SVELTE.read_text(encoding="utf-8")
    assert "{#if dcTeaser}" in src
    assert "{#if !premium && dcAll.length > FREE_ROWS}" not in src
    teaser = src[src.index("const dcTeaser"):src.index("{#if dcTeaser}")]
    assert "m?.masked" in teaser and "total_rows" in teaser
    assert "meta?.free_rows" in src, "SPA ei lue rajaa palvelimelta"


def test_mobiili_fallback_vakio_on_sama_kuin_palvelimen():
    """goaliq-app on eri repo; ajetaan kun se on checkoutattuna rinnalla
    (sama kuvio kuin test_alltime_window_parity.py)."""
    if not APP_TOOLS.exists():
        pytest.skip("goaliq-app ei ole checkoutattuna, pariteettia ei voi ajaa")
    src = APP_TOOLS.read_text(encoding="utf-8")
    m = re.search(r"const LEADERS_FREE_ROWS = (\d+);", src)
    assert m, "FantasyTools.tsx: LEADERS_FREE_ROWS-vakio ei loydy"
    assert int(m.group(1)) == FREE_LEADERS_ROWS


def test_mobiili_teaser_lukee_palvelimen_maskilippua():
    """Sama vika kuin SPA:ssa: palvelinmaski antaa ilmaiskayttajalle TASAN
    free_rows rivia, joten `dcRows.length > LEADERS_FREE_ROWS` on aina epatosi
    ja mobiilin lukkokortti katoaisi heti kun backend deployataan, vaikka
    appia ei olisi paivitetty. Kortin ehto lukee meta.masked + total_rows,
    raja meta.free_rows:sta (fallback vakioon vanhalle backendille)."""
    if not APP_TOOLS.exists():
        pytest.skip("goaliq-app ei ole checkoutattuna, pariteettia ei voi ajaa")
    src = APP_TOOLS.read_text(encoding="utf-8")
    assert "{!isPremium && dcRows.length > LEADERS_FREE_ROWS && (" not in src, (
        "mobiilin lukkokortti paattelee maskin listan pituudesta: 3 > 3 on "
        "epatosi kun palvelin maskaa")
    assert "{dcTeaser && (" in src
    teaser = src[src.index("const dcTeaser"):src.index("{dcTeaser && (")]
    assert "meta?.masked" in teaser and "total_rows" in teaser
    assert "meta?.free_rows" in src, "mobiili ei lue rajaa palvelimelta"
