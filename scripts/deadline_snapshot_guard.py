"""DEADLINE-SNAPSHOT-guard (29.8.2026): ajetaanko refresh T-2 h -ikkunassa.

MIKSI: siirtofreeze (T-24 h, `freeze_model_squad_gw.py`, 30 h ikkuna) on
tarkoituksella aikaisin, jotta Ville ehtii syottaa rivin entryyn. Mutta
kutsujen loki (`log_gw_calls.py`) kirjattiin GW2:ssa SAMASTA ajosta 24 h
ennen deadlinea, eli ennen perjantain pressitilaisuuksia. Kutsu joka kirjataan
ennen pressien team newsia haviaa minuuttivirheisiin, ei mallivirheisiin.
Tama guard antaa `fpl-data-refresh.yml`:n tuntiajolle luvan vain kun
deadline on SNAPSHOT_WINDOW_MIN:n sisalla, jolloin log_gw_calls kirjoittaa
rivin uudelleen tuoreella projektiolla (xMins/start% paivittyneet).

IKKUNA VS CADENSSI (muisti "cron-ikkuna kapeampi kuin cadenssi"): tuntiajo
`40 7-18 * * *` on best-effort ja mitattu drift on ollut ~50 min (3 h -cron
ajoi 04:49, 23:46, 20:49). Ikkuna on 150 min levea ja cadenssi 60 min, joten
yksikin ajo osuu ikkunaan vaikka drift soisi kokonaisen tunnin. Alaraja 30 min
riittaa 10 min ajolle (mitattu 7-10 min); jos ajo silti valuu deadlinen yli,
log_gw_calls on fail-closed eika kirjoita.

Vain stdlib: askel ajetaan ENNEN pip installia, runnerin python3:lla, eika
se saa lukea data/raw:ta (tests/test_no_raw_disk_reads.py).

    python3 scripts/deadline_snapshot_guard.py   # tulostaa proceed=true|false
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
import urllib.request

FPL_BOOTSTRAP = "https://fantasy.premierleague.com/api/bootstrap-static/"
# (alaraja, ylaraja) minuutteina ENNEN deadlinea.
SNAPSHOT_WINDOW_MIN = (30, 180)
# Tuntiajon cadenssi minuutteina; testi vahtii etta ikkuna > cadenssi + drift.
CRON_CADENCE_MIN = 60
CRON_DRIFT_ALLOWANCE_MIN = 60


def _parse(s: str) -> _dt.datetime:
    t = _dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=_dt.timezone.utc)
    return t.astimezone(_dt.timezone.utc)


def snapshot_gw(events: list[dict], now: _dt.datetime) -> dict | None:
    """Ensimmainen GW jonka deadline on ikkunassa, tai None.

    Palauttaa {"gw", "deadline", "minutes_ahead"}. Deadline joka on jo ohi
    tai yli ylarajan ei kelpaa; tasan alaraja kelpaa, tasan ylaraja kelpaa."""
    lo, hi = SNAPSHOT_WINDOW_MIN
    best = None
    for ev in events or []:
        raw = ev.get("deadline_time")
        if not raw:
            continue
        dl = _parse(raw)
        ahead = (dl - now).total_seconds() / 60.0
        if lo <= ahead <= hi and (best is None or ahead < best["minutes_ahead"]):
            best = {"gw": int(ev.get("id") or 0), "deadline": dl,
                    "minutes_ahead": round(ahead, 1)}
    return best


def main() -> int:
    now = _dt.datetime.now(_dt.timezone.utc)
    try:
        with urllib.request.urlopen(FPL_BOOTSTRAP, timeout=30) as r:
            boot = json.load(r)
    except Exception as e:  # noqa: BLE001
        # FAIL-CLOSED, toisin kuin 09:15-guard (joka laukeaa kerran paivassa,
        # jolloin fail-open on sen ainoa uusintayritys). Tama cron laukeaa 12
        # kertaa paivassa: ohitettu ajo yritetaan uudelleen tunnin paasta ja
        # 150 min ikkunaan mahtuu kaksi ohitusta. Fail-open sen sijaan ajaisi
        # taydet builderit 12 kertaa vuorokaudessa aina kun FPL-API on nurin,
        # ja ne kaatuisivat -> pysyvasti punainen putki (muisti: "pysyvasti
        # punainen putki nielee regression"). Snapshotin menetys ei riko
        # mitaan: 3 h -ajon kirjaama rivi jaa voimaan.
        print(f"guard: bootstrap-haku epaonnistui ({e!r}), ohitetaan "
              "(uusinta tunnin paasta)", file=sys.stderr)
        print("proceed=false")
        return 0
    hit = snapshot_gw(boot.get("events") or [], now)
    if hit is None:
        print(f"guard: ei deadlinea {SNAPSHOT_WINDOW_MIN[0]}-"
              f"{SNAPSHOT_WINDOW_MIN[1]} min paassa ({now:%H:%M}Z), ohitetaan",
              file=sys.stderr)
        print("proceed=false")
        return 0
    print(f"guard: GW{hit['gw']} deadline {hit['deadline']:%Y-%m-%d %H:%M}Z on "
          f"{hit['minutes_ahead']:.0f} min paassa -> snapshot-ajo",
          file=sys.stderr)
    print("proceed=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
