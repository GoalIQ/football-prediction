# -*- coding: utf-8 -*-
"""Minuuttiperustan lippu on SAMA kortilla ja sivulla.

🔴 MITATTU 12.9.2026, GW4-deadlinekorttia tehdessa, ENNEN postausta.
Ilmaissivun `/fpl/expected-points#gw-xp` rivi 10 oli `Isak !` (694 minuuttia
viime kaudella -> minuuttiarvio nojaa lyhyeen otokseen), mutta
`gen_share_card.py xp` -kortin rivi 10 oli pelkka `Isak`. Sama pelaaja, sama
sija, kaksi eri lupausta varmuudesta - ja kortti on se joka leviaa ilman sivua
ymparillaan.

Sama vikaluokka on osunut kolmesti: 25.8 GW2-kortin `COV*`, 5.9 lippu ilman
legendaa kolmella taululla, ja `BASELINE-MERKINTA-VAIN-MOBIILISSA`. Joka
kerta lipun EHTO oli kirjoitettu uudelleen jokaiselle pinnalle.

CLAUDE.md 6a: ehto tulee nyt yhdesta lukijasta (`src.models.fpl_minutes_flags`)
ja tama portti mittaa etta molemmat pinnat kayttavat sita - myos synteettisilla
syotteilla, jotta portti ei ole vihrea vain siksi etta tama kausi sattuu
nayttamaan oikealta.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.models.fpl_minutes_flags import (  # noqa: E402
    NO_HISTORY, SHORT_BASIS, flag_symbol, legend_parts)

ART = ROOT / "data" / "fpl_xp_projections.json"


# --------------------------------------------------------------------------
# 1. Jaettu lukija: EHTO synteettisilla syotteilla, ei taman paivan datalla
# --------------------------------------------------------------------------

@pytest.mark.parametrize("p,odotus", [
    ({"data_basis": "pl_history"}, ""),
    ({"data_basis": "pl_history", "minutes_basis_flag": None}, ""),
    ({"data_basis": "limited_history"}, ""),
    ({"data_basis": "no_history"}, NO_HISTORY),
    ({"data_basis": "pl_history", "minutes_basis_flag": "short_season"}, SHORT_BASIS),
    ({"data_basis": "pl_history", "minutes_basis_flag": "new_club"}, SHORT_BASIS),
    # Molemmat: puuttuva otos voittaa lyhyen otoksen.
    ({"data_basis": "no_history", "minutes_basis_flag": "short_season"}, NO_HISTORY),
    ({}, ""),
])
def test_flag_symbol_ehto(p, odotus):
    assert flag_symbol(p) == odotus


def test_legend_vain_niille_merkeille_jotka_taulussa_on():
    assert legend_parts([{"data_basis": "pl_history"}]) == []
    vain_huuto = legend_parts([{"minutes_basis_flag": "new_club"}])
    assert len(vain_huuto) == 1 and vain_huuto[0].startswith("!")
    vain_kysymys = legend_parts([{"data_basis": "no_history"}])
    assert len(vain_kysymys) == 1 and vain_kysymys[0].startswith("?")
    molemmat = legend_parts([{"minutes_basis_flag": "short_season"},
                             {"data_basis": "no_history"}])
    assert [s[0] for s in molemmat] == ["!", "?"]


# --------------------------------------------------------------------------
# 2. Molemmat pinnat lukevat saman ehdon
# --------------------------------------------------------------------------

def test_sivun_lippu_seuraa_jaettua_lukijaa():
    from scripts.build_fpl_longtail import _no_history_flag
    for p, on_lippu in [
        ({"data_basis": "pl_history"}, False),
        ({"data_basis": "no_history"}, True),
        ({"data_basis": "pl_history", "minutes_basis_flag": "short_season",
          "last_season": {"minutes": 694}}, True),
        ({"data_basis": "pl_history", "minutes_basis_flag": "new_club",
          "last_season": {"minutes": 3085, "team_name": "Wolves"}}, True),
    ]:
        html = _no_history_flag(p)
        assert bool(html) is on_lippu, (p, html)
        assert bool(flag_symbol(p)) is on_lippu
        if html:
            assert flag_symbol(p) in html


@pytest.mark.skipif(not ART.is_file(), reason="artefaktia ei ole tassa ymparistossa")
def test_kortin_ja_sivun_lippu_tasmaa_tuotantodatalla():
    """Sama rivijoukko, sama lippu. Jos kortti pudottaa lipun, tama kaatuu."""
    from scripts.build_fpl_longtail import _no_history_flag
    from scripts.publish_gate import load_blocklist
    from src.models.fpl_gw_xp import free_rows
    data = json.loads(ART.read_text(encoding="utf-8"))
    gw, free = free_rows(data, load_blocklist())
    if gw is None:
        pytest.skip("kierrosta ei voi paatella")
    import scripts.gen_share_card as G

    class A:
        top = 10
    spec = G.card_xp(A())
    assert len(spec["rows"]) == 10
    for rivi, p in zip(spec["rows"], free[:10]):
        assert rivi["name"] == p["web_name"]
        kortti = "".join(rivi.get("badges") or [])
        sivu = flag_symbol(p)
        assert kortti == sivu, (
            f"{p['web_name']}: kortti {kortti!r} vs jaettu lukija {sivu!r}")
        # ...ja sivun oma renderoija on samaa mielta.
        assert bool(_no_history_flag(p)) is bool(sivu)


@pytest.mark.skipif(not ART.is_file(), reason="artefaktia ei ole tassa ymparistossa")
def test_lippu_kortilla_tuo_aina_selitteen():
    """Merkki ilman lukutapaa on merkki jolle ei ole selitysta (portti 5.9)."""
    import scripts.gen_share_card as G

    class A:
        top = 10
    spec = G.card_xp(A())
    merkit = {b for r in spec["rows"] for b in (r.get("badges") or [])}
    for m in merkit:
        assert m in spec["footNote"], (m, spec["footNote"])
    if not merkit:
        assert "Same row on the page" in spec["footNote"]


# --------------------------------------------------------------------------
# 3. Alatunniste ei saa vuotaa kortin reunan yli HILJAA
# --------------------------------------------------------------------------

def test_liian_pitka_alatunniste_kaataa_ajon():
    """MUTAATIO: aiemmin `_shrink` piirsi ylipitkan tekstin reunan yli.

    Mitattu 12.9: lipun pitka selite venytti alatunnisteen 1 176 px:iin
    960 px:n tilassa ja kortin AINOA tarkistusreitti (URL) leikkautui kesken.
    """
    import scripts.gen_share_card as G
    d = ImageDraw.Draw(Image.new("RGB", (G.W, 120)))
    with pytest.raises(SystemExit) as e:
        G._shrink(d, "x" * 400, 17, 200, 11, G.FONT_MED)
    assert "ei mahdu" in str(e.value)


def test_mahtuva_teksti_ei_kaada():
    """KONTROLLI: portti ei saa kaatua kaikesta (muisti: kontrolli-lapaisi-tyhjana)."""
    import scripts.gen_share_card as G
    d = ImageDraw.Draw(Image.new("RGB", (G.W, 120)))
    f = G._shrink(d, "lyhyt", 17, 900, 11, G.FONT_MED)
    assert f.size == 17


@pytest.mark.skipif(not ART.is_file(), reason="artefaktia ei ole tassa ymparistossa")
def test_xp_kortin_molemmat_alatunnisterivit_mahtuvat():
    """Tuotantoteksti mitataan samalla funktiolla kuin piirto."""
    import scripts.gen_share_card as G

    class A:
        top = 10
    spec = G.card_xp(A())
    d = ImageDraw.Draw(Image.new("RGB", (G.W, 120)))
    handle_w = d.textlength("@goaliqapp", font=G._font(G.FONT_BOLD, 20))
    G._shrink(d, spec["footNote"], 20, G.W - G.MX - handle_w - 24 - G.MX, 13, G.FONT_MED)
    G._shrink(d, spec["footNote2"], 17, G.W - 2 * G.MX, 11, G.FONT_MED)
