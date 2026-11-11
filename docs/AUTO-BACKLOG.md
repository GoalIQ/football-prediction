# Auto-backlog

Auto-kehitysagentti (`.github/workflows/auto-kehitys.yml`) tekee tästä listasta yhden rivin ajoa kohden
ja avaa PR:n. Aallonharja (`.github/workflows/aallonharja.yml`) lisää rivejä viikoittaisesta
benchmarkista. Säännöt, pisteet ja kiellot: `docs/TUOTEPERIAATTEET.md`. Ihminen mergeää.

Rivi, joka tarvitsee uuden bottiajon tai työnkulun askeleen: agentti kirjoittaa tuottajaskriptin ja testin,
ja PR:n Julkaisu-osio kertoo, mihin työnkulkuun askel lisätään. Työnkulun muutos tehdään käsin mergen yhteydessä.

## Signaalit

Havainnot, joista agentti tekee rivejä (enintään yksi ajoa kohden, alle 30 päivää vanhat). Ei henkilöiden
nimiä, ei sitaatteja, ei hintoja. Merkintä "→ backlog <pvm>" kertoo, että havainnosta on tehty rivi.

- 2026-11: Kumppanin utm ei kulje hubista tilille. `web/pro-spa/src/lib/partnerAttribution.ts` lukee
  `utm_medium=partner` + `utm_source` vain pro.goaliq.appin osoiteriviltä, ja `ref-bridge.js` kantaa hubista SPA:han vain
  `ref`-parametrin. goaliq.app/fpl?utm_medium=partner&utm_source=X -linkistä luotu tili ei saa `user_metadata.partner`-
  merkintää. Sama koskee Bluesky-botin linkkejä (`scripts/bsky_bot.py` SITE = https://goaliq.app, `utm_link`):
  kanava-attribuutio näyttää 0 vaikka tilejä tulisi. Korjaus: ref-bridge kantaa myös partner-utm:t, testi molemmille reiteille.
- 2026-11: `src/data/fpl_match_xg.team_xg_by_fixture` / `match_xg_rows` summaa pelaajan xG:n NYKYISEN bootstrapin joukkueelle
  ja yhdistää NYKYISEN kauden fixture-id:ihin. Edellisen kauden kaudelle (`summary_2526` levyllä, kuten CI:ssä) loaderin
  -FD-täydennys antaa siksi väärän xG:n väärille otteluille, ja kesken kauden siirtynyt pelaaja kirjautuu uuden seuransa
  otteluun. PL-fitti ei enää käytä tätä (`season_match_frame`, `was_home`-kenttä, fp #120). Korjaus: täydennys samalle
  `aggregate_matches`-lukijalle, testi siirtyneelle pelaajalle ja edelliselle kaudelle.
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
  nostaa kentän joka aamu (17.10). → backlog 2026-10-23
- 2026-10: Lainaesteen PR:n (#1) jatko, kaksi vaihetta: (a) jos otsikkokierros on estokierros, rivin `xmins` on 0
  mutta `predicted_starts` ja minuuttijakauma (p_start, p_cameo, p_bench) tulevat yhä minuuttimallista, eli sama rivi
  sanoo "0 minuuttia" ja "aloittaa todennäköisesti". Ensimmäinen osuma xP-listan pelaajalla 17.10 mitattuna: GW12
  (GW8:n estopelaaja on excluded-listalla). (b) Tuplakierroksella este koskee vain emoseuraa vastaan pelattavaa ottelua, mutta PR nollaa koko kierroksen.
- 2026-10: Kierrosrecapista (`scripts/build_fpl_recap_note.py`, PR #6) puuttuu tulos-kappale: joukkueen pisteet
  FPL:n keskiarvoa vastaan. Ylläpitäjän ohje 19.10: lähde on `data/gw_recap.json`:n `entry_series` (entry 116920,
  FPL:n omat pisteet ennen siirtokuluja, chipit mukaan, ja FPL:n `average_entry_score`), ei `running`-sarja.
  Tarkistuslinkki on FPL:n kierrossivu `https://fantasy.premierleague.com/entry/116920/event/{gw}` ja juoksevalle
  erolle `https://fantasy.premierleague.com/entry/116920/history`. Sanamuoto "We play our model's squad in FPL
  (entry 116920)", ja kierroksella pelattu chip kerrotaan meidän valintanamme. Muistioformaatissa on yksi
  `check_url` (/fpl), joten tulos-kappale tarvitsee oman linkin tekstissä tai oman muistion.
  FPL:n kentässä ei ole vastustajaa, se on vain notes-tekstissä ("face their parent club").
- 2026-10: Mallijoukkue jäi GW1-6 FPL-keskiarvosta 15 p, ja kapteenivalinta selittää koko eron (eniten kapteenoitu
  olisi tuonut 16 p lisää). Jäädytetyn xP:n yläpää: jokaisen kierroksen 20 suurinta xP:ta, toteuma miinus xP,
  FWD +0.55 (n 19), DEF -0.37 (n 41), MID -0.53 (n 55). Viikkobenchmarkista puuttuu yläpään kalibrointi
  pelipaikoittain ja mallin kapteenin ero eniten kapteenoituun (liukuva koko kausi). Parametrimuutos ei kuulu
  agentille (ylläpitäjän päätös); mittari kuuluu.
  Mitattu 22.10 (ylläpitäjän päätös: korjataan, jos mittaus tukee): parametrimuutosta EI tehty. Deadline-hetken
  projektiossa (viimeinen mainin `data/fpl_xp_projections.json` ennen deadlinea, `components` vs FPL:n explain,
  GW2-7) MID top-10 -0.18 (SE 0.57, n 60), top-20 +0.06 (SE 0.37, n 120), kaikki MID -0.09 (SE 0.06, n 1330).
  Yllä oleva -0.53 on jäädytetystä xP:stä (noin vuorokausi ennen deadlinea, GW1 mukana), ja yksi pelaaja tuo
  siitä noin puolet. `PREV_SEASON_CARRY` ei siirrä kärjen harhaa: MID top-20 xGI/90 harha +0.03 (0.0) … +0.01
  (0.7), ja koko joukon MAE paranee painon kasvaessa (0.189 -> 0.179). Mittariin kuuluu siis myös ero
  jäädytetyn ja deadline-projektion välillä. Seurattava: FWD-syötöt toteuma - ennuste +0.16 (SE 0.05, n 306)
  ja FWD-maalit -0.18 (SE 0.09), kuusi kierrosta.
- 2026-10: Ylläpitäjä kysyi 22.10, miksi kärjen keskikenttäpelaajan ennuste on korkea, vaikka kauden tulos on
  heikko. Vastaus löytyi vain repon datasta: kuluvan kauden xGI/90 (ilman yhtä ottelua) on alle puolet viime
  kauden tasosta, ja viime kausi kantaa noin 60 % vauhdista (`PREV_SEASON_CARRY` 0.5). Pelaajakortti ei näytä
  kumpaakaan. Sama kenttä kuin yllä (`players[].this_season` + `last_season`, autopilot S9): kortille kuluvan ja
  viime kauden xGI/90 rinnakkain, jotta lukija näkee mihin luku nojaa. → backlog 2026-10-23
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
- 2026-10: Hakukone ei ole ollut hankintakanava tällä kaudella. Search Consolen näyttöjen päivämediaani laski noin
  -67 % (elo-syyskuun taso palasi heinäkuun tasolle 16.9 alkaen), mutta klikkien päivämediaani ei muuttunut ja
  hakuriveihin kirjatut klikit ovat brändihakuja (19.10: 100 %). 18.10:n -83,5 %:ia liioitteli kauden alun piikki
  21.8 (54 % vertailujakson näytöistä kolmena päivänä). Näyttöjen lasku ei näy kävijöissä. Käytön oikea pudotus
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
  rakennetta, joten päätös on ylläpitäjän ennen riviä. Ylläpitäjä päätti 19.10: pysyvä tulossivu. → backlog 2026-10-19
- 2026-10: pro.goaliq.app-juuri ei anna canonical-tagia, joten seurantaparametrit (`src`, `srcp`, `tab`) tekevät
  siitä kopioita: Search Console (12.10) listaa 125 parametrillista juuren URL:ia ilman valittua ensisijaista
  osoitetta, ja osa näkyy hakutuloksissa omina sivuinaan. Alireiteillä (esim. /spl) canonical on jo. Juuri saa
  canonicalin ilman kyselyparametreja samalla lukijalla kuin alireitit, ja testi kaatuu jos se puuttuu.
- 2026-10: Myyvä todiste on FPL:n itse tarkistettava luku, mutta sitä ei käytetä. Mallin rungolla pelattava joukkue
  (entry 116920; runko tulee mallista, chipit ovat ylläpitäjän päätöksiä) on FPL:n entry history -rajapinnan mukaan GW1-6 yhteensä +25 pistettä FPL:n keskiarvon yläpuolella (chipit
  mukana), ja GW7:n alustavilla luvuilla kokonaissijoitus on noin top 15 %. `data/gw_recap.json` sisältää kaksi
  sarjaa: `running` (jäädytetty mallijoukkue ilman chippejä, -15 viidellä kierroksella, ei ilmaispinnalla) ja
  `entry_series` (FPL:n oma luku). Recap-PR käytti ensimmäistä, ja julkaisutarkistaja blokkasi sen, koska lukua ei
  löydy ilmaispinnalta. SPA:n neljässä lukkokomponentissa (`Paywall`, `LockedToolPreview`, `PersonalLock`,
  `PremiumPreview`) ei ole yhtään viittausta track recordiin tai tarkkuuteen (grep 19.10), eli ostohetkellä ei näy
  todistetta. Ylläpitäjä päätti 19.10: todiste ilmaispinnalle ja jokaiseen lukkoon. → backlog 2026-10-19
- 2026-10: Ensimmäisen puoliskon chipit vanhenevat GW19:n deadlinessa (2.1.2027). Jokaisella managerilla, jolla on
  chippejä käyttämättä, on päätös edessä marras-joulukuussa, ja chip timing on Premiumissa. Ilmaista näkymää "mitkä
  chipit minulla on jäljellä ja kuinka kauan" ei ole (grep web/pro-spa 19.10). Ylläpitäjä päätti 19.10:
  chip-tarkistin ilmaiseksi, ajoitussuunnitelma lukon takana. → backlog 2026-10-19
- 2026-10: X-linkkien kanava ei tallennu tilille: `utm_source=x` ja `utm_medium=partner` hylätään, koska
  `web/pro-spa/src/lib/partnerAttribution.ts`:n `PARTNER_RE = /^[a-z0-9_-]{2,32}$/` vaatii vähintään kaksi merkkiä.
  Koskee X-viikkoketjua ja Bluesky-botin X-peilausta, eli X:stä tulleita tilejä ei voi erottaa. Kuuluu
  kanava-attribuutiorivin testeihin: lähde `x` tallentuu, ja testi kaatuu, jos yhden merkin lähde hylätään.
  (julkaisutarkistaja 19.10)
- 2026-10: IHMISEN PROJEKTI (ei agentille): henkilökohtainen deadline-viesti nykyisille ilmaistileille (oman joukkueen
  kapteeni ja lukittu siirtoehdotus xP-hyötyineen). Massalähetys ei toiminut (GW5-deadlineviesti 18.9: avattu
  7,2 %, klikkejä 0), mutta viesti omasta joukkueesta ei ole massalähetys. `profiles.fpl_entry_id` on olemassa,
  push_tokens-taulussa entry ID:tä ei ole. Kanava (push vai sähköposti) on ylläpitäjän päätös, ja sitä varten
  mitataan ensin, kuinka suurella osalla tileistä entry ID on tallessa. → backlog 2026-10-19 (vain mittaus)
  Ylläpitäjä valitsi 19.10 pushin (osto onnistuu sovelluksessa, sähköposti ei toiminut). Rakennettu käsin:
  `scripts/push_dispatch.py` lähettää 24 h -ikkunassa henkilökohtaisen rungon samasta siirtosuunnitelmasta kuin
  sovellus, ja PostHog-tapahtuma `push_personal` kertoo tavoitettavuuden (entry ID:lliset ja henkilökohtaiset).
- 2026-10: Ennusteet ovat pimennetty tuote. Sovelluksessa ennustenäkymällä on vähintään yhtä paljon käyttäjiä kuin
  FPL-näkymällä, ja ennusteiden lukot tuottavat napautuksia noin kaksinkertaisesti FPL-lukkoihin verrattuna
  (PostHog 1.7.2026 alkaen, uniikit käyttäjät, mobiili). Silti kaikki jakelu on FPL:ää: Bluesky-botin
  `briefing.numbers` ei sisällä yhtään ottelun lukua, ja aivojen ohje puhuu vain FPL-managereille. Ylläpitäjä päätti
  20.10: ennusteet takaisin näkyviin kokeiluna GW10-katsaukseen asti, ja tulos luetaan ostopolusta tuotteittain
  (mittausdata `ostopolku.tuotteittain`, lisätty käsin 20.10). Store-tekstit eivät muutu ennen kuin iOS-version
  ikärajapäätös on tehty. → backlog 2026-10-20
- 2026-10: Julkisessa View Sourcessa on suomea: `<!-- GEN:FREE-...-START  check_free_window.py --fix renderoi
  taman; ala muokkaa kasin -->` etusivulla neljästi (index.html, merkit FREE-BAND, FREE-CTA, FREE-HERO-PRICE ja
  yksi sivun alempana) ja /predictions-sivulla kerran. `tests/test_viewsource_comments.py`:n `FINNISH`-sanalista ei
  tunne sanoja renderoi, taman, ala muokkaa ja kasin, joten portti on vihreä. `scripts/check_free_window.py`
  tunnistaa merkin regexillä `GEN:{key}-START[^>]*-->`, joten merkin perään voi kirjoittaa englanniksi (esim.
  "rendered by check_free_window.py --fix; do not edit by hand") skriptiin koskematta, ja sanalista laajenee samassa
  muutoksessa. Huom: index.html on agentilta kielletty (myyntilupaus), joten etusivun merkit vaihtaa ihminen
  mergen yhteydessä. (julkaisutarkistaja 20.10)
- 2026-10: Bluesky-botin kaatunut aivoajo kuluttaa aikaikkunan. 20.10 09 UTC Claude-kutsu palautti virheen
  (tilauksen katkos, 0 tokenia), mutta julkaise-job ajoi `publish --thought`, joka kirjaa `last_think_at`:n
  aina kun `think == 'true'`, eikä katso aivojen tulosta. Seuraava aivoajo oli vasta 17 UTC, eli päivän
  ensimmäinen ikkuna meni ilman uusintaa. Lisäksi punaisesta bsky-ajosta ei tule kenellekään ilmoitusta:
  ajon käynnistää fp-dispatch-relay (github-actions[bot]), joten GitHubin epäonnistumisviesti menee botille.
  Ylläpitäjä huomasi katkoksen vain siitä, että X-jonon issueita ei tullut. Korjaus kahdessa osassa:
  (a) `--thought` vain kun aivojen askel onnistui (työnkulun ehto, käsin mergen yhteydessä) ja/tai
  `cmd_publish` ei kirjaa `last_think_at`:ia ilman jonoa; (b) aivojen kaatuminen avaa tai päivittää
  yhden issuen ylläpitäjälle (sama kanava kuin X-jono, ei uutta issueta joka tunti).
- 2026-10: X-jonon issuet (label `x-jono`) jäävät auki: 20.10 auki 9, vanhimmat 18.10 ("tonight" -hintapostauksia,
  jotka vanhenevat samana päivänä). Issuen teksti pyytää sulkemaan käsin, mutta mikään ei lue tilaa
  (x_viikkoketju tarkistaa otsikot myös suljetuista). Ylläpitäjä kysyi 20.10, pitääkö ne sulkea erikseen.
  Ehdotus: `bsky_bot x-mirror` ja `x_viikkoketju` sulkevat omat issuensa, kun ne vanhenevat (bsky-peili 24 h,
  kierrosketju seuraavan deadlinen jälkeen) kommentilla "vanhentunut, ei postattu tai postattu käsin";
  issuen tekstistä pois sulkemispyyntö. Kummallakin askeleella on jo `issues: write`, joten työnkulkuun ei koskea.
- 2026-10: docs/bsky/AANI.md kieltää aivoja kirjoittamasta hashtageja (julkaisu lisää #FPL:n itse), mutta mikään ei
  valvo sitä: aivojen kirjoittama "#GW8" saa `tag_facets`-facetin ja menee portin läpi. Ehdotus: `bsky_gate` hylkää
  kirjaimella alkavan tunnisteen muualla kuin julkaisun lisäämänä #FPL:nä (omat postaukset) ja kokonaan vastauksista;
  numerolla alkava "#3" (sijoitus, käytössä vastauksissa 22.10) sallitaan. Testi positiivisella ja negatiivisella
  kontrollilla. (julkaisutarkistaja 22.10, PR #37)

- 2026-10: Ylläpitäjä 23.10: Bluesky-botti muodostaa mielipiteet itse, eikä niitä omista kukaan. 22.10 yksi botin
  vastaus luettiin väärin, ja ylläpitäjä korjasi sen käsin. Kanta tulee ylläpitäjältä kerran kierroksessa, ja botti
  käyttää mallin lukua sen todisteena. → backlog 2026-10-23
- 2026-10: Ylläpitäjä 23.10: X-jono teki 18.-22.10 viidessä päivässä 15 issueta, ja jokainen teksti kopioitiin X:ään
  käsin. Hyväksynnän on oltava helpompaa kuin ohittamisen, ja X:ään menee päivän paras postaus. → backlog 2026-10-23
- 2026-10: Ylläpitäjä 23.10: kun ylläpitäjän kanta on botin raaka-aineena, kierroksen tulos voi verrata ylläpitäjän ja
  mallin kapteenia FPL:n omilla pisteillä. Toistuva asetelma antaa syyn seurata tiliä. Riippuu kanta-rivistä.
- 2026-10: xP voitti FPL:n ep_nextin GW7:llä (MAE 1.608 vs 1.735) ja kolmella viidestä vertailukierroksesta (GW3, GW6, GW7;
  GW4 ja GW5 hävisi niukasti). Heikkoudet toistuvat: pelaamattomat (0.993 vs 0.558), maalivahdit (1.293 vs 1.055) ja
  isot pisteet (7.977 vs 7.091, n 11) häviävät yhä, kun taas DEF, MID ja FWD voittavat GW7:llä. Mallin muutos on
  ylläpitäjän päätös; kilpailijoiden julkinen virhe (FPLXI ±1.07 p GW7:llä) mitataan eri otoksella. (lähde: data/fpl_xp_gw_accuracy.json,
  https://fplxi.com/)
- 2026-10: Hakukone, 28 vrk (25.9.-22.10.): näyttöjen päivämediaani -62.8 %, klikkien päivämediaani 0.0 %, brändihakujen
  osuus klikeistä 100 %; Search Consolen tulkinta: "Kummassakaan jaksossa ei ole piikkiä: kokonaismuutos ja
  mediaanimuutos ovat vertailukelpoisia." /fpl on sijalla 8.6 mutta CTR 0 %, /faq sijalla 3.6 ja CTR 0 %. Tulos viittaa
  siihen, että tason lasku on todellinen eikä piikin loppu. (lähde: Search Console, https://goaliq.app/fpl)
- 2026-10: Ostopolku, ennuste vs FPL (mobiili, napautus lukosta, nyt vs edellinen 28 vrk): ennuste 18.9 % (13.6 %), FPL
  0.0 % (0.8 %); webissä FPL 3.4 % (12.5 %), ennusteen web-otos on pieni. Ostoja kummallakin mobiilituotteella 0. Ennustelukot
  kasvattavat napautusosuutta samalla kun FPL-lukot eivät. (lähde: mittausdata ostopolku.tuotteittain)
- 2026-10: Kilpailijat täyttävät chip- ja mallijoukkueaukkoa: FPL Pulse listaa "Chip Timing Suggestions" yhä kohdassa
  tulossa myöhemmin kaudella, FPL Rogue myy Chip Planneria ja Template Team -näkymää Pro-tasolla. GW19-deadline la 2.1.2027 on ensimmäinen ikkuna, jossa chip-ajoituksella on aikaraja. (lähde: https://www.fplpulse.com/ ,
  https://www.fplrogue.com/tools)
- 2026-10: Bluesky-botin portti (`src/marketing/bsky_gate.py`) tarkistaa luvut mutta ei pelaajan roolia. 26.10 klo 09 UTC
  postaus (`data/bsky_posted.jsonl`, at 2026-10-26T09:54:16) tarjosi puolustajaa joukkueensa hyökkäyksen halvempana
  vaihtoehtona. Luvut täsmäsivät sivuun, rooli ei: pelaajan xP tulee puhtaan pelin todennäköisyydestä, ja sivu näyttää
  hänet DEF-rivinä. Reply-moduulin pelaajariveillä on `pos`, mutta portti ei lue sitä. Samassa postauksessa vertailu
  "on the same number" läpäisi, vaikka avaimissa oli toiselle pelaajalle vain hinta (`captain_top5.<slug>.price`) eikä
  xP:tä: implisiittinen luku ei ole numero, joten `allowed_numbers` ei näe sitä. Puuttuu kaksi tarkistusta: (a) DEF- tai
  GKP-pelaajaa ei kuvata samassa lauseessa hyökkäyssanoilla (attack, attacker, forward, striker, up front) eikä FWD- tai
  MID-pelaajaa puolustussanoilla; (b) jokaisella pelaajalla, johon lause liittää luvun tai vertailun (same number,
  level with, matches), on oma `gw_xp`-avain. Testi kummallekin tämän postauksen muodolla ja negatiivinen kontrolli
  (sama lause ilman roolisanaa menee läpi). (lähde: data/bsky_posted.jsonl, https://goaliq.app/fpl/expected-points)
- 2026-10: Bluesky-botin CS-postaus 26.10 klo 17 UTC (`data/bsky_posted.jsonl`, at 2026-10-26T17:54:05) antoi kaksi
  puhtaan pelin lukua, mutta vastustajan vain ensimmäiselle ("38.1% to keep a clean sheet against Fulham ... with Arsenal
  next on 37%"). Ylläpitäjä luki toisen luvun kahdesti ensimmäisen joukkueen luvuksi (ensin edellisen kierroksen
  vastustajaa, sitten Arsenalia vastaan). Luvut olivat oikein ja sivun FAQ:n mukaisia, mutta lause ei kertonut, kenen
  luku ja mitä ottelua vastaan. Puuttuu portin tarkistus: jokaisen `cs_top.<joukkue>.cs_pct`-luvun lauseessa on
  joukkueen vastustaja (reply-moduulin rivillä on ottelu ja koti/vieras), esimerkiksi "Arsenal next on 37% at
  Liverpool". Testi tämän postauksen muodolla ja negatiivinen kontrolli (vastustajan kanssa menee läpi).
  (lähde: data/bsky_posted.jsonl, https://goaliq.app/fpl)
- 2026-10: Minuuttimallin aloitustodennäköisyyden yläpää on ylivarma. Deadline-hetken projektio (viimeinen mainin
  `data/fpl_xp_projections.json` ennen deadlinea, `p_start` riveillä joiden `xp_dist.gw` on kierros) vs FPL:n
  `event/{gw}/live` `starts`, GW2-8: `p_start` >= 0.99 aloitti 90/99 (0.91), 0.95-0.99 aloitti 106/113 (0.94).
  Alempana kalibrointi pitää: 0.80-0.90 0.87 (n 425), 0.90-0.95 0.92 (n 414), 0.50-0.80 0.73 (n 466). Huteja
  >= 0.99 -luokassa oli jokaisella kierroksella GW2-8. Myöhäinen ottelu ei selitä eroa: kun joukkueen ottelu alkoi
  yli 24 h deadlinen jälkeen, >= 0.99 aloitti 27/29. Vaikutus kapteeniin: GW8:lla mallin kapteenin `p_start` oli
  1.0 ja xP 5.93, eniten kapteenoidun 0.925 ja 5.63, ja mallin kapteeni ei pelannut. Yläpään 9 prosenttiyksikön
  harha on sillä rivillä noin 0.5 xP, ero eniten kapteenoituun 0.30. Parametrimuutos on ylläpitäjän päätös;
  agentille kuuluu mittari: `p_start`-kalibrointi luokittain viikkobenchmarkiin deadline-projektiosta.
  (lähde: data/fpl_xp_projections.json git-historia, data/gw_calls.json gw 8, https://goaliq.app/fpl#gw-calls)
- 2026-10: Kanta-issuen vastaus ei ole päässyt botille kertaakaan. `scripts/bsky_kanta.py` `read()` hyväksyy vain
  kommentit, joiden `author_association` on OWNER tai MEMBER, mutta ylläpitäjän jäsenyys orgissa on yksityinen, ja
  ulkopuolinen näkymä antaa samalle kommentille CONTRIBUTOR. GW9-issueen vastattiin 29.10 klo 15:10 UTC. Jokainen
  bsky-bot-ajo sen jälkeen kirjasi "uusi kanta False", ja klo 17 UTC aivoajo (`last_think_at` 17:51) teki
  player-postauksen ilman owner_takea. Sama vika korjattiin `.github/auto-kehitys/korjaus.py`:ssä 21.10
  kirjautumisnimellä (`YLLAPITAJAN_LOGINIT`), mutta 23.10 kirjoitettu `bsky_kanta.py` kopioi vanhan säännön, ja
  `current_takes` nielee virheet hiljaa (`except Exception: return []`). Puuttuu: (a) `read()` hyväksyy
  ylläpitäjän kirjautumisnimen samasta joukosta kuin korjaus.py (yksi lähde, ei kopiota); (b) should-think ja
  context tulostavat, montako kommenttia luettiin ja montako hylättiin millä syyllä; (c) testi, jossa kommentin
  association on CONTRIBUTOR ja kirjautumisnimi ylläpitäjän (menee läpi), ja negatiivinen kontrolli (muu
  kirjautumisnimi CONTRIBUTOR-tasolla ei mene). (lähde: https://api.github.com/repos/GoalIQ/football-prediction/issues/64/comments
  ilman tunnusta: author_association CONTRIBUTOR; https://api.github.com/orgs/GoalIQ/public_members tyhjä)
  → korjattu käsin 2026-10-30 ylläpitäjän pyynnöstä (a, b ja c), ei riviä agentille.
- 2026-11: Konversiovälin keskipiste laski noin 37 % viikossa (2,07-2,48 % → 1,23-1,65 %, vertailukelpoinen, ei tarkka).
  Ostopolun napautusosuus lukosta on ennallaan (web 13,2 % vs 12,8 %, mobiili 13,2 % vs 14,4 %), mutta FPL-lukkojen
  napautusosuus on 0,0 % sekä mobiilissa (1,4 %) että webissä (12,5 %), kun ennustelukot napauttavat 21,9 % (19,2 %).
  (lähde: mittausdata konversio ja ostopolku.tuotteittain, docs/BENCHMARK.md Muutokset 1.11.2026)
- 2026-11: Search Console 2.-29.10.: näyttöjen päivämediaani -58,3 %, klikkien päivämediaani 0,0 %, ei piikkiä. /fpl/stats on
  sijalla 2,9 ja CTR 0 %. Sivun meta-description on yli 160 merkkiä ja kertoo sarakkeista, ei syytä avata. → backlog 2026-11-01
  (lähde: Search Console https://goaliq.app/fpl/stats)
- 2026-11: xP voitti FPL:n ep_nextin GW8:lla (MAE 1,670 vs 1,795) ja neljällä kuudesta vertailukierroksesta. Pelaamattomat
  (0,988 vs 0,511) ja maalivahdit (1,546 vs 1,055) häviävät yhä, isot pisteet tasan (8,086 vs 8,100, n 15). Mallin
  muutos on ylläpitäjän päätös. (lähde: data/fpl_xp_gw_accuracy.json)
- 2026-11: ScoreGPT ryhmittelee ottelut varmuusluokkiin (High, Medium, Low) ja myy luokkien tarkkuuden Pro-tasolla. GoalIQ:n
  kalibraatio kertoo, missä todennäköisyys on epävarma: 0,65-lokero aliarvioi (0,648 vs 0,717, n 138), 0,84-lokero yliarvioi
  (0,839 vs 0,762, n 21). Lukija ei näe tätä ottelusivulla. → backlog 2026-11-01
  (lähde: data/accuracy.json, https://scoregpt.app/)
- 2026-11: Chip Timing -työkalua ei ole vielä FPL Pulsella (merkitty tulossa), Fixin Premiumilla eikä FFH:lla (vain opas).
  GW19-deadline la 2.1.2027 on 62 päivän päässä. Jo avoin chip-tarkistinrivi kattaa ilmaisen puolen.
  (lähde: https://www.fplpulse.com/ , https://www.fantasyfootballfix.com/premium/)
- 2026-11: Fixtures-rivin luku (kirjattu ennuste lokista) ja saman ottelun Predict-luku (malli ajetaan pyynnöstä) eroavat:
  2.11 Everton-Coventry 49/29/22 vs 53/28/20, Arsenal-Hull 71/21/8 vs 65/25/10. Lukija näkee samasta ottelusta kaksi lukua
  ilman selitystä. (lähde: /api/accuracy?include=pending, /api/predict, julkaisutarkistaja #85)
- 2026-11: llms.txt ("that same logged prediction is what the public track record grades") ja ottelusivujen lause
  "The prediction above is the one logged before kick-off and graded" eivät kerro, että kirjattu rivi voi muuttua aloitukseen
  asti (`scripts/accuracy_pipeline.py` `_refreshable`). Record-sivu korjattiin #85:ssä; portti
  `tests/test_record_ei_vaita_lukittua.py` laajennetaan näihin muotoiluihin samassa PR:ssä.
- 2026-11: Kolme Mestarien liigan joukkuetta (Shaktar, Sporting CP, Sl. Bratislava) ei esitäytä Predictiä Fixturesista, koska
  otteluohjelman ja mallin nimet eroavat (`web/pro-spa/src/lib/teamMatch.ts`, sama vika oli Forestilla ennen #85:tä).
- 2026-11: Squad-signals-vahti (`scripts/squad_signals_watch.py`) ajetaan kahdesti päivässä, ja päivän toinen ajo
  kirjoittaa `squad-signals-<pvm>.md`:n yli vertailulla saman päivän aamukuvaan. 3.11 aamun 29 erikoistilannemuutosta ja
  3 saatavuusmuutosta katosivat raportista (jäivät lokiin ja git-historiaan), tilalle jäi 1 rivi. Toisen ajon pitäisi
  lisätä osio eikä korvata tiedostoa.
- 2026-11: Mobiilisovelluksen Fixtures-rivi ei saa todennäköisyyspalkkia otteluille, joissa on Académico de Viseu FC
  (3.11: 116/117 seuraavan 7 päivän riviä sai palkin). Loki tuntee joukkueen nimellä "Academico Viseu", mutta
  goaliq-appin `lib/fixtureNames.ts` jättää nimen tarkoituksella mappaamatta (rivin 186 kommentti), ja peruste on vanhentunut.
- 2026-11: Bluesky-botin `owner_take`-postaus typisti ylläpitäjän perustelun. Kannassa oli vertailu: hylätyn vaihtoehdon
  katto, valitun vaihtoehdon katto ja johtopäätös. Postaukseen jäi vain ensimmäinen, joten lause ei kytkeytynyt valintaan.
  Ylläpitäjä luki sen ristiriidaksi ja poisti postauksen 6.11. Postauksessa pitää olla valitun vaihtoehdon peruste tai sana,
  joka sitoo perustelun valintaan. Aivojen ohje (`.github/workflows/bsky-bot.yml`) ja tarkistaja
  (`.claude/agents/bsky-tarkistaja.md`) ovat agentin ulottumattomissa, joten ne muutetaan käsin mergen yhteydessä.
- 2026-11: `scripts/bsky_bot.py` `cmd_perf` ei tunnista poistettua postausta. `bsky.get_posts` ei palauta sitä, joten lokirivi
  jää arvoon `engagement` 0 ja `topic_table` laskee sen aiheen tilastoon. 6.11 poistettu postaus nosti `owner_take`-aiheen
  n:n kahteen ja laski `engaged_rate_bayes`-arvon 0,667:stä 0,5:een, ja aiheen mittari tarkistetaan 2026-11-22. Puuttuva uri
  pitää merkitä poistetuksi ja jättää taulukosta pois, mutta vain kun haku itse onnistui.
- 2026-11: `optimal_xi` (`src/models/fpl_rate_team.py`) valitsee avauksen horisontti-xP:llä eikä kierroksen xP:llä. GW10:n
  jäädytetyssä mallirivissä penkille jäi pelaaja, jonka kierros-xP oli 0,7 suurempi kuin aloittavan, vaikka muodostelma olisi
  ollut laillinen. Jäädytettyyn riviin ei kosketa, koska se on julkinen loki. Avauksen pitää lukea saman kierroksen xP.
- 2026-11: `src/marketing/public_surface.py` hakee saraketta tarkalla nimellä `6GW xP`, mutta sivujen otsikko on `{n_gw}GW xP`.
  Kun ikkunassa on muu määrä kierroksia (6.11 mitattu `5GW xP`), `/fpl/expected-points`- ja seurasivujen luvut jäävät pois
  reply-moduulista. Vika on turvallinen, koska luku puuttuu eikä väärää lukua synny. Sarake pitää hakea ikkunan pituudesta riippumatta.
- 2026-11: `load_xp_actionable` (`src/models/fpl_xp.py`) rajaa kierrokset artefaktin `meta.deadline_gameweek`:sta, joka on
  rakennushetken arvo. Kun xP-builderi on kaatunut (Understat-katko 1.11 alkaen, artefaktissa 10), deadlinen jälkeen lukija pitää
  menneen kierroksen mukana: mitattu oikealla artefaktilla, rivit GW10-14 ja horisonttisumma sisältää GW10:n kellosta riippumatta.
  Lukijaa käyttävät `api/partner_feed.py` ja `src/models/fpl_player_stats.py`; `/api/fantasy/xp` lukee samaa kenttää
  `attach_horizon_total_actionable`:n kautta. PR #92 nojasi juuri tähän
  lukijaan ("lukijat suojaa"), mutta se suojaa vain, kun builder ajaa. `open_gameweek` lukee kellosta, mutta xP-artefaktissa ei ole
  `deadlines`-listaa, joten se palauttaa None. Hub-sivut ja reply-moduuli ovat kunnossa (phase0:ssa lista on, moduuli kieltäytyy
  deadlinen jälkeen). Ensimmäinen kerta 6.11 18:30Z, koska edellinen deadline meni ennen katkoa. Vaihetesti puuttuu tältä tilalta:
  vanhentunut artefakti deadlinen jälkeen (`tests/test_gameweek_phase_invariants.py`).
- 2026-11: Understat-katkon aikana `/fpl`:n GW-taulukon projected goals ja CS-% ovat 1.11:n sovituksesta, ottelusivujen voitto-%
  päivittyy. GW10:ssä sama ottelu on 61,0 % `/api/fantasy`:ssa ja 45 % ottelusivulla; samalla sivulla näkyvä xG 2,28-1,20 ei sovi
  45 %:iin. Erot keskittyvät nousijoihin (16, 6,5 ja 4,9 prosenttiyksikköä), muut ottelut ovat alle 3,5:n. Syy on mittaamatta:
  sovituksen päivä vai nousijoiden eri käsittely. Molemmat luvut ovat julkisia, eikä lukija näe, että ne ovat eri mallitilasta.
- 2026-11: `tests/test_committed_pages_match_builder.py` lupaa, ettei vertailussa ole kelloa, mutta `fact_context` lukee
  `page_gameweek()`:n kautta oikeaa kelloa. Deadlinen ja seuraavan sivurakennuksen valissa testi on punainen, vaikka sivu on
  oikein (6.11 18:30Z: tests.yml punainen commitilla f51d45a8c9, korjaantui bottiajossa 18:37Z). Builderia ei pida muuttaa:
  `/fpl`:n taulukko siirtyy seuraavaan kierrokseen, joten sivun ei pida enaa vaittaa samaa lukua. Testin pitaa lukea sama kello
  kuin sivun rakennushetki.
- 2026-11: xP hävisi FPL:n ep_nextille GW9:llä (MAE 1,467 vs 1,383), ja koko ero tulee pelaamattomista (0,953 vs 0,511, n 184 eli noin
  38 % jäädytetyistä riveistä). Pelanneilla GoalIQ voitti (1,777 vs 1,910), samoin MID (1,211 vs 1,251) ja blank-luokassa (1,129 vs 1,298).
  Maalivahdit (1,467 vs 0,919) ja isot pisteet (8,217 vs 6,986, n 7) häviävät yhä. Kolmella seitsemästä vertailukierroksesta GoalIQ
  häviää (GW4, GW5, GW9). Mallin muutos on ylläpitäjän päätös. (lähde: data/fpl_xp_gw_accuracy.json)
- 2026-11: Konversiovälin keskipiste on ennallaan (1,22-1,63 % vs 1,23-1,65 %, vertailukelpoinen, ei tarkka). Ostopolulla webin
  napautus lukosta nousi (33,3 % vs 14,3 %), mutta nousu tulee "muu"-luokan lukoista (40,7 % vs 12,5 %); FPL-lukot napauttavat 0,0 %
  sekä mobiilissa (2,1 % edellisellä jaksolla) että webissä (10,0 %), ja ennustelukot mobiilissa 21,9 % (13,6 %). Ostoja ei ole
  yhdelläkään tuotteella. → backlog 2026-11-08 (ennustelukko)
  (lähde: mittausdata konversio ja ostopolku.tuotteittain, docs/BENCHMARK.md Muutokset 8.11.2026)
- 2026-11: Search Console 9.10.-5.11.: näyttöjen päivämediaani +42,9 %, klikkien +50,0 %. Tulkinta sanatarkasti: "Vertailujakson
  näytöistä 43.5 % tuli kolmena päivänä (2026-09-11, 2026-09-12, 2026-09-14). Kokonaismuutos mittaa piikin loppumista, ei tason
  muutosta: käytä mediaanimuutosta." Kokonaisnäytöt -28,8 % on siis piikin loppu. Haku "rate this team out of 100" on sijalla 1 ja
  CTR 0 % (näytöt 1-9), eikä hub-sivuilla ole sivua, joka vastaisi siihen: rate my team on vain pro.goaliq.app:ssa. → backlog 2026-11-08
  (lähde: Search Console https://goaliq.app/fpl , https://goaliq.app/llms.txt)
- 2026-11: Kilpailijat myyvät miniliigan ja eliitin päätöksiä maksullisena: FPL Pulse Pro antaa kapteenipoiminnat "Future"- ja
  "Mini-League"-välilehdillä, Fixin Premium Plus eliittimanagerien live-siirtohälytykset ja kapteenidatan ennen deadlinea. GoalIQ:n
  miniliiganäkymä antaa H2H-voittotodennäköisyyden mutta ei sitä, mitä liigan muut kapteenoivat. → backlog 2026-11-08
  (lähde: https://www.fplpulse.com/ , https://www.fantasyfootballfix.com/premium/)
- 2026-11: Bluesky-botin ennusteaihe (kokeilu GW10-katsaukseen asti) ei herätä reaktioita: `by_topic.prediction` n 5, engaged 0,
  `engaged_rate_bayes` 0,143, kun muiden aiheiden mediaani on noin 0,29. Kokeilun mittari ❌ 8.11. Kokeilun jatko on ylläpitäjän päätös.
  (lähde: data/bsky_performance.json)
- 2026-11: X-jonon päiväkatto ei pitänyt kahtena päivänä: 3.11. syntyi kaksi issueta (#89, #90) ja 26.10. kolme (#54-#56), muut
  päivät yksi. Syy on mittaamatta. (lähde: https://github.com/GoalIQ/football-prediction/issues?q=label%3Ax-jono)

## Avoimet

- [x] Ylläpitäjän kanta Bluesky-botin raaka-aineeksi, kokeilu GW9-GW11 (ylläpitäjän päätös 2026-10-23): botti
  muodostaa nyt mielipiteet itse, ja 22.10 yksi vastaus luettiin väärin niin, että ylläpitäjä korjasi sen käsin. Uusi
  `scripts/bsky_kanta.py`: (a) `ask` avaa kerran kierroksessa noin 48 tuntia ennen deadlinea ylläpitäjälle issuen
  (label `kanta`, idempotentti otsikko `Kanta GW<N>`, sama issue-rajapinta kuin X-jonolla) ja siinä kolme kysymystä:
  kenet kapteenoit ja miksi, missä olet eri mieltä mallin kanssa, mikä meni pieleen viime kierroksella. Ylläpitäjä
  vastaa sähköpostilla, ja vastaus tulee issueen kommenttina. (b) `read` palauttaa vain kuluvan kierroksen issuen
  kommentit, joiden author_association on OWNER tai MEMBER (sama sääntö kuin `.github/auto-kehitys/korjaus.py`), ja
  `scripts/bsky_bot.py` `cmd_context` lisää ne briefingiin kenttään `owner_take` (gw, teksti, aika); ilman vastausta
  kenttä on tyhjä. Uusi aihe `owner_take` TOPICS-listaan. `src/marketing/bsky_gate.py` hylkää `owner_take`-itemin,
  jos briefingissä ei ole saman kierroksen vastausta (botti ei voi keksiä ylläpitäjän kantaa), vaatii tekstiin
  ilmaisun, joka kertoo kannan olevan tilin takana olevan ihmisen eikä mallin (sallitut ilmaisut portissa), ja
  hylkää tekstin, joka väittää postauksen olevan ihmisen kirjoittama. Luvut yhä vain reply-moduulista, ja
  automaatiomaininta biossa säilyy. Vaihetesti: ei issueta yli 48 tuntia ennen deadlinea, issue tasan kerran
  kierroksessa, deadlinen jälkeen vastausta ei käytetä; testi kaatuu, jos OWNER/MEMBER-suodatus tai portin
  kierrosehto poistetaan. Työnkulun muutos tehdään käsin mergen yhteydessä: `ask` bsky-bot.yml:n tuntiajoon ja
  aivojen ohjeeseen yksi kohta (kun `owner_take` on, vähintään yksi item rakentuu sen ympärille, mallin luku
  todisteena). PR:n Julkinen teksti -osioon kolme esimerkkipostausta sanatarkasti (julkaisutarkistaja ennen mergeä).
  (ylläpitäjän signaali 2026-10-23, lähde: Signaalit) (PR, 2026-10-23)
      Pisteet: (lukittu) arvo 2/3 · kiire 3/3 · työ M · myynti 3/3 · uutuus 2/2 = 14
      Mittari: data/bsky_performance.json by_topic.owner_take n vähintään 3 ja engaged_rate_bayes vähintään muiden aiheiden mediaani · tarkistus 2026-11-22
- [x] X-jonoon yhden napautuksen postaus ja enintään yksi issue päivässä (ylläpitäjän päätös 2026-10-23): X-jono teki
  18.-22.10 viidessä päivässä 15 issueta, ja ylläpitäjä kopioi jokaisen tekstin X:ään käsin. `scripts/bsky_bot.py`
  `x_issue` lisää runkoon X:n oman jakolinkin `https://x.com/intent/tweet?text=` + `x_version` urlenkoodattuna:
  ylläpitäjä napauttaa, X avautuu teksti valmiina ja hän painaa itse Post (ei rajapintaa eikä automaatiota). Kuvaa
  jakolinkki ei tue, joten kortin kuva ja sen linkki säilyvät rungossa. `cmd_x_mirror` tekee päivässä (UTC) enintään
  yhden issuen: ensin `owner_take`-aiheinen postaus, muuten päivän ensimmäinen (aivot listaavat parhaan ensin). Muut
  merkitään `x_skipped`-listaan, ja ohitettujen määrä tulostetaan ajon lokiin. `scripts/x_viikkoketju.py` saa saman
  linkin ketjun ensimmäiselle postaukselle. Testi: linkin dekoodattu teksti on täsmälleen `x_version`, toista issueta
  ei synny samana päivänä, ja testi kaatuu, jos kattoehto poistetaan. (ylläpitäjän signaali 2026-10-23, lähde:
  Signaalit) (PR, 2026-10-26)
      Pisteet: (lukittu) arvo 1/3 · kiire 2/3 · työ S · myynti 1/3 · uutuus 1/2 = 7
      Mittari: label x-jono -issueita enintään yksi päivässä 2026-10-26 alkaen, ja jokaisen rungossa on x.com/intent-linkki (github.com/GoalIQ/football-prediction/issues?q=label:x-jono) · tarkistus 2026-11-08
      Tulos 2026-11-08: ❌ GitHubin x-jono-issuelista (julkinen sivu): 26.10. syntyi kolme issueta ja 3.11. kaksi, eli enintään yksi päivässä ei täyttynyt kahtena päivänä (27.10.-2.11. ja 4.-5.11. yksi päivässä); x.com/intent-linkin esiintymistä rungoissa ei voinut varmistaa, koska sivu näyttää vain otsikot
- [x] Ottelusivu pysyy kickoffin jälkeen tulossivuna (ylläpitäjän päätös 2026-10-19): `scripts/build_prediction_pages.py` (PR, 2026-10-28)
  ei enää poista ottelusivua, vaan sivu jää samaan URL:iin ja näyttää ennen kickoffia kirjatun ennusteen
  (`data/prediction_log.json`, sama rivi kuin track recordissa, lukuja ei lasketa uudelleen), toteuman kun rivillä on
  `result`, muuten tilan "result pending", ja linkin /predictions#record. Sama maskaus kuin nyt (vain 1X2-%).
  Kauden jo poistetut sivut syntyvät uudelleen samasta lokista samalla slug-logiikalla (esim.
  /predictions/la-liga/real-madrid-vs-real-sociedad palaa 404:stä). Julkaistu URL ei koskaan vaihdu: jos myöhempi
  ottelu saisi saman slugin, se saa päivämääräsuffiksin. Liigahub listaa tulevien rinnalla viimeisen 7 päivän
  pelatut, ja sivustokartta sisältää pelatut (lastmod = tuloksen päivä). Vaihetesti samalla rivillä: ennen
  kickoffia, kickoffin jälkeen ilman tulosta, tuloksen jälkeen; ennusteluvut ja URL identtiset kaikissa
  vaiheissa, ja testi kaatuu jos poisto (`unlink`) palaa tai luku tulee muualta kuin lokista. Cloudflare Pagesin
  20 000 tiedoston raja tarkistetaan builderissa. PR:n Julkinen teksti -osioon pelatun sivun otsikko ja
  tuloslauseet sanatarkasti (julkaisutarkistaja ennen mergeä). (ylläpitäjän signaali 2026-10-19, lähde: Signaalit)
      Pisteet: (lukittu) arvo 2/3 · kiire 2/3 · työ L · myynti 3/3 · uutuus 1/2 = 11
      Mittari: pelattu ottelusivu palauttaa 200 ennusteen ja tuloksen kanssa, ja gsc.json:n sivut-listalla on vähintään 20 ottelusivua (19.10: 9) · tarkistus 2026-12-14
- [x] Ottelun ennuste Bluesky-botin aiheeksi, kokeilu GW10-katsaukseen asti (ylläpitäjän päätös 2026-10-20): botti (PR, 2026-10-30)
  ei voi nyt postata ottelun lukua, koska reply-moduulissa ei ole ottelukohtaista osiota. Lisää
  `src/marketing/reply_sections.py`:hin osio `matches`: seuraavien 72 tunnin ottelut, joilla on julkaistu
  ottelusivu, ja niiden 1X2-todennäköisyydet samasta lähteestä ja samalla muotoilulla kuin ottelusivulla
  (`data/prediction_log.json`; `scripts/build_prediction_pages.py`:n `_upcoming_by_comp` ja `_fmt_pct` siirretään
  yhdeksi lukijaksi, jota sivu ja osio kutsuvat). Jokaisen luvun `page` on ottelusivun URL, ja track record -osion
  sivu on /predictions#record. Ottelu ilman julkaistua sivua ei tule osioon. Vaihetesti: ennen kickoffia mukana,
  kickoffin jälkeen ei; testi kaatuu, jos osion luku eroaa sivun luvusta tai jos kutsupaikka poistetaan.
  `bsky_gate` hylkää vedonlyöntisanat myös ennusteaiheessa (testi ennusteaiheen tekstillä). Työnkulun muutos
  tehdään käsin mergen yhteydessä: `bsky-bot.yml`:n aivojen ohjeeseen ennusteaihe kokeilun ajaksi (noin joka
  kolmas item aiheella prediction tai track_record); ohjeen ehdotus PR:n Julkaisu-osioon. PR:n Julkinen teksti
  -osioon kolme esimerkkipostausta sanatarkasti (julkaisutarkistaja ennen mergeä). (ylläpitäjän signaali
  2026-10-20, lähde: Signaalit)
      Pisteet: (lukittu) arvo 2/3 · kiire 3/3 · työ M · myynti 3/3 · uutuus 1/2 = 13
      Mittari: data/bsky_performance.json by_topic.prediction n vähintään 3 ja engaged_rate_bayes vähintään muiden aiheiden mediaani · tarkistus 2026-11-08
      Tulos 2026-11-08: ❌ data/bsky_performance.json by_topic.prediction: n täyttää rajan (vähintään 3), mutta engaged_rate_bayes 0,143 on alle muiden aiheiden mediaanin (noin 0,29; 12 muuta aihetta), eikä yhtään postausta ole herättänyt reaktiota
- [x] Bluesky-botin omat postaukset noin 3 h välein ja #FPL-tunniste tag-facetilla, kokeilu (ylläpitäjän päätös 2026-10-22, tehty
  käsin PR #36 ja tunnisteen PR): 16.-21.10 viitenä päivänä kaksi omaa postausta 0-5 s välein. Mitattu 22.10: suosituimman
  FPL-syötteen 180 postauksesta 114 kantaa #fpl:n, omista 18:sta ei yksikään. Avainsanasyötteet löytävät botin jo linkin
  "goaliq.app/fpl" kautta (syöte keräsi ennen 21.10 vain 3-34 postausta vuorokaudessa, sen jälkeen noin 150). Tilikuratoituun
  FPL-syötteeseen tunniste ei vie: se vaatii pyynnön kuraattorille (julkaisu, ylläpitäjän GO). Mittari mittaa välin ja
  tunnisteen yhdessä.
      Pisteet: (lukittu) arvo 1/3 · kiire 2/3 · työ S · myynti 1/3 · uutuus 1/2 = 7
      Mittari: data/bsky_performance.json followers viimeisin vähintään 10 (2026-10-22: 5) tai omien postausten tykkäyksiä keskimäärin yli 0,25 per postaus 2026-10-23 alkaen (16.-22.10: 4 tykkäystä 16 postauksesta) · tarkistus 2026-11-06
      Tulos 2026-11-08: ✅ data/bsky_performance.json followers: viimeisin merkintä (8.11. klo 09.54 UTC) on 10 eli täyttää rajan "vähintään 10" (22.10.: 5), kasvu noin kaksinkertainen; tykkäysehtoa ei tarvittu
- [x] Automaattinen kierrosrecap goaliq.app/fpl/notes-sivulle (ylläpitäjän päätös 2026-10-17): muistioita ei enää (PR #6, 2026-10-21, osittain: kutsut ja tarkkuus; tulos-kappale Signaaleissa)
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
      Tulos 2026-11-01: ✅ data/fpl_xp_gw_accuracy.json: GW8 graded_at 2026-10-26T15:47:40Z, data/fpl_notes.json: recap-gw8 päivätty 2026-10-26, eli samana päivänä; PostHog näyttää sivun /fpl/note/recap-gw8 käyntejä pienessä kokoluokassa
- [x] Lainaeste xP:hen: lue `elements[].scout_risks` (property `loan_ineligible`, `gameweek`) yhdellä lukijalla
  (esim. `src/models/fpl_xp.py: loan_ineligible_gws(element) -> set[int]`) ja aseta xP-putkessa
  (`scripts/build_fpl_xp.py`) pelaajan `gameweeks[].xp` ja `xmins` nollaksi niillä kierroksilla; horisonttisumma ja
  per-GW-jakauma samasta lähteestä. Testi synteettisellä elementillä, joka kaatuu jos kutsupaikka poistetaan, ja
  vaihetesti (estokierros horisontissa / ei horisontissa / jo pelattu). Todennus: seuraavan bottiajon jälkeen
  `data/fpl_xp_projections.json` Danso GW12 xp 0. (ylläpitäjän signaali 2026-10, lähde: Signaalit, docs/BENCHMARK.md) (PR, 2026-10-16)
      Pisteet: (lukittu) arvo 3/3 · kiire 2/3 · työ M · myynti 1/3 · uutuus 0/2 = 7
      Mittari: data/fpl_xp_projections.json Danso GW12 xp 0.0 ja testit vihreät · tarkistus 2026-10-26
      Tulos 2026-11-01: ➖ data/fpl_xp_projections.json: Danso GW12 xp 0.0 ja xmins 0.0 (täyttyy), mutta testien vihreyttä ei voinut mitata, koska pytest-ajo ei ollut sallittu tässä ajossa
- [ ] Entry 116920:n kirjanpito ilmaispinnalle (ylläpitäjän päätös 2026-10-19): `data/gw_recap.json`
  `entry_series` (entry 116920, FPL:n omat pisteet chipit mukaan ja FPL:n `average_entry_score`) näkyy
  goaliq.app/fpl-sivulla omana osionaan `#model-entry`: kierroksittain pisteet, FPL-keskiarvo, ero ja juokseva ero,
  sekä kokonaissijoitus ja managerien määrä. Sijoitus ja managerien määrä tulevat FPL:n entry history- ja
  bootstrap-rajapinnasta samalla haulla, ja `scripts/build_gw_recap.py` lisää ne sarjaan (`overall_rank`,
  `total_players`). Vain lopullisesti gradatut kierrokset (FPL `finished` ja `data_checked`): kesken oleva kierros ei
  näy lukuna. Peruste näkyy tekstissä (FPL:n pisteet ennen siirtohittejä, chipit mukana) ja hitit omana
  sarakkeenaan. Linkki FPL:n entry-sivulle, josta lukija tarkistaa saman luvun. Yksi lukija (esim.
  `src/models/model_squad_scores.py: model_entry_ledger()`), jota sivu ja API käyttävät, ja sama lukija syöttää
  seuraavan rivin lukot. Vaihetesti: kesken oleva kierros ei näy, gradattu näkyy, uusi kausi ei peri edellisen
  sarjaa; testi kaatuu, jos gradausehto poistetaan. Builder, regeneroitu sivu ja llms.txt samassa PR:ssä. Julkinen
  sanamuoto: "We play our model's squad in FPL (entry 116920)", ja chipit mainitaan meidän päätöksinämme;
  "model's own FPL team" on hylätty (`data/rejected_phrases.json`, 29.9), koska chipit eivät tule mallista. PR:n
  Julkinen teksti -osioon otsikko ja lauseet sanatarkasti. (ylläpitäjän signaali 2026-10-19, lähde: Signaalit)
      Pisteet: (lukittu) arvo 2/3 · kiire 3/3 · työ M · myynti 3/3 · uutuus 1/2 = 13
      Mittari: goaliq.app/fpl#model-entry näyttää jokaisen gradatun kierroksen, ja luvut täsmäävät FPL:n entry history -rajapintaan (testi ja live) · tarkistus 2026-11-02
- [ ] Todiste jokaiseen lukkoon (ylläpitäjän päätös 2026-10-19): SPA:n lukkokomponentit (`Paywall.svelte`,
  `LockedToolPreview.svelte`, `PersonalLock.svelte`, `PremiumPreview.svelte`) näyttävät yhden todisterivin
  edellisen rivin lukijasta: entry 116920:n juokseva ero FPL-keskiarvoon ja kokonaissijoitus viimeisimmän
  gradatun kierroksen jälkeen, ja linkit /fpl#model-entry-osioon ja FPL:n entry-sivulle. Luku näytetään sellaisenaan
  myös silloin, kun ero on negatiivinen: testi kaatuu, jos rivin näkyminen riippuu luvun etumerkistä. Puuttuva sarja
  tarkoittaa, että riviä ei näytetä (ei nollaa). Premium-lupauksen teksti, hinnat ja ostopainikkeet eivät muutu.
  Testi kaatuu, jos todisterivi puuttuu yhdestäkin neljästä komponentista. PR:n Julkinen teksti -osioon rivi
  sanatarkasti. Riippuu edellisestä rivistä. (ylläpitäjän signaali 2026-10-19, lähde: Signaalit)
      Pisteet: (lukittu) arvo 2/3 · kiire 3/3 · työ M · myynti 3/3 · uutuus 1/2 = 13
      Mittari: kaikki neljä lukkoa näyttävät todisterivin (testi), ja mittausdatan ostopolussa upgrade_tapped/paywall_shown-suhde 28 vrk ei ole pienempi kuin edellisen 28 vrk:n · tarkistus 2026-11-23
- [ ] Chip-tarkistin: ensimmäisen puoliskon chipit ennen GW19:ää (ylläpitäjän päätös 2026-10-19): ilmainen työkalu,
  joka kertoo entry ID:llä, mitkä chipit ovat käyttämättä, mihin kierrokseen asti kukin on käytettävissä ja montako
  kierrosta on jäljellä. Chip-ikkunat luetaan FPL:n bootstrapin `chips`-listasta (`start_event`, `stop_event`)
  yhdellä lukijalla, ei kovakoodattua GW19:ää, ja käytetyt chipit entryn historiasta. Mallin ehdotus kierrokseksi on
  Premiumin chip timing: ilmaisversio näyttää lukitun kortin, joka avaa sen (ominaisuus ei siirry rajan yli).
  Pinnat: API ja SPA:n ToolsHome. PostHog-tapahtuma `chips_left_checked` sekä lukon `paywall_shown` ja
  `upgrade_tapped` lähteellä `chips_left`. Vaihetesti: ennen ensimmäisen ikkunan loppua, ikkunan viimeinen kierros,
  ikkunan jälkeen (toisen puoliskon chipit), chip jo käytetty, tuplakierros; testi kaatuu, jos ikkuna kovakoodataan.
  PR:n Julkinen teksti -osioon merkkijonot sanatarkasti. (ylläpitäjän signaali 2026-10-19, lähde: Signaalit)
      Pisteet: (lukittu) arvo 2/3 · kiire 2/3 · työ M · myynti 3/3 · uutuus 2/2 = 13
      Mittari: mittausdatan PostHog-tapahtumissa chips_left_checked näkyy, ja ostopolussa on lähde chips_left · tarkistus 2026-11-23
- [ ] Entry ID -osuus konversioaggregaattiin (ylläpitäjän päätös 2026-10-19): `/api/admin/conversion` palauttaa
  lisäksi kentät `entry_id_share_pct_free` ja `entry_id_share_pct_premium`, eli kuinka suurella osalla ilmais- ja
  Premium-tileistä `profiles.fpl_entry_id` on tallessa. Ei määriä eikä käyttäjärivejä vastauksessa. Tarvitaan
  päätökseen henkilökohtaisesta deadline-viestistä (ihmisen projekti, Signaalit). Testi synteettisillä profiileilla:
  osuus oikein, tyhjä profiilijoukko antaa null eikä nollaa. Lisäksi `push_reach_pct`: kuinka suurella osalla
  deadline-muistutuksen kytkeneistä laitteista on tili ja entry ID (sama liitos kuin `/api/admin/push-targets`),
  koska henkilökohtainen push tavoittaa vain ne. (ylläpitäjän signaali 2026-10-19, lähde: Signaalit)
      Pisteet: (lukittu) arvo 1/3 · kiire 3/3 · työ S · myynti 3/3 · uutuus 0/2 = 11
      Mittari: mittausdatan konversio-osiossa on entry ID -osuus ilmais- ja Premium-tileille · tarkistus 2026-11-02
- [ ] Kanava-attribuutio hubista sovellukseen: `ref-bridge.js` kuljettaa `utm_source`, `utm_medium`, `utm_campaign` ja
  `utm_content` jokaiseen pro.goaliq.app-linkkiin samalla tavalla kuin `ref`in (ensimmainen kosketus pysyy), ja SPA
  (`web/pro-spa/src/lib/partnerAttribution.ts`) tallentaa tilille avaimen `channel` = {source, campaign, content}
  ensimmaisesta kosketuksesta. `partner`-avain ja `ref` (provisiot) pysyvat ennallaan eika niita sekoiteta. Testit:
  ref-bridge kuljettaa utm:t ja vain sallitut merkit; attributionData kirjoittaa channelin vain kun tililla ei ole.
  (yllapitajan signaali 2026-10-16: botin pitaa tietaa mitka postaukset saavat asiakkaita, lahde: Signaalit)
      Pisteet: (lukittu) arvo 2/3 · kiire 3/3 · tyo M · myynti 3/3 · uutuus 1/2 = 10
      Mittari: uuden tilin raw_user_meta_data.channel.source = bluesky Bluesky-linkista tulleella · tarkistus 2026-11-01
- [ ] xP-jäädytys päivittyy deadlineen asti (ylläpitäjän päätös 2026-10-16): `scripts/freeze_fpl_xp_gw.py`
  kirjoittaa kierroksen jäädytyksen uudelleen jokaisella ajolla niin kauan kuin kierroksen deadline ei ole mennyt, ja
  deadlinen jälkeen ei koskaan (immutable). Nyt olemassa olevaa ei ylikirjoiteta, joten jäädytys on noin vuorokauden
  vanha ja gameweek calls (päivittyy deadlineen asti) eroaa siitä (GW6 0.93). fpl_reference_gate säilyy (ep_next vain
  ennen deadlinea haetusta bootstrapista, is_next = kierros). Vaihetesti: ennen deadlinea päivittyy, deadlinen jälkeen
  ei muutu, puuttuva luodaan; testi kaatuu jos deadline-ehto poistetaan. (ylläpitäjän signaali 2026-10, lähde: Signaalit)
      Pisteet: (lukittu) arvo 3/3 · kiire 3/3 · työ M · myynti 1/3 · uutuus 0/2 = 9
      Mittari: tests/test_points_frozen_vs_calls.py: GW8 kutsujen ja jäädytyksen ero alle 0.05 · tarkistus 2026-10-26
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

- [ ] Pelaajakortille kuluvan ja viime kauden xGI/90 rinnakkain (ylläpitäjän päätös 2026-10-23): ylläpitäjä kysyi
  22.10, miksi kärjen keskikenttäpelaajan ennuste on korkea, vaikka kausi on heikko, ja vastaus löytyi vain repon
  datasta. Kortti näyttää viime kauden per 90 -luvut (`last_season`, `last_season_show`), mutta kuluvan kauden
  xGI/90:n vain silloin, kun why-lause valitsee sen (mitattu 23.10: 85 lauseessa 150:stä). Lisää palvelimella
  laskettu `xgi_this_per90` pelaajan payloadiin samalla lukijalla kuin why-lause (`src/models/fpl_xp.py`
  `xgi_per90(player)["this"]`, minuuttiraja `XGI_SEASON_MIN_MINUTES`), ja
  `web/pro-spa/src/lib/components/PlayerCard.svelte` näyttää sen viime kauden xGI/90:n vieressä (this season / last
  season). Alle minuuttirajan kortti näyttää syyn eikä lukua, eikä SPA laske lukua itse. Testi: payloadin luku on
  sama kuin `xgi_per90`:n, ja testi kaatuu, jos kutsupaikka poistetaan; vitest: kortti näyttää molemmat luvut ja alle
  rajan syyn. Mobiilin vastaava kohta on ihmisen työ (OTA). (ylläpitäjän signaali 2026-10-22, lähde: Signaalit)
      Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 3/3 · uutuus 1/2 = 11
      Mittari: PlayerCard.svelte renderöi xgi_this_per90:n viime kauden xGI/90:n vieressä ja payload-testi on vihreä · tarkistus 2026-11-08
- [ ] /fpl-sivun hakutulos: `scripts/build_fpl_page.py` (noin rivi 2525) kirjoittaa meta-descriptionin, joka on noin 172
  merkkiä, vaikka builderin oma kommentti tavoittelee alle 160 (hakutulos katkaisee lauseen lopun). Search Consolen mukaan
  /fpl on keskimäärin sijalla 8.6 ja CTR 0 %, ja näyttöjä on kymmeniä, joten katkeava kuvaus on ainoa hakutuloksen osa, jonka
  agentti voi muuttaa. Lyhennä kuvaus alle 160 merkkiin niin, että sijoitus ja ilmainen "no sign-in" säilyvät ja Premium-lupaus
  ei muutu (copy julkaisutarkistajan kautta); regeneroitu fpl.html ja llms.txt samassa PR:ssä. Testi mittaa pituuden
  builderin tuloksesta (ei kovakoodattua merkkijonoa) ja kaatuu, jos raja ylittyy. PR:n Julkinen teksti -osioon uusi kuvaus
  sanatarkasti. (aallonharja 2026-10-25, lähde: Search Console https://goaliq.app/fpl , Signaalit)
      Pisteet: arvo 1/3 · kiire 1/3 · työ S · myynti 3/3 · uutuus 0/2 = 9
      Mittari: gsc.json:n sivut-listalla goaliq.app/fpl CTR yli 0 % tai sijainti alle 8.6 · tarkistus 2026-11-22
- [ ] Template-XI rank-tasoittain /fpl-sivulle: `data/fpl_elite_ownership.json` kertoo jo, mitä top 1k, 10k ja 100k
  -otos omistaa. Lisää EO-osion viereen kullekin tasolle XI (11 omistetuinta pelaajaa, joiden muoto on kelvollinen),
  yleisin kapteeni ja otoskoko samasta artefaktista kuin EO-taulukon sarakeotsikossa. Yksi lukija, jota sivu käyttää;
  puuttuva taso on "ei dataa", ei tyhjä XI. Free/Premium-sijoitus ehdotetaan PR:n rungossa (ehdotus: ilmainen, koska EO
  rank-tasoittain on jo ilmainen), ihminen päättää. Vaihetesti: ennen deadlinea, kesken kierroksen, gradauksen jälkeen
  (otos kuuluu aina edelliseen gradattuun kierrokseen ja se sanotaan); testi kaatuu, jos kutsupaikka poistetaan. Builder,
  regeneroitu sivu ja llms.txt samassa PR:ssä. (aallonharja 2026-10-25, lähde: https://www.fplrogue.com/tools)
      Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 2/3 · uutuus 2/2 = 10
      Mittari: /fpl näyttää template-XI:n ja otoskoon jokaiselle kolmelle tasolle ja testi on vihreä · tarkistus 2026-11-30
- [ ] Ennusteen ikä näkyviin track recordissa: `/api/accuracy` jakaa jo ennusteet tuoreisiin (lead enintään 48 h) ja
  vanhentuneisiin (`by_lead`), ja vanhentuneet osuvat selvästi huonommin (44.2 % vs 53.3 %, Brier 0.613 vs 0.583). Näytä
  /predictions-sivun track record -osiossa molemmat osuudet ja Brierit samalla n:llä kuin API, ja ottelusivulla ennusteen
  kirjausaika ("Predicted <n> h before kickoff"). Luku luetaan artefaktista, ei lasketa sivulla; ei muokkaa kirjattuja
  ennusteita. llms.txt samassa PR:ssä. PR:n Julkinen teksti -osioon rivit sanatarkasti. (aallonharja 2026-10-25, lähde:
  data/accuracy.json, https://scoregpt.app/)
      Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 2/3 · uutuus 2/2 = 10
      Mittari: /predictions näyttää fresh- ja stale-osuudet samalla n:llä kuin /api/accuracy by_lead (testi) · tarkistus 2026-11-30
- [ ] /fpl/stats-sivun hakutulos: `scripts/build_fpl_longtail.py` (noin rivi 2561)
  kirjoittaa meta-descriptionin, joka on yli 160 merkkiä ja luettelee sarakkeet (shots, key passes, tackles ...), joten
  hakutulos katkaisee sen ennen kuin syy avata tulee esiin. Search Consolen mukaan sivu on sijalla 2,9 ja CTR 0 %.
  Lyhennä kuvaus alle 160 merkkiin niin, että "free, no sign-in", "filterable", "CSV" ja pelaajamäärä säilyvät
  ja luku tulee builderin omasta lukijasta (ei kovakoodattua määrää). Ei Premium-lupauksia. Regeneroitu fpl/stats.html ja
  llms.txt samassa PR:ssä. Testi mittaa pituuden builderin tuloksesta ja kaatuu, jos raja ylittyy. PR:n Julkinen teksti
  -osioon uusi kuvaus sanatarkasti. (aallonharja 2026-11-01, lähde: Search Console https://goaliq.app/fpl/stats , Signaalit)
      Pisteet: arvo 1/3 · kiire 1/3 · työ S · myynti 3/3 · uutuus 0/2 = 9
      Mittari: gsc.json:n sivut-listalla goaliq.app/fpl/stats CTR yli 0 % tai sijainti alle 2,9 · tarkistus 2026-11-29
- [ ] Ottelun varmuusluokka ja luokan oma osuus: ottelusivulle ja /predictions-sivun track record -osioon kolme luokkaa
  (esimerkiksi matala, keskitaso, korkea) voittajan todennäköisyyden mukaan, ja jokaiselle luokalle sen oma toteutunut
  osuus ja n samasta lokista kuin `/api/accuracy` (`data/prediction_log.json`, ei lasketa sivulla uudelleen). Rajat
  kirjoitetaan koodiin ennen mittausta ja pysyvät, eikä niitä virit jälkikäteen luokan osuuden perusteella. Näkyviin
  myös, missä luokassa malli aliarvioi tai yliarvioi (kalibraatiolokerot 0,65 ja 0,84). Ei kertoimia eikä panoksia.
  Yksi luokittelija, jota sivu ja API käyttävät; puuttuva todennäköisyys on "ei dataa". Vaihetesti: ennen kickoffia,
  kickoffin jälkeen ilman tulosta, tuloksen jälkeen (luokka ei muutu); testi kaatuu, jos kutsupaikka poistetaan tai luokka
  lasketaan sivulla uudelleen. Builder, regeneroitu sivu ja llms.txt samassa PR:ssä. Free/Premium-sijoitus ehdotetaan PR:n
  rungossa (ehdotus: ilmainen, koska 1X2 on ilmainen), ihminen päättää. PR:n Julkinen teksti -osioon merkkijonot
  sanatarkasti. (aallonharja 2026-11-01, lähde: https://scoregpt.app/ , data/accuracy.json)
      Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 2/3 · uutuus 2/2 = 10
      Mittari: /predictions näyttää kolme luokkaa ja niiden osuudet samalla n:llä kuin /api/accuracy (testi) · tarkistus 2026-12-06
- [ ] Sarjan oma track record ennustelukkoon: SPA:n ennusteiden lukot (scoreline, Predict ja Fixtures-lukko) näyttävät yhden
  todisterivin ottelun sarjasta: kuinka suuri osa sarjan gradatuista ennusteista osui ja n, luettuna `/api/accuracy`n
  `by_competition`-kohdasta (`data/accuracy.json`, ei lasketa selaimessa), ja linkin /predictions#record-osioon. Luku näytetään
  sellaisenaan myös, kun se on heikko (Championship 45 %, Premier League 45 %): testi kaatuu, jos rivin näkyminen riippuu luvusta.
  Sarja ilman gradattuja ennusteita tai puuttuva luku tarkoittaa, ettei riviä näytetä (ei nollaa). Premium-lupauksen teksti, hinnat ja
  ostopainikkeet eivät muutu. Yksi lukija, jota kaikki kolme lukkoa käyttävät; testi kaatuu, jos todisterivi puuttuu yhdestäkin
  lukosta. Mobiilin vastaava kohta on ihmisen työ (OTA). PR:n Julkinen teksti -osioon rivi sanatarkasti. Ennustelukot ovat ainoat,
  jotka tuottavat napautuksia (mobiili 21,9 % lukon näkijöistä, FPL-lukot 0,0 %), joten todiste ostohetkeen tehdään sinne, missä
  kiinnostus on. (aallonharja 2026-11-08, lähde: mittausdata ostopolku.tuotteittain, data/accuracy.json)
      Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 3/3 · uutuus 1/2 = 11
      Mittari: ostopolku.tuotteittain ennuste (web) ei ole pieni_otos ja napautus_lukosta_pct on yli 0 % (8.11.: pieni otos, 0,0 %), ja todisterivitesti on vihreä · tarkistus 2026-12-06
- [ ] Rate my team -hubisivu hakuun: uusi staattinen sivu goaliq.app/fpl/rate-my-team, joka kertoo ilmaiseksi ja ilman tiliä, mitä
  joukkuearvio mittaa (miten XI:n projektio vertautuu mallin löytämään vahvimpaan joukkueeseen 100,0 m budjetilla), esimerkkituloksen
  ja syöttökentän entry ID:lle, joka avaa pro.goaliq.app:n työkalun (`ref-bridge.js` kuljettaa lähteen). Sivun luvut luetaan samasta
  lukijasta kuin työkalu, ei kovakoodattuja arvoja; jos arviota ei esitetä asteikolla 100, sivu ei väitä niin. Search Consolen
  mukaan haku "rate this team out of 100" on sijalla 1 ja CTR 0 %, eikä hubissa ole sivua, joka vastaisi siihen. Builder
  (`scripts/build_fpl_longtail.py`-tyyliin), regeneroitu sivu, sitemap ja llms.txt samassa PR:ssä; Premium-lupaus ei muutu
  (täysi analyysi pysyy lukon takana). PR:n Julkinen teksti -osioon otsikko, kuvaus ja lauseet sanatarkasti. (aallonharja
  2026-11-08, lähde: Search Console https://goaliq.app/fpl , https://fplxi.com/)
      Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 3/3 · uutuus 1/2 = 11
      Mittari: gsc.json:n sivut-listalla goaliq.app/fpl/rate-my-team näkyy tai haun "rate this team out of 100" CTR on yli 0 % · tarkistus 2026-12-06
- [ ] Miniliigan kapteenit deadlinen jälkeen: miniliiganäkymään lista siitä, ketä liigan managerit kapteenoivat kuluvalla
  kierroksella (kapteeni ja varakapteeni, osuus liigasta), kun kierroksen deadline on mennyt ja FPL:n picks-data on julkista;
  ennen deadlinea "ei dataa". Luku haetaan samasta entry-lähteestä kuin miniliigan standings-haku, enintään liigan 50 ensimmäistä
  rivin managerista (sama raja kuin standingsissa) ja tulos välimuistiin, ettei API-pyyntö kasva (Render 512 Mi); jos raja
  ylittyy, otoskoko näkyy lukijalle. Yksi lukija API:ssa ja SPA:ssa. Vaihetesti: ennen deadlinea ei dataa, deadlinen jälkeen näkyy,
  uusi kierros nollaa; testi kaatuu, jos deadline-ehto poistetaan. Free/Premium-sijoitus ehdotetaan PR:n rungossa (ehdotus:
  Premium, koska miniliigan H2H-analyysi on Premiumia), ihminen päättää. (aallonharja 2026-11-08, lähde:
  https://www.fplpulse.com/ , https://www.fantasyfootballfix.com/premium/)
      Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 2/3 · uutuus 2/2 = 10
      Mittari: PostHog-tapahtuma miniliigan kapteeninäkymän avauksista näkyy mittausdatan tapahtumissa · tarkistus 2026-12-06

## Tehdyt
