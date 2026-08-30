"""GW-CALLS-LOKI (28.8.2026): mallin julkiset kierroskutsut lokiin ennen
deadlinea, gradaus kierroksen jalkeen samaan tiedostoon.

MIKSI: Wolfylle luvattiin "every call gets logged before the deadline so it
can be graded after", ja standouts-kortti (Captain pick / Ceiling / Safest /
The gamble) lisasi toisen julkisen kutsuvirran jota mikaan ei kirjannut.
Mallin oman rivin kapteeni oli freezessa, mutta kortin nelja nimea elivat vain
PNG:ssa: jos kortti postattiin ja luvut liikkuivat seuraavassa refreshissa,
kutsua ei voinut enaa jaljittaa.

SAANNOT
- Yksi rivi per GW, `data/gw_calls.json`, versioitu (ei outputs/).
- Kirjaus on idempotentti ENNEN deadlinea: sama GW paivitetaan (kortti
  regeneroidaan postaushetkella, ja loki seuraa viimeisinta korttia).
- DEADLINE-SNAPSHOT (29.8): rivi kirjoitetaan uudelleen tuoreella
  projektiolla T-2 h -ikkunassa (pressien jalkeen, xMins/start% paivittyneet),
  erillaan siirtofreezesta (T-24 h). Kaksi aikaleimaa: `logged_at` on
  ENSIMMAINEN kirjaus eika muutu koskaan, `updated_at` on VIIMEISIN kirjaus
  ennen deadlinea. `source.projection_generated_at` seuraa viimeisinta.
  Paivitys ei pudota kutsuja joita se ei itse tuota (projected_xi tulee
  kortista): ne sailyvat rivilla.
- Deadlinen JALKEEN kirjaus on kielletty (fail-closed, `DeadlinePassed`):
  kutsu joka kirjataan deadlinen jalkeen ei ole kutsu vaan jalkiviisaus.
- Gradaus kirjoittaa `graded`-lohkon samaan riviin. Provisionaalinen kunnes
  FPL kaantaa `data_checked`:in (sama kasittely kuin model_squad_gw_scores).

Puhdas logiikka, ei verkkoa: skriptit `scripts/log_gw_calls.py` ja
`scripts/grade_gw_calls.py` hakevat datan ja kutsuvat naita.

EI NIMIESTOA TAHALLAAN: render_standouts_card.py:n EXCLUDED_NAMES (Thiaw)
koskee promopintoja (kortit ja postaukset), ei track-record-lokia. Loki
kirjaa sen mita kortti valitsi; kortti on jo suodattanut, ja jos suodatin
joskus poistuu, loki nayttaa sen eika piilota. Sensuroiva loki ei olisi loki.
"""
from __future__ import annotations

import datetime as _dt


class DeadlinePassed(RuntimeError):
    """Kirjaus deadlinen jalkeen on kielletty. Ei ohitusta."""


NEW_LOG = {
    "meta": {
        "product": "GoalIQ gameweek calls log",
        "version": 1,
        "rules": (
            "Every public call for a gameweek (the model squad captain, the "
            "four standouts card picks and the projected XI card) is written "
            "here before the FPL deadline "
            "and scored with official FPL points after the gameweek. A gameweek "
            "row can be updated until its deadline and never after it. In "
            "each row, logged_at is the first write and updated_at the last "
            "write before the deadline. A row without updated_at was written "
            "before the log kept both timestamps, and there logged_at is the "
            "last write. Scores are provisional until FPL confirms bonus "
            "points."),
    },
    "gameweeks": [],
}

CALL_LABELS = {
    "model_captain": "Model squad captain",
    "captain_pick": "Captain pick",
    "ceiling": "Ceiling",
    "safest": "Safest pick",
    "gamble": "The gamble",
    "projected_xi": "Projected XI",
}


