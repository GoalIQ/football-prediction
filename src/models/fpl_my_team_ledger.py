"""MY TEAM LEDGER: sinun joukkueesi ennuste vs toteuma kauden yli (25.8.2026).

Villen kysymys: *"pitaisko fantasyyn laittaa joku erillinen my team missa oikeet
pisteet vrt mita ennustettu"*.

Erotus muihin pintoihin:
  rate_teamin "Model vs actual"  = YKSI kierros, pelaajatasolla
  model-race                     = MALLIN rivi vs sinun rivisi
  tama                           = SINUN rivisi ennuste vs toteuma, KUMULOITUVA

🔴 VERTAILUKOHTA ON DEADLINE-FREEZE, EI ELAVA PROJEKTIO. Elava xP liikkuu kohti
toteumaa kierroksen aikana (minuuttimalli paivittyy kesken ottelun), joten
elavaa vastaan vertaaminen saisi mallin nayttamaan tarkemmalta kuin se on.
Tama on kirjattu vika: 22.8 "Model vs actual" vertasi elavaan xP:hen ja se
korjattiin deadline-freezella. Sama sopimus tassa.

🔴 KIERROS JOLLE EI OLE FREEZEA JATETAAN POIS, JA MAARA KERROTAAN. Nolla ei ole
sama kuin "ei tietoa": ilman freezea emme tieda mita ennustimme, ja 0,0
projektiona nayttaisi silta etta malli odotti nollaa. `missing_freeze_gws`
kertoo mitka jaivat pois.

🔴 KERTOIMET MUKANA MOLEMMILLA PUOLILLA. Toteutuneet kierrospisteet sisaltavat
kapteenin tuplauksen ja jattavat penkin nollaan, joten projektion on tehtava
sama: `sum(frozen_xp[pid] * multiplier)`. Ilman kerrointa vertailu olisi
15 pelaajan summa vastaan 11 pelaajan tulos.
"""
from __future__ import annotations

from typing import Any

from src.models import fpl_actuals
from src.models.fpl_model_race import (ROW_AWAITING_CHECK, ROW_FINAL,
                                       ROW_IN_PROGRESS, ROW_UNKNOWN)

NOTE_NO_ENTRY = (
    "Add your FPL team ID to see your own projected points against what you "
    "actually scored."
)
CODE_NO_ENTRY = "ledger.note.no_entry"
NOTE_NOT_STARTED = (
    "Your ledger starts once a gameweek has been played with a projection "
    "frozen before its deadline."
)
CODE_NOT_STARTED = "ledger.note.not_started"


def _projected_for(picks: dict, frozen: dict[int, float]) -> tuple[float, int]:
    """(projisoidut pisteet, montako riviä loytyi freezesta).

    Kerroin mukaan: penkki 0, pelaava 1, kapteeni 2, TC 3 - sama kohtelu kuin
    toteutuneissa pisteissa.

    🔴 Pelaaja jota EI ole freezessa ei ole nolla vaan tuntematon. Palautetaan
    loytyneiden maara, jotta kutsuja voi kertoa kattavuuden sen sijaan etta
    esittaisi vajaan summan taytena.
    """
    total = 0.0
    hits = 0
    for p in picks.get("picks") or []:
        pid = p.get("element")
        xp = frozen.get(pid)
        if xp is None:
            continue
        hits += 1
        total += float(xp) * int(p.get("multiplier", 0))
    return round(total, 2), hits


