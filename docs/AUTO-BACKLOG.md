# Auto-backlog

Auto-kehitysagentti (`.github/workflows/auto-kehitys.yml`) tekee tästä listasta yhden rivin ajoa kohden
ja avaa PR:n. Aallonharja (`.github/workflows/aallonharja.yml`) lisää rivejä viikoittaisesta
benchmarkista. Säännöt, pisteet ja kiellot: `docs/TUOTEPERIAATTEET.md`. Ihminen mergeää.

Rivi, joka tarvitsee uuden bottiajon tai työnkulun askeleen: agentti kirjoittaa tuottajaskriptin ja testin,
ja PR:n Julkaisu-osio kertoo, mihin työnkulkuun askel lisätään. Työnkulun muutos tehdään käsin mergen yhteydessä.

## Signaalit

Havainnot, joista agentti tekee rivejä (enintään yksi ajoa kohden, alle 30 päivää vanhat). Ei henkilöiden
nimiä, ei sitaatteja, ei hintoja. Merkintä "→ backlog <pvm>" kertoo, että havainnosta on tehty rivi.

- 2026-10: Jakokortin uusi ulkoasu on SPA:ssa ja goaliq.app/fpl-sivuilla, mutta PIL-generaattori
  `scripts/gen_share_card.py` piirtää yhä vanhaa ulkoasua. Sama luku näyttää eri kortilta eri reitillä. → backlog 2026-10-16
- 2026-10: Ylläpitäjä: tuote benchmarkataan jatkuvasti ja uusia ominaisuuksia haetaan sekä FPL-työkaluihin
  että ottelu-ennusteisiin. Ensimmäinen benchmark: `docs/BENCHMARK.md`. → backlog 2026-10-16
- 2026-10: FPL:n API:ssa on kaudesta 2026/27 kenttä `elements[].scout_risks` (loan_ineligible kierroksittain,
  suspension_risk). xP-putki ei lue sitä: Danso GW12 xp 3.91 vaikka FPL ilmoittaa lainaesteen. → backlog 2026-10-16
- 2026-10: IHMISEN PROJEKTI (ei agentille): oman joukkueen status-push (status tai chance_of_playing muuttuu
  omassa 15:ssä). Vaatii Supabase-migraation (push_tokens ilman entry ID:tä) ja mobiilisovelluksen muutoksen.
  Kilpailija mainostaa tätä natiivisovelluksessaan. Lähde: docs/BENCHMARK.md luku 5.
- 2026-10: IHMISEN PROJEKTI (ei agentille): lukuoikeudellinen MCP-liitin ilmaisdataan (CS%, FDR, top 100 xP,
  track record lähdelinkkeineen). Vaatii uuden Cloudflare Workerin julkaisun; 0 euron raja tarkistettava.
  Lähde: docs/BENCHMARK.md luku 5.
- 2026-10: Ilmaisella /fpl#gw-calls-paneelilla kutsut seuraavat uusinta projektiota deadlineen asti, xP-jäädytys
  tehdään noin vuorokautta ennen. GW6:lla ero 0.93. Ylläpitäjä päätti 16.10: jäädytys päivittyy deadlineen asti. → backlog 2026-10-16

## Avoimet

- [ ] Lainaeste xP:hen: lue `elements[].scout_risks` (property `loan_ineligible`, `gameweek`) yhdellä lukijalla
  (esim. `src/models/fpl_xp.py: loan_ineligible_gws(element) -> set[int]`) ja aseta xP-putkessa
  (`scripts/build_fpl_xp.py`) pelaajan `gameweeks[].xp` ja `xmins` nollaksi niillä kierroksilla; horisonttisumma ja
  per-GW-jakauma samasta lähteestä. Testi synteettisellä elementillä, joka kaatuu jos kutsupaikka poistetaan, ja
  vaihetesti (estokierros horisontissa / ei horisontissa / jo pelattu). Todennus: seuraavan bottiajon jälkeen
  `data/fpl_xp_projections.json` Danso GW12 xp 0. (ylläpitäjän signaali 2026-10, lähde: Signaalit, docs/BENCHMARK.md)
      Pisteet: (lukittu) arvo 3/3 · kiire 2/3 · työ M · myynti 1/3 · uutuus 0/2 = 7
      Mittari: data/fpl_xp_projections.json Danso GW12 xp 0.0 ja testit vihreät · tarkistus 2026-10-26
