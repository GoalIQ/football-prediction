"""Jakokortin luvut on oltava samat kuin ilmaispinnalla.

MIKSI TAMA ON OLEMASSA (17.8.2026). `card_gw_outlook` luki
`fpl_cs_fdr.json`:aa, mutta `goaliq.app/fpl` servaa
`fpl_projections_phase0.json`:aa. Ne ovat eri mielta, koska cs_fdr EI aja
`fpl_context.fixture_adjustments`-kerrosta: nousijan sarja-avaus kotona jaa
korjaamatta, ja vastustajan CS-% yliarvioituu. GW1:ssa ero oli MUN 41 % vs
31,2 % ja SUN 36 % vs 26,9 % — eli kortti olisi vaittanyt Sunderlandia
kolmanneksi kun sivu sanoo seitsemas.

Vika oli hiljainen tasan siksi etta MOLEMMISSA tiedostoissa on samat
kentannimet (`xg_home`, `cs_home_pct`, `home_short`). Vaara lahde ei
kaatanut mitaan, se vain tuotti eri luvut. Siksi portti vertaa ARVOJA eika
tarkista etta lataus onnistui.

Portti on jakopintakohtainen: se ei valita kumpi malli on oikeassa, vaan
etta jaettu kuva ja tarkistuspinta sanovat saman asian. Lukija joka klikkaa
linkkia ei saa nahda eri lukua kuin kuvassa.
"""
from __future__ import annotations

import json

import pytest

import config

PAGE_SOURCE = "fpl_projections_phase0.json"


def _page_doc() -> dict:
    path = config.DATA_DIR / PAGE_SOURCE
    if not path.exists():
        pytest.skip(f"{PAGE_SOURCE} puuttuu (ei generoitu tassa ymparistossa)")
    return json.loads(path.read_text(encoding="utf-8"))


def _ajankohtainen_gw() -> int:
    """Kierros jonka SIVU nayttaa — sama lukija kuin sivulla.

    🔴 Testi kaatui 25.8 kun FPL vihdoin merkitsi GW1:n ottelut finishediksi
    ja builderi pudotti pelatun kierroksen projektioista: `gw=1` ei enaa
    loytynyt tiedostosta. Kovakoodattu kierrosnumero vanhenee joka viikko, ja
    portti joka vanhenee itsestaan on huonompi kuin ei porttia - se punaisee
    ilman etta mikaan on rikki, ja opettaa ohittamaan sen.

    🔴 JA SITTEN SE KAATUI UUDELLEEN 12.9 klo 12:30, ERI SYYSTA (mitattu).
    Tama funktio luki `actionable_gameweek`ia (= GW5 heti deadlinen jalkeen)
    kun sivu lukee `display_gameweek`ia (= GW4 niin kauan kuin GW4:n ottelut
    ovat kesken). Portti vertasi siis GW5:n korttia GW4:n sivuun ja ilmoitti
    kaikki 20 ottelua "puuttuvina". Sivu oli oikeassa koko ajan: FPL:n GW4 on
    SUN-ARS, LEE-NEW, LIV-FUL, COV-BHA... ja juuri ne olivat sivulla.

    Ironia on kirjattava: tama on TASAN se vika jota tama tiedosto vartioi —
    sama kysymys vastattu eri saannolla kahdessa paikassa. `fpl_gameweek`in
    docstring sanoo etta vastaus on "nyt yhdessa paikassa", mutta siina
    moduulissa on kolme funktiota, ja portti valitsi niista eri kuin pinta.
    Yksi lukija tarkoittaa saman FUNKTION, ei saman moduulin.
    """
    import json as _j
    from pathlib import Path as _P
    doc = _j.loads((_P(__file__).resolve().parents[1] / "data"
                    / "fpl_projections_phase0.json").read_text(encoding="utf-8"))
    from src.models.fpl_gameweek import display_gameweek
    gws = sorted({f["gameweek"] for f in doc["fixtures"] if f.get("gameweek")})
    gw = display_gameweek(doc.get("meta") or {}, doc.get("fixtures") or [])
    if gw in gws:
        return gw
    return gws[0] if gws else 1


def _card_spec(gw: int | None = None):
    if gw is None:
        gw = _ajankohtainen_gw()
    from scripts.gen_share_card import card_gw_outlook

    class _Args:
        pass

    a = _Args()
    a.gw = gw
    return card_gw_outlook(a)


