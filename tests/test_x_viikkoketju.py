"""X-viikkoketju (19.10.2026): entry 116920:n kierroskatsaus X-jonoon.

Portti kaatuu, jos
  * ketju syntyy kierrokselle, joka ei ole finished ja data_checked, tai seuraavan deadlinen jälkeen,
  * kauden ero lasketaan muusta kuin FPL:n kokonaispisteistä keskiarvojen summaa vastaan, tai top-% tulee
    muualta kuin FPL:n omasta overall_rank_percentage-kentästä,
  * viesti ylittää X:n rajan, sisältää em- tai en-viivan, pohjat toistavat samaa lausetta tai teksti palaa
    julkaisutarkistajan 19.10 blokkaamiin lupauksiin ("every player", "Every number", "locked"),
  * pelaamaton tai estolistan kapteeni mainitaan, tai CTA jää kauden viimeiselle kierrokselle,
  * sama kierros saa toisen issuen, tai työnkulku tai rele lakkaa kutsumasta generaattoria.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

JUURI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(JUURI))
from scripts import publish_gate  # noqa: E402
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
    {"event": 6, "points": 57, "total_points": 382, "overall_rank": 2_730_030, "event_transfers_cost": 0,
     "overall_rank_percentage": 25},
    # 14 eikä 15: rank / total = 14,5 %, joten oma kaava (ceil tai round) antaisi 15. Erotteleva fikstuuri.
    {"event": 7, "points": 81, "total_points": 459, "overall_rank": 1_618_187, "event_transfers_cost": 4,
     "overall_rank_percentage": 14},
]}
PICKS = {"active_chip": "bboost", "picks": [{"element": 2, "is_captain": False, "multiplier": 1},
                                            {"element": 1, "is_captain": True, "multiplier": 2}]}
LIVE = {"elements": [{"id": 1, "stats": {"total_points": 13, "minutes": 90}},
                     {"id": 2, "stats": {"total_points": 2, "minutes": 90}}]}


def _d(**muutos):
    return {**xk.kokoa(7, _bootstrap(), HISTORIA, PICKS, LIVE), **muutos}


def test_vain_lopullinen_kierros_ennen_seuraavaa_deadlinea():
    assert xk.lopullinen_kierros(_bootstrap(), NYT) == 7
    assert xk.lopullinen_kierros(_bootstrap(gw7_valmis=False), NYT) is None, "GW6:n seuraava deadline on mennyt"
    assert xk.lopullinen_kierros(_bootstrap(gw8_deadline="2026-10-20T11:00:00Z"), NYT) is None
    b = _bootstrap()
    b["events"][1]["data_checked"] = False
    assert xk.lopullinen_kierros(b, NYT) is None, "finished ilman data_checked ei ole lopullinen"


def test_kauden_ero_ja_top_prosentti_fpl_n_luvuista():
    b = _bootstrap()
    historia = {"current": [{"event": g, "points": 50, "total_points": 50 * g, "overall_rank": 1,
                             "event_transfers_cost": 0, "overall_rank_percentage": 1} for g in range(1, 6)]
                + HISTORIA["current"]}
    for g, ka in zip(range(1, 6), (50, 81, 51, 69, 48)):
        b["events"].append({"id": g, "finished": True, "data_checked": True, "average_entry_score": ka})
    d = xk.kokoa(7, b, historia, PICKS, LIVE)
    assert d["kokonais"] == 459 and d["keskiarvo_summa"] == 50 + 81 + 51 + 69 + 48 + 58 + 55
    assert d["hitti"] == 4 and d["chip"] == "Bench Boost"
    assert d["top_pct"] == 14, "FPL:n overall_rank_percentage, ei rank/total-kaavaa"
    assert (d["kapteeni"], d["kapteeni_pisteet"], d["kapteeni_minuutit"], d["kerroin"]) == ("Haaland", 13, 90, 2)
    ilman = {"current": [{**HISTORIA["current"][1], "overall_rank_percentage": None}, HISTORIA["current"][0]]}
    assert xk.kokoa(7, _bootstrap(), ilman, PICKS, LIVE)["top_pct"] is None, "puuttuva on None, ei laskettu"


# Kapteeni-, chip- ja tasolause ovat datapaloja, jotka pohjat jakavat tarkoituksella (julkaisutarkistajan
# 19.10 korjaama rakenne). Runko eli pohjan oma lause ei saa toistua.
DATAPALAT = re.compile(r"^(#\.?|Top #% overall\.|Overall rank #\.|We played the [A-Za-z ]+\.|"
                       r".+ with the armband:|.+ blanked with the armband\.|Triple Captain on .+)$")


def _lauseet(viestit):
    teksti = re.sub(r"https?://\S+|\d[\d,]*", "#", " ".join(viestit))
    return {s.strip() for s in re.split(r"(?<=[.:])\s+", teksti) if s.strip() and not DATAPALAT.match(s.strip())}


def test_pohjat_mahtuvat_eivat_toista_lauseita_eivatka_lupaa_blokattua():
    viesteja, lauseet = {}, {}
    for gw in (6, 7, 8):
        viestit = xk.ketju(_d(gw=gw, seuraava=gw + 1))
        viesteja[gw % 3] = len(viestit)
        for v in viestit:
            assert xk.x_pituus(v) <= xk.X_MAX and "—" not in v and "–" not in v and "’" not in v
        koko = " ".join(viestit)
        assert "116920" in koko and "utm_source=x" in viestit[-1] and "/fpl/best-captain?" in viestit[-1]
        for kielletty in ("every player", "Every number", "locked", "model's own FPL team", "in public"):
            assert kielletty not in koko, kielletty
        for s in _lauseet(viestit):
            lauseet.setdefault(s, set()).add(gw % 3)
    assert viesteja == {0: 3, 1: 2, 2: 3}
    toistuvat = [s for s, pohjat in lauseet.items() if len(pohjat) > 1]
    assert not toistuvat, f"sama lause useassa pohjassa: {toistuvat}"


def test_pelaamaton_ja_estolistan_kapteeni_eivat_nay():
    assert "Haaland" in " ".join(xk.ketju(_d()))
    assert "Haaland" not in " ".join(xk.ketju(_d(kapteeni_minuutit=0, kapteeni_pisteet=0)))
    estetty = publish_gate.load_blocklist()[0]["name"]
    assert estetty not in " ".join(xk.ketju(_d(kapteeni=estetty)))


def test_viimeinen_kierros_ilman_cta_ta_ja_triple_captain():
    for gw in (36, 37, 38):  # kaikki kolme pohjaa
        viestit = xk.ketju(_d(gw=gw, seuraava=None))
        assert "goaliq.app" not in " ".join(viestit) and "None" not in " ".join(viestit), gw
    assert "Triple Captain on Haaland: 39." in " ".join(xk.ketju(_d(kerroin=3, chip="Triple Captain")))


def test_yksikko():
    assert xk._p(1) == "1 point" and xk._p(2) == "2 points"


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


def test_ketjun_issue_sisaltaa_x_jakolinkin_ensimmaiselle_viestille():
    """23.10: yhden napautuksen postaus. Linkin dekoodattu teksti on täsmälleen ensimmäinen viesti."""
    import urllib.parse
    viestit = xk.ketju(_d(gw=7, seuraava=8))
    body = xk.issue(_d(gw=7, seuraava=8), viestit)["body"]
    m = re.search(r"\(https://x\.com/intent/tweet\?text=([^)\s]+)\)", body)
    assert m and urllib.parse.unquote(m.group(1)) == viestit[0]
    assert body.count("x.com/intent/tweet") == 1
