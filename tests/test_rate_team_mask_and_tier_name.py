# -*- coding: utf-8 -*-
"""Kaksi porttia julkaisutarkistajan 5.9.2026 loydoksista.

1. /api/fantasy/rate-team ei saa antaa siirtosuosituksia anonyymille.
   Portti oli vain selaimessa ({#if premium}); curl sai 5 rivia nimineen ja
   delta_xp_horizon-lukuineen. Viides kerta samaa vikaluokkaa (captain 15.8,
   replacements 2.9, value + chip-ev 4.9). Maski on nyt endpointissa.

2. Maksullisen tason nimi on "Premium", ei "PRO". ToolRow.svelte sanoi
   aria-labelissa Premium ja nakyvassa tekstissa PRO; kaksi muuta pintaa
   samoin. Portti kieltaa nakyvan >PRO< julkisissa komponenteissa.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPA = ROOT / "web" / "pro-spa" / "src"


def test_rate_team_mask_poistaa_suositukset_mutta_jattaa_ilmaisen() -> None:
    from api.premium import mask_rate_team_payload

    payload = {
        "rating": {"rating": 99, "weakest_line": "GKP"},
        "captain": {"pick": {"web_name": "Haaland"}, "alternative": {"web_name": "Isak"}},
        "transfers": {
            "hold_verdict": {"verdict": "hold", "message": "The best move the model checked gains only +2.2 xP"},
            "suggestions": [
                {"out": {"web_name": "A"}, "in": {"web_name": "B"}, "delta_xp_horizon": 2.23},
                {"out": {"web_name": "C"}, "in": {"web_name": "D"}, "delta_xp_horizon": 1.1},
            ],
        },
        "meta": {"gw_from": 4, "gw_to": 8},
    }
    out = mask_rate_team_payload(payload)

    assert out["transfers"]["suggestions"] == []
    assert out["meta"]["masked"] is True
    assert "2 transfer suggestions" in out["meta"]["mask"]
    # Ilmainen puoli koskematon: myyntisivu lupaa "Rate my team, with a captain pick".
    assert out["rating"] == payload["rating"]
    assert out["captain"] == payload["captain"]
    assert out["transfers"]["hold_verdict"] == payload["transfers"]["hold_verdict"]
    # Alkuperaista ei mutatoida (cache jakaa saman olion premium-kutsuille).
    assert len(payload["transfers"]["suggestions"]) == 2


def test_rate_team_endpoint_kutsuu_maskia_ilman_premiumia() -> None:
    """Lahdetason vahti: endpointin runko sisaltaa maskikutsun is_premium-
    haarassa. Ilman tata seuraava refaktorointi voi pudottaa kutsun ja
    yksikkotesti ylla pysyy vihreana."""
    src = (ROOT / "api" / "main.py").read_text(encoding="utf-8")
    i = src.index('@app.get("/api/fantasy/rate-team"')
    runko = src[i : i + 4000]
    assert "if not is_premium_request(request):" in runko
    assert "return mask_rate_team_payload(payload)" in runko


PRO_RE = re.compile(r">\s*PRO\s*<")


def test_julkisissa_komponenteissa_ei_nakyvaa_PRO_tunnistetta() -> None:
    osumat = []
    for p in sorted(SPA.rglob("*.svelte")):
        teksti = re.sub(r"<!--.*?-->", "", p.read_text(encoding="utf-8"), flags=re.S)
        for m in PRO_RE.finditer(teksti):
            rivi = teksti[: m.start()].count("\n") + 1
            osumat.append(f"{p.relative_to(SPA)}:{rivi}")
    assert not osumat, (
        "Maksullinen taso on Premium, ei PRO. Nakyva >PRO< loytyi: " + ", ".join(osumat)
    )


def test_negatiivinen_kontrolli_PRO_regex_osuu() -> None:
    assert PRO_RE.search('<span class="lock">PRO</span>')
    assert not PRO_RE.search('<span class="lock">Premium</span>')
