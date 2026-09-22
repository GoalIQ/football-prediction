"""Reply-kortit (gen_share_card: reply-cs, reply-xp, captain-compare,
model-vs-template): kortin luku = moduulin teksti, lappu samasta parista.

Muisti jakokortin-arvo-seuraa-sorttia: arvo ja nimilappu tulevat SAMASTA
lukijasta. Tassa pari on `REPLY_FIELDS[card] = (osio, kentta, lappu)`, ja
testi rakentaa moduulin jossa kentilla on eri tekstit: jos kortti lukisi
vaaran kentan, luku ei tasmaisi.
"""
from __future__ import annotations

import pytest

import scripts.gen_share_card as g


def _v(text, url="https://goaliq.app/x"):
    return {"text": text, "public_url": url, "verified_at": "t"}


def _module():
    rows_xp = [{"key": f"p{i}-ars", "name": f"P{i}", "team": "ARS", "opponent": "LEE (H)",
                "values": {"gw_xp": _v(f"{6 - i}.1", "https://goaliq.app/fpl/expected-points#gw-xp"),
                           "p_10plus": _v(f"{20 - i}%"), "p_blank": _v(f"{10 + i}%"),
                           "xmins": _v("90"), "start_pct": _v("97%")}}
               for i in range(7)]
    rows_cs = [{"key": f"t{i}", "team": f"Team {i}", "opponent": "Leeds", "venue": "H",
                "values": {"cs_pct": _v(f"{40 - i}.5%", "https://goaliq.app/fpl#clean-sheets")}}
               for i in range(7)]
    return {"gw": 6, "generated_at": "2026-09-22T08:43:27+00:00",
            "sections": {"xp_top5": {"available": True, "rows": rows_xp[:5]},
                         "cs_top": {"available": True, "rows": rows_cs},
                         "player_lookup": {"available": True, "rows": rows_xp}}}


@pytest.mark.parametrize("card", sorted(g.REPLY_FIELDS))
def test_value_and_label_come_from_the_same_field(card):
    m = _module()
    spec = g.reply_list_spec(m, card, n=10)
    section, field, label = g.REPLY_FIELDS[card]
    rows = m["sections"][section]["rows"]
    assert len(spec["rows"]) == g.REPLY_MAX_ROWS == 5
    assert [r["value"] for r in spec["rows"]] == [r["values"][field]["text"] for r in rows[:5]]
    assert spec["value_label"] == label.format(gw=6)


def test_reply_card_refuses_a_number_without_free_route():
    m = _module()
    m["sections"]["cs_top"]["rows"][2]["values"]["cs_pct"]["public_url"] = None
    with pytest.raises(SystemExit, match="ilmaispinnalla"):
        g.reply_list_spec(m, "reply-cs")


def test_unavailable_section_says_why():
    m = _module()
    m["sections"]["xp_top5"] = {"available": False, "reason": "free GW xP list is for GW5"}
    with pytest.raises(SystemExit, match="GW5"):
        g.reply_list_spec(m, "reply-xp")


def test_captain_compare_reads_module_rows_and_needs_2_to_3():
    m = _module()
    spec = g.captain_compare_spec(m, ["p0-ars", "p1-ars"])
    assert [c["values"][0]["value"] for c in spec["cols"]] == ["6.1", "5.1"]
    assert [v["label"] for v in spec["cols"][0]["values"]] == [
        lab.format(gw=6) for _f, lab in g.COMPARE_FIELDS]
    with pytest.raises(SystemExit):
        g.captain_compare_spec(m, ["p0-ars"])
    with pytest.raises(SystemExit):
        g.captain_compare_spec(m, ["p0-ars", "nobody"])


def test_model_vs_template_unavailable_and_gap_only_when_like_for_like():
    m = {"gw": 6, "sections": {"model_vs_template": {
        "available": False, "reason": "model squad for GW6 not frozen yet"}}}
    with pytest.raises(SystemExit, match="not frozen"):
        g.model_vs_template_spec(m)
    sec = {"available": True, "template_rule": "r", "model_frozen_at": "2026-09-11T07:45:24Z",
           "model_only": [{"name": "A", "team": "ARS",
                           "values": {"gw_xp_frozen": _v("5.47", None)}}],
           "template_only": [{"name": "B", "team": "CHE",
                              "values": {"eo_pct": _v("150.0%", "https://goaliq.app/fpl#eo-by-tier")}}],
           "xp_gap": {"available": False, "reason": "no like-for-like total"}}
    spec = g.model_vs_template_spec({"gw": 4, "sections": {"model_vs_template": sec}})
    assert spec["gap"] is None
    # Ennen kierrosta jaadytetylla xP:lla ei ole reittia -> nimi ilman lukua.
    assert spec["left"][0]["value"] == "" and spec["right"][0]["value"] == "EO 150.0%"


def _fonts_ok():
    return g.FONT_MED.is_file() and g.FONT_BOLD.is_file()


@pytest.mark.skipif(not _fonts_ok(), reason="IBM Plex Mono puuttuu tasta ymparistosta")
def test_rendered_reply_card_is_16_9_and_big_enough_for_the_feed(tmp_path):
    from PIL import Image
    spec = g.reply_list_spec(_module(), "reply-cs")
    out = g.render_reply_list(spec, tmp_path / "c.png")
    assert Image.open(out).size == (1200, 675)
    # Paaluku >= 48 px 1200 px leveydella (c3-suunnitelma): ~20 px kun X
    # nayttaa kuvan 500 px leveana.
    assert g.REPLY_VALUE_PX >= 48
    spec2 = g.captain_compare_spec(_module(), ["p0-ars", "p1-ars", "p2-ars"])
    out2 = g.render_captain_compare(spec2, tmp_path / "cc.png")
    assert Image.open(out2).size == (1200, 675)