def test_card_clean_sheet_matches_team_block_on_the_page():
    """Kortin jokainen CS-luku loytyy sivun omasta joukkuelohkosta samana.

    Sivun joukkuelohko (`teams[].fixtures[]`) on se mita lukija nakee
    taulukossa. Vertaa siihen eika fixtures-lohkoon: jos ne kaksi ajautuvat
    erilleen, tama portti huutaa siita myos.
    """
    doc = _page_doc()
    by_name = {t["name"]: t for t in doc["teams"]}
    spec = _card_spec()

    erot = []
    for row in spec["cs"]:
        team = by_name.get(row["team"])
        assert team is not None, f"{row['team']} ei ole sivun joukkuelistalla"
        gw1 = [f for f in team["fixtures"] if f["gw"] == spec["gw"]]
        assert gw1, f"{row['team']}: ei GW{spec['gw']}-fixturea sivulla"
        sivu = gw1[0].get("cs_pct")
        if sivu is None or abs(float(sivu) - float(row["cs"])) > 0.05:
            erot.append(f"{row['team']}: kortti {row['cs']} vs sivu {sivu}")

    assert not erot, "kortti ja ilmaispinta eri mielta:\n  " + "\n  ".join(erot)


def test_card_ranking_matches_the_page_ranking():
    """Jarjestys on oma vaite: kortti sanoo 'kolmas', ja lukija laskee sen.

    Pelkka arvovertailu ei riita — jos kortti ottaisi oikeat luvut mutta
    lajittelisi ne eri joukosta (esim. eri GW), rivit tasmaisivat mutta
    sijaluvut eivat.
    """
    doc = _page_doc()
    spec = _card_spec()
    gw = spec["gw"]

    sivun_jarjestys = sorted(
        (
            (t["name"], f["cs_pct"])
            for t in doc["teams"]
            for f in t["fixtures"]
            if f["gw"] == gw and f.get("cs_pct") is not None
        ),
        key=lambda x: -x[1],
    )
    n = len(spec["cs"])
    # Tasapelit puretaan eri jarjestyksessa eika kumpikaan ole vaarassa:
    # GW1:ssa Ipswich ja Nottingham Forest ovat molemmat 25,4. Vertaa siksi
    # ARVOSARJAA (joka kantaa sijaluvun) ja NIMIJOUKKOA erikseen, ei
    # nimilistaa jarjestyksessa — muuten portti huutaisi tasapeleista
    # ikuisesti ja se opetettaisiin ohittamaan.
    odotetut_arvot = [round(v, 4) for _, v in sivun_jarjestys[:n]]
    saadut_arvot = [round(float(r["cs"]), 4) for r in spec["cs"]]
    assert saadut_arvot == odotetut_arvot, (
        f"eri arvosarja:\n  kortti {saadut_arvot}\n  sivu   {odotetut_arvot}"
    )

    odotetut_nimet = {n_ for n_, _ in sivun_jarjestys[:n]}
    saadut_nimet = {r["team"] for r in spec["cs"]}
    assert saadut_nimet == odotetut_nimet, (
        f"eri joukkueet:\n  vain kortissa {saadut_nimet - odotetut_nimet}"
        f"\n  vain sivulla  {odotetut_nimet - saadut_nimet}"
    )


def test_negative_control_wrong_source_is_caught():
    """Negatiivinen kontrolli: portin on KAADUTTAVA vanhalla lahteella.

    Ilman tata testi lapaisisi myos silloin jos vertailu olisi tautologinen
    (esim. jos molemmat puolet lukisivat vahingossa samaa tiedostoa).
    """
    cs_fdr = config.DATA_DIR / "fpl_cs_fdr.json"
    if not cs_fdr.exists():
        pytest.skip("fpl_cs_fdr.json puuttuu")

    doc = _page_doc()
    vanha = json.loads(cs_fdr.read_text(encoding="utf-8"))
    gw = _card_spec()["gw"]

    # LIITOS OTTELUAJALLE, EI NIMELLE. Kaksi aiempaa versiota lapaisi
    # TYHJANA, kumpikin eri syysta:
    #   1. vertasi vain cs_home_pct:ta — GW1:n erot ovat MUN @ Hull ja
    #      SUN @ Ipswich eli VIERASjoukkueissa
    #   2. liitti nimella — cs_fdr sanoo "Hull City", phase0 "Hull", ja
    #      nimet eroavat tasan niissa otteluissa joissa luvut eroavat
    # Yhteinen vika ei ollut kumpikaan yksityiskohta vaan se, ettei portti
    # huomannut mittaavansa NOLLAA rivia. Siksi alla vaaditaan erikseen
    # etta liitos osui — tyhja vertailu on nyt kaatuva tulos eika hiljainen
    # lapimeno.
    sivu = {
        (f["kickoff_ms"], side): f[f"cs_{side}_pct"]
        for f in doc["fixtures"]
        if f["gameweek"] == gw
        for side in ("home", "away")
    }
    parit = [
        (f, side)
        for f in vanha.get("fixtures", [])
        if f.get("gameweek") == gw and (f.get("kickoff_ms"), "home") in sivu
        for side in ("home", "away")
    ]
    assert len(parit) >= 16, (
        f"liitos osui vain {len(parit)} riviin (odotus >=16 eli 8+ ottelua). "
        "Kontrolli ei mittaa mitaan — korjaa liitosavain, ala loysenna tata."
    )

    poikkeavat = [
        f"{f['home']} vs {f['away']} ({side}): "
        f"vanha {f[f'cs_{side}_pct']} / sivu {sivu[(f['kickoff_ms'], side)]}"
        for f, side in parit
        if abs(
            float(f[f"cs_{side}_pct"])
            - float(sivu[(f["kickoff_ms"], side)])
        )
        > 0.05
    ]
    assert poikkeavat, (
        "vanha lahde ei enaa eroa sivusta — jos cs_fdr on korjattu ajamaan "
        "fixture_adjustments, tama kontrolli on paivitettava, mutta ala poista "
        "sita: se on ainoa todiste etta yla olevat portit mittaavat jotain."
    )

