"""XP-DOUBT-LIPPU-LAIMENEE (23.9.2026): FPL:n d-lippu kertoo aloitus-tn:n
kertoimella eika laimene minuuttipasseissa.

Julkaisutarkistaja mittasi M101:ssa: Joao Pedro d/75 -> p_start 0.6013, ilman
lippua 0.6939, eli kerroin 0.867. Syy: lippu kerrottiin ennen syvyyspassia,
hintaprioria ja joukkuerajoitetta, ja ne palauttivat osan massasta. /fpl/team-news
lupaa "with the reduced chance of playing already priced in".

Invariantti: epavarman pelaajan p_start = kerroin x saman pelaajan p_start
terveessa ajossa. Mitataan jokaisessa kauden vaiheessa (saanto 6a, kohta 3):
alkukausi (hintapriori paalla, ohut otos), keskikausi (paksu otos, ei prioria),
esikausi (koko kausi ilman recency-ikkunaa). Pelaajatyypit: naulattu avaaja
(syvyyspassin nosto) ja kiertopelaaja ylibuukatussa ryhmassa (joukkuerajoite).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from scripts import build_fpl_xp as b

ROOT = Path(__file__).resolve().parents[1]

# (positio, maara, aloittaa kierroksista osuuden) per joukkue
SQUAD = ((1, 2, (1.0, 0.0)),
         (2, 6, (1.0, 1.0, 1.0, 1.0, 0.5, 0.0)),
         (3, 6, (1.0, 1.0, 1.0, 0.7, 0.7, 0.3)),
         (4, 3, (1.0, 0.6, 0.2)))

PHASES = {
    # kierroksia, recency_window
    "alkukausi": (3, True),
    "keskikausi": (14, True),
    "esikausi": (38, False),
}


def _league(n_rounds: int):
    elements, mins, starts, cur = [], {}, {}, {}
    pid = 0
    for team in (1, 2, 3):
        for pos, n, shares in SQUAD:
            for i in range(n):
                pid += 1
                share = shares[i]
                elements.append({"id": pid, "team": team, "element_type": pos,
                                 "now_cost": 40 + 5 * i + 3 * team + 10 * pos,
                                 "status": "a", "chance_of_playing_next_round": None})
                started = {r: 1 if (r * 7 + pid) % 100 < share * 100 else 0
                           for r in range(1, n_rounds + 1)}
                mins[pid] = {r: (90.0 if s else (20.0 if share > 0 else 0.0))
                             for r, s in started.items()}
                starts[pid] = started
                cur[pid] = sum(mins[pid].values())
    return elements, mins, starts, cur


def _run(elements, mins, starts, cur, recency):
    return b.minute_passes(elements, mins, starts, {}, cur, recency,
                           log=lambda *a, **k: None)


def _flag(elements, pid, status, chance):
    return [dict(e, status=status, chance_of_playing_next_round=chance)
            if e["id"] == pid else e for e in elements]


def _pipeline(elements, mins, starts, cur, recency):
    """Sama jarjestys kuin main(): lipullinen ajo, terve ajo, lippu jalkeen."""
    flagged, _ = _run(elements, mins, starts, cur, recency)
    healthy, _ = _run(b.healthy_elements(elements), mins, starts, cur, recency)
    final, replaced = b.availability_after_passes(flagged, healthy, elements)
    return flagged, healthy, final, replaced


# Naulattu avaaja (GK1, joukkue 1) ja kiertopelaaja (MID, osuus 0.7).
NAILED_GK = 1
ROTATION_MID = 2 + 6 + 4   # joukkue 1: GK x2, DEF x6, MID #4


@pytest.mark.parametrize("phase", sorted(PHASES))
@pytest.mark.parametrize("pid", [NAILED_GK, ROTATION_MID])
@pytest.mark.parametrize("chance,f", [(25, 0.25), (50, 0.5), (75, 0.75), (None, 0.5)])
def test_epavarman_p_start_on_kerroin_kertaa_terve(phase, pid, chance, f):
    n_rounds, recency = PHASES[phase]
    elements, mins, starts, cur = _league(n_rounds)
    els = _flag(elements, pid, "d", chance)
    _, _, final, replaced = _pipeline(els, mins, starts, cur, recency)
    assert pid in replaced
    # Vertailu on RIIPPUMATON healthy_elementsista: sama liiga ilman lippua.
    ref, _ = _run(elements, mins, starts, cur, recency)
    h = ref[pid]
    assert h["p_start"] > 0, "fikstuuri: pelaajan pitaa aloittaa terveena"
    assert final[pid]["p_start"] == pytest.approx(f * h["p_start"], abs=1e-12)
    assert final[pid]["p_start_raw"] == pytest.approx(f * h["p_start_raw"], abs=1e-12)
    assert final[pid]["p_start"] <= f * h["p_start"] + 1e-12


NAILED_DEF = 3             # joukkue 1: DEF #1, osuus 1.0


@pytest.mark.parametrize("pid,suunta", [(NAILED_GK, "ylos"), (NAILED_DEF, "alas")])
def test_fikstuuri_erottelee_vanhan_polun(pid, suunta):
    """Vanha polku (lipullinen ajo sellaisenaan) antaa alkukaudella kertoimen
    joka EI ole lippu. Ilman tata invarianttitesti voisi olla vihrea myos
    vanhalla koodilla (muisti exit-koodi-ei-ole-todiste-mekanismista).

    Mitattu 23.9 talla fikstuurilla, d/75:
      ylos: naulattu maalivahti 0.908 (syvyysnosto ja joukkuerajoite nostavat
            kumpikin 1.10:lla, eli lippu melkein katoaa)
      alas: naulattu puolustaja 0.369 (lippu vie raw-tn:n 1.0 -> 0.75 eli
            naulattujen suojan NAILED_PROTECT_P_START 0.85 alle, ja
            ylibuukatun ryhman p**k-leikkaus osuu hanen koko arvoonsa)
    """
    n_rounds, recency = PHASES["alkukausi"]
    elements, mins, starts, cur = _league(n_rounds)
    els = _flag(elements, pid, "d", 75)
    flagged, _, final, _ = _pipeline(els, mins, starts, cur, recency)
    healthy, _ = _run(elements, mins, starts, cur, recency)
    ratio = flagged[pid]["p_start"] / healthy[pid]["p_start"]
    if suunta == "ylos":
        assert ratio > 0.75 + 0.1, f"vanha polku antoi {ratio:.3f}"
    else:
        assert ratio < 0.75 - 0.1, f"vanha polku antoi {ratio:.3f}"
    assert final[pid]["p_start"] / healthy[pid]["p_start"] == pytest.approx(0.75)


@pytest.mark.parametrize("phase", sorted(PHASES))
def test_joukkuetoverit_pitavat_uudelleenjaon(phase):
    """Epavarman avaajan puuttuva massa nostaa varamiesta (lipullinen ajo), ja
    kaikki muut kuin lippupelaaja pitavat lipullisen ajon arvonsa."""
    n_rounds, recency = PHASES[phase]
    elements, mins, starts, cur = _league(n_rounds)
    els = _flag(elements, NAILED_GK, "d", 50)
    flagged, healthy, final, replaced = _pipeline(els, mins, starts, cur, recency)
    assert replaced == {NAILED_GK}
    for e in els:
        if e["id"] != NAILED_GK:
            assert final[e["id"]] == flagged[e["id"]]
    backup_gk = NAILED_GK + 1
    assert final[backup_gk]["p_start"] >= healthy[backup_gk]["p_start"] - 1e-12


@pytest.mark.parametrize("status", ["i", "s", "u", "n"])
def test_sivussa_pysyy_nollassa_eika_korvata(status):
    elements, mins, starts, cur = _league(PHASES["alkukausi"][0])
    els = _flag(elements, ROTATION_MID, status, 0)
    flagged, _, final, replaced = _pipeline(els, mins, starts, cur, True)
    assert replaced == set()
    assert final[ROTATION_MID]["p_start"] == 0.0
    assert final[ROTATION_MID] == flagged[ROTATION_MID]


def test_varma_poissaolo_pysyy_terveessa_ajossa():
    """Terve ajo poistaa vain d-liput. Loukkaantunut (i) kilpailija ei ole
    kentalla myoskaan terveessa ajossa, joten epavarman pelaajan ehdollinen
    aloitus-tn lasketaan oikeaa kilpailua vastaan.

    Erotteleva: vertailu ajetaan seka 'vain X terve' (oikea) etta 'kaikki
    terveita' (vaara) -maailmassa, ja testi varmistaa etta ne eroavat."""
    n_rounds, recency = PHASES["keskikausi"]
    elements, mins, starts, cur = _league(n_rounds)
    injured_mid = 2 + 6 + 1          # joukkue 1: MID #1, osuus 1.0
    els = _flag(_flag(elements, ROTATION_MID, "d", 75), injured_mid, "i", 0)
    _, healthy, final, replaced = _pipeline(els, mins, starts, cur, recency)
    assert replaced == {ROTATION_MID}
    assert healthy[injured_mid]["p_start"] == 0.0, "i pysyy sivussa terveessa ajossa"
    oikea, _ = _run(_flag(elements, injured_mid, "i", 0), mins, starts, cur, recency)
    vaara, _ = _run(elements, mins, starts, cur, recency)
    assert abs(oikea[ROTATION_MID]["p_start"] - vaara[ROTATION_MID]["p_start"]) > 0.01,         "fikstuuri ei erottele: loukkaantuneen poissaolo ei muuta kilpailua"
    assert final[ROTATION_MID]["p_start"] == pytest.approx(
        0.75 * oikea[ROTATION_MID]["p_start"], abs=1e-12)


