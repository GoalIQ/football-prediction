"""#43 FPL hinnanmuutosennuste — tuotanto-builderi: net-transfer-velocity → JSON.

Tuottaa `data/fpl_price_watch.json`:n jonka `/api/fantasy/price-watch` tarjoilee
(ei on-request-laskentaa — Render 0.5 vCPU -budjettisääntö, sama pattern kuin
build_fpl_phase0/build_fpl_xp). Ajo: päivittäinen fpl-data-refresh.yml-cron
(#16) tai käsin `python -m scripts.build_fpl_price_watch`.

LÄHDE (22.8.2026 MUUTTUI): FPL alkoi 26/27-kaudella julkaista hinnanmuutokset
itse (`price_change_percent`, `price_change_projections`, `hourly_rate`
bootstrapissa). Ensisijainen polku lukee ne suoraan — se on tarkka eikä arvio,
ja se antaa myös PÄIVÄN jolloin muutos osuu (`eta_days`), mitä heuristiikka ei
voinut tietää. Alla oleva velocity-kaava jää FALLBACKIKSI siltä varalta että
kentät katoavat; `has_official_fields` valitsee polun rakenteellisesti, ei
kausiehdolla. Sama muutos lopetti LiveFPL:n oman hinnanennusteen.

FALLBACK-SIGNAALIKAAVA (approksimaatio, käytössä vain ilman virallisia kenttiä):
  net_event   = transfers_in_event - transfers_out_event (bootstrap, per pelaaja)
  owners      = selected_by_percent / 100 * total_players
  threshold   = max(MIN_THRESHOLD, THRESHOLD_OWNER_RATE * owners)
                (yhteisöheuristiikka: kynnys skaalautuu omistajamäärään;
                 laskuille korkeampi kerroin — pudotukset ovat FPL:ssä jäykempiä)
  progress    = |net_event| / threshold  → progress_pct = min(100, 100*progress)
  status      = rising_soon  (net>0, progress >= 0.9)
                rising_watch (net>0, progress >= 0.5)
                falling_soon / falling_watch (net<0, samat rajat)
                stable       (muuten)
  confidence  = min(1.0, progress) pyöristettynä — monotoninen net_eventissä
                samassa omistushaarukassa (ship-gate vahtii).
  cost_change_event != 0 → already_changed_today=true; jos toteutunut muutos on
  ristiriidassa lasketun suunnan kanssa (nousi mutta luokka falling_* tms.),
  luokka clampataan stableksi (suunta-konsistenssi, ship-gate).

REHELLISYYS: `meta.source` + `meta.official_projection` kertovat KUMPI polku
tuotti rivit, ja disclaimer vaihtuu sen mukana. Vanha varaus ("FPL's exact
price thresholds are not public") ei ole enää tosi eikä sitä saa näyttää
virallisen datan vieressä. EI "guaranteed"-copyä. IP-puhdas (vain tekstidata).

FAIL-SAFE: FPL-API alhaalla / vastaus rikki / sanity-gate kiinni → JSONia EI
kirjoiteta (vanha jää voimaan), exit != 0 → cron-step punainen, ei committia.
Exit 0 = ok, 1 = tekninen virhe, 2 = sanity-gate.
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

import config
from src.models.fpl_price_watch import (DISCLAIMER_ESTIMATE,
                                        DISCLAIMER_OFFICIAL)

FPL_BASE = "https://fantasy.premierleague.com/api"
FPL_HEADERS = {"User-Agent": "Mozilla/5.0 (GoalIQ refresh job)"}
OUT_PATH = config.PROJECT_ROOT / "data" / "fpl_price_watch.json"

# Kynnysapproksimaation parametrit (dokumentoitu yllä; EI virallinen algoritmi)
THRESHOLD_OWNER_RATE_RISE = 0.05   # ~5 % omistajista nettona sisään ≈ nousu
THRESHOLD_OWNER_RATE_FALL = 0.075  # laskut jäykempiä → korkeampi kynnys
MIN_THRESHOLD = 20_000             # pieniomisteisten lattia (kohinasuoja)
SOON_PROGRESS = 0.9
WATCH_PROGRESS = 0.5
TOP_N = 20


def fetch_bootstrap() -> dict:
    r = requests.get(f"{FPL_BASE}/bootstrap-static/", headers=FPL_HEADERS,
                     timeout=30)
    r.raise_for_status()
    return r.json()


def _f(v, default: float = 0.0) -> float:
    """FPL palauttaa projected_percentin merkkijonona ("5.7")."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def has_official_fields(bootstrap: dict) -> bool:
    """Onko FPL:n virallinen hinnanmuutosdata saatavilla?

    26/27-kaudella FPL alkoi julkaista hinnanmuutokset läpinäkyvästi
    (`price_change_percent`, `price_change_projections`, `hourly_rate`).
    Todennettu tuotannon bootstrapista 22.8.2026: 600/600 pelaajaa kantaa
    kentät, `price_change_calibrating` false kaikilla.

    Tarkistus on RAKENTEELLINEN eikä kausikohtainen: jos FPL poistaa kentät,
    palataan vanhaan velocity-heuristiikkaan automaattisesti eikä sivu jää
    tyhjäksi.
    """
    for e in (bootstrap.get("elements") or [])[:20]:
        if e.get("price_change_percent") is not None:
            return True
    return False


