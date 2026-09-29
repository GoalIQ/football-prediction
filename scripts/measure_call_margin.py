"""Mittaa suosikin nimeämisen marginaali omasta track recordista.

Kirjoittaa `data/call_margin.json`, jota `src/models/call_margin.call_state`
lukee. Ajetaan accuracy-log-workflow'ssa reconcilen jälkeen ja ennen
build_prediction_pages-askelta, jotta sivut ja API lukevat saman luvun.

    python -m scripts.measure_call_margin           # kirjoita artefakti
    python -m scripts.measure_call_margin --check   # älä kirjoita, tulosta

Lähde on `data/prediction_log.json` (gradatut rivit). Ei ulkoista dataa:
tämä on mallin oma osumatarkkuus eron funktiona, ei vertailu markkinaan.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.call_margin import MARGIN_PATH, measure_margin  # noqa: E402

LOG_PATH = PROJECT_ROOT / "data" / "prediction_log.json"


def build(log_path: Path = LOG_PATH) -> dict:
    doc = json.loads(log_path.read_text(encoding="utf-8"))
    rows = doc.get("predictions") or []
    from src.models.accuracy import counts_in_record, model_of
    graded = [r for r in rows if counts_in_record(r)]
    # 29.9.2026 (TRACK-RECORD-NIMIKKEET kohta 5): marginaali koskee
    # seuraotteluita (ottelusivut, /api/predict, apit), joten se mitataan
    # VAIN seuramallin riveista. Lokissa on kesan 56 MM-rivia
    # maajoukkuemallista, ja niilla on voittotodennakoisyys, joten ennen
    # tata ne olivat mukana: 609 -> 48 %, seuramalli yksin 553 -> 49 %.
    club = [r for r in graded if model_of(r.get("competition")) == "club"]
    out = measure_margin(club)
    out["scope"] = "club"
    # Heron luku (kaikki gradatut), jotta sivu voi nimeta eron.
    out["n_graded_all"] = len(graded)
    maa = [r for r in graded if model_of(r.get("competition")) == "national"]
    out["excluded"] = {
        "national_model": len(maa),
        "national_competitions": sorted({str(r.get("competition")) for r in maa}),
        # Luokittelematon kilpailukoodi (esim. uusi seurakilpailu ennen kuin
        # CLUB_COMPETITIONS paivitetaan): ei nimeta maajoukkuemalliksi, sivu
        # putoaa syyttomaan lauseeseen (julkaisutarkistaja 29.9).
        "unclassified": sum(1 for r in graded if model_of(r.get("competition")) is None),
        # Seurariveja joilla ei ole voittotodennakoisyytta (measure_margin
        # ohittaa ne): club-syotteen kaikki miinus kaytetyt.
        "no_win_probability": len(club) - out["n_graded"],
    }
    out["measured_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    out["source"] = "data/prediction_log.json"
    out["_comment"] = (
        "Luetaan src/models/call_margin.call_state():lla. Kun |p_home - p_away| "
        "< margin_pp, mikaan pinta ei nimea suosikkia. Alla olevat luokat ovat "
        "se mittaus josta luku johdetaan."
    )
    return out


def main(argv: list[str]) -> int:
    out = build()
    summary = (
        f"call_margin: margin_pp={out['margin_pp']} n_graded={out['n_graded']} "
        f"below={out['n_below_margin']} hit_below={out['hit_pct_below_margin']}%"
    )
    print(summary)
    if "--check" in argv:
        for r in out["buckets"]:
            print(f"  {r['gap_from_pp']:>3}-{r['gap_to_pp']:<3} n={r['n']:4} "
                  f"hit={r['hit_pct']} draw={r['draw_pct']} decisive_hit={r['decisive_hit_pct']}")
        return 0
    MARGIN_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(f"wrote {MARGIN_PATH.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
