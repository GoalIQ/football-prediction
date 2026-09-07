# -*- coding: utf-8 -*-
"""YKSI LUKIJA sille onko kierroksen pistemaara LOPULLINEN.

MIKSI (7.9.2026, julkaisutarkistajan loydos A1). Kaksi pintaa (`gw-review`,
`my-team-ledger`) lukivat `provisional`-lipun johdetusta artefaktista
`data/model_squad_gw_scores.json` -> `meta.provisional_gws`. Se on
POSITIIVINEN LISTA, ja siksi sen puuttuminen kaantyi vaitteeksi:

    prov = meta.provisional_gws or []          # GW3 ei ole listalla
    "provisional": gw in set(prov)             # -> False = "lopullinen"

Mitattu 7.9: artefakti oli generoitu 1.9 ja kattoi GW1-2. GW3:sta FPL sanoi
`finished=False`, `data_checked=False` — kierros oli KESKEN — ja payload
vaitti silti `provisional=false`. Kierros jota grader ei ole viela
kirjoittanut ei voi olla lopullinen; puuttuva tieto muuttui julkiseksi
vaitteeksi lopullisuudesta.

INVARIANTTI: LOPULLISUUS ON TODISTETTAVA, EI OLETETTAVA. Tama lukija on
fail-closed: kierros on provisionaalinen aina paitsi jos FPL:n oma
`events`-rivi sanoo `finished AND data_checked`. Tuntematon kierros,
puuttuva bootstrap ja rikkinainen artefakti tuottavat kaikki
"provisionaalinen", koska jokainen niista on tila jossa emme tieda.

`data_checked` on mukana `finished`in lisaksi siksi etta bonukset ja BPS
ratkeavat vasta sen kanssa: `finished=True, data_checked=False` on ikkuna
jossa pisteet viela liikkuvat.
"""
from __future__ import annotations

from typing import Any, Iterable


def final_gws(events: Iterable[dict[str, Any]] | None) -> set[int]:
    """Kierrokset joiden pisteet FPL sanoo lopullisiksi.

    Vain `finished AND data_checked`. Tyhja tai puuttuva syote -> tyhja
    joukko, jolloin kaikki on provisionaalista.
    """
    out: set[int] = set()
    for e in events or []:
        if not isinstance(e, dict):
            continue
        gw = e.get("id")
        if not isinstance(gw, int) or isinstance(gw, bool):
            continue
        if e.get("finished") and e.get("data_checked"):
            out.add(gw)
    return out


def provisional_gws(events: Iterable[dict[str, Any]] | None,
                    gws: Iterable[Any],
                    artifact_gws: Iterable[Any] | None = None) -> list[int]:
    """Ne `gws`:n kierrokset jotka on merkittava provisionaalisiksi.

    `artifact_gws` on vanha johdettu lista. Se otetaan mukaan UNIONINA eika
    korvaajana: se voi lisata epavarmuutta (grader tietaa jotain mita
    bootstrap ei kerro) mutta se ei voi koskaan POISTAA sita. Juuri se
    suunta oli vika A1:ssa.
    """
    lopulliset = final_gws(events)
    extra: set[int] = set()
    for g in artifact_gws or []:
        try:
            extra.add(int(g))
        except (TypeError, ValueError):
            continue
    out: set[int] = set()
    for g in gws:
        try:
            gw = int(g)
        except (TypeError, ValueError):
            continue
        if gw not in lopulliset or gw in extra:
            out.add(gw)
    return sorted(out)


def is_provisional(events: Iterable[dict[str, Any]] | None,
                   gw: Any,
                   artifact_gws: Iterable[Any] | None = None) -> bool:
    """Yhden kierroksen muoto. Tuntematon -> True."""
    try:
        g = int(gw)
    except (TypeError, ValueError):
        return True
    return bool(provisional_gws(events, [g], artifact_gws))