def _iso(t: _dt.datetime) -> str:
    return t.astimezone(_dt.timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def parse_utc(s: str) -> _dt.datetime:
    t = _dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=_dt.timezone.utc)
    return t.astimezone(_dt.timezone.utc)


_POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def _slim(p: dict) -> dict:
    pos = p.get("pos")
    if isinstance(pos, int):  # freeze kantaa element_type-numeron
        pos = _POS.get(pos, str(pos))
    return {
        "player_id": int(p["id"]),
        "web_name": p.get("web_name"),
        "team_short": p.get("team_short"),
        "pos": pos,
    }


def build_entry(frozen: dict, standouts: dict, xp_meta: dict,
                now: _dt.datetime, players_by_id: dict | None = None) -> dict:
    """Yhden GW:n lokirivi freezesta + standouts-valinnoista.

    frozen: data/model_squad_frozen/gw{N}.json (meta.gw, meta.deadline,
            captain, vice_captain, xi, bench, meta.transfers)
    standouts: pick_standouts()-tulos (captain/ceiling/safest/gamble ->
            projektiorivi tai None), jokaisella xp_dist + gameweeks
    xp_meta: projektion meta (generated_at)
    """
    meta = frozen.get("meta") or {}
    gw = int(meta["gw"])
    deadline = parse_utc(meta["deadline"])
    if now >= deadline:
        raise DeadlinePassed(
            f"GW{gw}: deadline {_iso(deadline)} on ohi ({_iso(now)}), "
            "kutsua ei kirjata jalkikateen.")
    squad = {int(p["id"]): p
             for p in (frozen.get("xi") or []) + (frozen.get("bench") or [])}
    calls: list[dict] = []

    def _gw_xp(p: dict):
        for g in p.get("gameweeks") or []:
            if int(g.get("gw", -1)) == gw:
                return g.get("xp")
        return None

    cap = (squad.get(int(frozen["captain"]))
           if frozen.get("captain") is not None else None)
    if cap is not None:
        # Kapteenin HENKILO tulee freezesta (immutable, Ville syottaa rivin
        # entryyn T-24 h). ARVO tulee tuoreesta projektiosta jos se on
        # annettu: snapshot kirjaa sen mita malli sanoo kirjaushetkella, ei
        # sita mita se sanoi vuorokausi aiemmin.
        fresh = _gw_xp((players_by_id or {}).get(int(cap["id"])) or {})
        calls.append({
            "call": "model_captain", **_slim(cap),
            "metric": "gw_xp",
            "value": fresh if fresh is not None else cap.get("xp"),
            "frozen_value": cap.get("xp"),
            "criterion": "captain return, points doubled",
        })

    # pick_standouts() avaimet: captain/ceiling/safest/gamble. Lokissa kortin
    # kapteeni on "captain_pick", jotta se ei sekoitu mallin rivin kapteeniin.
    for key, src_key, metric, crit in (
        ("captain_pick", "captain", "p_haul", "10+ pts"),
        ("ceiling", "ceiling", "p90", "reached p90"),
        ("safest", "safest", "p_3plus", "3+ pts"),
        ("gamble", "gamble", "p_haul", "10+ pts"),
    ):
        p = standouts.get(src_key)
        if not p:
            continue
        d = p.get("xp_dist") or {}
        if metric == "p_3plus":
            value = round(1.0 - float(d.get("p_blank", 0.0)), 3)
        else:
            value = d.get(metric)
        calls.append({
            "call": key, **_slim(p),
            "metric": metric, "value": value,
            "criterion": crit,
            "gw_xp": _gw_xp(p),
            "xp_dist": {k: d.get(k) for k in
                        ("p_haul", "p_blank", "p10", "median", "p90",
                         "haul_pts", "blank_pts", "n")},
        })

    def _name(pid):
        p = squad.get(int(pid))
        if p is None and players_by_id:
            p = players_by_id.get(int(pid))
        return (p or {}).get("web_name")

    transfers = [{
        "out": t.get("out"), "out_name": _name(t.get("out")),
        "in": t.get("in"), "in_name": _name(t.get("in")),
        "hit": bool(t.get("hit")),
    } for t in (meta.get("transfers") or [])]

    return {
        "gw": gw,
        "deadline_utc": _iso(deadline),
        "logged_at": _iso(now),
        "updated_at": _iso(now),
        "source": {
            "freeze_frozen_at": meta.get("frozen_at"),
            "projection_generated_at": xp_meta.get("generated_at"),
        },
        "calls": calls,
        # Mallin AIKOMUS freezesta. Se ei ole sama kuin mita tili teki:
        # 28.8 freeze listasi 3 siirtoa ja 2 hittia, mutta entry pelasi
        # wildcardin (0 siirtoa, 0 hittia). Julkaisuportti 29.8: lahdelinkki
        # nayttaa taman lohkon ilman kontekstia ja lukija lukee sen tilin
        # tekemisiksi. `entry_actual` taytetaan gradauksessa FPL:n omasta
        # datasta, ja sivu voi nayttaa ne rinnakkain.
        "model_transfers": transfers,
        "entry_actual": None,
        "graded": None,
    }