- [ ] xP-jäädytys päivittyy deadlineen asti (ylläpitäjän päätös 2026-10-16): `scripts/freeze_fpl_xp_gw.py`
  kirjoittaa kierroksen jäädytyksen uudelleen jokaisella ajolla niin kauan kuin kierroksen deadline ei ole mennyt, ja
  deadlinen jälkeen ei koskaan (immutable). Nyt olemassa olevaa ei ylikirjoiteta, joten jäädytys on noin vuorokauden
  vanha ja gameweek calls (päivittyy deadlineen asti) eroaa siitä (GW6 0.93). fpl_reference_gate säilyy (ep_next vain
  ennen deadlinea haetusta bootstrapista, is_next = kierros). Vaihetesti: ennen deadlinea päivittyy, deadlinen jälkeen
  ei muutu, puuttuva luodaan; testi kaatuu jos deadline-ehto poistetaan. (ylläpitäjän signaali 2026-10, lähde: Signaalit)
      Pisteet: (lukittu) arvo 3/3 · kiire 3/3 · työ M · myynti 1/3 · uutuus 0/2 = 9
      Mittari: tests/test_points_frozen_vs_calls.py: GW8 kutsujen ja jäädytyksen ero alle 0.05 · tarkistus 2026-10-26
- [ ] Jakokortin PIL-generaattori uuteen ulkoasuun: `scripts/gen_share_card.py` piirtää saman asettelun
  kuin SPA:n ja sivujen kortti (`scripts/share_card_js.py`, web/pro-spa). Todennus: `tests/test_share_card_*.py`
  vihreä ja uusi testi, joka vertaa kortin rivien järjestyksen ja otsikot JS-kortin sopimukseen.
  (ylläpitäjän signaali 2026-10, lähde: Signaalit)
      Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 1/3 · uutuus 1/2 = 6
      Mittari: testit vihreät; kortti näyttää samalta kuin SPA:n kortti · tarkistus 2026-11-16
