"""Mittarisilmukka ja rivin valinta (18.10.2026, Villen GO, automaatiokohta 1).

Ennen tätä backlog-rivien mittareita ei luettu koskaan takaisin. Portti kaatuu, jos
  * erääntynyt mittari voi jäädä ilman tulosta tai agentti voi muuttaa vanhoja pisteitä, mittareita
    tai tuloksia ilman että aallonharjan julkaisu hylkää haaran,
  * valinta ei noudata kaavaa (2 x arvo + kiire + 2 x myynti + uutuus - työ + näyttö), lukitusta,
    varauksia tai kärkivuoroa,
  * näyttö ei rankaise lähdettä, jonka mittarit epäonnistuvat,
  * mittausdata vuotaa julkiseen repoon tilien, Premiumien, käyntien tai tapahtumien määriä.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

JUURI = Path(__file__).resolve().parent.parent
KANSIO = JUURI / ".github" / "auto-kehitys"


def _lataa(nimi):
    spec = importlib.util.spec_from_file_location(f"auto_{nimi}", KANSIO / f"{nimi}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclass tarvitsee moduulin sys.modulesissa
    spec.loader.exec_module(mod)
    return mod


mt = _lataa("mittarit")
md = _lataa("mittausdata")

PISTEET = "      Pisteet: {lukko}arvo {a}/3 · kiire {k}/3 · työ {t} · myynti {m}/3 · uutuus {u}/2 = 0"


def _rivi(otsikko, tehty=False, a=2, k=1, t="M", m=1, u=1, lukko="", mittari=None, tulokset=(), lahde=""):
    rivit = [f"- [{'x' if tehty else ' '}] {otsikko}", f"  kuvaus {lahde}".rstrip(),
             PISTEET.format(lukko=lukko, a=a, k=k, t=t, m=m, u=u)]
    if mittari:
        rivit.append(f"      Mittari: {mittari}")
    rivit += [f"      Tulos {p}: {merkki} {teksti}" for p, merkki, teksti in tulokset]
    return "\n".join(rivit)


def _backlog(*rivit, tehdyt=()):
    return "\n".join(["# Auto-backlog", "## Signaalit", "- 2026-10: signaali", "", "## Avoimet", ""]
                     + list(rivit) + ["", "## Tehdyt", ""] + list(tehdyt)) + "\n"


def test_jasennys_ja_tulosrivit():
    t = _backlog(_rivi("A", tehty=True, mittari="x · tarkistus 2026-10-20",
                       tulokset=[("2026-10-21", "✅", "näkyy sivulla")]))
    (r,) = mt.jasenna(t)
    assert r.tehty and r.tarkistus == "2026-10-20" and r.tulokset == [("2026-10-21", "✅", "näkyy sivulla")]
    assert r.komponentit() == {"arvo": 2, "kiire": 1, "myynti": 1, "uutuus": 1, "tyo": "M"}


def test_vanha_ascii_tyo_kelpaa():
    t = _backlog(_rivi("A").replace("työ", "tyo"))
    assert mt.jasenna(t)[0].komponentit()["tyo"] == "M"


def test_eraantyneet_vain_tehdyt_ilman_tulosta():
    t = _backlog(
        _rivi("Tehty erääntynyt", tehty=True, mittari="x · tarkistus 2026-10-20"),
        _rivi("Tehty tuleva", tehty=True, mittari="x · tarkistus 2026-11-20"),
        _rivi("Avoin erääntynyt", mittari="x · tarkistus 2026-10-01"),
        _rivi("Tehty mitattu", tehty=True, mittari="x · tarkistus 2026-10-01", tulokset=[("2026-10-02", "❌", "ei")]),
    )
    assert [r.otsikko for r in mt.eraantyneet(mt.jasenna(t), "2026-10-25")] == ["Tehty erääntynyt"]


def test_tarkista_vaatii_tuloksen_ja_kieltaa_vanhojen_muutokset():
    pohja = mt.jasenna(_backlog(_rivi("E", tehty=True, mittari="x · tarkistus 2026-10-20"),
                                _rivi("V", tehty=True, mittari="y · tarkistus 2026-10-01",
                                      tulokset=[("2026-10-02", "✅", "ok")])))
    ilman = mt.jasenna(_backlog(_rivi("E", tehty=True, mittari="x · tarkistus 2026-10-20"),
                                _rivi("V", tehty=True, mittari="y · tarkistus 2026-10-01",
                                      tulokset=[("2026-10-02", "✅", "ok")])))
    assert any("ilman Tulos" in v for v in mt.tarkista(pohja, ilman, "2026-10-25"))
    hyva = mt.jasenna(_backlog(_rivi("E", tehty=True, mittari="x · tarkistus 2026-10-20",
                                     tulokset=[("2026-10-25", "➖", "PostHog-avain puuttuu")]),
                               _rivi("V", tehty=True, mittari="y · tarkistus 2026-10-01",
                                     tulokset=[("2026-10-02", "✅", "ok")])))
    assert mt.tarkista(pohja, hyva, "2026-10-25") == []
    muutettu = mt.jasenna(_backlog(_rivi("E", tehty=True, mittari="x · tarkistus 2026-10-20", a=3,
                                         tulokset=[("2026-10-25", "✅", "ok")]),
                                   _rivi("V", tehty=True, mittari="y · tarkistus 2026-10-01",
                                         tulokset=[("2026-10-02", "❌", "muutettu")])))
    virheet = mt.tarkista(pohja, muutettu, "2026-10-25")
    assert any("Pisteet tai Mittari" in v for v in virheet)
    assert any("Tulos-rivi muuttui" in v for v in virheet)
    vaara_muoto = _backlog(_rivi("E", tehty=True, mittari="x · tarkistus 2026-10-20")) + "      Tulos: hyvä\n"
    assert mt.tarkista(pohja, mt.jasenna(vaara_muoto.replace("## Tehdyt", "## Tehdyt")), "2026-10-25")


def test_valinta_lukitut_ensin_listan_jarjestyksessa_sitten_kaava():
    t = _backlog(
        _rivi("Iso piste", a=3, k=3, m=3, u=2, t="S"),
        _rivi("Lukittu 1", lukko="(lukittu) "),
        _rivi("Lukittu 2", lukko="(lukittu) ", a=3, m=3),
    )
    v = mt.valitse(mt.jasenna(t), [], karki=False)
    assert v["valittu"]["otsikko"] == "Lukittu 1"
    v = mt.valitse(mt.jasenna(t), ["Lukittu 1", "Lukittu 2"], karki=False)
    assert v["valittu"]["otsikko"] == "Iso piste"
    assert v["valittu"]["piste"] == 2 * 3 + 3 + 2 * 3 + 2 - 0


def test_myynti_painaa_kaksinkertaisesti():
    t = _backlog(_rivi("Arvo", a=3, m=1), _rivi("Myynti", a=2, m=3))
    # Arvo: 6+1+2+1-1 = 9; Myynti: 4+1+6+1-1 = 11
    assert mt.valitse(mt.jasenna(t), [], karki=False)["valittu"]["otsikko"] == "Myynti"


def test_karkivuoro_ja_kysymys():
    t = _backlog(_rivi("Korkea vanha", a=3, k=3, u=1),
                 _rivi("Uusi kyky", u=2) + "\n  - ⚠️ EHDOTUS/KYSYMYS: hinta?",
                 _rivi("Toinen uusi", u=2, k=2))
    v = mt.valitse(mt.jasenna(t), [], karki=True)
    assert v["valittu"]["otsikko"] == "Toinen uusi", "kysymysrivi ohitetaan, kärkivuoro vaatii uutuus 2"
    v = mt.valitse(mt.jasenna(t), [], karki=False)
    assert v["valittu"]["otsikko"] == "Korkea vanha"


def test_naytto_rankaisee_epaonnistuvaa_lahdetta():
    tehdyt = [_rivi(f"Vanha {i}", tehty=True, mittari="x · tarkistus 2026-10-01", lahde="(aallonharja 2026-10-01)",
                    tulokset=[(f"2026-10-0{i}", "❌", "ei")]) for i in (2, 3)]
    t = _backlog(_rivi("Aallonharjan", lahde="(aallonharja 2026-10-18, lähde: x)", a=2, m=2),
                 _rivi("Ylläpitäjän", lahde="(ylläpitäjän signaali)", a=2, m=2), tehdyt=tehdyt)
    rivit = mt.jasenna(t)
    assert mt.naytto(rivit)["aallonharja"] == -1
    v = mt.valitse(rivit, [], karki=False)
    assert v["valittu"]["otsikko"] == "Ylläpitäjän"
    assert "näyttö -1" in v["top"][1]["erittely"]


def test_oikea_backlog_jasentyy():
    rivit = mt.jasenna((JUURI / "docs" / "AUTO-BACKLOG.md").read_text(encoding="utf-8"))
    avoimet = [r for r in rivit if not r.tehty]
    assert avoimet, "backlogissa ei ole avoimia rivejä tai jäsennys hajosi"
    rikki = [r.otsikko[:60] for r in rivit if r.pisteet and r.komponentit() is None]
    assert not rikki, f"Pisteet-rivi ei jäsenny: {rikki}"
    assert not [r for r in rivit if r.tulos_virheet], "Tulos-rivi väärässä muodossa"


# ------------------------------------------------------------------ mittausdata: julkisuussääntö

def test_kokoluokka():
    assert [md.kokoluokka(n) for n in (None, 0, 3, 42, 420, 4200)] == [None, "0", "1-9", "10-99", "100-999", "1000+"]


def test_konversiosta_jaa_vain_suhdeluku():
    doc = {"total_accounts": 242, "premium_accounts": 18, "premium_web": 3, "conversion_pct_min": 2.07,
           "conversion_pct_max": 2.48, "conversion_exact": False, "comparable": True, "window_active": False}
    s = md.siivoa_konversio(doc)
    assert s["konversio_pct_min"] == 2.07
    assert "242" not in str(s) and "18" not in str(s.values())
    assert not any(k in s for k in ("total_accounts", "premium_accounts", "premium_web"))


def test_gsc_ja_posthog_ilman_absoluuttisia_maaria():
    nyt = [{"keys": ["https://goaliq.app/fpl"], "impressions": 5321, "clicks": 87, "ctr": 0.0163, "position": 7.2}]
    ennen = [{"keys": ["https://goaliq.app/fpl"], "impressions": 4000, "clicks": 50}]
    (r,) = md.siivoa_gsc(nyt, ennen, "sivu")
    assert r["nayttoja"] == "1000+" and r["ctr_pct"] == 1.63 and r["naytot_muutos_pct"] == 33.0
    assert "5321" not in str(r) and "87" not in str(r)
    (p,) = md.siivoa_posthog([["paywall_shown", 955, 800]], ["tapahtuma", "nyt", "ennen"])
    assert p == {"tapahtuma": "paywall_shown", "kokoluokka_28vrk": "100-999", "muutos_pct": 19.4}


def test_puuttuva_avain_on_puuttuu_ei_nolla():
    assert md.hae_konversio(None)["tila"] == "puuttuu"
    assert md.hae_posthog("")["tila"] == "puuttuu"
    assert md.hae_gsc(None, None)["tila"] == "puuttuu"


# ------------------------------------------------------------------ mittausdata: piikki ei ole tason muutos
# Search Consolen päivänäytöt 18.10 ajon jaksoilta (sc-domain:goaliq.app, luettu 19.10). GSC jättää
# nollapäivät pois, siksi 26.9 puuttuu nykyjaksosta.
GSC_ENNEN = dict(zip(
    [f"2026-08-{d:02d}" for d in range(21, 32)] + [f"2026-09-{d:02d}" for d in range(1, 18)],
    [586, 19, 10, 16, 17, 11, 15, 12, 10, 22, 15, 34, 26, 29, 46, 23, 39, 39, 20, 49, 35, 73, 61, 42, 47, 21, 7, 18]))
GSC_NYT = dict(zip(
    [f"2026-09-{d:02d}" for d in range(18, 26)] + [f"2026-09-{d:02d}" for d in range(27, 31)]
    + [f"2026-10-{d:02d}" for d in range(1, 16)],
    [11, 10, 4, 7, 5, 6, 18, 11, 3, 8, 3, 18, 7, 2, 7, 6, 7, 5, 7, 2, 10, 15, 8, 10, 16, 6, 9]))
GSC_DIMENSIOT = {
    "date": lambda alku: [{"keys": [p], "impressions": n, "clicks": 1}
                          for p, n in (GSC_NYT if alku >= "2026-09-18" else GSC_ENNEN).items()],
    "page": lambda alku: ([{"keys": ["https://goaliq.app/"], "impressions": 150, "clicks": 30}]
                          + ([] if alku >= "2026-09-18" else
                             [{"keys": ["https://goaliq.app/predictions/la-liga/a-vs-b"], "impressions": 431, "clicks": 0}])),
    "query": lambda alku: [{"keys": ["goaliq"], "impressions": 120, "clicks": 30},
                           {"keys": ["fpl tools"], "impressions": 40, "clicks": 3}],
}


def _vale_gsc(monkeypatch):
    import types

    class Istunto:
        def __init__(self, _cr):
            pass

        def post(self, _url, json, timeout):
            dims = json.get("dimensions")
            if dims:
                rivit = GSC_DIMENSIOT[dims[0]](json["startDate"])
            else:
                lahde = GSC_NYT if json["startDate"] >= "2026-09-18" else GSC_ENNEN
                rivit = [{"impressions": sum(lahde.values()), "clicks": 35, "ctr": 0.158, "position": 14.1}]
            return types.SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"rows": rivit})

    tr = types.ModuleType("google.auth.transport.requests")
    tr.AuthorizedSession = Istunto
    sa = types.ModuleType("google.oauth2.service_account")
    sa.Credentials = types.SimpleNamespace(from_service_account_info=lambda info, scopes: object())
    for nimi, moduuli in (("google", types.ModuleType("google")), ("google.auth", types.ModuleType("google.auth")),
                          ("google.auth.transport", types.ModuleType("google.auth.transport")),
                          ("google.auth.transport.requests", tr),
                          ("google.oauth2", types.ModuleType("google.oauth2")),
                          ("google.oauth2.service_account", sa)):
        monkeypatch.setitem(sys.modules, nimi, moduuli)
    monkeypatch.setattr(sys.modules["google.oauth2"], "service_account", sa, raising=False)
    monkeypatch.setattr(sys.modules["google.auth.transport"], "requests", tr, raising=False)


def test_gsc_piikki_vertailujaksossa_saa_tulkinnan_ja_mediaanin(monkeypatch):
    import datetime as dt
    import json

    _vale_gsc(monkeypatch)
    g = md.hae_gsc("{}", dt.date(2026, 10, 18))
    assert g["tila"] == "ok", g
    y = g["yhteensa"]
    assert y["naytot_muutos_pct"] == -83.5  # 18.10:n luku, joka luettiin pudotukseksi
    assert y["piikki_vertailujaksossa"] is True and y["huippu3_osuus_pct"]["ennen"] >= md.PIIKKI_RAJA_PCT
    assert "2026-08-21" in y["tulkinta"] and "mediaanimuutosta" in y["tulkinta"]
    # Päivämediaani 22.5 -> 7: taso laski (kauden alun ja ilmaisikkunan aikainen taso), mutta ei -83,5 %.
    assert y["naytot_mediaani_muutos_pct"] == -68.9
    assert y["brandihaut_klikeista_pct"] == 90.9
    kadonnut = [s for s in g["sivut_vertailujaksossa"] if "a-vs-b" in s["sivu"]]
    assert kadonnut and kadonnut[0]["naytot_muutos_pct"] == -100.0
    assert not [s for s in g["sivut"] if "a-vs-b" in s["sivu"]], "nykyjakson lista ei näytä kadonnutta sivua"
    teksti = json.dumps(g)
    for maara in ("586", "1342", "221", "431"):
        assert maara not in teksti, f"absoluuttinen määrä {maara} vuotaa tuotokseen"


def test_gsc_ilman_piikkia_kokonaismuutos_on_vertailukelpoinen():
    import datetime as dt

    a, b = dt.date(2026, 9, 1), dt.date(2026, 9, 28)
    tasainen = [{"keys": [(a + dt.timedelta(days=i)).isoformat()], "impressions": 10, "clicks": 1} for i in range(28)]
    t = md.gsc_paivatunnusluvut(tasainen, tasainen, a, b, a, b)
    assert t["piikki_vertailujaksossa"] is False and t["piikki_tassa_jaksossa"] is False
    assert "vertailukelpoisia" in t["tulkinta"] and t["naytot_mediaani_muutos_pct"] == 0.0


def test_gsc_puuttuva_paiva_on_nolla_ei_pois_mediaanista():
    import datetime as dt

    a, b = dt.date(2026, 9, 1), dt.date(2026, 9, 4)
    # Kaksi päivää neljästä puuttuu: oikea mediaani on 2.5 (0, 0, 5, 10), ilman täyttöä 7.5.
    nyt = [{"keys": ["2026-09-01"], "impressions": 5}, {"keys": ["2026-09-02"], "impressions": 10}]
    ennen = [{"keys": [(a + dt.timedelta(days=i)).isoformat()], "impressions": 5} for i in range(4)]
    assert md.gsc_paivatunnusluvut(nyt, ennen, a, b, a, b)["naytot_mediaani_muutos_pct"] == -50.0


def test_posthog_viikkokayttajat_ilman_maaria(monkeypatch):
    import json
    import types

    viikot = [["2026-09-07T00:00:00Z", 65, 34, 355, 7], ["2026-09-14T00:00:00Z", 39, 13, 290, 9]]

    def post(_url, headers, json, timeout):
        q = json["query"]["query"]
        tulos = viikot if "toStartOfWeek" in q else [["paywall_shown", 955, 800]] if "GROUP BY event" in q else []
        return types.SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"results": tulos})

    monkeypatch.setattr(md.requests, "post", post)
    p = md.hae_posthog("avain")
    assert p["tila"] == "ok", p
    eka, toka = p["viikkokayttajat"]
    assert eka["sovellus"] == {"kayttajia": "10-99", "muutos_edellisesta_pct": None}
    assert toka["viikko"] == "2026-09-14" and toka["sovellus"]["muutos_edellisesta_pct"] == -40.0
    assert "toStartOfWeek(now(), 1)" in md.HOGQL_VIIKOT, "kesken oleva viikko näyttäisi pudotukselta"
    teksti = json.dumps(p["viikkokayttajat"])
    for maara in ("65", "34", "355", "39", "290"):
        assert f": {maara}" not in teksti and f"[{maara}" not in teksti


def test_ostopolku_suhdeluvut_ilman_maaria(monkeypatch):
    """19.10.2026: lukko -> napautus -> osto lähteittäin ja alustoittain, vain kokoluokat ja suhteet."""
    import json
    import types

    lahteet = [["fantasy_manager", "web", 412, 37, 0, 300, 21, 0],
               ["predict_screen", "mobiili", 6, 2, 1, 4, 0, 0]]
    alustat = [["mobiili", 58, 11, 3, 61, 9, 2], ["web", 530, 44, 2, 410, 30, 1]]

    def post(_url, headers, json, timeout):
        q = json["query"]["query"]
        tulos = lahteet if "GROUP BY lahde, alusta" in q else alustat if "GROUP BY alusta" in q else []
        return types.SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"results": tulos})

    monkeypatch.setattr(md.requests, "post", post)
    p = md.hae_posthog("avain")
    assert p["tila"] == "ok", p
    o = p["ostopolku"]
    web = o["lahteittain"][0]
    assert web["lahde"] == "fantasy_manager" and web["alusta"] == "web"
    assert web["nyt"] == {"lukko": "100-999", "napautus": "10-99", "osto": "0", "napautus_lukosta_pct": 9.0,
                          "osto_napautuksesta_pct": 0.0, "pieni_otos": False}
    assert o["lahteittain"][1]["nyt"]["pieni_otos"] is True
    assert o["alustoittain"][0]["nyt"]["osto_napautuksesta_pct"] == 27.3
    assert o["lahteittain"][0]["ennen"]["napautus_lukosta_pct"] == 7.0
    teksti = json.dumps(o)
    for maara in ("412", "37", "530", "44", "300", "410"):
        assert f": {maara}" not in teksti and f"[{maara}" not in teksti, maara
    for kysely in (md.HOGQL_OSTOPOLKU_LAHTEET, md.HOGQL_OSTOPOLKU_ALUSTAT):
        assert "uniqIf(distinct_id, event = 'paywall_shown'" in kysely and "purchase_completed" in kysely


def test_ostopolun_lahde_siivotaan():
    (r,) = md.siivoa_ostopolku([["<script>x</script>" * 5, 1, 0, 0, 0, 0, 0]], ("lahde",))
    assert "<" not in r["lahde"] and len(r["lahde"]) <= 40
    assert r["nyt"]["napautus_lukosta_pct"] == 0.0 and r["nyt"]["osto_napautuksesta_pct"] is None


def test_konversio_kuljettaa_entry_id_osuuden():
    s = md.siivoa_konversio({"conversion_pct_min": 2.0, "entry_id_share_pct_free": 41.3,
                             "entry_id_share_pct_premium": 88.2})
    assert s["entry_id_osuus_pct_ilmainen"] == 41.3 and s["entry_id_osuus_pct_premium"] == 88.2
    assert md.siivoa_konversio({})["entry_id_osuus_pct_ilmainen"] is None, "puuttuva on None, ei nolla"


def test_aallonharja_kirjaa_ostopolun():
    doc = yaml.safe_load((JUURI / ".github" / "workflows" / "aallonharja.yml").read_text(encoding="utf-8"))
    prompt = next(s for s in doc["jobs"]["agentti"]["steps"] if "claude-code-action" in str(s.get("uses")))["with"]["prompt"]
    assert '"ostopolku"' in prompt and "pieni_otos" in prompt


def test_aallonharja_sulkee_mittarit_ja_tarkistaa_ne_mainin_versiolla():
    doc = yaml.safe_load((JUURI / ".github" / "workflows" / "aallonharja.yml").read_text(encoding="utf-8"))
    agentti = doc["jobs"]["agentti"]
    assert agentti["needs"] == "mittausdata"
    run = "\n".join(str(s.get("run", "")) for s in agentti["steps"])
    assert "mittarit.py\" eraantyneet" in run and "mittarit.py\" kooste" in run
    julkaise = "\n".join(str(s.get("run", "")) for s in doc["jobs"]["julkaise"]["steps"])
    assert "git show origin/main:.github/auto-kehitys/mittarit.py" in julkaise
    assert "mittarit.py\" tarkista" in julkaise
    prompt = next(s for s in agentti["steps"] if "claude-code-action" in str(s.get("uses")))["with"]["prompt"]
    assert "MITTARIEN SULKU" in prompt and "JULKISUUSSÄÄNTÖ" in prompt


def test_auto_kehitys_kayttaa_laskettua_valintaa():
    doc = yaml.safe_load((JUURI / ".github" / "workflows" / "auto-kehitys.yml").read_text(encoding="utf-8"))
    askeleet = doc["jobs"]["agentti"]["steps"]
    run = "\n".join(str(s.get("run", "")) for s in askeleet)
    assert "mittarit.py\" valitse" in run
    prompt = next(s for s in askeleet if "claude-code-action" in str(s.get("uses")))["with"]["prompt"]
    assert "/tmp/valinta.json" in prompt
