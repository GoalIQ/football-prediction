"""Yhden kierroksen xP-valinta: YKSI lista, kaksi pintaa (FREE-GW-XP 30.8.2026).

MIKSI TAMA MODUULI ON OLEMASSA
------------------------------
Projected-XI-kortti julkaisee GW-xP top 15:n kuvana ja sanoo alapalkissaan
mista luvun voi tarkistaa. 30.8 mitattu: tarkistusreitti osoitti sivulle jolla
ei ollut yhtakaan kortin lukua. `/fpl/expected-points` rankkaa kuuden
kierroksen YHTEISSUMMALLA ja sanoo sen itse ("xP/GW is that total divided by
6, not a single-gameweek projection"), joten Haaland oli kortilla 6.2 ja
sivulla 35.6 / 5.94, ja jarjestyskin oli eri. Luku jota ei voi tarkistaa on
julkaisutarkistajan portti 1, ja se on blokannut omia GW-xP-vaitteitamme.

Korjaus ei ole "renderoi sivulle samankaltainen taulukko" vaan **sama
valintafunktio molemmille pinnoille**. Jos kortti ja sivu laskisivat listansa
omilla silmukoillaan, ne ajautuisivat erilleen hiljaa - ja tarkistusreitti
joka nayttaa ERI luvun on pahempi kuin puuttuva tarkistusreitti, koska se
nayttaa toimivalta (muisti: kuratoitu-lista-jaettuun-moduuliin,
sama-vaite-monella-renderointipolulla).

Sijainti on `src/models/`, ei kumpikaan skripti: `render_projected_xi_card`
importoi jo `build_fpl_longtail`ista (`_kit_svg`), joten vastakkainen import
olisi syklinen.

KOLME SAANTOA JOTKA KULKEVAT LISTAN MUKANA
------------------------------------------
1. **Kierros on `actionable_gameweek`, ei `next_gameweek`.** Mitattu 30.8:
   `next_gameweek` oli 2 ja `deadline_gameweek` 3, eli GW2 oli KESKEN.
   Ranking kierrokselle jonka deadline on mennyt ei ole ennuste vaan
   historiaa vaarassa asussa - eika siihen voi enaa siirtaa ketaan.
2. **Seurakatto `MAX_PER_CLUB`** (luetaan `fpl_rate_team`ista kutsuhetkella). Villen paatos 30.8 kortille: ilman kattoa
   GW3:n lista oli 8x Man City + 3x Hull viidestatoista. Mitattu tanaan
   ilman kattoa top 20:lle: **10/20 Man City, 7 eri seuraa**; FPL:n oma
   `ep_next` samalle kierrokselle antaa 11 eri seuraa, korkeintaan 4 samasta.
   Ero on mekanismi eika malliharha - MCI kotona nousijaa vastaan nostaa koko
   puolustuksen nollapeli-%:n kerralla - mutta **FPL sallii korkeintaan kolme
   pelaajaa per seura**, joten kattamaton lista on rivi riviltä pelikelvoton.
3. **Sama estolista kuin kortilla.** status 'a' + `publish_blocklist.json` +
   Thiaw-esto sukunimiosalla. Ilmaissivu on julkinen pinta siina missa kortti.
"""
from __future__ import annotations

from src.models.fpl_gameweek import actionable_gameweek

# Nimet joita ei nosteta millekaan julkiselle pinnalle (muisti:
# thiaw-ei-markkinointiin). Sukunimiosalla: "M.Thiaw" ja "Thiaw" ovat sama.
EXCLUDED_NAMES = {"thiaw"}

# Ilmaispinnan rivimaara. Villen GO 30.8 koski tasmalleen tata lukua
# ("GW-xP top 20"), joten se ei ole viritysparametri: sen kasvattaminen on
# hinnoittelupaatos, ei renderointipaatos.
FREE_TOP_N = 20


def excluded(name: str, blocklist: list[dict] | None = None) -> bool:
    """Sukunimiosalla ja pienin kirjaimin, kuten kortin oma esto."""
    tail = str(name or "").split(".")[-1].strip().lower()
    names = set(EXCLUDED_NAMES)
    for e in blocklist or ():
        names.add(str(e.get("name") or "").split(".")[-1].strip().lower())
    return tail in names


def gw_xp(p: dict, gw: int):
    """Pelaajan xP TALLE kierrokselle (`gameweeks[].xp`), EI `xp_per_gw`.

    `xp_per_gw` on horisontin summa jaettuna kierrosmaaralla (muisti:
    xp-per-gw-ei-ole-gw-xp). Palauttaa None kun kierros puuttuu (blank GW),
    ei 0.0 - nolla lukisi "ei tuota pisteita" (muisti:
    nolla-ei-ole-sama-kuin-ei-tietoa).
    """
    for g in p.get("gameweeks") or []:
        if g.get("gw") == gw:
            return float(g.get("xp") or 0.0)
    return None


