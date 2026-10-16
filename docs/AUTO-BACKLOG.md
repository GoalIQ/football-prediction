# Auto-backlog

Auto-kehitysagentti (`.github/workflows/auto-kehitys.yml`) tekee tästä listasta yhden rivin ajoa kohden
ja avaa PR:n. Aallonharja (`.github/workflows/aallonharja.yml`) lisää rivejä viikoittaisesta
benchmarkista. Säännöt, pisteet ja kiellot: `docs/TUOTEPERIAATTEET.md`. Ihminen mergeää.

## Signaalit

Havainnot, joista agentti tekee rivejä (enintään yksi ajoa kohden, alle 30 päivää vanhat). Ei henkilöiden
nimiä, ei sitaatteja, ei hintoja. Merkintä "→ backlog <pvm>" kertoo, että havainnosta on tehty rivi.

- 2026-10: Jakokortin uusi ulkoasu on SPA:ssa ja goaliq.app/fpl-sivuilla, mutta PIL-generaattori
  `scripts/gen_share_card.py` piirtää yhä vanhaa ulkoasua. Sama luku näyttää eri kortilta eri reitillä. → backlog 2026-10-16
- 2026-10: Ylläpitäjä: tuote benchmarkataan jatkuvasti ja uusia ominaisuuksia haetaan sekä FPL-työkaluihin
  että ottelu-ennusteisiin. Ensimmäinen benchmark: `docs/BENCHMARK.md`.

## Avoimet

- [ ] Jakokortin PIL-generaattori uuteen ulkoasuun: `scripts/gen_share_card.py` piirtää saman asettelun
  kuin SPA:n ja sivujen kortti (`scripts/share_card_js.py`, web/pro-spa). Todennus: `tests/test_share_card_*.py`
  vihreä ja uusi testi, joka vertaa kortin rivien järjestyksen ja otsikot JS-kortin sopimukseen.
  (ylläpitäjän signaali 2026-10, lähde: Signaalit)
      Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 1/3 · uutuus 1/2 = 6
      Mittari: testit vihreät; kortti näyttää samalta kuin SPA:n kortti · tarkistus 2026-11-16

## Tehdyt