# ---------------------------------------------------------------------------
# 10.9 FPL-SIVU-OTTELUIDEN-XG: kortin ottelurivin maalit on loydyttava sivun
# HTML:sta, ei JSONista. Portti 9.9 mittasi ettei projisoituja maaleja ollut
# millaan ihmisluettavalla ilmaissivulla vaikka kortti nayttaa niita.
# ---------------------------------------------------------------------------
def _page_html() -> str:
    """Sama polku kuin CI:n bake: build_context + cs_table_html artefaktista."""
    import config as _cfg
    from scripts import build_fpl_page as bfp
    acc_path = _cfg.DATA_DIR / "accuracy.json"
    if not acc_path.exists():
        pytest.skip("accuracy.json puuttuu")
    acc = json.loads(acc_path.read_text(encoding="utf-8"))
    c = bfp.build_context(_page_doc(), acc)
    return bfp.cs_table_html(c)


def test_card_fixture_goals_are_readable_on_the_page():
    spec = _card_spec()
    html = _page_html()
    puuttuu = []
    for f in spec["fixtures"]:
        # Kortti: "AVL 1.61 - 1.41 NFO". Sivu: kotijoukkueen rivilla
        # "projected goals AVL 1.61 v NFO 1.41" ja vierasjoukkueen rivilla
        # "projected goals NFO 1.41 v AVL 1.61" - luvut JA lyhenteet.
        hs, as_ = f["home_short"], f["away_short"]
        koti = f'projected goals<br>{hs} {f["xg_home"]:.2f} v {as_} {f["xg_away"]:.2f}'
        vieras = f'projected goals<br>{as_} {f["xg_away"]:.2f} v {hs} {f["xg_home"]:.2f}'
        if koti not in html:
            puuttuu.append(f'{f["home"]}: "{koti}"')
        if vieras not in html:
            puuttuu.append(f'{f["away"]}: "{vieras}"')
    assert not puuttuu, "kortin maaliluvut eivat ole sivulla:\n  " + "\n  ".join(puuttuu)


def test_card_goals_column_matches_the_page_values():
    """Kortin PROJECTED GOALS -sarake (top 10 xg) on sama luku kuin sivun rivi."""
    spec = _card_spec()
    html = _page_html()
    for r in spec["goals"]:
        assert f'{r["short"]} {r["xg"]:.2f} v ' in html, (
            f'{r["team"]} {r["xg"]:.2f} ei ole sivulla')


def test_negative_control_goals_mismatch_is_caught(monkeypatch):
    """Portin on kaaduttava jos sivu ja kortti lukisivat eri lukua."""
    from scripts import build_fpl_page as bfp
    orig = bfp.cs_table_html

    def tampered(c):
        for row in c["cs_rows"]:
            if row.get("xg_for") is not None:
                row["xg_for"] = round(row["xg_for"] + 0.5, 3)
        return orig(c)

    monkeypatch.setattr(bfp, "cs_table_html", tampered)
    with pytest.raises(AssertionError):
        test_card_fixture_goals_are_readable_on_the_page()


def _fx(ko, home, away, xh, xa):
    return {"gameweek": 4, "kickoff_ms": ko, "home": home, "away": away,
            "home_short": home[:3].upper(), "away_short": away[:3].upper(),
            "xg_home": xh, "xg_away": xa}


