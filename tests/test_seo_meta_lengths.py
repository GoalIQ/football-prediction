# -*- coding: utf-8 -*-
"""Hakutuloksen otsikko <= 60 ja kuvaus <= 160 merkkia (LOYDETTAVYYS-5, 3.11.2026).

TAUSTA. Mitattu 3.11: julkaistavista sivuista 2 789 / 3 315 kuvausta oli yli
160 merkkia ja 1 274 otsikkoa yli 60. Pohjat oli kirjoitettu kasin yksi
kerrallaan, ja raja muistettiin vain osassa: points-sivun kuvaus oli tasan
160 kierroksilla 1-9 ja olisi ollut 161 kierroksesta 10 alkaen.

PORTTI (CLAUDE.md 6a):
1. Jokaisen builderin `_page()` kutsuu `seo_meta.check`ia, joten yli rajan
   menevaa sivua ei kirjoiteta. Tama testi ajaa builderit OIKEALLA datalla
   hiekkalaatikkoon ja tarkistaa, etta jokainen kirjoitettu sivu kulki
   tarkistuksen lapi (ei ohitusreittia) ja pysyi rajoissa.
2. Poikkeus vain `seo_meta.POIKKEUKSET`-listan perustellulla avaimella, ja
   vain lyhimmalle ehdokkaalle (`seo_meta.fit`).
3. Vaiheet ja pahimmat arvot: ottelusivun kaikki tilat (tuleva, kesken,
   pelattu) pisimmilla oikeilla nimilla, points-sivu kierroksilla 1-38,
   longtail pisimmalla ikkunatekstilla ja pelaajanimella.
"""
from __future__ import annotations

import html as _html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import seo_meta
from scripts import build_prediction_pages as bpp
from src.models import accuracy as acc
from src.models.call_margin import call_state

ROOT = Path(__file__).resolve().parents[1]
T = re.compile(r"<title>(.*?)</title>", re.S)
D = re.compile(r'<meta name="description" content="([^"]*)"')


def _meta(html: str) -> tuple[str, str | None]:
    t = T.search(html)
    d = D.search(html)
    return (_html.unescape(t.group(1).strip()) if t else "",
            _html.unescape(d.group(1)) if d else None)


@pytest.fixture
def recorded(monkeypatch):
    """Kirjaa jokaisen `seo_meta.check`-kutsun ja delegoi oikealle."""
    seen: list[tuple[str, str, str]] = []
    real = seo_meta.check

    def rec(title, desc, where):
        seen.append((where, title, desc))
        real(title, desc, where)

    monkeypatch.setattr(seo_meta, "check", rec)
    return seen


def _assert_all_written_pages_checked(files: list[Path], seen) -> dict[str, int]:
    """Jokainen kirjoitettu sivu kulki checkin lapi samoilla arvoilla ja on
    rajoissa tai perustellussa poikkeuksessa. Palauttaa poikkeuslaskurin."""
    assert files, "builder ei kirjoittanut yhtaan sivua"
    checked = {(str(t), str(d)) for _, t, d in seen}
    poikkeukset: dict[str, int] = {}
    for where, t, d in seen:
        assert not seo_meta.problems(t, d), (where, seo_meta.problems(t, d))
        for v in (t, d):
            if isinstance(v, seo_meta.Poikkeus):
                poikkeukset[v.syy] = poikkeukset.get(v.syy, 0) + 1
    for f in files:
        t, d = _meta(f.read_text(encoding="utf-8"))
        assert d is not None, f"{f}: ei meta descriptionia"
        assert (t, d) in checked, f"{f}: sivu ohitti seo_meta.checkin"
    return poikkeukset


# ---------------------------------------------------------------------------
# 1. seo_meta itse
# ---------------------------------------------------------------------------
def test_poikkeuslistan_jokaisella_avaimella_on_perustelu():
    assert seo_meta.POIKKEUKSET
    for k, v in seo_meta.POIKKEUKSET.items():
        assert isinstance(v, str) and len(v.strip()) >= 40, k


