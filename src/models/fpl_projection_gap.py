"""FPL:n oma projektio (`ep_next`) mallin xP:n rinnalla: lukija ja kynnys (10.9.2026).

MIKSI. Rowanin pyynto 19.8: "nayta ne tapaukset joissa malli on selvasti eri
mielta kuin muut". Villen paatos 10.9: vertailukohta on FPL:n oma `ep_next`,
nimettyna pinnalla tasmalleen "FPL's own projection" (ei "consensus", ei
"others say"). Se on lukijan tarkistettavissa FPL:n omasta sovelluksesta.

YKSI LUKIJA (CLAUDE.md 6a, mekanismi 1). Kynnysta EI kovakoodata mihinkaan
pintaan: builderi johtaa sen gradatusta tarkkuuslokista
(`data/fpl_xp_gw_accuracy.json`) ja kirjoittaa sen payloadin
`meta.projection_gap`-lohkoon. SPA lukee lohkon ja piilottaa rivin jos lohko
puuttuu (fail-closed). Sama funktio `gap_state` on Pythonin
referenssitoteutus; SPA:n `projectionGap` on sen pariteettikopio ja
`tests/test_fpl_projection_gap.py` mittaa etta TS ei kanna omaa lukua.

KYNNYS JOHDETAAN, EI VALITA. Kahden ennusteen ero on "merkittava" vasta kun
se ylittaa sen mita kumpikin ennuste itse tyypillisesti ERHEHTYY toteumaa
vastaan. Sama periaate kuin CALL-MARGIN (10.9): ero marginaalin alla ei ole
vaite. Mitta on viimeisin gradattu vertailu jossa GoalIQ ja FPL ep_next on
pisteytetty samalla rivijoukolla:

    min_abs_xp = ceil(max(MAE_goaliq, MAE_fpl_ep_next) / 0.5) * 0.5

GW3 (jaadytetty 4.9, gradattu 7.9, n=501): MAE goaliq 1.536, fpl_ep_next
1.688 -> min_abs_xp = 2.0. Pyoristys 0.5:een jotta kynnys ei liiku joka
gradauksesta kolmannessa desimaalissa (lukijan on voitava sanoa "kynnys on
kaksi pistetta").

SUHTEELLINEN EHTO. Absoluuttinen ero 2.0 on suuri 3 xP:n pelaajalle ja pieni
9 xP:n kapteeniehdokkaalle, joten lisaksi vaaditaan ero >= MIN_REL_GAP
suuremmasta luvusta. Mitattu jaadytetysta GW3:sta (n=501, ainoa freeze jossa
ep_next on mukana; GW1-2 jaadytettiin ennen 29.8 kun ep_next lisattiin):

    ehto                       kaikista   xP >= 2 -riveista (n=210)
    |d| >= 1.0 TAI rel >= 30 %   74.5 %        -        (ei "merkittava")
    |d| >= 1.0 JA  rel >= 30 %   33.3 %      57.1 %
    |d| >= 1.5 JA  rel >= 30 %   21.6 %      43.8 %
    |d| >= 2.0 JA  rel >= 30 %   14.2 %      31.0 %     <- valittu
    |d| >= 2.0 JA  rel >= 40 %   13.6 %      29.5 %
    |d| >= 2.0 JA  rel >= 50 %    9.8 %      20.5 %

Suunta oli tasan: 53 rivilla malli korkeampi, 55 rivilla FPL korkeampi
(|d| >= 1.5 & 30 %), joten kynnys ei valitse kumpaakaan puolta.
Jakauman mediaani |d| oli 0.77, p90 2.35: kynnys 2.0 osuu noin joka
seitsemanteen projektioriviin ja joka kolmanteen pelaavaan riviin.

VANHENEMINEN. Mittaus kuvaa mallia vain lahella mittaushetkea: kesalla
edellisen kauden MAE ei sano mitaan uuden kauden mallista. Jos viimeisin
vertailu on yli COMPARISON_MAX_AGE_DAYS vanha, kynnysta ei ole ja rivi
jaa pois (fail-closed), kunnes uusi kierros on gradattu.

MITA EI SANOTA. Rivi nayttaa kaksi lukua eika selita eroa: selitys olisi
vaite ilman reittia (portin saanto). Lukija nakee numerot ja voi tarkistaa
FPL:n luvun FPL:sta ja meidan luvun tasta samasta kortista.
"""
from __future__ import annotations

import datetime as _dt
import math

# Suhteellinen kynnys suuremmasta luvusta laskettuna. Perustelu docstringin
# taulukossa (GW3, n=501). Muutos ilman uutta mittausta kaatuu testissa
# tests/test_fpl_projection_gap.py::test_parameters_are_pinned_with_reason.
MIN_REL_GAP = 0.30

# Absoluuttisen kynnyksen pyoristysaskel (ks. docstring "KYNNYS JOHDETAAN").
GAP_ROUND_TO = 0.5

# Viimeisin gradattu vertailu saa olla korkeintaan nain vanha (60 vrk ~ 6
# kierrosta). Kesatauolla kynnysta ei siis ole ja rivi jaa pois.
COMPARISON_MAX_AGE_DAYS = 60

# Payloadin kentat. Nimessa on lahde ("fpl_"), jotta luku ei sekoitu mallin
# omaan xP:hen missaan lukijassa.
PLAYER_FIELD = "fpl_ep_next"
META_GW_FIELD = "fpl_ep_next_gw"
META_FIELD = "projection_gap"