def classify_official(pct_now: float, projections: list[dict],
                      cost_change_event: int) -> tuple[str, float, float, int | None]:
    """FPL:n omasta datasta → (status, confidence, progress_pct, eta_days).

    `price_change_percent` on matka kynnykselle: +100 = nousu, -100 = lasku.
    `price_change_projections` on lista {offset (vrk), projected_percent,
    likelihood} seuraavalle kolmelle päivälle.

    eta_days = ensimmäinen offset jolla |projected_percent| >= 100, eli päivä
    jolloin FPL:n oma projektio ylittää kynnyksen. None = ei kolmen päivän
    sisällä. TÄMÄ ON SE LUKU JOTA ARVIO EI VOINUT ANTAA.
    """
    direction = "rising" if pct_now > 0 else "falling" if pct_now < 0 else ""
    if not direction:
        return "stable", 0.0, 0.0, None
    eta = None
    for p in projections:
        if abs(_f(p.get("projected_percent"))) >= 100.0:
            off = p.get("offset")
            eta = int(off) if isinstance(off, (int, float)) else None
            break
    progress = min(1.0, abs(pct_now) / 100.0)
    if eta == 0 or progress >= SOON_PROGRESS:
        status = f"{direction}_soon"
    elif eta is not None or progress >= WATCH_PROGRESS:
        status = f"{direction}_watch"
    else:
        status = "stable"
    # Suunta-konsistenssi toteutuneeseen muutokseen — sama vartija kuin
    # heuristiikkapolulla: nousi tänään → ei falling_*, ja päinvastoin.
    if cost_change_event > 0 and status.startswith("falling"):
        status = "stable"
    if cost_change_event < 0 and status.startswith("rising"):
        status = "stable"
    return status, round(progress, 2), round(100.0 * progress, 1), eta


def classify(net_event: int, owners: float,
             cost_change_event: int) -> tuple[str, float, float]:
    """→ (status, confidence, progress_pct). Puhdas funktio → testattava."""
    if net_event > 0:
        threshold = max(MIN_THRESHOLD, THRESHOLD_OWNER_RATE_RISE * owners)
        direction = "rising"
    elif net_event < 0:
        threshold = max(MIN_THRESHOLD, THRESHOLD_OWNER_RATE_FALL * owners)
        direction = "falling"
    else:
        return "stable", 0.0, 0.0
    progress = min(1.0, abs(net_event) / threshold)
    if progress >= SOON_PROGRESS:
        status = f"{direction}_soon"
    elif progress >= WATCH_PROGRESS:
        status = f"{direction}_watch"
    else:
        status = "stable"
    # Suunta-konsistenssi toteutuneeseen muutokseen: nousi tänään → ei falling_*,
    # laski tänään → ei rising_* (clamp stableksi).
    if cost_change_event > 0 and status.startswith("falling"):
        status = "stable"
    if cost_change_event < 0 and status.startswith("rising"):
        status = "stable"
    return status, round(progress, 2), round(100.0 * progress, 1)


