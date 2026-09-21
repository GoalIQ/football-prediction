"""Beat the Model V2 vaihe b: mallin joukkueen gradaus (13.8).

Kun jäädytetty GW on ratkennut (finished + data_checked), lasketaan mallin
lukitulle riville FPL:n omat pisteet: XI + autosubit + kapteenin tuplaus.
Append-only-loki data/model_squad_frozen_gw_scores.json.

🔴 TAMA ON JULKINEN SARJA (Villen paatos 21.9.2026, kumoaa 12.9:n).
Julkinen track record, Season race ja tuloskortti mittaavat mallin
JAADYTETTYA rivia, eivat FPL-entrya 116920. Pinnat lukevat sen
`model_squad_scores.load_public_model_series()`:lla. Syy: 18.9 Ville ajoi
GW5:n jaadytetyn rivin yli (De Cuyper XI:iin Bobby Thomasin tilalle), ja
entry-sarja mittasi silloin mallin ja Villen yhdistelmaa. Kolme seurausta
tahan graderiin:

  1. Kelvollinen freeze gradataan MYOS kun entry poikkeaa siita. Ennen
     portti `require_entry_provenance` ohitti rungon jota ei ollut todistettu
     entryn rungoksi. Se oli oikein kun julkinen sarja oli entry, mutta nyt
     se jattaisi juuri mallin oman rivin gradaamatta (GW1, GW2). Ero
     kirjataan riville (`entry_diverged`, `entry_diff`), ja vertailija on
     yksi: `fpl_model_entry.entry_diff`, sama jota verify-vahti kayttaa.
  2. Rakenteellisesti epakelpo freeze (`freeze_invalid`: putosi vapaaseen
     optimiin, mitattu gw4.json 12.9) EI gradaudu: se ei ole mallin
     saavutettava rivi. Kierros jaa mallisarjasta pois nakyvalla koodilla
     (`unscored_gws`) eika saa entryn lukua (Villen paatos 21.9).
  3. Siirtokustannus kuuluu riviin (`transfer_cost`), ja se lasketaan
     FPL:N SAANNOILLA, ei freezen omasta FT-laskurista (mitattu vaaraksi:
     GW5 freeze sanoo 1 hitti, FPL:n saldo oli 3 -> 0 p, jonorivi
     FREEZE-FT-LASKURI-VAARIN). Ks. `_siirtokustannus`. Kun kustannusta ei
     voi todentaa, se kirjataan `None`:ksi ja rivi naytetaan bruttona
     nakyvalla merkinnalla (Villen paatos 21.9).

Entry-rivi haetaan ennen gradausta. Jos sita ei saada luettua, kierros
JATETAAN seuraavaan ajoon: loki on append-only, eika rivia jonka ero tai
kustannus on mittaamatta kirjoiteta peruuttamattomasti.

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
                                           UNSCORED_NO_VALID_FREEZE,
                                           SarjaVirhe, freeze_invalid,
                                           load_gw_scores, validate_gw_scores)

FROZEN_DIR = config.PROJECT_ROOT / "data" / "model_squad_frozen"
# Julkinen mallisarja (ks. docstring). Polku maaritellaan lukijassa.
LOG_PATH = FROZEN_SCORES_PATH
FPL_BASE = "https://fantasy.premierleague.com/api"
FPL_HEADERS = {"User-Agent": "Mozilla/5.0 (GoalIQ grade job)"}

#: FPL:n hitin hinta per ylimaarainen siirto.
HIT_POINTS = 4

# Meta-kentat. 21.9: KIRJOITETAAN AINA (ei setdefault): sarjan asema muuttui
# diagnostiikasta julkiseksi, ja vanha teksti ("the public season race reads
# the entry series") olisi jaanyt elavaan tiedostoon epatotena, koska
# setdefault ei koske olemassa olevaan kenttaan. `series_source` tulee
# lukijalta (`load_gw_scores`), ei tasta - sita ei voi unohtaa.
#
# 🔴 JULKINEN TEKSTI. Artefakti on julkisessa repossa. Historia:
#   12.9 chip-kieltolause poistettiin (epatosi: entry pelasi WC + 3xc).
#   18.9 "a chip round scores lower" -> mitattu suunta "never scores higher"
#        (3xc nollan tehneelle kapteenille lisaa 0 p). Portti:
#        tests/test_model_squad_scores_provenance.py
#          ::test_freeze_metan_chip_vaite_on_mitattu_suunta
#   21.9 sarja on julkinen; lause "only rows provably the entry's squad are
#        graded" on poistettu koska se ei enaa pida.
_META = {
        "product": ("GoalIQ Beat the Model: frozen-squad per-GW scores. This "
                    "is the model's public series (season race and track "
                    "record)."),
        "rules": ("The frozen squad is the model's own line, scored with "
                  "official FPL points once the gameweek finishes. Autosubs "
                  "and the captain/vice rule are applied as FPL applies them, "
                  "and the model's own transfer hits are in transfer_cost "
                  "(null when FPL's rules could not confirm the cost). No "
                  "chip is applied, because the frozen squad records none. "
                  "FPL entry 116920 is a separate series: it starts from this "
                  "squad, but its chips and some lineup calls were ours, so in "
                  "any round the two can score differently in either "
                  "direction. Rows graded by the current grader record "
                  "whether the entry differed (entry_diverged, entry_diff); "
                  "the GW3 row predates those fields. GW3 restarts from the "
                  "entry's squad after its GW2 wildcard. A gameweek whose "
                  "freeze rebuilt the squad from scratch (squad_rebuilt: "
                  "true) is not scored. Append-only."),
}
# Taaksepain yhteensopiva nimi (testit ja vanhat kutsujat lukevat tata).
_META_DEFAULTS = _META


def _entry_event(gw: int) -> tuple[dict | None, str]:
    """(entryn event-picks-vastaus, tila). Tila: ok / not_played / unreachable.

    Sama kolmen tilan jako kuin verify-vahdilla: 404 on tieto (tilia ei
    pelattu), 5xx/verkko on EI TIETOA eika saa nayttaa erolta.
    """
    from src.models.fpl_model_entry import ENTRY_ID
    try:
        r = requests.get(f"{FPL_BASE}/entry/{ENTRY_ID}/event/{gw}/picks/",
                         headers=FPL_HEADERS, timeout=30)
    except Exception as e:
        return None, f"unreachable ({e!r})"
    if getattr(r, "status_code", 200) == 404:
        return None, "not_played"
    try:
        r.raise_for_status()
        return r.json(), "ok"
    except Exception as e:
        return None, f"unreachable ({e!r})"


def _siirtokustannus(frozen: dict, ft_fpl) -> tuple[int | None, str]:
    """(kustannus, lahde) FPL:n saannoilla. `ft_fpl()` palauttaa FPL:n oman
    FT-saldon taman kierroksen deadlinella entryn historiasta (tai None).

    Saannot jarjestyksessa, jokainen mitattu tai FPL:n saanto:
      GW1              siirrot rajattomat               -> 0
      0 siirtoa                                          -> 0
      1 siirto         FPL antaa vahintaan 1 FT joka kierros GW2:sta -> 0
      GW2              saldo on 1 kaikilla (GW1 rajaton) -> (n - 1) x 4
      reseed (entry_picks)  malli perii entryn rungon JA saldon, joten
                       FPL:n oma saldo historiasta on mallin saldo
                                                         -> max(0, n - ft) x 4
      muu              saldoa ei voi todentaa (ketju jatkui mallin omilla
                       siirroilla, ja sen laskuri on mitattu vaaraksi)
                                                         -> None (brutto +
                                                            nakyva merkinta)
    Mitattu 21.9 GW2: 3 siirtoa, FT 1 (FPL:n historia) -> 8 = freezen oma
    kirjaus. GW5: 2 siirtoa, reseed, FPL:n saldo 3 -> 0 (freeze sanoi 4).
    """
    meta = frozen.get("meta") or {}
    gw = int(meta.get("gw") or 0)
    n = len(meta.get("transfers") or [])
    if gw <= 1:
        return 0, "gw1_unlimited"
    if n == 0:
        return 0, "no_transfers"
    if n == 1:
        return 0, "one_transfer_always_free"
    if gw == 2:
        return HIT_POINTS * max(0, n - 1), "fpl_rules_gw2"
    if meta.get("squad_source") == "entry_picks":
        ft = ft_fpl()
        if ft is not None:
            return HIT_POINTS * max(0, n - int(ft)), "fpl_rules_entry_ft"
    return None, "unverified"


def _entry_history():
    """(historia, tila). Tila ok / unreachable."""
    from src.models.fpl_model_entry import ENTRY_ID
    try:
        r = requests.get(f"{FPL_BASE}/entry/{ENTRY_ID}/history/",
                         headers=FPL_HEADERS, timeout=30)
        r.raise_for_status()
        return r.json(), "ok"
    except Exception as e:
        return None, f"unreachable ({e!r})"


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
    # Vain olemassa olevan tiedoston vanha teksti paivitetaan ilman gradausta;
    # uutta tiedostoa ei luoda pelkasta metasta.
    meta_muuttui = LOG_PATH.exists() and any(
        log["meta"].get(k) != v for k, v in _META.items())
    log["meta"].update(_META)
    done = {g.get("gw") for g in log["gameweeks"]}
    # 21.9 (Villen paatos GW4:sta): epakelpo freeze EI ole mallin rivi, mutta
    # sen luku kirjataan DIAGNOSTISESTI omaan listaansa, jotta pinta voi
    # sanoa "scored as frozen it would have had N" lukematta lukua mistaan
    # muualta. Ei `gameweeks`issa: se lista on mallisarja.
    done_unscored = {int(u.get("gw")) for u in (log.get("unscored") or [])
                     if u.get("gw") is not None}

    kaikki = []
    for f in sorted(FROZEN_DIR.glob("gw*.json")):
        frozen = json.loads(f.read_text(encoding="utf-8"))
        gw = frozen.get("meta", {}).get("gw")
        kaikki.append((int(gw), frozen))
    ensimmainen = min((g for g, _ in kaikki), default=None)
    pending = [(gw, fr) for gw, fr in sorted(kaikki, key=lambda t: t[0])
               if gw not in done and gw not in done_unscored]
    if not pending:
        print("Kaikki jäädytetyt mallirivit on jo gradattu.")
        if meta_muuttui:
            validate_gw_scores(log, source=SOURCE_FROZEN)
            LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=1)
                                + "\n", encoding="utf-8")
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
    diagnosoitu = 0
    epakelvot = []

    def _live(gw_):
        r_ = requests.get(f"{FPL_BASE}/event/{gw_}/live/",
                          headers=FPL_HEADERS, timeout=60)
        r_.raise_for_status()
        pts, mins = {}, {}
        for el in r_.json().get("elements") or []:
            st = el.get("stats") or {}
            pts[int(el["id"])] = int(st.get("total_points") or 0)
            mins[int(el["id"])] = int(st.get("minutes") or 0)
        return pts, mins
    for gw, frozen in pending:
        ev = events.get(int(gw))
        if not ev or not (ev.get("finished") and ev.get("data_checked")):
            print(f"GW{gw}: ei vielä ratkennut (finished+data_checked) — odotetaan.")
            continue
        # 🔴 EPAKELPO FREEZE EI OLE MALLIN RIVI (12.9 mittaus, 21.9 rakenne).
        # Ratkeamisehto ensin, jotta kierroksista joita ei viela pelata ei
        # huudeta.
        syy = freeze_invalid(frozen, earlier_exists=(ensimmainen is not None
                                                     and gw > ensimmainen))
        if syy:
            epakelvot.append(int(gw))
            try:
                d_pts, d_mins = _live(gw)
            except Exception as e:
                print(f"VIRHE: event/{gw}/live-haku epäonnistui: {e!r}")
                return 1
            diag = score_gw(frozen, d_pts, d_mins)
            log.setdefault("unscored", []).append({
                "gw": int(gw),
                "code": UNSCORED_NO_VALID_FREEZE,
                # Jaadytetty runko FPL:n pisteilla, samat saannot kuin
                # mallisarjassa (autosubit, kapteeni). Brutto: epakelvon
                # freezen siirtolista ei kuvaa mitaan (gw4: transfers []
                # vaikka 8/15 vaihtui), joten hittia ei voi laskea.
                "would_have_scored": diag["points"],
                "fpl_average": ev.get("average_entry_score"),
                "graded_at": _dt.datetime.now(_dt.timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"),
            })
            diagnosoitu += 1
            print(f"::warning::GW{gw} EI GRADATA mallisarjaan: {syy}. "
                  f"Kirjattu unscored-listaan (no_valid_frozen_squad), "
                  f"diagnostinen luku {diag['points']} p, FPL-keskiarvo "
                  f"{ev.get('average_entry_score')}. Ei entryn lukua "
                  f"korvikkeeksi (Villen paatos 21.9).")
            continue
        event, tila = _entry_event(int(gw))
        if tila.startswith("unreachable"):
            print(f"::warning::GW{gw}: entryn rivia ei saatu luettua ({tila}). "
                  f"Kierros jaa seuraavaan ajoon: eroa ja kustannusta ei "
                  f"kirjata append-only-lokiin mittaamatta.")
            continue
        try:
            points, minutes = _live(gw)
        except Exception as e:
            print(f"VIRHE: event/{gw}/live-haku epäonnistui: {e!r}")
            return 1

        from src.models.fpl_entry_history import free_transfers_for_gw
        from src.models.fpl_model_entry import (ProvenienssiPuuttuu,
                                                entry_diff,
                                                require_entry_provenance)
        diff = entry_diff(frozen, event.get("picks") or []) if event else None
        historia_tila = {}

        def _ft():
            if "h" not in historia_tila:
                historia_tila["h"] = _entry_history()
            h, tila = historia_tila["h"]
            return free_transfers_for_gw(h, int(gw)) if h else None

        kustannus, lahde = _siirtokustannus(frozen, _ft)
        if (lahde == "unverified" and "h" in historia_tila
                and historia_tila["h"][0] is None):
            print(f"::warning::GW{gw}: entryn historiaa ei saatu luettua "
                  f"({historia_tila['h'][1]}), joten siirtokustannusta ei voi "
                  f"todentaa. Kierros jaa seuraavaan ajoon (append-only).")
            continue
        try:
            peruste = require_entry_provenance(frozen, FROZEN_DIR)
        except ProvenienssiPuuttuu:
            # Ennen 21.9 tama ohitti rivin. Nyt se on vain tieto: runko ei
            # ole todistetusti entryn runko, mutta se on mallin oma rivi.
            peruste = "frozen_only"

        row = score_gw(frozen, points, minutes)
        row["graded_at"] = _dt.datetime.now(_dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        row["frozen_at"] = frozen.get("meta", {}).get("frozen_at")
        # 🔴 PROVENIENSSI RIVIIN ASTI (12.9.2026). Lukija vaatii etta
        # jokainen rivi sanoo provenienssinsa.
        row["source"] = SOURCE_FROZEN
        row["provenance"] = peruste
        row["transfer_cost"] = kustannus
        row["transfer_cost_source"] = lahde
        if diff is None:
            # 404: entrya ei pelattu talla kierroksella. Se on ero.
            row["entry_diverged"] = True
            row["entry_diff"] = {"entry_not_played": True}
        else:
            row["entry_diverged"] = bool(diff["diverged"])
            row["entry_diff"] = {k: diff[k] for k in (
                "common", "missing", "extra", "xi_only_frozen",
                "xi_only_entry", "bench_order_match", "captain_match",
                "vice_match")}
        # Keskiarvo vertailukohdaksi: "voititko mallin" on eri kysymys kuin
        # "voititko keskiverto-FPL-managerin", ja molemmat kiinnostavat.
        row["fpl_average"] = ev.get("average_entry_score")
        log["gameweeks"].append(row)
        graded += 1
        subs = ", ".join(f"{s['out']}->{s['in']}" for s in row["autosubs"]) or "-"
        print(f"OK: GW{gw} mallin rivi gradattu — {row['points']} p "
              f"(ilman kapteenia {row['points_before_captain']}, "
              f"kapteeni {row['captain_reason']} +{row['captain_points_added']}), "
              f"siirtokustannus {kustannus if kustannus is not None else 'TODENTAMATON'} "
              f"({lahde}), autosubit: {subs}, "
              f"penkille jäi {row['bench_points']} p, FPL-keskiarvo "
              f"{row['fpl_average']}, entry poikkesi: {row['entry_diverged']}.")
        if row["entry_diverged"]:
            print(f"::warning::GW{gw}: entry poikkesi jaadytetysta rivista "
                  f"({row['entry_diff']}). Julkinen sarja mittaa jaadytettya "
                  f"rivia (Villen paatos 21.9); ero on kirjattu riville.")

    if epakelvot:
        print(f"Epakelvon freezen takia gradaamatta: GW{epakelvot}.")
    if graded or diagnosoitu or meta_muuttui:
        # Portti ennen kirjoitusta: tulos on yhden provenienssin freeze-sarja.
        validate_gw_scores(log, source=SOURCE_FROZEN)
        LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
