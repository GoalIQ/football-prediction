"""Fast-lane-portti (scripts/check_reply_numbers.py): erottelevat fikstuurit.

Jokainen rikottu muunnelma rikkoo TASAN YHDEN tarkistuksen ja jattaa muut
vihreiksi. Muuten testi joka "kaatuu" voisi kaatua vaarasta syysta, ja
tarkistus jonka se vaittaa vartioivansa olisi vartioimatta (muisti:
exit-koodi-ei-ole-todiste-mekanismista).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from scripts import check_reply_numbers as C
from src.marketing.reply_module import ReplyModuleRefused

NOW = datetime(2026, 9, 22, 9, 0, tzinfo=timezone.utc)
URL_CS = "https://goaliq.app/fpl#clean-sheets"
URL_XP = "https://goaliq.app/fpl/expected-points#gw-xp"
URL_TOP = "https://goaliq.app/fpl/expected-points#top-100"

GOOD = """
kohde:      https://x.com/OfficialFPL/status/111
tekija:     @OfficialFPL · 6 820 305 · tier 1
julkaistu:  2026-09-22T08:50Z · ika 10 (raja 240)
luonnos:    Arsenal at home to Leeds for GW6, 46.5% clean sheet chance. Haaland 5.5 and 14% for 10+.
liite:      ei
luvut:      cs_top.ars.cs_pct = 46.5% · captain_top5.haaland-mci.gw_xp = 5.5 · player_lookup.haaland-mci.p_10plus = 14%
tarkistus:  https://goaliq.app/fpl#clean-sheets https://goaliq.app/fpl/expected-points#gw-xp https://goaliq.app/fpl/expected-points#top-100 · moduuli gw6
CTA:        ei linkkia
"""


def _v(text, url, check):
    return {"text": text, "public_url": url, "check": check, "verified_at": "x"}


MODULE = {
    "gw": 6,
    "sections": {
        "cs_top": {"rows": [{"key": "ars", "values": {
            "cs_pct": _v("46.5%", URL_CS, ["clean_sheets", ["Arsenal"]])}}]},
        "captain_top5": {"rows": [{"key": "haaland-mci", "values": {
            "gw_xp": _v("5.5", URL_XP, ["gw_xp", ["Haaland", "MCI"]])}}]},
        "player_lookup": {"rows": [{"key": "haaland-mci", "values": {
            "p_10plus": _v("14%", URL_TOP, ["top100", ["Haaland", "MCI"]]),
            "xp_6gw": {"text": "39.1", "public_url": None, "verified_at": None}}}]},
    },
}

PAGES = {
    "clean_sheets": {"url": URL_CS, "gw": 6, "rows": {"Arsenal": {"cs_pct": "46.5%"}}},
    "gw_xp": {"url": URL_XP, "gw": 6, "rows": {("Haaland", "MCI"): {"gw_xp": "5.5"}}},
    "top100": {"url": URL_TOP, "gw": 6, "rows": {("Haaland", "MCI"): {"p_10plus": "14%"}}},
}


def _run(text, *, module=MODULE, pages=PAGES, refuse=None, now=NOW):
    def loader(gw, keys):
        if refuse:
            raise ReplyModuleRefused(refuse)
        assert gw == module["gw"]
        from src.marketing.reply_module import _select
        chosen, _k = _select(module, None, keys)
        return {"gw": gw, "sections": chosen}

    checks = C.check_draft(text, now=now, loader=loader,
                           surfaces=lambda needed, gw: (pages, {}, []),
                           blocklist=C.load_blocklist())
    return {c.name.split()[0]: c for c in checks}


def _only_fails(res, which: str):
    failed = {k for k, c in res.items() if not c.ok}
    assert failed == {which}, {k: c.detail for k, c in res.items()}


def test_good_draft_passes_all_five():
    res = _run(GOOD)
    assert all(c.ok for c in res.values()), {k: c.detail for k, c in res.items()}
    assert len(res) == 5


@pytest.mark.parametrize("old,new", [
    ("46.5% clean sheet", "47% clean sheet"),        # numero jota ei ole luvut-rivilla
    ("for GW6,", "for GW7,"),                         # vaara kierrostunnus
])
def test_check1_number_not_on_luvut_line(old, new):
    _only_fails(_run(GOOD.replace(old, new)), "1")


def test_check1_ten_plus_needs_the_probability_on_luvut():
    t = GOOD.replace(" · player_lookup.haaland-mci.p_10plus = 14%", "") \
            .replace(" and 14% for 10+.", " and a 10+ ceiling.") \
            .replace(" https://goaliq.app/fpl/expected-points#top-100", "")
    _only_fails(_run(t), "1")


def test_check2_value_differs_from_module():
    t = GOOD.replace("gw_xp = 5.5", "gw_xp = 5.6").replace("Haaland 5.5", "Haaland 5.6")
    _only_fails(_run(t), "2")


def test_check2_number_without_free_route_is_rejected():
    t = GOOD.replace("gw_xp = 5.5", "gw_xp = 5.5 · player_lookup.haaland-mci.xp_6gw = 39.1") \
            .replace("Haaland 5.5", "Haaland 5.5 (39.1 over six)")
    res = _run(t)
    _only_fails(res, "2")
    assert "public_url null" in res["2"].detail


def test_check2_page_changed_since_module_was_built():
    pages = dict(PAGES)
    pages["clean_sheets"] = {"url": URL_CS, "gw": 6, "rows": {"Arsenal": {"cs_pct": "44.9%"}}}
    res = _run(GOOD, pages=pages)
    _only_fails(res, "2")
    assert "44.9" in res["2"].detail


def test_check2_module_refusal_blocks():
    res = _run(GOOD, refuse="GW6 deadline passed")
    _only_fails(res, "2")


def test_check2_tarkistus_must_name_the_route():
    t = GOOD.replace("https://goaliq.app/fpl#clean-sheets ", "")
    _only_fails(_run(t), "2")


def test_check3_target_older_than_240_minutes():
    _only_fails(_run(GOOD.replace("2026-09-22T08:50Z", "2026-09-22T04:59Z")), "3")
    # 239 min: lapi
    res = _run(GOOD.replace("2026-09-22T08:50Z", "2026-09-22T05:01Z"))
    assert res["3"].ok


def test_check3_time_without_zone_is_rejected():
    _only_fails(_run(GOOD.replace("2026-09-22T08:50Z", "2026-09-22T08:50")), "3")


@pytest.mark.parametrize("handle", ["FFScout", "FPL_Harry", "fplreview", "LetsTalk_FPL"])
def test_check4_blocked_target_account(handle):
    t = GOOD.replace("x.com/OfficialFPL/", f"x.com/{handle}/").replace("@OfficialFPL", f"@{handle}")
    _only_fails(_run(t), "4")


@pytest.mark.parametrize("extra", [" goaliq.app/fpl", " https://t.co/abc", " GoalIQ has it"])
def test_check5_no_link_or_product_name(extra):
    t = GOOD.replace("for 10+.", "for 10+." + extra)
    _only_fails(_run(t), "5")


def test_numberless_human_reply_passes_without_module():
    t = """