def test_double_gameweek_pairs_goals_with_the_first_fixture():
    """DGW: joukkueen rivi nayttaa ottelun 1 vastustajan JA ottelun 1 maalit.
    Nimiavain olisi antanut ottelun 2 maalit (portti 10.9). Testataan
    lukijaa suoraan: build_context kaataa DGW:n tarkoituksella (FDR-GRID-DGW)."""
    from scripts import build_fpl_page as bfp
    idx = bfp.match_goals_index(
        [_fx(100, "Arsenal", "Sunderland", 1.64, 0.67),
         _fx(200, "Everton", "Arsenal", 0.90, 1.80)], 4)
    first = {"gw": 4, "opponent": "Sunderland", "kickoff_ms": 100}
    second = {"gw": 4, "opponent": "Everton", "kickoff_ms": 200}
    assert bfp.match_goals_for(idx, "Arsenal", first) == (1.64, 0.67, "ARS", "SUN")
    assert bfp.match_goals_for(idx, "Arsenal", second) == (1.80, 0.90, "ARS", "EVE")
    assert bfp.match_goals_for(idx, "Everton", {"gw": 4, "opponent": "Arsenal",
                                                "kickoff_ms": 200}) == (0.90, 1.80, "EVE", "ARS")
    # vaara kierros ei indeksoidu
    assert bfp.match_goals_index([{**_fx(100, "A", "B", 1, 1), "gameweek": 5}], 4) == {}


def test_blank_gameweek_row_has_no_goals_and_caption_does_not_promise_them(monkeypatch):
    """BGW / epasynkka: joukkuelohko sanoo ottelu, fixtures-lohko ei ->
    ei alarivia, eika caption lupaa alarivia."""
    from scripts import build_fpl_page as bfp
    idx = bfp.match_goals_index([_fx(100, "Arsenal", "Sunderland", 1.64, 0.67)], 4)
    assert bfp.match_goals_for(idx, "Everton", {"opponent": "Fulham", "kickoff_ms": 300}) \
        == (None, None, None, None)

    def row(team, opp, venue, goals):
        xf, xa, sf, sa = goals
        return {"team": team, "cs_pct": 30.0, "opponent": opp, "venue": venue, "fdr": 3,
                "run_cs_pct": 30.0, "run_n": 6, "xg_for": xf, "xg_against": xa,
                "short_for": sf, "short_against": sa}
    rows = [row("Arsenal", "Sunderland", "H", (1.64, 0.67, "ARS", "SUN")),
            row("Everton", "Fulham", "H", (None, None, None, None))]
    monkeypatch.setattr(bfp, "_turnover_by_model_team",
                        lambda: {bfp.map_name("Arsenal"): {"minutes_churn_pct": 5.0}})
    c = {"cs_rows": rows, "next_gw": 4, "season": "2026/27"}
    html = bfp.cs_table_html(c)
    assert "projected goals<br>ARS 1.64 v SUN 0.67" in html
    assert html.count("projected goals") == 1
    assert "Projected goals are" not in html, "caption lupaa alarivia jota Evertonilla ei ole"
    # ja kun kaikilla on alarivi, caption saa luvata sen
    rows[1].update({"xg_for": 1.1, "xg_against": 1.2, "short_for": "EVE", "short_against": "FUL"})
    assert "Projected goals are" in bfp.cs_table_html(c)


# ---------------------------------------------------------------------------
# 10.9 XP-AJURIT-ILMAISPINNALLE: xP-kortin todiste == sivun alarivi
# ---------------------------------------------------------------------------
def _xp_card_spec():
    from scripts.gen_share_card import card_xp

    class _A:
        gw = None
        top = 20
    try:
        return card_xp(_A())
    except SystemExit as e:
        pytest.skip(f"card_xp: {e}")


def _rows_by_name_team(html: str) -> dict[tuple[str, str], str]:
    """(web_name, team_short) -> sen <tr>:n sisalto. Rivisidottu, koska
    "on penalties" esiintyy 15 kertaa ja koko osion substring-osuma olisi
    sokea vaaralle parille (muisti: gate-substring-osuma-on-sokea)."""
    import re as _re
    out = {}
    for tr in _re.findall(r"<tr>(.*?)</tr>", html, flags=_re.S):
        m = _re.search(r"<td>([^<]+)", tr)
        t = _re.search(r'<span>([A-Z]{3})</span>', tr)
        if m and t:
            out[(m.group(1).strip(), t.group(1))] = tr
    return out


