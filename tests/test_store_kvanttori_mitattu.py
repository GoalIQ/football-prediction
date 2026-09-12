"""Portti: store-kuvauksen pelaajajoukon kvanttori on mitattava artefaktista.

TAUSTA (12.9.2026). Store-kuvauksen rivi sanoi

    "- Per-gameweek DefCon matrix: every player, all of last season"

ja se oli **epatosi**: `data/fpl_defcon_gw.json` kantaa 326 pelaajaa, ei
yhtaan maalivahtia (`scripts/build_fpl_defcon_gw.py:137` sulkee GKP:n pois
eksplisiittisesti), eika ketaan jolla ei ole 2025/26-minuutteja. Sivu itse on
rehellisempi kuin kuvaus oli: `/fpl/defcon.html` sanoo "Ranking needs at least
19 starts."

Miksi tama tapahtui on tarkeampaa kuin mita tapahtui: rivi syntyi kun
kuvausta TIIVISTETTIIN. Lyhyempi rivi tuli teravammaksi lisaamalla
universaalikvanttori, ja kvanttori on vaite jota kukaan ei mitannut.
Julkaisutarkistaja, joka hyvaksyi tiivistyksen, huomasi sen vasta
seuraavalla kierroksella omasta korjauksestaan.

MEKANISMI (CLAUDE.md saanto 6a, mekanismi 2): poikkeuslista jossa on
perustelu. Uusi "every player" / "cada jugador" / "todos os jogadores" ei
paase kuvaukseen vahingossa: testi kaatuu ja kirjoittaja joutuu joko
mittaamaan artefaktista tai kirjoittamaan rajauksen nakyviin.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STORE = ROOT.parent / "goaliq-app" / "store.config.json"
DEFCON = ROOT / "data" / "fpl_defcon_gw.json"

# Universaalikvanttori + pelaajajoukko, neljalla kielella joita kaupassa on.
NL = chr(10)

KVANTTORI_RE = re.compile(
    r"(?:every|each|all(?:\s+of)?\s+the|all)\s+players?\b"
    r"|\bevery\s+player\b"
    r"|(?:cada|todos\s+los|todo)\s+(?:el\s+)?jugador(?:es)?\b"
    r"|(?:cada|todos\s+os|todo)\s+(?:o\s+)?jogador(?:es)?\b",
    re.I,
)

# Poikkeuslista: sallittu VAIN kun rivilla on nakyva rajaus, ja rajaus on
# kirjoitettu tahan auki. Avain on kvanttorin osuma pienella; arvo on
# perustelu joka nakyy diffissa kun joku lisaa uuden.
SALLITUT = {
    "every player with data": (
        "xG/xA/xGI-liiderit: rajaus 'with data' on rivilla itsellaan, ja "
        "rivi listaa vain ne joilla lahdedataa on."
    ),
    "cada jugador con datos": "sama rivi es-ES:ssa, sama rajaus.",
    "cada jogador com dados": "sama rivi pt-BR:ssa, sama rajaus.",
}


def _kuvaukset() -> dict[str, str]:
    if not STORE.exists():
        return {}  # mobiilirepo ei ole mountattu
    d = json.loads(STORE.read_text(encoding="utf-8"))
    return {
        loc: v.get("description", "")
        for loc, v in (d.get("apple", {}).get("info", {}) or {}).items()
    }


def _sallittu(teksti: str, alku: int) -> bool:
    """Katsooko osumaa seuraava rajaus poikkeuslistalta."""
    hanta = " ".join(teksti[alku:alku + 60].split()).lower()
    return any(hanta.startswith(k) for k in SALLITUT)


def test_defcon_matriisi_ei_kata_kaikkia_pelaajia():
    """Mittaus jonka varassa poikkeuslista on. Jos tama muuttuu, kvanttori
    voi muuttua sallituksi -- mutta vasta kun luku sanoo niin."""
    if not DEFCON.exists():
        return
    pelaajat = json.loads(DEFCON.read_text(encoding="utf-8")).get("players") or []
    positiot = {(p.get("pos") or p.get("position")) for p in pelaajat}
    assert pelaajat, "artefakti tyhja: mittaus ei kelpaa"
    assert "GKP" not in positiot, (
        "DefCon-matriisissa on nyt maalivahteja. Kvanttorisaanto tassa "
        "tiedostossa perustuu siihen ettei ole; tarkista store-copy."
    )


def test_store_kuvaus_ei_vaita_kaikkia_pelaajia_ilman_rajausta():
    kuvaukset = _kuvaukset()
    if not kuvaukset:
        return
    viat = []
    for loc, teksti in kuvaukset.items():
        for m in KVANTTORI_RE.finditer(teksti):
            if _sallittu(teksti, m.start()):
                continue
            # Rivi lasketaan OSUMAN SIJAINNISTA. Substring-haku "mika rivi
            # sisaltaa taman tekstin" osoittaa ensimmaiseen samannimiseen
            # riviin, ja 12.9 se osoitti nimenomaan siihen VIATTOMAAN riviin
            # jolla rajaus oli (muisti: tiivistys-piilottaa-vaaran-rivin).
            r_alku = teksti.rfind(NL, 0, m.start()) + 1
            r_loppu = teksti.find(NL, m.start())
            rivi = teksti[r_alku:r_loppu if r_loppu != -1 else len(teksti)]
            viat.append(f"{loc}: {rivi.strip()[:120]}")
    assert not viat, (
        "Store-kuvaus vaittaa kattavansa KAIKKI pelaajat ilman rajausta:\n  "
        + "\n  ".join(viat)
        + "\n\nMittaa artefaktista ennen kuin vaitat. Esim. DefCon-matriisi "
        "on 326 pelaajaa ilman maalivahteja (data/fpl_defcon_gw.json), joten "
        "'every player' on siina epatosi. Joko kirjoita rajaus riville "
        "(kuten 'every player with data') ja lisaa se SALLITUT-listaan "
        "perusteluineen, tai vaihda kuvaileva substantiivi "
        "('outfield players' / 'jugadores de campo' / 'jogadores de linha')."
    )


def test_kontrolli_regex_loytaa_poistetun_rivin():
    """Ilman tata edellinen voisi olla vihrea tyhjana."""
    for rivi in (
        "- Per-gameweek DefCon matrix: every player, all of last season",
        "- Matriz DefCon por jornada: cada jugador, toda la temporada pasada",
        "- Matriz DefCon por rodada: cada jogador, toda a temporada passada",
    ):
        assert KVANTTORI_RE.search(rivi), rivi
        m = KVANTTORI_RE.search(rivi)
        assert not _sallittu(rivi, m.start()), rivi


def test_kontrolli_rajattu_rivi_menee_lapi():
    rivi = "- Player leaders: xG, xA and xGI for every player with data"
    m = KVANTTORI_RE.search(rivi)
    assert m and _sallittu(rivi, m.start()), rivi


def test_kontrolli_korjattu_rivi_ei_ole_kvanttori():
    for rivi in (
        "- Per-gameweek DefCon matrix: outfield players, all of last season",
        "- Matriz DefCon por jornada: jugadores de campo, toda la temporada pasada",
        "- Matriz DefCon por rodada: jogadores de linha, toda a temporada passada",
    ):
        assert not KVANTTORI_RE.search(rivi), rivi
