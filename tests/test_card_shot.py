"""Portti: jakokortin asettelu ei riipu koneen fonteista, ja rikkinainen
asettelu ei paady kuvaksi (scripts/card_shot.py, 22.9.2026).

Tausta ja mittaukset: scripts/card_shot.py:n docstring. Lyhyesti: kortit
renderoitiin vain Windowsilla Segoe UI:lla; ubuntu-runnerilla sama HTML
piirtyi DejaVu Sansilla ja tarkistusreitti katkesi tai valui kuvan ulkopuolelle.
Projected-XI-kortin reitti valui ulos jo Windowsilla (1 346 px / 1 200 px).

Chromea vaativat testit ajetaan kun Chrome loytyy (ubuntu-latest: on), eli
tests.yml mittaa saman asettelun LINUXILLA jokaisella pushilla - se on
Linux-vastaavuuden todiste, jota Windows-kone ei voi antaa.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import pytest

from scripts import card_shot as C

ROOT = Path(__file__).resolve().parent.parent
RENDEROIJAT = ["scripts/render_standouts_card.py",
               "scripts/render_projected_xi_card.py",
               "scripts/render_frozen_squad_card.py"]


def test_upotetut_fontit_ja_lisenssi_ovat_repossa():
    for family, stem, weight in C.FACES:
        for subset in C.SUBSETS:
            f = C.FONT_DIR / f"{stem}-{subset}-{weight}-normal.woff2"
            assert f.exists() and f.stat().st_size > 5000, f
    # OFL 1.1 edellyttaa lisenssin fonttien mukana.
    assert "SIL Open Font License" in (C.FONT_DIR / "OFL.txt").read_text(
        encoding="utf-8")


@pytest.mark.parametrize("polku", RENDEROIJAT)
def test_kortin_tekstifontti_on_upotettu_ei_koneen(polku):
    """Jokainen font-family kortin CSS:ssa alkaa upotetulla perheella.
    'Segoe UI' tai system-ui ensimmaisena = asettelu riippuu koneesta."""
    src = (ROOT / polku).read_text(encoding="utf-8")
    css = re.search(r'CSS = """(.*?)"""', src, re.S).group(1)
    perheet = re.findall(r"font-family:\s*([^;}]+)", css)
    assert perheet, "CSS:sta ei loytynyt font-familya - portti mittaisi tyhjaa"
    upotetut = {f for f, _, _ in C.FACES}
    for p in perheet:
        eka = p.split(",")[0].strip().strip("'\"")
        assert eka in upotetut, (polku, p)
    assert "Segoe UI" not in css


def test_nykyiset_pelaajanimet_kuuluvat_upotettuihin_fontteihin():
    d = json.loads((ROOT / "data" / "fpl_xp_projections.json").read_text(
        encoding="utf-8"))
    teksti = " ".join(str(p.get(k) or "") for p in
                      d.get("players", []) + d.get("excluded", [])
                      for k in ("web_name", "team_short"))
    assert len(teksti) > 1000, "tyhja nimilista - portti mittaisi tyhjaa"
    assert C.uncovered_chars(teksti) == []


def test_negatiivinen_kontrolli_kattamaton_merkki_loytyy():
    assert C.uncovered_chars("Horníček Šeško Ødegaard") == []
    assert C.uncovered_chars("Ωmega Ж") == ["Ω", "Ж"]


def test_fontit_upotetaan_vain_kuvattavaan_tiedostoon():
    """Tekstiportit (publish_gate, BANNED_COPY) skannaavat build_htmlin
    tuloksen. Base64-fonttidata siella voisi osua sattumalta sanaan
    (\\bPro\\b, estolistan nimi) ja kaataa kortin syytta."""
    html = "<!doctype html><style>.card{}</style><div class='card'>x</div>"
    ulos = C.with_fonts(html)
    assert "base64" not in html and ulos.count("@font-face") == 10
    with pytest.raises(ValueError):
        C.with_fonts("<div>ei tyylia</div>")


def test_ongelmien_luokittelu():
    hyva = {"outside": [], "overlap": [], "clipped": [], "ellipsis": ["td.nm x"],
            "fonts": [], "card": [1200, 675]}
    assert C.problems(hyva) == [], "ellipsi on suunniteltu katkaisu"
    for avain in ("outside", "overlap", "clipped", "fonts"):
        paha = dict(hyva, **{avain: ["span x"]})
        assert C.problems(paha), avain
    assert C.problems(dict(hyva, card=[1346, 675]))
    assert C.problems({"error": "ei raporttia"})
    assert C.problems(hyva, "Ω")


# ---------------------------------------------------------------------------
# Chromella mitatut (ajetaan kun Chrome loytyy; ubuntu-latest: loytyy)
# ---------------------------------------------------------------------------

CHROME = C.find_chrome()
tarvitsee_chromen = pytest.mark.skipif(CHROME is None, reason="Chromea ei loydy")

_KORTTI = ("<!doctype html><meta charset='utf-8'><style>"
           "*{margin:0;padding:0;box-sizing:border-box;}"
           ".card{width:1200px;height:675px;padding:20px 40px;"
           "font-family:'IBM Plex Sans',sans-serif;display:flex;"
           "flex-direction:column;justify-content:flex-end;background:#111;color:#eee}"
           ".ftr{display:flex;justify-content:space-between;gap:14px;"
           "white-space:nowrap;border-top:1px solid #555;font-size:13px}"
           "</style><div class='card'><div class='ftr'>{spans}</div></div>")


def _kirjoita(tmp_path, spans: str) -> Path:
    p = tmp_path / "kortti.html"
    p.write_text(C.with_fonts(_KORTTI.replace("{spans}", spans)), encoding="utf-8")
    return p


@tarvitsee_chromen
def test_ylivuotava_alapalkki_ei_paady_kuvaksi(tmp_path):
    """Tasan 22.9:n vika: kolme nowrap-spania, reitti valuu kuvan ulkopuolelle.
    Vanha PNG poistetaan, jotta julkaisu ei poimi edellista kuvaa."""
    pitka = "The model&#39;s squad is frozen before each deadline, and entry 116920 plays it with our own calls"
    html = _kirjoita(tmp_path, f"<span>{pitka}</span><span>model projections, "
                     "not betting advice · card made 22 Sep 08:23 UTC</span>"
                     "<span>projected points list: goaliq.app/fpl/expected-points#gw-xp</span>")
    png = tmp_path / "kortti.png"
    png.write_bytes(b"vanha")
    with pytest.raises(C.CardLayoutError, match="valuu yli"):
        C.render_card(CHROME, html, png)
    assert not png.exists()


@tarvitsee_chromen
def test_reunallinen_kehys_kortin_alla_ei_paady_kuvaksi(tmp_path):
    """KORTTI-SIMS-YLIVUOTO 23.9: penkki on oma reunallinen kehyksensa, joten
    sen teksti oli 'kehyksen sisalla' vaikka koko penkki oli 675 px:n alla.
    Kortin raja tarkistetaan aina, ei vain lahimman kehyksen."""
    p = tmp_path / "kortti.html"
    p.write_text(C.with_fonts(
        "<!doctype html><meta charset='utf-8'><style>*{margin:0;padding:0}"
        ".card{width:1200px;height:675px;font-family:'IBM Plex Sans',sans-serif}"
        ".tayte{height:660px}.bench{border-top:1px solid #555;height:60px}"
        "</style><div class='card'><div class='tayte'></div>"
        "<div class='bench'><b>Dovin</b></div><div>kortin alla</div></div>"),
        encoding="utf-8")
    with pytest.raises(C.CardLayoutError, match=r"valuu yli: b \"Dovin\" out of div\.card"):
        C.render_card(CHROME, p, tmp_path / "kortti.png")


@tarvitsee_chromen
def test_paallekkaiset_tekstit_eivat_paady_kuvaksi(tmp_path):
    """23.9: kapteenimerkki peitti ylemman rivin 'blank 9%' -tekstin."""
    p = tmp_path / "kortti.html"
    p.write_text(C.with_fonts(
        "<!doctype html><meta charset='utf-8'><style>*{margin:0;padding:0}"
        ".card{width:1200px;height:675px;font-family:'IBM Plex Sans',sans-serif;"
        "position:relative}.c{position:absolute;left:40px;top:34px}"
        "</style><div class='card'><div style='padding:30px 40px'>"
        "10+ 21% · blank 9%</div><span class='c'>C</span></div>"),
        encoding="utf-8")
    with pytest.raises(C.CardLayoutError, match="tekstit paallekkain"):
        C.render_card(CHROME, p, tmp_path / "kortti.png")


@tarvitsee_chromen
def test_merkin_tausta_ei_saa_peittaa_tekstia(tmp_path):
    """23.9 mitattu: C-kirjaimen ja tekstin glyfit menivat paallekkain vain
    2 px, mutta merkin ympyra peitti tekstia 4 px. Peittaja on tausta."""
    p = tmp_path / "kortti.html"
    p.write_text(C.with_fonts(
        "<!doctype html><meta charset='utf-8'><style>*{margin:0;padding:0}"
        ".card{width:1200px;height:675px;font-family:'IBM Plex Sans',sans-serif;"
        "position:relative}.t{position:absolute;left:40px;top:40px;font-size:11px}"
        ".b{position:absolute;left:60px;top:50px;width:22px;height:22px;"
        "border-radius:50%;background:#F5C542;font-size:13px;line-height:22px;"
        "text-align:center}</style><div class='card'>"
        "<span class='t'>10+ 21% · blank 9%</span><span class='b'>C</span></div>"),
        encoding="utf-8")
    with pytest.raises(C.CardLayoutError, match=r"covers span\.t"):
        C.render_card(CHROME, p, tmp_path / "kortti.png")


@tarvitsee_chromen
def test_mahtuva_alapalkki_kuvataan(tmp_path):
    html = _kirjoita(tmp_path, "<span>entry 116920</span>"
                     "<span>goaliq.app/fpl/expected-points#gw-xp</span>")
    png = tmp_path / "kortti.png"
    rep = C.render_card(CHROME, html, png)
    assert png.exists() and png.stat().st_size > 1000
    assert rep["card"] == [1200, 675] and not rep["fonts"]


def _xi_data():
    """Projected-XI-kortin syote pitkilla nimilla (pahin realistinen tapaus
    kentan 118 px:n soluille ja top-15-taulukolle)."""
    gw, clubs = 6, ["ARS", "MCI", "LIV", "CHE", "TOT", "MUN", "NEW", "AVL"]
    pitkat = ["Alexander-Arnold", "Calvert-Lewin", "Hudson-Odoi",
              "Szoboszlai", "Gibbs-White", "Thomas-Asante", "Mac Allister",
              "Dewsbury-Hall"]
    ps, pid = [], 1

    def p(name, pos, club, price, xp):
        nonlocal pid
        pid += 1
        return {"id": pid, "web_name": name, "pos": pos, "team": club,
                "team_short": club, "price": price, "status": "a",
                "xmins": 90.0, "p_start": 0.9, "owned_pct": 5.0,
                "xp_per_gw": xp, "xp_horizon_total": xp * 6,
                "gameweeks": [{"gw": gw, "xp": xp,
                               "opponents": [{"opp": "BOU", "venue": "H"}]}]}
    for i in range(3):
        ps.append(p(f"Keeper{i}", "GKP", clubs[i], 4.5, [4.0, 3.5, 1.0][i]))
    for i in range(8):
        ps.append(p(pitkat[i], "DEF", clubs[i], 5.0, 4.6 - i * 0.3))
    for i in range(8):
        ps.append(p(pitkat[(i + 3) % 8] + "s", "MID", clubs[(i + 3) % 8], 6.0, 5.5 - i * 0.3))
    for i in range(5):
        ps.append(p(f"Striker{i}", "FWD", clubs[(i + 5) % 8], 6.5, 5.2 - i * 0.4))
    dl = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=3)).isoformat()
    return {"meta": {"deadline_gameweek": gw, "next_gameweek": gw, "available": True,
                     "deadline_utc": dl,
                     # oma generated_at: free_optimumin valimuisti avaintaa
                     # sen mukaan, eika fikstuuri saa osua oikean datan XI:hin
                     "generated_at": "2000-01-01T00:00:00+00:00"},
            "players": ps}


@tarvitsee_chromen
def test_projected_xi_pohja_renderoituu_ehjana_pitkilla_nimilla(tmp_path):
    """Oikea pohja, upotetut fontit, pitkat nimet: ei ylivuotoa. tests.yml
    ajaa taman ubuntu-runnerilla, eli sama asettelu mitataan Linuxilla."""
    from scripts.render_projected_xi_card import build_html
    html, _ = build_html(_xi_data(), log=None, blocklist=[])
    p = tmp_path / "xi.html"
    p.write_text(C.with_fonts(html), encoding="utf-8")
    C.render_card(CHROME, p, tmp_path / "xi.png")
    assert (tmp_path / "xi.png").exists()


def test_sisaltotiiviste_ohittaa_aikaleimat_mutta_ei_lukuja():
    a = "<div class='card'>GW6 · projection run 22 Sep 08:07 UTC <b>21%</b></div>"
    b = "<div class='card'>GW6 · projection run 22 Sep 11:07 UTC <b>21%</b></div>"
    c = "<div class='card'>GW6 · projection run 22 Sep 08:07 UTC <b>20%</b></div>"
    d1 = a.replace("GW6 ·", "GW6 · card made 22 Sep 08:44 UTC ·")
    d2 = a.replace("GW6 ·", "GW6 · card made 23 Sep 11:44 UTC ·")
    assert C.content_signature(a) == C.content_signature(b)
    assert C.content_signature(d1) == C.content_signature(d2)
    assert C.content_signature(a) != C.content_signature(c)
    # Deadline on sisaltoa (vaihtuu kierroksen mukana), ei aikaleima.
    e = "<div class='card'>GW6 deadline Sat 10 Oct 10:00 UTC</div>"
    f = "<div class='card'>GW6 deadline Sat 17 Oct 10:00 UTC</div>"
    assert C.content_signature(e) != C.content_signature(f)
    # Tyyli ei ole sisaltoa.
    g = "<style>.x{color:red}</style>" + a
    assert C.content_signature(g) == C.content_signature(a)