def _empty_note(bootstrap: dict, n_active: int) -> tuple[str, str]:
    """Tyhjien listojen selite. 22.8: "Pre-season" vain kun kausi EI ole
    alkanut — vanha versio väitti esikautta myös GW1:n jälkeen (kuvakaappaus
    Villeltä 22.8), koska ehto oli pelkkä n_active == 0. Kauden aikana tyhjä
    lista tarkoittaa joko siirtolaskurien nollausikkunaa deadlinen jälkeen
    tai sitä ettei kukaan ole kynnyksen tuntumassa."""
    season_started = any(ev.get("finished") or ev.get("is_current")
                         for ev in bootstrap.get("events") or [])
    if not season_started:
        return ("Pre-season: no transfer activity yet - price watch "
                "goes live when the FPL game opens.",
                "price_watch.note.preseason")
    if n_active == 0:
        return ("No transfer activity in the FPL feed right now - "
                "candidates appear as transfers come in.",
                "price_watch.note.no_activity")
    return ("No players are close to a price change right now - "
            "candidates appear as net transfers build up.",
            "price_watch.note.none_near_threshold")


def build_payload(bootstrap: dict) -> dict:
    total_players = int(bootstrap.get("total_players") or 0)
    official = has_official_fields(bootstrap)
    rows = []
    for e in bootstrap.get("elements") or []:
        net_event = int(e.get("transfers_in_event") or 0) - \
            int(e.get("transfers_out_event") or 0)
        try:
            owned_pct = float(e.get("selected_by_percent") or 0.0)
        except (TypeError, ValueError):
            owned_pct = 0.0
        owners = owned_pct / 100.0 * total_players
        cce = int(e.get("cost_change_event") or 0)
        eta = None
        if official:
            status, confidence, progress_pct, eta = classify_official(
                _f(e.get("price_change_percent")),
                e.get("price_change_projections") or [], cce)
        else:
            status, confidence, progress_pct = classify(net_event, owners, cce)
        rows.append({
            "id": e["id"],
            "web_name": e.get("web_name") or "",
            "team": e.get("team"),
            "now_cost": (e.get("now_cost") or 0) / 10.0,
            "status": status,
            "confidence": confidence,
            "progress_pct": progress_pct,
            "net_event": net_event,
            "already_changed_today": cce != 0,
            # Vain viralliselta polulta: päivien määrä kynnykseen (0 = tänä
            # yönä). Heuristiikka ei voinut tätä tietää, joten kenttä puuttuu
            # kokonaan fallback-tilassa — tyhjä ei ole sama kuin "ei tänään".
            **({"eta_days": eta} if official and eta is not None else {}),
        })
    # Virallisella polulla kiireellisin ensin: pienin eta_days voittaa, ja
    # vasta sen sisalla suurin edistyminen. Pelkka progress-jarjestys nostaisi
    # karkeen pelaajan joka on 90 %:ssa mutta hidastunut, ja tyontaisi alas
    # sen joka muuttuu TANA yona — se on juuri se rivi jota sivulta haetaan.
    def _rank(r: dict) -> tuple[int, float]:
        eta = r.get("eta_days")
        return (eta if isinstance(eta, int) else 99, -r["progress_pct"])

    risers = sorted((r for r in rows if r["status"].startswith("rising")),
                    key=_rank)[:TOP_N]
    fallers = sorted((r for r in rows if r["status"].startswith("falling")),
                     key=_rank)[:TOP_N]
    n_active = sum(1 for r in rows if r["net_event"] != 0)
    return {
        "meta": {
            "product": "GoalIQ Fantasy - price watch",
            "available": True,
            "generated_at": _dt.datetime.now(_dt.timezone.utc)
                            .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_players": total_players,
            "n_players_scanned": len(rows),
            "n_with_transfer_activity": n_active,
            # Lahde nakyviin: lukija saa tietaa kumpaa han katsoo.
            "source": ("FPL official price projection" if official
                       else "GoalIQ net-transfer velocity estimate"),
            "official_projection": official,
            "disclaimer": (DISCLAIMER_OFFICIAL if official
                           else DISCLAIMER_ESTIMATE),
            # BACKEND-EN-VUOTAA-ES-PT (23.8): vakaa tunniste proosan rinnalle.
            # Klientti voi kaantaa oman i18n-tiedostonsa avulla; proosa jaa
            # paikalleen varakielena eika mikaan hajoa.
            "disclaimer_code": ("price_watch.disclaimer.official" if official
                                else "price_watch.disclaimer.estimate"),
            # Note aina kun molemmat listat ovat tyhjiä — ilman sitä sivujen
            # fallback-copy ("goes live when the FPL game opens") valehtelisi
            # kauden aikana kun aktiviteettia on mutta kynnys ei ylity.
            **(dict(zip(("note", "note_code"),
                        _empty_note(bootstrap, n_active)))
               if not risers and not fallers else {}),
        },
        "risers": risers,
        "fallers": fallers,
        # 30.7 tarkkuusloki: koko hintataulun snapshot (id → kymmenykset).
        # Seuraavan yön grade_price_watch diffaa tätä vasten → toteutuneet
        # muutokset ilman arkistokaivuuta. ~700 int-paria, kompakti.
        "prices": {str(e["id"]): int(e.get("now_cost") or 0)
                   for e in bootstrap.get("elements") or []},
    }


