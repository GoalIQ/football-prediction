"""Ottelua edeltava xG ei ole julkinen (Villen paatos 22.9.2026).

`data/prediction_log.json` on julkinen kahdesta paikasta: goaliq.app/data/ ja
julkinen repo. 22.9 mitattiin, etta siina oli 2 677 gradaamatonta riviä joilla
oli `xg_home`/`xg_away`, eli tulevien otteluiden xG ennen ottelua. 2.8:n linjaus
oli: todennakoisin tulos saa olla julkinen (se gradataan), xG ei. Sama luku on
PREDICT_MASKin takana /api/predictissa, joten loki olisi ollut maskin kiertotie.

Suunnittelu (saanto 6a, mekanismi 1): siivous on `save_log`issa, joka on lokin
ainoa kirjoittaja. Uusi kutsupaikka ei voi unohtaa saantoa.

Vaiheet (kohta 3): gradaamaton tuleva rivi, gradaamaton mennyt rivi (kesken tai
tulos puuttuu), gradattu rivi, rivi jolla ei ole xG:ta lainkaan.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from src.models import accuracy as acc

ROOT = Path(__file__).resolve().parents[1]


def _row(mid: str, *, result, xg=(1.8, 0.9), kickoff="2026-10-08T18:00:00Z") -> dict:
    return {"match_id": mid, "competition": "PL", "date": kickoff[:10],
            "kickoff": kickoff, "home_team": "A", "away_team": "B",
            "p_home": 0.5, "p_draw": 0.3, "p_away": 0.2,
            "xg_home": xg[0], "xg_away": xg[1],
            "most_likely_score": "1-0", "predicted_winner": "A",
            "logged_at": "2026-09-22T18:00:00Z", "result": result}


def test_gradaamattomalta_rivilta_xg_katoaa_gradatulta_jaa(tmp_path):
    log = {"version": acc.LOG_VERSION, "predictions": [
        _row("tuleva", result=None),
        _row("kesken", result=None, kickoff="2026-09-22T16:00:00Z"),
        _row("gradattu", result={"home_score": 2, "away_score": 1}),
        {"match_id": "ei-xg", "result": None, "p_home": 0.4},
    ]}
    p = tmp_path / "prediction_log.json"
    acc.save_log(log, p)
    rows = {e["match_id"]: e for e in json.loads(p.read_text(encoding="utf-8"))["predictions"]}
    assert rows["tuleva"]["xg_home"] is None and rows["tuleva"]["xg_away"] is None
    assert rows["kesken"]["xg_home"] is None
    assert rows["gradattu"]["xg_home"] == 1.8, "pelatun ottelun xG ei ole ennakkotieto"
    assert rows["ei-xg"].get("xg_home") is None
    # Muut kentat ennallaan: siivous ei saa koskea todennakoisyyksiin eika
    # todennakoisimpaan tulokseen (2.8: se on julkinen koska se gradataan).
    assert rows["tuleva"]["most_likely_score"] == "1-0"
    assert rows["tuleva"]["p_home"] == 0.5


def test_julkaistussa_lokissa_ei_ole_gradaamattomien_xgta():
    """Elava data: sama tiedosto joka on goaliq.app/data/prediction_log.json."""
    log = acc.load_log()
    vuotavat = [e.get("match_id") for e in log["predictions"]
                if e.get("result") is None
                and (e.get("xg_home") is not None or e.get("xg_away") is not None)]
    assert vuotavat == [], f"{len(vuotavat)} gradaamatonta riviä kantaa xG:ta, esim. {vuotavat[:3]}"


def test_gradattuja_xg_riveja_on_yha():
    """Erotteleva: jos siivous veisi kaikki, testi 1 olisi vihrea tyhjyydesta."""
    log = acc.load_log()
    gradatut = [e for e in log["predictions"]
                if e.get("result") is not None and e.get("xg_home") is not None]
    assert len(gradatut) > 100, "pelattujen otteluiden xG katosi lokista"


def test_save_log_on_ainoa_kirjoittaja():
    """Kutsupaikkaportti: kukaan ei kirjoita lokia save_login ohi."""
    bad: list[str] = []
    for p in list((ROOT / "scripts").glob("*.py")) + list((ROOT / "src").rglob("*.py")):
        src = p.read_text(encoding="utf-8", errors="ignore")
        # Vain ennustelokia kasittelevat tiedostot: muilla skripteilla on omat
        # LOG_PATH-vakionsa (gw_calls, hintavahti, squad-signaalit).
        if "prediction_log" not in src:
            continue
        lines = src.splitlines()
        # Mitka nimet osoittavat TAHAN lokiin tassa tiedostossa. Ilman tata
        # osuma tulisi HTML-kirjoittajista ja muiden lokien LOG_PATHeista.
        log_names = set(re.findall(r"^(\w+)\s*=\s*[^\n]*prediction_log", src, re.M))
        log_names |= {"log", "LOG_PATH"} if p.name == "accuracy.py" else set()
        if not log_names:
            continue
        for m in re.finditer(r"(\w+)\.write_text\s*\(|json\.dump\s*\(\s*(\w+)", src):
            name = m.group(1) or m.group(2)
            if name not in log_names:
                continue
            line_no = src[:m.start()].count("\n") + 1
            if p.name == "accuracy.py" and "def save_log" in src[max(0, m.start() - 600):m.start()]:
                continue
            bad.append(f"{p.name}:{line_no}: {lines[line_no - 1].strip()[:80]}")
    assert bad == [], "ennustelokia kirjoitetaan save_login ohi: " + "; ".join(bad)