kohde:      https://x.com/OfficialFPL/status/111
tekija:     @OfficialFPL
julkaistu:  2026-09-22T08:58Z
luonnos:    Already have him
luvut:
tarkistus:  ei lukuja
"""
    res = _run(t, refuse="should not be called")
    assert all(c.ok for c in res.values()), {k: c.detail for k, c in res.items()}


def test_blocklist_covers_every_c2_no_and_grey_row():
    """C2:n EI- ja HARMAA-rivit (c1-c2-x-tutkimus.md 22.9) ovat kaikki listalla."""
    bl = C.load_blocklist()
    c2 = ["FFScout", "FFH_HQ", "FantasyFootyFix", "FPLFocal", "LiveFPLnet", "FplMode",
          "FPLJoeYT", "FPL_Spaceman", "robtFPL", "LetsTalk_FPL", "FPL_Harry", "FPLOlympian",
          "FPLGeneral", "FPL__Raptor", "BigManBakar", "FPLMate", "FPL_Salah", "FplToni",
          "FPL_Heisenberg", "FPLMattW", "FPLKarim_", "fpl_phenom", "allaboutfpl",
          "greekgodFpl", "FPLTom_", "FPL_Armo"]
    missing = [h for h in c2 if h.lower() not in bl]
    assert not missing, missing
    for a in bl.values():
        assert a["line"] in ("EI", "HARMAA") and a["reason"].strip()
