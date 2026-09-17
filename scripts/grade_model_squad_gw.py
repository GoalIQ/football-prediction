"""Beat the Model V2 vaihe b: mallin joukkueen gradaus (13.8).

Kun jäädytetty GW on ratkennut (finished + data_checked), lasketaan mallin
lukitulle riville FPL:n omat pisteet: XI + autosubit + kapteenin tuplaus.
Append-only-loki data/model_squad_frozen_gw_scores.json.

🔴 OMA TIEDOSTO, EI JULKINEN SARJA (KAKSI-GRADERIA-YKSI-TIEDOSTO, 17.9.2026).
Tama graderi kirjoitti aiemmin samaan `data/model_squad_gw_scores.json`:iin
kuin entry-pohjainen `grade_model_squad.py`. Mitattu 12.9: sama GW3 olisi
tasta 63 p ja entrysta 72 p, ja sekaprovenienssi tarttuu (entry-graderi
pitaa rivin jolla ei ole provisional-kenttaa "jo lopullisena"). Villen
paatos 12.9: julkinen sarja on ENTRY-sarja (GW1-GW4 entrysta). Tama sarja on
diagnostiikkaa - mita jaadytetty runko OLISI tehnyt - eika mikaan julkinen
pinta lue sita. Polut ja provenienssisaannot ovat
`src/models/model_squad_scores.py`:ssa, ja sen lukija kieltaytyy antamasta
talle graderille entry-sarjaa vaikka polku osoitettaisiin sinne.

Säännöt ovat src/models/fpl_autosub.py:ssä puhtaana logiikkana ja katettu
omalla testisetillä (tests/test_fpl_autosub.py) — spec nimeää autosubin
ainoaksi oikeasti virhealttiiksi palaksi, ja väärä luku julkisessa
race-paneelissa on luottamusmyrkkyä.

Luku on tarkistettavissa: se lasketaan FPL:n `total_points`-kentästä
jäädytetylle riville, jonka git-historia todistaa lukituksi ennen deadlinea.

Idempotentti per GW. Exit 0 kun ei gradattavaa; tekninen virhe → 1.
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

import config
from src.models.fpl_autosub import score_gw
from src.models.model_squad_scores import (FROZEN_SCORES_PATH, SOURCE_FROZEN,
                                           SarjaVirhe, load_gw_scores,
                                           validate_gw_scores)

FROZEN_DIR = config.PROJECT_ROOT / "data" / "model_squad_frozen"
# Oma sarja, ei entry-sarja (ks. docstring). Polku maaritellaan lukijassa.
LOG_PATH = FROZEN_SCORES_PATH
FPL_BASE = "https://fantasy.premierleague.com/api"
FPL_HEADERS = {"User-Agent": "Mozilla/5.0 (GoalIQ grade job)"}

# Meta-kentat jotka lisataan kun sarja luodaan. `series_source` tulee
# lukijalta (`load_gw_scores`), ei tasta - sita ei voi unohtaa.
_META_DEFAULTS = {
        "product": ("GoalIQ Beat the Model — frozen-squad per-GW scores "
                    "(diagnostic series; the public season race reads the "
                    "entry series in model_squad_gw_scores.json)"),
        # 🔴 CHIP-KIELTOLAUSE POISTETTU TASTA METASTA (12.9.2026,
        # julkaisutarkistajan loydos). Se oli kovakoodattu vaite JULKISEEN
        # artefaktiin: `_NEW_LOG` kirjoitetaan kun `LOG_PATH` ei ole
        # olemassa, eli kausivaihdoksessa tai jos tiedosto poistetaan — ja
        # sitten vaite pushataan julkiseen repoon. Nykyinen artefakti on
        # puhdas vain siksi etta tiedosto on olemassa. Tasan saanto 6a kohta
        # 3: invariantti mitattu hetkella jolloin se sattuu pitamaan.
        #
        # Vaite oli myos epatosi: entry 116920 pelasi wildcardin GW2:ssa ja
        # triple captainin GW3:ssa, ja ne ovat kauden kaksi isointa lukua.
        # Chip-tieto elaa nyt rivin omassa `active_chip`-kentassa ja
        # `model-race`-payloadin `chips_played`issa, eika sita vaiteta
        # metassa lainkaan.
        "rules": ("The frozen squad is scored with official FPL points once "
                  "the gameweek finishes. Autosubs and the captain/vice rule "
                  "are applied exactly as FPL applies them. Only rows whose "
                  "frozen squad is provably the entry's squad are graded "
                  "(provenance). Append-only."),
}


def main() -> int:
    if not FROZEN_DIR.exists():
        print("Ei jäädytettyjä mallirivejä — ei gradattavaa.")
        return 0
    # 🔴 YKSI LUKIJA (17.9.2026): kaatuu jos LOG_PATH on entry-sarja tai
    # sekasarja. Vanha raaka `json.loads` olisi appendannut freeze-rivin
    # entry-sarjaan ja palauttanut 0. Tekninen virhe -> 1, mitaan ei kirjoiteta.
    try:
        log = load_gw_scores(LOG_PATH, source=SOURCE_FROZEN)
    except SarjaVirhe as e:
        print(f"::error::{LOG_PATH.name}: {e} Freeze-graderi ei kirjoita "
              f"mitaan. Sen oma sarja on {FROZEN_SCORES_PATH.name}; entry-sarjaan "
              f"kirjoittaa vain grade_model_squad.py.")
        return 1
    for k, v in _META_DEFAULTS.items():
        log["meta"].setdefault(k, v)
    done = {g.get("gw") for g in log["gameweeks"]}

    pending = []
    for f in sorted(FROZEN_DIR.glob("gw*.json")):
        frozen = json.loads(f.read_text(encoding="utf-8"))
        gw = frozen.get("meta", {}).get("gw")
        if gw not in done:
            pending.append((gw, frozen))
    if not pending:
        print("Kaikki jäädytetyt mallirivit on jo gradattu.")
        return 0

    try:
        r = requests.get(f"{FPL_BASE}/bootstrap-static/", headers=FPL_HEADERS,
                         timeout=30)
        r.raise_for_status()
        events = {int(e["id"]): e for e in r.json().get("events") or []}
    except Exception as e:
        print(f"VIRHE: bootstrap-haku epäonnistui: {e!r}")
        return 1

    graded = 0
    ohitetut_provenienssi = []
    for gw, frozen in pending:
        ev = events.get(int(gw))
        if not ev or not (ev.get("finished") and ev.get("data_checked")):
            print(f"GW{gw}: ei vielä ratkennut (finished+data_checked) — odotetaan.")
            continue
        # 🔴 SAMA PORTTI KUIN KORTILLA (12.9.2026, Villen päätös).
        #
        # Korttigeneraattori kieltäytyy renderöimästä runkoa jonka provenienssi
        # puuttuu (`require_entry_provenance`), mutta tämä graderi ei lukenut
        # sitä lainkaan: se olisi gradannut ilomielin rungon jonka oma meta
        # sanoo `squad_match: false`. Sama epäsymmetria kuin `_off_pool`
        # (yksi polku osasi tapauksen, toinen ei).
        #
        # Mitattu 12.9: gw4.json on runko jossa 8/15 vaihtui ja jonka meta
        # sanoo `transfers: []` — runko jota malli ei voi saavuttaa. Villen
        # päätös oli että GW4 gradataan ENTRYSTÄ (`grade_model_squad.py`),
        # kuten GW1–GW3 tosiasiassa on gradattu. Ilman tätä porttia päätös
        # jäisi cron-järjestyksen varaan: jos entry-putki kaatuu, tämä graderi
        # saa vuoron ja kirjaa väärän rungon pisteet append-only-lokiin
        # peruuttamattomasti. Portti tekee päätöksestä rakenteen.
        #
        # Fail-closed: puuttuva provenienssi EI gradaannu, ja ohitus sanotaan
        # ääneen `::warning::`-rivillä eikä vaieta.
        try:
            from src.models.fpl_model_entry import (ProvenienssiPuuttuu,
                                                    require_entry_provenance)
            peruste = require_entry_provenance(frozen, FROZEN_DIR)
        except ProvenienssiPuuttuu as e:
            ohitetut_provenienssi.append(int(gw))
            print(f"::warning::GW{gw} EI GRADATA: {e} Rivi jää tälle "
                  f"graderille gradaamatta; entry-pohjainen "
                  f"`grade_model_squad.py` kirjaa kierroksen entryn omista "
                  f"pisteistä. Tämä ei ole virhe vaan kieltäytyminen.")
            continue
        try:
            r = requests.get(f"{FPL_BASE}/event/{gw}/live/",
                             headers=FPL_HEADERS, timeout=60)
            r.raise_for_status()
            live = r.json()
        except Exception as e:
            print(f"VIRHE: event/{gw}/live-haku epäonnistui: {e!r}")
            return 1
        points, minutes = {}, {}
        for el in live.get("elements") or []:
            st = el.get("stats") or {}
            points[int(el["id"])] = int(st.get("total_points") or 0)
            minutes[int(el["id"])] = int(st.get("minutes") or 0)

        row = score_gw(frozen, points, minutes)
        row["graded_at"] = _dt.datetime.now(_dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        row["frozen_at"] = frozen.get("meta", {}).get("frozen_at")
        # 🔴 PROVENIENSSI RIVIIN ASTI (12.9.2026). Mitattu 12.9: entry-sarjan
        # GW1-GW3 ovat entry-pohjaisia, ja freeze-graderin sama GW3 olisi
        # 63 p eika 72 p. Ilman tata kenttaa sekaprovenienssi ei nay mistaan.
        # 17.9 alkaen sarjat ovat eri tiedostoissa, ja lukija vaatii etta
        # jokainen rivi sanoo provenienssinsa - se on se mita lukija mittaa.
        row["source"] = SOURCE_FROZEN
        row["provenance"] = peruste
        # Keskiarvo vertailukohdaksi: "voititko mallin" on eri kysymys kuin
        # "voititko keskiverto-FPL-managerin", ja molemmat kiinnostavat.
        row["fpl_average"] = ev.get("average_entry_score")
        log["gameweeks"].append(row)
        graded += 1
        subs = ", ".join(f"{s['out']}->{s['in']}" for s in row["autosubs"]) or "-"
        print(f"OK: GW{gw} mallin rivi gradattu — {row['points']} p "
              f"(ilman kapteenia {row['points_before_captain']}, "
              f"kapteeni {row['captain_reason']} +{row['captain_points_added']}), "
              f"autosubit: {subs}, penkille jäi {row['bench_points']} p, "
              f"FPL-keskiarvo {row['fpl_average']}.")

    if ohitetut_provenienssi:
        print(f"Provenienssin takia gradaamatta: GW{ohitetut_provenienssi}. "
              f"Nama kierrokset EIVAT saa pisteita tasta graderista; ne tulevat "
              f"entry-pohjaisesta `grade_model_squad.py`:sta tai jaavat auki.")
    if graded:
        # Portti ennen kirjoitusta: tulos on yhden provenienssin freeze-sarja.
        validate_gw_scores(log, source=SOURCE_FROZEN)
        LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
