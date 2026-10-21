"""Automaattinen kierrosrecap (/fpl/notes): vaihetesti.

Ennen gradausta ei muistiota, provisional ei muistiota, gradattu tasan yksi,
toinen ajo ei tuplaa. Testi kaatuu, jos gradausehto poistetaan.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_fpl_longtail import note_plain_text, render_notes  # noqa: E402
from scripts.build_fpl_recap_note import add_recaps, build_note, slug_for  # noqa: E402

TODAY = date(2026, 10, 19)


def _gw(gw: int = 6, provisional: bool = False, graded: bool = True) -> dict:
    return {
        "gw": gw,
        "provisional": provisional,
        "squad": {"points": 57, "average": 58, "graded_at": "2026-10-13T19:00:20Z"},
        "calls": {
            "graded": graded,
            "provisional": False,
            "calls": [
                {"call": "safest", "web_name": "Haaland", "points": 6,
                 "criterion": "3+ pts", "met": True},
                {"call": "captain_pick", "web_name": "Fernandes", "points": 1,
                 "criterion": "10+ pts", "met": False},
            ],
        },
    }


def _recap(*gws: dict) -> dict:
    per_gw = [{"gw": g["gw"], "diff": g["squad"]["points"] - g["squad"]["average"]}
              for g in gws if g["squad"].get("points") is not None]
    return {"gameweeks": list(gws), "running": {"per_gw": per_gw}}


def _acc(gw: int = 6) -> dict:
    return {"gameweeks": [{"gw": gw, "comparison": {
        "n": 483,
        "mae": {"goaliq": 1.612, "fpl_ep_next": 1.626, "form_baseline": 1.644},
    }}]}


def test_gradattu_kierros_tuottaa_tasan_yhden_muistion():
    doc = {"notes": []}
    added = add_recaps(doc, _recap(_gw()), _acc(), TODAY)
    assert added == [slug_for(6)]
    assert len(doc["notes"]) == 1


def test_toinen_ajo_ei_tuplaa():
    doc = {"notes": []}
    recap = _recap(_gw())
    add_recaps(doc, recap, _acc(), TODAY)
    assert add_recaps(doc, recap, _acc(), TODAY) == []
    assert len(doc["notes"]) == 1


def test_provisional_kierros_ei_tuota_muistiota():
    doc = {"notes": []}
    assert add_recaps(doc, _recap(_gw(provisional=True)), _acc(), TODAY) == []
    assert doc["notes"] == []


def test_ennen_gradausta_ei_muistiota():
    doc = {"notes": []}
    assert add_recaps(doc, _recap(_gw(graded=False)), _acc(), TODAY) == []
    ei_pisteita = _gw()
    ei_pisteita["squad"] = {"points": None, "average": None}
    assert add_recaps(doc, _recap(ei_pisteita), _acc(), TODAY) == []
    assert doc["notes"] == []


def test_kutsujen_provisional_ei_tuota_muistiota():
    g = _gw()
    g["calls"]["provisional"] = True
    assert build_note(g, _recap(g), _acc(), TODAY) is None


def test_jokainen_claim_on_tekstissa_ja_kentat_ovat_olemassa():
    n = build_note(_gw(), _recap(_gw()), _acc(), TODAY)
    assert n["check_url"] and n["cta"] and len(n["claims"]) >= 3
    teksti = note_plain_text(n)
    assert [c for c in n["claims"] if c not in teksti] == []
    for luku in ("1.61", "1.63", "1.64"):
        assert luku in n["claims"]


def test_tappio_ja_huti_kerrotaan_voiton_rinnalla():
    teksti = note_plain_text(build_note(_gw(), _recap(_gw()), _acc(), TODAY))
    assert "FPL average" not in teksti and "model squad" not in teksti
    assert "across" not in teksti and "1.612" not in teksti
    assert "Hit:" in teksti and "Missed:" in teksti


def test_pohjat_vaihtuvat_kierroksen_mukaan_eika_sisalla_em_dashia():
    rungot = set()
    for gw in (3, 4, 5):
        g = _gw(gw)
        n = build_note(g, _recap(g), _acc(gw), TODAY)
        assert "—" not in note_plain_text(n) + n["title"]
        rungot.add(n["paragraphs"][0][:20])
    assert len(rungot) == 3


def test_kutsuluku_koskee_picks_ei_taulukon_rivimaaraa():
    for gw in (3, 4, 5):
        g = _gw(gw)
        teksti = note_plain_text(build_note(g, _recap(g), _acc(gw), TODAY))
        assert "graded rows" not in teksti and "graded calls" not in teksti
        assert "picks" in teksti.lower()


def test_ilman_tarkkuusdataa_muistio_syntyy_ilman_keksittya_lukua():
    g = _gw()
    g["calls"]["calls"].append({"call": "ceiling", "web_name": "Salah",
                                "points": 9, "criterion": "8+ pts", "met": True})
    n = build_note(g, _recap(g), {"gameweeks": []}, TODAY)
    assert n is not None
    assert "ep_next" not in note_plain_text(n)
    # kahdella kutsun luvulla ilman tarkkuutta ei synny muistiota (alle 3 claimia)
    assert build_note(_gw(), _recap(_gw()), {"gameweeks": []}, TODAY) is None


def test_muistio_renderoituu_notes_sivulle():
    n = build_note(_gw(), _recap(_gw()), _acc(), TODAY)
    html = render_notes({"notes": [n]}, TODAY_DT)
    assert html and 'id="recap-gw6"' in html


from datetime import datetime, timezone  # noqa: E402

TODAY_DT = datetime(2026, 10, 19, tzinfo=timezone.utc)


def test_tasatilanne_pyoristetyissa_luvuissa_ei_vaita_johtoa():
    acc = _acc()
    acc["gameweeks"][0]["comparison"]["mae"] = {
        "goaliq": 1.614, "fpl_ep_next": 1.606, "form_baseline": 1.644}
    teksti = note_plain_text(build_note(_gw(), _recap(_gw()), acc, TODAY))
    assert "closest" not in teksti and "level with" in teksti
