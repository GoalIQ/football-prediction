"""Ottelusivu todisteeksi + liigahubin ryhmittely (ulkoasu WP11, 1.11.2026).

Lukitsee rakenteella (CLAUDE.md 6a), ei tapauksella:

1. LUKOSSA EI OLE PREMIUM-LUKUJA. CSS-sumennus ei piilota DOM:sta mitaan,
   joten sumennetun ruudukon solut ovat paikkamerkkeja. Testi ajaa OIKEAN
   mallin (Dixon-Coles, synteettiset parametrit) -> oikean lokittajan
   (`accuracy_pipeline.prediction_row_from_api`) -> sivun, ja mittaa etta
   mallin muut 9 tulosta, niiden todennakoisyydet ja xG eivat ole sivulla,
   JSON-LD:ssa, sitemapissa eivatka lokirivilla.
2. Suosikki on nakyvin segmentti ja se tulee call_statesta (sama funktio
   ottelusivulle ja hubin riveille).
3. Gradatun sivun "Model said X · Result Y · Counted as a hit/miss" on sama
   kuin julkisen track recordin taulukon rivi (build_fpl_page.record_table_html),
   koko oikealle lokille. Ei toista gradausta.
4. Hub: oletuksena vain HUB_VISIBLE_DAYS, loput <details>-elementissa.
5. Vaiheinvariantit: ennen kickoffia / kickoffin jalkeen gradaamatta /
   gradattu. Form ei koskaan sisalla ottelua itseaan eika myohempaa tulosta.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import build_prediction_pages as bpp
from src.models import accuracy as acc
from src.models import call_margin as cm

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
M16 = {"margin_pp": 16, "decisive_below_pct": 46,
       "measured_at": "2026-09-10T03:36:00+00:00"}


@pytest.fixture(autouse=True)
def _kiintea_marginaali(monkeypatch):
    """call_state ilman levyn artefaktia: 16 pp kuten test_call_margin."""
    monkeypatch.setattr(bpp, "call_state",
                        lambda ph, pd_, pa: cm.call_state(ph, pd_, pa, margin=M16))


def _entry(days: float, result=None, home="Arsenal", away="Liverpool",
           ph=0.62, pd_=0.21, pa=0.17, now=NOW, **kw) -> dict:
    ko = now + timedelta(days=days)
    e = {
        "match_id": f"t-{home}-{away}-{days}", "competition": "PL",
        "home_team": home, "away_team": away,
        "kickoff": ko.strftime("%Y-%m-%dT%H:%M:%SZ"), "date": ko.strftime("%Y-%m-%d"),
        "p_home": ph, "p_draw": pd_, "p_away": pa,
        "predicted_winner": acc.named_winner(ph, pa),
        "most_likely_score": "1-0",
        "logged_at": (ko - timedelta(hours=3)).isoformat(), "result": result,
    }
    e.update(kw)
    return e


def _result(hs: int, as_: int, e: dict) -> dict:
    """Gradaus TUOTANNON funktiolla, ei kasin."""
    return acc._build_result(e, hs, as_)


def _graded(days: float, hs: int, as_: int, **kw) -> dict:
    e = _entry(days, **kw)
    e["result"] = _result(hs, as_, e)
    return e


def _body(html: str) -> str:
    """Nakyva runko ilman <head>:ia, tyyleja ja skripteja."""
    b = html[html.index("<body>"):]
    b = re.sub(r"<script.*?</script>", "", b, flags=re.S)
    return re.sub(r"<style.*?</style>", "", b, flags=re.S)


def _lock(html: str) -> str:
    m = re.search(r'<div class="lock-grid".*?</div>', html, re.S)
    assert m, "lukkoruudukko puuttuu"
    return m.group(0)


# ---------------------------------------------------------------------------
# 1. Premium-vuoto: malli -> lokittaja -> sivu
# ---------------------------------------------------------------------------
def _malli_ja_vastaus():
    """Oikea Dixon-Coles-malli synteettisilla parametreilla ja /api/predictin
    muotoinen vastaus siita (PREDICT_MASK pois = taysi Premium-vastaus)."""
    from src.models.dixon_coles import DixonColesModel
    dc = DixonColesModel(attack={"Arsenal": 0.35, "Liverpool": 0.1},
                         defence={"Arsenal": -0.25, "Liverpool": -0.05},
                         home_advantage=0.22, rho=-0.08,
                         teams_=["Arsenal", "Liverpool"])
    lam, mu = dc.expected_goals("Arsenal", "Liverpool")
    p = dc.predict_1x2("Arsenal", "Liverpool")
    top = dc.todennakoisin_tulos("Arsenal", "Liverpool", top_n=bpp.PREMIUM_TOP_SCORES)
    vastaus = {
        "p_home_win": p["home"], "p_draw": p["draw"], "p_away_win": p["away"],
        "expected_goals_home": lam, "expected_goals_away": mu,
        "top_scores": [{"score": s, "probability": round(q, 4)} for s, q in top],
        "meta": {},
    }
    return vastaus


def _lukumuodot(x: float) -> set[str]:
    """Muodot joissa luku voisi vuotaa: 0.137, 0.14, 13.7, 14% ..."""
    return {f"{x:.4f}", f"{x:.3f}", f"{x:.2f}", f"{x * 100:.1f}", f"{x * 100:.2f}"}


def test_lukossa_ei_mallin_premium_lukuja_sivulla_eika_jsonld_ssa():
    from scripts import accuracy_pipeline as ap
    v = _malli_ja_vastaus()
    rivi = ap.prediction_row_from_api("Arsenal", "Liverpool", v)
    # lokirivi saa ylimman tuloksen ja sen todennakoisyyden, ei muuta
    assert rivi["most_likely_score"] == v["top_scores"][0]["score"]
    assert rivi["most_likely_score_p"] == v["top_scores"][0]["probability"]
    assert "top_scores" not in rivi
    e = _entry(2, **{k: rivi[k] for k in rivi if k not in ("home_team", "away_team")})
    acc.strip_prematch_private({"predictions": [e]})   # sama siivous kuin save_log
    assert e["xg_home"] is None and e["xg_away"] is None
    html = bpp.render_match_page("PL", e, NOW)

    # (a) ruudukossa ei ole yhtaan numeroa: solut ovat paikkamerkkeja
    assert not re.search(r"\d", _lock(html)), _lock(html)
    # (b) ylin tulos ja sen % nakyvat (Villen paatos 1.11), loput 9 eivat
    top1 = v["top_scores"][0]
    assert f"<b>{top1['score']}</b>" in html
    assert f'<span class="p">{bpp._fmt_pct(top1["probability"])}</span>' in html
    body = _body(html)
    for s in v["top_scores"][1:]:
        for muoto in _lukumuodot(s["probability"]):
            assert muoto not in body, (s, muoto)
    # nakyvassa tekstissa ei muita tuloslukuja kuin ylin (paivamaarat pois)
    tulokset = set(re.findall(r"(?<![\d-])\d{1,2}-\d{1,2}(?![\d-])", body))
    assert tulokset == {top1["score"]}, tulokset
    # (c) xG ei missaan muodossa
    for x in (v["expected_goals_home"], v["expected_goals_away"]):
        for muoto in _lukumuodot(x):
            assert muoto not in body, muoto
    # (d) JSON-LD: ei tulos-, xG- eika todennakoisyyskenttia
    for blokki in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        avaimet = json.dumps(json.loads(blokki)).lower()
        for kielletty in ("xg", "expected", "probab", "scoreline", "most_likely"):
            assert kielletty not in avaimet, kielletty


def test_gradatun_rivin_xg_ei_paady_sivulle():
    """Gradatulla rivilla xG jaa lokiin (ottelu pelattu), mutta sivu ei nayta sita."""
    e = _graded(-1, 2, 1, xg_home=1.734, xg_away=0.619)
    html = bpp.render_match_page("PL", e, NOW)
    for muoto in ("1.734", "1.73", "0.619", "0.62", "1.7 ", "0.6 "):
        assert muoto not in _body(html), muoto
    # Pelattu sivu: ei ruudukkoa lainkaan (julkaisutarkistaja 1.11, PR #76).
    assert '<div class="lock-grid"' not in html


def test_ylimman_tuloksen_prosentti_vain_lokista():
    """Ei keksitty luku: ilman lokin kenttaa sivu nayttaa vain tuloksen."""
    ilman = bpp.render_match_page("PL", _entry(2), NOW)
    assert "<b>1-0</b>" in ilman and '<span class="p">' not in ilman
    assert "9 more scorelines and expected goals in Premium." in ilman
    kanssa = bpp.render_match_page("PL", _entry(2, most_likely_score_p=0.1349), NOW)
    assert '<span class="p">13%</span>' in kanssa
    # ei tulosta lokissa -> ei "more", maara kattaa kaikki
    tyhja = bpp.render_match_page("PL", _entry(2, most_likely_score=None), NOW)
    assert "Top scoreline" not in tyhja
    assert f"{bpp.PREMIUM_TOP_SCORES} scorelines and expected goals in Premium." in tyhja


def test_premium_maara_on_sama_kuin_predictissa():
    """'9 more' on tosi vain jos Premium nayttaa 10: luetaan SPA:n lahteesta."""
    svelte = (ROOT / "web/pro-spa/src/lib/components/Predict.svelte").read_text(encoding="utf-8")
    m = re.search(r"premium \? (\d+) : (\d+)", svelte)
    assert m, "Predict.svelte: top_n-valinta ei loydy"
    assert int(m.group(1)) == bpp.PREMIUM_TOP_SCORES


def test_lukon_nappi_vie_olemassa_olevaan_kassaan_ja_hinta_yhdesta_lahteesta():
    from src import price_copy as PC
    html = bpp.render_match_page("PL", _entry(2), NOW)
    napit = re.findall(r'<a class="btn solid" href="([^"]+)"', html)
    assert napit == ["https://pro.goaliq.app/checkout?plan=season"]
    # WP6 (4.11.2026): vuosipaketti on kertamaksu -> PC.season_cta().
    assert f"Start Premium, {PC.season_cta()}" in html
    assert "a year" not in html.split("Start Premium", 1)[1][:60]


def test_sitemap_ja_sivut_eivat_kanna_premium_kenttia(tmp_path, monkeypatch):
    """main() koko ajona: yksikaan kirjoitettu tiedosto ei sisalla rivin xG:ta."""
    monkeypatch.setattr(bpp, "OUT_ROOT", tmp_path / "predictions")
    monkeypatch.setattr(bpp, "SITEMAP_PRED_PATH", tmp_path / "sitemap.xml")
    monkeypatch.setattr(bpp, "PREDICTIONS_HTML", tmp_path / "none.html")
    monkeypatch.setattr(bpp, "LLMS_TXT", tmp_path / "llms.txt")
    monkeypatch.setattr(bpp, "_deploy_file_count", lambda: 1)
    monkeypatch.setattr(bpp, "_attach_confidence", lambda by_comp: 1)
    now = datetime.now(timezone.utc)
    rows = [_entry(3, now=now, xg_home=1.987, xg_away=0.456),
            _graded(-2, 1, 1, now=now, home="Everton", away="Fulham",
                    xg_home=1.876, xg_away=0.345)]
    monkeypatch.setattr(bpp.acc, "load_log", lambda: {"predictions": rows})
    assert bpp.main() == 0
    files = list((tmp_path / "predictions").rglob("*.html")) + [tmp_path / "sitemap.xml"]
    assert len(files) >= 3
    for f in files:
        t = f.read_text(encoding="utf-8")
        t = _body(t) if f.suffix == ".html" else t
        for muoto in ("1.987", "0.456", "1.876", "0.345", "1.99", "0.46", "1.88", "0.35"):
            assert t.count(muoto) == 0, (f.name, muoto)


# ---------------------------------------------------------------------------
# 2. Suosikki nakyvin segmentti
# ---------------------------------------------------------------------------
def _p3(html: str) -> list[tuple[str, str]]:
    return re.findall(r'<div class="p3c ([a-z]+)"><b>(\d+%)</b>', html)


def _bar(html: str, mini: bool = False) -> list[str]:
    m = re.search(r'<div class="pbar%s" aria-hidden="true">(.*?)</div>'
                  % (" mini" if mini else ""), html)
    return re.findall(r'<span class="([a-z]+)"', m.group(1))


@pytest.mark.parametrize("ph,pd_,pa,odotus", [
    (0.62, 0.21, 0.17, ["fav", "draw", "side"]),
    (0.17, 0.21, 0.62, ["side", "draw", "fav"]),
    (0.405, 0.24, 0.355, ["side", "draw", "side"]),   # too close: ei korostusta
])
def test_suosikki_on_korostettu_segmentti_ja_luku(ph, pd_, pa, odotus):
    html = bpp.render_match_page("PL", _entry(2, ph=ph, pd_=pd_, pa=pa), NOW)
    assert [r for r, _ in _p3(html)] == odotus
    assert _bar(html) == odotus
    # hubin rivi kayttaa samaa funktiota
    hub = bpp.render_league_hub("PL", [_entry(2, ph=ph, pd_=pd_, pa=pa)], NOW)
    assert _bar(hub, mini=True) == odotus
    assert ".pbar .fav{background:var(--amber);height:12px;}" in html


def test_lause_ei_puhu_simulaatioista_ja_nimeaa_suosikin():
    html = bpp.render_match_page("PL", _entry(2, ph=0.46, pd_=0.29, pa=0.25), NOW)
    assert ("The model makes <strong>Arsenal</strong> the favourite: "
            "46% to win, 29% draw, 25% Liverpool.") in html
    vieras = bpp.render_match_page("PL", _entry(2, ph=0.25, pd_=0.29, pa=0.46), NOW)
    assert ("<strong>Liverpool</strong> the favourite: 46% to win, 29% draw, "
            "25% Arsenal.") in vieras
    assert "simulat" not in html.lower() and "simulat" not in vieras.lower()


# ---------------------------------------------------------------------------
# 3. Tuomio = track recordin rivi
# ---------------------------------------------------------------------------
def _record_row(e: dict) -> tuple[str, bool] | None:
    """(pick-symboli 1/2/X, osuma) julkisen recordin taulukosta, tai None."""
    from scripts.build_fpl_page import record_table_html
    html = record_table_html([e], {"acc_pending": 0, "by_comp": []})
    m = re.search(r'<td class="team">.*?</td><td><strong>([12X-])</strong>.*?'
                  r'<td class="num">.*?</td><td class="num"><span class="rec-(hit|miss)">',
                  html, re.S)
    return (m.group(1), m.group(2) == "hit") if m else None


def _page_verdict(html: str) -> tuple[str, str, str] | None:
    m = re.search(r'<div class="verdict ([a-z]*)"><span>Model said <b>(.*?)</b>.*?'
                  r'<b>(Counted as a hit|Counted as a miss|Not counted in the track record)</b>',
                  html, re.S)
    return m.groups() if m else None


def test_tuomio_on_sama_kuin_recordissa_koko_lokille():
    log = acc.load_log()
    graded = [e for e in log["predictions"]
              if e.get("result") and e.get("competition") in bpp.LEAGUES
              and e.get("p_home") is not None]
    assert len(graded) > 100, "lokissa liian vahan gradattuja"
    for e in graded:
        rec = _record_row(e)
        html = bpp.render_match_page(e["competition"], dict(e), NOW)
        v = _page_verdict(html)
        assert v is not None, e["match_id"]
        cls, said, tail = v
        if rec is None:
            assert tail == "Not counted in the track record", e["match_id"]
            continue
        sym, hit = rec
        assert tail == ("Counted as a hit" if hit else "Counted as a miss"), e["match_id"]
        assert cls == ("hit" if hit else "miss")
        nimi = {"1": e["home_team"], "2": e["away_team"], "X": "Draw"}[sym]
        assert said.startswith(nimi), (e["match_id"], said, nimi)


def test_tuomio_ei_gradaa_uudelleen():
    """Rivin kirjattu osuma ratkaisee, vaikka luvut sanoisivat muuta (record
    ei koskaan muokkaa gradausta jalkikateen)."""
    e = _graded(-1, 2, 0)          # koti voitti, malli nimesi kodin -> hit
    e["result"] = dict(e["result"], hit_1x2=False)
    assert _page_verdict(bpp.render_match_page("PL", e, NOW))[2] == "Counted as a miss"
    assert _record_row(e)[1] is False


def test_tuomio_jatkoajalla_kertoo_90_min_tuloksen():
    e = _entry(-1)
    e["result"] = acc._build_result(e, 2, 1, duration="EXTRA_TIME",
                                    regular_home=1, regular_away=1)
    html = bpp.render_match_page("PL", e, NOW)
    assert "Result <b>2-1 (graded on the 90-minute score, 1-1)</b>" in html
    assert "Counted as a miss" in html


def test_too_close_tuomio_selittaa_recordin_nimeaman_puolen():
    e = _graded(-1, 1, 0, ph=0.405, pd_=0.24, pa=0.355)
    html = bpp.render_match_page("PL", e, NOW)
    assert "Too close to call" not in html          # pelattu: ei tulkintaa (neutraali lause)
    assert "even when the pre-match page called it too close." in html
    selva = bpp.render_match_page("PL", _graded(-1, 1, 0), NOW)
    assert "always names the more likely side" not in selva


# ---------------------------------------------------------------------------
# 4. Hub: ryhmittely ja ikkuna
# ---------------------------------------------------------------------------
def _outside_details(html: str) -> str:
    return re.sub(r"<details.*?</details>", "", html, flags=re.S)


def test_hub_nayttaa_vain_kaksi_viikkoa_loput_laajennuksessa():
    rows = [_entry(d, home=f"H{i}", away=f"A{i}")
            for i, d in enumerate((1, 1.2, 5, 13.5, 15, 40, 200))]
    html = bpp.render_league_hub("PL", rows, NOW)
    ulko = _outside_details(html)
    det = re.search(r"<details.*?</details>", html, re.S).group(0)
    for i in (0, 1, 2, 3):
        assert f">H{i} vs A{i}</a>" in ulko and f">H{i} vs A{i}</a>" not in det
    for i in (4, 5, 6):
        assert f">H{i} vs A{i}</a>" in det and f">H{i} vs A{i}</a>" not in ulko
    assert "<summary>Show all fixtures (3 more)</summary>" in det
    # paivaryhmat: kaksi saman paivan ottelua yhden otsikon alla
    assert ulko.count('<h2 class="dgrp">') == 3
    assert "Next 14 days" in ulko
    # kaikki rivit DOM:ssa ja ItemListissa (SEO), title ilman "This Week"
    assert html.count('class="mrow"') == 7
    assert '"numberOfItems": 7' in html
    t = re.search(r"<title>(.*?)</title>", html).group(1)
    assert "This Week" not in t and len(t) <= 60


def test_hub_tyhja_ikkuna_nayttaa_seuraavan_ottelupaivan():
    rows = [_entry(20, home="H0", away="A0"), _entry(20.1, home="H1", away="A1"),
            _entry(30, home="H2", away="A2")]
    html = bpp.render_league_hub("PL", rows, NOW)
    ulko = _outside_details(html)
    assert ">H0 vs A0</a>" in ulko and ">H1 vs A1</a>" in ulko
    assert ">H2 vs A2</a>" not in ulko
    assert "Next fixtures" in ulko and "Next 14 days" not in html


def test_hubin_viikkoluku_on_recordin_rasteista():
    recent = [_graded(-1, 2, 0, home="A", away="B"),        # hit
              _graded(-2, 0, 1, home="C", away="D"),        # miss
              _graded(-3, 1, 1, home="E", away="F"),        # draw = miss
              dict(_graded(-4, 3, 0, home="G", away="H"), void="NO_TIMESTAMP")]
    html = bpp.render_league_hub("PL", [_entry(2)], NOW, recent)
    assert "Last 7 days: <strong>1 of 3</strong> predictions were hits" in html
    played = html[html.index("Played in the last 7 days"):]
    assert played.count("&#10003; hit") == 1 and played.count("&#10007; miss") == 2
    for e in recent:
        rec = _record_row(e)
        if rec is not None:
            assert bpp.record_verdict(e)["hit"] is rec[1]
    assert "Last 7 days" not in bpp.render_league_hub("PL", [_entry(2)], NOW)


# ---------------------------------------------------------------------------
# 5. Vaiheinvariantit
# ---------------------------------------------------------------------------
def _form(html: str, team: str) -> str:
    m = re.search(r'<span class="t">%s</span><span class="fchips"[^>]*>(.*?)</span></div>'
                  % re.escape(team), html, re.S)
    return "".join(re.findall(r">([WDL])</span>", m.group(1))) if m else ""


def _historia() -> list[dict]:
    """Arsenalin ja Liverpoolin aiemmat tulokset + yksi MYOHEMPI ottelu."""
    h = []
    tulokset = [(-30, "Arsenal", "Chelsea", 2, 0), (-23, "Spurs", "Arsenal", 1, 1),
                (-16, "Arsenal", "Leeds", 0, 1), (-9, "Wolves", "Arsenal", 0, 3),
                (-30, "Liverpool", "Everton", 1, 0), (-23, "Liverpool", "Leeds", 2, 2),
                (-16, "Brentford", "Liverpool", 2, 1), (-9, "Liverpool", "Spurs", 4, 0),
                (-37, "Arsenal", "Everton", 5, 0), (-37, "Fulham", "Liverpool", 0, 0),
                (-44, "Arsenal", "Fulham", 0, 2), (-44, "Liverpool", "Wolves", 1, 0)]
    for d, ho, aw, hs, as_ in tulokset:
        h.append(_graded(d, hs, as_, home=ho, away=aw))
    # myohempi: tulos ei saa nakya ottelusivulla joka on ennen sita
    h.append(_graded(5, 0, 4, home="Arsenal", away="Brentford"))
    # siirretty ottelu ei ole tulos
    h.append(dict(_entry(10, home="Arsenal", away="Burnley"), void="POSTPONED"))
    return h


@pytest.mark.parametrize("vaihe", ["upcoming", "pending", "final"])
def test_vaiheinvariantit(vaihe):
    days = {"upcoming": 2, "pending": -1, "final": -1}[vaihe]
    e = _entry(days)
    hist = _historia()
    if vaihe == "final":
        e["result"] = _result(1, 2, e)
        hist.append(e)                  # oma rivi on historiassa gradattuna
    html = bpp.render_match_page("PL", e, NOW, history=hist)

    # luvut ja URL eivat riipu vaiheesta
    assert [p for _, p in _p3(html)] == ["62%", "21%", "17%"]
    assert 'rel="canonical" href="https://goaliq.app/predictions/premier-league/arsenal-vs-liverpool"' in html
    # lukko: tulevalla sivulla ruudukko ilman numeroita; pelatulla ei ruudukkoa
    # eika "N more" -lupausta (ruudukkoa ei ole tallessa)
    if vaihe == "upcoming":
        assert not re.search(r"\d", _lock(html))
    else:
        assert '<div class="lock-grid"' not in html
        assert "more scorelines" not in html
        assert "Scorelines and expected goals for upcoming matches are in Premium." in html
    # tuomio vain gradattuna, "pending" vain gradaamattomana kickoffin jalkeen
    assert (_page_verdict(html) is not None) == (vaihe == "final")
    assert ("Result pending" in html) == (vaihe == "pending")
    # kirjausleima: kirjattu ennen kickoffia joka vaiheessa
    assert "Logged before kick-off: " in html
    # form: viimeiset 5 ENNEN tata ottelua, vanhin ensin; ei omaa eika
    # myohempaa tulosta, ei siirrettya
    assert _form(html, "Arsenal") == "WWDLW"
    assert _form(html, "Liverpool") == "DWDLW"
    assert "Form, last 5 Premier League results" in html
    # jako ja kickoff kaikissa vaiheissa
    assert html.count('class="share-btn"') == 3
    # Yksi aikasaanto (src/local_time.py, WP2): time_tag + LOCAL_TIME_JS.
    assert re.search(r'kickoff <time datetime="[^"]+Z" data-giq-local>[^<]+UTC</time>', html)


def test_form_ei_lue_omaa_eika_myohempaa_tulosta():
    e = _entry(-1)
    e["result"] = _result(0, 5, e)
    myohempi = _graded(3, 0, 6, home="Arsenal", away="Spurs")
    aiempi = _graded(-8, 2, 0, home="Arsenal", away="Fulham")
    ko = bpp._kickoff_dt(e)
    assert bpp.team_form("Arsenal", [e, myohempi, aiempi], ko) == ["W"]
    assert bpp.team_form("Liverpool", [e, myohempi, aiempi], ko) == []


def test_kirjausleima_vain_jos_kirjattu_ennen_kickoffia():
    assert "Logged before kick-off" in bpp.render_match_page("PL", _entry(2), NOW)
    myoha = _entry(2)
    myoha["logged_at"] = (bpp._kickoff_dt(myoha) + timedelta(minutes=5)).isoformat()
    # leima (class="stamp"); meta-kuvauksen vakiolause ei ole leima
    assert 'class="stamp"' not in bpp.render_match_page("PL", myoha, NOW)
    assert 'class="stamp"' not in bpp.render_match_page(
        "PL", _entry(2, logged_at=None), NOW)


def test_kickoff_paikallisena_utc_varalla_ja_vahvistamaton_aika_ennallaan():
    html = bpp.render_match_page("PL", _entry(2), NOW)
    assert '<time datetime="2026-11-03T12:00:00Z" data-giq-local>Tue 03 Nov 2026, 12:00 UTC</time>' in html
    from src import local_time as LT
    assert LT.LOCAL_TIME_JS in html
    assert "time[data-ko]" not in html          # toinen aikasaanto ei palaa
    tbc = _entry(2)
    tbc["kickoff"] = "2026-11-03T00:00:00Z"
    h2 = bpp.render_match_page("PL", tbc, NOW)
    assert "kick-off time to be confirmed" in h2
    assert 'data-giq-local>Tue 03 Nov 2026, kick' not in h2
    assert not re.search(r'kickoff <time', h2)


def test_jakolinkit_ovat_tavallisia_linkkeja_ilman_kolmansia_skripteja():
    html = bpp.render_match_page("PL", _entry(2), NOW)
    url = "https%3A%2F%2Fgoaliq.app%2Fpredictions%2Fpremier-league%2Farsenal-vs-liverpool"
    assert f'href="https://x.com/intent/post?text=Arsenal%20vs%20Liverpool%20prediction&amp;url={url}"' in html
    assert f'href="https://wa.me/?text=Arsenal%20vs%20Liverpool%20prediction%20{url}"' in html
    assert 'data-copy="https://goaliq.app/predictions/premier-league/arsenal-vs-liverpool" hidden>Copy link</button>' in html
    # vain oman originin skriptit (ref-bridge.js), ei kolmansia osapuolia
    assert re.findall(r'<script[^>]+src="([^"]+)"', html) == ["/ref-bridge.js"]


def test_ei_alle_12px_fonttia_uusissa_tyyleissa():
    uudet = bpp.CSS[bpp.CSS.index("UI programme WP11"):bpp.CSS.index("/* GEN:MOBILE-CSS */")]
    koot = [int(x) for x in re.findall(r"font-size:(\d+)px", uudet)]
    assert koot and min(koot) >= 12, koot


def test_julkisessa_copyssa_ei_vedonlyontisanoja():
    sivut = [bpp.render_match_page("PL", _entry(2), NOW),
             bpp.render_match_page("PL", _graded(-1, 1, 0), NOW, history=_historia()),
             bpp.render_league_hub("PL", [_entry(2)], NOW, [_graded(-1, 1, 0)])]
    for h in sivut:
        t = _body(h).lower()
        for sana in ("odds", "tips", " edge", "best bet", "value", "simulat",
                     "most likely score", "—"):
            assert sana not in t, sana


def test_refresh_kirjoittaa_ylimman_tuloksen_todennakoisyyden():
    """Kenttä tulee lokiin samalla polulla kuin muut ennusteluvut: ensikirjaus
    (prediction_row_from_api) ja pre-kickoff-refresh (REFRESH_FIELDS)."""
    from scripts import accuracy_pipeline as ap
    rivi = ap.prediction_row_from_api("Arsenal", "Liverpool", _malli_ja_vastaus())
    e = _entry(2, most_likely_score_p=None, league="ENG-Premier League")
    paivitetyt, _, _ = ap._apply_refresh([e], lambda lg, h, a: rivi)
    assert paivitetyt == 1
    assert e["most_likely_score_p"] == rivi["most_likely_score_p"] > 0
    assert "most_likely_score_p" in ap.REFRESH_FIELDS


def test_form_vaatii_vahintaan_kolme_tulosta_molemmille():
    hist = [_graded(-9, 1, 0, home="Arsenal", away="Fulham"),
            _graded(-16, 1, 0, home="Arsenal", away="Leeds"),
            _graded(-23, 1, 0, home="Arsenal", away="Wolves"),
            _graded(-9, 1, 0, home="Liverpool", away="Spurs"),
            _graded(-16, 1, 0, home="Liverpool", away="Everton")]
    html = bpp.render_match_page("PL", _entry(2), NOW, history=hist)
    assert "Form, last" not in html          # Liverpoolilla vain 2
    hist.append(_graded(-23, 0, 0, home="Liverpool", away="Brentford"))
    html = bpp.render_match_page("PL", _entry(2), NOW, history=hist)
    assert "Form, last 3 Premier League results" in html
    assert _form(html, "Liverpool") == "DWW" and _form(html, "Arsenal") == "WWW"


# ---------------------------------------------------------------------------
# Julkaisutarkistaja 1.11 (PR #76), korjauskierros 1
# ---------------------------------------------------------------------------
def test_form_siirretty_ottelu_ennen_tata_piilottaa_nauhan():
    """Uusintaa ei kirjata lokiin (void jaa voidiksi), joten void-rivi ennen tata
    ottelua = emme tieda puuttuuko tulos -> ei nauhaa (fail-closed).
    Tuotannon tapaus: Athletic W D D D W, oikea D D D L W."""
    e = _entry(2)
    hist = _historia()
    assert _form(bpp.render_match_page("PL", e, NOW, history=hist), "Arsenal") == "WWDLW"
    hist.append(dict(_entry(-20, home="Burnley", away="Arsenal"), void="POSTPONED"))
    html = bpp.render_match_page("PL", e, NOW, history=hist)
    assert "Form, last" not in html
    # Toisen joukkueen void piilottaa myos (lohko on kummallekin sama)
    hist2 = _historia() + [dict(_entry(-20, home="Liverpool", away="Everton"), void="CANCELLED")]
    assert "Form, last" not in bpp.render_match_page("PL", e, NOW, history=hist2)


def test_form_kutsupaikka_antaa_void_rivit_ika_rajaamatta():
    """`_played_by_comp` pudottaa yli 3 vrk vanhat gradaamattomat rivit, joten
    void-rivien on tultava erikseen (Feed.voided)."""
    log = {"predictions": [
        dict(_entry(-30, home="Burnley", away="Arsenal"), competition="PL", void="POSTPONED"),
        dict(_entry(2), competition="PL"),
    ]}
    feed = bpp.load_feed(log, NOW)
    assert [r["home_team"] for r in feed.voided.get("PL", [])] == ["Burnley"]
    assert all(not r.get("void") for r in feed.played.get("PL", []))
    src = Path(bpp.__file__).read_text(encoding="utf-8")
    assert "history=done + (feed.voided.get(comp) or [])" in src


def test_pelattu_sivu_ei_vaita_suosikkia_jalkikateen():
    """call_state lasketaan taman paivan marginaalilla; pelattu sivu nayttaa
    kirjatun ennusteen sellaisenaan eika korosta suosikkia."""
    e = _graded(-1, 2, 0)
    html = bpp.render_match_page("PL", e, NOW)
    assert "Logged prediction: Arsenal 62%, draw 21%, Liverpool 17%." in html
    assert "the favourite" not in _body(html)
    assert 'class="p3c fav"' not in html
    tuleva = bpp.render_match_page("PL", _entry(2), NOW)
    assert "the favourite" in _body(tuleva)        # erotteleva: ennen kickoffia suosikki nimetaan


@pytest.mark.parametrize("p", [0.465, 0.425, 0.445, 0.505])
def test_record_ja_sivu_pyoristavat_samoin_tasan_puolikkaassa(p):
    """Julkaisutarkistaja 1.11 (PR #76): record `.0f` (puoliparillinen) vs sivu
    `pct_int` (puoli ylos) -> Lincoln-Burnley 46 % recordissa, 47 % sivulla.
    Nyt molemmat pct_int. Tasan .5 -arvot ovat erottelevia (half-even != half-up)."""
    from scripts import build_fpl_page as bfp
    e = _graded(-1, 0, 1, ph=round(1 - p - 0.2, 4), pd_=0.2, pa=p)
    rec = bfp._pick_pct(e)
    page = bpp.render_match_page("PL", e, NOW)
    want = cm.pct_int(p)
    assert rec == f" &middot; {want}%", (p, rec)
    assert f"Model said Liverpool <b>{want}%</b>" in page or f"Liverpool {want}%" in page


def test_void_rivit_saavat_samat_nayttonimet_kuin_sivu():
    """Tuotannon tapaus 1.11: lokissa 'Athletic Club', sivulla 'Athletic Bilbao'.
    Ilman nimimuunnosta void-rivi ei osu sivun joukkueeseen ja vajaa nauha jaa."""
    log = {"predictions": [
        dict(_entry(-11, home="Levante UD", away="Athletic Club"), competition="PD", void="POSTPONED"),
        dict(_entry(2, home="Athletic Club", away="Real Sociedad de Fútbol"), competition="PD"),
    ]}
    feed = bpp.load_feed(log, NOW)
    page_team = feed.upcoming["PD"][0]["home_team"]
    assert page_team == "Athletic Bilbao"
    assert page_team in (feed.voided["PD"][0]["home_team"], feed.voided["PD"][0]["away_team"])