def test_fit_valitsee_ensimmaisen_joka_mahtuu_eika_katkaise():
    assert seo_meta.fit(["x" * 61, "y" * 60, "z"], 60) == "y" * 60
    with pytest.raises(seo_meta.MetaTooLong):
        seo_meta.fit(["x" * 61, "y" * 62], 60)


def test_poikkeus_vain_listatulla_avaimella_ja_vain_lyhimmalle():
    v = seo_meta.fit(["x" * 70, "y" * 65], 60, poikkeus="joukkuenimet")
    assert isinstance(v, seo_meta.Poikkeus) and v == "y" * 65
    seo_meta.check(v, "ok", "testi")  # perusteltu -> lapi
    with pytest.raises(seo_meta.MetaTooLong):
        seo_meta.fit(["x" * 70], 60, poikkeus="ei-listalla")
    # Tavallinen merkkijono ei saa poikkeusta, vaikka sisalto on sama.
    with pytest.raises(seo_meta.MetaTooLong):
        seo_meta.check("y" * 65, "ok", "testi")
    with pytest.raises(seo_meta.MetaTooLong):
        seo_meta.check("ok", "d" * 161, "testi")


def test_tyhja_perustelu_ei_vapauta(monkeypatch):
    monkeypatch.setitem(seo_meta.POIKKEUKSET, "tyhja", "   ")
    with pytest.raises(seo_meta.MetaTooLong):
        seo_meta.fit(["x" * 70], 60, poikkeus="tyhja")


# ---------------------------------------------------------------------------
# 2. Ottelusivut ja liigahubit oikealla lokilla
# ---------------------------------------------------------------------------
@pytest.fixture
def pred_sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(bpp, "OUT_ROOT", tmp_path / "predictions")
    monkeypatch.setattr(bpp, "SITEMAP_PRED_PATH", tmp_path / "sitemap.xml")
    monkeypatch.setattr(bpp, "PREDICTIONS_HTML", tmp_path / "none.html")
    monkeypatch.setattr(bpp, "LLMS_TXT", tmp_path / "llms.txt")
    monkeypatch.setattr(bpp, "_deploy_file_count", lambda: 1)
    return tmp_path


