"""PORTTI: /api/fantasy/xp:n ETag kantaa jokaisen osan joka erottaa vastaukset.

🔴 MITATTU VIKA 16.9: ETag-lauseke oli
`'W/"xp-{}-{}-{}-{}{}"'.format(lg, generated, mask, schema, why, trend)` —
VIISI paikanpidinta, KUUSI argumenttia. `str.format` ei kaadu ylimaarasesta,
joten `trend_tag` katosi aanettomasti. Seuraus olisi ollut: kun uusi
deadline-freeze ilmestyy (gw4 -> gw5), `generated_at` voi olla sama, ETag
sama, ja ehdollinen pyynto olisi validoinut vanhan vastauksen 304:lla —
minuuttitrendi olisi nayttanyt EDELLISEN kierroksen eroa tasan niille joilla
vastaus on jo valimuistissa.

Vika loytyi vain siksi etta tulostin ETagin silmilla. Tama testi tekee siita
mitattavan: jokainen osa on oltava vastauksen ETagissa, ja paikanpitimia on
oltava yhta monta kuin argumentteja.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import api.main as m

client = TestClient(m.app)
ROOT = Path(__file__).resolve().parents[1]


def _etag() -> str:
    r = client.get("/api/fantasy/xp")
    assert r.status_code == 200
    tag = r.headers.get("etag")
    assert tag, "ETag puuttuu kokonaan"
    return tag


def test_etag_kantaa_kaikki_erottavat_osat() -> None:
    tag = _etag()
    for osa, mita in (
        ("xp-fpl", "liiga"),
        ("-f-", "mask-bitti"),
        ("-s", "skeemaversio"),
        ("-en", "kieli"),
        ("-mt", "minuuttitrendin vertailukohta"),
    ):
        assert osa in tag, f"{mita} puuttuu ETagista: {tag}"


def test_paikanpitimia_on_yhta_monta_kuin_argumentteja() -> None:
    """Juurisyy: `format` nielaisee ylimaarasen argumentin.

    Luetaan LAUSEKE eika ajonaikaista ETagia: ajonaikainen tag ei paljasta
    puuttuvaa osaa jos se sattuu olemaan tyhja merkkijono juuri nyt.
    AST eika regex — ensimmainen versioni laski pilkkuja merkkijonosta ja
    laski mukaan KOMMENTTIEN pilkut (6 vs 9). Portti joka laskee vaarin on
    pahempi kuin ei porttia.
    """
    import ast

    src = (ROOT / "api" / "main.py").read_text(encoding="utf-8")
    puu = ast.parse(src)
    kutsut = [
        n for n in ast.walk(puu)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute) and n.func.attr == "format"
        and isinstance(n.func.value, ast.Constant)
        and isinstance(n.func.value.value, str)
        and n.func.value.value.startswith('W/"xp-')
    ]
    assert len(kutsut) == 1, f"xp-ETag-lauseketta ei loytynyt yksiselitteisesti ({len(kutsut)})"
    kutsu = kutsut[0]
    paikat = kutsu.func.value.value.count("{}")
    args = len(kutsu.args)
    assert paikat == args, (
        f"ETag-muodossa {paikat} paikanpidinta mutta {args} argumenttia - "
        "format ei kaadu ylimaarasesta, osa katoaa aanettomasti")


def test_ehdollinen_pyynto_validoituu_samalla_tagilla() -> None:
    """Positiivinen kontrolli: jos 304-polku ei toimi, koko ETag on koriste."""
    tag = _etag()
    r = client.get("/api/fantasy/xp", headers={"if-none-match": tag})
    assert r.status_code == 304, r.status_code


def test_eri_kieli_ei_validoidu_ristiin() -> None:
    """Negatiivinen kontrolli samalle polulle."""
    tag = _etag()
    r = client.get("/api/fantasy/xp?lang=es", headers={"if-none-match": tag})
    assert r.status_code == 200, "es-vastaus validoitui en-tagilla"


# --------------------------------------------------------------------------
# 18.9 (SPA:n haarojen purku): IKKUNAN ARVO, ei vain skeemaversio.
# --------------------------------------------------------------------------
def _xp_with_deadline(dl_gw: int) -> dict:
    """Tuotantoartefakti jossa `deadline_gameweek` on siirretty mutta
    `generated_at` LUKITTU. Tasan se tila jota ETag ei erottanut."""
    import copy
    import io
    import json

    raw = json.load(io.open(ROOT / "data" / "fpl_xp_projections.json",
                            encoding="utf-8"))
    d = copy.deepcopy(raw)
    d["meta"]["deadline_gameweek"] = dl_gw
    d["meta"]["generated_at"] = "2026-09-18T07:49:39+00:00"
    return d


def test_ikkunan_arvo_on_etagissa_ei_vain_skeemaversio(monkeypatch) -> None:
    """🔴 EROTTELEVA FIKSTUURI: vaara haara oikeasti onnistuisi ilman tata.

    Mitattu 18.9 tulostetusta ETagista (ei koodista): samalla
    `generated_at`illa arvoilla deadline_gameweek 5 / 6 / 7 vastauksen summa
    oli 38.48 / 31.97 / 26.30 ja otsikko "6 GWs" / "5 GWs" / "4 GWs", mutta
    ETag oli kolmesti IDENTTINEN ja ehdollinen pyynto vastasi 304 — eli
    klientti olisi nayttanyt VANHAN summan UUDEN ikkunan otsikon alla, tasan
    niille joilla vastaus on jo valimuistissa. `schema` erottaa kentan
    OLEMASSAOLON, ei sen ARVOA.

    Tama testi kaatuu jos `hw`-osa poistetaan ETagista: silloin kaikki kolme
    tagia ovat taas samoja. Se EI nojaa siihen etta `deadline_gameweek` on
    tanaan artefaktissa — juuri se sidos on se jota ei saa olettaa.
    """
    import src.models.fpl_xp as fx

    tagit, summat, ikkunat = [], [], []
    for dl in (5, 6, 7):
        monkeypatch.setattr(fx, "load_xp", lambda path=None, _d=dl: _xp_with_deadline(_d))
        r = client.get("/api/fantasy/xp")
        assert r.status_code == 200, r.status_code
        body = r.json()
        tagit.append(r.headers["etag"])
        summat.append(body["players"][0]["xp_horizon_total"])
        ikkunat.append(body["meta"]["horizon_total_gw"])

    assert len(set(summat)) == 3, f"fikstuuri ei erota tiloja: {summat}"
    assert len(set(ikkunat)) == 3, f"fikstuuri ei erota ikkunoita: {ikkunat}"
    assert len(set(tagit)) == 3, (
        "ETag ei erota vaikutettavan kierroksen ARVOA - kolme eri summaa "
        f"({summat}) sai tagit {tagit}")


def test_vanha_ikkuna_ei_validoi_uutta_vastausta(monkeypatch) -> None:
    """Positiivinen kontrolli 304-polulle: tagi ei ole koriste."""
    import src.models.fpl_xp as fx

    monkeypatch.setattr(fx, "load_xp", lambda path=None: _xp_with_deadline(5))
    vanha = client.get("/api/fantasy/xp").headers["etag"]
    # sama ikkuna -> 304 (muuten testi olisi vihrea vain siksi ettei mikaan
    # validoidu)
    assert client.get("/api/fantasy/xp",
                      headers={"if-none-match": vanha}).status_code == 304
    monkeypatch.setattr(fx, "load_xp", lambda path=None: _xp_with_deadline(6))
    r = client.get("/api/fantasy/xp", headers={"if-none-match": vanha})
    assert r.status_code == 200, (
        "deadline siirtyi (summa 38.48 -> 31.97) mutta vanha ETag validoi "
        "vastauksen 304:lla")


def test_etag_kantaa_ikkunaosan() -> None:
    assert "-hw" in _etag(), "ikkunaosa puuttuu ETagista"
