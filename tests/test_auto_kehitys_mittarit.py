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
