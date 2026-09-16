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