def entry_actual(history_row: dict | None, picks: dict | None) -> dict | None:
    """Mita TILI teki kierroksella, FPL:n omasta datasta.

    `history_row` = entry/{id}/history -&gt; current[] alkio, `picks` =
    entry/{id}/event/{gw}/picks. Palauttaa None jos kumpikaan ei ole
    luettavissa (nolla ei ole sama kuin ei tietoa).
    """
    if not history_row and not picks:
        return None
    out: dict = {}
    if history_row:
        out["transfers"] = int(history_row.get("event_transfers") or 0)
        out["transfers_cost"] = int(history_row.get("event_transfers_cost") or 0)
        # 🔴 `points` EI kuulu tanne (poistettu 30.8, julkaisutarkistaja B5).
        # Lohko kirjoitetaan kerran (`grade_gw_calls.py`: `if not
        # row.get("entry_actual")`), joten provisionaalisessa gradauksessa
        # napattu luku jaatyy pysyvasti. GW2: tiedostoon jai 15, kun FPL:n
        # oma luku oli jo 28. Sivu LINKKAA tahan tiedostoon lahteena, joten
        # lukija olisi nahnyt kaksi eri lukua samasta kierroksesta.
        # Chip, kapteeni ja siirrot ovat lukittuja deadlinen jalkeen; pisteet
        # eivat ole. Jos pisteet joskus tarvitaan, ne luetaan FPL:sta
        # gradaushetkella, ei tasta lohkosta.
    if picks:
        out["chip"] = picks.get("active_chip")
        cap = [int(p["element"]) for p in (picks.get("picks") or [])
               if p.get("is_captain")]
        out["captain"] = cap[0] if cap else None
    return out or None


# ---------------------------------------------------------------------------
# PROJECTED-XI-KORTTI (29.8.2026, GW-PROJECTED-XI-CARD): XI + kapteeni on
# yksi kutsu, ei 11. Gradataan FPL:n saannoilla: kapteeni tuplana, nollan
# minuutin pelaaja vaihtuu penkilta jarjestyksessa jos muodostelma pysyy
# laillisena (GK vain GK:hon), varakapteeni tuplataan jos kapteeni ei pelaa.
# Ei binaarista lupausta ("met" = None): tulos on pistesumma, jota verrataan
# kutsun arvoon (value = XI:n GW-xP kapteeni tuplana).
# ---------------------------------------------------------------------------

PROJECTED_XI_CALL = "projected_xi"
_XI_MIN = {"GKP": 1, "DEF": 3, "MID": 2, "FWD": 1}
_XI_MAX = {"GKP": 1, "DEF": 5, "MID": 5, "FWD": 3}


def _xi_slim(p: dict) -> dict:
    d = _slim(p)
    d["gw_xp"] = p.get("gw_xp")
    return d


