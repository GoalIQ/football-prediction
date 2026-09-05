"""Portti: hold- ja transfer-verdiktin copy ei saa vaittaa kattavuutta jota mallilla ei ole.

TAUSTA (29.8.2026, julkaisutarkistaja kolme kierrosta): sama vaite eli SEITSEMALLA
renderointipolulla, ja jokainen kierros loysi yhden lisaa. Testivahdit mittasivat
vain `hold_verdict["message"]`-kentan None-haaraa, joten "Best available plan",
"Best available single-transfer gain ... this week" ja normaalipolun
"Your best move gains ... over N GWs" menivat lapi vihreana kolme kertaa.

Miksi vaite on vaara: rate-team hakee vain YKSITTAISIA siirtoja (`single_moves`),
ja plannerin oma `meta.heuristic` sanoo kayttajalle "it doesn't try every possible
plan". Sanat "available", "beats" ja "no plan" lupaavat haun kattaneen kaiken.
"this week" on lisaksi ristiriidassa saman kortin horisonttilauseen kanssa.

Tama portti lukee TIEDOSTOT eika kutsu funktioita: se on ainoa tapa kattaa
renderointipolut jotka eivat kulje yhden testattavan paluuarvon kautta.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Tiedostot joissa hold/transfer-verdiktin copy elaa (fp-repo).
SCANNED = [
    Path("src/models/fpl_rate_team.py"),
    Path("src/models/fpl_planner.py"),
    Path("api/fantasy_edge.py"),
    Path("web/pro-spa/src/lib/components/HoldVerdictCard.svelte"),
    Path("web/pro-spa/src/lib/components/TransferPlanner.svelte"),
    Path("web/pro-spa/src/lib/components/PlanChains.svelte"),
    Path("web/pro-spa/src/lib/components/RateTeam.svelte"),
    Path("web/pro-spa/src/lib/components/FitChecker.svelte"),
    # 5.9: SquadNews ei renderoi verdiktia, mutta sen lahderivi sisaltaa
    # sanan "transfers." (myohaiset siirrot liikuttavat hintapaivaa) ja
    # loytotesti osuu siihen. Skannataan, jotta portti kattaa sen jos
    # komponentti joskus alkaa puhua siirtoverdiktista.
    Path("web/pro-spa/src/lib/components/SquadNews.svelte"),
    Path("src/models/fpl_fit.py"),
    Path("src/models/fpl_gameweek.py"),
]

#: Komponentit jotka mainitsevat verdiktidatan mutta joita EI skannata,
#: perustelu per rivi. Loytotesti alla kaataa jos uusi komponentti ilmestyy
#: kumpaankaan listaan kuulumatta -- SCANNED oli 29.8 kasin piirretty lista ja
#: sen ulkopuolelta loytyi heti kaksi rikkovaa tiedostoa.
NOT_SCANNED: dict[str, str] = {}

BANNED = {
    # 3.9 (julkaisuportti B4): kuvio oli `Best available` ja se on SUBSTRING-
    # sokea. Kirjoitin "Best move available" ja hylatty kattavuusvaite palasi
    # tuotantoon VIHREAN portin lapi — sama kuvio kuin muistissa
    # [gate-substring-osuma-on-sokea]. Nyt sanojen valiin mahtuu jotain.
    r"\bBest\b[^.\n]{0,24}\bavailable\b": (
        "kattavuusvaite: malli hakee vain osan vaihtoehdoista "
        "(kayta 'Best move the model checked')"),
    r"No available move": "sama kattavuusvaite kielletyssa muodossa",
    r"\bbeats your team\b": "ylikvanttori, korvattu muodolla 'the model checked'",
    r"\bbeats my team\b": "ylikvanttori jakokortilla",
    r"\bno plan\b": "rate-team ei laske suunnitelmia lainkaan",
    # 29.8 k4: alkuperainen kuvio ei osunut Svelte-muotoon ${n} eika paljaaseen
    # lukuun, ja juuri ne kaksi ovat skannatuista tiedostoista Svelteä. \S*
    # kattaa {n}, ${n}, ${a.b} ja 6.
    r"over the next \S* ?GWs": "kayta '{n}-GW horizon', kestaa myos arvon 1",
    r"over \$?\{[^}]+\} GWs": "kayta '${...}-GW horizon'",
    r"over \d+ GWs": "kayta '{n}-GW horizon'",
    # k5: sama kuvio kirjoitettuna auki. Ei viela elavaa osumaa, mutta
    # mobiiliportin oma DEFERRED-testi tunsi muodon jo -> tuleva reika.
    r"over the next \S* ?gameweeks": "kayta '{n}-gameweek horizon'",
    r"across \S* ?GWs": "yksikkomuoto puuttuu: 'across 1 GWs'",
    # k5: \S* ei ylita valilyontia lausekkeen sisalla ({a ?? 6}).
    r"over the next \{[^}]*\} ?GWs": "kayta '{n}-GW horizon'",
    # k7: sama reika oli auki 'gameweeks'-muodolle. Portti oli vihrea koska se
    # ei nahnyt rivia, ei koska rivi noudatti saantoa.
    r"over the next \{[^}]*\} ?gameweeks": "kayta '{n}-gameweek horizon'",
    r"this week": "ristiriita saman kortin horisonttilauseen kanssa",
}


#: Rivit joissa kielletty kuvio on TARKOITUKSELLINEN, perustelu per rivi.
#: Lisays tanne on tietoinen paatos, kuten llms.txt-portin EXEMPT-listassa.
ALLOWED = {
    "keep the free transfer this week and bank it":
        "FPL-kasite: vapaa siirto sailytetaan talle kierrokselle. Ei kattavuusvaite "
        "mallin hausta vaan selitys siita mita 'hold' tarkoittaa pelissa.",
    "Keeping (rolling) your free transfer this week instead of spending it":
        "Sama FPL-kasite RateTeamin abbr-titlessa. 'this week' viittaa siihen "
        "kierrokseen jolle siirto sailyy, ei mallin hakuhorisonttiin.",
}


def _code_lines(path: Path) -> list[tuple[int, str]]:
    """Rivit ilman kommentteja ja ilman sallittuja rivejä.

    Kommenteissa vanhat sanamuodot ovat sallittuja, koska juuri niissa
    selitetaan miksi ne poistettiin. Monirivinen kommentti tunnistetaan
    tilakoneella: pelkka aloitusmerkin tarkistus paasti 29.8 lapi
    vaarapositiivin oman selityskommenttini keskirivilta.
    """
    out = []
    in_block = False
    for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        s = ln.strip()
        if in_block:
            if "*/" in s or "-->" in s:
                in_block = False
            continue
        if s.startswith("#") or s.startswith("//") or s.startswith("*"):
            continue
        if (s.startswith("/*") or s.startswith("<!--") or s.startswith("{/*")) and not (
            "*/" in s[2:] or "-->" in s[4:]
        ):
            in_block = True
            continue
        # ALLOW poistaa VAIN sallitun osamerkkijonon: koko rivin ohittaminen
        # salakuljettaisi toisen kielletyn kuvion samalla rivilla.
        cleaned = ln
        for a in ALLOWED:
            cleaned = cleaned.replace(a, "")
        out.append((i, cleaned))
    return out


def _normalise(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Yhdista rivit joilta kayttajalle nakyva LAUSE jatkuu seuraavalle.

    29.8 k5: rivipohjainen skannaus oli sokea kahdelle elavalle rikkomukselle,
    koska Pythonin implisiittinen konkatenaatio (f"... over " + f"{n} GWs")
    ja Svelten markup jakavat lauseen kahdelle riville eika kumpikaan puolisko
    osu kuvioon. Rivi ei ole oikea skannausyksikko.

    Rivinumero sailyy LAUSEEN ensimmaisen rivin numerona.
    """
    QUOTES = ('"', "'")
    JOIN_END = (";", "{", "}", ">", ",", ":", "(")
    out: list[tuple[int, str]] = []
    for lineno, ln in lines:
        stripped = ln.strip()
        if not stripped:
            out.append((lineno, ln))
            continue
        if out:
            prev_no, prev = out[-1]
            prev_s = prev.rstrip()
            py_concat = prev_s.endswith(QUOTES) and (
                stripped.startswith('f"')
                or stripped.startswith("f'")
                or stripped.startswith('"')
                or stripped.startswith("'")
            )
            markup_wrap = (
                not prev_s.endswith(JOIN_END)
                and not stripped.startswith("<")
                and not stripped.startswith("{#")
                and not stripped.startswith("{:")
                and not stripped.startswith("{/")
                and not stripped.startswith("def ")
                and prev_s.endswith(("the", "over", "next", "by", "xP", "gains", "and"))
            )
            if py_concat or markup_wrap:
                merged = prev_s + " " + stripped
                # poista konkatenaation saumamerkit, jotta kuvio osuu lauseeseen
                for seam in ('" f"', "' f'", '" "', "' '", '" ', "' "):
                    merged = merged.replace(seam, " ")
                out[-1] = (prev_no, merged)
                continue
        out.append((lineno, ln))
    return out


