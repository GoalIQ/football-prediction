"""Deterministinen jarjestys julkisille listoille (sivu JA jakokortti).

TAUSTA (29.8.2026): sivun EO-lohkon kapteenitaulukko lajitteli pelkalla
`-captain_pct`:lla. Python-lajittelu on stabiili, joten tasapelin ratkaisi
SYOTTEEN JARJESTYS, ja syote tulee eri polkua sivulle kuin jakokortille. Samasta
otoksesta saattoi siis syntya kaksi eri "viidetta kapteenia", ja kumpikin naytti
oikealta omalla pinnallaan. Julkaisuportti nosti taman kierroksella 1: GW2:n
datassa Mbeumo ja Isak ovat molemmat tasan 3.5 %:ssa juuri viidennella sijalla.

SAANTO: arvo laskevasti, tasapeli pelaajan id:lla nousevasti. id EIKA web_name,
koska web_name ei ole avain (FPL:n bootstrapissa on samannimisia pelaajia;
mitattu 9 duplikaattia). Sama funktio molemmille generaattoreille, jotta
jarjestys ei voi erota pinnasta toiseen.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Sequence

#: Kaytetaan kun rivilta puuttuu id. Suuri luku -> ilman id:ta olevat rivit
#: valahtavat tasapelissa viimeisiksi sen sijaan etta sekoittuisivat mukaan.
_NO_ID = 10**9


def _player_id(row: Any) -> int:
    """Rivin vakaa identiteetti. Hyvaksyy dictin tai olion, jolla on id."""
    if isinstance(row, dict):
        raw = row.get("id", row.get("element"))
    else:
        raw = getattr(row, "id", None)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return _NO_ID


def rank_key(value: float, row: Any) -> tuple[float, int]:
    """Lajitteluavain: arvo laskevasti, tasapeli id:lla nousevasti."""
    return (-float(value), _player_id(row))


def ranked(
    rows: Iterable[Any],
    value: Callable[[Any], float],
    limit: int | None = None,
) -> list[Any]:
    """Rivit arvon mukaan laskevasti, tasapeli id:lla. Sama tulos syotteen
    jarjestyksesta riippumatta."""
    out = sorted(rows, key=lambda r: rank_key(value(r), r))
    return out if limit is None else out[:limit]


def order_differs(a: Sequence[Any], b: Sequence[Any]) -> bool:
    """Kaksi listaa samasta otoksesta: eroaako jarjestys id-tasolla?

    Kayttokohde testeissa ja porteissa: sivun taulukko vs. jakokortti.
    """
    return [_player_id(r) for r in a] != [_player_id(r) for r in b]
