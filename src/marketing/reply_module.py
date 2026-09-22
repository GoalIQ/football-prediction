"""GW-kohtainen reply-moduuli: YKSI lukija joka ei voi palauttaa vanhaa lukua.

X-REPLY-MOOTTORI (Villen GO 22.9.2026; suunnitelma goaliq-app/cos-reports/
ux-uudistus-2026-09/c3-reply-valmius.md luvut 2 ja 5).

Moduuli (`data/reply_modules/gw{N}.json`) on kierroksen alussa ajettu ja
julkista pintaa vasten tarkistettu lukupaketti. Yksittainen X-vastaus ei laske
mitaan: se lainaa moduulin tekstia. Siksi vastauksen ainoa kova tarkistus on
"tuleeko jokainen luku tuoreesta moduulista" (fast-lane, C4) - ja "tuore" on
TAMAN tiedoston vastuu, ei muistin.

`load_reply_module(gw)` KIELTAYTYY (ReplyModuleRefused) kun:
  (a) kierroksen deadline on mennyt,
  (b) projektio tai muu paikallinen lahde on regeneroitu moduulin jalkeen JA
      jokin valituista luvuista naytettaisiin nyt eri tekstina,
  (c) valitussa rivissa nimetyn pelaajan FPL-status, pelitodennakoisyys tai
      uutinen on muuttunut (loukkaantuminen, pelikielto).
Silloin moduuli ajetaan uudelleen (`scripts/build_reply_module.py`), ei
korjata kasin.

KYNNYS (b) ON NAYTTOTARKKUUS. Luku joka pyoristyy sivulla samaksi on sama
luku lukijalle; luku joka pyoristyy toiseksi on eri luku, vaikka ero olisi
0,01. Liukulukukynnys (esim. 0,2 xP) sallisi vastauksen "5.5 xP" kun sivu
sanoo 5.6 - juuri sen tilanteen jota reitti on olemassa estamaan.

Saanto 6a: (1) tama on ainoa lukija, (2) muut tiedostot jotka lukevat
`data/reply_modules/`-kansiota ovat poikkeuslistalla perusteluineen
(tests/test_reply_module_reader_discipline.py), (3) vaiheet testataan
synteettisilla kelloilla (tests/test_reply_module_phases.py).
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import config

MODULE_DIR = config.DATA_DIR / "reply_modules"
SCHEMA = "goaliq.reply_module.v1"
DRIFT_RULE = "display_text"   # ks. moduulidocstring: kynnys = nayttotarkkuus

# Paikalliset lahteet joiden regenerointi voi muuttaa lukua (b). Avain on
# moduulin `sources`-avain; arvo = (tiedosto, aikaleimakentta metassa).
LOCAL_SOURCES = {
    "xp": ("fpl_xp_projections.json", ("meta", "generated_at")),
    "phase0": ("fpl_projections_phase0.json", ("meta", "generated_at")),
    "accuracy": ("accuracy.json", ("updated_at",)),
    "xp_accuracy": ("fpl_xp_gw_accuracy.json", None),
    "gw_calls": ("gw_calls.json", None),
}

# Osiot joiden riveissa on nimetty pelaaja (c).
PLAYER_SECTIONS = ("captain_top5", "xp_top5", "player_lookup", "differentials")


class ReplyModuleRefused(Exception):
    """Moduulia ei palauteta. Viesti kertoo miksi ja mita tehda."""


def module_path(gw: int, module_dir: Path | None = None) -> Path:
    return (module_dir or MODULE_DIR) / f"gw{int(gw)}.json"


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def norm_text(t) -> str:
    """Vertailumuoto: '46.5%' == '46.5 %' == '46.5'. Desimaalipilkku -> piste."""
    return str(t if t is not None else "").replace("%", "").replace(",", ".").strip()


# ---------------------------------------------------------------------------
# Arvojen lapikaynti
# ---------------------------------------------------------------------------
def iter_values(sections: dict):
    """(avain, arvo, rivi, osio) jokaiselle luvulle. Avain on muotoa
    `osio.rivi.kentta` (esim. captain_top5.haaland-mci.gw_xp) tai
    `osio.kentta` rivittomille osioille (track_record.pct_1x2)."""
    for sname, sec in (sections or {}).items():
        if not isinstance(sec, dict):
            continue
        for k, v in (sec.get("values") or {}).items():
            yield f"{sname}.{k}", v, None, sname
        for listname in ("rows", "model_only", "template_only"):
            for row in sec.get(listname) or []:
                prefix = f"{sname}.{row['key']}" if listname == "rows" else \
                    f"{sname}.{listname}.{row['key']}"
                for k, v in (row.get("values") or {}).items():
                    yield f"{prefix}.{k}", v, row, sname
        cap = sec.get("captain")
        if isinstance(cap, dict):
            for k, v in (cap.get("values") or {}).items():
                yield f"{sname}.captain.{k}", v, cap, sname
        gap = sec.get("xp_gap")
        if isinstance(gap, dict):
            for k, v in (gap.get("values") or {}).items():
                yield f"{sname}.xp_gap.{k}", v, None, sname


def value_index(sections: dict) -> dict:
    return {k: v for k, v, _r, _s in iter_values(sections)}


# ---------------------------------------------------------------------------
# Reittien tarkistus julkista pintaa vasten (generaattori + fast-lane-portti)
# ---------------------------------------------------------------------------
def surface_lookup(pages: dict, sid: str, key: list, field: str, gw: int,
                   ctx: dict | None = None):
    """Palauttaa (url, teksti) jos rivi on pinnalla, (url, None) jos pinta on
    luettu mutta rivia ei ole, tai None jos pintaa ei ole kaytettavissa talle
    kierrokselle (ei haettu, eri kierros)."""
    from src.marketing import reply_sections as rs
    ctx = ctx or {}
    if sid.startswith("club:"):
        slug = sid.split(":", 1)[1]
        p = (pages.get("clubs") or {}).get(slug)
        if p is None:
            return None
        row = p.get(key[0])
        return rs.club_url(slug), (row or {}).get(field) if row else None
    p = pages.get(sid)
    if p is None:
        return None
    if sid == "fpl_entry":
        return p["url"], (p.get(key[0]) if p.get(key[0]) is not None else None)
    rows = p.get("rows") or {}
    page_gw = p.get("gw")
    url = p.get("url") or rs.URL.get(sid)
    # Kierrossidotut pinnat: eri kierros = pinta ei kelpaa reitiksi talle luvulle.
    if sid in ("gw_xp", "clean_sheets") and page_gw != gw:
        return None
    if sid == "top100" and field in ("p_10plus", "p_blank") and page_gw != gw:
        return None
    if sid == "eo" and page_gw != ctx.get("template_picks_gw"):
        return None
    if sid == "track_record":
        return url, (rows or {}).get(key[0])
    if sid == "xp_accuracy":
        row = rows.get(int(key[0]))
        return url, (row or {}).get(key[1]) if row else None
    if sid == "gw_calls":
        row = rows.get((int(key[0]), key[1]))
        col = key[2] if len(key) > 2 else "points"
        return url, (row or {}).get(col) if row else None
    k = tuple(key) if len(key) > 1 else key[0]
    row = rows.get(k)
    return url, ((row or {}).get(field) if row else None)


FIELD_ALIASES = {"gw_xp_frozen": "xp", "eo_pct": "eo_lead"}


def verify_value(v: dict, pages: dict, gw: int, field: str, ctx: dict | None = None):
    """Kavele reitit. Palauttaa (url tai None, virhe tai None, reitti tai None).

    Generaattori antaa koko `routes`-listan (ehdokkaat); valmis moduuli
    kantaa vain loydetyn reitin `check`-kentassa, ja fast-lane-portti
    tarkistaa sen uudelleen elavaa sivua vasten julkaisuhetkella.
    """
    routes = v.get("routes") or ([v["check"]] if v.get("check") else [])
    for sid, key in routes:
        got = surface_lookup(pages, sid, key, FIELD_ALIASES.get(field, field), gw, ctx)
        if got is None:
            continue
        url, text = got
        if text is None:
            continue
        if norm_text(text) != norm_text(v["text"]):
            return None, (f"{sid} {key}: page shows {text!r}, module has "
                          f"{v['text']!r} ({url})"), None
        return url, None, [sid, key]
    return None, None, None


def resolve_routes(sections: dict, pages: dict, gw: int, verified_at: str,
                   sources: dict) -> tuple[int, int, list[str]]:
    """Kirjoita jokaiselle luvulle public_url/verified_at/source/generated_at.

    Palauttaa (varmennetut, ilman reittia, ristiriidat). Ristiriita = sama
    rivi julkisella pinnalla nayttaa eri tekstia -> moduulia EI kirjoiteta.
    """
    ok = none = 0
    bad: list[str] = []
    for key, v, _row, sname in iter_values(sections):
        field = key.rsplit(".", 1)[1]
        ctx = {"template_picks_gw": (sections.get(sname) or {}).get("template_picks_gw")}
        url, err, route = verify_value(v, pages, gw, field, ctx)
        if err:
            bad.append(f"{key}: {err}")
        src = sources.get(v.get("src")) or {}
        v["source"] = f"{src.get('file')}@{src.get('commit')}"
        v["generated_at"] = src.get("generated_at")
        v["public_url"] = url
        v["verified_at"] = verified_at if url else None
        v.pop("routes", None)
        if url:
            ok += 1
            v["check"] = route
        else:
            none += 1
    return ok, none, bad


# Pinnat jotka generaattori hakee aina (points_gw vain kun sita tarvitaan).
ALL_SURFACES = ("gw_xp", "top100", "clean_sheets", "gw_calls", "xp_accuracy",
                "track_record", "eo", "differentials", "clubs")
_PAGE_OF = {"gw_xp": "https://goaliq.app/fpl/expected-points",
            "top100": "https://goaliq.app/fpl/expected-points",
            "clean_sheets": "https://goaliq.app/fpl", "gw_calls": "https://goaliq.app/fpl",
            "xp_accuracy": "https://goaliq.app/fpl", "track_record": "https://goaliq.app/fpl",
            "eo": "https://goaliq.app/fpl",
            "differentials": "https://goaliq.app/fpl/differentials"}
REQUIRED_PAGES = {"https://goaliq.app/fpl/expected-points", "https://goaliq.app/fpl",
                  "https://goaliq.app/fpl/differentials"}


def fetch_surfaces(needed, gw: int, fetch=None) -> tuple[dict, dict, list[str]]:
    """Hae ja jasenna julkiset pinnat: (pages, meta per URL, virheet).

    Sama funktio generaattorille (kaikki pinnat) ja fast-lane-portille (vain
    luonnoksen lukujen pinnat, julkaisuhetkella). `needed` = pintatunnukset
    (`club:<slug>` hakee yhden seurasivun, `clubs` kaikki).
    """
    from src.marketing import public_surface as ps
    from src.marketing import reply_sections as rs
    fetch = fetch or ps.fetch
    needed = set(needed)
    pages: dict = {}
    meta: dict = {}
    errs: list[str] = []
    cache: dict = {}

    def get(url):
        if url in cache:
            return cache[url]
        try:
            f = fetch(url)
            meta[url] = {"http": f.status, "fetched_at": f.fetched_at}
            cache[url] = f.html
        except Exception as e:  # noqa: BLE001
            meta[url] = {"error": f"{type(e).__name__}: {e}"}
            cache[url] = None
            if url in REQUIRED_PAGES:
                errs.append(f"required page unreachable: {url} ({type(e).__name__})")
        return cache[url]

    for sid in sorted(needed):
        url = _PAGE_OF.get(sid)
        if url is None:
            continue
        h = get(url)
        if h is None:
            continue
        if sid == "gw_xp":
            g, rows = ps.gw_xp_table(h)
        elif sid == "top100":
            g, rows = ps.top100_table(h)
        elif sid == "clean_sheets":
            g, rows = ps.clean_sheet_table(h)
        elif sid == "eo":
            g, rows = ps.eo_table(h)
        else:
            g = None
            rows = {"gw_calls": ps.gw_calls_table, "xp_accuracy": ps.xp_accuracy_table,
                    "track_record": lambda x: ps.track_record_sentence(x) or {},
                    "differentials": ps.differentials_table}[sid](h)
        pages[sid] = {"url": rs.URL.get(sid, url), "gw": g, "rows": rows}
    slugs = set()
    if "clubs" in needed:
        from scripts.build_fpl_longtail import CLUB_SLUGS
        slugs |= set(CLUB_SLUGS.values())
    slugs |= {s.split(":", 1)[1] for s in needed if s.startswith("club:")}
    if slugs:
        pages["clubs"] = {}
        for slug in sorted(slugs):
            h = get(rs.club_url(slug))
            if h:
                pages["clubs"][slug] = ps.club_table(h)
    if "points_gw" in needed:
        u = f"https://goaliq.app/fpl/points/gw{gw}"
        h = get(u)
        if h:
            pages["points_gw"] = {"url": u, "rows": ps.points_table(h)}
    return pages, meta, errs


# ---------------------------------------------------------------------------
# Lukija
# ---------------------------------------------------------------------------
def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _stamp(doc: dict, where) -> str | None:
    if where is None:
        return None
    cur = doc
    for k in where:
        cur = (cur or {}).get(k) if isinstance(cur, dict) else None
    return str(cur) if cur is not None else None


def source_stamp(name: str, data_dir: Path | None = None) -> str | None:
    """Paikallisen lahteen aikaleima (tai sisallon tiiviste kun kenttaa ei ole)."""
    fname, where = LOCAL_SOURCES[name]
    p = (data_dir or config.DATA_DIR) / fname
    if not p.exists():
        return None
    if where is None:
        import hashlib
        return "sha1:" + hashlib.sha1(p.read_bytes()).hexdigest()[:12]
    return _stamp(_read(p), where)


def recompute_sections(module: dict, names: set[str], data_dir: Path | None = None) -> dict:
    """Aja samat osiofunktiot tuoreella paikallisella datalla."""
    from src.marketing import reply_sections as rs
    from src.models.fpl_xp import attach_horizon_total_actionable, load_xp_actionable
    from scripts.publish_gate import load_blocklist
    dd = data_dir or config.DATA_DIR
    gw = int(module["gw"])
    out: dict = {}
    need_xp = names & {"captain_top5", "xp_top5", "player_lookup", "differentials"}
    xp = None
    if need_xp:
        xp = attach_horizon_total_actionable(load_xp_actionable(dd / "fpl_xp_projections.json"))
    if "captain_top5" in names:
        out["captain_top5"] = rs.captain_top5(xp, gw, load_blocklist())
    if "xp_top5" in names:
        out["xp_top5"] = rs.xp_top5(xp, gw, load_blocklist())
    if "player_lookup" in names or "differentials" in names:
        out["player_lookup"] = rs.player_lookup(xp, gw, load_blocklist())
    if "cs_top" in names:
        out["cs_top"] = rs.cs_top(_read(dd / "fpl_projections_phase0.json"), gw)
    if "track_record" in names:
        acc = dd / "accuracy.json"
        xa = dd / "fpl_xp_gw_accuracy.json"
        out["track_record"] = rs.track_record(_read(acc) if acc.exists() else None,
                                              _read(xa) if xa.exists() else None)
    return out


def _fresh_text(key: str, fresh: dict, fresh_idx: dict) -> str | None:
    """Tuore teksti samalle avaimelle. Differentiaalirivin luvut luetaan
    pelaajan omista luvuista (sama projektio), koska lista itse tulee API:sta."""
    if key.startswith("differentials."):
        _s, row, field = key.split(".", 2)
        v = fresh_idx.get(f"player_lookup.{row}.{field}")
        return v["text"] if v else None
    v = fresh_idx.get(key)
    return v["text"] if v else None


def fetch_fpl_status() -> dict:
    """{player_id: {status, chance, news}} FPL:n bootstrapista (verkko)."""
    from src.models.fpl_rate_team import get_bootstrap
    b = get_bootstrap()
    return {int(e["id"]): {"status": e.get("status"),
                           "chance": e.get("chance_of_playing_next_round"),
                           "news": e.get("news") or ""}
            for e in b.get("elements") or []}


def _select(module: dict, sections, keys) -> tuple[dict, set[str]]:
    secs = module.get("sections") or {}
    names = set(sections) if sections else set(secs)
    unknown = names - set(secs)
    if unknown:
        raise ReplyModuleRefused(f"sections not in module gw{module.get('gw')}: {sorted(unknown)}")
    chosen = {n: copy.deepcopy(secs[n]) for n in names}
    if keys is None:
        return chosen, set(value_index(chosen))
    keys = set(keys)
    idx = value_index(chosen)
    missing = sorted(k for k in keys if k not in idx)
    if missing:
        raise ReplyModuleRefused(
            f"keys not in module gw{module.get('gw')}: {missing[:10]}"
            + (" (section not available)" if any(
                not (secs.get(k.split('.')[0]) or {}).get("available", True) for k in missing) else ""))
    # Karsi: palautetaan VAIN tarkistetut luvut, jottei kutsuja voi lukea
    # viereista lukua jota ei tarkistettu.
    for sname, sec in chosen.items():
        for listname in ("rows", "model_only", "template_only"):
            if listname not in sec:
                continue
            kept = []
            for row in sec[listname]:
                prefix = f"{sname}.{row['key']}" if listname == "rows" else \
                    f"{sname}.{listname}.{row['key']}"
                row["values"] = {k: v for k, v in (row.get("values") or {}).items()
                                 if f"{prefix}.{k}" in keys}
                if row["values"]:
                    kept.append(row)
            sec[listname] = kept
        if isinstance(sec.get("values"), dict):
            sec["values"] = {k: v for k, v in sec["values"].items() if f"{sname}.{k}" in keys}
        for sub in ("captain", "xp_gap"):
            if isinstance(sec.get(sub), dict) and isinstance(sec[sub].get("values"), dict):
                sec[sub]["values"] = {k: v for k, v in sec[sub]["values"].items()
                                      if f"{sname}.{sub}.{k}" in keys}
    chosen = {n: sec for n, sec in chosen.items() if value_index({n: sec})}
    return chosen, keys


def load_reply_module(gw: int, *, sections=None, keys=None, now: datetime | None = None,
                      data_dir: Path | None = None, module_dir: Path | None = None,
                      fpl_status=None) -> dict:
    """Palauta moduuli (tai sen osa) vain jos jokainen palautettu luku on tuore.

    sections: rajaa osioihin (None = kaikki). keys: rajaa yksittaisiin lukuihin
    (fast-lane-portti antaa luonnoksen `luvut:`-avaimet). Tarkistukset (b) ja
    (c) ajetaan VAIN palautettaville luvuille, ja palautus karsitaan niihin.
    fpl_status: None = hae FPL:sta; callable -> {id: {...}} (testit).
    """
    path = module_path(gw, module_dir)
    if not path.exists():
        raise ReplyModuleRefused(
            f"no reply module for GW{gw} ({path.name}); run "
            f"python -m scripts.build_reply_module --gw {gw}")
    module = _read(path)
    if module.get("schema") != SCHEMA or int(module.get("gw") or -1) != int(gw):
        raise ReplyModuleRefused(f"{path.name}: schema/gw mismatch")
    now = now or datetime.now(timezone.utc)
    dl = _parse_ts(module.get("deadline_utc"))
    if dl is None:
        raise ReplyModuleRefused(f"{path.name}: deadline missing")
    # (a) deadline
    if now >= dl:
        raise ReplyModuleRefused(
            f"GW{gw} deadline passed at {dl.isoformat()}: the module is history, "
            f"not a projection. Build the next gameweek's module.")

    chosen, keys = _select(module, sections, keys)

    # (b) regeneroitu lahde + muuttunut nayttoteksti
    srcs = module.get("sources") or {}
    used_srcs = {v.get("src") for _k, v, _r, _s in iter_values(chosen)}
    if "differentials" in used_srcs:
        used_srcs.add("xp")
    changed = {s for s in used_srcs if s in LOCAL_SOURCES
               and source_stamp(s, data_dir) != (srcs.get(s) or {}).get("stamp")}
    if changed:
        affected = {sname for _k, v, _r, sname in iter_values(chosen)
                    if v.get("src") in changed or (v.get("src") == "differentials" and "xp" in changed)}
        fresh = recompute_sections(module, affected, data_dir)
        fresh_idx = value_index(fresh)
        diffs = []
        for key, v, _r, sname in iter_values(chosen):
            if sname not in affected or sname in ("last_gw", "model_vs_template"):
                continue
            t = _fresh_text(key, fresh, fresh_idx)
            if t is None:
                diffs.append(f"{key}: no longer in the projection")
            elif norm_text(t) != norm_text(v["text"]):
                diffs.append(f"{key}: module {v['text']!r}, now {t!r}")
        if diffs:
            raise ReplyModuleRefused(
                f"GW{gw} sources regenerated ({', '.join(sorted(changed))}) and "
                f"{len(diffs)} number(s) changed: " + "; ".join(diffs[:8])
                + ". Rebuild the module.")

    # (c) nimetyn pelaajan FPL-tila
    ids = set()
    for sname in PLAYER_SECTIONS:
        for row in (chosen.get(sname) or {}).get("rows") or []:
            if row.get("values") and row.get("player_id") is not None:
                ids.add(int(row["player_id"]))
    if ids:
        snap = module.get("named_players") or {}
        try:
            live = fpl_status() if callable(fpl_status) else fetch_fpl_status()
        except Exception as e:  # fail-closed: ilman statusta ei tiedeta
            raise ReplyModuleRefused(f"FPL status check failed ({type(e).__name__}): {e}")
        moved = []
        for pid in sorted(ids):
            was = snap.get(str(pid))
            now_s = live.get(pid)
            if was is None or now_s is None:
                moved.append(f"{pid}: not in FPL status snapshot")
                continue
            for f in ("status", "chance", "news"):
                if (was.get(f) or None) != (now_s.get(f) or None):
                    moved.append(f"{was.get('web_name') or pid}: {f} "
                                 f"{was.get(f)!r} -> {now_s.get(f)!r}")
                    break
        if moved:
            raise ReplyModuleRefused(
                "FPL status changed for a named player: " + "; ".join(moved[:8])
                + ". Rebuild the module.")

    out = {k: module[k] for k in module if k != "sections" and k != "named_players"}
    out["sections"] = chosen
    out["checked_at"] = now.isoformat(timespec="seconds")
    return out
