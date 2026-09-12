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
    """Mittaa SIVUN populaatiolla: projisoitu >= raja JA pelasi.

    12.9 portti mittasi etta ilmaissivu `/fpl/minutes-accuracy` julkaisee
    sarakkeen "Overshoot, 80+ starters" populaatiosta `prior >= 80 AND
    played`, ja `/fpl/note/we-measured-our-own-worst-column` sanoo aareen
    etta "which is where the 10 minutes quoted there comes from". Jos otamme
    mukaan pelaajat jotka eivat pelanneet minuuttiakaan, keskiarvo on 13.8;
    ne kuusi pelaajaa (ka +82.5) tuottavat 27 % koko harhasta. Copy sanoi
    14 ja tarkistusreitti sanoi 10 (muisti: lause-ja-luku-eri-lahteesta).

    Populaatio on nyt sama kuin sivulla. `kaikki`-lohko jaa nakyviin, jotta
    ero on mitattavissa eika katoa.
    """
    erot, kaikki_erot, foldit = [], [], []
    for a, b in FOLDS:
        pred, act, _pos = fold_pairs(a, b)
        m = pred >= raja
        e_kaikki = pred[m] - act[m]
        pelasi = m & (act > 0)
        e = pred[pelasi] - act[pelasi]
        erot.append(e)
        kaikki_erot.append(e_kaikki)
        foldit.append({"fold": f"{a}->{b}", "n": int(pelasi.sum()),
                       "mean": round(float(e.mean()), 1),
                       "median": round(float(np.median(e)), 1),
                       "n_ei_pelannut": int(m.sum() - pelasi.sum())})
    e = np.concatenate(erot)
    ek = np.concatenate(kaikki_erot)
    return {
        "population": "prior >= threshold AND played (sama kuin /fpl/minutes-accuracy)",
        "kaikki_mukaan_lukien_ei_pelanneet": {
            "n": int(len(ek)), "mean": round(float(ek.mean()), 1),
            "median": round(float(np.median(ek)), 1),
        },
        "threshold_minutes": raja,
        "n": int(len(e)),
        "mean": round(float(e.mean()), 1),
        "median": round(float(np.median(e)), 1),
        "p25": round(float(np.percentile(e, 25)), 1),
        "p75": round(float(np.percentile(e, 75)), 1),
        "share_within_5": round(float((np.abs(e) <= OSUMA_RAJA).mean()), 3),
        # Copy sanoo "more than 30", joten mitta on tiukka > eika >=.
        "share_over_30": round(float((e > HANTA_RAJA).mean()), 3),
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