def test_xp_card_fact_is_on_the_players_own_row():
    """Kortin "on penalties" / "ARS 51% clean sheet chance" on SAMAN pelaajan
    rivilla sivulla, sanatarkasti. Molemmat lukevat fpl_why_drivers.fact_text."""
    import config as _cfg
    from html import escape as _esc
    from scripts import build_fpl_longtail as lt
    spec = _xp_card_spec()
    xp = json.loads((_cfg.DATA_DIR / "fpl_xp_projections.json").read_text(encoding="utf-8"))
    html = lt._gw_xp_section(xp)
    rows = _rows_by_name_team(html)
    assert len(rows) >= len(spec["rows"]) - 2, "rivien poiminta epaonnistui"
    puuttuu = []
    for r in spec["rows"]:
        t = r.get("fact_text")
        tr = rows.get((r["name"], r["team"]))
        if t and (tr is None or f'<span class="m-sub drv">{_esc(t)}</span>' not in tr):
            puuttuu.append(f'{r["name"]} ({r["team"]}): "{t}"')
        if t:
            assert r["sub"].endswith(t), r
    assert not puuttuu, "kortin todiste ei ole pelaajan rivilla:\n  " + "\n  ".join(puuttuu)
    assert any(r.get("fact_text") for r in spec["rows"])
    assert "Under each name: the one number the projection leans on." in html


def test_clean_sheet_fact_equals_the_fpl_page_team_number():
    """Portti k2 C1: pelaajan nollapeli on SEURAN GW-luku samasta kentasta
    jota /fpl renderoi, ei pistekomponentista johdettu."""
    import config as _cfg
    from src.models.fpl_why_drivers import load_team_cs, fact_text
    doc = _page_doc()
    xp = json.loads((_cfg.DATA_DIR / "fpl_xp_projections.json").read_text(encoding="utf-8"))
    gw = xp["meta"]["next_gameweek"]
    team_cs = load_team_cs(gw)
    if not team_cs:
        pytest.skip("phase0 ei kanna tata kierrosta")
    # Vertailukohta on SIVUN RENDEROITY SOLU, ei oma pyoristyskonventio:
    # build_context + cs_table_html on sama polku jonka /fpl#clean-sheets ajaa.
    from scripts import build_fpl_page as bfp
    import re as _re
    acc = json.loads((_cfg.DATA_DIR / "accuracy.json").read_text(encoding="utf-8"))
    page_html = bfp.cs_table_html(bfp.build_context(doc, acc))
    cells = {}
    for tr in _re.findall(r"<tr>(.*?)</tr>", page_html, flags=_re.S):
        m = _re.search(r'<td class="team">([^<]+)', tr)
        pct = _re.search(r'<td class="num">([0-9.]+%)</td>', tr)
        if m and pct:
            cells[m.group(1)] = pct.group(1)
    assert len(cells) >= 18, cells
    by_short = {t["short"]: t["name"] for t in doc["teams"]}
    n = 0
    for p in xp["players"]:
        if p.get("pos") not in ("GKP", "DEF"):
            continue
        t = fact_text(p, team_cs, "2025/26")
        if "clean sheet chance" not in t:
            continue
        n += 1
        short = p["team_short"]
        sivu = cells[by_short[short]]
        assert t == f"{short} {sivu} clean sheet chance", (p["web_name"], t, sivu)
    assert n > 0
    # negatiivinen kontrolli: round()-versio EI tasmaa sivuun jollain seuralla
    mismatch = [s_ for s_, v in team_cs.items()
                if f"{round(v)}%" != cells.get(by_short.get(s_), "")]
    assert mismatch, "kontrolli tyhja: round() tasmaisi kaikkiin soluihin"


def _player(pos, xmins=90.0, pens=None, corners=None, fk=None, xgi=None, team="ARS"):
    return {"web_name": "X", "pos": pos, "xmins": xmins, "team_short": team,
            "set_pieces": {"pens": pens, "corners": corners, "fk": fk},
            "last_season": {"per90": {"xgi": xgi}} if xgi is not None else {},
            "components": {"clean_sheet": 1.0},
            "owned_pct": 0.8, "price": 4.5, "gameweeks": []}


CS = {"ARS": 51.0, "CRY": 25.7}
PS = "2025/26"


def test_fact_text_never_publishes_ownership_price_fixtures_minutes_or_component_cs():
    from src.models.fpl_why_drivers import fact_text, NEVER
    from src.models.fpl_xp import driver_facts
    p = _player("MID")
    facts = driver_facts(p)
    assert "differential" in facts and "minutes" in facts and "clean_sheets" in facts, facts
    assert fact_text(p, CS, PS) == ""            # MID ilman set piece/xGI: tyhja, ei nollapeli
    for banned in ("owned", "mins a game", "(H)", "(A)", "bonus", "last season"):
        assert banned not in fact_text(_player("MID", xgi=0.3, pens=1), CS, PS)
    assert set(NEVER) == {"minutes", "fixtures", "bonus", "price", "differential"}


