"""Reply-moduulin `matches`-osio: ottelusivun luvut botin aiheeksi (20.10.2026).

Osio ja ottelusivu lukevat SAMASTA lukijasta (`build_prediction_pages.load_feed`)
ja muotoilevat samalla `_fmt_pct`:lla. Jokaiselle kontrollille on positiivinen
ja negatiivinen testi, ja kutsupaikkojen poisto kaataa jonkin niista.
"""
from __future__ import annotations

import inspect
import json
from datetime import datetime, timedelta, timezone

import pytest

from scripts import build_prediction_pages as bpp
from scripts import build_reply_module as brm
from src.marketing import bsky_gate as gate
from src.marketing import reply_module as rm
from src.marketing import reply_sections as rs

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


def _e(home, away, hours, comp="PL", p=(0.4565, 0.2635, 0.28), **kw):
    ko = NOW + timedelta(hours=hours)
    e = {"match_id": f"{comp}-{home}-{away}", "competition": comp, "home_team": home,
         "away_team": away, "kickoff": ko.strftime("%Y-%m-%dT%H:%M:%SZ"),
         "p_home": p[0], "p_draw": p[1], "p_away": p[2], "xg_home": None, "xg_away": None,
         "most_likely_score": "1-1", "predicted_winner": "home",
         "logged_at": "2026-10-29T00:00:00+00:00", "result": None}
    e.update(kw)
    return e


def _log(*entries):
    return {"predictions": list(entries)}


def test_osio_luku_on_sama_kuin_ottelusivulla():
    e = _e("Arsenal FC", "Leeds United", 20)
    sec = rs.matches(_log(e), NOW)
    assert sec["available"] and len(sec["rows"]) == 1
    row = sec["rows"][0]
    feed = bpp.load_feed(_log(e), NOW)
    page_entry = feed.upcoming["PL"][0]
    html = bpp.render_match_page("PL", page_entry, NOW)
    for field in ("p_home", "p_draw", "p_away"):
        text = row["values"][field]["text"]
        assert text == bpp._fmt_pct(e[field])
        assert text in html, (field, text)
    # sivun URL on se johon builder kirjoittaa tiedoston
    assert row["page"] == bpp.match_page_url("PL", page_entry)
    assert row["page"].endswith("/predictions/premier-league/arsenal-fc-vs-leeds-united")
    assert all(v["page"] == row["page"] for v in row["values"].values())


def test_osio_pyoristaa_kuten_sivu_ei_kahden_desimaalin_luvulla():
    # 45.65 -> 46 % (puoli ylos), ei 45 % eika 45.65
    sec = rs.matches(_log(_e("Arsenal FC", "Leeds United", 5)), NOW)
    assert sec["rows"][0]["values"]["p_home"]["text"] == "46%"


def test_nayttonimi_antaa_saman_urlin_kuin_sivu():
    e = _e("Athletic Club", "Girona FC", 10, comp="PD")
    sec = rs.matches(_log(e), NOW)
    feed = bpp.load_feed(_log(e), NOW)
    assert sec["rows"][0]["page"] == bpp.match_page_url("PD", feed.upcoming["PD"][0])
    assert "athletic-bilbao" in sec["rows"][0]["page"]


def test_vaihe_ennen_kickoffia_mukana_sen_jalkeen_ei():
    e = _e("Arsenal FC", "Leeds United", 3)
    assert rs.matches(_log(e), NOW)["available"]
    after = NOW + timedelta(hours=3, minutes=1)
    sec = rs.matches(_log(e), after)
    assert not sec["available"] and sec["rows"] == [] and sec["reason"]


def test_vaihe_72_tunnin_ikkuna():
    inside = _e("Arsenal FC", "Leeds United", 71)
    outside = _e("Chelsea FC", "Fulham FC", 73)
    keys = [r["home"] for r in rs.matches(_log(inside, outside), NOW)["rows"]]
    assert keys == ["Arsenal FC"]


def test_ottelu_ilman_sivua_ei_tule_osioon():
    no_league = _e("Foo FC", "Bar FC", 5, comp="XX")
    no_pred = _e("Chelsea FC", "Fulham FC", 5, p=(None, None, None))
    played = _e("Everton FC", "Burnley FC", 5, result={"home": 1, "away": 0})
    assert rs.matches(_log(no_league, no_pred, played), NOW)["rows"] == []


