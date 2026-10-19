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

- 2026-10: Yllapitaja: Bluesky-botin pitaa tietaa mitka postaukset herattavat kiinnostusta ja mitka saavat asiakkaita.
  Kiinnostus mitataan (data/bsky_performance.json), asiakkaat vaativat kanava-attribuution. → backlog 2026-10-16
- 2026-10: `data/fpl_xp_projections.json` `players[].this_season` (kuluvan kauden PL-minuutit, xGI ja xGI/90 FPL:n
  bootstrapista) on täytetty 100 %:lle pelaajista, mutta SPA ja mobiili eivät lue sitä: pelaajakortti näyttää
  kuluvan kauden luvun vain why-lauseessa, jonka `scripts/build_fpl_why.py` laskee omasta lähteestään. Autopilot S9
  nostaa kentän joka aamu (17.10).
- 2026-10: Lainaesteen PR:n (#1) jatko, kaksi vaihetta: (a) jos otsikkokierros on estokierros, rivin `xmins` on 0
  mutta `predicted_starts` ja minuuttijakauma (p_start, p_cameo, p_bench) tulevat yhä minuuttimallista, eli sama rivi
  sanoo "0 minuuttia" ja "aloittaa todennäköisesti". Ensimmäinen osuma xP-listan pelaajalla 17.10 mitattuna: GW12
  (GW8:n estopelaaja on excluded-listalla). (b) Tuplakierroksella este koskee vain emoseuraa vastaan pelattavaa ottelua, mutta PR nollaa koko kierroksen.
  FPL:n kentässä ei ole vastustajaa, se on vain notes-tekstissä ("face their parent club").
- 2026-10: Mallijoukkue jäi GW1-6 FPL-keskiarvosta 15 p, ja kapteenivalinta selittää koko eron (eniten kapteenoitu
  olisi tuonut 16 p lisää). Jäädytetyn xP:n yläpää: jokaisen kierroksen 20 suurinta xP:ta, toteuma miinus xP,
  FWD +0.55 (n 19), DEF -0.37 (n 41), MID -0.53 (n 55). Viikkobenchmarkista puuttuu yläpään kalibrointi
  pelipaikoittain ja mallin kapteenin ero eniten kapteenoituun (liukuva koko kausi). Parametrimuutos ei kuulu
  agentille (ylläpitäjän päätös); mittari kuuluu.
- 2026-10: /fpl#xp-accuracy pyöristää yhdistetyt rivit kahdesti: `src/models/fpl_xp_accuracy.py` `pool_groups`
  tekee `round(.., 3)` ja `scripts/build_fpl_page.py` `_mae_cell` vielä `:.2f`. Did not play -rivin GoalIQ-arvo
  0.9653 näkyy "0.96" (yksi pyöristys antaisi 0.97). Korjaus vaihtaa julkisen luvun; julkaistu teksti voi
  lainata vanhaa.
- 2026-10: tests.yml meni punaiseksi GW7-deadlinen aikana (17.10 noin 09:57-10:15 UTC, kolme peräkkäistä ajoa), koska
  `tests/test_xp_horizon_total_meta_routes.py` ja `tests/test_transfer_horizon_parity.py` kutsuvat live-FPL:n
  entry-rajapintaa, joka vastaa 503 kun peli päivittyy. Koodissa ei ollut vikaa. Sama toistuu joka deadline, ja
  pysyvästi punaiseksi tottunut putki nielee oikean regression. Testi ei saa riippua siitä, onko FPL ylhäällä.
- 2026-10: Huippumanagerien omistus (`data/fpl_elite_ownership.json`, top 1k/10k/100k, n=200 per taso) näkyy
  vain /fpl-sivulla. API ei tarjoa sitä eikä SPA:n pelaajakortti näytä sitä, vaikka kortissa on jo omistus-%.
  Jos se tuodaan kortille, otoskoko näkyy lukijalle samasta artefaktista kuin sivulla.
- 2026-10: SPA:n tulostila (TeamPitchManager settledView) näyttää ratkenneen kierroksen pelaajalle FPL:n nykyisen
  saatavuuslipun (`chance_of_playing_next_round`) ilman kierrosta, eli lippu näyttää koskevan jo pelattua kierrosta.
  Piilotus ei käy, koska ilmaispinnalla tulostila on päällä koko suunnitteluikkunan. Lippu sidotaan kierrokseen
  ("GW8 OUT" / "GW8 75%", deadline_gameweek) samalla lukijalla kuin muualla. Mobiilin vastaava kohta on ihmisen työ (OTA).
- 2026-10: xP-builderin esikausiehto `preseason = not any(finished)` tekee GW1:n aikana debytoineesta pelaajasta
  no_history-rivin, jolloin kortti sanoo "No PL minutes this season or last" noin 3-4 vrk. Seuraava osuma
  elokuu 2027; vaihetesti (ennen GW1:tä, GW1 kesken, GW1 gradattu) estää toiston.
- 2026-10: Deadlinen jälkeen API jää lukitulle kierrokselle, kunnes seuraava render-daily-deploy vie uuden datan
  Renderiin. 17.10 mitattuna: GW7-deadline 10:00 UTC, artefakti ja /fpl/model-xi siirtyivät GW8:aan 12:30, mutta
  /api/fantasy/captain ja /api/fantasy/edge palauttivat meta.gw 7 (data 09:53) vielä 12:40, koska 10:45-deploy oli
  myöhässä. Freezelle on jo vastaava askel (`scripts/render_deploy_after_freeze.py`); deadlinen ylitykselle ei ole.
  Työnkulun askel lisätään käsin mergen yhteydessä.
- 2026-10: `/fpl/expected-points`-sivun leimarivi näyttää "Updated <pvm> ·  · ", kun caveat on tyhjä
  (`scripts/build_fpl_longtail.py` noin rivi 5013): erotin kirjoitetaan ilman tarkistusta, onko sen jälkeen tekstiä.
- 2026-10: `fpl.html`:n meta-description on 174 merkkiä, vaikka builderin oma kommentti asettaa tavoitteeksi alle 160
  (hakutulos katkaisee). Testi, joka mittaa pituuden builderin tuloksesta, estää toiston.
- 2026-10: Mobiilin hintahälytys (`schedulePriceAlerts`) lukee yhä tallennetun watchlistin myös ilmaiselta, vaikka
  watchlist on 17.10 alkaen Premiumia. Ei lupaa mitään julkisesti, mutta lukko ja hälytys ovat eri mieltä. Mobiili on
  ihmisen työ (OTA).
- 2026-10: Ilmaiskäyttäjän pelaajakortti sanoo top 10:n ulkopuoliselle pelaajalle "Not on the club's set-piece lists
  right now", myös erikoistilanteiden hoitajalle: maskattu `/api/fantasy/xp` palauttaa `pool`-rivit ilman `set_pieces`-
  ja `p_start`-kenttiä, ja kortti tulkitsee puuttuvan kentän tyhjäksi listaksi (mobiili `PlayerSheet.tsx`
  `cardPlayerFor`). Puuttuva kenttä on "ei dataa" tai lukko, ei epätosi väite. Tarkista SPA:n pelaajakortti samasta
  syystä. Mobiili on ihmisen työ (OTA). (lähde: julkaisutarkistaja 18.10, App Store 1.0.10 -kuvaus)
- 2026-10: Championship-ennusteiden Brier on 0.674 (n=129, osuma 40.3 %), eli tasajakaumaa (0.667) huonompi, ja
  Premier League 0.628 (n=65). Liukuva Brier (100 ottelua) heikkeni 0.555:stä 0.582:een kahdessa päivässä, vaikka osuma
  nousi 59 %:iin. Vanhentuneet ennusteet (lead yli 48 h) osuvat 44.2 % (n=138) vs tuoreet 53.1 % (n=644).
  (lähde: data/accuracy.json, docs/BENCHMARK.md Muutokset 2026-10-18)
- 2026-10: xP häviää FPL:n ep_nextille pelaamattomien pelaajien luokassa joka kierroksella (GW6 MAE 0.945 vs 0.460),
  isoissa pisteissä (10+) joka kierroksella GW3-GW6 (GW6 9.29 vs 8.73) ja maalivahdeilla GW3-GW6. Kokonaisuutena
  GoalIQ hävisi GW4:n ja GW5:n (1.680 vs 1.648, 1.616 vs 1.588) ja voitti GW3:n ja GW6:n niukasti. Mallin muutos on
  ylläpitäjän päätös; mittari on jo olemassa. (lähde: data/fpl_xp_gw_accuracy.json)
- 2026-10: Kilpailijat siirtyvät julkiseen tarkkuuteen ja ilmaisiin ennusteisiin: FPLXI julkaisee kierroskohtaisen
  virheen (±1.17 p), FPL Pulse antaa ennustetut pisteet seuraavalle kierrokselle ilmaiseksi ja lupaa chip-ajoituksen
  myöhemmin kaudella, ScoreGPT myy 7/14/30 pv:n KPI-ikkunoita Pro-tasolla. (lähde: https://fplxi.com/ , https://www.fplpulse.com/ , https://scoregpt.app/)
- 2026-10: FPL-skeemavahdin ensimmäinen tilannekuva tallennettiin 18.10. (`data/fpl_schema_snapshot.json`), joten
  skeemamuutosta ei vielä voi todeta. Seuraava viikko antaa ensimmäisen diffin. (lähde: data/fpl_schema_snapshot.json)
- 2026-10: Hakukone ei ole ollut hankintakanava tällä kaudella, eikä 18.10 mitattu Search Consolen -83,5 % ollut
  pudotus: vertailujakson näytöistä 54 % tuli kolmena päivänä (kauden alun piikki 21.8), päivämediaanin muutos oli
  -69 % ja klikkien -22 %, ja hakuriveihin kirjatuista klikeistä valtaosa on brändihakuja. Käytön oikea pudotus
  alkoi viikolla 14.9, kun ilmainen Premium-ikkuna sulkeutui 12.9: uusien tilien viikkomäärä noin -80 %,
  sovelluksen ja työkalujen uniikit viikkokäyttäjät noin -65...-70 %. Taso on nyt myös alempi kuin ennen
  ikkunaa (heinä-elokuu), joten ikkuna ei selitä kaikkea. Hankintapolun rivien mittari kannattaa
  sitoa rekisteröitymisiin tai viikkokäyttäjiin, ei hakunäyttöihin. (lähde: Search Console päiväsarja, PostHog
  viikkokäyttäjät, mittausdata.py 19.10)
- 2026-10: Ottelusivut eivät pääse Googlen hakemistoon. `scripts/build_prediction_pages.py` poistaa ottelusivun
  kickoffissa ja URL palauttaa 404:n, joten sivu elää muutaman päivän, lyhyemmän ajan kuin indeksointi kestää.
  Search Consolessa (12.10) "Löydetty, ei toistaiseksi indeksoitu" -luokassa on 347 URL:ia, lähes kaikki
  ottelusivuja, ja ottelusivujen näytöt ovat olleet lähes nolla 22.8 alkaen. Vaihtoehto on pysyvä tulossivu
  (ennen kickoffia kirjattu ennuste ja toteuma samasta lokista kuin track record). Se muuttaa sivuston
  rakennetta, joten päätös on ylläpitäjän ennen riviä.
- 2026-10: pro.goaliq.app-juuri ei anna canonical-tagia, joten seurantaparametrit (`src`, `srcp`, `tab`) tekevät
  siitä kopioita: Search Console (12.10) listaa 125 parametrillista juuren URL:ia ilman valittua ensisijaista
  osoitetta, ja osa näkyy hakutuloksissa omina sivuinaan. Alireiteillä (esim. /spl) canonical on jo. Juuri saa
  canonicalin ilman kyselyparametreja samalla lukijalla kuin alireitit, ja testi kaatuu jos se puuttuu.

## Avoimet

- [ ] Automaattinen kierrosrecap goaliq.app/fpl/notes-sivulle (ylläpitäjän päätös 2026-10-17): muistioita ei enää
  kirjoiteta käsin, joten sivustolle ei tule uutta sisältöä. Uusi `scripts/build_fpl_recap_note.py` lisää
  `data/fpl_notes.json`:iin yhden recap-muistion kierrosta kohden samaan muotoon kuin nykyiset (slug, date, title,
  paragraphs, claims, check_url, cta), ja nykyinen `build_fpl_longtail.py` renderöi sen. Luvut VAIN artefakteista:
  `data/gw_recap.json` (mallijoukkueen pisteet vs FPL-keskiarvo, juokseva ero, kutsujen osumat ja hudit) ja
  `data/fpl_xp_gw_accuracy.json` comparison (GoalIQ xP vs form, MAE); jokainen luku claimsiin ja check_url sivulle,
  josta lukija näkee sen ilman tiliä (/fpl#xp-accuracy, /fpl#gw-calls, FPL:n entry-sivu). Tappiot mukaan samalla
  painolla kuin voitot. Vähintään kolme pohjaa vuorotellen (sama runko joka viikko on AI-tunnusmerkki), ei em dashia,
  data/rejected_phrases.json ja scripts/check_copy_style.py läpi. Muistio syntyy vain kun kierros on lopullisesti
  gradattu (ei provisional) ja täsmälleen kerran (idempotentti slug recap-gwN). Vaihetesti: ennen gradausta ei
  muistiota, provisional ei muistiota, gradattu tasan yksi, toinen ajo ei tuplaa; testi kaatuu jos gradausehto
  poistetaan. PR:n Julkinen teksti -osioon pohjat sanatarkasti (julkaisutarkistaja ennen mergeä). Työnkulun askel
  (gradauksen jälkeen fpl-data-refreshiin) lisätään käsin mergen yhteydessä. (ylläpitäjän signaali 2026-10, lähde: Signaalit)
      Pisteet: (lukittu) arvo 2/3 · kiire 2/3 · työ M · myynti 1/3 · uutuus 1/2 = 8
      Mittari: /fpl/notes näyttää GW8-recapin 48 tunnin sisällä GW8:n gradauksesta · tarkistus 2026-10-30
- [x] Lainaeste xP:hen: lue `elements[].scout_risks` (property `loan_ineligible`, `gameweek`) yhdellä lukijalla
  (esim. `src/models/fpl_xp.py: loan_ineligible_gws(element) -> set[int]`) ja aseta xP-putkessa
  (`scripts/build_fpl_xp.py`) pelaajan `gameweeks[].xp` ja `xmins` nollaksi niillä kierroksilla; horisonttisumma ja
  per-GW-jakauma samasta lähteestä. Testi synteettisellä elementillä, joka kaatuu jos kutsupaikka poistetaan, ja
  vaihetesti (estokierros horisontissa / ei horisontissa / jo pelattu). Todennus: seuraavan bottiajon jälkeen
  `data/fpl_xp_projections.json` Danso GW12 xp 0. (ylläpitäjän signaali 2026-10, lähde: Signaalit, docs/BENCHMARK.md) (PR, 2026-10-16)
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
- [ ] Kanava-attribuutio hubista sovellukseen: `ref-bridge.js` kuljettaa `utm_source`, `utm_medium`, `utm_campaign` ja
  `utm_content` jokaiseen pro.goaliq.app-linkkiin samalla tavalla kuin `ref`in (ensimmainen kosketus pysyy), ja SPA
  (`web/pro-spa/src/lib/partnerAttribution.ts`) tallentaa tilille avaimen `channel` = {source, campaign, content}
  ensimmaisesta kosketuksesta. `partner`-avain ja `ref` (provisiot) pysyvat ennallaan eika niita sekoiteta. Testit:
  ref-bridge kuljettaa utm:t ja vain sallitut merkit; attributionData kirjoittaa channelin vain kun tililla ei ole.
  (yllapitajan signaali 2026-10-16: botin pitaa tietaa mitka postaukset saavat asiakkaita, lahde: Signaalit)
      Pisteet: (lukittu) arvo 2/3 · kiire 3/3 · tyo M · myynti 3/3 · uutuus 1/2 = 10
      Mittari: uuden tilin raw_user_meta_data.channel.source = bluesky Bluesky-linkista tulleella · tarkistus 2026-11-01
- [ ] Konversio kanavittain: `/api/admin/conversion` palauttaa lisaksi aggregaatin `by_channel` (tilit ja Premiumit
  kanavan source ja campaign mukaan, myos `partner`-avaimesta), ei sahkoposteja eika kayttajarivejä. Sitten
  `scripts/bsky_bot.py perf` lukee sen ADMIN_TOKENilla ja kirjoittaa data/bsky_performance.json:iin `customers`-
  osion aiheittain (utm_campaign = aihe). Testit: aggregaatti synteettisilla kayttajilla, ei henkilotietoja vastauksessa.
  Tyonkulun bsky-bot.yml perf-askel tarvitsee ADMIN_TOKEN-envin: lisataan kasin mergen yhteydessa.
  (yllapitajan signaali 2026-10-16, lahde: Signaalit; riippuu edellisesta rivista)
      Pisteet: (lukittu) arvo 2/3 · kiire 2/3 · tyo M · myynti 3/3 · uutuus 1/2 = 9
      Mittari: data/bsky_performance.json customers-osio ei tyhja kun kanavalta on tili · tarkistus 2026-11-15
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
- [ ] Pelaajan tasaisuus stats-taulukkoon: lisää /fpl/stats-sivulle ja SPA:n Players/stats-näkymään sarakkeet
  "return rate" (osuus pelatuista kierroksista, joilla pelaaja sai vähintään 5 pistettä) ja pisteiden hajonta per
  aloitus, laskettuna FPL:n kierroshistoriasta, jota stats-näkymä jo lukee; vähimmäisaloitukset näkyvät, puuttuva
  arvo on "ei dataa". Builder + regeneroitu sivu + llms.txt samassa PR:ssä. Free/Premium-sijoitus ehdotetaan
  PR:n rungossa, ihminen päättää. (aallonharja 2026-10-18, lähde: https://www.fplrogue.com/tools)
      Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 2/3 · uutuus 2/2 = 8
      Mittari: /fpl/stats näyttää sarakkeet ja testi vihreä; Web Analytics -käynnit /fpl/stats · tarkistus 2026-11-30
- [ ] Rullaavat aikaikkunat track recordiin: `/api/accuracy` palauttaa osuuden ja Brierin myös viimeisiltä 30 ja 90
  päivältä (ottelun päivän mukaan, sama loki, n näkyy), ja /predictions näyttää ne nykyisen rolling-100:n rinnalla.
  Luku luetaan artefaktista, ei lasketa sivulla. Ei muokkaa kirjattuja ennusteita. llms.txt päivitetään samassa
  PR:ssä. (aallonharja 2026-10-18, lähde: https://scoregpt.app/)
      Pisteet: arvo 2/3 · kiire 1/3 · työ S · myynti 2/3 · uutuus 1/2 = 8
      Mittari: /api/accuracy sisältää ikkunat ja /predictions näyttää samat n:t; testit vihreät · tarkistus 2026-11-30

## Tehdyt