def build_projected_xi_call(xi: list[dict], bench: list[dict], captain: dict,
                            vice: dict | None, formation: str) -> dict:
    """Kutsurivi projected-XI-kortista. xi/bench-rivit: id, web_name,
    team_short, pos (GKP/DEF/MID/FWD tai element_type), gw_xp. Penkki
    penkkijarjestyksessa (GK ensin), koska gradaus lukee sen sellaisenaan."""
    xi_rows = [_xi_slim(p) for p in xi]
    cap_id = int(captain["id"])
    xp_total = round(sum(float(r.get("gw_xp") or 0.0) for r in xi_rows)
                     + float(captain.get("gw_xp") or 0.0), 2)
    return {
        "call": PROJECTED_XI_CALL,
        "player_id": cap_id,  # kapteeni: sivun rivi + yksiloity kutsu
        "web_name": f"{formation} XI, captain {captain.get('web_name')}",
        "team_short": captain.get("team_short"),
        "pos": "XI",
        "metric": "xi_gw_xp",
        "value": xp_total,
        "criterion": ("XI points with the captain doubled, FPL automatic "
                      "substitutions applied from the bench in order"),
        "formation": formation,
        "captain": _xi_slim(captain),
        "vice_captain": _xi_slim(vice) if vice else None,
        "xi": xi_rows,
        "bench": [_xi_slim(p) for p in bench],
    }


def upsert_call(log: dict, gw: int, deadline_utc: str, call: dict,
                now: _dt.datetime, source: dict | None = None) -> dict:
    """Lisaa tai korvaa YKSI kutsu GW-rivilla. Rivi luodaan jos sita ei ole
    (esim. kortti ajetaan ennen log_gw_calls:ia). Sama fail-closed kuin
    upsert: deadlinen jalkeen tai gradatulle riville ei kirjoiteta."""
    deadline = parse_utc(deadline_utc)
    if now >= deadline:
        raise DeadlinePassed(
            f"GW{gw}: deadline {_iso(deadline)} on ohi ({_iso(now)}), "
            "kutsua ei kirjata jalkikateen.")
    rows = log.setdefault("gameweeks", [])
    row = next((r for r in rows if int(r.get("gw", -1)) == int(gw)), None)
    if row is None:
        row = {"gw": int(gw), "deadline_utc": _iso(deadline),
               "logged_at": _iso(now), "updated_at": _iso(now),
               "source": dict(source or {}),
               "calls": [], "model_transfers": [], "graded": None}
        rows.append(row)
        rows.sort(key=lambda r: int(r.get("gw", 0)))
    if row.get("graded"):
        raise DeadlinePassed(f"GW{gw} on jo gradattu, kutsua ei muuteta.")
    calls = [c for c in row.get("calls") or [] if c.get("call") != call["call"]]
    calls.append(call)
    row["calls"] = calls
    row["updated_at"] = _iso(now)   # logged_at = ensimmainen kirjaus, ei muutu
    if source:
        row.setdefault("source", {}).update(source)
    return log


def _played(pid: int, minutes: dict[int, int]) -> bool:
    return int(minutes.get(pid) or 0) > 0


def _formation_ok(rows: list[dict]) -> bool:
    n = {"GKP": 0, "DEF": 0, "MID": 0, "FWD": 0}
    for r in rows:
        pos = r.get("pos")
        if pos in n:
            n[pos] += 1
    return all(_XI_MIN[k] <= n[k] <= _XI_MAX[k] for k in n)