def test_kickoff_paikkamerkki_keskiyo_jaa_pois():
    ko = (NOW + timedelta(hours=10)).replace(hour=0, minute=0)
    e = _e("Arsenal FC", "Leeds United", 10)
    e["kickoff"] = ko.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert rs.matches(_log(e), NOW)["rows"] == []


def test_jarjestys_kickoffin_mukaan():
    a = _e("Chelsea FC", "Fulham FC", 30)
    b = _e("Arsenal FC", "Leeds United", 5)
    assert [r["home"] for r in rs.matches(_log(a, b), NOW)["rows"]] == \
        ["Arsenal FC", "Chelsea FC"]


# ---- kutsupaikat -----------------------------------------------------------
def test_builder_ja_osio_kayttavat_samaa_lukijaa():
    assert "load_feed(" in inspect.getsource(bpp.main)
    assert "load_feed(" in inspect.getsource(rs.matches)
    assert "_fmt_pct(" in inspect.getsource(rs.matches)


def test_generaattori_kutsuu_osiota_ja_hakee_pinnan():
    assert "rs.matches(" in inspect.getsource(brm.build)
    assert "match_pages" in rm.ALL_SURFACES


def test_pinta_loytyy_ja_eroava_teksti_hylataan(monkeypatch):
    e = _e("Arsenal FC", "Leeds United", 5)
    monkeypatch.setattr("src.models.accuracy.load_log", lambda *a, **k: _log(e))
    sections = {"matches": rs.matches(_log(e), NOW)}
    # fetch_surfaces laskee pinnan oman kellonsa mukaan, joten kaytetaan samaa kelloa
    monkeypatch.setattr(rm, "datetime", type("D", (), {"now": staticmethod(lambda tz=None: NOW),
                                                        "fromisoformat": datetime.fromisoformat}))
    pages, _meta, errs = rm.fetch_surfaces({"match_pages"}, 7)
    assert not errs
    ok, none, bad = rm.resolve_routes(sections, pages, 7, "2026-10-30T12:00:00+00:00",
                                      {"prediction_log": {"file": "f", "commit": "c"}})
    assert (ok, none, bad) == (3, 0, [])
    v = sections["matches"]["rows"][0]["values"]["p_home"]
    assert v["public_url"].startswith("https://goaliq.app/predictions/premier-league/")
    # sivu muuttuu: moduulin teksti ei enaa vastaa
    sec2 = {"matches": rs.matches(_log(e), NOW)}
    sec2["matches"]["rows"][0]["values"]["p_home"]["text"] = "99%"
    ok, none, bad = rm.resolve_routes(sec2, pages, 7, "2026-10-30T12:00:00+00:00",
                                      {"prediction_log": {"file": "f", "commit": "c"}})
    assert len(bad) == 1 and "99%" in bad[0]


# ---- lukija ----------------------------------------------------------------
def _module(tmp_path, entry):
    dd, md = tmp_path / "data", tmp_path / "modules"
    dd.mkdir()
    md.mkdir()
    (dd / "prediction_log.json").write_text(json.dumps(_log(entry)), encoding="utf-8")
    sections = {"matches": rs.matches(_log(entry), NOW)}
    for _k, v, _r, _s in rm.iter_values(sections):
        v["public_url"] = v["page"]
        v.pop("routes", None)
    module = {"schema": rm.SCHEMA, "gw": 9, "deadline_utc": "2026-11-07T10:00:00+00:00",
              "sources": {"prediction_log": {"stamp": rm.source_stamp("prediction_log", dd)}},
              "named_players": {}, "sections": sections}
    (md / "gw9.json").write_text(json.dumps(module), encoding="utf-8")
    return dd, md


def _read(dd, md, now, keys=None):
    return rm.load_reply_module(9, keys=keys, now=now, data_dir=dd, module_dir=md,
                                fpl_status=lambda: {})


