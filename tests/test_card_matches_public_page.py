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
