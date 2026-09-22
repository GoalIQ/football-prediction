"""Etusivun kortit uusiksi kun niiden NAKYVA SISALTO muuttuisi (fpl-data-refresh).

🔴 TAUSTA (22.9.2026, LANDING-KORTIT-GW3-VANHAT). goaliq.app:n "What the
model publishes" naytti GW3:n kortteja 18 vrk GW3:n deadlinen jalkeen, kun
kausi oli GW6:ssa. `publish_cards_to_site.py` sanoi "aja fpl-data-refreshissa",
mutta yksikaan workflow ei ajanut sita, ja renderoijat ajettiin vain kasin.
Figcaption lupaa "Every gameweek the model posts its picks".

🔴 22.9 JULKAISUPORTTI: liipaisin oli ensin "actionable GW vaihtui". Portti
blokkasi sen: GW6:n kortti olisi jaanyt sivulle 22 vrk:n maaotteluvalin ajaksi
samalla kun ilmaissivun luvut (joilla kortin prosentit tarkistetaan) liikkuvat
3 h valein. Liipaisin on nyt kortin nakyvan sisallon tiiviste.

MITA TAMA TEKEE
  1. Laskee kummallekin kortille tiivisteen siita mita se NYT nayttaisi
     (`publish_cards_to_site.nykyiset_tiivisteet`: sama HTML-funktio kuin
     renderoijalla) ja vertaa `assets/cards/cards.json`iin. Jos samat: exit 0,
     ei Chromea, ei tiedostomuutoksia. Aikaleimat eivat kuulu tiivisteeseen,
     joten pelkka uusi projektioajo ilman nakyvaa muutosta ei renderoi.
  2. Muuten renderoi VAIN muuttuneet kortit ja julkaisee ne. Muuttumaton
     kortti nayttaa jo samat luvut kuin nykyinen projektio. Projected XI
     ajetaan `--dry-run`: kutsulokiin (data/gw_calls.json) sen kirjaa Ville
     GO-hetkella, ei cron.
  3. Mittaa lopputuloksen manifestista, ei renderoijan exit-koodista
     (renderoija palauttaa 0 myos kun Chromea ei loytynyt). Jos kortti jai
     vanhaksi: `stale_since` cards.json:iin (ensimmainen kaatuminen, ei
     ylikirjoiteta) ja exit 1. Portti sallii poikkeaman 24 h siita hetkesta.

Ajetaan `log_gw_calls`in JALKEEN: standouts-kortti ei saa erota lokista ennen
deadlinea (`reconcile_with_log` kaatuu), ja samassa ajossa samasta datasta
kirjoitettu loki on aina sama.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import publish_cards_to_site as P
from scripts import render_projected_xi_card, render_standouts_card

RENDEROIJAT = {
    "gameweek-card.webp": ("render_standouts_card",
                           lambda: render_standouts_card.main([])),
    "projected-xi-card.webp": ("render_projected_xi_card",
                               lambda: render_projected_xi_card.main(["--dry-run"])),
}


def _aja(nimi: str, f) -> int:
    """Toinen kortti yritetaan vaikka ensimmainen kaatuisi (esim. standouts
    eroaa lokista ennen deadlinea -> RuntimeError, xp_dist vaaralta
    kierrokselta -> SystemExit). Kaatuminen nakyy exit-koodissa ja lokissa."""
    try:
        return f()
    except (Exception, SystemExit) as e:  # noqa: BLE001 - raportoidaan alla
        print(f"::error::{nimi} kaatui: {e!r}")
        return 1


def main(argv=None) -> int:
    meta = P.lue_meta()
    now = dt.datetime.now(dt.timezone.utc)
    nykyiset = P.nykyiset_tiivisteet(now)
    vanhat = P.tarvitsee_renderoinnin(P.lue_manifesti(), nykyiset, meta)
    if not vanhat:
        print("Etusivun kortit vastaavat nykyista projektiota - ei renderointia.")
        return 0
    print(f"Kortit joiden sisalto muuttuisi: {', '.join(vanhat)}. Renderoidaan.")
    rc = {}
    for nimi in vanhat:
        tunnus, f = RENDEROIJAT[nimi]
        rc[tunnus] = _aja(tunnus, f)
    jaljella = P.tarvitsee_renderoinnin(P.lue_manifesti(), nykyiset, meta)
    if jaljella:
        P.merkitse_vanhaksi(jaljella, now)
        print(f"::error::kortit eivat paivittyneet: {', '.join(jaljella)} "
              f"(exit-koodit {rc}). Sivulla nakyy vanha kortti; "
              "tests/test_site_card_images.py punastuu 24 h ensimmaisesta "
              "kaatumisesta (cards.json: stale_since).")
        return 1
    print("OK: etusivun kortit vastaavat nykyista projektiota.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