- [ ] Brier, taitopiste ja kalibraatio /predictions-sivulle: näytä track record -osiossa Brier-piste, Brier skill
  score yksinkertaista perustasoa vastaan (sarjan koti-, tasapeli- ja vierasfrekvenssit samasta lokista) ja
  kalibraatiotaulukko, jotka /api/accuracy jo laskee. Luku luetaan artefaktista, ei lasketa sivulla uudelleen.
  llms.txt päivitetään samassa PR:ssä. (benchmark 2026-10-16, lähde: docs/BENCHMARK.md 4.5, https://arxiv.org/abs/2607.17765)
      Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 1/3 · uutuus 1/2 = 6
      Mittari: /predictions näyttää Brierin ja taitopisteen samalla n:llä kuin /api/accuracy; S17 vihreä · tarkistus 2026-11-16
- [ ] Hyökkäysvaikeus 6 GW:n ruudukkoon: joukkueen projisoidut maalit per ottelu seuraaville 6 GW:lle /fpl-sivun
  CS%-ruudukon rinnalle (malli laskee ne jo; nyt näkyy vain kuluva GW). Builder + regeneroitu sivu + llms.txt
  samassa PR:ssä. (benchmark 2026-10-16, lähde: https://www.fplform.com/ , https://www.fplrogue.com/tools)
      Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 1/3 · uutuus 1/2 = 6
      Mittari: /fpl näyttää projisoidut maalit 6 GW:lle; Cloudflare Web Analytics /fpl-käynnit · tarkistus 2026-11-16
- [ ] Kauden simulaatio kotimaisille sarjoille, vaihe 1: Monte Carlo jäljellä olevista otteluista omalla
  Dixon-Coles-mallilla, tuloksena mestaruuden, top-4:n ja putoamisen todennäköisyydet joukkueittain. Vaihe 1 =
  tuottajaskripti + testit (deterministinen siemen) + artefaktin muoto; ei Mestarien liigaa. Työnkulkuun kytkentä
  ja sivu ovat seuraavat vaiheet. (benchmark 2026-10-16, lähde: https://theanalyst.com/articles/premier-league-predictions-2026-27-opta-supercomputer , http://clubelo.com/)
      Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 1/3 · uutuus 2/2 = 7
      Mittari: skripti tuottaa todennäköisyydet, joiden summa per sija = 1; testit vihreät · tarkistus 2026-11-16
- [ ] FPL-todennäköisyyksien jäädytys: `scripts/freeze_fpl_xp_gw.py` jäädyttää xp:n lisäksi `xp_dist`-kentän
  p_haul (10+) ja p_blank, jotta haul-todennäköisyyksien kalibraatio voidaan julkaista kierrosten kertyessä.
  Vanhoja jäädytyksiä ei muuteta (immutable). (benchmark 2026-10-16, lähde: docs/BENCHMARK.md 4.5)
      Pisteet: arvo 2/3 · kiire 2/3 · työ S · myynti 1/3 · uutuus 1/2 = 8
      Mittari: seuraava data/fpl_xp_frozen/gw{n}.json sisältää p_haul ja p_blank · tarkistus 2026-10-26
- [ ] xP-horisontti GW19:ään, vaihe 1 (selvitys): mittaa minuuttiennusteen ja xP:n virhe horisontin funktiona
  jäädytetyistä kierroksista ja kirjoita tulos docs/:iin; päätös näkymän laajentamisesta ensimmäisen chip-puoliskon
  loppuun (GW19-deadline 2.1.2027) tehdään luvuilla. (benchmark 2026-10-16, lähde: https://fplreview.com/)
      Pisteet: arvo 2/3 · kiire 2/3 · työ L · myynti 2/3 · uutuus 1/2 = 7
      Mittari: selvitys docs/:ssa, MAE per horisontti-GW · tarkistus 2026-11-16
- [ ] Kenttäpelaajien rotaatioparit: laajenna Premiumin MV-rotaatioparit puolustajiin ja hyökkääjiin (2 tai 3
  pelaajan yhdistelmät, joiden CS% tai xP vuorottelee 6 GW:n aikana); API + SPA. (benchmark 2026-10-16,
  lähde: https://www.fplrogue.com/tools , https://www.fantasyfootballfix.com/premium/)
      Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 2/3 · uutuus 1/2 = 7
      Mittari: PostHog-tapahtuma rotaationäkymän avauksista · tarkistus 2026-11-30
- [ ] Miniliigan voittotodennäköisyys koko liigalle: laajenna "Catch your rival" simulaatioksi, joka antaa
  jokaiselle liigan jäsenelle voiton ja top 3:n todennäköisyyden jäljellä olevilla kierroksilla; API + SPA.
  (benchmark 2026-10-16, lähde: https://www.fplpulse.com/)
      Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 2/3 · uutuus 1/2 = 7
      Mittari: PostHog-tapahtuma miniliiganäkymän avauksista · tarkistus 2026-11-30
- [ ] Maalin ja maalipisteen todennäköisyys kuluvan GW:n xP-taulukkoon (top 20): P(maali) ja P(maali tai syöttö)
  jo olemassa olevasta xp_dist-simulaatiosta; ei kerroin- eikä "most likely" -kehystystä. (benchmark 2026-10-16,
  lähde: https://www.fantasyfootballpundit.com/)
      Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 1/3 · uutuus 1/2 = 6
      Mittari: /fpl/expected-points#gw-xp näyttää sarakkeet; Web Analytics -käynnit · tarkistus 2026-11-30

## Tehdyt