def _average(v: Any) -> int | None:
    """FPL:n kierroskeskiarvo tai None. 0 ja puuttuva = ei tietoa (FPL
    antaa 0:n kierrokselle jota ei ole viela laskettu)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
        return None
    return int(v)


def build_ledger(entry_history: dict | None,
                 picks_by_gw: dict[int, dict] | None,
                 provisional_gws: list[int] | None = None,
                 states: dict[int, str] | None = None,
                 averages: dict[int, Any] | None = None) -> dict:
    """Puhdas ydin: FPL:n historia + kierrosvalinnat -> ledger-payload.

    `picks_by_gw` on {gw: picks-vastaus}. Kutsuja hakee ne; tama moduuli ei
    tee verkkokutsuja (testattavuus + sama kuvio kuin fpl_model_race).

    `states` {gw: fpl_model_race.row_state} provisionaalisille kierroksille.
    🔴 26.9 (julkaisutarkistaja MP-14 B3): KESKEN OLEVA kierros ('in_progress')
    jaetaan pois riveista ja summista ja kerrotaan (`in_progress_gws`).
    Muuten GW:n deadlinen jalkeen koko kierroksen jaadytetty projektio
    (~55) verrattiin osittaisiin pisteisiin: ~-55 pylvas 3-4 paivaa joka
    kierroksella. Sama kolmen tilan lukija kuin model-racessa.

    `averages` {gw: FPL:n average_entry_score}. 🔴 B4: ilman vertailukohtaa
    9/10 satunnaista entrya nakyi projektion ylapuolella (mediaani ~+9 p/GW),
    eli plus oli oletustila eika signaali. Summa annetaan vain jos JOKAISELLE
    mukana olevalle kierrokselle on keskiarvo (osittainen summa ei kelpaa).
    """
    if entry_history is None:
        return {
            "meta": {"available": False, "graded_gws": 0,
                     "note": NOTE_NO_ENTRY, "note_code": CODE_NO_ENTRY},
            "totals": {"projected": None, "actual": None, "diff": None},
            "gameweeks": [],
        }

    prov = set(provisional_gws or [])
    tilat = states or {}
    keskiarvot = averages or {}
    rows = []
    puuttuvat: list[int] = []
    kesken: list[int] = []
    proj_sum = 0.0
    act_sum = 0
    cum = 0.0

    for h in sorted((entry_history.get("current") or []),
                    key=lambda r: int(r.get("event") or 0)):
        gw = int(h.get("event") or 0)
        if not gw:
            continue
        if gw in prov and tilat.get(gw) == ROW_IN_PROGRESS:
            kesken.append(gw)
            continue
        frozen = fpl_actuals.frozen_xp_for(gw)
        if not frozen:
            # 🔴 Ei freezea -> emme tieda mita ennustimme. Pois, ja kerrotaan.
            puuttuvat.append(gw)
            continue
        picks = (picks_by_gw or {}).get(gw)
        if picks is None:
            puuttuvat.append(gw)
            continue

        projected, hits = _projected_for(picks, frozen)
        # 🔴 Portin 11. kierros: NETTO. `entry_history.points` on brutto, ja
        # sen vertaaminen jaadytettyyn projektioon antoi kayttajalle hitin
        # verran etumatkaa kumulatiivisessa "sina vs malli" -rivissa.
        # Mitattu 7.9: seuratuilla entryilla 0 hittikierrosta talla
        # kaudella, joten julkaistu luku ei liiku.
        actual = int(h.get("points") or 0) - int(h.get("event_transfers_cost") or 0)
        diff = round(actual - projected, 2)
        proj_sum += projected
        act_sum += actual
        cum = round(cum + diff, 2)
        rows.append({
            "gw": gw,
            "projected": projected,
            "actual": actual,
            "diff": diff,
            "cumulative_diff": cum,
            # Kuinka moni 15:sta loytyi freezesta. < 15 = vajaa kattavuus,
            # ja se on kerrottava eika piilotettava.
            "players_matched": hits,
            "bench_points": int(h.get("points_on_bench") or 0),
            "transfer_cost": int(h.get("event_transfers_cost") or 0),
            "provisional": gw in prov,
            # final / awaiting_check / unknown (in_progress on jo pois).
            "state": (ROW_FINAL if gw not in prov
                      else tilat.get(gw) if tilat.get(gw) in (ROW_AWAITING_CHECK, ROW_UNKNOWN)
                      else ROW_UNKNOWN),
            "fpl_average": _average(keskiarvot.get(gw)),
        })

    if not rows:
        return {
            "meta": {"available": False, "graded_gws": 0,
                     "missing_freeze_gws": puuttuvat,
                     "in_progress_gws": kesken,
                     "note": NOTE_NOT_STARTED,
                     "note_code": CODE_NOT_STARTED},
            "totals": {"projected": None, "actual": None, "diff": None},
            "gameweeks": [],
        }

    return {
        "meta": {
            "available": True,
            "graded_gws": len(rows),
            # 🔴 Kierrokset jotka jaivat pois. Tyhja lista = tayysi kattavuus.
            "missing_freeze_gws": puuttuvat,
            "in_progress_gws": kesken,
            "provisional_gws": sorted(g for g in prov
                                      if g in {r["gw"] for r in rows}),
            "basis": ("projection frozen before each deadline, never the live "
                      "one"),
            "note": None,
            "note_code": None,
        },
        "totals": {
            "projected": round(proj_sum, 2),
            "actual": act_sum,
            "diff": round(act_sum - proj_sum, 2),
            "fpl_average": (sum(r["fpl_average"] for r in rows)
                            if all(r["fpl_average"] is not None for r in rows)
                            else None),
        },
        "gameweeks": rows,
    }