def score_projected_xi(call: dict, points: dict[int, int],
                       minutes: dict[int, int]) -> dict:
    """FPL:n pisteytys yhdelle XI-kutsulle. Puuttuva pelaaja live-datasta
    -> points None (ei nolla)."""
    xi = list(call.get("xi") or [])
    bench = list(call.get("bench") or [])
    ids = [int(r["player_id"]) for r in xi + bench]
    if any(points.get(pid) is None for pid in ids):
        return {"points": None, "minutes": None, "met": None,
                "autosubs": [], "captain_points": None}
    final = list(xi)
    subs: list[dict] = []
    for b in bench:
        if not _played(int(b["player_id"]), minutes):
            continue
        for i, s in enumerate(final):
            if _played(int(s["player_id"]), minutes):
                continue
            same_gk = (s.get("pos") == "GKP") == (b.get("pos") == "GKP")
            if not same_gk:
                continue
            cand = final[:i] + [b] + final[i + 1:]
            if _formation_ok(cand):
                final = cand
                subs.append({"out": int(s["player_id"]), "in": int(b["player_id"])})
                break
    cap = call.get("captain") or {}
    vice = call.get("vice_captain") or {}
    cap_id = int(cap.get("player_id", -1))
    vice_id = int(vice.get("player_id", -1))
    doubled = None
    if _played(cap_id, minutes):
        doubled = cap_id
    elif _played(vice_id, minutes) and any(
            int(r["player_id"]) == vice_id for r in final):
        doubled = vice_id
    total = sum(int(points[int(r["player_id"])]) for r in final)
    cap_pts = int(points[doubled]) if doubled is not None else 0
    return {"points": total + cap_pts, "minutes": None, "met": None,
            "captain_points": cap_pts, "doubled": doubled, "autosubs": subs}


def upsert(log: dict, entry: dict, now: _dt.datetime) -> dict:
    """Lisaa tai paivita GW-rivi. Fail-closed deadlinen jalkeen, myos silloin
    kun rivi on jo olemassa (paivitys deadlinen jalkeen muuttaisi kutsua).

    Paivitys (DEADLINE-SNAPSHOT 29.8): uuden entryn kutsut korvaavat samat
    kutsut, `logged_at` sailyy ensimmaisesta kirjauksesta, `updated_at` =
    now, ja kutsut joita entry ei tuota (projected_xi kortista) sailyvat.
    Aiempi versio korvasi koko rivin ja pudotti kortin kutsun jokaisessa
    3 h -refreshissa ennen deadlinea."""
    deadline = parse_utc(entry["deadline_utc"])
    if now >= deadline:
        raise DeadlinePassed(
            f"GW{entry['gw']}: deadline {entry['deadline_utc']} on ohi, "
            "lokia ei paiviteta.")
    rows = log.setdefault("gameweeks", [])
    for i, r in enumerate(rows):
        if int(r.get("gw", -1)) == int(entry["gw"]):
            if r.get("graded"):
                raise DeadlinePassed(
                    f"GW{entry['gw']} on jo gradattu, kutsua ei muuteta.")
            mine = {c.get("call") for c in entry.get("calls") or []}
            kept = [c for c in r.get("calls") or [] if c.get("call") not in mine]
            entry["calls"] = list(entry.get("calls") or []) + kept
            entry["logged_at"] = r.get("logged_at") or entry["logged_at"]
            entry["updated_at"] = _iso(now)
            src = dict(r.get("source") or {})
            src.update({k: v for k, v in (entry.get("source") or {}).items()
                        if v is not None})
            entry["source"] = src
            rows[i] = entry
            break
    else:
        entry.setdefault("updated_at", entry["logged_at"])
        rows.append(entry)
    rows.sort(key=lambda r: int(r.get("gw", 0)))
    return log


def gw_status(boot: dict, fixtures: list[dict]) -> dict[int, dict]:
    """Sama saanto kuin grade_model_squad._gw_status: gradattavissa kun kaikki
    kierroksen ottelut ovat finished_provisional; provisionaalinen kunnes
    data_checked."""
    by_gw: dict[int, list[dict]] = {}
    for f in fixtures:
        gw = f.get("event")
        if gw is not None:
            by_gw.setdefault(int(gw), []).append(f)
    out: dict[int, dict] = {}
    for ev in boot.get("events") or []:
        gw = int(ev["id"])
        fx = by_gw.get(gw) or []
        if not fx:
            continue
        out[gw] = {
            "gradable": all(f.get("finished_provisional") for f in fx),
            "provisional": not bool(ev.get("data_checked")),
        }
    return out


