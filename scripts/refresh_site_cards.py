"""Etusivun kortit uusiksi VAIN kun actionable GW vaihtuu (fpl-data-refresh).

🔴 TAUSTA (22.9.2026, LANDING-KORTIT-GW3-VANHAT). goaliq.app:n "What the
model publishes" naytti GW3:n kortteja 18 vrk GW3:n deadlinen jalkeen, kun
kausi oli GW6:ssa. `publish_cards_to_site.py` sanoi "aja fpl-data-refreshissa",
mutta yksikaan workflow ei ajanut sita, ja renderoijat ajettiin vain kasin.
Figcaption lupaa "Every gameweek the model posts its picks".

MITA TAMA TEKEE
  1. Lukee `assets/cards/cards.json`in ja datan actionable GW:n
     (`publish_cards_to_site.tarvitsee_renderoinnin`). Jos kaikki kortit ovat
     jo talta kierrokselta: exit 0, ei Chromea, ei tiedostomuutoksia. Nain
     refresh ei tuota commit-churnia joka 3 h ajossa - kortit vaihtuvat
     kerran kierroksessa, samassa committissa kuin data joka ne kaansi.
  2. Muuten renderoi MOLEMMAT kortit (eri ajoista tulleet kortit voisivat
     nayttaa eri lukuja rinnakkain) ja julkaisee ne. Projected XI ajetaan
     `--dry-run`: kutsulokiin (data/gw_calls.json) sen kirjaa Ville
     GO-hetkella, ei cron.
  3. Mittaa lopputuloksen: jos jokin kortti ei ole nyt actionable GW:lta,
     exit 1. Renderoija voi palauttaa 0 ilman kuvaa (Chromea ei loytynyt),
     joten exit-koodi ei ole todiste - manifesti on.

Ajetaan `log_gw_calls`in JALKEEN: standouts-kortti ei saa erota lokista ennen
deadlinea (`reconcile_with_log` kaatuu), ja samassa ajossa samasta datasta
kirjoitettu loki on aina sama.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import publish_cards_to_site as P
from scripts import render_projected_xi_card, render_standouts_card
from src.models.fpl_gameweek import actionable_gameweek


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
    act = actionable_gameweek(meta)
    vanhat = P.tarvitsee_renderoinnin(P.lue_manifesti(), meta)
    if not vanhat:
        print(f"Etusivun kortit ovat jo GW{act}:lta - ei renderointia.")
        return 0
    print(f"Actionable GW{act}; vanhat kortit: {', '.join(vanhat)}. "
          "Renderoidaan molemmat samasta datasta.")
    rc_s = _aja("render_standouts_card",
                lambda: render_standouts_card.main([]))
    rc_x = _aja("render_projected_xi_card",
                lambda: render_projected_xi_card.main(["--dry-run"]))
    jaljella = P.tarvitsee_renderoinnin(P.lue_manifesti(), meta)
    if jaljella:
        print(f"::error::kortit eivat paivittyneet GW{act}:lle: "
              f"{', '.join(jaljella)} (standouts exit {rc_s}, projected XI "
              f"exit {rc_x}). Sivulla nakyy edellinen kierros; portti "
              "tests/test_site_card_images.py punastuu armonajan jalkeen.")
        return 1
    print(f"OK: molemmat etusivun kortit ovat GW{act}:lta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
