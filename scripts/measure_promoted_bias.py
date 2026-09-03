"""Mittaa nousijaseurojen pelaajien ennustevirheen gradatusta datasta.

MIKSI (3.9.2026, Villen GO). `fpl_transfers.LOW_CONFIDENCE_WEIGHT` oli 0.75
ja moduulin oma docstring sanoi sen olevan OLETUS eika mittaus, TODO:na
"kun 3+ kierrosta on gradattu, laske MAE erikseen price-prior-pelaajille ja
aseta paino niiden yliarvioinnin suhteessa".

Paino ei ole kosmeettinen: se ohjasi entry 116920:n ykkosehdotusta
(Tzolakis ulos), jonka PAINOTTAMATON hyoty oli -0.87 xP. Eli malli suositteli
siirtoa joka haviaa pisteita sen omilla luvuilla.

MITA TAMA MITTAA. Jokaiselle gradatulle kierrokselle:
  ennuste = `data/fpl_xp_frozen/gw{N}.json` (deadline-freeze, se luku joka
            oli julkaistu ennen kierrosta — ei jalkikateen laskettu)
  toteuma = FPL:n oma `event/{N}/live/` total_points
  populaatio = pelaajat joilla on minuutteja (nollaminuuttiset mittaisivat
            minuuttimallia, eivat pistemallia)
  ryhmat = nousijaseura vs muut, `is_promoted` xP-artefaktin
            team_confidence-lohkosta (sama lahde kuin siirtomoottorilla)

Ajo:
    .venv/Scripts/python.exe -m scripts.measure_promoted_bias
"""
from __future__ import annotations

import json
import math
import statistics as st
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402

FROZEN_DIR = config.PROJECT_ROOT / "data" / "fpl_xp_frozen"
XP_PATH = config.PROJECT_ROOT / "data" / "fpl_xp_projections.json"
LIVE_URL = "https://fantasy.premierleague.com/api/event/{gw}/live/"
BOOT_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"


def promoted_shorts() -> set[str]:
    """Nousijaseurojen lyhenteet artefaktista, ei kovakoodattuna.

    🔴 Artefaktin oma nimeaminen on epajohdonmukainen: `team_confidence`n
    avaimet ovat lyhytmuotoisia ("Hull") mutta pelaajarivien `team` on
    taysmittainen ("Hull City"). Suora `==`-vertailu bootstrapiin palautti
    TYHJAN JOUKON, ja mittaus olisi raportoinut "n=0" ilman virhetta — eli
    hiljaisen nollan josta olisi voinut paatella etta nousijoita ei ole.
    Tasmays tehdaan molempiin suuntiin ja tulos varmistetaan.
    """
    xp = json.loads(XP_PATH.read_text(encoding="utf-8"))
    tc = ((xp.get("meta") or {}).get("team_confidence") or {}).get("teams") or {}
    names = {n for n, r in tc.items()
             if isinstance(r, dict) and r.get("is_promoted")}
    if not names:
        raise SystemExit("VIRHE: artefaktissa ei ole nousijaseuroja "
                         "(meta.team_confidence.teams[*].is_promoted).")
    boot = json.loads(urllib.request.urlopen(BOOT_URL).read())
    shorts = set()
    for t in boot["teams"]:
        full = t["name"]
        if any(full == n or full.startswith(n + " ") or n.startswith(full + " ")
               for n in names):
            shorts.add(t["short_name"])
    if len(shorts) != len(names):
        raise SystemExit(
            f"VIRHE: {len(names)} nousijaseuraa artefaktissa "
            f"({sorted(names)}) mutta {len(shorts)} tasmasi bootstrapiin "
            f"({sorted(shorts)}) — nimeaminen muuttui, ala mittaa vajaalla.")
    return shorts


def graded_gameweeks() -> list[int]:
    """Kierrokset joille on SEKA freeze ETTA gradattu tulos."""
    boot = json.loads(urllib.request.urlopen(BOOT_URL).read())
    done = {e["id"] for e in boot["events"]
            if e.get("finished") and e.get("data_checked")}
    have = {int(p.stem[2:]) for p in FROZEN_DIR.glob("gw*.json")}
    return sorted(done & have)


def rows(gws: list[int], prom: set[str]) -> list[tuple[bool, float, float]]:
    out = []
    for gw in gws:
        froz = {p["id"]: p for p in json.loads(
            (FROZEN_DIR / f"gw{gw}.json").read_text(encoding="utf-8"))["players"]}
        live = json.loads(urllib.request.urlopen(LIVE_URL.format(gw=gw)).read())
        for el in live["elements"]:
            f = froz.get(el["id"])
            if not f or f.get("xp") is None:
                continue
            s = el["stats"]
            if (s.get("minutes") or 0) <= 0:
                continue
            out.append((f["team_short"] in prom, float(f["xp"]),
                        float(s["total_points"])))
    return out


def _group(data: list[tuple[bool, float, float]], sel: bool) -> dict:
    d = [a - p for pr, p, a in data if pr == sel]
    n = len(d)
    if n < 2:
        return {"n": n}
    sd = st.stdev(d)
    return {"n": n, "bias": st.mean(d), "se": sd / math.sqrt(n),
            "mae": st.mean([abs(x) for x in d])}


def main() -> int:
    prom = promoted_shorts()
    gws = graded_gameweeks()
    if not gws:
        raise SystemExit("VIRHE: yhtaan gradattua kierrosta jolle on freeze.")
    data = rows(gws, prom)
    p, m = _group(data, True), _group(data, False)
    print(f"Nousijaseurat: {sorted(prom)} | gradatut kierrokset: {gws}")
    print("Populaatio: pelaajat joilla minuutteja. bias = toteuma - ennuste "
          "(positiivinen = malli ALIarvioi).")
    for lbl, g in (("nousijaseurat", p), ("muut", m)):
        if g["n"] < 2:
            print(f"  {lbl:16} n={g['n']} — liian vahan mittaukseen")
            continue
        print(f"  {lbl:16} n={g['n']:5}  bias {g['bias']:+6.3f}  "
              f"se {g['se']:.3f}  MAE {g['mae']:.3f}")
    if p["n"] >= 2 and m["n"] >= 2:
        diff = p["bias"] - m["bias"]
        z = diff / math.sqrt(p["se"] ** 2 + m["se"] ** 2)
        print(f"\n  ero (nousija - muu) {diff:+.3f}   z {z:+.2f}   "
              f"{'merkitseva' if abs(z) > 2 else 'EI merkitseva'}")
        print("\n  🔴 Alennuskerroin (<1.0) on perusteltu VAIN jos bias on "
              "negatiivinen (malli yliarvioi) ja ero merkitseva.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