def sanity_gate(payload: dict) -> list[str]:
    """Ship-gate: suunta-konsistenssi + top-listojen eheys. → rikkeet.

    22.8: `net_event`-ehto koskee VAIN heuristiikkapolkua. FPL:n oma
    projektio perustuu tuntinopeuteen eikä kierroksen nettosiirtoihin, joten
    virallisella datalla nousija voi täysin laillisesti kantaa negatiivisen
    `net_event`-luvun (esim. deadlinen jälkeen laskurit nollautuvat mutta
    hintamomentti jatkuu). Ilman tätä erottelua portti olisi kaatanut ajon
    ja JÄÄDYTTÄNYT koko price watchin — sama fail-safen kääntöpuoli joka
    padotti data-refreshin 21.-22.8.
    """
    errors = []
    official = bool(payload.get("meta", {}).get("official_projection"))
    for r in payload["risers"]:
        if not r["status"].startswith("rising"):
            errors.append(f"riser-rikke: {r['web_name']} {r['status']}")
        elif not official and r["net_event"] <= 0:
            errors.append(f"riser-rikke: {r['web_name']} net={r['net_event']}")
    for r in payload["fallers"]:
        if not r["status"].startswith("falling"):
            errors.append(f"faller-rikke: {r['web_name']} {r['status']}")
        elif not official and r["net_event"] >= 0:
            errors.append(f"faller-rikke: {r['web_name']} net={r['net_event']}")
    for r in payload["risers"] + payload["fallers"]:
        if not 0.0 <= r["confidence"] <= 1.0 or not 0.0 <= r["progress_pct"] <= 100.0:
            errors.append(f"range-rikke: {r['web_name']}")
    return errors


def main() -> int:
    try:
        bootstrap = fetch_bootstrap()
    except Exception as e:
        print(f"VIRHE: FPL-API-haku epäonnistui: {e!r} — vanha JSON jää voimaan.")
        return 1
    if not bootstrap.get("elements"):
        print("VIRHE: bootstrap ilman elements-listaa — ei kirjoiteta.")
        return 1

    payload = build_payload(bootstrap)
    errors = sanity_gate(payload)
    if errors:
        print("SANITY-GATE KIINNI — JSONia ei kirjoiteta:")
        for err in errors:
            print(f"  {err}")
        return 2

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    print(f"OK: {OUT_PATH.name} kirjoitettu — risers {len(payload['risers'])}, "
          f"fallers {len(payload['fallers'])}, "
          f"aktiivisia {payload['meta']['n_with_transfer_activity']}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