def _met(call: dict, pts: int):
    d = call.get("xp_dist") or {}
    k = call["call"]
    if k in ("captain_pick", "gamble"):
        return pts >= int(d.get("haul_pts") or 10)
    if k == "ceiling":
        return d.get("p90") is not None and pts >= int(d["p90"])
    if k == "safest":
        blank = d.get("blank_pts")
        return pts > int(blank if blank is not None else 2)
    return None  # model_captain: ei binaarista lupausta


def grade_entry(entry: dict, points: dict[int, int], minutes: dict[int, int],
                provisional: bool, now: _dt.datetime,
                starts: dict[int, int] | None = None) -> dict:
    """Kirjoita `graded`-lohko. Pisteet FPL:n event/{gw}/live total_points.
    Puuttuva pelaaja -> None (ei nolla: nolla vaittaisi blankia).

    `starts` (FPL live stats `starts`, 29.8 DEADLINE-SNAPSHOT-mittari M1):
    kirjaa `started` per kutsu, jotta minuuttivirhe (ei aloittanut) erottuu
    mallivirheesta (aloitti, ei tuottanut). Ilman dataa `started` = None."""
    if entry.get("graded") and not entry["graded"].get("provisional"):
        return entry  # lopullinen, ei kirjoiteta yli
    by_call = {}

    def _started(pid: int):
        if starts is None or pid not in starts:
            return None
        return int(starts.get(pid) or 0) > 0

    for c in entry.get("calls") or []:
        if c["call"] == PROJECTED_XI_CALL:
            xi_row = score_projected_xi(c, points, minutes)
            xi_ids = [int(r["player_id"]) for r in c.get("xi") or []]
            flags = [_started(pid) for pid in xi_ids]
            xi_row["xi_started"] = (None if any(f is None for f in flags)
                                    else sum(1 for f in flags if f))
            by_call[c["call"]] = xi_row
            continue
        pid = int(c["player_id"])
        pts = points.get(pid)
        mins = minutes.get(pid)
        row = {"points": pts, "minutes": mins, "met": None,
               "started": _started(pid)}
        if pts is not None:
            row["met"] = _met(c, int(pts))
            if c["call"] == "model_captain":
                row["captain_total"] = int(pts) * 2
        by_call[c["call"]] = row
    entry["graded"] = {
        "graded_at": _iso(now),
        "provisional": bool(provisional),
        "by_call": by_call,
    }
    return entry


def start_share(log: dict, gws) -> dict:
    """Mittari M1 (DEADLINE-SNAPSHOT 29.8): montako kutsuttua pelaajaa aloitti.

    Lasketaan lokista gradatuilta riveilta, pelaajakutsut (ei projected_xi).
    `started` tulee gradauksesta (FPL live `starts`); jos se puuttuu, rivi
    ei ole mukana (ei arvata minuuteista: 1 min vaihdolta ei ole aloitus).
    Vertailu: start_share(log, [1, 2]) vs start_share(log, [3, 4]).
    """
    want = {int(g) for g in gws}
    n = started = 0
    for row in log.get("gameweeks") or []:
        if int(row.get("gw", -1)) not in want or not row.get("graded"):
            continue
        by_call = row["graded"].get("by_call") or {}
        for c in row.get("calls") or []:
            if c["call"] == PROJECTED_XI_CALL:
                continue
            st = (by_call.get(c["call"]) or {}).get("started")
            if st is None:
                continue
            n += 1
            started += 1 if st else 0
    return {"gws": sorted(want), "calls": n, "started": started,
            "share": (round(started / n, 3) if n else None)}