def scan(text_lines: list[tuple[int, str]]) -> list[str]:
    hits = []
    for lineno, ln in _normalise(text_lines):
        for pat, why in BANNED.items():
            if re.search(pat, ln):
                hits.append(f"rivi {lineno}: {pat} ({why}) -> {ln.strip()[:100]}")
    return hits


def test_portti_osuu_hylattyyn_sanamuotoon():
    """NEGATIIVINEN KONTROLLI portille itselleen (3.9).

    3.9 kirjoitin `Best move available` ja portti oli vihrea: kuvio oli
    `Best available`, eika substring-osuma nae sanaa valissa. Portti joka ei
    osu on portti jota ei ole, ja se loytyy vain nain: syota sille rivi jonka
    sen PITAA hylata.
    """
    for bad in ("Best move available: +0.19 xP per gameweek",
                "Best available plan (3 moves)",
                "Best single move available this week",
                "No available move improves your team"):
        assert scan([(1, bad)]), f"portti EI osunut: {bad}"
    # ...eika osu sallittuun muotoon (muuten portti kieltaisi kaiken)
    for ok in ("Best move the model checked: +0.06 xP per gameweek",
               "No move the model checked improves your projected xP"):
        assert not scan([(1, ok)]), f"portti osui sallittuun: {ok}"


