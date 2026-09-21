"""Beat the Model V2 -vahti: FPL-tilin rivi vs jäädytetty rivi (14.8).

MIKSI TÄMÄ ON OLEMASSA. `freeze_model_squad_gw.py` lukitsee mallin rungon
tiedostoon ja tekee siitä todistettavan git-historiasta. Mutta se EI kosketa
FPL-tiliä: rivi syötetään FPL:ään käsin. Nämä kaksi ovat siis kaksi eri
totuutta mallin joukkueesta, ja niiden välillä ei ollut mitään joka
huomaisi eron.

Mitattu 14.8: entryn rivi valittiin käsin **23.7** — eli ENNEN 13.8:n
P0-korjausta joka muutti mallin XI:n (101,5 m laiton runko → 100,0 m,
XI xP 311,91 → 277,49). Jos entryä ei päivitetty, "malli pelaa omaa
FPL-joukkuettaan" osoittaa joukkueeseen jota malli ei valinnut — ja koko
Beat the Model, Season race ja "logged before kickoff" nojaavat siihen.

Vahti ei voi korjata tätä (FPL-tilille kirjautuminen on käsityötä eikä sitä
automatisoida). Se tekee erosta ÄÄNEKKÄÄN:

  * ennen deadlinea  -> tulostaa rivin syötettävässä muodossa, exit 0
  * deadlinen jälkeen -> vertaa entryn picksejä jäädytettyyn ja kirjaa eron
                         freezen metaan. 21.9.2026 alkaen ero = ::warning::
                         ja exit 0 (Villen paatos "mallin rivi": julkinen
                         sarja on jaadytetty rivi, joten ero ei siirry
                         mallin lukuun). Exit 1 jaa 404:lle, rikkinaiselle
                         poikkeukselle ja yli 24 h lukemattomalle kierrokselle.

Ennen-deadlinea-haara on tarkoituksella exit 0: rivin syöttäminen on
Villen tehtävä eikä puuttuva syöttö ole vielä virhe. Jälkeen-haara on
exit 1, koska silloin se on peruuttamaton.

KIRJATTU POIKKEUS (29.8). GW2:ssa Ville pelasi wildcardin XP-SEASON-CARRY-
korjatun mallin optimilla, mutta gw2.json oli jäädytetty vanhan mallin
kannalla ja jäi Villen päätöksellä arkistoksi. Vahti kaatui oikein — mutta
koska sillä ei ollut continue-on-erroria, se padotti commit-askeleen ja
KOKO refresh-data jäätyi 28.8 17:08:aan (3 punaista ajoa). Nyt: tiedosto
`data/model_squad_exceptions/gw{N}.json` (kentät gw, reason, decided_by,
decided_at) muuttaa eron ::warning::-riviksi ja exit 0:ksi VAIN sille
kierrokselle. Poikkeus ilman syytä tai väärälle kierrokselle on itsessään
virhe (exit 1) — se ei ole vapaakortti. OMA HAKEMISTO: ensimmäinen versio
(29.8 aamu) pani tiedoston freeze-kansioon nimellä gw2.exception.json, ja
graderien `glob("gw*.json")` luki sen runkona → int(None) → commit padottui
uudelleen. Freeze-kansiossa saa olla vain gw{N}.json (testi vartioi).

Käyttö:
    python -m scripts.verify_model_entry_matches_freeze          # uusin GW
    python -m scripts.verify_model_entry_matches_freeze --gw 1
    python -m scripts.verify_model_entry_matches_freeze --print  # aina tuloste
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

import config

FROZEN_DIR = config.PROJECT_ROOT / "data" / "model_squad_frozen"
# Poikkeukset OMASSA hakemistossa: freeze-kansion glob("gw*.json") lukisi ne runkoina.
EXCEPTIONS_DIR = config.PROJECT_ROOT / "data" / "model_squad_exceptions"
FPL_BASE = "https://fantasy.premierleague.com/api"
FPL_HEADERS = {"User-Agent": "Mozilla/5.0 (GoalIQ entry-check job)"}

# Entry EI ole kovakoodattu vaan ymparistosta, jotta tama skripti ei ole
# ainoa paikka jossa mallin tilinumero elaa. Oletus on nykyinen tili.
ENTRY_ID = int(os.environ.get("FPL_MODEL_ENTRY_ID", "116920"))

POS_NAME = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def latest_frozen() -> Path | None:
    """Suurin gw{N}.json. Nimesta luetaan numero, ei lajitella merkkijonona
    (gw10 < gw9 merkkijonona)."""
    if not FROZEN_DIR.exists():
        return None
    best, best_gw = None, -1
    for p in FROZEN_DIR.glob("gw*.json"):
        m = re.fullmatch(r"gw(\d+)\.json", p.name)
        if not m:
            continue
        n = int(m.group(1))
        if n > best_gw:
            best, best_gw = p, n
    return best


def enterable(frozen: dict) -> str:
    """Runko muodossa jonka voi syottaa FPL:aan rivi kerrallaan."""
    lines = []
    cap, vice = frozen.get("captain"), frozen.get("vice_captain")
    for label, rows in (("XI", frozen.get("xi") or []),
                        ("PENKKI (jarjestyksessa)", frozen.get("bench") or [])):
        lines.append(f"  {label}:")
        for i, p in enumerate(rows, 1):
            mark = ""
            if p.get("id") == cap:
                mark = "  <- KAPTEENI"
            elif p.get("id") == vice:
                mark = "  <- VARAKAPTEENI"
            pos = POS_NAME.get(p.get("pos"), "?")
            price = (p.get("price") or 0) / 10
            lines.append(f"    {i:>2}. {pos} {p.get('web_name','?'):<16} "
                         f"{p.get('team_short','?'):<4} {price:>4.1f}m{mark}")
    return "\n".join(lines)


EXCEPTION_KEYS = ("gw", "reason", "decided_by", "decided_at")


def load_exception(gw: int) -> tuple[dict | None, str | None]:
    """(poikkeus, virhe). Poikkeus on voimassa vain jos tiedosto on olemassa,
    sen gw on sama ja kaikki kentat ovat epatyhjia. Vaara tai vajaa poikkeus
    palautetaan virheena, ei ohiteta hiljaa."""
    path = EXCEPTIONS_DIR / f"gw{gw}.json"
    if not path.exists():
        return None, None
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return None, f"{path.name}: ei kelvollista JSONia ({e!r})"
    missing = [k for k in EXCEPTION_KEYS if not str(d.get(k) or "").strip()]
    if missing:
        return None, f"{path.name}: kentat puuttuvat tai tyhjia: {', '.join(missing)}"
    if int(d.get("gw") or 0) != gw:
        return None, f"{path.name}: gw={d.get('gw')} mutta tiedosto on GW{gw}:n"
    return d, None


#: Kuinka kauan deadlinen jalkeen "en saanut luettua" saa olla pelkka varoitus.
#: Sen jalkeen se on oma vikansa: FPL ei ole ollut poissa vuorokautta.
UNREACHABLE_ESCALATE_H = 24
#: Uudelleenyritykset transientille vastaukselle (5xx/429/verkkovirhe).
RETRIES = 3
RETRY_SLEEP_S = (2, 5, 12)


def fetch_picks(entry: int, gw: int, *, sleep=None):
    """(picks, status, kind). picks=None kun ei saatavilla.

    🔴 KOLME TILAA, EI KAHTA (12.9.2026). Ennen tama palautti vain
    `(None, syy)` ja kutsuja tulkitsi JOKAISEN Nonen samaksi asiaksi.
    Mitattu 12.9: GH-runnerilla FPL vastasi **503**, ja skripti tulosti
    *"Joko tilia ei ole pelattu tassa kierroksessa tai entry-id on vaara"* —
    kumpikaan ei ollut totta. Step health kaansi sen viela muotoon
    *"FPL-entry EI VASTAA jaadytettya runkoa ... kirjaa poikkeus"*, eli
    operaattoria kehotettiin **valkolistaamaan ero jota ei ollut mitattu**.
    Poikkeus olisi jaanyt voimaan sille kierrokselle pysyvasti.

    `kind` on nyt eksplisiittinen:
      "ok"          200, picks luettu
      "not_played"  404 — tilia ei ole pelattu talla kierroksella (aito tieto)
      "unreachable" 5xx / 429 / verkkovirhe / rikkinainen JSON — EI TIETOA

    "ei tietoa" ei ole "ei vastaa" (muisti: `nolla-ei-ole-sama-kuin-ei-tietoa`).
    """
    import time

    sleep = sleep if sleep is not None else time.sleep
    url = f"{FPL_BASE}/entry/{entry}/event/{gw}/picks/"
    viimeisin = "?"
    for yritys in range(RETRIES):
        try:
            r = requests.get(url, headers=FPL_HEADERS, timeout=30)
        except Exception as e:
            viimeisin = f"verkkovirhe: {e!r}"
        else:
            if r.status_code == 404:
                return None, "404", "not_played"
            if r.status_code == 200:
                try:
                    return r.json().get("picks") or [], "200", "ok"
                except Exception as e:
                    viimeisin = f"JSON-virhe: {e!r}"
            else:
                viimeisin = f"HTTP {r.status_code}"
        if yritys < RETRIES - 1:
            sleep(RETRY_SLEEP_S[min(yritys, len(RETRY_SLEEP_S) - 1)])
    return None, viimeisin, "unreachable"


def record_verification(path: Path, frozen: dict, gw: int, *, squad_match: bool,
                        captain_match: bool, common: int, now,
                        lineup_match: bool | None = None) -> None:
    """Kirjoittaa `meta.entry_verified` samaan artefaktiin. Ei erillista
    tiedostoa freeze-hakemistoon: vieras tiedosto glob-kansiossa luettiin
    runkona 29.8. Kirjoitetaan vain kun tosiasia muuttuu (aikaleima ei ole
    tosiasia), jotta CI:n commit ei kasva joka yo."""
    from src.models.fpl_model_entry import verified_record
    rec = verified_record(gw, ENTRY_ID, squad_match=squad_match,
                          captain_match=captain_match,
                          at=now.strftime("%Y-%m-%dT%H:%M:%SZ"), common=common,
                          lineup_match=lineup_match)
    meta = frozen.setdefault("meta", {})
    vanha = dict(meta.get("entry_verified") or {})
    vanha.pop("at", None)
    uusi = dict(rec)
    uusi.pop("at", None)
    if vanha == uusi:
        return
    meta["entry_verified"] = rec
    # 🔴 SAMA SARJALLISTUS KUIN FREEZELLA (12.9.2026). Ilman `separators`ia
    # json.dumps kirjoittaa valilyonnit joka erottimen jalkeen ja jattaa
    # rivinvaihdon pois: yhden metakentan lisays nayttaa gitissa KOKO rungon
    # uudelleenkirjoitukselta. Koko V2:n vaite on "todistettavissa
    # git-historiasta", ja se lepaa sen varassa etta diffista nakee yhdella
    # silmayksella ettei riviin ole koskettu.
    # `newline="\n"`: Windowsilla oletus kirjoittaisi CRLF:n ja koko tiedosto
    # nayttaisi muuttuneelta (.gitattributes normalisoi commitissa, mutta
    # tyopuun diffi ja jokainen lokaali tarkistus valehtelisi silti).
    path.write_text(
        json.dumps(frozen, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8", newline="\n")
    print(f"meta.entry_verified kirjoitettu: match={rec['match']} "
          f"(15: {rec['squad_match']}, C: {rec['captain_match']}, "
          f"kokoonpano: {rec.get('lineup_match')}, yhteisia {rec['common']})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gw", type=int, default=None)
    ap.add_argument("--print", dest="always_print", action="store_true")
    args = ap.parse_args()

    path = (FROZEN_DIR / f"gw{args.gw}.json") if args.gw else latest_frozen()
    if path is None or not path.exists():
        # EI VIRHE: ennen kauden ensimmaista freezea hakemistoa ei ole.
        print("::notice::Ei jaadytettya runkoa viela — ei verrattavaa.")
        return 0

    frozen = json.loads(path.read_text(encoding="utf-8"))
    meta = frozen.get("meta") or {}
    gw = int(meta.get("gw") or 0)
    deadline = _dt.datetime.fromisoformat(
        str(meta.get("deadline", "")).replace("Z", "+00:00"))
    now = _dt.datetime.now(_dt.timezone.utc)

    frozen_ids = {p["id"] for p in (frozen.get("xi") or [])}
    frozen_ids |= {p["id"] for p in (frozen.get("bench") or [])}

    print(f"GW{gw} jaadytetty {meta.get('frozen_at')}, deadline {meta.get('deadline')}")
    print(f"entry {ENTRY_ID}, jaadytetyssa {len(frozen_ids)} pelaajaa")

    if now < deadline:
        left = deadline - now
        h = int(left.total_seconds() // 3600)
        print(f"::notice::Deadlineen {h} h — rivi on syotettava FPL-tilille "
              f"ENNEN sita. Vahti kaantyy virheeksi deadlinen jalkeen.")
        print(enterable(frozen))
        return 0

    picks, status, kind = fetch_picks(ENTRY_ID, gw)
    if kind == "unreachable":
        # EI TIETOA. Ei saa nayttaa erolta eika saa kehottaa poikkeukseen.
        ika_h = (now - deadline).total_seconds() / 3600.0
        jo_verifioitu = bool((meta.get("entry_verified") or {}).get("at"))
        if ika_h >= UNREACHABLE_ESCALATE_H and not jo_verifioitu:
            print(f"::error::Entryn {ENTRY_ID} GW{gw}-rivia ei ole saatu "
                  f"luettua {ika_h:.0f} h deadlinen jalkeen ({status}, "
                  f"{RETRIES} yritysta). Tama ei ole enaa transientti: "
                  f"vahti ei ole ajanut kertaakaan talle kierrokselle, joten "
                  f"'malli pelaa omaa joukkuettaan' on tarkistamatta. ALA "
                  f"kirjaa poikkeusta — poikkeus koskee mitattua EROA, ei "
                  f"mittaamatta jaanytta kierrosta.")
            return 1
        print(f"::warning::Entryn {ENTRY_ID} GW{gw}-rivi ei ollut luettavissa "
              f"({status}, {RETRIES} yritysta, {ika_h:.1f} h deadlinesta). "
              f"Tama on upstream-tila, EI ero jaadytettyyn runkoon: mitaan "
              f"ei ole verrattu. Vahti yrittaa uudelleen seuraavassa ajossa "
              f"ja kaantyy virheeksi {UNREACHABLE_ESCALATE_H} h kohdalla jos "
              f"lukemista ei saada kertaakaan lapi.")
        return 0
    if picks is None:
        print(f"::error::Entryn {ENTRY_ID} GW{gw}-rivi ei ole luettavissa "
              f"({status}) vaikka deadline on mennyt: FPL vastasi 404. "
              f"Joko tilia ei ole pelattu tassa kierroksessa tai entry-id "
              f"on vaara.")
        return 1

    from src.models.fpl_model_entry import entry_diff
    diff = entry_diff(frozen, picks)

    # 5.9 KORTTI-PROVENIENSSI-PORTTI: tulos kirjoitetaan freezen metaan, jotta
    # kortin generaattori (ja seuraavan kierroksen ketju) lukee "onko tama
    # entryn runko" yhdesta paikasta eika oleta. Kirjoitetaan MYOS ero: se on
    # eksplisiittinen kielto, ei vain puuttuva lupa. 21.9: myos kokoonpano
    # (`lineup_match`), jota vahti ei aiemmin nahnyt lainkaan.
    record_verification(path, frozen, gw, squad_match=diff["squad_match"],
                        captain_match=diff["captain_match"],
                        common=diff["common"], now=now,
                        lineup_match=diff["lineup_match"])

    if args.always_print:
        print(enterable(frozen))

    exception, exc_err = load_exception(gw)
    if exc_err:
        print(f"::error::Poikkeustiedosto on rikki: {exc_err}. Poikkeus ei ole "
              f"vapaakortti — korjaa tiedosto tai poista se.")
        return 1

    if not diff["diverged"]:
        if exception:
            print(f"::warning::GW{gw}:lle on kirjattu poikkeus mutta rivit "
                  f"tasmaavat (15/15 + kapteeni + kokoonpano) — poikkeus on "
                  f"vanhentunut, poista {EXCEPTIONS_DIR.name}/gw{gw}.json.")
        print(f"OK: entry {ENTRY_ID} vastaa GW{gw}:n jaadytettya runkoa "
              f"(15/15 + kapteeni + kokoonpano).")
        return 0

    # 🔴 ERO ON SALLITTU, EI VIRHE (Villen paatos 21.9.2026, "mallin rivi").
    # Ennen tama oli exit 1, koska julkinen sarja mittasi ENTRYA ja ero
    # tarkoitti etta "mallin luku" oli Villen luku. Nyt julkinen sarja on
    # jaadytetty rivi (`model_squad_scores.load_public_model_series`), joten
    # ero ei siirry mallin lukuun - se kirjataan (freezen meta +
    # jaadytetyn graderin rivi `entry_diverged`) ja sanotaan aaneen.
    names = {p["id"]: p.get("web_name", "?")
             for p in (frozen.get("xi") or []) + (frozen.get("bench") or [])}

    def _nimet(ids):
        return ", ".join(f"{names.get(i, i)} ({i})" for i in ids) or "-"

    print(f"::warning::ENTRY {ENTRY_ID} poikkeaa GW{gw}:n jaadytetysta rivista. "
          f"Julkinen sarja mittaa jaadytettya rivia (Villen paatos 21.9), joten "
          f"ero on kirjattu eika se ole virhe.")
    if exception:
        print(f"  Kirjattu poikkeus: {exception['reason']} "
              f"({exception['decided_by']} {exception['decided_at']})")
    print(f"  15: yhteisia {diff['common']}; jaadytetyssa mutta ei tililla: "
          f"{_nimet(diff['missing'])}; tililla mutta ei jaadytetyssa: "
          f"{', '.join(str(i) for i in diff['extra']) or '-'}")
    print(f"  XI: vain jaadytetyssa {_nimet(diff['xi_only_frozen'])}; vain "
          f"tililla {', '.join(str(i) for i in diff['xi_only_entry']) or '-'}")
    print(f"  kapteeni {'sama' if diff['captain_match'] else 'ERI'}, "
          f"varakapteeni {'sama' if diff['vice_match'] else 'ERI'}, "
          f"penkkijarjestys {'sama' if diff['bench_order_match'] else 'ERI'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
