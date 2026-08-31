# -*- coding: utf-8 -*-
"""GW-RECAP: yksi artefakti per gradattu kierros, "miten meni".

MIKSI (Villen pyynto 31.8.2026): *"saadaan aina peliviikkoa seuraavana
paivana postaus ulos missa kaydaan lapi miten meni predict, fantasy jne...
samoja kaavoja/teemoja jotka toistuisi. ei turhaa halya."*

Kadenssi ei ole tahan asti pitanyt siksi etta luvut ovat NELJASSA eri
tiedostossa (`gw_calls`, `model_squad_gw_scores`, `fpl_xp_gw_accuracy`,
ennustelokit), ja jokainen viikko on ollut kasin kaivamista. `fpl_notes.json`
-muistiopinta on ollut 10 vrk seisonut samasta syysta. Tama kokoaa ne kerran,
jotta viikoittainen tyo on kirjoittamista eika arkeologiaa.

🔴 KOLME REHELLISYYSSAANTOA, JOTKA OVAT KOKO PISTE

1. **Gradaamaton ei ole nolla.** Kesken oleva kierros (`provisional`) ja
   gradaamaton kutsu merkitaan sellaisiksi eivatka ne pudota juoksevaan
   riviin. Muisti: `nolla-ei-ole-sama-kuin-ei-tietoa`.
2. **`met = None` ei ole huti.** Se tarkoittaa ettei pelaajaa loytynyt
   FPL:n live-datasta - eri asia kuin "kutsu meni pieleen".
3. **Tappiot ovat mukana.** Juokseva rivi kantaa jokaisen kierroksen
   etumerkin. Tama on koko syy miksi track record on julkaisukelpoinen:
   voitot ovat uskottavia vain jos tappiot nakyvat samassa listassa.

Tama skripti EI kirjoita julkista tekstia. Se kokoaa luvut; muistio ja
postaus kirjoitetaan naista, ja ne kulkevat julkaisutarkistajan lapi.

AJO:  python -m scripts.build_gw_recap
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CALLS_PATH = ROOT / "data" / "gw_calls.json"
SQUAD_PATH = ROOT / "data" / "model_squad_gw_scores.json"
ACC_PATH = ROOT / "data" / "fpl_xp_gw_accuracy.json"
OUT_PATH = ROOT / "data" / "gw_recap.json"

# Segmentti nostetaan "kiinnostavimmaksi vaaraksi" vasta kun se on ISO
# suhteessa mallin omaan tarkkuuteen. Sama suhteellinen raja kuin
# autopilotin S10:ssa: absoluuttinen luku vanhenisi mallin parantuessa.
MIN_SEGMENT_N = 15
BIAS_X_MAE = 2.0


def _load(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def squad_rows(doc) -> list[dict]:
    rows = doc if isinstance(doc, list) else ((doc or {}).get("gameweeks") or [])
    return sorted([r for r in rows if isinstance(r, dict) and r.get("gw") is not None],
                  key=lambda r: int(r["gw"]))


def running_record(rows: list[dict]) -> dict:
    """Juokseva rivi VAIN lopullisesti gradatuista kierroksista.

    Provisionaalinen kierros jatetaan pois: kesken oleva luku vaihtuu viela,
    ja juokseva summa joka muuttuu jalkikateen ei ole track record vaan
    liikkuva maali.
    """
    lopulliset = [r for r in rows
                  if not r.get("provisional") and r.get("fpl_average") is not None
                  and r.get("points") is not None]
    if not lopulliset:
        return {"gameweeks": 0, "note": "ei lopullisesti gradattuja kierroksia"}
    diffs = [int(r["points"]) - int(r["fpl_average"]) for r in lopulliset]
    return {
        "gameweeks": len(lopulliset),
        "gw_list": [int(r["gw"]) for r in lopulliset],
        "total_diff": sum(diffs),
        "avg_diff": round(sum(diffs) / len(diffs), 1),
        "beat_average": sum(1 for d in diffs if d > 0),
        "below_average": sum(1 for d in diffs if d < 0),
        "per_gw": [{"gw": int(r["gw"]), "points": int(r["points"]),
                    "average": int(r["fpl_average"]), "diff": d}
                   for r, d in zip(lopulliset, diffs)],
    }


def _ennen(logged, deadline):
    """Kirjattiinko rivi ennen deadlinea. None = ei voi sanoa.

    Tama on julkaistavan vaitteen ydin, joten se LASKETAAN eika oleteta.
    """
    if not logged or not deadline:
        return None
    try:
        a = _dt.datetime.fromisoformat(str(logged).replace("Z", "+00:00"))
        b = _dt.datetime.fromisoformat(str(deadline).replace("Z", "+00:00"))
    except ValueError:
        return None
    return a < b


def calls_block(gw_row: dict) -> dict:
    """Kutsut osumineen. `logged_at` ja `deadline_utc` kulkevat mukana, koska
    ne ovat koko vaitteen todiste: rivi kirjoitettiin ENNEN deadlinea."""
    graded = (gw_row or {}).get("graded") or {}
    by_call = graded.get("by_call") or {}
    out = []
    for c in gw_row.get("calls") or []:
        nimi = c.get("call")
        g = by_call.get(nimi) or {}
        out.append({
            "call": nimi,
            "web_name": c.get("web_name"),
            "team_short": c.get("team_short"),
            "criterion": c.get("criterion"),
            "predicted": c.get("value"),
            "points": g.get("points"),
            "started": g.get("started"),
            # None = pelaajaa ei loytynyt live-datasta. EI sama kuin huti.
            "met": g.get("met"),
        })
    return {
        "logged_at": gw_row.get("logged_at"),
        "deadline_utc": gw_row.get("deadline_utc"),
        "logged_before_deadline": _ennen(gw_row.get("logged_at"),
                                         gw_row.get("deadline_utc")),
        "graded": bool(graded),
        "provisional": bool(graded.get("provisional")) if graded else None,
        "hits": sum(1 for c in out if c["met"] is True),
        "misses": sum(1 for c in out if c["met"] is False),
        "ungraded": sum(1 for c in out if c["met"] is None),
        "calls": out,
    }


def headline_miss(acc_row):
    """Se yksi kiinnostavin asia joka meni vaarin.

    Ei suurin virhe absoluuttisesti vaan suurin SUHTEESSA mallin omaan
    tarkkuuteen: segmentti jonka harha on iso kokonais-MAE:hen nahden.
    Pieni segmentti on kohinaa, ei loydos.
    """
    if not acc_row:
        return None
    mae = acc_row.get("mae")
    if not mae:
        return None
    paras = None
    for lohko, etuliite in (("by_class", ""), ("by_pos_stats", "pos:")):
        for nimi, t in (acc_row.get(lohko) or {}).items():
            if not isinstance(t, dict):
                continue
            n, bias = t.get("n"), t.get("bias")
            if not isinstance(n, int) or n < MIN_SEGMENT_N or bias is None:
                continue
            suhde = abs(float(bias)) / float(mae)
            if suhde < BIAS_X_MAE:
                continue
            if paras is None or suhde > paras["x_mae"]:
                paras = {"segment": etuliite + str(nimi), "n": n,
                         "bias": round(float(bias), 2),
                         "mae": round(float(t.get("mae") or 0), 2),
                         "x_mae": round(suhde, 1),
                         "direction": ("aliarvio" if float(bias) > 0
                                       else "yliarvio")}
    return paras


def build(calls_doc, squad_doc, acc_doc, now: _dt.datetime) -> dict:
    rows = squad_rows(squad_doc)
    by_gw_calls = {int(g["gw"]): g for g in ((calls_doc or {}).get("gameweeks") or [])
                   if g.get("gw") is not None}
    by_gw_acc = {int(g["gw"]): g for g in ((acc_doc or {}).get("gameweeks") or [])
                 if g.get("gw") is not None}

    lahteet = {
        "gw_calls": calls_doc is not None,
        "model_squad_gw_scores": squad_doc is not None,
        "fpl_xp_gw_accuracy": acc_doc is not None,
    }
    gws = []
    for r in rows:
        gw = int(r["gw"])
        c = by_gw_calls.get(gw)
        a = by_gw_acc.get(gw)
        pts, avg = r.get("points"), r.get("fpl_average")
        gws.append({
            "gw": gw,
            "provisional": bool(r.get("provisional")),
            "squad": {
                "points": pts,
                "average": avg,
                "diff": (int(pts) - int(avg)
                         if pts is not None and avg is not None else None),
                "bench_points": r.get("bench_points"),
                "transfer_cost": r.get("transfer_cost"),
                "chip": r.get("active_chip"),
                "captain_id": r.get("captain_id"),
                "captain_points_added": r.get("captain_points_added"),
                "graded_at": r.get("graded_at"),
            },
            "calls": calls_block(c) if c else None,
            "accuracy": ({"mae": a.get("mae"), "n": a.get("n"),
                          "bias": a.get("bias")} if a else None),
            "headline_miss": headline_miss(a),
        })
    return {
        "meta": {
            "generated_at": now.replace(microsecond=0).isoformat(),
            "sources": lahteet,
            # Puuttuva lahde EI ole tyhja tulos: kuluttajan on nahtava ero.
            "complete": all(lahteet.values()),
        },
        "running": running_record(rows),
        "gameweeks": gws,
    }


def main() -> int:
    doc = build(_load(CALLS_PATH), _load(SQUAD_PATH), _load(ACC_PATH),
                _dt.datetime.now(_dt.timezone.utc))
    if not doc["gameweeks"]:
        print("::warning::ei gradattuja kierroksia - ei kirjoiteta recapia.")
        return 0
    OUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    r = doc["running"]
    print("gw_recap.json: {} kierrosta, juokseva {} lopullista, {:+d} p yhteensa, "
          "yli keskiarvon {}x".format(
              len(doc["gameweeks"]), r.get("gameweeks", 0),
              r.get("total_diff", 0), r.get("beat_average", 0)))
    if not doc["meta"]["complete"]:
        puuttuu = [k for k, v in doc["meta"]["sources"].items() if not v]
        print("::warning::lahteita puuttuu: " + ", ".join(puuttuu)
              + " - recap on vaillinainen, ei tyhja.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
