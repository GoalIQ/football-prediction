"""KUMPPANIKORTTI (27.9.2026 rivina, 28.9 kortiksi kahdelle pinnalle; FPL Demon,
Villen paatokset).

Portti vartioi:
  1. URL on Demonin itse lahettama planneri-linkki hanen omilla utm-tageillaan
     (hanen analytiikkansa lukee niita, ei meidan keksimiamme);
  2. kumppanin domain on VAIN src/partners.py:ssa (saanto 6a: pinta ei
     kirjoita URL:ia kasin, joten tagi tai paattyminen ei unohdu);
  3. kortti paattyy itsestaan `active_until`-paivana (julkaisutarkistaja B4);
  4. SIJOITUS mitataan RENDEROIDYLTA sivulta, ei funktiosta (muisti:
     testi kutsuu funktiota, ei kutsupaikkaa):
       - /fpl/expected-points: GW-taulukon alla ja ENNEN top 100:aa, jotta koko
         top 100 jaa kortin ja UPSELL/CTA:n (ostohetki) valiin;
       - /fpl: heti heron jalkeen, eli meidan oma Premium-nappi tulee ensin;
     ja kummallakin sivulla kortti on tasan kerran JA sen tyyli on sivulla
     (luokka ilman tyylia olisi 12 px:n rivi uudelleen, eli se vika jota
     kortti korjaa);
  5. lauseen "five" on syotteen horisontti (saanto 6a: kaksi paikkaa samalle
     luvulle, joten niiden ero kaataa buildin eika jata lausetta valehtelemaan).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from src.partners import (FPL_DEMON, PARTNER_CARD_CSS, SURFACES,
                          partner_active, partner_card_html)

ROOT = Path(__file__).resolve().parents[1]
UNTIL = datetime.fromisoformat(FPL_DEMON["active_until"]).replace(tzinfo=timezone.utc)
BEFORE = UNTIL - timedelta(seconds=1)
CARD = 'class="partner-card"'
CARD_CSS = ".partner-card{"


def test_url_is_demons_own_planner_link():
    u = urlparse(FPL_DEMON["url"])
    q = parse_qs(u.query)
    assert u.scheme == "https"
    assert u.hostname == "fpldemon.com"
    assert u.path == "/fpl/planner"
    assert q == {"utm_source": ["goaliq"], "utm_medium": ["social"],
                 "utm_campaign": ["goaliq"]}


def test_partner_domain_only_in_partners_module():
    lahteet = [
        *(ROOT / "src").rglob("*.py"),
        *(ROOT / "scripts").rglob("*.py"),
        *(ROOT / "api").rglob("*.py"),
        *(ROOT / "web" / "pro-spa" / "src").rglob("*.ts"),
        *(ROOT / "web" / "pro-spa" / "src").rglob("*.svelte"),
    ]
    osumat = sorted(
        p.relative_to(ROOT).as_posix() for p in lahteet
        if "node_modules" not in p.parts and not p.name.endswith(".test.ts")
        # URL-muoto, ei pelkka nimi: api/partner_feed.py:n docstring
        # mainitsee kumppanin domainin kertoakseen kenelle syote on.
        and "//fpldemon.com" in p.read_text(encoding="utf-8", errors="ignore")
    )
    assert osumat == ["src/partners.py"]


def test_ends_by_itself():
    assert partner_active(FPL_DEMON, BEFORE)
    assert not partner_active(FPL_DEMON, UNTIL)
    assert partner_active(FPL_DEMON, datetime(2026, 9, 27, 12, tzinfo=timezone.utc))
    # Naiivi kello tulkitaan UTC:ksi, ei kaadu.
    assert partner_active(FPL_DEMON, BEFORE.replace(tzinfo=None))
    for huono in ("", "huomenna", None):
        assert not partner_active({**FPL_DEMON, "active_until": huono}, BEFORE)
    for s in SURFACES:
        assert partner_card_html(FPL_DEMON, UNTIL, s) == ""
    # Kokeilu on sovittu GW10:n loppuun; pidempi paiva vaatii paatoksen.
    assert FPL_DEMON["active_until"] <= "2026-11-10"


def test_unknown_surface_fails_loudly():
    """Kirjoitusvirhe pinnan nimessa ei saa tuottaa korttia jonka klikkaukset
    kirjautuvat olemattomalle pinnalle."""
    with pytest.raises(ValueError):
        partner_card_html(FPL_DEMON, BEFORE, "hub_expected_point")


def test_card_markup():
    html = partner_card_html(FPL_DEMON, BEFORE, "hub_expected_points")
    assert html.startswith('<aside class="partner-card" aria-label="Partner: FPL Demon">')
    assert '<span class="partner-kicker">Partner</span>' in html
    assert ('<b class="partner-name">FPL Demon</b>\'s planner uses our xP '
            "for the next five gameweeks.") in html
    assert "solver" not in html and "these projections" not in html
    assert 'href="https://fpldemon.com/fpl/planner?utm_source=goaliq&amp;utm_medium=social&amp;utm_campaign=goaliq"' in html
    assert 'class="partner-btn"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener sponsored"' in html
    assert ("posthog.capture('partner_link_clicked',"
            "{partner:'fpldemon',surface:'hub_expected_points'})") in html
    assert "Plan your transfers there &rarr;</a>" in html
    assert "—" not in html  # em dash kielletty
    # Kumppanin nappi ei saa nayttaa meidan ostonapilta (amber #F5C542).
    assert "#F5C542" not in PARTNER_CARD_CSS.upper()


def _xp(next_gw: int = 6, dl_gw: int = 6) -> dict:
    return {
        "meta": {"available": True, "next_gameweek": next_gw,
                 "deadline_gameweek": dl_gw, "season": "2026/27"},
        "players": [{
            "id": i, "web_name": f"P{i}", "team_short": "ARS",
            "pos": "MID", "price": 60, "xp_horizon_total": 30.0 - i,
            "xp_per_gw": 5.0, "xp_per_90": 5.0, "xmins": 85.0,
            "p_start": 0.9, "gameweeks": [{"gw": next_gw, "xp": 5.0}],
        } for i in range(1, 12)],
    }


def test_free_expected_points_page_places_it_under_the_gw_table():
    import scripts.build_fpl_longtail as L
    page = L.render_expected_points(_xp(), BEFORE) or ""
    assert page.count("fpldemon.com") == 1
    assert page.count(CARD) == 1
    assert page.count(CARD_CSS) == 1, "kortti ilman tyylia on taas alaviiterivi"
    card = page.index(CARD)
    gw = page.index('id="gw-xp"')
    gw_table_end = page.index("</table>", gw)
    top100 = page.index('id="top-100"')
    top100_end = page.index("</table>", top100)
    upsell = page.index(L.UPSELL)
    cta = page.index('class="cta-row"')
    # Koko top 100 -taulukko kortin ja ostohetken valissa.
    assert gw < gw_table_end < card < top100 < top100_end < upsell < cta
    assert "surface:'hub_expected_points'" in page


def test_card_css_only_where_the_card_is():
    """Kortin tyyli ei valu muille ~50 alasivulle."""
    import scripts.build_fpl_longtail as L
    page = L.render_captain(_xp(), BEFORE) or ""
    assert page, "vertailusivu ei renderoitynyt"
    assert CARD not in page and CARD_CSS not in page


def _fpl_page(iso_date: str | None = None) -> str:
    import scripts.build_fpl_page as B
    c = B.build_context(*B.load_data())
    if iso_date:
        c = {**c, "iso_date": iso_date}
    return B.render_page(c, B._load_json(B.XP_PATH))


def test_fpl_page_places_it_after_our_own_hero_cta():
    """Meidan Premium-nappi (hero-CTA) ensin, kortti heti heron jalkeen ja ennen
    ensimmaista data-osiota. Tyokaluhakemiston alla kortti oli 390 px:lla
    304 px ostonapin YLAPUOLELLA samassa ruudussa (mitattu 28.9)."""
    page = _fpl_page((BEFORE - timedelta(days=1)).date().isoformat())
    assert page.count("fpldemon.com") == 1
    assert page.count(CARD) == 1
    assert page.count(CARD_CSS) == 1, "kortti ilman tyylia on taas alaviiterivi"
    card = page.index(CARD)
    hero_cta = page.index('data-cta="fpl"')
    hero_end = page.index("</section>", hero_cta)
    first_data = page.index('id="clean-sheets"')
    premium = page.index("Unlock the full FPL toolkit with Premium")
    assert hero_cta < hero_end < card < first_data < premium
    assert "surface:'hub_fpl'" in page


def test_claim_horizon_matches_the_feed():
    from api.partner_feed import PARTNER_XP_HORIZON
    sanat = {3: "three", 4: "four", 5: "five", 6: "six", 8: "eight"}
    assert f"next {sanat[PARTNER_XP_HORIZON]} gameweeks" in FPL_DEMON["claim"]


def test_expired_pages_have_no_card():
    import scripts.build_fpl_longtail as L
    page = L.render_expected_points(_xp(), UNTIL) or ""
    assert page, "sivu ei renderoitynyt"
    fpl = _fpl_page(UNTIL.date().isoformat())
    for p in (page, fpl):
        assert "fpldemon.com" not in p
        assert CARD not in p and CARD_CSS not in p


def test_call_sites_are_the_two_surfaces():
    """Muut sivut (ja paywall) eivat saa korttia vahingossa: kutsupaikkoja on
    kaksi, yksi kummallekin SURFACES-pinnalle. Uusi sijoitus vaatii tietoisen
    muutoksen tahan ja SURFACESiin."""
    kutsut = []
    for p in [*(ROOT / "scripts").rglob("*.py"), *(ROOT / "src").rglob("*.py"),
              *(ROOT / "api").rglob("*.py")]:
        if p.name == "partners.py":
            continue
        for m in re.finditer(r"partner_card_html\(\s*FPL_DEMON,[^\n]*?\"(\w+)\"\)",
                             p.read_text(encoding="utf-8", errors="ignore")):
            kutsut.append((p.relative_to(ROOT).as_posix(), m.group(1)))
    assert sorted(kutsut) == [
        ("scripts/build_fpl_longtail.py", "hub_expected_points"),
        ("scripts/build_fpl_page.py", "hub_fpl"),
    ]
    assert sorted(SURFACES) == ["hub_expected_points", "hub_fpl"]
    src = (ROOT / "scripts" / "build_fpl_longtail.py").read_text(encoding="utf-8")
    alku = src.index("def render_expected_points(")
    loppu = src.index("\ndef ", alku + 1)
    assert 'partner_card_html(FPL_DEMON, now, "hub_expected_points")' in src[alku:loppu]