# Pinnan lause. SPA:n PlayerCard ja mobiilin en.ts kantavat saman lauseen;
# tests/test_i18n_svelte_parity.py mittaa arvon. Tama vakio on
# dokumentaatio, ei renderoija.
SURFACE_LABEL = "FPL's own projection"
# Koko lause paikkamerkkeineen. SPA:n PlayerCard renderoi taman; mobiilin
# en.ts-avain fantasy.playercard.fpl_projection kantaa saman arvon kun se
# lisataan (mobiilikoodi ei ole tassa haarassa). tests/test_fpl_projection_gap
# mittaa Svelten ja taman vakion pariteetin arvona, ei substringina.
SURFACE_SENTENCE = "GW{gw}. FPL's own projection: {fpl}. Ours: {ours}."


def parse_fpl_num(v) -> float | None:
    """FPL antaa ep_next/form merkkijonoina ("4.5"). Puuttuva -> None, ei 0:
    0 olisi "FPL ennusti nollaa" ja se on eri asia kuin "ei lukua"."""
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def ep_next_by_id(boot: dict | None) -> dict[int, float | None]:
    """{element_id: ep_next} bootstrapista. Ainoa parseri; freeze_fpl_xp_gw
    kayttaa samaa, jotta jaadytetty ja serveroitu luku eivat voi erota."""
    out: dict[int, float | None] = {}
    for el in (boot or {}).get("elements") or []:
        try:
            out[int(el["id"])] = parse_fpl_num(el.get("ep_next"))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def fpl_next_event_id(boot: dict | None) -> int | None:
    """FPL:n oma "seuraava kierros" (events[].is_next). ep_next viittaa
    TAHAN kierrokseen, ei meidan headline-kierrokseemme: jos ne eroavat
    (esim. deadlinen ja kickoffin valissa), vertailua ei tehda."""
    for ev in (boot or {}).get("events") or []:
        if ev.get("is_next"):
            try:
                return int(ev["id"])
            except (KeyError, TypeError, ValueError):
                return None
    return None


def _parse_utc(s) -> _dt.datetime | None:
    if not isinstance(s, str) or not s:
        return None
    try:
        d = _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=_dt.timezone.utc)
    return d


def derive_threshold(acc_doc: dict | None,
                     now: _dt.datetime | None = None) -> dict | None:
    """Kynnys viimeisimmasta gradatusta vertailusta, tai None.

    None tarkoittaa "ei kynnysta, ei rivia": ei vertailua vielä (kausi
    alussa), vertailusta puuttuu toinen MAE, tai vertailu on vanhentunut.
    Koskaan ei palauteta oletusarvoa: oletus olisi luku jota kukaan ei ole
    mitannut."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_dt.timezone.utc)
    gws = (acc_doc or {}).get("gameweeks") or []
    best = None
    for g in gws:
        cmp_ = g.get("comparison") if isinstance(g, dict) else None
        if not isinstance(cmp_, dict):
            continue
        mae = cmp_.get("mae") or {}
        ours, theirs = mae.get("goaliq"), mae.get("fpl_ep_next")
        if not isinstance(ours, (int, float)) or not isinstance(theirs, (int, float)):
            continue
        if not (math.isfinite(ours) and math.isfinite(theirs)) or ours <= 0 or theirs <= 0:
            continue
        frozen = _parse_utc(g.get("frozen_at")) or _parse_utc(g.get("graded_at"))
        if frozen is None:
            continue
        if best is None or frozen > best[0]:
            best = (frozen, g, float(ours), float(theirs))
    if best is None:
        return None
    frozen, g, ours, theirs = best
    if (now - frozen).days > COMPARISON_MAX_AGE_DAYS:
        return None
    worst = max(ours, theirs)
    min_abs = math.ceil(worst / GAP_ROUND_TO - 1e-9) * GAP_ROUND_TO
    return {
        "min_abs_xp": round(min_abs, 2),
        "min_rel": MIN_REL_GAP,
        "basis_gw": g.get("gw"),
        "basis_n": cmp_n(g),
        "basis_mae": {"goaliq": ours, "fpl_ep_next": theirs},
        "basis_frozen_at": g.get("frozen_at"),
        "rule": ("shown when |ours - fpl| >= min_abs_xp and "
                 "|ours - fpl| / max(ours, fpl) >= min_rel"),
    }


def cmp_n(g: dict) -> int | None:
    c = g.get("comparison") or {}
    n = c.get("n")
    return int(n) if isinstance(n, (int, float)) else None


def gap_state(ours, fpl, threshold: dict | None) -> dict | None:
    """Referenssitoteutus (SPA:n projectionGap on pariteettikopio).

    Palauttaa {"ours", "fpl", "abs", "rel"} kun ero on merkittava, muuten
    None. Puuttuva luku, puuttuva kynnys tai molemmat nollassa -> None."""
    if not threshold:
        return None
    if not isinstance(ours, (int, float)) or not isinstance(fpl, (int, float)):
        return None
    if not (math.isfinite(ours) and math.isfinite(fpl)):
        return None
    hi = max(ours, fpl)
    if hi <= 0:
        return None
    gap = abs(ours - fpl)
    rel = gap / hi
    if gap < float(threshold["min_abs_xp"]) or rel < float(threshold["min_rel"]):
        return None
    return {"ours": float(ours), "fpl": float(fpl),
            "abs": round(gap, 2), "rel": round(rel, 3)}