def test_kaikki_terveita_ei_muuta_mitaan():
    elements, mins, starts, cur = _league(PHASES["keskikausi"][0])
    flagged, _, final, replaced = _pipeline(elements, mins, starts, cur, True)
    assert replaced == set() and final == flagged


def test_d_ilman_alennusta_ei_korvata():
    """d + chance 100 on kerroin 1: sama kuin terve."""
    elements, mins, starts, cur = _league(PHASES["alkukausi"][0])
    els = _flag(elements, NAILED_GK, "d", 100)
    _, _, _, replaced = _pipeline(els, mins, starts, cur, True)
    assert replaced == set()


def test_main_ajaa_passit_kahdesti_ja_lippu_jalkeen():
    """Kutsupaikka (muisti testi-kutsuu-funktiota-ei-kutsupaikkaa): main()
    ajaa minute_passesin FPL:n statuksilla JA healthy_elementsilla, ja
    mm_by_player tulee availability_after_passesista."""
    src = (ROOT / "scripts" / "build_fpl_xp.py").read_text(encoding="utf-8")
    main = next(n for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    calls = [n for n in ast.walk(main) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name)]
    passes = [c for c in calls if c.func.id == "minute_passes"]
    assert len(passes) == 2, "main() ajaa minute_passesin tasan kahdesti"
    firsts = [ast.unparse(c.args[0]) for c in passes]
    assert "boot['elements']" in firsts
    assert "healthy_elements(boot['elements'])" in firsts
    after = [n for n in ast.walk(main) if isinstance(n, ast.Assign)
             and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
             and n.value.func.id == "availability_after_passes"]
    assert after, "main() ei kutsu availability_after_passesia"
    target = after[0].targets[0]
    assert isinstance(target, ast.Tuple) and target.elts[0].id == "mm_by_player"
    # Jarjestys: lippu passien JALKEEN ja ennen pelaajaohituksia.
    body_src = ast.unparse(main)
    assert (body_src.index("availability_after_passes(")
            < body_src.index("load_player_overrides()"))
