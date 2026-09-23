"""KORTTI-SIMS-YLIVUOTO (23.9.2026): mallin jakokortti mahtuu 1200x675:een
myos sims-tilassa, penkin ja alatunnisteen kanssa.

Julkaisutarkistajan stressirenderointi 23.9: `--sims` vei penkin ja
alatunnisteen GitHub-reitin (kortin tarkistusreitin) kuvan alapuolelle jo
ilman saatavuusmerkkeja. Kortti kuvattiin suoraan Chromella, joten ylivuoto
paatyi PNG:hen hiljaa.

Mekanismit (CLAUDE.md 6a):
  (1) yksi kuvauspolku: kortti kulkee `card_shot.render_card`in lapi, joka
      mittaa asettelun ennen kuvausta ja kieltaytyy kirjoittamasta PNG:ta.
      Kutsupaikka tarkistetaan AST:lla (muisti testi-kutsuu-funktiota-ei-
      kutsupaikkaa), jottei suora `--screenshot` palaa hiljaa.
  (2) upotetut fontit: asettelu ei riipu koneen fonteista (Segoe UI vs
      DejaVu), joten Windowsilla mitattu mahtuminen patee CI:n Linuxilla.
  (3) pahin tapaus mitataan kummassakin tilassa: pisimmat nimet, kallein
      hinta, jokaisella pelaajalla lippu, penkki mukana.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import card_shot as C  # noqa: E402
from scripts import render_frozen_squad_card as card  # noqa: E402

SRC = (ROOT / "scripts" / "render_frozen_squad_card.py").read_text(encoding="utf-8")
CHROME = C.find_chrome()
tarvitsee_chromen = pytest.mark.skipif(CHROME is None, reason="Chromea ei loydy")

PITKAT = ["Alexander-Arnold", "Calvert-Lewin", "Dewsbury-Hall", "Gibbs-White",
          "Mac Allister", "Szoboszlai", "Hudson-Odoi", "Thomas-Asante",
          "George Hemmings", "Ait-Nouri", "Schade-Ferreira", "Sarabia-Garcia",
          "Kristensen-Holm", "Rodrigo Muniz", "Dominguez-Lopez"]
LIPUT = [("d", 75), ("d", 50), ("d", 25), ("u", 0), ("d", None), ("i", 0)]


def _pahin_runko(muoto=(5, 4, 1), chip=None) -> dict:
    """15 pelaajaa, jokaisella lippu ja pitka nimi. 5 puolustajan rivi on
    levein mahdollinen, 12.5m pisin hintateksti."""
    pos = [1] + [2] * muoto[0] + [3] * muoto[1] + [4] * muoto[2]
    assert len(pos) == 11
    bench_pos = [1, 2, 3, 4]

    def pelaaja(i, p):
        st, ch = LIPUT[i % len(LIPUT)]
        return {"id": 100 + i, "web_name": PITKAT[i], "team_short": "WOL",
                "pos": p, "price": 125, "status": st, "chance": ch}
    xi = [pelaaja(i, p) for i, p in enumerate(pos)]
    bench = [pelaaja(11 + i, p) for i, p in enumerate(bench_pos)]
    # Kapteeni hyokkaysrivin ensimmaisena ja varakapteeni keskikentan
    # ensimmaisena: 4-3-3:ssa molemmat ovat suoraan ylemman rivin pelaajan
    # alla, jolloin merkki osuu ylemman solun sims-riviin jos se nousee
    # solunsa ylapuolelle (23.9: C peitti B.Fernandesin 'blank 9%').
    return {"xi": xi, "bench": bench, "captain": xi[11 - muoto[2]]["id"],
            "vice_captain": xi[1 + muoto[0]]["id"],
            "meta": {"gw": 6, "frozen_at": "2026-10-09T05:00:00Z", "chip": chip,
                     "selling_value_tenths": 1004, "bank_tenths": 123}}


def _sims(frozen: dict) -> tuple[dict, dict]:
    dists = {p["id"]: {"gw": 6, "p_haul": 0.21, "p_blank": 0.09}
             for p in frozen["xi"]}
    xps = {p["id"]: 10.4 for p in frozen["xi"]}
    return dists, xps


def _kuvaa(tmp_path, frozen, sims: bool, **kw) -> dict:
    dists, xps = _sims(frozen) if sims else ({}, {})
    html = card.build_html(frozen, 6, sims=sims, dists=dists, xps=xps, **kw)
    hp = tmp_path / "kortti.html"
    hp.write_text(C.with_fonts(html), encoding="utf-8")
    return C.render_card(CHROME, hp, tmp_path / "kortti.png")


# ---------------------------------------------------------------- Chromella
@tarvitsee_chromen
@pytest.mark.parametrize("sims", [True, False])
@pytest.mark.parametrize("muoto", [(5, 4, 1), (3, 5, 2), (4, 3, 3)])
def test_pahin_kortti_mahtuu_penkin_ja_reitin_kanssa(tmp_path, sims, muoto):
    rep = _kuvaa(tmp_path, _pahin_runko(muoto), sims)
    assert (tmp_path / "kortti.png").stat().st_size > 1000
    assert rep["card"] == [1200, 675] and not rep["outside"]


@tarvitsee_chromen
def test_triple_captain_merkki_mahtuu_simsissa(tmp_path):
    _kuvaa(tmp_path, _pahin_runko(chip="3xc"), True)


@tarvitsee_chromen
def test_vanha_paitakoko_ei_paady_kuvaksi(tmp_path, monkeypatch):
    """Erotteleva: 23.9:n asettelu (46/42 px paidat sims-tilassa) valuu yli,
    ja portti kieltaytyy. Jos tama menee lapi, portti ei mittaa korkeutta."""
    monkeypatch.setitem(card.KIT, True, card.KIT[False])
    png = tmp_path / "kortti.png"
    png.write_bytes(b"vanha")
    with pytest.raises(C.CardLayoutError, match="valuu yli"):
        _kuvaa(tmp_path, _pahin_runko(), True)
    assert not png.exists()


# ---------------------------------------------------------------- kutsupaikka
def _main() -> ast.FunctionDef:
    return next(n for n in ast.parse(SRC).body
                if isinstance(n, ast.FunctionDef) and n.name == "main")


def test_main_kuvaa_vain_render_cardin_kautta():
    """Suora Chrome-kuvaus ohittaisi mittauksen (23.9:n vika)."""
    kutsut = {ast.unparse(n.func) for n in ast.walk(_main())
              if isinstance(n, ast.Call)}
    assert "render_card" in kutsut and "with_fonts" in kutsut
    assert "--screenshot" not in SRC and "subprocess" not in SRC


def test_main_valittaa_tilan_build_htmlille():
    kutsu = next(n for n in ast.walk(_main()) if isinstance(n, ast.Call)
                 and ast.unparse(n.func) == "build_html")
    kw = {k.arg: ast.unparse(k.value) for k in kutsu.keywords}
    assert kw == {"sims": "args.sims", "dists": "dists", "xps": "xps",
                  "hide_bench": "args.hide_bench",
                  "subtitle_override": "args.subtitle"}


def test_asetteluvirhe_on_exit_1():
    """CardLayoutError ei saa muuttua exit 0:ksi (kortti puuttuisi hiljaa)."""
    h = next(n for n in ast.walk(_main()) if isinstance(n, ast.ExceptHandler)
             and ast.unparse(n.type) == "CardLayoutError")
    assert any(isinstance(s, ast.Return) and ast.unparse(s.value) == "1"
               for s in h.body)


# ---------------------------------------------------------------- merkki
def _saanto(valitsin: str) -> str:
    m = re.search(re.escape(valitsin) + r"\{([^}]*)\}", card.CSS)
    assert m, valitsin
    return m.group(1)


def test_lippu_erottuu_sims_rivista():
    """Tarkistaja 23.9: FPL:n '75%' (#F5A142) ja sims-rivin '10+ N%'
    (#F5C542) erottuivat vain lahes samalla savylla. Lippu on nyt taytetty
    merkki tummalla tekstilla: ero on muodossa, ei savyssa."""
    sim = _saanto(".xip span.sim")
    sim_vari = re.search(r"color:([^;]+)", sim).group(1)
    assert "background" not in sim
    assert "color:var(--ink)" in _saanto(".xip span em.flag")
    for luokka in ("d", "out"):
        tausta = re.search(r"background:([^;]+)",
                           _saanto(f".xip span em.flag.{luokka}")).group(1)
        assert tausta.lower() not in (sim_vari.lower(), "#f5c542",
                                      "var(--amber)")
