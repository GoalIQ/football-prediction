"""Fast-lane-portti X-vastausluonnokselle (C4, Villen GO 22.9.2026).

    python -m scripts.check_reply_numbers <luonnos.md> [--now 2026-09-22T09:00Z]

Brief C4: kun Ville on hyvaksynyt vastauksen, julkaisutarkistaja ei pysayta
sita tyyli- tai muotoseikoista. AINOA kova tarkistus on, etta luvut tulevat
esitarkistetusta GW-moduulista. Tama skripti on se tarkistus. Standalone-
postaukset, uudet vaitteet ja saantotulkinnat kulkevat edelleen taydessa
julkaisutarkistajassa - tama portti ei tunnista niita eika vaita tunnistavansa.

Tarkistukset (exit 0 vain kun KAIKKI lapaisevat):
  1. luvut-kattavuus: jokainen `luonnos:`-tekstin numero loytyy `luvut:`-
     rivilta samana (GW-tunnus = moduulin kierros, "10+" vain P(10+)-luvun
     kanssa).
  2. moduuli: jokainen `luvut:`-arvo loytyy TUOREESTA moduulista samana
     (`load_reply_module`: deadline, regenerointi, FPL-status), lukua on
     ilmaispinnalla (public_url), `tarkistus:`-rivi nimeaa sen, ja sama teksti
     nakyy sivulla NYT (haetaan uudelleen julkaisuhetkella).
  3. tuoreus: kohdepostaus alle 240 min vanha (`julkaistu:`).
  4. kohdetili: ei data/reply_blocklist.json:ssa (C2:n EI- ja HARMAA-rivit).
  5. CTA: ei linkkia eika tuotenimea vastaustekstissa (C1 kohdat 6-7).

Luonnoksen muoto: goaliq-app/cos-reports/marketing/replies/_TEMPLATE.md.

MITA TAMA EI NAE: sanoin kirjoitetut luvut ("two clean sheets"), vaitteet
ilman numeroa ("the best captain") ja sen onko luku oikea VASTAUS kohde-
postauksen kysymykseen. Ne jaavat Villen hyvaksynnalle.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402

AGE_LIMIT_MIN = 240
BLOCKLIST_PATH = config.DATA_DIR / "reply_blocklist.json"
FIELDS = ("kohde", "tekija", "julkaistu", "luonnos", "liite", "luvut", "tarkistus", "cta")

_FIELD_RE = re.compile(r"^\s*(" + "|".join(FIELDS) + r")\s*:\s?(.*)$", re.I)
_KEYVAL_RE = re.compile(r"([a-z0-9_]+(?:\.[a-z0-9_\-]+)+)\s*=\s*([+\-]?\d+(?:[.,]\d+)?%?)", re.I)
_NUM_RE = re.compile(r"(?<![\w.])[+\-]?\d+(?:[.,]\d+)?(?![\w])")
_GW_RE = re.compile(r"\b(?:GW|gameweek\s*)(\d{1,2})\b", re.I)
_URL_RE = re.compile(r"https?://\S+|www\.\S+|\b[\w-]+\.(?:app|com|net|org|io|co|uk)\b\S*", re.I)
_HANDLE_RE = re.compile(r"@\w+")


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def parse_draft(text: str) -> dict:
    """Kentat `nimi: arvo`; seuraavat rivit ilman kenttanimea jatkavat edellista.
    Koodiaidat (```), otsikot (#) ja lainaukset (>) ohitetaan."""
    out: dict = {}
    cur = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.strip().startswith(("```", "#", ">")):
            cur = None if line.strip().startswith("```") else cur
            continue
        m = _FIELD_RE.match(line)
        if m:
            cur = m.group(1).lower()
            out[cur] = m.group(2).strip()
        elif cur and line.strip():
            out[cur] = (out[cur] + " " + line.strip()).strip()
    return out


def parse_ts(s: str) -> datetime | None:
    """'2026-09-22T08:15Z', '2026-09-22 08:15 UTC', '2026-09-22T08:15:00+00:00'."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)\s*(Z|UTC|[+\-]\d{2}:?\d{2})?",
                  s or "")
    if not m:
        return None
    tz = m.group(3) or ""
    if tz.upper() in ("Z", "UTC", ""):
        tz = "+00:00"
    elif len(tz) == 5:
        tz = tz[:3] + ":" + tz[3:]
    try:
        t = datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}{tz}")
    except ValueError:
        return None
    if not m.group(3):
        return None  # aika ilman vyohyketta ei kelpaa: 3 h virhe olisi hiljainen
    return t.astimezone(timezone.utc)


def target_handles(fields: dict) -> list[str]:
    hs = []
    m = re.search(r"(?:x|twitter)\.com/(\w+)/status", fields.get("kohde") or "", re.I)
    if m:
        hs.append(m.group(1))
    m = re.search(r"@(\w+)", fields.get("tekija") or "")
    if m and m.group(1).lower() not in {h.lower() for h in hs}:
        hs.append(m.group(1))
    return hs


def _num(t: str) -> float | None:
    try:
        return float(str(t).replace("%", "").replace(",", ".").strip())
    except ValueError:
        return None


def load_blocklist(path: Path = BLOCKLIST_PATH) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    return {a["handle"].lower(): a for a in d.get("accounts") or []}


def check_draft(text: str, *, now: datetime, loader, surfaces, blocklist: dict) -> list[Check]:
    """Puhdas ydin. loader(gw, keys) -> moduuli (tai ReplyModuleRefused);
    surfaces(needed, gw) -> (pages, meta, virheet)."""
    from src.marketing.reply_module import (ReplyModuleRefused, norm_text, value_index,
                                            verify_value)
    f = parse_draft(text)
    out: list[Check] = []
    body = f.get("luonnos") or ""
    pairs = _KEYVAL_RE.findall(f.get("luvut") or "")
    luvut = {k.lower(): v for k, v in pairs}
    gw_m = re.search(r"\bgw\s*(\d{1,2})\b", f.get("tarkistus") or "", re.I)
    gw = int(gw_m.group(1)) if gw_m else None

    # --- 1. jokainen tekstin numero on luvut-rivilla -----------------------
    if not body:
        out.append(Check("1 luvut-kattavuus", False, "luonnos: puuttuu"))
    else:
        t = _URL_RE.sub(" ", _HANDLE_RE.sub(" ", body))
        errs = []
        for m in _GW_RE.finditer(t):
            if gw is None or int(m.group(1)) not in _allowed_gws(gw, luvut):
                errs.append(f"'{m.group(0)}' ei ole moduulin kierros (tarkistus: gw{gw})")
        t = _GW_RE.sub(" ", t)
        if re.search(r"\b10\s*\+", t):
            if not any(k.endswith(".p_10plus") for k in luvut):
                errs.append("'10+' ilman P(10+)-lukua luvut-rivilla")
            t = re.sub(r"\b10\s*\+", " ", t)
        vals = [_num(v) for v in luvut.values()]
        for m in _NUM_RE.finditer(t):
            n = _num(m.group(0))
            if n is None or not any(v is not None and abs(abs(n) - abs(v)) < 1e-9 for v in vals):
                errs.append(f"'{m.group(0)}' ei ole luvut-rivilla")
        out.append(Check("1 luvut-kattavuus", not errs,
                         "; ".join(errs) or f"{len(_NUM_RE.findall(t))} numeroa, kaikki luvut-rivilla"))

    # --- 2. luvut tuoreesta moduulista + ilmaispinnalla nyt ----------------
    if not luvut:
        out.append(Check("2 moduuli", True, "ei lukuja (ihmisaani ilman dataa)"))
    elif gw is None:
        out.append(Check("2 moduuli", False, "tarkistus:-rivilta puuttuu 'moduuli gw{N}'"))
    else:
        errs = []
        try:
            mod = loader(gw, sorted(luvut))
        except ReplyModuleRefused as e:
            mod = None
            errs.append(f"moduuli kieltaytyi: {e}")
        if mod is not None:
            idx = value_index(mod.get("sections") or {})
            needed = set()
            for k, want in luvut.items():
                v = idx.get(k)
                if v is None:
                    errs.append(f"{k}: ei moduulissa")
                    continue
                if norm_text(v["text"]) != norm_text(want):
                    errs.append(f"{k}: luonnoksessa {want}, moduulissa {v['text']}")
                if not v.get("public_url"):
                    errs.append(f"{k}: ei ilmaispinnalla (public_url null), ei julkiseen tekstiin")
                    continue
                if v["public_url"] not in (f.get("tarkistus") or ""):
                    errs.append(f"{k}: tarkistus:-rivilta puuttuu {v['public_url']}")
                sid = (v.get("check") or [None])[0]
                if sid:
                    needed.add("points_gw" if sid == "points_gw" else sid)
            if not errs and needed:
                pages, _meta, perr = surfaces(needed, gw)
                errs += perr
                mvt = (mod.get("sections") or {}).get("model_vs_template") or {}
                ctx = {"template_picks_gw": mvt.get("template_picks_gw")}
                for k in luvut:
                    v = idx[k]
                    url, err, _r = verify_value(v, pages, gw, k.rsplit(".", 1)[1], ctx)
                    if err:
                        errs.append(f"{k}: sivu muuttunut: {err}")
                    elif url is None:
                        errs.append(f"{k}: ei loydy enaa sivulta {v['public_url']}")
        out.append(Check("2 moduuli", not errs,
                         "; ".join(errs) or f"{len(luvut)} lukua, tuore moduuli gw{gw}, sama teksti sivulla nyt"))

    # --- 3. tuoreus ---------------------------------------------------------
    ts = parse_ts(f.get("julkaistu") or "")
    if ts is None:
        out.append(Check("3 tuoreus", False, "julkaistu: puuttuu tai ilman aikavyohyketta (UTC)"))
    else:
        age = (now - ts).total_seconds() / 60
        ok = -5 <= age < AGE_LIMIT_MIN
        out.append(Check("3 tuoreus", ok,
                         f"kohde {age:.0f} min vanha (raja {AGE_LIMIT_MIN})"
                         + ("" if age >= -5 else ", aikaleima tulevaisuudessa")))

    # --- 4. kohdetili ------------------------------------------------------
    hs = target_handles(f)
    if not hs:
        out.append(Check("4 kohdetili", False, "kohde:-URL:sta ei loydy kahvaa"))
    else:
        hit = [(h, blocklist[h.lower()]) for h in hs if h.lower() in blocklist]
        out.append(Check("4 kohdetili", not hit,
                         "; ".join(f"@{h}: {a['line']} ({a['reason']})" for h, a in hit)
                         or f"@{hs[0]} ei estolistalla"))

    # --- 5. ei linkkia eika tuotenimea -------------------------------------
    bad = []
    if _URL_RE.search(body):
        bad.append("linkki tai domain tekstissa")
    if re.search(r"goal\s*iq", body, re.I):
        bad.append("tuotenimi tekstissa")
    out.append(Check("5 CTA", not bad, "; ".join(bad) or "ei linkkia eika tuotenimea"))
    return out


def _allowed_gws(gw: int, luvut: dict) -> set[int]:
    """Moduulin kierros + last_gw:n kierros jos sen lukuja kaytetaan."""
    allowed = {gw}
    if any(k.startswith("last_gw.") for k in luvut):
        allowed.add(gw - 1)
    if any(k.startswith("track_record.xp_mae") for k in luvut):
        allowed.add(gw - 1)
    return allowed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="X-reply fast-lane gate")
    ap.add_argument("draft")
    ap.add_argument("--now", default=None, help="UTC-aika (testaus), oletus nyt")
    a = ap.parse_args(argv)
    from src.marketing.reply_module import fetch_surfaces, load_reply_module
    text = Path(a.draft).read_text(encoding="utf-8")
    now = parse_ts(a.now) if a.now else datetime.now(timezone.utc)
    checks = check_draft(
        text, now=now,
        loader=lambda gw, keys: load_reply_module(gw, keys=keys, now=now),
        surfaces=lambda needed, gw: fetch_surfaces(needed, gw),
        blocklist=load_blocklist())
    for c in checks:
        print(f"{'PASS' if c.ok else 'FAIL'}  {c.name}: {c.detail}")
    ok = all(c.ok for c in checks)
    print("\nFAST-LANE: " + ("PASS, Villen hyvaksynta riittaa." if ok else
                             "FAIL, korjaa luonnos tai aja moduuli uudelleen."))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
