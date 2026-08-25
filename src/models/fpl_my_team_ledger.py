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

from src.models import fpl_actuals

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


def build_ledger(entry_history: dict | None,
                 picks_by_gw: dict[int, dict] | None,
                 provisional_gws: list[int] | None = None) -> dict:
    """Puhdas ydin: FPL:n historia + kierrosvalinnat -> ledger-payload.

    `picks_by_gw` on {gw: picks-vastaus}. Kutsuja hakee ne; tama moduuli ei
    tee verkkokutsuja (testattavuus + sama kuvio kuin fpl_model_race).
    """
    if entry_history is None:
        return {
            "meta": {"available": False, "graded_gws": 0,
                     "note": NOTE_NO_ENTRY, "note_code": CODE_NO_ENTRY},
            "totals": {"projected": None, "actual": None, "diff": None},
            "gameweeks": [],
        }

    prov = set(provisional_gws or [])
    rows = []
    puuttuvat: list[int] = []
    proj_sum = 0.0
    act_sum = 0
    cum = 0.0

    for h in sorted((entry_history.get("current") or []),
                    key=lambda r: int(r.get("event") or 0)):
        gw = int(h.get("event") or 0)
        if not gw:
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
        actual = int(h.get("points") or 0)
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
        })

    if not rows:
        return {
            "meta": {"available": False, "graded_gws": 0,
                     "missing_freeze_gws": puuttuvat,
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
        },
        "gameweeks": rows,
    }
