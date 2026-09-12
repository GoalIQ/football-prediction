"""Perustajan FPL-historia julkisesta lähteestä (1.8.2026).

Miksi: etusivun uskottavuuslohko väitti "12 seasons", "best finish is top 6%"
ja "worst is 6,138,376" kovakoodattuna. Kaksi ongelmaa:
  1. "12 seasons" vanhenee joka kausi eikä mikään huomauta siitä.
  2. Lohko LINKKAA julkiseen entryyn, eli lukija voi tarkistaa luvut yhdellä
     klikkauksella. Väärä luku juuri siinä kohdassa on pahin mahdollinen,
     koska koko lohkon pointti on "anyone can check it".

Ratkaisu: luvut samasta lähteestä johon linkki osoittaa. "top 6%" pudotettiin,
koska prosentti vaatii kauden pelaajamäärän jota tämä API ei anna — sijaluku
sen sijaan on suoraan verifioitavissa.

Kirjoittaa data/founder_entry.json. Fail-safe: sanity FAIL → exit 2 → ei
tiedostoa → build_fpl_page jättää markerin koskematta (vanha teksti jää).

🔴 UPSTREAM-VIRHE EI OLE SANITY-VIRHE (12.9.2026). Askelen kommentti
workflow'ssa lupasi "fail-safe: jos FPL-API on nurin, askel ei kaada ajoa",
mutta `fetch()` ei ottanut kiinni yhtään verkkovirhettä: 12.9 GH-runnerin
saama **HTTP 503** nousi paljaana tracebackina ulos, ja Step health punasti
koko `fpl-data-refresh`-ajon (3 peräkkäistä). Luvattu fail-safe koski vain
sanityä.

Nyt kolme tilaa. Transientti (5xx/429/verkkovirhe) yritetään uudelleen, ja
jos se ei aukea, **vanha artefakti jää voimaan ja ajo jatkuu** — mutta vain
`STALE_ESCALATE_H` tuntia. Sen jälkeen se on oma vikansa eikä ohimenevä
häiriö, ja askel kaatuu äänekkäästi. Ilman ikärajaa tämä olisi juuri se
hiljainen jäätyminen jota `fail-safe-jaatyy-alavirtaan` varoittaa: etusivun
perustajalohko näyttäisi vanhaa lukua eikä mikään huutaisi.
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

ENTRY_ID = 1186244
API = f"https://fantasy.premierleague.com/api/entry/{ENTRY_ID}/history/"
OUT_PATH = config.DATA_DIR / "founder_entry.json"
UA = "Mozilla/5.0 (compatible; GoalIQ/1.0; +https://goaliq.app)"

SANITY_MIN_SEASONS = 5
SANITY_MAX_RANK = 20_000_000

#: Kuinka vanhaksi olemassa oleva artefakti saa jäädä upstream-häiriön takia.
STALE_ESCALATE_H = 36
RETRIES = 3
RETRY_SLEEP_S = (2, 5, 12)


def fetch() -> dict:
    req = urllib.request.Request(API, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_retry(*, sleep=None) -> tuple[dict | None, str]:
    """(payload, syy). payload=None kun upstream ei vastaa yrityksistä huolimatta."""
    import time

    sleep = sleep if sleep is not None else time.sleep
    viimeisin = "?"
    for yritys in range(RETRIES):
        try:
            return fetch(), "ok"
        except Exception as e:                      # noqa: BLE001 - upstream
            viimeisin = f"{type(e).__name__}: {e}"
        if yritys < RETRIES - 1:
            sleep(RETRY_SLEEP_S[min(yritys, len(RETRY_SLEEP_S) - 1)])
    return None, viimeisin


def artefaktin_ika_h(path: Path, *, now=None) -> float | None:
    """Olemassa olevan artefaktin ikä tunteina, tai None jos sitä ei ole.

    Luetaan `generated_at`-kentästä eikä tiedoston mtime:stä: CI:n checkout
    antaa jokaiselle tiedostolle checkout-hetken, joten mtime kertoisi
    runnerista eikä datasta (muisti: `git-archive-head-nayttaa-runnerin`).
    Molemmat puolet naiivia paikallista aikaa, samasta kellosta, jotta
    vertailu ei riipu ajokoneen vyöhykkeestä.
    """
    if not path.exists():
        return None
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        t = _dt.datetime.fromisoformat(str(d.get("generated_at")))
    except Exception:                                # noqa: BLE001
        return None
    if t.tzinfo is not None:
        t = t.astimezone().replace(tzinfo=None)
    return ((now or _dt.datetime.now()) - t).total_seconds() / 3600.0


def summarise(payload: dict) -> dict:
    past = [p for p in (payload.get("past") or []) if p.get("rank")]
    if not past:
        raise SystemExit("VIRHE: entryn historiassa ei ole yhtään kautta.")
    best = min(past, key=lambda p: p["rank"])
    worst = max(past, key=lambda p: p["rank"])
    return {
        "entry_id": ENTRY_ID,
        "generated_at": _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "source": API,
        "seasons": len(past),
        "first_season": past[0]["season_name"],
        "best": {"season": best["season_name"], "rank": best["rank"]},
        "worst": {"season": worst["season_name"], "rank": worst["rank"]},
    }


def sanity(d: dict) -> list[str]:
    fails = []
    if d["seasons"] < SANITY_MIN_SEASONS:
        fails.append(f"kausia {d['seasons']} < {SANITY_MIN_SEASONS}")
    if d["best"]["rank"] > d["worst"]["rank"]:
        fails.append("paras sija on huonompi kuin huonoin")
    for k in ("best", "worst"):
        if not 0 < d[k]["rank"] < SANITY_MAX_RANK:
            fails.append(f"{k}-sija epauskottava: {d[k]['rank']}")
    return fails


def ratkaise_upstream(syy: str, ika: float | None,
                      *, nimi: str = None) -> tuple[int, str]:
    """(exit-koodi, viesti) kun upstream ei vastannut.

    🔴 OMA FUNKTIO EIKA `__main__`-LOHKO (12.9.2026, tarkistuksen loydos).
    Ensimmainen versio kirjoitti taman paatoslogiikan suoraan
    `if __name__ == "__main__"` -lohkoon, jota **yksikaan testi ei voi ajaa**.
    Mitattu: kun `raise SystemExit(0)` vaihdettiin `SystemExit(1)`:ksi — eli
    tasan sama vika joka 12.9 punasti refreshin kolme kertaa — **koko 4207
    testin suite pysyi vihreana**. `fetch_retry` ja `artefaktin_ika_h` olivat
    katettuja erikseen, mutta paatos niiden valilla ei.
    """
    nimi = nimi or OUT_PATH.name
    if ika is None:
        return 1, (f"::error::FPL-API ei vastannut ({syy}, {RETRIES} yritysta) "
                   f"eika {nimi} ole olemassa — etusivun perustajalohkolle ei "
                   f"ole lukua lainkaan.")
    if ika >= STALE_ESCALATE_H:
        return 1, (f"::error::FPL-API ei ole vastannut ({syy}, {RETRIES} "
                   f"yritysta) ja {nimi} on {ika:.0f} h vanha (raja "
                   f"{STALE_ESCALATE_H} h). Etusivun perustajalohko nayttaa "
                   f"vanhentunutta lukua eika se ole enaa ohimenevaa.")
    return 0, (f"::warning::FPL-API ei vastannut ({syy}, {RETRIES} yritysta). "
               f"{nimi} on {ika:.1f} h vanha (raja {STALE_ESCALATE_H} h) — "
               f"vanha luku jaa voimaan, ajo jatkuu.")


if __name__ == "__main__":
    payload, syy = fetch_retry()
    if payload is None:
        koodi, viesti = ratkaise_upstream(syy, artefaktin_ika_h(OUT_PATH))
        print(viesti)
        raise SystemExit(koodi)
    data = summarise(payload)
    fails = sanity(data)
    if fails:
        print("SANITY FAIL:")
        for f in fails:
            print(" -", f)
        raise SystemExit(2)
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"OK: {data['seasons']} kautta ({data['first_season']}–), "
          f"paras {data['best']['rank']:,} ({data['best']['season']}), "
          f"huonoin {data['worst']['rank']:,} ({data['worst']['season']}) "
          f"-> {OUT_PATH}")