def test_fact_text_set_piece_needs_first_or_second_taker():
    """Odegaard-tapaus: kolmas nimi listalla ei ole vastuu."""
    from src.models.fpl_why_drivers import fact_text
    assert fact_text(_player("MID", pens=3, corners=3, xgi=0.32), CS, PS) == "0.32 xGI/90 in 2025/26"
    assert fact_text(_player("MID", pens=1, xgi=0.32), CS, PS) == "on penalties"
    assert fact_text(_player("MID", pens=2, corners=1, fk=1, xgi=0.68), CS, PS) \
        == "on penalties, corners, free kicks"


def test_fact_text_by_position_with_route():
    from src.models.fpl_why_drivers import fact_text, XGI_MIN
    from scripts.build_fpl_why import XGI_MIN as WHY_MIN
    assert WHY_MIN == XGI_MIN == 0.15                     # yksi kynnys
    # DEF: seuran luku, ei komponentti, ei xGI (Gabriel 0,15)
    assert fact_text(_player("DEF", xgi=0.15), CS, PS) == "ARS 51% clean sheet chance"
    assert fact_text(_player("DEF", xgi=0.15, team="CRY"), CS, PS) == "CRY 25.7% clean sheet chance"
    assert fact_text(_player("DEF", team="BHA"), CS, PS) == ""      # ei GW-lukua -> tyhja
    assert fact_text(_player("GKP"), CS, PS).endswith("clean sheet chance")
    # MID/FWD: xGI lattialla, kausi nimettyna, ei nollapelia fallbackina
    assert fact_text(_player("MID", xgi=0.13), CS, PS) == ""        # Ampadu: alle lattian
    assert fact_text(_player("FWD", xgi=0.57), CS, PS) == "0.57 xGI/90 in 2025/26"
    assert fact_text(_player("FWD", xgi=0.57), CS, None) == ""     # kautta ei voi johtaa
    t = fact_text(_player("FWD", xgi=0.57), CS, PS)
    assert "+" not in t and " and " not in t


def test_previous_season_and_team_cs_readers(tmp_path):
    from src.models.fpl_why_drivers import previous_season_label, load_team_cs
    assert previous_season_label({"season": "2026/27"}) == "2025/26"
    assert previous_season_label({"season": "26/27"}) is None
    assert previous_season_label({}) is None
    p = tmp_path / "p0.json"
    p.write_text(json.dumps({"teams": [
        {"short": "ARS", "fixtures": [{"gw": 4, "cs_pct": 51.0}, {"gw": 5, "cs_pct": 30.0}]},
        {"short": "MCI", "fixtures": [{"gw": 4, "cs_pct": 40.0}, {"gw": 4, "cs_pct": 35.0}]},  # DGW
        {"short": "BHA", "fixtures": [{"gw": 5, "cs_pct": 20.0}]},                             # BGW
    ]}), encoding="utf-8")
    assert load_team_cs(4, p) == {"ARS": 51.0}
    assert load_team_cs(None, p) == {} and load_team_cs(4, tmp_path / "x.json") == {}


def test_card_sub_is_xmins_plus_fact():
    from src.models.fpl_why_drivers import card_sub
    ctx = {"team_cs": CS, "prev_season": PS}
    assert card_sub(_player("FWD", xmins=88.4, pens=1), ctx) == "88 xMins  ·  on penalties"
    assert card_sub(_player("DEF", xmins=70.0, team="BHA"), ctx) == "70 xMins"
    assert card_sub({"pos": "DEF"}, ctx) is None


def _phase_payload(next_gw: int, deadline_gw: int) -> dict:
    """Synteettinen xP-artefakti jossa raaka kierroskentta ja vaikutettava
    kierros EROAVAT (30.8: next=2, vaikutettava=3)."""
    def pl(i, name, team, pos, xp2, xp3, pens=None):
        return {"id": i, "web_name": name, "team_short": team, "team": team, "pos": pos,
                "xmins": 90.0, "price": 8.0, "owned_pct": 30.0,
                "set_pieces": {"pens": pens, "corners": None, "fk": None},
                "last_season": {"per90": {"xgi": 0.5}}, "components": {"clean_sheet": 1.0},
                "gameweeks": ([{"gw": next_gw, "xp": xp2, "opponents": [{"opp": "AAA", "venue": "H"}]}]
                              if next_gw != deadline_gw else [])
                + [{"gw": deadline_gw, "xp": xp3, "opponents": [{"opp": "BBB", "venue": "A"}]}]}
    players = [pl(1, "Alpha", "ARS", "FWD", 9.0, 2.0, pens=1),
               pl(2, "Beta", "MCI", "DEF", 1.0, 8.0),
               pl(3, "Gamma", "LIV", "MID", 5.0, 5.0)]
    return {"meta": {"available": True, "season": "2026/27",
                     "next_gameweek": next_gw, "deadline_gameweek": deadline_gw,
                     "generated_at": "2026-09-10T00:00:00"},
            "players": players}