def test_lukija_palauttaa_ennen_kickoffia_ja_kieltaytyy_sen_jalkeen(tmp_path):
    e = _e("Arsenal FC", "Leeds United", 3)
    dd, md = _module(tmp_path, e)
    key = "matches.pl-arsenal-fc-vs-leeds-united.p_home"
    out = _read(dd, md, NOW, keys=[key])
    assert out["sections"]["matches"]["rows"][0]["values"]["p_home"]["text"] == "46%"
    with pytest.raises(rm.ReplyModuleRefused, match="kicked off"):
        _read(dd, md, NOW + timedelta(hours=3, minutes=1), keys=[key])


def test_lukija_kieltaytyy_kun_loki_muuttaa_lukua(tmp_path):
    e = _e("Arsenal FC", "Leeds United", 3)
    dd, md = _module(tmp_path, e)
    e2 = dict(e, p_home=0.60, p_draw=0.2, p_away=0.2)
    (dd / "prediction_log.json").write_text(json.dumps(_log(e2)), encoding="utf-8")
    with pytest.raises(rm.ReplyModuleRefused, match="changed"):
        _read(dd, md, NOW, keys=["matches.pl-arsenal-fc-vs-leeds-united.p_home"])


def test_lukija_sallii_muuttumattoman_luvun_kun_loki_regeneroitu(tmp_path):
    e = _e("Arsenal FC", "Leeds United", 3)
    dd, md = _module(tmp_path, e)
    (dd / "prediction_log.json").write_text(
        json.dumps(_log(dict(e, refresh_count=2))), encoding="utf-8")
    assert _read(dd, md, NOW, keys=["matches.pl-arsenal-fc-vs-leeds-united.p_draw"])


# ---- portti ----------------------------------------------------------------
def test_portti_hylkaa_vedonlyontisanan_ennusteaiheessa():
    key = "matches.pl-arsenal-fc-vs-leeds-united.p_home"
    page = "https://goaliq.app/predictions/premier-league/arsenal-fc-vs-leeds-united"
    values = {key: {"text": "46%", "public_url": page}}

    def probs(text):
        item = {"kind": "post", "text": text, "keys": [key], "link": page, "topic": "prediction"}
        return gate.check(item, values=values, gw=9, now=NOW, state={
            "posted_slots": [], "replied_uris": [], "replied_roots": [], "author_last_reply": {},
            "daily": {}, "recent_texts": [], "handled_notifications": []},
            blocklist=set(), phrases=[])

    clean = probs("Arsenal at 46% to beat Leeds in the model. goaliq.app/predictions/premier-league/arsenal-fc-vs-leeds-united")
    assert not any("betting" in p or "sanamuoto" in p for p in clean), clean
    dirty = probs("Betting tips: Arsenal at 46% to beat Leeds. goaliq.app/predictions/premier-league/arsenal-fc-vs-leeds-united")
    assert dirty and any("betting" in p.lower() or "tips" in p.lower() for p in dirty), dirty


# ---- joukkue ja luku (CoS 30.10) -------------------------------------------
# 26.10 roolivirhe: luku oikein, rooli vaara. Ottelussa sama vika on "Liverpool 46%", kun 46 % on Arsenalin.
# Portti vaatii, etta luvun lahin nimi samassa lauseessa on sen oma label, ja briefi antaa labelin aivoille.
LIV, ARS = "Liverpool FC", "Arsenal FC"


def _gate_values(*entries):
    """Arvot sellaisina kuin botti antaa ne portille: moduulin arvo + julkinen reitti."""
    vals = {}
    for r in rs.matches(_log(*entries), NOW)["rows"]:
        for f, v in r["values"].items():
            vals[f"matches.{r['key']}.{f}"] = dict(v, public_url=v["page"])
    return vals


def _key(vals, match, field):
    return next(k for k in vals if k.startswith(f"matches.{match}") and k.endswith(f".{field}"))


def _gate(text, keys, vals):
    page = vals[keys[0]]["public_url"]
    item = {"kind": "post", "text": f"{text} {page.replace('https://', '')}", "keys": keys,
            "link": page, "topic": "prediction"}
    return gate.check(item, values=vals, gw=9, now=NOW, state={
        "posted_slots": [], "replied_uris": [], "replied_roots": [], "author_last_reply": {},
        "daily": {}, "recent_texts": [], "handled_notifications": []}, blocklist=set(), phrases=[])


