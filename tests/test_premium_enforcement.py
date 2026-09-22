"""P0 (11.8.2026): Premium-payload oli julkinen tuotannossa.

Loydos: `curl https://api.goaliq.app/api/fantasy/xp` palautti 502 pelaajaa
taysilla kentilla (xp_per_gw, xp_horizon_total, components, owned_pct) ILMAN
autentikointia. Syy ei ollut puuttuva gate vaan se etta `PREMIUM_ENFORCE` oli
Renderissa pois, jolloin `is_premium_request()` palauttaa aina True.

Nama testit lukitsevat kaksi asiaa joita mikaan olemassa oleva portti ei mitannut:

  1. **Maskaus toimii kun flagi on paalla.** Ilman tata "gate on paikallaan"
     -tarkistus on pelkka koodinluku: kutsupaikan olemassaolo ei todista etta
     payload oikeasti kutistuu (vrt. muisti `portti-voi-mitata-eri-koodipolkua`).
  2. **Gatettujen endpointtien JOUKKO on tasan odotettu.** Jos joku lisaa uuden
     premium-endpointin ilman gatea, tai poistaa gaten olemassa olevasta, testi
     kaatuu. Tama on se portti jota ei ollut: gatejen kattavuutta ei mitannut
     mikaan, joten aukon olisi voinut huomata vasta tuotannosta.

Negatiivinen kontrolli mukana molemmissa: flagi pois -> payload EI kutistu.
Ilman sita testi lapaisisi myos silloin kun maskaus kutistaisi kaiken aina.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

API_DIR = Path(__file__).resolve().parents[1] / "api"

# Endpointit jotka SAAVAT palauttaa premium-datan vain tunnistautuneelle.
# Lahde: klienttien gate-totuus (goaliq-app/components/FantasyTools.tsx
# TOOL_PREMIUM = chips/plans/edge true; web/pro-spa .../ToolsHome.svelte
# premium: true) + landingin Premium-paneeli (index.html).
GATED_EXPECTED = {
    "/api/fantasy/xp",
    "/api/fantasy/xp.csv",
    "/api/fantasy/chip-ev",
    # 25.8: WILDCARD-PLAN on GATED, mutta sen maski on osittainen — verdikti
    # ("kannattaako, ja kuinka paljon per kierros") on ilmainen, rivisto ja
    # pelaajanimet premiumia. 🔴 Maski poistaa nimeavat perustelut MYOS
    # `reasons`-listasta: pelkka kenttien pudotus olisi jattanyt karkipoiminnan
    # nakyviin lauseen sisalle ("The strongest it brings in is X at 5.79").
    "/api/fantasy/wildcard-plan",
    "/api/fantasy/plan-chains",
    "/api/fantasy/edge",
    # 2.9 FANTASY-TOOLS-ENDPOINT-AUTH: myyty premium-riville, mitattu
    # anonyymina taysi lista -> gate + mask (free = kohde + 1 rivi).
    "/api/fantasy/replacements",
    # 4.9: VALUE oli maskattu vain SELAIMESSA (Value.svelte leikkaa listan
    # kolmeen ja GK-osio on `{#if premium}`), mutta API palautti 20 rivia +
    # koko GK-lohkon anonyymille. GK-parit ovat myyntilistan premium-rivi.
    # Free = sama 3 rivia jonka klientti nayttaa -> nakyva sisalto ei muutu.
    "/api/fantasy/value",
    # 18.9 COMPARE-PALVELINRAJA: compare siirtyi FREE_EXPECTEDista tanne.
    # Anonyymi `?players=411,426` palautti 2 taytta rivia + verdictin ja
    # `meta.mask=None` (mitattu livena 18.9 13:40 UTC). Seitsemas kerta
    # tata vikaluokkaa.
    #
    # GATED eika PARTIAL, ja se on MITATTU: molemmat klientit piilottavat
    # comparen ilmaiskayttajalta KOKONAAN (SPA ToolsHome `{#if premium}`
    # ymparoi seka ComparePlayersin etta XpTablen, jonka "share comparison"
    # kutsuu samaa endpointia; mobiili `isPremium ? <CompareSection/> :
    # <ToolsLockedTeaser/>`), ja viisi julkista pintaa mainitsevat player
    # comparen vain Premium-lauseessa. Ilmaista ydinta ei ole, joten
    # PARTIAL-rivi olisi vaite jota testit valvoisivat vaarana.
    "/api/fantasy/compare",
}

# Nama ovat tarkoituksella ilmaisia (rate my team, kapteenipoiminta,
# price watch, leaderboardien karki, career, mini-liiga). Jos jokin naista
# muuttuu premiumiksi, se lisataan GATED_EXPECTEDiin ja gate koodiin.
FREE_EXPECTED = {
    # 25.8: MY TEAM LEDGER on tietoisesti ilmainen. Se nayttaa kuinka paljon
    # mallin ennuste erosi lukijan TOTEUTUNEISTA pisteista, eli se on luku joka
    # voi nolata mallin. Mitattu ensimmaisella ajolla: mallin oma joukkue
    # yliennustettiin 14,6 pisteella (55,64 -> 41). Rehellisyyspinta
    # maksumuurin takana kumoaa itsensa - koko tuote myydaan silla etta
    # tarkkuuden voi tarkistaa ennen maksamista.
    "/api/fantasy/my-team-ledger",
    # 25.8: POST-GW-KATSAUS samasta syysta. Sen `worst_call`-kentta nayttaa
    # mallin PAHIMMAN hudin kierroksella, ja se on koko pinnan tarkoitus:
    # rehellisyys on kayttoliittyma. Huti maksumuurin takana on sama asia kuin
    # ei hutia.
    "/api/fantasy/gw-review",
    "/api/fantasy/price-watch",
    "/api/fantasy/fit",
    "/api/fantasy/model-squad",
    # 22.9: mallin kapteeni seuraavalle deadlinelle. Sama kapteeni on jo
    # julkinen goaliq.app/fpl:n kutsulokissa ja rate-teamin ilmaisessa
    # `captain.pick`issa; vastaus rajataan response_modelilla nimettyihin
    # kenttiin (ei siirtoehdotuksia).
    "/api/fantasy/model-captain",
    # 4.9 VILLEN PAATOS: differentials on ilmainen kaikilla pinnoilla
    # (landing, rekisterin tier, SPA:n gate, API). Mitattu syy paatoksen
    # taustalla: julkisen /fpl/differentials-sivun generaattori hakee taman
    # CI:sta ANONYYMINA ja nielee virheen varoituksella, joten maski olisi
    # pudottanut sivun kahteen riviin hiljaa.
    "/api/fantasy/differentials",
    "/api/fantasy/xg-leaders",
    # 17.9: defcon-gw ja defcon/{player_id} pysyvat ilmaisina myos sen
    # jalkeen kun defcon-leaders siirtyi PARTIALiin: per-GW-matriisi ja
    # pelaajakortin DefCon-loki ovat FPL:n omaa otteludataa, eivat rankingia.
    "/api/fantasy/defcon-gw",
    "/api/fantasy/defcon-live",
    # 18.9: compare siirtyi GATED_EXPECTEDiin (perustelu siella).
    "/api/fantasy/career",
    "/api/fantasy/league/{league_id}",
    "/api/fantasy/h2h",
    "/api/fantasy/defcon/{player_id}",
}

# KOLMAS LUOKKA (13.8): ilmainen ydin + premium-erittely samassa vastauksessa.
# Taksonomia oli binaarinen, ja `/api/fantasy/model-race` ei mahtunut
# kumpaankaan: Season race -tulos on ilmainen (silmukan palkinto), mutta
# "missa ero syntyi" -erittely on premiumia. Pakottaminen GATEDiin olisi
# vaittanyt etta koko endpoint on maksumuurin takana; FREEhen pakottaminen
# olisi kaatanut test_free_endpoints_stay_ungatedin ja poistanut gaten.
# Nailla on TIUKEMMAT saannot kuin kummallakaan: gate on pakollinen JA
# maskaus todennetaan ajamalla, ei merkkijonohaulla.
PARTIAL_EXPECTED = {
    # 6.9: FPL:n raakaluvut ja freeze-vertailu ilmaisia, next_gw_xp ja
    # xp_horizon_total premium (Villen 8.8-linjaus: raakaluvut ilmaiseksi).
    "/api/fantasy/player-stats",
    "/api/fantasy/model-race",
    # 13.8: sama kuvio — sija ja piste-ero ovat FPL:n julkista dataa
    # (free), mallin kanta siihen mita erolle pitaisi tehda on premium.
    "/api/fantasy/rival",
    # 15.8: captain siirtyi FREEsta tanne. Se oli listattu ilmaiseksi ja
    # palautti autentikoimattomalle `top3` JA `differential` — eli tasan sen
    # mita premium-paneeli myy ("Captain ranker: top three, a differential
    # pick"). Portti oli VAIN selaimessa, joten suora API-kutsu sai koko
    # ominaisuuden.
    #
    # Se ei kuulu kumpaankaan binaariseen luokkaan: myyntisivu lupaa ILMAISEKSI
    # "Rate my team, with a captain pick" eli YHDEN valinnan. Vastaus on siis
    # ilmainen ydin + premium-erittely, mika on tasan tama kolmas luokka.
    # Koodi siirtyi vastaamaan copya, ei toisin pain.
    "/api/fantasy/captain",
    # 5.9: rate-team siirtyi FREEsta tanne, samasta syysta kuin captain 15.8.
    # Julkaisutarkistaja mittasi anonyymilla curlilla: `transfers.suggestions`
    # palautui 5 rivina nimineen ja delta_xp_horizon-lukuineen, `meta.masked`
    # null. Portti oli vain selaimessa ({#if premium}). Myyntisivu lupaa
    # ILMAISEKSI "Rate my team, with a captain pick" ja PREMIUMIKSI
    # siirtosuositukset, joten vastaus on ilmainen ydin (rating, linjat,
    # kapteeni, hold-verdikti) + premium-erittely (suositukset). Viides
    # kerta tata vikaluokkaa; maski on nyt endpointissa.
    "/api/fantasy/rate-team",
    # 17.9 DEFCON-LEADERS-PALVELINRAJA: defcon-leaders siirtyi FREEsta tanne.
    # "Full DefCon leaderboard" on myyty premiumina vahintaan viidella
    # pinnalla (fpl.html, build_fpl_page.py, llms.txt, mobiilin
    # paywall-bulletit, SPA:n Leaders-teaser), mutta anonyymi kutsu sai
    # 182 rivia (season) / 377 rivia (window=5) ja meta.masked=None
    # (mitattu livena 12.9 ja 17.9). Portti oli VAIN selaimessa: molemmat
    # klientit leikkasivat listan kolmeen itse. Kuudes kerta tata
    # vikaluokkaa. Ilmainen ydin = top 3 (sama luku jonka klientit jo
    # nayttivat), premium-erittely = loput rivit. Maski on endpointissa.
    "/api/fantasy/defcon-leaders",
    # 20.9 MITATTU LIVENA, anonyymi `GET /api/fantasy/plan?entry=116920`:
    # **200**, `meta.masked: True`, `meta.mask: "first 1 of 5 gameweeks
    # (free preview)"` ja yksi taysi rivi jossa on kapteenin NIMI ja xP.
    # Se ei ole GATED vaan PARTIAL, ja ero ei ole kosmeettinen: GATED-
    # luokassa mikaan testi ei mittaa maskin KOKOA, joten kasvava ilmainen
    # esikatselu ei punastuisi. Luokittelu seuraa nyt mitattua kaytosta.
    "/api/fantasy/plan",
}

# Erittelykentat jotka EIVAT saa nakya ilman premiumia.
PARTIAL_PREMIUM_KEYS = {
    "/api/fantasy/player-stats": ("next_gw_xp", "xp_horizon_total"),
    "/api/fantasy/model-race": (
        "model_captain_id", "model_bench_points", "model_autosubs"),
    "/api/fantasy/rival": ("differentials",),
    # Differential-kapteeni on nimenomaan myyty premium-riville.
    "/api/fantasy/captain": ("differential",),
    "/api/fantasy/rate-team": ("suggestions",),
    # 17.9: premium-osa on LISTAN HANTA, ei kentta. Raja on yksi vakio
    # (api.premium.FREE_LEADERS_ROWS) ja se kulkee vastauksen metassa
    # (`free_rows`); vuoto = players-lista pidempi kuin free_rows ilman
    # premiumia. Todennetaan ajamalla alla (molemmat basikset).
    "/api/fantasy/defcon-leaders": ("players[free_rows:]",),
    # Premium-osa on LISTAN HANTA kuten defcon-leadersissa: ilmainen saa
    # `plan[:FREE_PLAN_GWS]`, loput kierrokset ovat premiumia.
    "/api/fantasy/plan": ("plan[FREE_PLAN_GWS:]",),
}


def _scan_gates() -> dict[str, bool]:
    """Lue @app/@router-dekoraattorit ja kerro kutsuuko runko gatea.

    Staattinen luku eika app.routes-introspektio, koska me haluamme tietaa
    kutsuuko juuri TAMAN endpointin runko is_premium_requestia — reitistosta
    sita ei nae.
    """
    gates: dict[str, bool] = {}
    pat = re.compile(r'@(?:app|router)\.(?:get|post)\("(/api/fantasy/[^"]+)"')
    for src in (API_DIR / "main.py", API_DIR / "fantasy_edge.py"):
        lines = src.read_text(encoding="utf-8").split("\n")
        hits = [(i, m.group(1)) for i, ln in enumerate(lines)
                if (m := pat.match(ln.strip()))]
        for k, (i, path) in enumerate(hits):
            end = hits[k + 1][0] if k + 1 < len(hits) else len(lines)
            body = "\n".join(lines[i:end])
            gates[path] = "is_premium_request" in body
    return gates


def test_premium_endpoints_are_gated():
    """Jokainen premium-endpoint kutsuu gatea."""
    gates = _scan_gates()
    missing = sorted(p for p in GATED_EXPECTED if not gates.get(p))
    unknown = sorted(p for p in GATED_EXPECTED if p not in gates)
    assert not unknown, f"Endpointtia ei loydy koodista enaa: {unknown}"
    assert not missing, (
        "Premium-endpoint ilman is_premium_request-gatea: "
        f"{missing}. Tama on P0 — payload vuotaa tunnistautumattomille."
    )


def test_no_new_ungated_endpoint_appeared():
    """Uusi fantasy-endpoint on luokiteltava eksplisiittisesti.

    Tama on se portti jota ei ollut: aiemmin uuden endpointin saattoi lisata
    ilman etta kukaan paatti onko se ilmainen vai maksullinen.
    """
    gates = _scan_gates()
    known = GATED_EXPECTED | FREE_EXPECTED | PARTIAL_EXPECTED
    surprises = sorted(set(gates) - known)
    assert not surprises, (
        f"Luokittelematon fantasy-endpoint: {surprises}. Lisaa se joko "
        "GATED_EXPECTEDiin (ja gate koodiin) tai FREE_EXPECTEDiin."
    )


def test_gated_endpoints_actually_truncate():
    """Gate ei riita: jokaisen on myos TYPISTETTAVA payload.

    Todellinen vikatila jota tama vahtii: endpoint laskee
    `premium = is_premium_request(request)` ja **ei kayta muuttujaa mihinkaan**.
    Silloin `test_premium_endpoints_are_gated` on vihrea, koodinluku nayttaa
    oikealta, ja koko payload menee silti ulos. Sama luokka kuin muisti
    `portti-voi-mitata-eri-koodipolkua`.

    Hyvaksytaan joko FREE_*-vakio (inline-typistys, fantasy_edge.py) tai
    mask_*-funktio (main.py) — molemmat ovat aitoja typistyksia.
    """
    import re
    gates: dict[str, str] = {}
    pat = re.compile(r'@(?:app|router)\.(?:get|post)\("(/api/fantasy/[^"]+)"')
    for src in (API_DIR / "main.py", API_DIR / "fantasy_edge.py"):
        lines = src.read_text(encoding="utf-8").split("\n")
        hits = [(i, m.group(1)) for i, ln in enumerate(lines)
                if (m := pat.match(ln.strip()))]
        for k, (i, path) in enumerate(hits):
            end = hits[k + 1][0] if k + 1 < len(hits) else len(lines)
            gates[path] = "\n".join(lines[i:end])

    toothless = []
    for path in sorted(GATED_EXPECTED):
        body = gates.get(path, "")
        if not ("FREE_" in body or "mask_" in body):
            toothless.append(path)
    assert not toothless, (
        f"Gate ilman typistysta: {toothless}. Endpoint laskee premium-lipun "
        "mutta ei kutista payloadia — portti on vihrea ja data vuotaa silti."
    )


def test_free_endpoints_stay_ungated():
    """Negatiivinen kontrolli luokittelulle: ilmaiset EIVAT ole gatettuja.

    Ilman tata GATED_EXPECTED lapaisisi myos silloin jos joku gateaisi kaiken,
    jolloin ilmaispinta ja sivugeneraattorit hajoaisivat hiljaa.
    """
    gates = _scan_gates()
    wrongly_gated = sorted(p for p in FREE_EXPECTED if gates.get(p))
    assert not wrongly_gated, (
        f"Ilmaiseksi luokiteltu endpoint on gatettu: {wrongly_gated}. "
        "Tama katkaisee ilmaispinnan ja mahdollisesti sivugeneraattorit."
    )


def test_partial_endpoints_are_gated():
    """Osittain gatetun endpointin runko ON kutsuttava gatea.

    Ilman tata erittelykentat vuotaisivat kaikille, ja koska ydin on
    ilmainen, mikaan 403 tai tyhja vastaus ei paljastaisi vuotoa.
    """
    gates = _scan_gates()
    missing = sorted(p for p in PARTIAL_EXPECTED if not gates.get(p))
    assert not missing, (
        f"Osittain gatettu endpoint ilman is_premium_requestia: {missing}.")


@pytest.fixture()
def race_client(tmp_path, monkeypatch):
    """TestClient jolla on synteettinen gradausloki levylla.

    Esikaudella oikea loki on tyhja, jolloin maskaustesti mittaisi tyhjaa
    vastausta eika maskausta (vrt. muisti `gate-substring-osuma-on-sokea`).
    """
    import api.main as m
    import src.models.model_squad_scores as mss

    # 21.9.2026: endpoint lukee julkisen mallisarjan yhdella lukijalla
    # (load_public_model_series), ei tiedostoa PROJECT_ROOTista.
    sarja = {"meta": {"series_source": "frozen_squad"}, "gameweeks": [{
        "gw": 1, "points": 61, "fpl_average": 57, "captain_id": 351,
        "captain_reason": "captain", "captain_points_added": 12,
        "bench_points": 5, "transfer_cost": 0, "active_chip": None,
        "provisional": False, "row_basis": "frozen",
        "autosubs": [{"out": 7, "in": 13, "pos": 2}]}]}
    monkeypatch.setattr(mss, "load_public_model_series", lambda **kw: sarja)
    return TestClient(m.app)


def test_model_race_hides_breakdown_when_enforcement_on(race_client, monkeypatch):
    """Flagi paalla + ei tokenia -> tulos nakyy, erittely ei."""
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    d = race_client.get("/api/fantasy/model-race").json()
    assert d["meta"]["available"] is True
    assert d["meta"]["masked"] is True
    assert d["totals"]["model"] == 61          # ydin on ilmainen
    row = d["gameweeks"][0]
    assert row["model_points"] == 61
    leaked = [k for k in PARTIAL_PREMIUM_KEYS["/api/fantasy/model-race"]
              if k in row]
    assert not leaked, f"Premium-erittely vuoti ilmaiselle: {leaked}"


def test_model_race_full_when_enforcement_off(race_client, monkeypatch):
    """NEGATIIVINEN KONTROLLI: flagi pois -> erittely on mukana.

    Ilman tata edellinen testi lapaisisi myos silloin jos kentat puuttuisivat
    aina — eli mittaisimme kentan poissaoloa emmeka maskausta.
    """
    monkeypatch.setenv("PREMIUM_ENFORCE", "off")
    d = race_client.get("/api/fantasy/model-race").json()
    assert d["meta"]["masked"] is False
    row = d["gameweeks"][0]
    for k in PARTIAL_PREMIUM_KEYS["/api/fantasy/model-race"]:
        assert k in row, f"Erittelykentta {k} puuttuu premiumilta"
    assert row["model_captain_id"] == 351


@pytest.fixture()
def client():
    import api.main as m
    return TestClient(m.app)


def test_xp_is_masked_when_enforcement_on(client, monkeypatch):
    """Flagi paalla + ei tokenia -> typistetty lista, ei koko payload."""
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    from api.premium import FREE_XP_TEASER_N

    r = client.get("/api/fantasy/xp")
    assert r.status_code == 200
    d = r.json()
    assert d["meta"].get("masked") is True
    assert len(d["players"]) == FREE_XP_TEASER_N


def test_xp_is_masked_for_invalid_token(client, monkeypatch):
    """Kelvoton token ei ohita gatea (fail-closed tunnistautumisessa)."""
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    from api.premium import FREE_XP_TEASER_N

    r = client.get("/api/fantasy/xp",
                   headers={"Authorization": "Bearer ei-kelpaa"})
    assert r.status_code == 200
    assert len(r.json()["players"]) == FREE_XP_TEASER_N


def test_xp_is_full_when_enforcement_off(client, monkeypatch):
    """NEGATIIVINEN KONTROLLI: flagi pois -> payload EI kutistu.

    Ilman tata kaksi edellista testia lapaisisivat myos silloin jos maskaus
    olisi paalla aina — eli emme mittaisi flagia vaan maskifunktiota.
    """
    monkeypatch.setenv("PREMIUM_ENFORCE", "off")
    from api.premium import FREE_XP_TEASER_N

    r = client.get("/api/fantasy/xp")
    assert r.status_code == 200
    d = r.json()
    assert d["meta"].get("masked") is not True
    assert len(d["players"]) > FREE_XP_TEASER_N, (
        "Flagi pois eika payload ole taysi — maskaus vuotaa flagin ohi."
    )


def test_masked_rows_stay_complete(client, monkeypatch):
    """Maski on TYPISTYS eika null-korvaus.

    Mobiili renderoi esim. player.xp_per_gw.toFixed(1); null kaataisi nakyman.
    Sama suunnitteluperiaate on kirjattu api/premium.py:n maskilohkoon.
    """
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    r = client.get("/api/fantasy/xp")
    players = r.json()["players"]
    assert players, "Maskattu payload on tyhja — teaser ei saa olla nolla rivia."
    for p in players:
        for field in ("web_name", "team", "pos", "xp_per_gw", "xp_horizon_total"):
            assert p.get(field) is not None, f"Maskattu rivi menetti kentan {field}"


# --- FREE-DRAFT-POOL (14.8) ------------------------------------------------
#
# Loydos 14.8: maskattu vastaus antoi free-kayttajalle 10 rivia 505:sta ja
# niissa oli MID 4 / DEF 4 / FWD 2 / **GKP 0**. Draft rater vaatii 2 GKP, joten
# lahetysnappi ei aktivoitunut koskaan — seka mobiilissa etta webissa, koska
# molemmat hakevat valitsinpoolinsa samasta kutsusta. Yksikaan portti ei
# nahnyt sita: backend vastasi 200, tsc oli vihrea, ja rikki oli tyhja lista.
# Nama testit lukitsevat KAYTETTAVYYDEN (voiko 15 slottia tayttaa) eivatka
# vain listan pituutta.

DRAFT_SLOTS = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}


def _pos_counts(rows: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        out[r.get("pos")] = out.get(r.get("pos"), 0) + 1
    return out


def test_maskattu_vastaus_ei_riita_valitsimeksi(client, monkeypatch):
    """Kontrolli itse oireelle: teaser-rivit EIVAT tayta draftin slotteja.

    Jos tama joskus lakkaa patemasta, `pool` on tarpeeton — mutta silloin se
    on paatettava eksplisiittisesti eika vahingossa.
    """
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    d = client.get("/api/fantasy/xp").json()
    counts = _pos_counts(d["players"])
    puuttuu = {p: n for p, n in DRAFT_SLOTS.items() if counts.get(p, 0) < n}
    assert puuttuu, ("teaser tayttaa jo draftin slotit — tama testi ei enaa "
                     "mittaa mitaan")


def test_anonyymi_saa_taydentavan_valitsinpoolin(client, monkeypatch):
    """POSITIIVINEN: anonyymi pystyy tayttamaan 15/15 slottia."""
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    r = client.get("/api/fantasy/xp")
    assert r.status_code == 200
    pool = r.json().get("pool")
    assert pool, "kevyt valitsinpooli puuttuu maskatusta vastauksesta"
    counts = _pos_counts(pool)
    vajaat = {p: (counts.get(p, 0), n) for p, n in DRAFT_SLOTS.items()
              if counts.get(p, 0) < n}
    assert not vajaat, f"valitsimesta ei saa koottua 15:ta: {vajaat}"


def test_valitsinpooli_ei_sisalla_yhtaan_xp_arvoa(client, monkeypatch):
    """NEGATIIVINEN KONTROLLI: pooli ei saa vuotaa premium-ydinta.

    Testataan kentat NIMELTA eika vain otoksesta: uusi kentta joka livahtaa
    XP_POOL_FIELDSiin loytyisi vasta tuotannosta.
    """
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    from api.premium import XP_POOL_FIELDS

    pool = client.get("/api/fantasy/xp").json()["pool"]
    assert pool
    kielletyt = {"xp_per_gw", "xp_horizon_total", "xp_per_90", "components",
                 "owned_pct", "why", "gameweeks", "xmins"}
    for row in pool:
        assert set(row) == set(XP_POOL_FIELDS), (
            f"valitsinpoolin kenttajoukko muuttui: {sorted(row)}")
        assert not (set(row) & kielletyt)
    # ...ja sama vaite kenttalistalle itselleen, jotta lisays huomataan
    # myos silloin kun rivi sattuisi olemaan tyhja.
    assert not (set(XP_POOL_FIELDS) & kielletyt)
    assert not [f for f in XP_POOL_FIELDS if "xp" in f.lower()]


def test_valitsinpooli_on_myos_premiumilla(client, monkeypatch):
    """Yksi koodipolku klientilla: pooli tulee myos maskaamattomana.

    Jos pooli olisi vain maskatussa vastauksessa, klientti tarvitsisi kaksi
    haaraa ja pinnat voisivat eriytya — sama vikaluokka josta tama korjaus
    lahti liikkeelle.
    """
    monkeypatch.setenv("PREMIUM_ENFORCE", "off")
    d = client.get("/api/fantasy/xp").json()
    assert d["meta"].get("masked") is not True
    assert _pos_counts(d.get("pool") or {}) and all(
        _pos_counts(d["pool"]).get(p, 0) >= n for p, n in DRAFT_SLOTS.items())


def test_pool_lisays_nosti_etag_skeemaversiota():
    """Serve-time-kentta ilman skeemanostoa jaisi 304:n taakse.

    Muisti `serve-time-kentta-ei-invalidoi-etagia`: `generated_at` ei liiku
    kun kentta lisataan servaushetkella, joten ehdollinen pyynto validoisi
    vanhan vastauksen ja valitsin olisi tyhja tasan niilla kayttajilla joilla
    vastaus on jo valimuistissa.
    """
    # nosta AINA kun pooliin/vastaukseen tulee serve-time-kentta.
    # s6 (14.8): `why.lang` = toteutunut kieli (WHY-I18N). Tama lukitustesti
    # puri kuten kuuluu — se on ainoa asia joka pakottaa nostamaan version
    # kasin, ja se loysi noston puuttumisen ennen kuin kayttajat loysivat
    # tyhjan kentan valimuistista.
    # s7 (20.8): `why.driver_facts` + `drivers` kapenee kolmeen
    # (SHARE-CARD-WHY-EMPHASIS). Ja taas testi puri: skeemanosto tehtiin
    # patchissa jonka verifiointi ajoi vain why/xp-testit, ja tama vakio
    # jai nostamatta kunnes koko setti ajettiin.
    # s8 (16.9): `xmins_prev` + `xmins_delta` (MINUUTTITRENDI). Nama ovat
    # serve-time-kenttia joiden VERTAILUKOHTA vaihtuu ilman uutta projektiota:
    # kun uusi deadline-freeze ilmestyy (gw4 -> gw5), `generated_at` voi olla
    # sama ja luvut ovat eri. Testi puri KOLMANNEN kerran perakkain (s6, s7,
    # s8) — se on ainoa mekanismi joka pakottaa noston kasin.
    #
    # HUOM: skeemaversio erottaa kentan OLEMASSAOLON, ei sen ARVOA. Siksi
    # ETagiin lisattiin myos `mt<gw>` (vertailukohdan kierros); pelkka s8
    # olisi jattanyt sarakkeen nayttamaan edellisen kierroksen eroa uuden
    # freezen jalkeen. Ks. tests/test_xp_etag_parts.py.
    NYKYINEN = "s9"
    src = (API_DIR / "main.py").read_text(encoding="utf-8")
    assert f'schema = "{NYKYINEN}"' in src, (
        f"ETagin skeemaversio ei ole {NYKYINEN}. Jos lisasit pooliin kentan "
        "(XP_POOL_FIELDS) tai muun serve-time-kentan, nosta BOTH: "
        "api/main.py:n `schema` JA tama vakio. Jos et lisannyt, joku muu "
        "nosti version ja tama testi on jaljessa.")
    # Sidonta kenttajoukkoon: jos XP_POOL_FIELDS kasvaa mutta versio ei liiku,
    # yllaoleva assert kaatuu vasta jos joku muistaa paivittaa NYKYISEN.
    # Tama rivi tekee kytkennan nakyvaksi lukijalle: s4 = 5 kenttaa (draft),
    # s5 = 7 kenttaa (+ status/news ilmaista watchlistia varten).
    from api.premium import XP_POOL_FIELDS
    assert len(XP_POOL_FIELDS) == 7, (
        "XP_POOL_FIELDS muuttui — tarkista ETagin skeemaversio ja paivita "
        "tama luku samassa committissa")


# --- DEFCON-LEADERS-PALVELINRAJA (17.9) ------------------------------------
#
# Maskaus todennetaan AJAMALLA molemmilla basiksilla (recent + season),
# koska reitilla on kaksi paluupolkua ja vanha muoto palautti kummankin
# rankkerin tuloksen suoraan. Synteettinen data monkeypatchataan lukijoihin,
# jotta testi ei riipu repon artefaktin sisallosta (datasidonnainen testi
# punastuu ilman etta mikaan on rikki, ks. 12.9-raportti kohta 12) eika
# tyhjasta esikausiartefaktista (silloin mittaisimme tyhjaa vastausta).
#
# Erotteleva fikstuuri: LEADERS_N > FREE_LEADERS_ROWS, jotta vanha koodi
# (ei maskia) oikeasti lapaisisi "palauttaa rivit" -ehdon ja kaatuisi
# "tasan free_rows rivia" -ehtoon. Muuten exit-koodi ei todistaisi mekanismia.

LEADERS_N = 6


def _leaders_recent_fixture() -> dict:
    """rank_defcon_leaders-syote: jokaisella eri hit-rate -> jarjestys on
    yksikasitteinen, jolloin 'top 3 on sama kuin premiumin 3 ensimmaista'
    on aito vaite eika tasapelin sattumaa."""
    players = []
    for i in range(1, LEADERS_N + 1):
        hits = LEADERS_N - i  # P1 osuu 5/5, P6 0/5
        players.append({
            "id": i, "web_name": f"P{i}", "team_short": "TST", "pos": "DEF",
            "price": 5.0, "owned_pct": 1.0, "basis": "2025/26",
            "games_total": 5,
            "recent_games": [
                {"round": r + 1, "opp": "OPP", "venue": "H", "minutes": 90,
                 "xg": 0.1, "xa": 0.1, "xgi": 0.2,
                 "dc": 12 if r < hits else 3}
                for r in range(5)],
        })
    return {"meta": {"available": True, "basis_season": "2025/26",
                     "is_prev_season_basis": True,
                     "basis_label": "Based on 2025/26",
                     "generated_at": "2026-09-17T00:00:00"},
            "players": players}


def _leaders_season_fixture() -> dict:
    """rank_defcon_season-syote (per-GW-matriisin kausisummat)."""
    players = []
    for i in range(1, LEADERS_N + 1):
        hits = 30 - 4 * i
        players.append({
            "id": i, "code": 90000 + i, "web_name": f"P{i}",
            "team_short": "TST", "pos": "DEF", "price": 5.0, "owned_pct": 3.0,
            "threshold": 10, "games": 38, "hits": hits,
            "hit_rate": round(hits / 38, 3), "dc_points": hits * 2,
            "basis": "2025/26",
            "per_gw": [[g + 1, "OPP", "H", 90, 8] for g in range(38)],
        })
    return {"meta": {"available": True, "basis_season": "2025/26",
                     "basis_label": "Based on 2025/26",
                     "generated_at": "2026-09-17T00:00:00",
                     "n_players": LEADERS_N},
            "players": players}


@pytest.fixture()
def leaders_client(monkeypatch):
    """TestClient jonka defcon-lukijat palauttavat synteettisen datan.

    Reitti importoi lukijat kutsun sisalla (`from src.models.fpl_leaders
    import load_leaders, load_defcon_gw`), joten moduuliattribuutin
    monkeypatch osuu molempiin basiksiin ja myos /defcon-gw:hen.
    """
    import api.main as m
    import src.models.fpl_leaders as fl
    monkeypatch.setattr(fl, "load_leaders", _leaders_recent_fixture)
    monkeypatch.setattr(fl, "load_defcon_gw", _leaders_season_fixture)
    return TestClient(m.app)


_LEADERS_QUERIES = {
    "recent": "/api/fantasy/defcon-leaders?window=5&top_n=400",
    "season": "/api/fantasy/defcon-leaders?basis=season&top_n=400",
}


@pytest.mark.parametrize("basis", sorted(_LEADERS_QUERIES))
def test_defcon_leaders_masked_when_enforcement_on(leaders_client, monkeypatch,
                                                   basis):
    """Flagi paalla + ei tokenia -> tasan free_rows rivia + meta.masked.

    Rivit ovat palvelinjarjestyksen kolme ensimmaista (sama siivu jonka
    klientit leikkasivat itse) ja taysia.
    """
    from api.premium import FREE_LEADERS_ROWS

    monkeypatch.setenv("PREMIUM_ENFORCE", "off")
    full = leaders_client.get(_LEADERS_QUERIES[basis]).json()
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    r = leaders_client.get(_LEADERS_QUERIES[basis])
    assert r.status_code == 200
    d = r.json()
    assert d["meta"]["masked"] is True
    assert d["meta"]["free_rows"] == FREE_LEADERS_ROWS
    assert d["meta"]["total_rows"] == LEADERS_N
    assert len(d["players"]) == FREE_LEADERS_ROWS, (
        f"{basis}: anonyymi sai {len(d['players'])} rivia, ei "
        f"{FREE_LEADERS_ROWS} — 'Full DefCon leaderboard' vuotaa")
    assert ([p["id"] for p in d["players"]]
            == [p["id"] for p in full["players"][:FREE_LEADERS_ROWS]])
    for p in d["players"]:
        for field in ("web_name", "hit_rate_pct", "dc_per_game",
                      "defcon_points_window", "games", "price"):
            assert p.get(field) is not None, f"maskattu rivi menetti {field}"


@pytest.mark.parametrize("basis", sorted(_LEADERS_QUERIES))
def test_defcon_leaders_full_when_enforcement_off(leaders_client, monkeypatch,
                                                  basis):
    """NEGATIIVINEN KONTROLLI: flagi pois -> koko lista, ei maskilippua.

    Ilman tata edellinen lapaisisi myos silloin jos rankkeri antaisi aina
    vain kolme rivia — eli mittaisimme dataa emmeka maskia.
    """
    from api.premium import FREE_LEADERS_ROWS

    monkeypatch.setenv("PREMIUM_ENFORCE", "off")
    d = leaders_client.get(_LEADERS_QUERIES[basis]).json()
    assert d["meta"].get("masked") is not True
    assert "free_rows" not in d["meta"]
    assert len(d["players"]) == LEADERS_N > FREE_LEADERS_ROWS


def test_defcon_leaders_masked_for_invalid_token(leaders_client, monkeypatch):
    """Kelvoton token ei ohita gatea (fail-closed tunnistautumisessa)."""
    from api.premium import FREE_LEADERS_ROWS

    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    r = leaders_client.get(_LEADERS_QUERIES["season"],
                           headers={"Authorization": "Bearer ei-kelpaa"})
    assert r.status_code == 200
    assert len(r.json()["players"]) == FREE_LEADERS_ROWS


@pytest.mark.parametrize("basis", sorted(_LEADERS_QUERIES))
def test_defcon_leaders_full_for_premium_token_when_enforcement_on(
        leaders_client, monkeypatch, basis):
    """DoD 2: enforcement PAALLA + kelvollinen premium-token -> koko lista,
    ei maskilippua.

    Flagi-pois-kontrolli ei todista tata: siina is_premium_request palauttaa
    True ennen token-haaraa. Tassa token kulkee koko polun (verify ->
    profiili) kuten tuotannossa. Vaihe-invariantti: tulos on sama riippumatta
    siita onko GW1-GW3 ilmaisikkuna auki (ikkuna antaa True aiemmin, profiili
    myohemmin; kumpikin on premium).
    """
    import api.premium as prem
    from api.premium import FREE_LEADERS_ROWS

    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    monkeypatch.setattr(prem, "_verify_token_user_id", lambda t: "user-1")
    monkeypatch.setattr(prem, "_profile_is_premium", lambda uid: True)
    with prem._PREMIUM_CACHE_LOCK:
        prem._PREMIUM_CACHE.clear()
    try:
        r = leaders_client.get(_LEADERS_QUERIES[basis],
                               headers={"Authorization": "Bearer premium-ok"})
    finally:
        with prem._PREMIUM_CACHE_LOCK:
            prem._PREMIUM_CACHE.clear()
    assert r.status_code == 200
    d = r.json()
    assert d["meta"].get("masked") is not True, "premium sai maskatun listan"
    assert "free_rows" not in d["meta"]
    assert len(d["players"]) == LEADERS_N > FREE_LEADERS_ROWS


def test_defcon_gw_stays_free_when_enforcement_on(leaders_client, monkeypatch):
    """DoD 5: per-GW-matriisi pysyy ilmaisena (pelaajakortin DefCon-loki).

    Sama synteettinen data kuin season-basiksella: jos joku ulottaisi
    maskin lukijaan (load_defcon_gw) reitin sijaan, tama punastuisi.
    """
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    d = leaders_client.get("/api/fantasy/defcon-gw").json()
    assert "masked" not in d["meta"]
    assert len(d["players"]) == LEADERS_N


def test_defcon_player_stays_free_when_enforcement_on(leaders_client,
                                                      monkeypatch):
    """DoD 5: yhden pelaajan DefCon-loki pysyy ilmaisena."""
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    r = leaders_client.get("/api/fantasy/defcon/1?window=5")
    assert r.status_code == 200
    d = r.json()
    assert d.get("meta", {}).get("masked") is not True
    assert len(d["games"]) == 5


def test_partial_routes_declare_what_leaks():
    """Poikkeuslista perusteluineen (6a kohta 2): jokainen PARTIAL-reitti
    nimeaa PARTIAL_PREMIUM_KEYSissa mika osa vastauksesta on premiumia.

    PARTIAL ilman maaritelmaa on reitti jonka maskia kukaan ei ole paattanyt
    eika mikaan testi voi todentaa (17.9 asti defcon-leaders olisi voinut
    siirtya tanne pelkalla joukkorivilla). Maaritelma ilman reittia on
    vanhentunut rivi joka vartioi tyhjaa.
    """
    ilman_maaritelmaa = sorted(PARTIAL_EXPECTED - set(PARTIAL_PREMIUM_KEYS))
    ilman_reittia = sorted(set(PARTIAL_PREMIUM_KEYS) - PARTIAL_EXPECTED)
    assert not ilman_maaritelmaa and not ilman_reittia, (
        f"PARTIAL ilman premium-osan maaritelmaa: {ilman_maaritelmaa}; "
        f"maaritelma ilman PARTIAL-reittia: {ilman_reittia}")


@pytest.mark.parametrize("window_open", [True, False],
                         ids=["ikkuna-auki", "ikkuna-kiinni"])
@pytest.mark.parametrize("basis", sorted(_LEADERS_QUERIES))
def test_defcon_leaders_anonymous_masked_in_every_free_window_phase(
        leaders_client, monkeypatch, basis, window_open):
    """6a kohta 3: invariantti mitataan joka vaiheessa, ei nykyhetkessa.

    GW1-GW3 ilmaisikkuna (free_premium_window_active) antaa premiumin
    KIRJAUTUNEELLE ilman Supabase-hakua. Anonyymin on pysyttava maskattuna
    ikkunasta riippumatta: muuten "Full DefCon leaderboard" olisi kolme
    kierrosta kaudesta julkinen curlilla. Vaihe injektoidaan, ei lueta
    kellosta. Erotteleva kontrolli on seuraava testi.
    """
    import api.premium as prem
    from api.premium import FREE_LEADERS_ROWS

    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    monkeypatch.setattr(prem, "free_premium_window_active",
                        lambda *a, **k: window_open)
    d = leaders_client.get(_LEADERS_QUERIES[basis]).json()
    assert d["meta"]["masked"] is True
    assert d["meta"]["total_rows"] == LEADERS_N
    assert len(d["players"]) == FREE_LEADERS_ROWS, (
        f"{basis}, ikkuna {'auki' if window_open else 'kiinni'}: anonyymi "
        f"sai {len(d['players'])} rivia")


@pytest.mark.parametrize("window_open", [True, False],
                         ids=["ikkuna-auki", "ikkuna-kiinni"])
def test_defcon_leaders_signed_in_non_premium_follows_free_window(
        leaders_client, monkeypatch, window_open):
    """Erotteleva kontrolli edelliselle: vaihe VAIHTAA tuloksen
    kirjautuneelle ei-premiumille (ikkuna auki -> koko lista, kiinni ->
    maski). Ilman tata edellinen lapaisisi myos silloin jos monkeypatch
    osuisi nimeen jota polku ei lue, eli mittaisimme nykyhetkea."""
    import api.premium as prem
    from api.premium import FREE_LEADERS_ROWS

    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    monkeypatch.setattr(prem, "free_premium_window_active",
                        lambda *a, **k: window_open)
    monkeypatch.setattr(prem, "_verify_token_user_id", lambda t: "user-free")
    monkeypatch.setattr(prem, "_profile_is_premium", lambda uid: False)
    monkeypatch.setattr(prem, "_web_subscription_active", lambda uid: False)
    with prem._PREMIUM_CACHE_LOCK:
        prem._PREMIUM_CACHE.clear()
    try:
        d = leaders_client.get(
            _LEADERS_QUERIES["season"],
            headers={"Authorization": "Bearer free-user"}).json()
    finally:
        with prem._PREMIUM_CACHE_LOCK:
            prem._PREMIUM_CACHE.clear()
    if window_open:
        assert d["meta"].get("masked") is not True
        assert len(d["players"]) == LEADERS_N
    else:
        assert d["meta"]["masked"] is True
        assert len(d["players"]) == FREE_LEADERS_ROWS


# ---------------------------------------------------------------------------
# 20.9.2026: ILMAISEN ESIKATSELUN KOKO ON PAATOS, EI VAHINKO
# ---------------------------------------------------------------------------

#: Mita tuote antaa ilmaiseksi, lukuna. Arvo ja perustelu samassa paikassa.
#:
#: 🔴 MIKSI TAMA ON OLEMASSA. Kaikki olemassa olevat portit mittaavat maskin
#: OLEMASSAOLOA: "kutsuuko runko gatea", "onko rungossa mask_-funktio",
#: "kutistuuko payload". Yksikaan ei mittaa maskin KOKOA. Siksi ilmainen
#: esikatselu voi kasvaa rivi kerrallaan ilman etta mikaan punastuu - ja
#: se on tasan se muutos joka antaa tuotteen pois ilman etta kukaan paattaa
#: niin. Mitattu 18.9: `/api/fantasy/plan` oli luokiteltu GATEDiksi vaikka se
#: palauttaa anonyymille taysi rivin kapteenin nimineen, eli koko oli jo
#: kasvanut nollasta yhteen kenenkaan huomaamatta.
#:
#: Taman testin kaataminen EI ole vika. Se tarkoittaa etta joku muuttaa sita
#: mita tuote antaa ilmaiseksi, ja silloin luku muutetaan TASSA ja diffissa
#: nakyy paatos eika sivuvaikutus.
ILMAINEN_ESIKATSELU = {
    "FREE_XP_TEASER_N": (10, "/api/fantasy/xp: top-10 rivia"),
    "FREE_PLAN_GWS": (1, "/api/fantasy/plan: ensimmainen kierros"),
    "FREE_CHIP_WINDOWS": (3, "/api/fantasy/chip-ev: kolme ikkunaa"),
    "FREE_PLAN_CHAINS": (1, "/api/fantasy/plan-chains: yksi ketju"),
    "FREE_EDGE_CAPTAINS": (2, "/api/fantasy/edge: kaksi kapteenirivia"),
    "FREE_EDGE_DIFFERENTIALS": (2, "/api/fantasy/edge: kaksi differentiaalia"),
    "FREE_CAPTAIN_PICKS": (1, "/api/fantasy/captain: yksi valinta - sama "
                              "lupaus kuin myyntisivun 'with a captain pick'"),
    "FREE_REPLACEMENTS_ROWS": (1, "/api/fantasy/replacements: kohde + 1 rivi"),
    "FREE_EDGE_TEMPLATE_RISKS": (1, "/api/fantasy/edge: yksi template-riski"),
    "FREE_VALUE_ROWS": (3, "/api/fantasy/value: sama 3 rivia jonka "
                           "Value.svelte nayttaa"),
    "FREE_LEADERS_ROWS": (3, "/api/fantasy/defcon-leaders: top 3"),
    "FREE_COMPARE_ROWS": (0, "/api/fantasy/compare: nolla - molemmat klientit "
                             "piilottavat comparen ilmaiskayttajalta kokonaan"),
    # 22.9 PREDICT-API-MASK (PREDICT_MASK-lipun takana, oletus pois).
    "FREE_PARLAY_LEGS": (0, "/api/parlay: nolla - mobiilin ParlayScreen "
                            "palauttaa lukkonakyman ennen kutsua eika SPA:ssa "
                            "ole parlayta (tests/test_predict_mask.py)"),
}


def test_ilmaisen_esikatselun_koko_on_paatos_ei_vahinko():
    """Jokaisen ilmaisen esikatselun koko on pinnattu lukuna."""
    import api.premium as prem
    erot = []
    for nimi, (odotus, miksi) in sorted(ILMAINEN_ESIKATSELU.items()):
        arvo = getattr(prem, nimi, None)
        if arvo != odotus:
            erot.append(f"{nimi}: {arvo} (odotettu {odotus} - {miksi})")
    assert not erot, (
        "Ilmaisen esikatselun koko muuttui: " + "; ".join(erot) +
        ". Jos muutos on tarkoitettu, paivita ILMAINEN_ESIKATSELU samassa "
        "committissa - silloin diffissa nakyy paatos eika sivuvaikutus.")


def test_jokainen_free_vakio_on_pinnattu():
    """Negatiivinen kontrolli: uusi FREE_*-vakio ei paase ohi listan.

    Ilman tata ylla oleva testi vartioisi vain niita lukuja jotka joku
    muisti lisata, ja seuraava ilmainen esikatselu syntyisi vartioimatta -
    sama unohdusvika jonka lista on olemassa estamaan.
    """
    import re as _re
    lahde = (API_DIR / "premium.py").read_text(encoding="utf-8")
    loydetyt = set(_re.findall(r"^(FREE_[A-Z0-9_]+)\s*=\s*\d+\s*$",
                               lahde, flags=_re.M))
    vartioimatta = sorted(loydetyt - set(ILMAINEN_ESIKATSELU))
    assert not vartioimatta, (
        f"FREE_*-vakio ilman pinnia: {vartioimatta}. Lisaa se "
        "ILMAINEN_ESIKATSELU-listaan arvon JA perustelun kanssa.")


# --- COMPARE-PALVELINRAJA (18.9) -------------------------------------------
#
# 18.9-LOYDOS JOKA MUUTTI TAKSONOMIAA: GATED-luokka mittasi vain maskin
# OLEMASSAOLON. `test_gated_endpoints_actually_truncate` etsii rungosta
# merkkijonon "FREE_" tai "mask_" — se pysyy vihreana vaikka maski KASVAISI
# kymmenesta rivista viiteensataan, koska merkkijono on yha siella. Sama
# sokeus kuin "gate on paikallaan" -tarkistuksella ennen 11.8:aa: luokka on
# oikea, koko ei ole kenenkaan vastuulla.
#
# Alla oleva taulukko on poikkeuslista perusteluineen (saanto 6a kohta 2):
# jokainen GATED-reitti nimeaa VAKION joka rajaa sen ilmaisosuuden JA sen
# arvon. Uusi gatettu reitti ei paase listalle vahingossa (testi kaatuu ja
# kirjoittaja joutuu paattamaan koon), eika vakion kasvattaminen voi enaa
# tapahtua hiljaa: myyntirajan siirto nakyy diffissa kahdessa paikassa.
#
# `None` = reitti ei typista riveja vaan pudottaa lohkoja (wildcard-plan);
# sen maskin muoto on lukittu omassa testissaan, ei rivimaaralla.
GATED_MASK_SIZE: dict[str, tuple[str, int] | None] = {
    "/api/fantasy/xp": ("FREE_XP_TEASER_N", 10),
    "/api/fantasy/xp.csv": ("FREE_XP_TEASER_N", 10),
    # /api/fantasy/plan siirtyi 20.9 PARTIALiin (mitattu kaytos), joten se ei
    # ole enaa tassa taulukossa; sen koko on pinnattu ILMAINEN_ESIKATSELUssa.
    "/api/fantasy/chip-ev": ("FREE_CHIP_WINDOWS", 3),
    "/api/fantasy/plan-chains": ("FREE_PLAN_CHAINS", 1),
    "/api/fantasy/edge": ("FREE_EDGE_CAPTAINS", 2),
    "/api/fantasy/replacements": ("FREE_REPLACEMENTS_ROWS", 1),
    "/api/fantasy/value": ("FREE_VALUE_ROWS", 3),
    # 18.9: nolla, ja se on mitattu klienteista eika valittu — perustelu on
    # kirjoitettu auki api/premium.py:hyn vakion viereen.
    "/api/fantasy/compare": ("FREE_COMPARE_ROWS", 0),
    "/api/fantasy/wildcard-plan": None,
}


def test_gated_routes_declare_their_mask_size():
    """Jokainen GATED-reitti on taulukossa, ja taulukko vastaa koodia.

    Tama on se portti jota ei ollut: luokka oli paatetty, koko ei.
    """
    import api.premium as prem

    puuttuu = sorted(GATED_EXPECTED - set(GATED_MASK_SIZE))
    ylimaarainen = sorted(set(GATED_MASK_SIZE) - GATED_EXPECTED)
    assert not puuttuu, (
        f"GATED-reitti ilman ilmoitettua maskin kokoa: {puuttuu}. Paata "
        "montako rivia free saa ja kirjoita se GATED_MASK_SIZEen.")
    assert not ylimaarainen, (
        f"Maskin koko ilmoitettu reitille joka ei ole GATED: {ylimaarainen}.")

    for route, spec in sorted(GATED_MASK_SIZE.items(),
                              key=lambda kv: kv[0]):
        if spec is None:
            continue
        nimi, odotettu = spec
        todellinen = getattr(prem, nimi, None)
        assert todellinen == odotettu, (
            f"{route}: {nimi} on {todellinen}, taulukko sanoo {odotettu}. "
            "Myyntiraja siirtyi — paivita molemmat samassa committissa tai "
            "peru muutos.")


# Erotteleva fikstuuri: kaksi TAYTTA rivia + verdict, eli tasan se muoto
# jonka tuotanto palautti anonyymille 18.9. Vanha koodi (ei maskia)
# lapaisisi "vastaa 200" -ehdon ja kaatuisi "nolla rivia" -ehtoon, joten
# exit-koodi todistaa mekanismin eika pelkkaa importtia.
_COMPARE_META = {
    "generated_at": "2026-09-18T13:40:00+00:00", "horizon_gw": 6,
    "defcon_basis_season": "2025/26", "defcon_available": True,
    "unprojected": ["P426"],
    "unprojected_note": "P426 is outside the projection.",
}
_COMPARE_ROW = {
    "projected": True, "excluded_reason": None, "status": "a",
    "team_short": "MCI", "pos": "FWD", "price": 15.6, "owned_pct": 73.2,
    "xp_per_gw": 6.41, "xp_horizon_total": 38.49, "p_start": 0.925,
    "components": {"goals": 3.06}, "components_gw": 5,
}
_COMPARE_VERDICT = {
    "pick": {"id": 411, "web_name": "P411"},
    "margin_xp_horizon": 3.49,
    "text": "P411 projects 3.49 xP more than P426 over the horizon.",
}
_COMPARE_URL = "/api/fantasy/compare?players=411,426"
_COMPARE_URL_4 = "/api/fantasy/compare?players=411,426,351,15"


@pytest.fixture()
def compare_client(monkeypatch):
    """TestClient jonka compare_players palauttaa synteettisen vertailun.

    Reitti importoi sen kutsun sisalla (`from src.models.fpl_planner import
    compare_players`), joten moduuliattribuutin monkeypatch osuu. Syy
    synteettiseen dataan: oikea vertailu lataa projektioartefaktin, jolloin
    testi mittaisi repon datan sisaltoa eika maskia (esikaudella tyhjaa).
    """
    import api.main as m
    import src.models.fpl_planner as fp

    def _fake(player_ids, squad=None):
        rows = [dict(_COMPARE_ROW, id=pid, web_name=f"P{pid}")
                for pid in player_ids]
        return {"meta": dict(_COMPARE_META), "players": rows,
                "verdict": dict(_COMPARE_VERDICT)}

    monkeypatch.setattr(fp, "compare_players", _fake)
    return TestClient(m.app)


@pytest.mark.parametrize("url,n", [(_COMPARE_URL, 2), (_COMPARE_URL_4, 4)],
                         ids=["kaksi-pelaajaa", "nelja-pelaajaa"])
def test_compare_masked_when_enforcement_on(compare_client, monkeypatch,
                                            url, n):
    """Flagi paalla + ei tokenia -> nolla rivia, ei verdiktia, meta kertoo.

    Molemmat paatepisteet (2 ja 4 pelaajaa) mitataan: maski ei saa riippua
    siita montako pelaajaa kysyttiin.
    """
    from api.premium import FREE_COMPARE_ROWS

    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    r = compare_client.get(url)
    assert r.status_code == 200
    d = r.json()
    assert d["meta"]["masked"] is True
    assert d["meta"]["free_rows"] == FREE_COMPARE_ROWS
    assert d["meta"]["total_rows"] == n
    assert len(d["players"]) == FREE_COMPARE_ROWS, (
        f"anonyymi sai {len(d['players'])} vertailurivia, ei "
        f"{FREE_COMPARE_ROWS} — player compare vuotaa")
    assert d["verdict"] is None, "suora kanta vuoti ilmaiselle"
    assert isinstance(d["players"], list) and isinstance(d["meta"], dict), (
        "maski rikkoi vastauksen muodon — klientti ei voi lukea meta.maskedia")


def test_compare_mask_ei_vuoda_pelaajien_nimia(compare_client, monkeypatch):
    """Maskattu vastaus ei saa nimeta yhtaan pyydettya pelaajaa.

    `meta.unprojected` on NIMILISTA ja `verdict.text` sisaltaa molemmat
    nimet. Pelkka `players`-listan typistys jattaisi ne nakyviin, eli
    vertailun lopputulos ("P411 projects 3.49 xP more") olisi yha
    luettavissa ilman premiumia — maski nayttaisi toimivan ja myisi silti
    sen mita tyokalu myy.
    """
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    body = compare_client.get(_COMPARE_URL).text
    vuoti = [osa for osa in ("P411", "P426", "3.49", "38.49")
             if osa in body]
    assert not vuoti, f"maskattu compare-vastaus sisaltaa: {vuoti}"


@pytest.mark.parametrize("url,n", [(_COMPARE_URL, 2), (_COMPARE_URL_4, 4)],
                         ids=["kaksi-pelaajaa", "nelja-pelaajaa"])
def test_compare_full_when_enforcement_off(compare_client, monkeypatch,
                                           url, n):
    """NEGATIIVINEN KONTROLLI: flagi pois -> taydet rivit + verdict.

    Ilman tata edellinen lapaisisi myos silloin jos compare palauttaisi
    aina nolla rivia — eli mittaisimme tyhjaa dataa emmeka maskia.
    """
    monkeypatch.setenv("PREMIUM_ENFORCE", "off")
    d = compare_client.get(url).json()
    assert d["meta"].get("masked") is not True
    assert "free_rows" not in d["meta"]
    assert len(d["players"]) == n
    assert d["verdict"] is not None
    assert d["verdict"]["text"]


def test_compare_masked_for_invalid_token(compare_client, monkeypatch):
    """Kelvoton token ei ohita gatea (fail-closed tunnistautumisessa)."""
    from api.premium import FREE_COMPARE_ROWS

    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    r = compare_client.get(_COMPARE_URL,
                           headers={"Authorization": "Bearer ei-kelpaa"})
    assert r.status_code == 200
    assert len(r.json()["players"]) == FREE_COMPARE_ROWS


@pytest.mark.parametrize("url,n", [(_COMPARE_URL, 2), (_COMPARE_URL_4, 4)],
                         ids=["kaksi-pelaajaa", "nelja-pelaajaa"])
def test_compare_full_for_premium_token_when_enforcement_on(
        compare_client, monkeypatch, url, n):
    """Enforcement PAALLA + kelvollinen premium-token -> taysi vertailu.

    Flagi-pois-kontrolli ei todista tata: siina is_premium_request palauttaa
    True ennen token-haaraa. Tassa token kulkee koko polun kuten
    tuotannossa — eli maksava kayttaja saa sen mista maksaa.
    """
    import api.premium as prem

    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    monkeypatch.setattr(prem, "_verify_token_user_id", lambda t: "user-1")
    monkeypatch.setattr(prem, "_profile_is_premium", lambda uid: True)
    with prem._PREMIUM_CACHE_LOCK:
        prem._PREMIUM_CACHE.clear()
    try:
        r = compare_client.get(url,
                               headers={"Authorization": "Bearer premium-ok"})
    finally:
        with prem._PREMIUM_CACHE_LOCK:
            prem._PREMIUM_CACHE.clear()
    d = r.json()
    assert d["meta"].get("masked") is not True, "premium sai maskatun vertailun"
    assert len(d["players"]) == n
    assert d["verdict"] is not None


def test_compare_tuntematon_id_ei_ohita_maskia(compare_client, monkeypatch):
    """Vaihe: kysely jonka rivit jaavat vajaiksi (tuntematon / sivussa oleva
    pelaaja) on yha maskattu.

    Ilman tata `len(players) == 0` voisi tarkoittaa kahta eri asiaa, ja
    klientti joka paattelee lukon listan pituudesta nayttaisi lukon myos
    premiumille jonka kysely ei tuottanut riveja. Siksi klienttien on
    luettava `meta.masked`, ja siksi maski asettaa sen myos talla polulla.
    """
    import src.models.fpl_planner as fp

    monkeypatch.setattr(fp, "compare_players",
                        lambda ids, squad=None: {
                            "meta": dict(_COMPARE_META),
                            "players": [],
                            "verdict": {"pick": None,
                                        "margin_xp_horizon": None,
                                        "text": "Not enough data."}})
    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    d = compare_client.get(_COMPARE_URL).json()
    assert d["meta"]["masked"] is True
    assert d["meta"]["total_rows"] == 0
    assert d["verdict"] is None


@pytest.mark.parametrize("window_open", [True, False],
                         ids=["ikkuna-auki", "ikkuna-kiinni"])
def test_compare_anonymous_masked_in_every_free_window_phase(
        compare_client, monkeypatch, window_open):
    """6a kohta 3: invariantti mitataan joka vaiheessa, ei nykyhetkessa.

    GW1-GW3 ilmaisikkuna antaa premiumin KIRJAUTUNEELLE ilman
    Supabase-hakua. Anonyymin on pysyttava maskattuna ikkunasta riippumatta.
    Vaihe injektoidaan, ei lueta kellosta (ikkuna on tanaan kiinni, joten
    kellosta luettuna tama testi mittaisi vain toista haaraa). Erotteleva
    kontrolli on seuraava testi.
    """
    import api.premium as prem
    from api.premium import FREE_COMPARE_ROWS

    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    monkeypatch.setattr(prem, "free_premium_window_active",
                        lambda *a, **k: window_open)
    d = compare_client.get(_COMPARE_URL).json()
    assert d["meta"]["masked"] is True
    assert len(d["players"]) == FREE_COMPARE_ROWS
    assert d["verdict"] is None


@pytest.mark.parametrize("window_open", [True, False],
                         ids=["ikkuna-auki", "ikkuna-kiinni"])
def test_compare_signed_in_non_premium_follows_free_window(
        compare_client, monkeypatch, window_open):
    """Erotteleva kontrolli edelliselle: vaihe VAIHTAA tuloksen
    kirjautuneelle ei-premiumille. Ilman tata edellinen lapaisisi myos
    silloin jos monkeypatch osuisi nimeen jota polku ei lue."""
    import api.premium as prem
    from api.premium import FREE_COMPARE_ROWS

    monkeypatch.setenv("PREMIUM_ENFORCE", "on")
    monkeypatch.setattr(prem, "free_premium_window_active",
                        lambda *a, **k: window_open)
    monkeypatch.setattr(prem, "_verify_token_user_id", lambda t: "user-free")
    monkeypatch.setattr(prem, "_profile_is_premium", lambda uid: False)
    monkeypatch.setattr(prem, "_web_subscription_active", lambda uid: False)
    with prem._PREMIUM_CACHE_LOCK:
        prem._PREMIUM_CACHE.clear()
    try:
        d = compare_client.get(
            _COMPARE_URL,
            headers={"Authorization": "Bearer free-user"}).json()
    finally:
        with prem._PREMIUM_CACHE_LOCK:
            prem._PREMIUM_CACHE.clear()
    if window_open:
        assert d["meta"].get("masked") is not True
        assert len(d["players"]) == 2
    else:
        assert d["meta"]["masked"] is True
        assert len(d["players"]) == FREE_COMPARE_ROWS