@pytest.mark.parametrize("next_gw,deadline_gw", [(2, 3), (4, 4), (3, 5)])
def test_card_gameweek_equals_page_and_fact_gameweek_in_every_phase(monkeypatch, next_gw, deadline_gw):
    """Portti k4: kortin otsikon kierros, alarivin nollapelikierros ja sivun
    #gw-xp-kierros ovat SAMA luku myos kun raaka meta-kentta eroaa
    vaikutettavasta kierroksesta. Mitataan synteettisilla vaiheilla, ei
    taman hetken metalla (CLAUDE.md 6a mek. 3)."""
    from scripts import gen_share_card as gsc
    from scripts import build_fpl_longtail as lt
    from src.models import fpl_why_drivers as fwd
    data = _phase_payload(next_gw, deadline_gw)
    monkeypatch.setattr(gsc, "_xp_payload", lambda: data)
    seen = []
    monkeypatch.setattr(fwd, "load_team_cs", lambda gw, path=None: (seen.append(gw) or {"MCI": 40.0}))
    monkeypatch.setattr(gsc, "_as_of", lambda d: "10 Sep", raising=False)

    class _A:
        gw = None
        top = 20
    spec = gsc.card_xp(_A())
    assert spec["title"].startswith(f"GAMEWEEK {deadline_gw} ")
    assert seen and set(seen) == {deadline_gw}, seen
    # rivit ovat vaikutettavan kierroksen xP:n mukaan: Beta (8.0) ennen Alphaa (2.0)
    names = [r["name"] for r in spec["rows"]]
    assert names.index("Beta") < names.index("Alpha")
    beta = next(r for r in spec["rows"] if r["name"] == "Beta")
    assert beta["sub"] == "90 xMins  ·  MCI 40% clean sheet chance"
    html = lt._gw_xp_section(data)
    assert f"Gameweek {deadline_gw} expected points" in html
    assert f'<span class="m-sub drv">MCI 40% clean sheet chance</span>' in html


def test_kortti_ja_sivu_lukevat_SAMAA_kierrosfunktiota():
    """Lahdekoodiportti — mutta kommentit poistetaan ennen etsintaa.

    🔴 Ensimmainen versio greppasi raakaa lahdetta ja osui `card_gw_outlook`in
    OMAAN perustelukommenttiin, jossa lukee sana `display_gameweek`. Mitattu
    12.9 illalla: kun korjaus perutaan takaisin `min(fixtures)`-saantoon
    kommentit ennallaan, tama testi on **vihrea**. Portti ei voinut erottaa
    kommenttia koodista (muisti: `portti-joka-etsii-merkkijonoa-ei-mittaa-arvoa`).

    Varsinainen vahti on alla oleva vaihe-injektoitu kaytostesti; tama on
    halpa lisavarmistus siita etta kutsu on olemassa lahdekoodissa asti.
    """
    import re as _re
    from pathlib import Path as _P
    root = _P(__file__).resolve().parents[1]

    def _ilman_kommentteja(t: str) -> str:
        rivit = []
        for r in t.split(chr(10)):
            k = r.split("#", 1)[0] if "#" in r else r
            rivit.append(k)
        return chr(10).join(rivit)

    kortti = _ilman_kommentteja(
        (root / "scripts" / "gen_share_card.py").read_text(encoding="utf-8"))
    sivu = _ilman_kommentteja(
        (root / "scripts" / "build_fpl_page.py").read_text(encoding="utf-8"))
    i = kortti.find("def card_gw_outlook")
    assert i > 0
    runko = kortti[i:i + 3000]
    assert "display_gameweek" in runko, (
        "card_gw_outlook ei KUTSU display_gameweekia (kommentit poistettu "
        "ennen etsintaa) — kortti voi olla eri kierroksessa kuin sivu")
    assert "display_gameweek" in sivu, "sivu ei lue display_gameweekia"