def test_tuotantopinnat_ovat_skoopattuja():
    problems = []
    for rel in SCANNED:
        p = ROOT / rel
        assert p.exists(), f"{rel} puuttuu - portti mittaisi tyhjaa"
        for h in scan(_code_lines(p)):
            problems.append(f"{rel}: {h}")
    assert not problems, "skooppaamaton hold-copy:\n" + "\n".join(problems)


#: Negatiiviset kontrollit. Jokaisella BANNED-kuviolla on oltava vahintaan
#: yksi sample joka osuu SIIHEN kuvioon -- ei riita etta sample osuu johonkin.
#: 29.8 k4 mittasi: sample "No transfer beats your team over the next 6 GWs."
#: lapaisi kontrollin `beats your team` -kuvion kautta ja peitti sen, etta
#: horisonttikuvio oli rikki. Kaksi vahtia yhdessa testissa.
SAMPLES = [
        "	const plan = `Best available plan (${n} moves)`;",
        "	No available move improves your projected xP.",
        '	message = "No transfer beats your team over the next 6 GWs."',
        "	`No transfer beats my team over the next ${n} GWs.`",
        '	title = "Hold - no plan is worth the move"',
        "	subtitle = `${plan} ${gain} xP over ${v.horizon_gws} GWs`",
    '	note = "holding your team is a fine play this week."',
    '	subtitle = `${net} xP net over ${v.horizon_gws} GWs`',
    '	subtitle = `xP over the next ${n} GWs`',
    '	msg = "gains 1.2 xP over 6 GWs"',
    '	"x": "projected points over the next {n} gameweeks",',
    '	Dead level over the next {data.meta.horizon_gw ?? 6} GWs.',
    '	projected points over the next {data.meta.horizon_gw ?? 6} gameweeks',
    '	const plan = `(${n} moves across ${h} GWs)`;',
]


def test_kontrolli_havaitsee_jokaisen_kielletyn_muodon():
    for smp in SAMPLES:
        assert scan([(1, smp)]), f"kontrolli ei havainnut: {smp}"


def test_jokaisella_kielletylla_kuviolla_on_oma_kontrolli():
    """Ilman tata yksi rikki oleva kuvio piiloutuu toisen osuman taakse."""
    for pat in BANNED:
        assert any(re.search(pat, smp) for smp in SAMPLES), (
            f"kuviolla ei ole omaa negatiivista kontrollia: {pat}"
        )


def test_kontrolli_ei_kaadu_korjatusta_muodosta():
    ok = [
        "	const plan = `Best plan the model checked (${n} moves across the ${h}-GW horizon)`;",
        "	Nothing the model checked improves your projected xP over the {n}-GW horizon.",
        '	message = "No move the model checked improves your team over the 6-GW horizon."',
    ]
    for s in ok:
        assert not scan([(1, s)]), f"kontrolli kaatui korjattuun muotoon: {s}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


def test_allow_lista_ei_vanhene():
    """Sallittu rivi on oikeasti olemassa jossakin skannatussa tiedostossa.

    Portin sanalista vanhenee: jos sallittu lause poistetaan koodista, merkinta
    jaa elamaan ja voi myohemmin niella eri rivin joka sattuu sisaltamaan saman
    tekstin.
    """
    blob = chr(10).join((ROOT / rel).read_text(encoding="utf-8") for rel in SCANNED)
    for allowed in ALLOWED:
        assert allowed in blob, (
            f"ALLOWED-merkinta ei vastaa mitaan riviä enaa: {allowed!r} - poista se"
        )


def test_kaikki_verdiktikomponentit_ovat_listalla():
    """SCANNED on kasin piirretty lista, ja se on sama vikamuoto jota portti estaa.

    Jokainen SPA-komponentti joka koskee verdiktidataa on oltava joko
    SCANNED- tai NOT_SCANNED-listalla perusteluineen.
    """
    comp_dir = ROOT / "web" / "pro-spa" / "src" / "lib" / "components"
    scanned = {p.name for p in SCANNED}
    missing = []
    for f in sorted(comp_dir.glob("*.svelte")):
        txt = f.read_text(encoding="utf-8")
        if "hold_verdict" in txt or "transfers." in txt:
            if f.name not in scanned and f.name not in NOT_SCANNED:
                missing.append(f.name)
    assert not missing, (
        "verdiktidataa koskeva komponentti ei ole kummallakaan listalla: "
        + ", ".join(missing)
    )
