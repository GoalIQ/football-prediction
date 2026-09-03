"""MY-TEAM-CONTEXT (3.9.2026): jaettu joukkuekonteksti työkaluille jotka
eivät ennen lukeneet entryä (GK rotation pairs, price watch, replacements,
differentials, compare).

Kartoitus 3.9 (cos-reports/cc-reports/2026-09-03-oma-joukkue-tyokalut-
kartoitus.md): entry-id on jo jaettu tila molemmilla pinnoilla ja 14 työkalua
käyttää sitä, mutta kuusi ei — vaikka ne ovat samassa näkymässä vieressä.
Tämä moduuli antaa yhden `squad_context`-kutsun, joka palauttaa aina dictin
(ei koskaan nosta): entry-virhe (esikausi 404, väärä id, FPL alhaalla) ei saa
kaataa työkalua joka toimi ennen ilman entryä. Työkalu jatkaa kuten ilman
entryä ja meta kertoo miksi (`available: False` + `note`).

Sama resolveri kuin rate-team/planner/edge (`fpl_rate_team.resolve_squad`),
ei uutta client-putkea. Testit monkeypatchaavat `resolve_squad`in tästä
moduulista — ei verkkoa.
"""

from __future__ import annotations

from src.models.fpl_rate_team import RateTeamError, resolve_squad

MY_TEAM_NOTE = (
    "Squad read from the public FPL entry (15 players and bank). Prices are "
    "current FPL prices; your real selling price can be lower after rises."
)


def squad_context(bootstrap: dict, entry: int | None,
                  players: list[int] | None = None) -> dict | None:
    """Joukkuekonteksti tai None kun entryä/playersia ei annettu.

    Palauttaa aina dictin kun jompikumpi annettiin:
      available   True kun 15 id:tä + bank saatiin
      entry       annettu entry (None manual-moodissa)
      ids         set[int] (tyhjä kun ei saatavilla)
      bank_tenths int
      gw          picks-kierros (None kun ei saatavilla)
      note        selite kun ei saatavilla
    """
    if entry is None and not players:
        return None
    try:
        ids, _cap, bank_tenths, picks_gw = resolve_squad(
            bootstrap, entry, None, players, None, None)
    except RateTeamError as e:
        return {"available": False, "entry": entry, "ids": set(),
                "bank_tenths": 0, "gw": None, "note": e.detail}
    return {"available": True, "entry": entry, "ids": set(ids),
            "bank_tenths": int(bank_tenths), "gw": picks_gw, "note": None}


def squad_meta(ctx: dict | None) -> dict | None:
    """Metaan kirjoitettava, JSON-turvallinen kuvaus kontekstista."""
    if ctx is None:
        return None
    return {
        "available": ctx["available"],
        "entry": ctx["entry"],
        "gw": ctx["gw"],
        "bank": round(ctx["bank_tenths"] / 10.0, 1) if ctx["available"] else None,
        "note": ctx["note"] if not ctx["available"] else MY_TEAM_NOTE,
    }
