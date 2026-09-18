# -*- coding: utf-8 -*-
"""JULKAISTU SIVU == SE MITA BUILDERI TUOTTAA COMMITTATUSTA ARTEFAKTISTA.

🔴 MIKSI (18.9, adversariaalinen tarkistus haarasta XP-HORIZON-ALKANUT-
KIERROS): `tests/test_club_best_page.py` oli AINOA portti joka vertasi
jakokorttia JULKAISTUUN sivuun — kortin alatunniste ohjaa lukijan juuri
sille sivulle todistamaan luvun. Haara vaihtoi sen fikstuurin lukemaan
prosessissa renderoitua sivua samasta payloadista jolla kortti tehdaan,
jolloin levylla oleva `fpl/club-best.html` (jonka CF Pages tarjoilee) voi
olla mita tahansa. Mitattu samana paivana: 13/80 club-best-rivia erosi
uudesta laskennasta NAKYVALLA tarkkuudella (SUN GKP gap +15.3 -> +15.2,
NEW DEF +0.6 -> +0.5, MCI DEF xP 29.7 -> 29.8). Kortti olisi siis
ohjannut lukijan sivulle joka sanoo eri luvun — tasan se vikaluokka jota
haaran commit-viesti kaytti perusteluna.

MIKSI TAMA EI OLE VAIHESIDOTTU TESTI (se perustelu jolla vertailu
poistettiin): vertailussa ei ole kelloa eika verkkoa. Molemmat puolet ovat
COMMITTATTUJA: `data/fpl_xp_projections.json` ja `fpl/*.html`. Sivun leima
tulee datan `generated_at`ista (`_data_now`), ei ajohetkesta, joten render
on deterministinen. Testi ei siis sano "sivu on vanha" vaan "sivu ei ole
sen artefaktin ja sen builderin tulos jotka olet committoimassa".

KUN TAMA ON PUNAINEN, KORJAUS ON SIVUJEN REGENEROINTI SAMAAN PUSHIIN:
    python scripts/build_fpl_longtail.py     (tai vain nama renderit)
Ei portin loysentaminen. Rivien luvut ovat julkista tekstia.

Mekanismi (2) — POIKKEUSLISTA JOSSA ON PERUSTELU: `EXEMPT` nimeaa jokaisen
xP-artefaktista rakennetun sivun jota EI voi verrata, ja miksi. Uusi
`render_*(xp, now)` -kutsu builderin `main()`issa kaatuu
`test_every_xp_page_is_compared_or_exempt`iin ennen kuin se voi ajautua
julkaisuun vartioimatta.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
XP_PATH = ROOT / "data" / "fpl_xp_projections.json"

# renderoija -> julkaistu sivu (polku repon juuresta)
PAGES = {
    "render_captain": "fpl/best-captain.html",
    "render_model_xi": "fpl/model-xi.html",
    "render_expected_points": "fpl/expected-points.html",
    "render_club_best": "fpl/club-best.html",
    "render_team_news": "fpl/team-news.html",
    "render_predicted_lineups": "fpl/predicted-lineups.html",
}

# renderoija -> perustelu. Uusi rivi tanne vaatii kirjoitetun syyn.
EXEMPT: dict[str, str] = {
    # ei yhtaan: seurasivut verrataan omassa testissaan (render_club_pages
    # kirjoittaa itse levylle, joten sille annetaan tmp-hakemisto)
}

CLUB_RENDERER = "render_club_pages"


def _norm(s: str) -> str:
    """Rivinvaihdot normalisoidaan: builderi kirjoittaa Windowsilla CRLF:n
    ja git sailoo LF:n. Ero ei ole se mita tama portti mittaa."""
    return s.replace("\r\n", "\n")


@pytest.fixture(scope="module")
def payload():
    """SAMA LUKIJA kuin builderin `main()`illa (17.9): horisonttisumma vain
    vaikutettavista kierroksista."""
    from src.models.fpl_xp import attach_horizon_total_actionable
    if not XP_PATH.exists():
        pytest.skip("artefaktia ei ole talla koneella")
    return attach_horizon_total_actionable(
        json.loads(XP_PATH.read_text(encoding="utf-8")))


@pytest.mark.parametrize("renderer,rel", sorted(PAGES.items()))
def test_committed_page_is_what_the_builder_writes_today(payload, renderer, rel):
    import scripts.build_fpl_longtail as L
    page = getattr(L, renderer)(payload, L._data_now(payload))
    assert page, f"{renderer} palautti None"
    disk = (ROOT / rel).read_text(encoding="utf-8")
    assert _norm(page) == _norm(disk), (
        f"{rel} EI ole sen artefaktin ja taman builderin tulos. "
        "Aja refresh ja committaa regeneroitu sivu SAMAAN pushiin — "
        "julkinen sivu on se jolla lukija tarkistaa kortin luvun.")


def test_committed_club_pages_are_what_the_builder_writes_today(
        payload, tmp_path, monkeypatch):
    import scripts.build_fpl_longtail as L
    monkeypatch.setattr(L, "CLUB_DIR", tmp_path)
    slugs = L.render_club_pages(payload, L._data_now(payload))
    assert slugs, "yhtaan seurasivua ei syntynyt"
    for slug in slugs:
        got = (tmp_path / f"{slug}.html").read_text(encoding="utf-8")
        repo = ROOT / "fpl" / "club" / f"{slug}.html"
        assert repo.exists(), f"seurasivu {slug} ei ole committoitu"
        assert _norm(got) == _norm(repo.read_text(encoding="utf-8")), (
            f"fpl/club/{slug}.html ei ole taman builderin tulos")


def test_every_xp_page_is_compared_or_exempt():
    """Mekanismi (2): uusi xP-artefaktista rakennettu sivu ei paase
    julkaisuun vartioimatta. Skannataan builderin `main()` ja poimitaan
    jokainen `render_*(xp, ...)` -kutsu."""
    src = (ROOT / "scripts" / "build_fpl_longtail.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    main = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    found = set()
    for n in ast.walk(main):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id.startswith("render_") and n.args
                and isinstance(n.args[0], ast.Name) and n.args[0].id == "xp"):
            found.add(n.func.id)
    assert found, "skanneri ei loytanyt yhtaan render_*(xp, ...) -kutsua"
    listed = set(PAGES) | set(EXEMPT) | {CLUB_RENDERER}
    assert found - listed == set(), (
        f"Uusi xP-sivu ilman vertailua: {sorted(found - listed)}. Lisaa "
        "PAGES-listalle (ja committaa sen tuotos) tai EXEMPT-listalle "
        "perusteluineen.")
    assert listed - found == set(), f"poistunut renderoija listalla: {sorted(listed - found)}"
    for r, why in EXEMPT.items():
        assert why and len(why) > 20, r


def test_the_comparison_would_see_a_single_changed_number():
    """EXIT-KOODI EI OLE TODISTE: vertailu ei saa olla vihrea siksi etta se
    vertaa jotain muuta kuin sivun sisaltoa. Yksi merkki riittaa."""
    a = "<td>29.7</td>\r\n"
    assert _norm(a) == "<td>29.7</td>\n"
    assert _norm(a) != _norm("<td>29.8</td>\r\n")
