"""Beat the Model V2 vaihe a: mallin joukkueen deadline-freeze (13.8).

Lukitsee mallin rivin data/model_squad_frozen/gw{N}.json:iin kun seuraavan
GW:n deadline on alle FREEZE_WINDOW_H päässä — SAMA ikkuna ja sama cron kuin
freeze_fpl_xp_gw.py:llä, jotta xP-freeze ja joukkuefreeze kuvaavat samaa
hetkeä (muuten "sinä vs malli" vertaisi kahta eri maailmantilaa).

Rivi tulee free_optimum():sta eli TÄSMÄLLEEN samasta funktiosta jota
/api/fantasy/model-squad, rate-teamin benchmark ja fit checker käyttävät.
Oma kopio optimoinnista tähän olisi toinen totuus mallin joukkueesta, ja
julkinen race-paneeli lukisi eri riviä kuin sivu näyttää.

Immutable: olemassa olevaa freezeä EI ylikirjoiteta. Koko V2:n väite on
"logged before kickoff, todistettavissa git-historiasta" — jälkikäteen
vaihdettu rivi tuhoaa sen kertaheitolla.

LAILLISUUSVAHTI (12.8:n oppi): SPL:n model squad julkaistiin sivulle
laittomana (kaksi seuraa yli 3/seura-katon), koska optimoija palautti
lähtötilansa kun yksikään vaihto ei tuottanut laillista joukkuetta. Sama
virhe tässä olisi pysyvä: laiton rivi jäätyisi kauden mittaiseksi
vastustajaksi eikä sitä saisi enää korjata ilman että immutable-lupaus
rikkoutuu. Siksi freeze REFUSOI laittoman rungon (exit 1) eikä lukitse sitä.

Exit 0 myös kun ei jäädytettävää; tekninen virhe tai laiton runko → 1.
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

import config

FROZEN_DIR = config.PROJECT_ROOT / "data" / "model_squad_frozen"
FPL_BASE = "https://fantasy.premierleague.com/api"
FPL_HEADERS = {"User-Agent": "Mozilla/5.0 (GoalIQ freeze job)"}
FREEZE_WINDOW_H = 30   # sama kuin freeze_fpl_xp_gw.py

SQUAD_QUOTA = {1: 2, 2: 5, 3: 5, 4: 3}   # GK/DEF/MID/FWD 15:ssä
MAX_PER_CLUB = 3
BUDGET_TENTHS = 1000   # 100.0m


def gw_xp(player: dict, gw: int) -> float:
    """Pelaajan xP TÄLLE kierrokselle (ei horisonttisumma).

    Kapteeni on aina kierroskohtainen valinta: horisonttisumma nostaisi
    kapteeniksi pelaajan jolla on hyvä ohjelma myöhemmin, vaikka hän olisi
    tässä kierroksessa heikoin. Palauttaa 0.0 jos kierrosta ei projektiossa.
    """
    for g in player.get("gameweeks") or []:
        if g.get("gw") == gw:
            return float(g.get("xp") or 0.0)
    return 0.0


def validate_squad(xi: list[dict], bench: list[dict]) -> list[str]:
    """Palauta rikkeet listana; tyhjä lista = laillinen runko.

    Tarkistetaan koko 15:n runko, ei pelkkää XI:tä — kattorike voi olla
    kokonaan penkillä ja se on silti laiton FPL-joukkue.
    """
    problems: list[str] = []
    squad = list(xi) + list(bench)
    if len(squad) != 15:
        problems.append(f"runko on {len(squad)} pelaajaa, pitää olla 15")
    if len({p["id"] for p in squad}) != len(squad):
        problems.append("rungossa on sama pelaaja kahdesti")

    pos_have: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
    for p in squad:
        et = p.get("element_type")
        if et in pos_have:
            pos_have[et] += 1
    if pos_have != SQUAD_QUOTA:
        problems.append(
            f"positiojakauma {pos_have} != vaadittu {SQUAD_QUOTA}")

    per_club: dict[int, int] = {}
    for p in squad:
        per_club[p.get("club")] = per_club.get(p.get("club"), 0) + 1
    over = {c: n for c, n in per_club.items() if n > MAX_PER_CLUB}
    if over:
        problems.append(f"yli {MAX_PER_CLUB}/seura: {over}")

    cost = sum(int(p.get("price") or 0) for p in squad)
    if cost > BUDGET_TENTHS:
        problems.append(f"hinta {cost / 10:.1f}m yli {BUDGET_TENTHS / 10:.1f}m")

    # OPTIMAALISUUSVAHTI (14.8): laillinen ei riitä. 14.8 julkaistu malli-XI
    # oli täysin laillinen mutta hävisi omalle penkilleen 7.4 % — kuka tahansa
    # olisi voittanut "mallin" siirtämällä kaksi pelaajaa penkiltä avaukseen.
    # Freeze on immutable ja kestää koko kauden, joten se on viimeinen paikka
    # jossa tämän voi vielä pysäyttää.
    # Vaatii horisontti-xP:n; ilman sitä tarkistus ohitetaan eksplisiittisesti
    # (yksikkötestien kevyet poolirivit) — hiljainen KeyError-nielaisu tekisi
    # vahdista näennäisen.
    if len(squad) == 15 and all(p.get("xp_horizon_total") is not None
                                for p in squad):
        from src.models.fpl_rate_team import RateTeamError, optimal_xi
        try:
            best = sum(p["xp_horizon_total"] for p in optimal_xi(squad))
        except RateTeamError:
            best = None
        if best is not None:
            cur = sum(float(p.get("xp_horizon_total") or 0.0) for p in xi)
            if best > cur + 1e-6:
                problems.append(
                    f"XI häviää omalle penkilleen: paras jako {best:.2f} xP "
                    f"> jäädytettävä XI {cur:.2f} xP "
                    f"(+{best - cur:.2f}, {(best / cur - 1) * 100:+.1f} %)")
    return problems


def order_bench(bench: list[dict], gw: int) -> list[dict]:
    """FPL:n penkkijärjestys: GK omana slottinaan, kenttäpelaajat xP-laskevasti.

    Autosub-sääntö kohtelee penkin maalivahtia erikseen (hän tulee vain
    maalivahdin tilalle), joten järjestys EI ole pelkkä xP-lajittelu koko
    penkistä. Tämä järjestys jäätyy riviin ja vaiheen b gradaus lukee sen
    sellaisenaan — penkkijärjestyksen päättäminen vasta gradaushetkellä
    olisi jälkiviisautta.
    """
    gks = [p for p in bench if p.get("element_type") == 1]
    outfield = [p for p in bench if p.get("element_type") != 1]
    outfield.sort(key=lambda p: (-gw_xp(p, gw), p["id"]))
    return gks + outfield


def pick_captain(xi: list[dict], gw: int) -> tuple[dict, dict]:
    """(kapteeni, varakapteeni) = kierroksen kaksi korkeinta xP:tä XI:ssä.

    Tasapelin ratkaisee id, jotta sama pooli tuottaa aina saman rivin
    (freeze on todiste, ei saa heilua ajokerroittain).
    """
    ranked = sorted(xi, key=lambda p: (-gw_xp(p, gw), p["id"]))
    return ranked[0], ranked[1]


def slim(p: dict, gw: int) -> dict:
    return {"id": p["id"], "web_name": p.get("web_name"),
            "team_short": p.get("team_short"), "pos": p.get("element_type"),
            "club": p.get("club"), "price": p.get("price"),
            "xp": round(gw_xp(p, gw), 3)}


# 🔴 SIIRTORAJOITE (25.8.2026, Villen paatos "korjaa malli").
#
# Ennen tata `free_optimum()` rakensi mallin rungon ALUSTA joka kierros: ei
# viittausta edelliseen runkoon, ei siirtorajaa, ei hit-kustannusta. Mitattu
# 25.8 GW1 -> GW2: 7 pelaajaa 15:sta olisi vaihtunut. Ihminen saa YHDEN
# ilmaisen siirron; seitseman maksaisi -24 pistetta. Malli ei maksanut mitaan.
#
# Ja kayttajalle nakyi samaan aikaan lause "The model's squad is locked before
# every deadline and plays no chips." Se on teknisesti tosi (FPL-chippia ei
# aktivoida) mutta antaa ymmartaa etta malli pelaa samoilla saannoilla kuin
# lukija. Alusta rakentaminen on VAHVEMPI kuin wildcard, jonka ihminen saa
# kerran tai kaksi kaudessa. Kisa oli rakenteellisesti epareilu.
#
# Nyt: ensimmainen kierros on vapaa valinta (kauden aloitus, kuten ihmisellakin),
# ja siita eteenpain runko peritaan ja siihen tehdaan FPL:n saannoilla sallitut
# siirrot samalla funktiolla jota TUOTE suosittelee kayttajille.
FT_PER_GW = 1
# Konservatiivinen: klassinen saanto sallii yhden rullauksen (max 2). Jos
# kausisaanto sallii enemman, malli on tassa ALIRAJOITETTU eika ylirajoitettu -
# ja se on oikea suunta epavarmuudessa, koska virhe ei silloin imartele mallia.
FT_MAX = 2


def _prev_freeze(gw: int) -> tuple[int, dict] | None:
    """Lahin AIEMPI jaadytetty kierros ja sen sisalto, tai None.

    Ei oleteta gw-1: kierros voi jaada valiin (ajo kaatui, kausitauko), ja
    silloin runko peritaan silti viimeisimmasta joka on olemassa.
    """
    ehdokkaat = []
    for f in FROZEN_DIR.glob("gw*.json"):
        try:
            n = int(f.stem[2:])
        except ValueError:
            continue
        if n < gw:
            ehdokkaat.append((n, f))
    if not ehdokkaat:
        return None
    n, f = max(ehdokkaat)
    try:
        return n, json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _ft_available(prev_meta: dict) -> int:
    """Kaytettavissa olevat ilmaiset siirrot.

    Rullaus: kayttamaton FT siirtyy seuraavalle kierrokselle FT_MAX:iin asti.
    Vanha freeze ilman kenttaa -> oletus FT_PER_GW (ei rullausta), eli
    konservatiivinen.
    """
    jaljella = prev_meta.get("ft_left")
    if not isinstance(jaljella, int):
        jaljella = 0
    return min(jaljella + FT_PER_GW, FT_MAX)


def _constrained_from_prev(prev: dict, pool: list[dict], gw: int,
                           ft: int) -> dict | None:
    """Peri edellinen runko ja tee siihen FPL:n saannoilla sallitut siirrot.

    🔴 Kayttaa `transfer_suggestions`ia eli TASMALLEEN samaa funktiota jolla
    tuote suosittelee siirtoja kayttajalle. Oma kopio siirtologiikasta tekisi
    mallista eri mielta kuin sen oma neuvo.

    Hitti otetaan vain kun horisontti-hyoty YLITTAA sen hinnan (HIT_COST_XP),
    eli sama kynnys jolla tuote kehottaa ottamaan hitin.
    """
    from src.models.fpl_rate_team import HIT_COST_XP, transfer_suggestions

    by_id = {p["id"]: p for p in pool}
    edellinen = (prev.get("xi") or []) + (prev.get("bench") or [])
    squad = [by_id[p["id"]] for p in edellinen if p["id"] in by_id]
    if len(squad) != 15:
        # Pelaaja poistunut poolista (siirto ulos liigasta tms.) -> emme voi
        # peria runkoa rehellisesti. Kutsuja putoaa vapaaseen optimiin ja se
        # KERROTAAN metassa, ei vaieta.
        return None

    budjetti = int(round(float(prev.get("meta", {}).get("budget", 100.0)) * 10))
    kaytetty = sum(int(p.get("price") or 0) for p in squad)
    bank = budjetti - kaytetty

    siirrot: list[dict] = []
    hitit = 0
    for _ in range(FT_MAX + 3):          # ylaraja: hitteja ei oteta loputtomiin
        ehdotus = transfer_suggestions(squad, pool, bank)
        rivit = ehdotus.get("suggestions") or []
        if not rivit or ehdotus.get("hold"):
            break
        paras = rivit[0]
        # 🔴 `delta_xp_horizon` ON XI-HYOTY. `delta_xp_squad` on RAAKAEROTUS,
        # ja nimet ovat harhaanjohtavat toisin pain kuin luulisi. Valitsin ensin
        # `delta_xp_squad`:in sen nimen perusteella ja mittasin sitten:
        #     Steele -> Verbruggen: delta_xp_squad 17,0 · delta_xp_horizon 2,41
        #     todellinen XI-hyoty (optimal_xi ennen/jalkeen): +2,41
        # Raakaerotus on 17,0 vain koska Steele on PENKKIVAHTI (5,75); XI-vahti
        # on Lammens (20,34), joten Verbruggen syrjayttaa hanet eika Steelea.
        # Verifioitu kaikilla viidella ehdotuksella: `delta_xp_horizon` tasmaa
        # todelliseen XI-hyotyyn joka kerta.
        #
        # Tuote kayttaa oikeaa kenttaa kaikilla pinnoilla (FantasyTools,
        # RateTeam, hold-kynnys) - tama oli vain taman skriptin virhe. Malli
        # joka valitsisi raakaerotuksella ottaisi -4 hitin siirrosta joka
        # tuottaa +2,41, eli tarkalleen sen virheen jota 28.7 korjattiin.
        hyoty = float(paras.get("delta_xp_horizon") or 0.0)
        maksaa = 0.0 if len(siirrot) < ft else HIT_COST_XP
        if hyoty <= maksaa:
            break
        out_id = (paras.get("out") or {}).get("id")
        in_id = (paras.get("in") or {}).get("id")
        if out_id is None or in_id is None or in_id not in by_id:
            break
        out_p = next((q for q in squad if q["id"] == out_id), None)
        in_p = by_id[in_id]
        if out_p is None:
            break
        bank += int(out_p.get("price") or 0) - int(in_p.get("price") or 0)
        squad = [in_p if q["id"] == out_id else q for q in squad]
        siirrot.append({"out": out_id, "in": in_id,
                        "gain_xp": round(hyoty, 2),
                        "hit": maksaa > 0})
        if maksaa > 0:
            hitit += 1

    return {"squad": squad, "bank": bank, "transfers": siirrot,
            "hits": hitit, "ft_available": ft,
            "ft_left": max(0, ft - len(siirrot))}


def next_freeze_gw(events: list[dict], now: _dt.datetime):
    """Seuraava deadline freeze-ikkunassa → (gw, deadline) tai None."""
    for ev in events:
        if ev.get("finished"):
            continue
        dl = _dt.datetime.fromisoformat(
            str(ev.get("deadline_time", "")).replace("Z", "+00:00"))
        if dl > now and (dl - now) <= _dt.timedelta(hours=FREEZE_WINDOW_H):
            return int(ev["id"]), dl
    return None


def main() -> int:
    try:
        r = requests.get(f"{FPL_BASE}/bootstrap-static/", headers=FPL_HEADERS,
                         timeout=30)
        r.raise_for_status()
        events = r.json().get("events") or []
    except Exception as e:
        print(f"VIRHE: bootstrap-haku epäonnistui: {e!r}")
        return 1

    now = _dt.datetime.now(_dt.timezone.utc)
    nxt = next_freeze_gw(events, now)
    if nxt is None:
        print("Ei deadlinea freeze-ikkunassa — ei jäädytettävää.")
        return 0
    gw, dl = nxt

    out = FROZEN_DIR / f"gw{gw}.json"
    if out.exists():
        print(f"GW{gw} on jo jäädytetty — ei ylikirjoiteta (immutable).")
        return 0

    # Sama polku kuin /api/fantasy/model-squad — ei omaa optimointia.
    from src.models.fpl_rate_team import (
        RateTeamError, build_context, free_optimum, optimal_xi)
    try:
        xp_data, _bootstrap, pool, _by_id = build_context()
    except RateTeamError as e:
        print(f"VIRHE: kontekstia ei saatu ({e.detail}).")
        return 1

    # 🔴 PERITTY RUNKO, EI ALUSTA RAKENNETTU. Ks. FT_PER_GW:n kommentti yllä.
    edellinen = _prev_freeze(gw)
    siirtotiedot = None
    free = None
    if edellinen is not None:
        prev_gw, prev = edellinen
        prev_meta = prev.get("meta") or {}
        rajoitettu = _constrained_from_prev(
            prev, pool, gw, _ft_available(prev_meta))
        if rajoitettu is None:
            # Pelaaja poistunut poolista -> runkoa ei voi peria rehellisesti.
            # Pudotaan vapaaseen optimiin ja KERROTAAN se metassa.
            print(f"VAROITUS: GW{prev_gw}:n runkoa ei voitu peria "
                  f"(pelaaja poistunut poolista) — vapaa optimi.")
        else:
            siirtotiedot = rajoitettu
            squad = rajoitettu["squad"]
            xi = optimal_xi(squad)
            xi_ids = {p["id"] for p in xi}
            bench = [p for p in squad if p["id"] not in xi_ids]

    if siirtotiedot is None:
        try:
            free = free_optimum(pool, str(xp_data["meta"].get("generated_at")))
        except RateTeamError as e:
            print(f"VIRHE: mallin runkoa ei saatu ({e.detail}).")
            return 1
        xi, bench = list(free.get("xi") or []), list(free.get("bench") or [])
    if not xi or len(bench) != 4:
        print(f"VIRHE: runko vajaa (XI {len(xi)}, penkki {len(bench)}).")
        return 1

    problems = validate_squad(xi, bench)
    if problems:
        print("VIRHE: optimoija palautti LAITTOMAN rungon — ei jäädytetä:")
        for p in problems:
            print(f"  - {p}")
        return 1

    bench = order_bench(bench, gw)
    cap, vice = pick_captain(xi, gw)
    cost = sum(int(p.get("price") or 0) for p in xi + bench)

    FROZEN_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "meta": {
            "gw": gw,
            "deadline": dl.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "frozen_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "projection_generated_at": xp_data.get("meta", {}).get("generated_at"),
            "cost": round(cost / 10, 1),
            "xi_xp_horizon": round(
                float(free.get("xi_xp") or 0.0) if free
                else sum(p.get("xp_horizon_total") or 0.0 for p in xi), 2),
            "xi_xp_gw": round(sum(gw_xp(p, gw) for p in xi), 2),
            "optimal_proven": bool(free.get("proven")) if free else None,
            # 🔴 SIIRROT JULKISEEN LOKIIN. Ilman naita "malli sai X pistetta"
            # ei kerro maksoiko se siita, ja kisa nayttaisi reilulta vaikka se
            # ei olisi. Ensimmainen kierros: `from_gw` null = vapaa valinta
            # (kauden aloitus, kuten ihmisellakin).
            "budget": 100.0,
            "from_gw": (edellinen[0] if edellinen and siirtotiedot else None),
            "transfers": (siirtotiedot or {}).get("transfers") or [],
            "hits": (siirtotiedot or {}).get("hits", 0),
            "ft_available": (siirtotiedot or {}).get("ft_available"),
            "ft_left": (siirtotiedot or {}).get("ft_left", 0),
            "squad_rebuilt": siirtotiedot is None,
            # Malli ei pelaa chippejä (spec) — kerrotaan datassa asti, jotta
            # paneeli ei joudu arvaamaan sitä copyn perusteella.
            "chip": None,
        },
        "captain": cap["id"],
        "vice_captain": vice["id"],
        "xi": [slim(p, gw) for p in xi],
        "bench": [slim(p, gw) for p in bench],
    }, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"OK: GW{gw} mallin runko jäädytetty "
          f"({cost / 10:.1f}m, kapteeni {cap.get('web_name')}, "
          f"XI xP {sum(gw_xp(p, gw) for p in xi):.2f}, deadline {dl}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