def test_ottelusivut_ja_hubit_oikealla_lokilla(pred_sandbox, recorded):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    assert bpp.main(now) == 0
    files = sorted((pred_sandbox / "predictions").rglob("*.html"))
    poikkeukset = _assert_all_written_pages_checked(files, recorded)
    # 3.11: 1 sivu (Sporting Clube de Portugal vs Manchester United FC).
    # Poikkeus on harvinainen; jos niita alkaa kertya, pohja on vaara.
    assert sum(poikkeukset.values()) <= max(3, len(files) // 500), poikkeukset
    print(f"ottelu- ja hubisivuja {len(files)}, poikkeukset {poikkeukset}")


def test_vanha_pitka_pohja_kaataa_buildin(pred_sandbox, monkeypatch):
    """MUTAATIO pysyvana kontrollina: 2.11:n pohja (otsikko brandilla ja
    liigalla, kuvaus liigalla, paivalla ja pitkalla varauksella) takaisin ->
    build kaatuu eika yhtaan sivua kirjoiteta."""
    def vanha(comp, e, state, call):
        home, away = e["home_team"], e["away_team"]
        name = bpp.LEAGUES[comp]["name"]
        fav, pct = bpp._favourite_label(e, call)
        title = f"{home} vs {away} Prediction: {name} | GoalIQ"
        desc = (f"{home} vs {away} ({name}, {e.get('date')}): the GoalIQ model "
                f"gives {fav} a {pct} chance to win. Updated until kick-off, and the "
                f"last version is graded in our public track record.")
        return title, desc

    monkeypatch.setattr(bpp, "match_page_meta", vanha)
    with pytest.raises(seo_meta.MetaTooLong):
        bpp.main(datetime.now(timezone.utc))


NOW = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
RESULT = {"home_score": 1, "away_score": 1, "actual_outcome": "draw",
          "actual_score": "1-1", "hit_1x2": False,
          "reconciled_at": "2026-11-01T00:00:00+00:00"}


_NAMES: dict[str, list[str]] = {}


def _longest_names() -> dict[str, list[str]]:
    """Kunkin kilpailun nelja pisinta nayttonimea oikeasta lokista."""
    if not _NAMES:
        feed = bpp.load_feed(acc.load_log(), NOW - timedelta(days=400))
        names: dict[str, set] = {}
        for comp in bpp.LEAGUES:
            for e in bpp.page_rows(feed, comp):
                names.setdefault(comp, set()).update((e["home_team"], e["away_team"]))
        _NAMES.update({c: sorted(v, key=len)[-4:] for c, v in names.items()})
    return _NAMES


@pytest.mark.parametrize("probs", [(0.70, 0.18, 0.12), (0.12, 0.18, 0.70),
                                   (0.36, 0.30, 0.34)], ids=["koti", "vieras", "tasan"])
@pytest.mark.parametrize("days,result", [(3, None), (-1, None), (-2, RESULT)],
                         ids=["tuleva", "kesken", "pelattu"])
def test_ottelusivu_pisimmilla_nimilla_kaikissa_tiloissa(probs, days, result):
    ko = NOW + timedelta(days=days)
    for comp, names in _longest_names().items():
        for home in names:
            for away in names:
                if home == away:
                    continue
                e = {"match_id": "x", "competition": comp, "home_team": home,
                     "away_team": away, "kickoff": ko.strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "date": ko.strftime("%Y-%m-%d"), "p_home": probs[0],
                     "p_draw": probs[1], "p_away": probs[2], "result": result,
                     "logged_at": "2026-10-20T10:00:00+00:00"}
                state = bpp._played_state(e, NOW)
                t, d = bpp.match_page_meta(comp, e, state,
                                           call_state(*probs))
                assert not seo_meta.problems(t, d), (comp, home, away)
                core = f"{home} vs {away} Prediction"
                # Otsikon poikkeus vain kun pelkka ydin ei mahdu.
                if isinstance(t, seo_meta.Poikkeus):
                    assert t == core and len(core) > seo_meta.TITLE_MAX
                assert len(t) <= max(seo_meta.TITLE_MAX, len(core))
                # Varaus on jokaisessa kuvauksessa.
                assert "updated until kick-off" in d.lower(), d


def test_liigahubien_kuvaus_mahtuu_jokaisella_liigalla():
    e = {"match_id": "x", "home_team": "A", "away_team": "B",
         "kickoff": "2026-11-05T15:00:00Z", "date": "2026-11-05",
         "p_home": 0.5, "p_draw": 0.3, "p_away": 0.2, "result": None}
    for comp in bpp.LEAGUES:
        t, d = _meta(bpp.render_league_hub(comp, [dict(e, competition=comp)], NOW))
        assert len(t) <= 60 and d is not None and len(d) <= 160, (comp, t, d)


# ---------------------------------------------------------------------------
# 3. Longtail (fpl/*) oikealla datalla + pahimmat arvot
# ---------------------------------------------------------------------------
@pytest.fixture
def longtail_sandbox(tmp_path, monkeypatch):
    from scripts import build_fpl_longtail as bfl
    out = tmp_path / "fpl"
    patched = {"OUT_DIR": out, "CLUB_DIR": out / "club", "NOTE_DIR": out / "note",
               "POINTS_DIR": out / "points", "SITEMAP_FPL_PATH": tmp_path / "sitemap-fpl.xml"}
    for k, v in patched.items():
        monkeypatch.setattr(bfl, k, v)
    # Turva: yksikaan muu moduulin polku ei saa osoittaa fpl/-hakemistoon
    # kirjoituskohteena (lukupolut sallitaan nimelta).
    reads = {"PLAYER_GW_PATH"}
    fpl_root = (bfl.ROOT / "fpl").resolve()
    for k, v in vars(bfl).items():
        if isinstance(v, Path) and k not in patched and k not in reads:
            assert fpl_root not in v.resolve().parents and v.resolve() != fpl_root, (
                f"{k} osoittaa fpl/-hakemistoon: lisaa se hiekkalaatikkoon")
    return bfl, out


def _longtail_files(out: Path) -> list[Path]:
    return sorted(out.rglob("*.html"))


def test_longtail_oikealla_datalla(longtail_sandbox, recorded):
    bfl, out = longtail_sandbox
    assert bfl.main() == 0
    files = _longtail_files(out)
    poikkeukset = _assert_all_written_pages_checked(files, recorded)
    # Poikkeus vain muistioiden toimituksellisille otsikoille (3.11: 2/12).
    assert set(poikkeukset) <= {"artikkelin-otsikko"}, poikkeukset
    print(f"longtail-sivuja {len(files)}, poikkeukset {poikkeukset}")


def test_longtail_pisimmalla_ikkunalla_ja_nimella(longtail_sandbox, recorded, monkeypatch):
    """Vaihe jota ei ole nyt: ikkuna ilman kierroksia ("a 5-GW horizon") ja
    pisin oikea pelaajanimi (16 merkkia, 3.11) jokaisella pelaajalla."""
    bfl, out = longtail_sandbox
    monkeypatch.setattr(bfl, "_window_label", lambda *a, **k: "a 5-GW horizon")
    real_load = bfl._load

    def load(path):
        d = real_load(path)
        if path == bfl.XP_PATH and d:
            for p in d.get("players") or []:
                p["web_name"] = "Williams-Barnett"
        return d

    monkeypatch.setattr(bfl, "_load", load)
    assert bfl.main() == 0
    files = _longtail_files(out)
    _assert_all_written_pages_checked(files, recorded)
    # Kontrolli: paikkaus oikeasti vaikutti (muuten testi olisi tyhja).
    metas = [d for _, _, d in recorded]
    assert any("a 5-GW horizon" in d for d in metas)
    assert any("Williams-Barnett" in d for d in metas)


@pytest.mark.parametrize("archive", [True, False])
def test_points_jokaisella_kierroksella(archive):
    from scripts.build_fpl_longtail import points_meta
    for gw in range(1, 39):
        t, d = points_meta(gw, archive)
        assert len(t) <= 60 and len(d) <= 160, (gw, t, d)


def test_muistion_otsikko_pudottaa_kokonaisia_paloja():
    from scripts.build_fpl_longtail import note_title
    assert note_title("Short headline") == "Short headline | GoalIQ"
    two = ("Everyone's buying the Arsenal defence. "
           "Read the minutes column first.")
    assert note_title(two) == "Everyone's buying the Arsenal defence."
    one = "A" * 40 + " " + "b" * 40
    t = note_title(one)
    assert isinstance(t, seo_meta.Poikkeus) and t == one


# ---------------------------------------------------------------------------
# 4. fpl.html ja kasin kirjoitetut juurisivut
# ---------------------------------------------------------------------------
def test_fpl_html_oikealla_datalla(recorded):
    from scripts import build_fpl_page as bfp
    fpl, accd = bfp.load_data()
    c = bfp.build_context(fpl, accd)
    xp = bfp._load_json(bfp.XP_PATH)
    if xp:
        xp = bfp.attach_horizon_total_actionable(xp)
    t, d = _meta(bfp.render_page(c, xp))
    assert recorded and (t, d) == tuple(map(str, recorded[-1][1:]))
    assert len(t) <= 60 and d is not None and len(d) <= 160, (t, d)


#: Juuren sivut jotka builder kirjoittaa kokonaan; niiden portti on yllä
#: (committoitu tiedosto on vanha kunnes bot ajaa builderin).
BUILDER_ROOT_PAGES = {"fpl.html"}


@pytest.mark.parametrize("f", sorted(p.name for p in ROOT.glob("*.html")
                                     if p.name not in BUILDER_ROOT_PAGES))
def test_kasin_kirjoitettu_juurisivu_mahtuu(f):
    t, d = _meta((ROOT / f).read_text(encoding="utf-8"))
    assert len(t) <= 60, f"{f}: title {len(t)}: {t}"
    if d is not None:
        assert len(d) <= 160, f"{f}: description {len(d)}: {d}"
