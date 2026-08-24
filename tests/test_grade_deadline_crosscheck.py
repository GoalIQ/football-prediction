# -*- coding: utf-8 -*-
"""GRADAUS: jalkikateen kirjattu paatos ei saa laskea track recordiin.

TAUSTA (24.8). `log_fpl_decision` (Supabase-migraatio 20260727220000) vertaa
`now() >= p_deadline_utc`, jossa `p_deadline_utc` tulee KLIENTILTA. Kanta ei
siis tunne kierroksen oikeaa deadlinea, ja vaara pari lapaisee lukituksen.
Mobiili luki kierroksen rate-teamista (`meta.gw` = 1) ja deadlinen Phase
0:sta (`deadline_utc` = GW2:n 28.8), joten GW1-paatoksia pystyi kirjaamaan
kolme paivaa GW1:n jalkeen - tulokset tiedossa.

Klientti korjattiin, mutta se on klientti: vanhat bundlet elavat laitteilla
ja RPC on suoraan kutsuttavissa. Gradaus on ainoa vaihe joka paattaa mika
menee track recordiin, joten se ristiintarkistaa `locked_at`in
(palvelinaikaa) FPL:n omaan deadlineen.
"""
from __future__ import annotations

import pytest

from src.models.fpl_grade import (NOTE_LOGGED_AFTER_DEADLINE,
                                  logged_after_deadline)

DL = "2026-08-21T17:30:00Z"


@pytest.mark.parametrize("locked,odotus,kuvaus", [
    ("2026-08-24T12:00:00+00:00", True, "kolme vuorokautta deadlinen jalkeen"),
    ("2026-08-21T17:30:01Z", True, "sekunti deadlinen jalkeen"),
    ("2026-08-21T17:29:59Z", False, "sekunti ennen deadlinea"),
    ("2026-08-21T17:30:00Z", False, "tasan deadlinella - ei myohassa"),
    # Vyohyke on jasennettava, ei verrattava merkkijonona: 20:29+03:00 on
    # 17:29Z eli ENNEN deadlinea, vaikka "20" > "17" merkkijonona.
    ("2026-08-21T20:29:00+03:00", False, "eri vyohyke, oikeasti ennen"),
    ("2026-08-21T20:31:00+03:00", True, "eri vyohyke, oikeasti jalkeen"),
])
def test_late_rows_are_detected(locked, odotus, kuvaus):
    assert logged_after_deadline(locked, DL) is odotus, kuvaus


@pytest.mark.parametrize("locked,deadline", [
    (None, DL),
    ("2026-08-24T12:00:00Z", None),
    ("roska", DL),
    ("2026-08-24T12:00:00Z", "roska"),
    ("", ""),
])
def test_unknown_is_not_guilty(locked, deadline):
    """Puuttuva aikaleima on datavika eika todiste jalkiviisaudesta.

    Rivin hylkaaminen sen perusteella rankaisisi kayttajaa infran ongelmasta,
    joten tuntematon tila EI merkitse rivia myohaiseksi.
    """
    assert logged_after_deadline(locked, deadline) is False


def test_note_is_distinct_from_the_other_notes():
    """Merkinnan on erotuttava, jotta myohaiset rivit voi laskea erikseen."""
    from src.models import fpl_grade as g
    muut = {g.NOTE_OK, g.NOTE_NO_ENTRY, g.NOTE_PICKS_UNAVAILABLE,
            g.NOTE_PLAYER_MISSING, g.NOTE_KIND_NOT_GRADED}
    assert NOTE_LOGGED_AFTER_DEADLINE not in muut
    assert NOTE_LOGGED_AFTER_DEADLINE == "logged_after_deadline"


def test_endpoint_reads_locked_at_and_uses_the_crosscheck():
    """Negatiivinen kontrolli koko ketjulle.

    Apuri voi olla oikein ja silti kutsumatta - ja `locked_at` on
    valittava kyselyssa, muuten ristiintarkistus saa aina None:n ja
    lapaisee kaiken hiljaa (fail-open).
    """
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "api" / "main.py").read_text(
        encoding="utf-8", errors="replace")
    assert "logged_after_deadline(" in src, "ristiintarkistusta ei kutsuta"
    assert "true_deadlines()" in src, "riippumatonta deadline-lahdetta ei haeta"
    assert "NOTE_LOGGED_AFTER_DEADLINE" in src, "merkintaa ei kirjoiteta"

    # 🔴 `"locked_at" in src` EI KELPAA. Ensimmainen versio tasta testista
    # teki juuri niin, ja mutaatiotesti (poista locked_at select-listalta)
    # LAPAISI: sana esiintyy tiedostossa muutenkin. Portin on osuttava tasan
    # siihen kyselyyn jonka rivit ristiintarkistetaan, muuten apuri saa aina
    # None:n ja lapaisee kaiken hiljaa.
    import re
    # Kysely on jaettu useaan f-string-literaaliin, joten "fpl_decisions" ja
    # "?graded_at" eivat ole peräkkain lahteessa. Ankkuroidaan lohkoon.
    kysely = re.search(r"graded_at=is\.null.*?timeout=", src, re.S)
    assert kysely, "gradauksen decisions-kyselya ei loydy"
    assert "locked_at" in kysely.group(0), (
        "locked_at puuttuu gradauskyselyn select-listalta - "
        "ristiintarkistus saisi aina None:n ja lapaisisi kaiken")
