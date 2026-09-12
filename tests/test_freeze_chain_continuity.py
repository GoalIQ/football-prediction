"""Jaadytetty runko ei voi muuttua enempaa kuin sen oma siirtoloki sanoo (12.9.2026).

🔴 MIKSI TAMA ON OLEMASSA. GW4:n freeze (`frozen_at 2026-09-11T07:45:25Z`)
kirjoitti rungon jossa **8 pelaajaa 15:sta oli vaihtunut edellisesta**, samalla
kun sen oma meta sanoi `transfers: []` ja `hits: 0`. Artefakti oli siis
ristiriidassa itsensa kanssa: "malli ei tehnyt yhtaan siirtoa" ja "kahdeksan
pelaajaa vaihtui" samassa tiedostossa. Sen tuottanut CI-ajo (34575124438) oli
**vihrea**, koska katkeaminen tulostettiin paljaana `print`ina askelella jolla
on `continue-on-error: true`.

Kolme asiaa joita ei ollut:
  1. Kentta `squad_rebuilt` oli **write-only**: koko repossa yksi osuma, se
     joka kirjoittaa sen. Ei lukijaa, ei testia.
  2. `squad_source` laskettiin pelkasta "onko edellista freezea olemassa", ei
     siita kaytettiinko sita. gw4.json sanoo `"chain"` vaikka runko
     rakennettiin alusta.
  3. Yksikaan testi ei verrannut kahta perakkaista freezea toisiinsa.

Tama testi mittaa invariantin **jokaisesta jaadytetysta kierroksesta joka
ajossa**, ei vain nykyisesta. Kauden vaiheeseen sidottu testi on vihrea siihen
asti kun se lakkaa olemasta tosi (CLAUDE.md saanto 6a, kohta 3).

POIKKEUSLISTA. Rikkinainen kierros ei paase listalle vahingossa: sille on
kirjoitettava syy tahan tiedostoon, jolloin tietoinen valinta nakyy diffissa.
Vanhentunut poikkeus (rivi joka ei enaa riko invarianttia) kaataa myos testin,
jottei lista kasva hiljaa.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "data" / "model_squad_frozen"

#: gw -> perustelu. Jokainen rivi on tietoinen paatos, ei unohdus.
KETJUPOIKKEUKSET: dict[int, str] = {
    4: (
        "Mitattu 12.9.2026. Ketju katkesi hiljaa: gw3.json:n rungossa oli "
        "Dovin (171, 'joined Leyton Orient on loan'), jonka saatavuussuodatin "
        "oli pudottanut xP-artefaktista. `_constrained_from_prev` palautti "
        "None ja `main()` pudotti vapaaseen optimiin -> 8/15 vaihtui, "
        "transfers=[] ja hits=0. Freeze on immutable eika sita korjata "
        "takautuvasti; syy on korjattu (ketju rakentaa poissaolevan jasenen "
        "bootstrapista, ja fallback vapaaseen optimiin on nyt exit 1). "
        "Rivin kohtalo (gradataanko GW4) on Villen paatos, ks. "
        "cos-reports/cc-reports/2026-09-12-freeze-ketju-katkesi-hiljaa.md"
    ),
}


def _lataa() -> dict[int, dict]:
    out: dict[int, dict] = {}
    if not FROZEN.exists():
        return out
    for p in FROZEN.glob("gw*.json"):
        m = re.fullmatch(r"gw(\d+)\.json", p.name)
        if not m:
            continue
        out[int(m.group(1))] = json.loads(p.read_text(encoding="utf-8"))
    return out


def _idt(f: dict) -> set[int]:
    return {p["id"] for p in (f.get("xi") or []) + (f.get("bench") or [])}


def _lahde(meta: dict) -> str:
    """Vanhoissa tiedostoissa `squad_source` puuttuu — johda se tosiasioista."""
    s = meta.get("squad_source")
    if s:
        return str(s)
    if meta.get("reseed"):
        return "entry_picks"
    return "chain" if isinstance(meta.get("from_gw"), int) else "free_optimum"


def _rikkoo(gw: int, frozen: dict[int, dict]) -> str | None:
    """Rikkooko GW invarianttia? Palauttaa syyn tai None."""
    if gw - 1 not in frozen:
        return None
    return _rikkoo_pari(gw, frozen[gw], frozen[gw - 1])


def _rikkoo_pari(gw: int, cur: dict, prev: dict) -> str | None:
    """Sama tarkistus kahdelle dictille — jotta se on ajettavissa
    synteettisella parilla eika vain levylla olevalla kaudella."""
    meta = cur.get("meta") or {}
    lahde = _lahde(meta)
    muutokset = len(_idt(prev) - _idt(cur))
    siirrot = meta.get("transfers") or []

    if lahde == "entry_picks":
        rs = meta.get("reseed") or {}
        puuttuu = [k for k in ("gw", "source_gw", "reason", "decided_by",
                               "decided_at") if not str(rs.get(k) or "").strip()]
        if puuttuu:
            return (f"squad_source=entry_picks mutta reseed-lohkosta puuttuu "
                    f"{puuttuu} — reseed ei ole vapaakortti ilman perustelua")
        return None

    if lahde == "free_optimum":
        return ("runko rakennettu alusta vaikka GW{}:lle on edellinen freeze "
                "— vapaa optimi on laillinen vain kauden ensimmaisella "
                "jaadytyksella".format(gw))

    # chain
    if meta.get("squad_rebuilt") is True:
        return ("squad_source='chain' ja squad_rebuilt=True samassa metassa "
                "— artefakti on ristiriidassa itsensa kanssa")
    if not isinstance(meta.get("from_gw"), int):
        return "squad_source='chain' mutta from_gw ei ole kierrosnumero"
    if muutokset != len(siirrot):
        return (f"{muutokset} pelaajaa vaihtui mutta siirtoloki sanoo "
                f"{len(siirrot)} siirtoa")
    # FPL:n saanto, ei moottorin katto: siirtoja saa tehda niin monta kuin on
    # vapaita + hitteja, ja jokainen ylimaarainen maksaa -4. Moottorin oma
    # `MAX_TRANSFERS_PER_GW` on eri asia (se rajaa hakua, ei laillisuutta) —
    # jos tama testi lukisi sita, GW2 (1 vapaa + 2 hittia = 3 siirtoa)
    # nayttaisi laittomalta vaikka se on tasan FPL:n saantojen mukainen.
    ft = int(meta.get("ft_available") or 1)
    hitit = int(meta.get("hits") or 0)
    if len(siirrot) > ft + hitit:
        return (f"{len(siirrot)} siirtoa mutta {ft} vapaata + {hitit} hittia "
                f"= enintaan {ft + hitit}")
    odotetut_hitit = max(0, len(siirrot) - ft)
    if hitit != odotetut_hitit:
        return (f"{len(siirrot)} siirtoa ja {ft} vapaata -> hitteja pitaisi "
                f"olla {odotetut_hitit}, metassa {hitit}")
    merkityt = sum(1 for s in siirrot if s.get("hit"))
    if merkityt != hitit:
        return (f"siirtolokissa {merkityt} hit-merkintaa mutta meta.hits on "
                f"{hitit}")
    return None


FROZEN_GWS = sorted(_lataa())


@pytest.mark.parametrize("gw", FROZEN_GWS)
def test_muutosten_maara_vastaa_siirtolokia(gw):
    """Jokainen jaadytetty kierros, ei vain nykyinen."""
    frozen = _lataa()
    syy = _rikkoo(gw, frozen)
    if gw in KETJUPOIKKEUKSET:
        pytest.skip(f"kirjattu poikkeus GW{gw}: {KETJUPOIKKEUKSET[gw]}")
    assert syy is None, f"GW{gw}: {syy}"


def test_poikkeuslista_ei_sisalla_ehjia_kierroksia():
    """Vanhentunut poikkeus poistetaan. Lista ei saa kasvaa hiljaa."""
    frozen = _lataa()
    turhat = [gw for gw in KETJUPOIKKEUKSET
              if gw in frozen and _rikkoo(gw, frozen) is None]
    assert not turhat, (
        f"GW{turhat} eivat riko invarianttia — poista rivi "
        f"KETJUPOIKKEUKSET-listalta")


def test_poikkeuksella_on_perustelu():
    for gw, syy in KETJUPOIKKEUKSET.items():
        assert len(syy.strip()) >= 80, (
            f"GW{gw}:n poikkeus on liian lyhyt ollakseen perustelu")


def _pari(prev_ids, cur_ids, meta):
    def f(ids):
        r = [{"id": i} for i in ids]
        return {"xi": r[:11], "bench": r[11:]}
    cur = f(cur_ids)
    cur["meta"] = meta
    return cur, f(prev_ids)


# ---------------------------------------------------------------------------
# Mutaatiotestit: nappaako mittari muutoksen ILMAN etta artefakti tunnustaa
# sen itse? Ilman naita testi lepaisi yhden kentan (`squad_rebuilt`) varassa,
# ja toinen mekanismi joka tuottaa saman lopputuloksen menisi lapi.
# ---------------------------------------------------------------------------
def test_kahdeksan_vaihtoa_ilman_siirtolokia_kaataa():
    """GW4:n oikea muoto, mutta `squad_rebuilt` rehellisesti False.

    Tama on se tapaus jota vastaan portti on rakennettu: jos jokin TOINEN
    polku tuottaa saman rungon eika merkitse itseaan uudelleenrakennetuksi,
    muutoslaskurin on purtava yksin.
    """
    cur, prev = _pari(range(1, 16), list(range(1, 8)) + list(range(100, 108)),
                      {"squad_source": "chain", "squad_rebuilt": False,
                       "from_gw": 3, "transfers": [], "hits": 0,
                       "ft_available": 1})
    syy = _rikkoo_pari(4, cur, prev)
    assert syy and "8 pelaajaa vaihtui" in syy, syy


def test_hittien_maara_ei_saa_olla_keksitty():
    """3 siirtoa ja 1 vapaa -> 2 hittia. Muu luku on kirjanpitovirhe joka
    tekisi kaudesta halvemman nakoisen kuin se oli."""
    cur, prev = _pari(range(1, 16), list(range(1, 13)) + [101, 102, 103],
                      {"squad_source": "chain", "squad_rebuilt": False,
                       "from_gw": 1,
                       "transfers": [{"out": 13, "in": 101, "hit": False},
                                     {"out": 14, "in": 102, "hit": True},
                                     {"out": 15, "in": 103, "hit": True}],
                       "hits": 0, "ft_available": 1})
    syy = _rikkoo_pari(2, cur, prev)
    assert syy and "hittia" in syy, syy
    # Ja toisin pain: hitteja LIIKAA. Katto ei pure (4 >= 3), joten talle
    # tarvitaan oma ehtonsa — muuten kausi nayttaisi kalliimmalta kuin oli.
    cur["meta"]["hits"] = 3
    syy2 = _rikkoo_pari(2, cur, prev)
    assert syy2 and "hitteja pitaisi olla 2" in syy2, syy2


def test_laillinen_ketju_menee_lapi():
    """Negatiivinen kontrolli: portti ei saa olla aina punainen."""
    cur, prev = _pari(range(1, 16), list(range(1, 15)) + [101],
                      {"squad_source": "chain", "squad_rebuilt": False,
                       "from_gw": 3,
                       "transfers": [{"out": 15, "in": 101, "hit": False}],
                       "hits": 0, "ft_available": 1})
    assert _rikkoo_pari(4, cur, prev) is None


def test_reseed_ilman_perustelua_kaataa():
    cur, prev = _pari(range(1, 16), range(100, 115),
                      {"squad_source": "entry_picks", "squad_rebuilt": False,
                       "reseed": {"gw": 4, "source_gw": 3, "reason": "",
                                  "decided_by": "", "decided_at": ""}})
    syy = _rikkoo_pari(4, cur, prev)
    assert syy and "reseed" in syy, syy


def test_ketju_ei_saa_pudota_vapaaseen_optimiin():
    """🔴 Lahdekoodin invariantti, ei vain artefaktin.

    Ilman tata `main()`:n haara voisi palata hiljaiseksi fallbackiksi ilman
    etta yksikaan artefaktitesti huomaisi mitaan — vika nakyisi vasta
    seuraavassa jaadytetyssa tiedostossa, eli kierroksen myohassa ja
    peruuttamattomasti.
    """
    src = (ROOT / "scripts" / "freeze_model_squad_gw.py").read_text(
        encoding="utf-8")
    # Katkeamishaaran on paatyttava exit 1:een, ei jatkoon.
    i = src.find("if rajoitettu is None:")
    assert i > 0, "katkeamishaaraa ei loydy — onko se nimetty uudelleen?"
    haara = src[i:i + 2000]
    loppu = haara.find("else:")
    assert loppu > 0
    assert "return 1" in haara[:loppu], (
        "ketjun katkeaminen ei paady exit 1:een — vapaa optimi voisi jalleen "
        "korvata peritun rungon hiljaa")


# ---------------------------------------------------------------------------
# 🔴 KAYTOSTESTI, EI MERKKIJONOPORTTI (lisatty 12.9 illalla tarkistuksen jalkeen)
#
# Ensimmainen versio talla tiedostolla vartioi katkeamishaaraa GREPPAAMALLA
# lahdekoodista "return 1". Adversariaalinen tarkistus mittasi sen: kun
# `main()`:n haara mutatoitiin takaisin hiljaiseksi fallbackiksi, **koko 4207
# testin suite pysyi vihreana** — merkkijonoportti ei voi erottaa kommenttia
# koodista, ja se osui omaan perustelukommenttiinsa.
#
# Tama ajaa `main()`:n oikeasti ja vaatii kaksi asiaa: exit 1 JA ettei
# yhtaan gw*.json-tiedostoa kirjoiteta. Positiivinen kontrolli samalla
# koneistolla todistaa etta portti voi myos olla vihrea oikeasta syysta —
# ja se kantaa samalla `squad_source`-invariantin, joka on tosi vain niin
# kauan kuin kieltaytyminen on paikallaan.
# ---------------------------------------------------------------------------
def _freeze_moduuli():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "freeze_model_squad_gw", ROOT / "scripts" / "freeze_model_squad_gw.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


#: Laillinen 15: 2 GKP, 5 DEF, 5 MID, 3 FWD, enintaan 3 per seura.
_POS15 = {1: 1, 2: 1, 3: 2, 4: 2, 5: 2, 6: 2, 7: 2,
          8: 3, 9: 3, 10: 3, 11: 3, 12: 3, 13: 4, 14: 4, 15: 4}


#: Isompi universumi: runko on 1-15, loput ovat vaihtoehtoja. Poolin on oltava
#: riittava jotta `free_optimum` ONNISTUU — muuten kieltaytymistesti ei erottele.
#: Mitattu 12.9: 14 pelaajan poolilla `free_optimum` heitti RateTeamErrorin, ja
#: testi lapaisi vaarasta syysta (rc 1 tuli virheesta eika kieltaytymisesta).
_POS40 = {}
for _i in range(1, 41):
    _POS40[_i] = _POS15.get(_i) or (1 if _i % 8 == 0 else
                                    2 if _i % 3 == 0 else
                                    3 if _i % 3 == 1 else 4)


def _pooli(ids, gw=4):
    return [{"id": i, "element_type": _POS40[i], "price": 45,
             "club": ((i - 1) % 14) + 1, "web_name": f"P{i}", "team_short": "AAA",
             "owned_pct": 1.0, "status": "a", "chance_next": 100,
             "xp_horizon_total": 5.0 + i * 0.01,
             "xp_per_gw": 0.8,
             "gameweeks": [{"gw": g, "xp": 0.8 + i * 0.001}
                           for g in range(gw, gw + 6)]}
            for i in ids]


def _boot(ids):
    return {
        "elements": [{"id": i, "web_name": f"P{i}",
                      "element_type": _POS40.get(i, 3),
                      "team": ((i - 1) % 5) + 1, "now_cost": 50, "status": "u",
                      "news": "left", "selected_by_percent": "0.1",
                      "chance_of_playing_next_round": 0} for i in ids],
        "teams": [{"id": c, "name": f"T{c}", "short_name": f"T{c}"}
                  for c in range(1, 6)],
    }


def _laita_freeze(dir_, gw, ids):
    rivit = [{"id": i, "web_name": f"P{i}", "pos": _POS40[i], "price": 45,
              "club": ((i - 1) % 14) + 1} for i in ids]
    d = {"meta": {"gw": gw, "budget": 100.0, "ft_left": 0,
                  "deadline": "2026-09-04T17:30:00Z"},
         "captain": rivit[0]["id"], "vice_captain": rivit[1]["id"],
         "xi": rivit[:11], "bench": rivit[11:]}
    (dir_ / f"gw{gw}.json").write_text(
        json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8", newline="\n")


def _aja_freeze_main(monkeypatch, tmp_path, *, bootstrap_ids):
    """Aja main() tmp-hakemistossa. gw3 on jaadytetty, id 15 puuttuu poolista."""
    m = _freeze_moduuli()
    _laita_freeze(tmp_path, 3, list(range(1, 16)))
    monkeypatch.setattr(m, "FROZEN_DIR", tmp_path)
    monkeypatch.setattr(m, "RESEED_DIR", tmp_path / "ei-reseedeja")
    monkeypatch.setattr(m, "next_freeze_gw", lambda events, now: (
        4, _dt.datetime(2026, 9, 12, 12, 30, tzinfo=_dt.timezone.utc)))
    monkeypatch.setattr(m, "entry_mismatch", lambda *a, **k: "")
    monkeypatch.setattr(m, "_entry_history",
                        lambda *a, **k: ({"value": 1000, "bank": 0}, None))
    monkeypatch.setattr(m, "budget_from_history", lambda h: 100.0)

    class _R:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"events": []}

    monkeypatch.setattr(m.requests, "get", lambda *a, **k: _R())

    # Runko on 1-15; id 15 EI ole poolissa, mutta 16-40 ovat -> vapaa optimi
    # ONNISTUISI jos kieltaytyminen poistettaisiin, ja silloin testi kaatuu.
    pool = _pooli(list(range(1, 15)) + list(range(16, 41)))
    boot = _boot(bootstrap_ids)
    xp = {"meta": {"generated_at": "2026-09-11T07:39:11+00:00"}}
    import src.models.fpl_rate_team as rt
    monkeypatch.setattr(rt, "build_context",
                        lambda *a, **k: (xp, boot, pool, {p["id"]: p for p in pool}))
    return m, m.main(), tmp_path / "gw4.json"


def test_main_kieltaytyy_kun_jasenta_ei_ole_missaan_lahteessa(
        monkeypatch, tmp_path, capsys):
    """🔴 Ydintesti. Ilman tata koko commitin vaite ei pida."""
    _m, rc, out = _aja_freeze_main(monkeypatch, tmp_path, bootstrap_ids=[])
    teksti = capsys.readouterr().out
    assert rc == 1, "ketjun katkeaminen ei johtanut kieltaytymiseen"
    assert not out.exists(), (
        "gw4.json KIRJOITETTIIN vaikka runkoa ei voitu peria — tasan se vika "
        "jota tama tiedosto vartioi (8/15 vaihtui 11.9)")
    assert "::error::" in teksti
    assert "vapaata optimia" in teksti


def test_main_perii_ketjun_kun_jasen_on_bootstrapissa(monkeypatch, tmp_path):
    """Positiivinen kontrolli JA `squad_source`-invariantti.

    `squad_source` voi olla totuudenmukainen vain niin kauan kuin
    kieltaytyminen ylla on paikallaan: sen jalkeen `siirtotiedot is None`
    ketjupolulla on mahdoton tila. Siksi nama kaksi testia kuuluvat yhteen.
    """
    _m, rc, out = _aja_freeze_main(monkeypatch, tmp_path, bootstrap_ids=[15])
    assert rc == 0, "ketju olisi pitanyt onnistua bootstrap-rekonstruktiolla"
    assert out.exists(), "laillinen runko jai kirjoittamatta"
    d = json.loads(out.read_text(encoding="utf-8"))
    meta = d["meta"]
    assert meta["squad_source"] == "chain"
    assert meta["squad_rebuilt"] is False
    assert meta["from_gw"] == 3
    assert len(meta["transfers"]) <= 2
    assert len(_idt(d)) == 15
    # Ja invariantti pitaa myos taman uuden parin yli.
    prev = json.loads((tmp_path / "gw3.json").read_text(encoding="utf-8"))
    assert _rikkoo_pari(4, d, prev) is None


def test_frozen_gws_ei_saa_olla_tyhja():
    """🔴 Tyhja parametrisointi raportoituu `1 skipped` — tasan sama rivi
    yhteenvedossa kuin GW4:n tarkoituksellinen skip. Ilman tata kauden
    tyhjentyminen nayttaisi identtiselta vihrealta ajolta."""
    assert len(FROZEN_GWS) >= 2, (
        f"jaadytettyja kierroksia {FROZEN_GWS} — invariantti tarvitsee "
        f"vahintaan parin ollakseen mitattavissa")


def test_ketjussa_ei_ole_aukkoja():
    """Kausi on ketju, mutta invariantti mittaa pareja: jos valista puuttuu
    kierros, `_rikkoo` palauttaa None eika mitaan verrata."""
    puuttuu = [g for g in range(min(FROZEN_GWS), max(FROZEN_GWS) + 1)
               if g not in FROZEN_GWS]
    assert not puuttuu, (
        f"jaadytetysta ketjusta puuttuu GW{puuttuu} — naiden ymparilla "
        f"invariantti ei mittaa mitaan")


def test_kieltaytyminen_puree_OIKEALLA_poolilla(monkeypatch, tmp_path):
    """🔴 Tama on se testi joka erottelee — ja sen loytyminen vaati kolme yritysta.

    Mitattu 12.9 illalla: synteettisella poolilla `main()` palauttaa 1 vaikka
    MOLEMMAT kieltaytymisguardit poistetaan, koska `free_optimum` ei onnistu
    tekopoolissa ja kolmas tarkistus (`runko vajaa`) nappaa sen. Testi
    lapaisi siis oikeasta lopputuloksesta vaarasta syysta — tasan se
    vikaluokka jota koko tama tiedosto vartioi.

    Tassa pooli on repon OIKEA pooli, jolla `free_optimum` onnistuu. Silloin
    guardin poisto **kirjoittaa gw-tiedoston**, ja tama testi kaatuu.
    Bootstrap annetaan tyhjana, joten poolista puuttuva rungon jasen ei ole
    rekonstruoitavissa -> kieltaytyminen on oikea vastaus.
    """
    proj = ROOT / "data" / "fpl_xp_projections.json"
    gw3 = FROZEN / "gw3.json"
    if not proj.exists() or not gw3.exists():
        pytest.skip("artefaktit puuttuvat (ei generoitu tassa ymparistossa)")

    from src.models.fpl_rate_team import build_context
    try:
        xp, boot, pool, _ = build_context()
    except Exception:                                # noqa: BLE001
        pytest.skip("build_context ei onnistu tassa ymparistossa")

    prev = json.loads(gw3.read_text(encoding="utf-8"))
    poissa = [p["id"] for p in (prev.get("xi") or []) + (prev.get("bench") or [])
              if p["id"] not in {q["id"] for q in pool}]
    if not poissa:
        pytest.skip("gw3:n rungossa ei ole poolin ulkopuolista jasenta")

    m = _freeze_moduuli()
    (tmp_path / "gw3.json").write_text(gw3.read_text(encoding="utf-8"),
                                       encoding="utf-8", newline="\n")
    monkeypatch.setattr(m, "FROZEN_DIR", tmp_path)
    monkeypatch.setattr(m, "RESEED_DIR", tmp_path / "ei-reseedeja")
    monkeypatch.setattr(m, "next_freeze_gw", lambda e, n: (
        4, _dt.datetime(2026, 9, 12, 12, 30, tzinfo=_dt.timezone.utc)))
    monkeypatch.setattr(m, "entry_mismatch", lambda *a, **k: "")
    monkeypatch.setattr(m, "_entry_history",
                        lambda *a, **k: ({"value": 1000, "bank": 0}, None))
    monkeypatch.setattr(m, "budget_from_history", lambda h: 100.0)

    class _R:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"events": []}

    monkeypatch.setattr(m.requests, "get", lambda *a, **k: _R())
    import src.models.fpl_rate_team as rt
    # Tyhja bootstrap -> rekonstruktio ei onnistu. Pooli on OIKEA.
    monkeypatch.setattr(rt, "build_context", lambda *a, **k: (
        xp, {"elements": [], "teams": []}, pool, {p["id"]: p for p in pool}))

    rc = m.main()
    kirjoitettu = sorted(p.name for p in tmp_path.glob("gw*.json"))
    assert rc == 1, f"odotettiin kieltaytymista, sain rc={rc}"
    assert kirjoitettu == ["gw3.json"], (
        f"gw4.json kirjoitettiin vaikka runkoa ei voitu peria: {kirjoitettu}. "
        f"Vapaa optimi korvasi peritun rungon hiljaa — poissa poolista: {poissa}")