def test_kortin_kierros_on_sivun_kierros_JOKA_VAIHEESSA():
    """🔴 Vaihe-injektoitu kaytostesti. Tama on se joka erottelee.

    Mitattu 12.9 illalla: `min(fixtures)` ja `display_gameweek` antavat saman
    vastauksen kaikissa kauden vaiheissa PAITSI yhdessa — siina ikkunassa
    jossa kierroksen kaikki ottelut on potkaistu mutta FPL:n `finished`-lippu
    laahaa (dokumentoitu 14 h, `fpl_gameweek.py`). Toiminnallinen testi joka
    lukee levylla olevaa artefaktia on siis diskriminoiva ~14 h kierroksessa
    ja vihrea muun ajan — tasan saannon 6a kohta 3.

    Tassa vaihe annetaan synteettisesti, joten ero on aina mitattavissa.
    """
    from scripts import gen_share_card as g
    from src.models.fpl_gameweek import display_gameweek

    # Vaihe: GW4:n kaikki ottelut potkaistu, FPL:n finished laahaa ->
    # display_gameweek sanoo 5, min(fixtures) sanoisi 4.
    meta = {"deadline_gameweek": 5, "completed_gameweeks": [1, 2, 3, 4],
            "generated_at": "2026-09-14T20:00:00+00:00"}
    fixtures = []
    for gw, ko in ((4, 1789000000000), (5, 1789600000000)):
        for n, (h, a) in enumerate((("Alpha", "Beta"), ("Gamma", "Delta"))):
            fixtures.append({
                "gameweek": gw, "kickoff_ms": ko + n,
                "home": h, "away": a,
                "home_short": h[:3].upper(), "away_short": a[:3].upper(),
                "xg_home": 1.5, "xg_away": 1.1,
                "cs_home_pct": 30.0, "cs_away_pct": 20.0,
            })
    doc = {"meta": meta, "fixtures": fixtures, "teams": []}

    odotettu = display_gameweek(meta, fixtures)
    assert odotettu == 5, (
        f"fikstuuri ei enaa erottele: display_gameweek={odotettu}, "
        f"min(fixtures)=4. Rakenna vaihe uudelleen.")

    alkuperainen = g._load
    try:
        g._load = lambda nimi: doc if "phase0" in nimi else alkuperainen(nimi)

        class _A:
            gw = None

        spec = g.card_gw_outlook(_A())
    finally:
        g._load = alkuperainen

    saadut = {f["gameweek"] for f in spec["fixtures"] if f.get("gameweek")}
    assert saadut == {5}, (
        f"kortti valitsi kierroksen {saadut}, sivu nayttaa {odotettu}. "
        f"Lukija on eri kuin sivulla — kortin tarkistusreitti vie vaaraan "
        f"kierrokseen.")


def test_vanha_card_gw_outlook_saanto_EI_riita():
    """Negatiivinen kontrolli portin erottelukyvylle.

    Osoittaa etta ylla oleva fikstuuri todella erottelee: vanha saanto
    (`min(fixtures)`) antaa 4 samalla datalla jolla oikea vastaus on 5.
    Ilman tata ei voi tietaa etta testi olisi punainen regressiosta.
    """
    from src.models.fpl_gameweek import display_gameweek
    meta = {"deadline_gameweek": 5, "completed_gameweeks": [1, 2, 3, 4],
            "generated_at": "2026-09-14T20:00:00+00:00"}
    fixtures = [{"gameweek": gw, "kickoff_ms": 1789000000000 + gw}
                for gw in (4, 5)]
    assert min(f["gameweek"] for f in fixtures) == 4
    assert display_gameweek(meta, fixtures) == 5


def test_kortti_ja_sivu_lukevat_SAMAA_kierrosfunktiota():
    """🔴 Neljas saanto ei saa palata (12.9.2026).

    Portti vertaa kortin ja sivun LUKUJA, mutta jos ne valitsevat kierroksen
    eri saannolla, vertailu on kahden eri maailmantilan valilla ja portti
    kertoo vaarasta asiasta. 12.9 kaikki 20 ottelua ilmoitettiin puuttuvina
    vaikka sivu oli oikeassa.

    Tama mittaa lahteesta etta kumpikin polku paatyy `display_gameweek`iin.
    """
    from pathlib import Path as _P
    root = _P(__file__).resolve().parents[1]
    kortti = (root / "scripts" / "gen_share_card.py").read_text(encoding="utf-8")
    sivu = (root / "scripts" / "build_fpl_page.py").read_text(encoding="utf-8")
    i = kortti.find("def card_gw_outlook")
    assert i > 0
    runko = kortti[i:i + 3000]
    assert "display_gameweek" in runko, (
        "card_gw_outlook ei lue display_gameweekia — kortti voi olla eri "
        "kierroksessa kuin sivu jolle se linkittaa")
    assert "display_gameweek" in sivu, "sivu ei lue display_gameweekia"


