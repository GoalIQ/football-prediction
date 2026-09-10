"""I18N-SVELTE-PARITEETTIPORTTI (10.9.2026).

Sama englanninkielinen lause elaa kahdessa paikassa: mobiilin
`lib/i18n/en.ts`-avain ja SPA:n Svelte-komponentin kovakoodattu teksti.
Drift on toteutunut kahdesti (7.9: sama epatosi lause monistui neljaan
tiedostoon kasin; `points_net`-migraatio jai SPA:sta kokonaan koska mikaan ei
verrannut tyyppeja). Tama portti mittaa ARVOA, ei substringia: en.ts-avaimen
koko lause normalisoituna (paikkamerkit -> yksi token) on loydyttava Svelten
normalisoidusta tekstista kokonaisena, ja `LastFinishedGw`-tyypin
kenttajoukko on sama molemmissa repoissa.

Kaksirepoinen: skippaa kun goaliq-app ei ole checkoutattu (CI).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

FP = Path(__file__).resolve().parents[1]
APP = FP.parent / "goaliq-app"
SPA = FP / "web" / "pro-spa" / "src" / "lib"
EN = APP / "lib" / "i18n" / "en.ts"
API_TS = APP / "lib" / "api.ts"

# en.ts-avain -> Svelte-tiedosto jossa sama lause on kovakoodattuna.
# Lisays tahan on vaite: "nama kaksi ovat sama lause". Jos SPA:n lause
# muuttuu tarkoituksella, muuta en.ts (tai poista pari perustelun kanssa).
PAIRS = [
    ("fantasy.manager.score_beat_model", "components/TeamPitchManager.svelte"),
    ("fantasy.manager.score_model_beat", "components/TeamPitchManager.svelte"),
    ("fantasy.manager.score_level", "components/TeamPitchManager.svelte"),
    ("fantasy.manager.score_average", "components/TeamPitchManager.svelte"),
    ("fantasy.manager.score_rank", "components/TeamPitchManager.svelte"),
    ("fantasy.manager.score_xp_line", "components/TeamPitchManager.svelte"),
    ("fantasy.manager.luck_note", "components/TeamPitchManager.svelte"),
    ("fantasy.manager.result_projected", "components/TeamPitchManager.svelte"),
    ("fantasy.review.title", "components/GwReview.svelte"),
    ("fantasy.review.coverage", "components/GwReview.svelte"),
    ("fantasy.review.provisional_generic", "components/GwReview.svelte"),
    ("fantasy.review.transfer_cost", "components/GwReview.svelte"),
    ("fantasy.review.worst", "components/GwReview.svelte"),
    ("fantasy.review.best", "components/GwReview.svelte"),
]

TOKEN = "§"


def _need_app():
    if not EN.exists() or not API_TS.exists():
        pytest.skip("goaliq-app ei ole checkoutattu, pariteettia ei voi verrata")


def _en_values() -> dict[str, str]:
    txt = EN.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r'^\s*"([a-z0-9_.]+)":\s*"((?:[^"\\]|\\.)*)",?\s*$', txt, re.M):
        out[m.group(1)] = m.group(2).replace('\\"', '"').replace("\\'", "'")
    return out


def _strip_braces(s: str) -> str:
    """Korvaa {…} ja ${…} (myos sisakkaiset) yhdella tokenilla."""
    out, depth, i = [], 0, 0
    while i < len(s):
        ch = s[i]
        if ch == "$" and s[i + 1:i + 2] == "{":
            i += 1
            continue
        if ch == "{":
            if depth == 0:
                out.append(TOKEN)
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
        i += 1
    return "".join(out)


def _norm(s: str) -> str:
    s = _strip_braces(s)
    s = re.sub(r"<[^>]+>", " ", s)          # tagit
    s = s.replace("\\u00b7", "·").replace("&#x27;", "'")
    s = re.sub(r"\s+", " ", s)
    # Svelte-ehtolohkojen jaannokset ({#if …} poistui tokeniksi) eivat ole tekstia
    return s.strip()


def _svelte_norm(rel: str) -> str:
    return _norm((SPA / rel).read_text(encoding="utf-8"))


def _en_norm(v: str) -> str:
    return _norm(v)


@pytest.mark.parametrize("key,rel", PAIRS, ids=[k for k, _ in PAIRS])
def test_en_key_sentence_exists_verbatim_in_svelte(key, rel):
    _need_app()
    values = _en_values()
    assert key in values, f"{key} puuttuu en.ts:sta"
    want = _en_norm(values[key])
    have = _svelte_norm(rel)
    assert want and want in have, (
        f"{key}: en.ts sanoo\n  {want!r}\nmutta {rel} ei sisalla sita samana lauseena. "
        "Kumpi on oikein? Korjaa toinen, ala molempia erikseen.")


def test_negative_control_mutated_sentence_is_not_found():
    _need_app()
    v = _en_values()["fantasy.manager.score_level"]
    assert _en_norm(v) in _svelte_norm("components/TeamPitchManager.svelte")
    assert _en_norm(v + " today") not in _svelte_norm("components/TeamPitchManager.svelte")


def _fields(block: str) -> set[str]:
    """Ylimman tason kentat aaltosulkulohkosta (sisakkaiset ohitetaan)."""
    out, depth = set(), 0
    for line in block.split("\n"):
        stripped = line.strip()
        if depth == 0:
            m = re.match(r"([a-z_]+)\??:", stripped)
            if m:
                out.add(m.group(1))
        depth += stripped.count("{") - stripped.count("}")
        depth = max(depth, 0)
    return out


def _spa_last_finished_fields() -> set[str]:
    txt = (SPA / "fantasyTools.ts").read_text(encoding="utf-8")
    m = re.search(r"export interface LastFinishedGw \{\n(.*?)\n\}", txt, re.S)
    assert m, "SPA: LastFinishedGw puuttuu"
    return _fields(m.group(1))


def _app_last_finished_fields() -> set[str]:
    txt = API_TS.read_text(encoding="utf-8")
    m = re.search(r"\n  last_finished\?: \{\n(.*?)\n  \} \| null;", txt, re.S)
    assert m, "mobiili: last_finished-lohko puuttuu"
    return _fields(m.group(1))


def test_last_finished_gw_type_has_same_fields_in_both_repos():
    _need_app()
    spa, app = _spa_last_finished_fields(), _app_last_finished_fields()
    assert "points_net" in spa and "points_net" in app, "points_net-migraatio (7.9) puuttuu"
    assert spa == app, (
        f"vain SPA:ssa {sorted(spa - app)}, vain mobiilissa {sorted(app - spa)} "
        "- LastFinishedGw on erkaantunut repojen valilla")


def test_negative_control_field_parser_sees_nested_fields_as_nested():
    blk = "gw: number;\nplayers: {\n  id: number;\n  nested: string;\n}[];\npoints: number | null;"
    assert _fields(blk) == {"gw", "players", "points"}
