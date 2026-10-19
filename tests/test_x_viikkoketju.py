"""X-viikkoketju (19.10.2026): mallin oman FPL-joukkueen kierroskatsaus X-jonoon.

Portti kaatuu, jos
  * ketju syntyy kierrokselle, joka ei ole finished ja data_checked, tai seuraavan deadlinen jälkeen,
  * kauden ero lasketaan muusta kuin FPL:n kokonaispisteistä keskiarvojen summaa vastaan,
  * viesti ylittää X:n rajan tai sisältää em- tai en-viivan, tai pohjia on vähemmän kuin kolme,
  * sama kierros saa toisen issuen, tai työnkulku tai rele lakkaa kutsumasta generaattoria.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

JUURI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(JUURI))
from scripts import x_viikkoketju as xk  # noqa: E402

NYT = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)


def _bootstrap(gw7_valmis=True, gw8_deadline="2026-10-23T17:30:00Z"):
    return {
        "total_players": 11_129_074,
        "events": [
            {"id": 6, "finished": True, "data_checked": True, "average_entry_score": 58,
             "deadline_time": "2026-10-03T10:00:00Z"},
            {"id": 7, "finished": gw7_valmis, "data_checked": gw7_valmis, "average_entry_score": 55,
             "deadline_time": "2026-10-17T10:00:00Z"},
            {"id": 8, "finished": False, "data_checked": False, "average_entry_score": 0,
             "deadline_time": gw8_deadline},
        ],
        "elements": [{"id": 1, "web_name": "Haaland"}, {"id": 2, "web_name": "Saka"}],
    }


HISTORIA = {"current": [
    {"event": 6, "points": 57, "total_points": 382, "overall_rank": 2_730_030, "event_transfers_cost": 0},
    {"event": 7, "points": 81, "total_points": 459, "overall_rank": 1_618_187, "event_transfers_cost": 4},
]}
PICKS = {"active_chip": "bboost", "picks": [{"element": 2, "is_captain": False, "multiplier": 1},
                                            {"element": 1, "is_captain": True, "multiplier": 2}]}
LIVE = {"elements": [{"id": 1, "stats": {"total_points": 13}}, {"id": 2, "stats": {"total_points": 2}}]}


def test_vain_lopullinen_kierros_ennen_seuraavaa_deadlinea():
    assert xk.lopullinen_kierros(_bootstrap(), NYT) == 7
    assert xk.lopullinen_kierros(_bootstrap(gw7_valmis=False), NYT) is None, "GW6:n seuraava deadline on mennyt"
    assert xk.lopullinen_kierros(_bootstrap(gw8_deadline="2026-10-20T11:00:00Z"), NYT) is None
    b = _bootstrap()
    b["events"][1]["data_checked"] = False
    assert xk.lopullinen_kierros(b, NYT) is None, "finished ilman data_checked ei ole lopullinen"


def test_kauden_ero_fpl_kokonaispisteista_keskiarvojen_summaa_vastaan():
    b = _bootstrap()
    historia = {"current": [{"event": g, "points": 50, "total_points": 50 * g, "overall_rank": 1,
                             "event_transfers_cost": 0} for g in range(1, 6)] + HISTORIA["current"]}
    for g, ka in zip(range(1, 6), (50, 81, 51, 69, 48)):
        b["events"].append({"id": g, "finished": True, "data_checked": True, "average_entry_score": ka})
    d = xk.kokoa(7, b, historia, PICKS, LIVE)
    assert d["kokonais"] == 459 and d["keskiarvo_summa"] == 50 + 81 + 51 + 69 + 48 + 58 + 55
    assert d["hitti"] == 4 and d["top_pct"] == 15 and d["chip"] == "Bench Boost"
    assert (d["kapteeni"], d["kapteeni_pisteet"], d["kerroin"]) == ("Haaland", 13, 2)


def test_viestit_mahtuvat_eivatka_sisalla_viivoja_ja_pohjia_on_kolme():
    b = _bootstrap()
    d = xk.kokoa(7, b, HISTORIA, PICKS, LIVE)
    rungot = set()
    for gw in (6, 7, 8):
        viestit = xk.ketju({**d, "gw": gw, "seuraava": gw + 1})
        assert len(viestit) == 4
        for v in viestit:
            assert xk.x_pituus(v) <= xk.X_MAX and "—" not in v and "–" not in v
        assert "116920" in "".join(viestit) and "utm_source=x" in viestit[-1], "CTA ja tarkistus mukana"
        rungot.add(viestit[0].split(":")[0][:20])
    assert len(rungot) == 3, "sama runko joka viikko on AI-tunnusmerkki"


def test_yksikko_ja_ero_molempiin_suuntiin():
    assert xk._p(1) == "1 point" and xk._p(2) == "2 points"
    assert xk._ero(-9) == "9 points below" and xk._ero(1) == "1 point above" and xk._ero(0) == "level with"


def test_sama_kierros_ei_saa_toista_issueta(monkeypatch):
    kutsut = []

    def gh(metodi, polku, token, data=None):
        kutsut.append(metodi)
        return [{"title": "X-ketju: mallin joukkue GW7"}] if metodi == "GET" else {"html_url": "u"}

    monkeypatch.setattr(xk, "_gh", gh)
    monkeypatch.setenv("GH_TOKEN", "t")
    haut = {"bootstrap-static": _bootstrap(), "history": HISTORIA, "picks": PICKS, "live": LIVE}
    hae = lambda url: next(v for k, v in haut.items() if k in url)  # noqa: E731
    assert xk.main([], nyt=NYT, hae=hae) == 0
    assert kutsut == ["GET"], "olemassa oleva issue: ei POST:ia"
    kutsut.clear()
    monkeypatch.setattr(xk, "_gh", lambda m, p, t, data=None: (kutsut.append(m), [] if m == "GET" else {"html_url": "u"})[1])
    assert xk.main([], nyt=NYT, hae=hae) == 0
    assert kutsut == ["GET", "POST"]


def test_tyonkulku_ja_rele_kutsuvat_generaattoria():
    doc = yaml.safe_load((JUURI / ".github" / "workflows" / "x-viikkoketju.yml").read_text(encoding="utf-8"))
    run = "\n".join(str(s.get("run", "")) for s in doc["jobs"]["ketju"]["steps"])
    assert "python -m scripts.x_viikkoketju" in run
    assert "secrets." not in yaml.safe_dump(doc), "ei salaisuuksia: FPL on julkinen"
    from scripts import fp_dispatch_relay as relay
    assert "x-viikkoketju.yml" in {t["workflow"] for t in relay.TARGETS}