def opponent_text(p: dict, gw: int) -> str:
    """Vastustaja(t) talle kierrokselle. Double gameweek nayttaa MOLEMMAT.

    🔴 Lista, ei dict: `fdr_rows_from_teams` avainsi ottelut gameweekilla ja
    doublen jalkimmainen ottelu ylikirjoitti ensimmaisen (FDR-GRID-DGW).
    Tassa lahde on jo lista, ja se pidetaan listana.
    """
    for g in p.get("gameweeks") or []:
        if g.get("gw") == gw:
            opps = g.get("opponents") or []
            if not opps:
                return "blank"
            return ", ".join(f"{o.get('opp')} ({o.get('venue')})" for o in opps)
    return ""


def eligible(players: list[dict], gw: int,
             blocklist: list[dict] | None = None) -> list[dict]:
    """Pooli: status 'a', ei estolistalla, GW-xP olemassa talle kierrokselle."""
    return [p for p in players
            if p.get("status", "a") == "a"
            and not excluded(p.get("web_name"), blocklist)
            and gw_xp(p, gw) is not None]


def club_of(p: dict):
    """Sama seura-avain kuin optimoijan poolissa."""
    return p.get("team") or p.get("team_short")


# Kapteenikandidaattien seurakatto (Villen paatos 30.8.2026). ERI luku kuin
# `MAX_PER_CLUB`, ja syy on eri: FPL:n sääntö sallii kolme pelaajaa per seura,
# mutta kapteeniehdokkaita ei valita saannon vaan HAJAUTUKSEN takia.
#
# 🔴 Mitattu 30.8 kuudelta kierrokselta: GW3 ja GW5 antoivat kolmen karjen
# jossa KAIKKI kolme olivat Man Cityn pelaajia (Haaland, Guehi, O'Reilly),
# molemmat Cityn kotiotteluita heikkoa vastustajaa vastaan. Se ei ole
# satunnaista vaan toistuu aina samalla fixture-kuviolla: vahva kotiottelu
# nostaa koko joukkueen kerralla.
#
# Kolme saman joukkueen pelaajaa samaa vastustajaa vastaan on YKSI veto
# kolmella nimella - jos joukkue epaonnistuu, kaikki kolme kaatuvat yhdessa.
# Kapteenisivun tehtava on antaa vaihtoehtoja, joten kandidaatteja rajataan
# kahteen per seura. Tama on tuotepaatos, ei saantopakko.
MAX_CAPTAIN_PER_CLUB = 2


def top_projected(players: list[dict], gw: int, n: int,
                  blocklist: list[dict] | None = None,
                  max_per_club: int | None = None) -> list[dict]:
    """GW-xP top n laskevasti, korkeintaan `MAX_PER_CLUB` per seura.

    `max_per_club` oletuksena `MAX_PER_CLUB` (FPL:n saanto). Kapteenisivu
    antaa `MAX_CAPTAIN_PER_CLUB`, koska sen rajaus on hajautusta eika saanto.

    Tasapeli ratkaistaan `id`:lla eika nimella: nimi ei ole avain (muisti:
    web-name-ei-ole-avain, 9 duplikaattia), ja ilman deterministista
    ratkaisijaa kortti ja sivu voisivat jarjestaa kaksi 4.8:aa eri tavalla.
    """
    # Katto luetaan KUTSUHETKELLA optimoijan omasta moduulista, ei tuoda
    # nimena tanne: nimeksi tuotu vakio jaatyisi import-hetkeen, ja silloin
    # kortin puoliskot voisivat ajautua eri sääntöön ilman etta mikaan huutaa.
    if max_per_club is None:
        from src.models.fpl_rate_team import MAX_PER_CLUB
        max_per_club = MAX_PER_CLUB
    pool = eligible(players, gw, blocklist)
    pool.sort(key=lambda p: (-gw_xp(p, gw), int(p.get("id") or 0)))
    out: list[dict] = []
    clubs: dict = {}
    for p in pool:
        c = club_of(p)
        if clubs.get(c, 0) >= max_per_club:
            continue
        clubs[c] = clubs.get(c, 0) + 1
        out.append(p)
        if len(out) >= n:
            break
    return out


def free_rows(xp: dict, blocklist: list[dict] | None = None
              ) -> tuple[int | None, list[dict]]:
    """(kierros, rivit) ilmaispinnalle. Kierros luetaan metasta, ei anneta.

    Palauttaa `(None, [])` kun artefakti ei ole kaytettavissa tai kierrosta ei
    voi paatella - kutsuja jattaa osion renderoimatta. Tyhja osio on parempi
    kuin osio joka nayttaa vaaran kierroksen lukuja.
    """
    meta = xp.get("meta") or {}
    players = xp.get("players") or []
    if not meta.get("available") or not players:
        return None, []
    gw = actionable_gameweek(meta)
    if not isinstance(gw, int):
        return None, []
    return gw, top_projected(players, gw, FREE_TOP_N, blocklist)
