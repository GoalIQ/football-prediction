"""Mittaa kauden alun minuuttiprojektion harha ja kirjoita se artefaktiksi.

MIKSI OMA SKRIPTI. Luku "about 14 minutes lower" elaa kolmella pinnalla
(`goaliq-app/lib/i18n/en.ts` kaksi avainta + pro-SPA:n `XpTable.svelte`) ja
jokainen niista on kasin kirjoitettu. Kolme kopiota samasta vaitteesta
eriytyy hiljaa, ja luku on sitaatti mittauksesta jota kukaan ei aja
uudelleen. Tama skripti tekee mittauksesta artefaktin, jolloin portti voi
sitoa copyn LAHTEESEEN eika toiseen pintaan.

12.9.2026 mittaus paljasti myos etta luku on oikea mutta lause on vaara:
keskiarvo +13.8 min, **mediaani +0.0 min**. Keskiarvon tekee hanta (21 %
pelaajista >= 30 min pielessa), kun taas 39 % osuu viiden minuutin sisaan.
Copy luki keskiarvon TYYPILLISENA tapauksena, ja se ei pida paikkaansa.

Ajo: `.venv/Scripts/python.exe scripts/measure_preseason_minutes_bias.py`
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.calibrate_preseason_minutes import FOLDS, fold_pairs  # noqa: E402

ULOS = ROOT / "data" / "preseason_minutes_bias.json"
KARKI_RAJA = 80  # projisoitu minuuttimaara jota copy koskee
OSUMA_RAJA = 5   # "osuu kohdalleen" = +- 5 min
HANTA_RAJA = 30  # "pahasti pielessa"


def mittaa(raja: int = KARKI_RAJA) -> dict:
    erot, foldit = [], []
    for a, b in FOLDS:
        pred, act, _pos = fold_pairs(a, b)
        m = pred >= raja
        e = pred[m] - act[m]
        erot.append(e)
        foldit.append({"fold": f"{a}->{b}", "n": int(m.sum()),
                       "mean": round(float(e.mean()), 1),
                       "median": round(float(np.median(e)), 1)})
    e = np.concatenate(erot)
    return {
        "threshold_minutes": raja,
        "n": int(len(e)),
        "mean": round(float(e.mean()), 1),
        "median": round(float(np.median(e)), 1),
        "p25": round(float(np.percentile(e, 25)), 1),
        "p75": round(float(np.percentile(e, 75)), 1),
        "share_within_5": round(float((np.abs(e) <= OSUMA_RAJA).mean()), 3),
        "share_over_30": round(float((e >= HANTA_RAJA).mean()), 3),
        "folds": foldit,
        # EI rakennusaikaa: se tuottaisi tyhjan commitin joka ajolla
        # (muisti: rakennusaika-artefaktissa-tuottaa-tyhjan-commitin).
    }


def main() -> int:
    tulos = mittaa()
    ULOS.write_text(json.dumps(tulos, indent=2) + "\n", encoding="utf-8")
    print(f"{ULOS.relative_to(ROOT)}: n={tulos['n']} ka={tulos['mean']:+} "
          f"mediaani={tulos['median']:+} "
          f"osuu+-5={tulos['share_within_5']:.0%} "
          f"yli30={tulos['share_over_30']:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
