"""Gradaa mallin oma FPL-rivi kierroksittain -> data/model_squad_gw_scores.json.

🔴 MIKSI TAMA ON OLEMASSA (loydos 25.8.2026)
`/api/fantasy/model-race` lukee tata tiedostoa, ja jonossa oli useita rivejä
joiden heratysehto oli "GW1 gradattu" / `model-race.meta.graded_gws >= 1`.
Mitattu 25.8: tiedostoa EI OLLUT OLEMASSA eika mikaan repossa kirjoittanut
sita. Este ei siis ollut FPL:n `finished`-lippu vaan puuttuva gradaaja.
Endpoint vastasi "First scores land once GW1 finishes" viela senkin jalkeen
kun GW1 oli pelattu, eli selite nimesi vaaran mekanismin.

LAHDE: mallin luvut otetaan FPL:n OMASTA vastauksesta (entry history + picks),
ei lasketa uudelleen. Rivin lukitus ennen deadlinea on todistettu erikseen
(`verify_model_entry_matches_freeze.py` + git-historia), joten tama skripti ei
vastaa siita - se vain lukee toteuman.

🔴 PROVISIONAALISUUS. FPL kaantaa `event.finished` ja `data_checked` vasta
tuntien viiveella viimeisen ottelun jalkeen (mitattu 25.8 klo 07 UTC: GW1
pelattu 21.-24.8, molemmat liput yha False, kaikki 10 ottelua
`finished_provisional: true`). Odottaminen `data_checked`:ia tarkoittaisi ettei
kierrosta nay tuotteessa vuorokauteen sen paattymisen jalkeen.

Ratkaisu: gradataan kun KAIKKI kierroksen ottelut ovat `finished_provisional`,
ja rivi merkitaan `"provisional": true` kunnes `data_checked` kaantyy. Seuraava
ajo gradaa rivin uudelleen ja poistaa lipun. Luku siis nakyy heti, mutta se ei
esiinny lopullisena. 🔴 Lippu on kannettava pintaan asti - provisionaalinen
luku esitettyna lopullisena on tasan se lupausrikko jota vastaan koko tuote
myydaan.

🔴 EI GH-RUNNERILTA (FPL-esto GitHubin IP-avaruudesta). Render tai paikallinen.

Ajo:
    python scripts/grade_model_squad.py            # kaikki gradattavat GW:t
    python scripts/grade_model_squad.py --gw 1     # vain yksi
    python scripts/grade_model_squad.py --dry-run  # ei kirjoita
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data import fpl_api  # noqa: E402
from src.models.model_squad_scores import (  # noqa: E402
    ENTRY_SCORES_PATH, SOURCE_ENTRY, load_gw_scores, validate_gw_scores)

# Sama lahde ja sama env-ohitus kuin verify_model_entry_matches_freeze.py:52,
# jotta mallin rivi ei voi olla eri kahdessa skriptissa.
ENTRY_ID = int(os.environ.get("FPL_MODEL_ENTRY_ID", "116920"))
# 🔴 KAKSI-GRADERIA-YKSI-TIEDOSTO (17.9.2026): polku tulee lukijamoduulista,
# jossa entry- ja freeze-sarjalla on ERI tiedosto. Tama on kanoninen,
# julkinen sarja (Villen paatos 12.9: entry). Freeze-graderi kirjoittaa
# omaansa (FROZEN_SCORES_PATH), eika lukija anna kummallekaan toisen sarjaa.
OUT_PATH = ENTRY_SCORES_PATH


def _gw_status(boot: dict, fixtures: list[dict]) -> dict[int, dict]:
    """Alias: src.models.fpl_gw_finality.gw_fixture_status (siirretty 26.9, MP-14)."""
    from src.models.fpl_gw_finality import gw_fixture_status
    return gw_fixture_status(boot, fixtures)

def _grade_gw(gw: int, history_by_gw: dict[int, dict], status: dict) -> dict:
    """Yhden kierroksen rivi. Kaikki luvut FPL:n omasta vastauksesta."""
    h = history_by_gw[gw]
    picks = fpl_api.fetch_entry_picks(ENTRY_ID, gw, force=status["provisional"])
    if picks is None:
        raise RuntimeError(
            f"entry {ENTRY_ID}: ei picks-rivia GW{gw}:lle. Malli ei ollut "
            f"mukana talla kierroksella, tai entry-ID on vaara."
        )

    captain_id = None
    captain_mult = 1
    for p in picks.get("picks") or []:
        if p.get("is_captain"):
            captain_id = p["element"]
            captain_mult = p.get("multiplier", 2)

    # Kapteenin TUOMA lisa = hanen pisteensa x (multiplier - 1). Elava
    # pistedata haetaan kierroksen live-vastauksesta.
    captain_added = None
    if captain_id is not None:
        try:
            live = fpl_api.fetch_event_live(gw, force=status["provisional"])
            pts = {e["id"]: (e.get("stats") or {}).get("total_points")
                   for e in live.get("elements") or []}
            base = pts.get(captain_id)
            if base is not None:
                captain_added = int(base) * (int(captain_mult) - 1)
        except Exception:
            # 🔴 Poikkeus -> None, EI nolla. Nolla vaittaisi etta kapteeni ei
            # tuonut mitaan; None sanoo ettemme tieda.
            captain_added = None

    return {
        "gw": gw,
        # Rivin provenienssi (17.9.2026). Lukija tulkitsee source-ttoman rivin
        # legacy-entryksi vain entry-muotoisena; uusi rivi sanoo sen itse.
        "source": SOURCE_ENTRY,
        # 🔴 PORTIN 15. KIERROS: kommentti oli VÄÄRÄ ja se levisi lukuun asti.
        # `entry_history.points` on BRUTTO, ei "siirtokustannukset jo mukana"
        # (verifioitu FPL:n API:sta 7.9: entry 12345 GW3 points 70, cost 8,
        # kausisumma 87 -> 149 eli 62 = 70 - 8).
        #
        # Korjasin 11.-14. kierroksella KAYTTAJAN puolen kaikilla pinnoilla ja
        # jatin MALLIN puolen bruttoon. Mitattu: hittikierroksella malli
        # nayttaisi 70 kun sen oma FPL-sivu sanoo 62, eli malli voittaisi
        # oman hittinsa verran. Ja mallin entry on JULKINEN (fpl.html:606
        # nimeaa sen, TeamPitchManager painaa entry-ID:n korttiin), joten
        # lukija voi katsoa.
        "points": h["points"],
        "points_net": h["points"] - (h["transfer_cost"] or 0),
        "bench_points": h["bench"],
        "transfer_cost": h["transfer_cost"],
        "fpl_average": status["fpl_average"],
        "captain_id": captain_id,
        "captain_points_added": captain_added,
        "active_chip": picks.get("active_chip"),
        "autosubs": [
            {"in": a.get("element_in"), "out": a.get("element_out")}
            for a in (picks.get("automatic_subs") or [])
        ],
        "provisional": status["provisional"],
        "all_fixtures_played": status["all_fixtures_played"],
        "graded_at": _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0).isoformat(),
    }


def build(only_gw: int | None = None, verbose: bool = True) -> dict:
    boot = fpl_api.fetch_bootstrap(max_age_s=600)
    fixtures = fpl_api.fetch_fixtures(max_age_s=600)
    status = _gw_status(boot, fixtures)

    history = fpl_api.fetch_entry_history(ENTRY_ID)
    history_by_gw = {
        int(r["event"]): {
            "points": int(r.get("points") or 0),
            "bench": int(r.get("points_on_bench") or 0),
            "transfer_cost": int(r.get("event_transfers_cost") or 0),
        }
        for r in (history.get("current") or [])
        if r.get("event") is not None
    }

    # Sailyta aiemmin gradatut rivit: lopullinen rivi ei saa muuttua takaisin
    # provisionaaliseksi jos FPL:n vastaus hetkellisesti puuttuu.
    #
    # 🔴 YKSI LUKIJA (17.9.2026). Aiempi raaka `json.loads` piti MINKA TAHANSA
    # rivin, ja rivi jolla ei ole `provisional`-kenttaa (freeze-graderin rivi)
    # luettiin alla "jo lopulliseksi" - sekaprovenienssi olisi jaanyt sarjaan
    # pysyvasti. `load_gw_scores` kaatuu jos sarjassa on kahta provenienssia
    # tai jos se ei ole entry-sarja, ja kaatuu myos rikkinaiseen tiedostoon
    # (vanha koodi nielaisi sen ja olisi ylikirjoittanut sarjan tyhjasta).
    # Puuttuva tiedosto on tyhja sarja. Legacy-rivit (GW1-GW4 ilman
    # source-kenttaa) hyvaksytaan entryna eika niita muuteta tassa.
    prev = load_gw_scores(OUT_PATH, source=SOURCE_ENTRY)
    existing: dict[int, dict] = {
        int(r["gw"]): r for r in (prev.get("gameweeks") or [])}
    _prev_generated_at = (prev.get("meta") or {}).get("generated_at")
    if _prev_generated_at is None:
        _prev_generated_at = (_dt.datetime.now(_dt.timezone.utc)
                              .replace(microsecond=0).isoformat())

    rows: dict[int, dict] = dict(existing)
    for gw, st in sorted(status.items()):
        if only_gw is not None and gw != only_gw:
            continue
        if not st["gradable"]:
            continue
        if gw not in history_by_gw:
            if verbose:
                print(f"   GW{gw}: entrylla ei riviä, ohitetaan")
            continue
        # Jo lopullisesti gradattu -> ei haeta uudelleen.
        old = existing.get(gw)
        if old is not None and not old.get("provisional") and not st["provisional"]:
            if verbose:
                print(f"   GW{gw}: jo lopullinen, ohitetaan")
            continue
        uusi = _grade_gw(gw, history_by_gw, st)
        # 🔴 `graded_at` on "milloin TAMA RIVI gradattiin", ei "milloin skripti
        # viimeksi ajoi". Jos sisalto on identtinen, sailytetaan vanha leima.
        # Ilman tata 6 h cron committaisi joka ajolla vaikka mikaan ei muuttunut
        # (mitattu 25.8: ensimmainen ajo tuotti committin jossa diff oli PELKAT
        # aikaleimat), ja git-historia lakkaisi kertomasta milloin luku muuttui.
        if old is not None:
            vertailu = {k: v for k, v in uusi.items() if k != "graded_at"}
            vanha_vertailu = {k: v for k, v in old.items() if k != "graded_at"}
            if vertailu == vanha_vertailu:
                uusi["graded_at"] = old.get("graded_at", uusi["graded_at"])
        rows[gw] = uusi
        if verbose:
            flag = " (PROVISIONAALINEN)" if st["provisional"] else ""
            print(f"   GW{gw}: {rows[gw]['points']} p, keskiarvo "
                  f"{st['fpl_average']}{flag}")

    ordered = [rows[g] for g in sorted(rows)]
    # Sama syy kuin `graded_at`:lla: jos yksikaan rivi ei muuttunut, tiedosto ei
    # ole "generoitu uudelleen" vaan sama tiedosto. Muuttuva leima tekisi
    # jokaisesta cron-ajosta committin.
    muuttui = ordered != [existing[g] for g in sorted(existing)]
    generated_at = (
        _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()
        if muuttui or not existing
        else _prev_generated_at
    )
    doc = {
        "meta": {
            "entry_id": ENTRY_ID,
            "source": "FPL entry history + picks (not recomputed)",
            # Sarjan provenienssi koneluettavasti (17.9.2026): tama on
            # entry-sarja, ja lukija kaatuu jos rivit sanovat muuta.
            "series_source": SOURCE_ENTRY,
            "generated_at": generated_at,
            "provisional_gws": [r["gw"] for r in ordered if r.get("provisional")],
        },
        "gameweeks": ordered,
    }
    # 🔴 PORTTI ENNEN KIRJOITUSTA. Tama doc menee kahta reittia levylle:
    # main() kirjoittaa sen paikallisesti, ja Render palauttaa sen
    # `model-squad-grade.yml`:n runnerille joka committaa sen gitiin.
    # Validointi on siksi TASSA eika main():ssa - kumpikaan reitti ei voi
    # ohittaa sita.
    return validate_gw_scores(doc, source=SOURCE_ENTRY)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gw", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    out = build(args.gw, verbose=not args.quiet)
    if args.dry_run:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    prov = out["meta"]["provisional_gws"]
    print(f"[ok] {OUT_PATH.name}: {len(out['gameweeks'])} kierrosta"
          + (f", provisionaalisia: {prov}" if prov else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