def _label_probs(probs):
    return [p for p in probs if "lahin nimi" in p or "(label)" in p]


@pytest.fixture
def liv_ars():
    vals = _gate_values(_e(LIV, ARS, 20, p=(0.25, 0.30, 0.46)))
    return vals, _key(vals, "pl-liverpool", "p_home"), _key(vals, "pl-liverpool", "p_away")


def test_portti_paastaa_luvun_oman_joukkueen_vieressa(liv_ars):
    vals, home, away = liv_ars
    assert _gate(f"{LIV} 25%, {ARS} 46% in the model for Sunday.", [home, away], vals) == []
    # vieras ensin ja koti perassa: lahin nimi ratkaisee, ei jarjestys
    assert _gate(f"{ARS} 46% at {LIV} in our model.", [away], vals) == []


def test_portti_hylkaa_vaihdetut_joukkueet(liv_ars):
    vals, home, away = liv_ars
    probs = _label_probs(_gate(f"{ARS} 25%, {LIV} 46% in the model for Sunday.", [home, away], vals))
    assert len(probs) == 2, probs


def test_portti_hylkaa_luvun_ilman_joukkuetta(liv_ars):
    vals, _home, away = liv_ars
    assert _label_probs(_gate("46% in the model for Sunday.", [away], vals))


def test_portti_ei_lue_nimea_edellisesta_lauseesta(liv_ars):
    vals, home, away = liv_ars
    # nimi edellisessa lauseessa ei omista lukua; oma nimi samassa lauseessa omistaa
    assert _gate(f"Big one on Sunday. {ARS} 46% at Anfield.", [away], vals) == []
    assert _label_probs(_gate(f"Watch {ARS} on Sunday. 46% in the model for the away side.", [away], vals))


def test_portti_tasapeli_ja_sama_luku_kahdesti():
    vals = _gate_values(_e("Tottenham Hotspur", "Crystal Palace", 20, p=(0.42, 0.29, 0.29)))
    draw, away = (_key(vals, "pl-tottenham", f) for f in ("p_draw", "p_away"))
    assert _gate("Crystal Palace 29% and draw 29% in the model.", [away, draw], vals) == []
    assert _label_probs(_gate("Draw 29% in the model.", [away], vals))


def test_portti_hylkaa_toisen_ottelun_joukkueen_luvun_vieressa():
    vals = _gate_values(_e(LIV, ARS, 20, p=(0.25, 0.30, 0.46)),
                        _e("Bayern Munich", "Borussia Dortmund", 22, comp="BL1", p=(0.67, 0.18, 0.15)))
    away = _key(vals, "pl-liverpool", "p_away")
    # oma nimi on lauseessa, mutta kauempana: lahin on toisen ottelun joukkue, jonka luku 46 % ei ole
    assert _label_probs(_gate(f"Bayern Munich 46% in the model, the same as {ARS}.", [away], vals))
    assert _gate(f"{ARS} 46% in the model, on the day Bayern Munich play at home.", [away], vals) == []


def test_pidempi_nimi_voittaa_lyhyemman():
    spans = gate._name_spans("AC Milan 32% at home", {"AC Milan", "Milan"})
    assert [n for _s, _e, n in spans] == ["ac milan"]


def test_briefi_antaa_ottelun_luvulle_nimen(liv_ars):
    from scripts import bsky_bot as bot
    vals, _home, away = liv_ars
    brief = bot.brief_numbers(vals)
    assert brief[away] == {"text": "46%", "page": bot.bsky_gate_page(vals[away]["public_url"]), "label": ARS}
    # osio ilman labelia pysyy ennallaan
    other = {"xp_top5.haaland-mci.gw_xp": {"text": "6.1", "public_url": "https://goaliq.app/fpl/expected-points"}}
    assert set(bot.brief_numbers(other)["xp_top5.haaland-mci.gw_xp"]) == {"text", "page"}
    # kutsupaikka: aivojen briefi rakennetaan taman kautta
    assert "brief_numbers(" in inspect.getsource(bot.cmd_context)


def test_portti_ei_arvaa_kun_kaksi_nimea_yhta_lahella(liv_ars):
    vals, _home, away = liv_ars
    assert _label_probs(_gate(f"{LIV} 46% {ARS} in the model.", [away], vals))
