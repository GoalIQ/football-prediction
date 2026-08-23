# -*- coding: utf-8 -*-
"""Per-gameweek-rivit pelaajatilastoille (fpl/player-gw.json).

MIKSI (Villen pyynto 9.8): /fpl/stats.html nayttaa kausisummia, eika niista voi
laskea "GW1-6" jalkikateen. Tama tiedosto antaa saman datan kierroksittain,
jolloin sivu voi aggregoida minka tahansa gameweek-ikkunan selaimessa.

MIKSI ERILLINEN TIEDOSTO EIKA SIVUN SISALLA: mitattu 551 KB (122 KB
gzipattuna). Sivu itse on 135 KB, joten inline kolminkertaistaisi sen KAIKILLE
- myos sille enemmistolle joka ei koske suodattimeen. Sivu hakee taman vasta
kun kayttaja ensimmaisen kerran vaihtaa ikkunaa.

KAUSIVAIHDOS: FPL:n element-id:t NOLLAUTUVAT kausien valilla, joten mappaus
tehdaan `code`-kentalla joka on pysyva. Ilman tata katettiin 269/400 pelaajaa
ja loput olisivat nayttaneet tyhjaa ikkunaa ilman virhetta (mitattu 9.8).

BASIS SEURAA STATS-SIVUA: kausi luetaan fpl_player_stats.json:n metasta, joten
GW-rivit eivat voi olla eri kaudelta kuin sivun kausisummat. Jos ne eriytyisivat,
ikkunan summa ei tasmaisi "kaikki kierrokset" -nakymaan eika kukaan huomaisi.

SARAKERAJAUS: mukana ovat VAIN FPL:n virallisen APIn kentat. Laukaustason
sarakkeet (shots, npxG, key passes, xGChain...) tulevat Understatista ilman
kierroskohtaista erittelya, joten niita EI voi ikkunoida. Sivu tietaa taman ja
sanoo sen; hiljainen nolla olisi pahempi kuin puuttuva sarake.

AJO:  python scripts/build_fpl_player_gw.py
"""

from __future__ import annotations

import gzip
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CACHE = ROOT / "data" / "raw" / "fpl"
STATS = ROOT / "data" / "fpl_player_stats.json"
OUT = ROOT / "fpl" / "player-gw.json"

# Kokonaisluvut ja liukuluvut erikseen: liukuluvut pyoristetaan 2 desimaaliin,
# mika pudottaa tiedostokoon noin neljanneksella ilman etta yksikaan sivulla
# nakyva luku muuttuu (sivu nayttaa 2 desimaalia).
INT_FIELDS = [
    ("pts", "total_points"), ("g", "goals_scored"), ("a", "assists"),
    ("tkl", "tackles"), ("cbi", "clearances_blocks_interceptions"),
    ("rec", "recoveries"), ("dc", "defensive_contribution"),
    ("cs", "clean_sheets"), ("gc", "goals_conceded"), ("saves", "saves"),
    ("bps", "bps"), ("bonus", "bonus"), ("yc", "yellow_cards"),
    ("rc", "red_cards"), ("starts", "starts"), ("mins", "minutes"),
]
FLOAT_FIELDS = [
    ("xg", "expected_goals"), ("xa", "expected_assists"),
    ("xgi", "expected_goal_involvements"), ("xgc", "expected_goals_conceded"),
    ("ict", "ict_index"),
]

SEASON_DIRS = {"2025/26": ("summary_2526", "bootstrap_static_2526.archive.json"),
               "2026/27": ("summary_2627", "bootstrap_static.json")}
SEASON_KEYS = {"2026/27": "2627"}
# Live-basiksella summary elaa joka GW — alle 6 h vanha tiedosto kelpaa
# (sama ikkuna kuin fixtures-cachella), vanhempi haetaan uudelleen.
LIVE_MAX_AGE_S = 6 * 3600


