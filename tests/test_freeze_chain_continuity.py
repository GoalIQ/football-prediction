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
