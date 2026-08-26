# -*- coding: utf-8 -*-
"""Etusivun (index.html) generoitujen lohkojen portit — scripts/build_fpl_page.py.

Kattaa "Live model projections" -taulukon: rivit tulevat xP-datasta ja
liputetut pelaajat rajataan pois. Negatiivinen kontrolli varmistaa etta portit
oikeasti suodattavat (ilman sita testi ei mittaisi mitaan).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# 1.8.2026: etusivun "Live model projections" -taulukko generoidaan datasta.
# Aiemmin kovakoodattu 24.7. ajosta samalla kun alaviite lupasi "refreshed
# daily". Karkirivilla oli pelaaja jonka FPL oli liputtanut loukkaantuneeksi.
# ---------------------------------------------------------------------------
def _xp_player(name, xp, status="a", chance=None, basis="pl_history"):
    return {"web_name": name, "team_short": "TST", "pos": "MID", "price": 6.0,
            "owned_pct": 5.0, "xp_horizon_total": xp, "status": status,
            "chance_next": chance, "data_basis": basis}


def test_xp_table_excludes_flagged_players():
    from scripts.build_fpl_page import xp_table_rows
    xp = {"meta": {"horizon_gw": 6}, "players": [
        _xp_player("Injured", 40.0, status="i", chance=0),
        _xp_player("Doubtful", 39.0, status="d", chance=25),
        _xp_player("Promoted", 38.0, basis="no_history"),
        _xp_player("Fit", 30.0),
    ]}
    html = xp_table_rows(xp, n=4)
    assert "Fit" in html
    # Negatiivinen kontrolli: jos portit eivat toimi, korkeamman xP:n nimet
    # nousevat karkeen ja etusivu suosittelee pelaajaa jota ei voi pelauttaa.
    for name in ("Injured", "Doubtful", "Promoted"):
        assert name not in html, f"{name} paasi etusivun taulukkoon"


# ---------------------------------------------------------------------------
# 10.8.2026: vaihtuvuusluku oli 5. sarakkeessa, joka on .m-hide eli piilossa
# kapealla naytolla — eli poissa siita pinnasta jolla FPL-liikenne on. Luku
# tulee riville .m-only-alarivina ja katoaa kun sarake palautetaan.
# ---------------------------------------------------------------------------
def _cs_row(team, cs_pct, opponent, venue, fdr):
    return {"team": team, "cs_pct": cs_pct, "opponent": opponent,
            "venue": venue, "fdr": fdr}


def test_cs_table_turnover_reaches_narrow_screen(monkeypatch):
    from scripts import build_fpl_page as bp
    from scripts.build_fpl_phase0 import map_name
    monkeypatch.setattr(bp, "_turnover_by_model_team", lambda: {
        map_name("Brighton & Hove Albion"): {"is_promoted": False,
                                             "minutes_churn_pct": 21.4},
        map_name("Coventry City"): {"is_promoted": True,
                                    "minutes_churn_pct": None},
    })
    html = bp.cs_table_html({
        "next_gw": 1, "season": "2026/27", "cs_rows": [
            _cs_row("Brighton & Hove Albion", 34.0, "Aston Villa", "H", 2),
            _cs_row("Coventry City", 6.4, "Arsenal", "A", 5),
            _cs_row("Tuntematon FC", 20.0, "Arsenal", "H", 4),
        ]})
    # Luku on rivilla ILMAN etta sarake tarvitsee palauttaa...
    assert '<span class="m-only m-sub">21% turnover</span>' in html
    # 14.8: teksti oli "no PL record", mutta se oli VAARA — Ipswich pelasi
    # PL:aa 24/25 ja on osa mitattua nousijabaselinea.
    # 26.8: VARAUS EI OLE ENAA .m-only. Vaihtuvuus-% on tilasto ja saa jaada
    # kapealle naytolle (sarake kantaa sen leveallä), mutta nousijan varaus on
    # syy olla luottamatta lukuun — se renderoidaan joka leveydella. Ilman
    # tata tyopoytalukija sai varauksen vain `title=`-tooltipista.
    assert '<span class="m-sub is-caveat">baseline rating</span>' in html
    # ...ja sarake on yha paikallaan leveille naytoille.
    assert '<td class="num m-hide">21%</td>' in html
    # Negatiivinen kontrolli: ilman tata testi menisi lapi myos jos alarivi
    # liimattaisiin jokaiseen riviin datasta riippumatta. Vaihtuvuusrivi on
    # tasan yksi (Brighton); Coventryn varaus on eri luokassa.
    assert html.count('class="m-only m-sub"') == 1, "alarivi ilman dataa"
    assert html.count('class="m-sub is-caveat"') == 1, "varaus ilman dataa"
    assert "Tuntematon FC" in html


def test_cs_table_seuraa_fitin_tilaa_eika_kovakoodaa_baselinea(monkeypatch):
    """26.8: sama rivi, eri `basis` -> eri vaite. Ilman tata haaraa sivu

    vaittaisi baselinea myos silloin kun sita ei sovelleta yhteenkaan
    joukkueeseen, mika oli livena tilanne 25.-26.8.
    """
    from scripts import build_fpl_page as bp
    from scripts.build_fpl_phase0 import map_name

    def _aja(basis, n):
        monkeypatch.setattr(bp, "_turnover_by_model_team", lambda: {
            map_name("Coventry City"): {"is_promoted": True,
                                        "minutes_churn_pct": None,
                                        "basis": basis, "own_matches": n},
        })
        return bp.cs_table_html({
            "next_gw": 2, "season": "2026/27",
            "cs_rows": [_cs_row("Coventry City", 36.3, "Hull", "H", 2)]})

    oma = _aja("own_thin_fit", 1)
    assert "rating from 1 match" in oma
    assert "baseline" not in oma, oma
    assert "fitted on 1 Premier League match" in oma  # tooltip kertoo saman

    # NEGATIIVINEN KONTROLLI: kaanna tila -> vaitteen ON vaihduttava.
    base = _aja("promoted_baseline", 0)
    assert "baseline rating" in base
    assert "rating from" not in base, base


def test_xp_table_foot_states_horizon_not_daily_promise():
    from scripts.build_fpl_page import xp_table_rows
    html = xp_table_rows({"meta": {"horizon_gw": 6},
                          "players": [_xp_player("Fit", 30.0)]}, n=1)
    assert "next 6 gameweeks" in html
    assert "refreshed daily" not in html


# ---------------------------------------------------------------------------
# 25.8: nayttonimien drift kahden listan valilla
# ---------------------------------------------------------------------------
def test_comp_names_cover_every_league_page():
    """Track recordin liiganimien on katettava JOKAINEN liiga jolla on sivu.

    Miksi tama on portti eika kommentti: ELC, DED ja PPL lisattiin liigoiksi
    22.8 ja saivat omat ennustesivunsa, mutta `build_fpl_page.COMP_NAMES` jai
    paivittamatta. Seuraus ei ollut kosmeettinen vaan lukijalle nakyva:
    /predictions -sivun track record listasi ne raakakoodeina "ELC", "DED",
    "PPL" siina missa muut liigat naytettiin nimella. Sama kartta on
    DUPLIKOITU mobiiliin (screens/ModelAccuracyScreen.tsx), jota tama testi ei
    nae — jos lisaat liigan, lisaa se molempiin.
    """
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]

    def _load(name: str):
        spec = importlib.util.spec_from_file_location(
            name, root / "scripts" / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    pages = _load("build_prediction_pages")
    fpl_page = _load("build_fpl_page")

    missing = sorted(set(pages.LEAGUES) - set(fpl_page.COMP_NAMES))
    assert not missing, (
        f"liigalla on ennustesivu mutta ei nayttonimea track recordissa: "
        f"{missing}. Lisaa build_fpl_page.COMP_NAMES:iin JA mobiilin "
        f"ModelAccuracyScreen.tsx:n COMP_NAMES:iin."
    )

    # ...ja nimen on oltava sama molemmissa, ei vain olemassa. Ilman tata
    # "Championship" ja "EFL Championship" lapaisisivat molemmat.
    for code, meta in pages.LEAGUES.items():
        name = meta.get("name")
        if name:
            assert fpl_page.COMP_NAMES[code] == name, (
                f"{code}: ennustesivu sanoo {name!r}, track record "
                f"{fpl_page.COMP_NAMES[code]!r}"
            )


# ---------------------------------------------------------------------------
# 25.8: tasapeliluku johdetaan, ei lueta (fail-open olisi julkaissut "0 draws")
# ---------------------------------------------------------------------------
def _bfp():
    import importlib.util
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "build_fpl_page", root / "scripts" / "build_fpl_page.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_tasapeliluku_johdetaan_vanhasta_skeemasta():
    """🔴 TAMA ON SE VIKA JOKA MELKEIN SHIPPASI.

    `draw_n`/`pct_draw` ovat uusia kenttia, mutta builderi ajetaan servattua
    `data/accuracy.json`:aa vasten joka voi olla vanhaa skeemaa:
    `fpl-page-refresh` (cron 09:30 UTC) bakettaa sivun AJAMATTA
    accuracy-pipelinea, joten koodi ja artefakti eivat paivity samassa ajossa.

    Mitattu 25.8: `(m.get("pct_draw") or 0.0)` olisi julkaissut jokaisella
    rivilla "0% were draws" - myos World Cupilla jolla oli 29 tasapelia
    (104 gradattua, 75 ratkennutta). Lukija tarkistaa sen vahennyslaskulla
    viidessa sekunnissa.
    """
    m = _bfp()
    # Vanha skeema: EI draw_n:aa eika pct_draw:ta.
    vanha = {"n": 104, "correct_1x2": 63, "pct_1x2": 0.6058,
             "decisive_n": 75, "decisive_correct": 63, "pct_decisive": 0.84,
             "exact_n": 56, "exact_correct": 11, "pct_exact": 0.1964,
             "brier": 0.49, "brier_n": 56}
    ctx = m.build_context_by_comp_row("WC", vanha) if hasattr(
        m, "build_context_by_comp_row") else {
        "name": "World Cup 2026",
        "dec_n": vanha["decisive_n"], "dec_correct": vanha["decisive_correct"],
        "pct_dec": vanha["pct_decisive"] * 100,
        "draw_n": vanha.get("draw_n") if vanha.get("draw_n") is not None
        else max(0, vanha["n"] - vanha["decisive_n"]),
    }
    sub = m._bycomp_sub(ctx)
    assert "29 draws" in sub, sub
    assert "0 draws" not in sub, f"fail-open palasi: {sub}"


def test_pienesta_otoksesta_ei_nayteta_prosenttia():
    """🔴 "100% (5 of 5)" on kuvakaappauksessa puolustuskelvoton, ja se
    seisoisi juuri sen rivin vieressa joka selittaa matalia lukuja -> koko
    lohko lukisi valikoivana. Ligue 1:lla dec_n oli 5."""
    m = _bfp()
    pieni = {"name": "Ligue 1", "dec_n": 5, "dec_correct": 5,
             "pct_dec": 100.0, "draw_n": 4}
    sub = m._bycomp_sub(pieni)
    assert "%" not in sub, sub
    assert "5 of 5" in sub
    # ...mutta riittavan iso otos SAA prosentin
    iso = {"name": "WC", "dec_n": 75, "dec_correct": 63, "pct_dec": 84.0,
           "draw_n": 29}
    assert "84%" in m._bycomp_sub(iso)


def test_yhden_tasapelin_yksikkomuoto():
    m = _bfp()
    yksi = {"name": "PL", "dec_n": 9, "dec_correct": 6, "pct_dec": 66.7,
            "draw_n": 1}
    sub = m._bycomp_sub(yksi)
    assert "1 draw " in sub or sub.rstrip("</div>").endswith("1 draw"), sub
    assert "1 draws" not in sub, sub


def test_ei_valikointia_lupaavaa_sanamuotoa():
    """🔴 1.8.2026 tehtiin nimenomainen rehellisyyskorjaus: malli nimeaa
    voittajan JOKA ottelussa, joten "kun malli nimesi voittajan" antaa
    ymmartaa valikointia jota ei ole. Uusi alarivi ei saa palauttaa sita."""
    m = _bfp()
    sub = m._bycomp_sub({"name": "WC", "dec_n": 75, "dec_correct": 63,
                         "pct_dec": 84.0, "draw_n": 29})
    assert "Winner named" not in sub, sub
    assert "when the match had a winner" in sub, sub


# ---------------------------------------------------------------------------
# 25.8: sivu ei saa nayttaa jo pelatun kierroksen projektioita
# ---------------------------------------------------------------------------
def _fx(gw, n, kickoff_ms):
    return [{"gameweek": gw, "kickoff_ms": kickoff_ms + i} for i in range(n)]


def test_siirtyy_seuraavaan_kun_kaikki_ottelut_alkaneet():
    """🔴 MITATTU VIKA. Sivu naytti Gameweek 1:n nollapeliprojektiot vaikka
    kaikki GW1:n ottelut oli pelattu. Arsenalille luki 53 % (koti, Coventry)
    kun GW2:n luku on 38 % (vieras, Aston Villa). Projektio jo pelatulle
    ottelulle on historiaa vaarassa asussa.

    `meta.next_gameweek` tulee FPL:n lipuista jotka laahaavat tunteja."""
    m = _bfp()
    import datetime as dt
    menneisyys = int((dt.datetime.now(dt.timezone.utc).timestamp() - 86400) * 1000)
    meta = {"next_gameweek": 1, "deadline_gameweek": 2}
    assert m.display_gw(meta, _fx(1, 10, menneisyys)) == 2


def test_kesken_kierroksen_pysytaan_paikallaan():
    """🔴 Ehto on tiukka tarkoituksella: YKSIKIN alkamaton ottelu pitaa sivun
    kuluvassa kierroksessa. Se on mita lukijan joukkue on juuri nyt
    keraamassa (22.8 linjaus rate_teamin target_gw:sta)."""
    m = _bfp()
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc).timestamp() * 1000
    fx = _fx(1, 9, int(now - 86400000)) + [{"gameweek": 1,
                                            "kickoff_ms": int(now + 3600000)}]
    meta = {"next_gameweek": 1, "deadline_gameweek": 2}
    assert m.display_gw(meta, fx) == 1, "yksi alkamaton ottelu -> ei siirryta"


def test_deadline_samassa_kierroksessa_ei_siirra():
    """Ennen deadlinea `deadline_gameweek == next_gameweek` -> ei liiketta,
    vaikka jokin ottelu olisi jo alkanut (DGW/siirretty ottelu)."""
    m = _bfp()
    import datetime as dt
    menneisyys = int((dt.datetime.now(dt.timezone.utc).timestamp() - 86400) * 1000)
    meta = {"next_gameweek": 2, "deadline_gameweek": 2}
    assert m.display_gw(meta, _fx(2, 10, menneisyys)) == 2


def test_puuttuva_deadline_kentta_ei_muuta_kaytosta():
    """Vanha payload -> bittitarkasti entinen kaytos."""
    m = _bfp()
    import datetime as dt
    menneisyys = int((dt.datetime.now(dt.timezone.utc).timestamp() - 86400) * 1000)
    fx = _fx(1, 10, menneisyys)
    assert m.display_gw({"next_gameweek": 1}, fx) == 1
    assert m.display_gw({"next_gameweek": 1, "deadline_gameweek": None}, fx) == 1
    # ...eika merkkijono saa lapaista int-tarkistusta
    assert m.display_gw({"next_gameweek": 1, "deadline_gameweek": "2"}, fx) == 1
