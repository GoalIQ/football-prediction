"""KUMPPANILINKKI (27.9.2026, FPL Demon, Villen paatos).

Portti vartioi nelja asiaa:
  1. URL on Demonin itse lahettama planneri-linkki hanen omilla utm-tageillaan
     (hanen analytiikkansa lukee niita, ei meidan keksimiamme);
  2. kumppanin domain on VAIN src/partners.py:ssa (saanto 6a: pinta ei
     kirjoita URL:ia kasin, joten tagi tai paattyminen ei unohdu);
  3. linkki paattyy itsestaan `active_until`-paivana (julkaisutarkistaja B4);
  4. SIJOITUS mitataan RENDEROIDYLTA sivulta, ei funktiosta (muisti:
     testi kutsuu funktiota, ei kutsupaikkaa): ilmaisen /fpl/expected-points
     -sivun top 100 -taulukon alla, ennen UPSELL/CTA:ta joka on ostohetki,
     ja vain talla sivulla.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from src.partners import FPL_DEMON, partner_active, partner_line_html

ROOT = Path(__file__).resolve().parents[1]
UNTIL = datetime.fromisoformat(FPL_DEMON["active_until"]).replace(tzinfo=timezone.utc)
BEFORE = UNTIL - timedelta(seconds=1)


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
    assert partner_line_html(FPL_DEMON, UNTIL, "x") == ""
    # Kokeilu on sovittu GW10:n loppuun; pidempi paiva vaatii paatoksen.
    assert FPL_DEMON["active_until"] <= "2026-11-10"


def test_line_markup():
    html = partner_line_html(FPL_DEMON, BEFORE, "hub_expected_points")
    assert html.startswith('<p class="note"><strong>Partner:</strong> ')
    assert "FPL Demon's planner and solver run on these projections." in html
    assert 'href="https://fpldemon.com/fpl/planner?utm_source=goaliq&amp;utm_medium=social&amp;utm_campaign=goaliq"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener sponsored"' in html
    assert ("posthog.capture('partner_link_clicked',"
            "{partner:'fpldemon',surface:'hub_expected_points'})") in html
    assert "—" not in html  # em dash kielletty


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


def test_free_expected_points_page_places_it_under_the_table():
    import scripts.build_fpl_longtail as L
    page = L.render_expected_points(_xp(), BEFORE) or ""
    assert page.count("fpldemon.com") == 1
    link = page.index("fpldemon.com")
    top100 = page.index('id="top-100"')
    table_end = page.index("</table>", top100)
    upsell = page.index(L.UPSELL)
    cta = page.index('class="cta-row"')
    assert top100 < table_end < link < upsell < cta


def test_expired_page_has_no_link():
    import scripts.build_fpl_longtail as L
    page = L.render_expected_points(_xp(), UNTIL) or ""
    assert page, "sivu ei renderoitynyt"
    assert "fpldemon.com" not in page
    assert "Partner:" not in page


def test_only_one_call_site():
    """Muut sivut (ja paywall) eivat saa linkkia vahingossa: kutsupaikkoja on
    yksi, ja se on render_expected_points. Uusi sijoitus vaatii tietoisen
    muutoksen tahan."""
    kutsut = []
    for p in [*(ROOT / "scripts").rglob("*.py"), *(ROOT / "src").rglob("*.py"),
              *(ROOT / "api").rglob("*.py")]:
        if p.name == "partners.py":
            continue
        for m in re.finditer(r"partner_line_html\(", p.read_text(encoding="utf-8", errors="ignore")):
            kutsut.append(p.relative_to(ROOT).as_posix())
    assert kutsut == ["scripts/build_fpl_longtail.py"]
    src = (ROOT / "scripts" / "build_fpl_longtail.py").read_text(encoding="utf-8")
    alku = src.index("def render_expected_points(")
    loppu = src.index("\ndef ", alku + 1)
    assert "partner_line_html(FPL_DEMON" in src[alku:loppu]