def _load(p: Path) -> dict:
    if not p.exists():
        raise SystemExit(f"Puuttuu: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def build() -> dict:
    stats = _load(STATS)
    basis = stats["meta"].get("basis_season")
    if basis not in SEASON_DIRS:
        raise SystemExit(
            f"Tuntematon basis_season {basis!r}. Lisaa se SEASON_DIRS:iin, "
            f"ala arvaa hakemistoa.")
    summary_dir_name, boot_name = SEASON_DIRS[basis]
    summary_dir = CACHE / summary_dir_name

    cur = _load(CACHE / "bootstrap_static.json")
    basis_boot = _load(CACHE / boot_name)
    # code on pysyva kausien yli; id ei ole.
    code_by_cur_id = {e["id"]: e.get("code") for e in cur["elements"]}
    basis_id_by_code = {e.get("code"): e["id"] for e in basis_boot["elements"]}

    idx = {c: i for i, c in enumerate(stats["meta"]["cols"])}
    players: dict[str, list[list]] = {}
    rows_total = 0
    missing: list[str] = []

    # 22.8 (GW1-kausivaihdos): kun basis on KULUVA kausi, levylla olevat
    # summaryt voivat olla ennen kierrosta haettuja (history tyhja) eika
    # mikaan muu askel paivita niita ennen kuin GW1 on finished ja
    # build_fpl_xp:n force-haku heraa. Ilman tata katettiin 0/31 pelaajaa
    # ja steppi punasi jokaisen refreshin. Haetaan puuttuvat ja yli 6 h
    # vanhat itse — kun xp-builderin force-haku palaa, tiedostot ovat
    # minuutteja vanhoja ja tama ei tee yhtaan verkkokutsua.
    live_basis = SEASON_KEYS.get(basis)
    haettu = 0

    for p in stats["players"]:
        cur_id = p[idx["id"]]
        code = code_by_cur_id.get(cur_id)
        basis_id = basis_id_by_code.get(code)
        f = summary_dir / f"element_{basis_id}.json" if basis_id else None
        if f is not None and live_basis and (
                not f.exists()
                or time.time() - f.stat().st_mtime > LIVE_MAX_AGE_S):
            try:
                from src.data.fpl_api import fetch_element_summary
                fetch_element_summary(basis_id, live_basis, force=True)
                haettu += 1
            except Exception as e:
                # Verkkovika: vanha tiedosto (jos on) kelpaa, puuttuva
                # paatyy missing-listalle alla — sanity paattaa.
                print(f"  varoitus: summary-haku {basis_id} epaonnistui: {e!r}")
        if not f or not f.exists():
            missing.append(str(p[idx["name"]]))
            continue
        hist = _load(f).get("history") or []
        rows = []
        for r in sorted(hist, key=lambda x: (x.get("round") or 0)):
            if (r.get("minutes") or 0) <= 0:
                continue      # nollaminuuttinen rivi ei muuta yhtaan summaa
            rows.append(
                [int(r.get("round") or 0)]
                + [int(r.get(src) or 0) for _, src in INT_FIELDS]
                + [round(float(r.get(src) or 0.0), 2) for _, src in FLOAT_FIELDS]
            )
        if rows:
            players[str(cur_id)] = rows
            rows_total += len(rows)

    if haettu:
        print(f"player-gw: haettiin {haettu} element-summarya (kuluva kausi, "
              f"cache oli tyhja tai yli {LIVE_MAX_AGE_S // 3600} h vanha).")
    return {
        "meta": {
            "basis_season": basis,
            "generated_at": stats["meta"].get("generated_at"),
            "cols": ["gw"] + [k for k, _ in INT_FIELDS] + [k for k, _ in FLOAT_FIELDS],
            "n_players": len(players),
            "n_rows": rows_total,
            # Sivu tarvitsee ylarajan valikkoon ENNEN kuin tama tiedosto on
            # ladattu (lataus on laiska), joten luku injektoidaan sivulle
            # build-aikana taalta.
            "max_gw": max((r[0] for rs in players.values() for r in rs),
                          default=0),
            "missing_players": missing,
            "note": ("Official FPL API per-gameweek history. Shot-level columns "
                     "(shots, npxG, key passes, xGChain) come from Understat "
                     "without a per-gameweek split and are not in this file."),
        },
        "players": players,
    }


def sanity(d: dict, stats: dict) -> list[str]:
    """Portti: ikkunan summa on tasmattava sivun kausisummaan."""
    fails = []
    m = d["meta"]
    want = len(stats["players"])
    if m["n_players"] < want:
        fails.append(f"katettu {m['n_players']}/{want} pelaajaa "
                     f"(puuttuu: {', '.join(m['missing_players'][:5])})")
    idx = {c: i for i, c in enumerate(stats["meta"]["cols"])}
    gidx = {c: i for i, c in enumerate(m["cols"])}
    # Kolme pelaajaa: kaikkien kierrosten summa vs sivun kausisumma.
    checked = 0
    for p in stats["players"][:40]:
        rows = d["players"].get(str(p[idx["id"]]))
        if not rows:
            continue
        for key in ("pts", "g", "a", "mins"):
            got = sum(r[gidx[key]] for r in rows)
            exp = p[idx[key]] if key in idx else None
            if exp is None:
                continue
            if got != exp:
                fails.append(f"{p[idx['name']]}: {key} summa {got} != sivun {exp}")
        checked += 1
        if checked >= 3:
            break
    if not checked:
        fails.append("yhtaan pelaajaa ei voitu ristiintarkistaa")
    return fails


def main() -> int:
    stats = _load(STATS)
    # 13.8: jäädytetyn basis-kauden lähdecache (arkisto-bootstrap + summary-
    # hakemisto) elää vain koneella jolla kausi arkistoitiin — CI-runnerilta
    # se puuttuu AINA eikä sitä voi enää hakea FPL-API:sta (API servaa vain
    # kuluvan kauden historiat). Jos committoitu output on jo samalta basis-
    # kaudelta, se on lopullinen → SKIP on oikea tulos, ei virhe. Kun basis
    # flippaa kuluvaan kauteen (GW1+), lähteet tulevat builderien tuoreesta
    # cachesta ja buildi ajaa CI:ssä normaalisti. Ilman tätä steppi failasi
    # accuracy-logissa joka ajossa 9.8–13.8 (26 punaista runia).
    # 23.8 (Villen havainto: "miksei fantasyssa pelaajien oikeat pisteet ole
    # paivittyneet muuten kuin Gabriel ja Tzolis"): ylla oleva SKIP kirjoitettiin
    # kun basis oli PAATTYNYT 25/26-kausi. Kun basis flippasi 22.8 kuluvaan
    # kauteen, sama ehto alkoi jaadyttaa ELAVAA outputtia: runnerilta puuttuu
    # `summary_2627/` (gitignore), joten jokainen ajo tulosti "SKIP" ja
    # `fpl/player-gw.json` jai 22.8 klo 07:45 tilaan — 31 pelaajaa, eli tasan ne
    # jotka olivat pelanneet ennen lauantain kierrosta. Steppi oli VIHREA koko
    # ajan, koska skip palauttaa 0.
    #
    # Kuluvan kauden summaryt ovat haettavissa (toisin kuin paattyneen kauden),
    # joten puuttuva hakemisto ei ole este vaan tyhja cache: luodaan se ja
    # annetaan build():n hakea puuttuvat (22.8:n lisays). SKIP jaa voimaan vain
    # jaadytetylle basis-kaudelle, jolle se kirjoitettiin.
    basis = stats["meta"].get("basis_season")
    live = SEASON_KEYS.get(basis)
    if basis in SEASON_DIRS and live:
        summary_dir_name, boot_name = SEASON_DIRS[basis]
        if not (CACHE / boot_name).exists():
            print(f"Puuttuu kuluvan kauden {basis} bootstrap ({boot_name}) — "
                  f"build_fpl_stats ei ole ajanut. Aito virhe.")
            return 1
        (CACHE / summary_dir_name).mkdir(parents=True, exist_ok=True)
    elif basis in SEASON_DIRS:
        summary_dir_name, boot_name = SEASON_DIRS[basis]
        if not (CACHE / boot_name).exists() or not (CACHE / summary_dir_name).exists():
            out_basis = None
            if OUT.exists():
                try:
                    out_basis = json.loads(
                        OUT.read_text(encoding="utf-8"))["meta"].get("basis_season")
                except Exception:
                    pass
            if out_basis == basis:
                print(f"basis {basis}: lähdecache puuttuu mutta committoitu "
                      f"output on jo samalta (jäädytetyltä) kaudelta — SKIP.")
                return 0
            print(f"Puuttuu basis-kauden {basis} lähdecache "
                  f"({boot_name} / {summary_dir_name}/) eikä kelvollista "
                  f"outputtia ole — tämä on aito virhe.")
            return 1
    d = build()
    fails = sanity(d, stats)
    if fails:
        print("SANITY FAIL:")
        for f in fails:
            print("  " + f)
        return 1
    s = json.dumps(d, separators=(",", ":"), ensure_ascii=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(s, encoding="utf-8")
    gz = len(gzip.compress(s.encode("utf-8")))
    print(f"player-gw.json: {d['meta']['n_players']} pelaajaa, "
          f"{d['meta']['n_rows']} riviä, {len(s)/1024:.0f} KB "
          f"({gz/1024:.0f} KB gzip), basis {d['meta']['basis_season']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
