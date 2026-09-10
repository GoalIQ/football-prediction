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
    """Kierros jota data tosiasiassa kantaa - EI kovakoodattua GW1:ta.

    🔴 Testi kaatui 25.8 kun FPL vihdoin merkitsi GW1:n ottelut finishediksi
    ja builderi pudotti pelatun kierroksen projektioista: `gw=1` ei enaa
    loytynyt tiedostosta. Kovakoodattu kierrosnumero vanhenee joka viikko, ja
    portti joka vanhenee itsestaan on huonompi kuin ei porttia - se punaisee
    ilman etta mikaan on rikki, ja opettaa ohittamaan sen.
    """
    import json as _j
    from pathlib import Path as _P
    doc = _j.loads((_P(__file__).resolve().parents[1] / "data"
                    / "fpl_projections_phase0.json").read_text(encoding="utf-8"))
    from src.models.fpl_gameweek import actionable_gameweek
    gws = sorted({f["gameweek"] for f in doc["fixtures"] if f.get("gameweek")})
    act = actionable_gameweek(doc.get("meta") or {})
    if act in gws:
        return act
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
