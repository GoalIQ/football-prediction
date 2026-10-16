# GoalIQ-benchmark 16.10.2026: FPL-työkalut ja otteluennusteet

Ensimmäinen kilpailija- ja ominaisuusbenchmark backlogin syötteeksi. Kausi 2026/27, GW7 (deadline la 17.10. klo 10.00 UTC).

**Käyttö.** Tämä tiedosto on aallonharja-työnkulun (`.github/workflows/aallonharja.yml`) pohja: agentti päivittää matriisit ja mittarit viikoittain ja kirjoittaa uudet havainnot `docs/AUTO-BACKLOG.md`:hen. Luvun 5 ehdokkaat on siirretty backlogiin 16.10.2026.

**Menetelmä.** Julkiset, kirjautumattomat sivut (curl ja WebFetch 16.10.2026), hakukoneen tiivistelmät silloin kun sivu esti suoran luvun (Cloudflare 403 tai JavaScript-renderöinti), GoalIQ:n oma koodi (tämä repo ja mobiilisovellus) ja julkinen API. Ei kirjautumista, ei maksumuurien kiertämistä, ei UEFA:n sivuja, ei massakeruuta. Reddit palautti kirjautumissivun (ks. 4.8). Aiempi sisäinen ominaisuusanalyysi (25.7.2026) [G13] tarkistettiin päällekkäisyyksien välttämiseksi: sen korien 1-3 kohteista suurin osa on jo tuotteessa (captain ranker, set-piecet, CSV, edge mode, chains, chip timing, miniliiga, Beat the Model, päätöspäiväkirja).

**Merkinnät taulukoissa.** ✓ = varmistettu palvelun omalta tai viralliselta sivulta 16.10. ✓h = hakukoneen tiivistelmä palvelun sivusta, sivua ei saatu auki suoraan. – = ei löytynyt palvelun ominaisuus- tai hintasivulta. ? = ei varmistettu. Suluissa taso tai huomio. Lähdekoodit (G, F, P, R) viittaavat lukuun 7.

## 1. GoalIQ nyt (ominaisuuslista)

### 1.1 Ilmaiset hub-sivut (goaliq.app, staattinen HTML, ei kirjautumista)
- Puhtaan pelin todennäköisyys (CS%) kaikille PL-joukkueille: kuluva GW sekä 6 GW:n ruudukko (vastustaja, koti/vieras, CS% solussa, mallin FDR 1-5 tooltipissä) ja pitkän aikavälin FDR GW13-38 asti [G3].
- Team news: loukkaantuneet ja epävarmat FPL:n status-syötteestä omistuksen mukaan, epävarmoille pelaajille xP epävarmuus hinnoiteltuna [G1, G3].
- Expected points: top 100 seuraavalle 6 GW:lle (pisteytystahti ja odotetut minuutit erikseen) ja top 20 kuluvalle GW:lle, 10+-, Blank- ja Ceiling-sarakkeet [G1, G3].
- Paras kapteeni, Model XI (100,0 m), Model Predicted XI (aloitus-% kaikille 20 seuralle), seurasivut (parhaat pelaajat, erikoistilanteiden järjestys), paras pelaaja per seura [G1].
- Differentials (20 matalan omistuksen pelaajaa), hinnanmuutokset, xG-leaders (5 viimeistä ottelua), DefCon-leaders [G1].
- Points vs projection: toteutuneet pisteet ennen deadlinea jäädytetyn xP:n vieressä, pysyvät GW-arkistosivut GW1:stä alkaen, MAE per GW [G1].
- Pelaajatilastot (suodatettava, per 90 tai per aloitus, CSV), puolustusprofiilit kenttäalueittain, minuuttiennusteen virhesivu [G1].
- Projektiotarkkuus julkisesti: GoalIQ:n xP:n MAE FPL:n omaa ep_next-lukua ja formia vastaan per GW, jaoteltuna toteuman ja pelipaikan mukaan [G3].
- Effective ownership rank-tasoittain (top 1k, 10k, 100k, otos n=200) sekä näiden managerien siirrot ja chipit [G3].
- Gameweek calls: mallin kapteeni ja neljä poimintaa lokattuna ennen deadlinea, pisteytetty jälkikäteen [G3].
- Mallin oma FPL-joukkue (entry 116920) ja Beat the Model -miniliiga (koodi jgi6j9, palkintona vuoden Premium) [G2].
- Notes from the model, FAQ ja llms.txt tekoälyhakukoneille [G1].
- Muut: FPL Career Card, RSL Fantasy -työkalut (Saudi Pro League, ilmainen), creator-ohjelma (referral-koodi) [G1].

### 1.2 Ilmaiset työkalut (pro.goaliq.app ja iOS/Android)
Rate my team (entry ID, ei kirjautumista), fit checker (lukitse 1-3 pelaajaa), draft rater tallennettavin luonnoksin, pelaajakortti (saatavuus, aloitus-%, keltaiset kortit, erikoistilanteet, hinta, omistus), kapteenipoiminta, CS%, FDR (web), miniliiganäkymä H2H-voittotodennäköisyydellä ja "Catch your rival" -todennäköisyydellä, price watch (merkitsee omat 15), watchlist (3 pelaajaa), Leaders (xG, xA, xGI), Stats (jäädytetty xP vs toteuma), Beat the model -päätösloki, GW review, value- ja DefCon-listojen top 3, ottelulista, "Predict a match" (voittotodennäköisyys) ja sarjataulukot [G1, G5, G6].

### 1.3 Premium
Hinta 3,99 €/kk tai 25 €/v, yksi tilaus web + iOS + Android; UK:ssa ja Mansaarella vain kauppojen kautta; webostoilla 30 päivän rahat takaisin [G1, G5].
Sisältö: interaktiivinen joukkueenhallinta ja 6 GW:n liukuva suunnittelija, xP jokaiselle projektion pelaajalle per GW omistuksineen ja CSV-vienti (web), captain ranker (top 3, differential-poiminta, bonusodotus), chip timing (WC, BB, TC, FH, molemmat puoliskot), transfer chains (1-2 siirron ketjut, hitit hinnoiteltu) ja siirtoehdotukset yhden napautuksen soveltamisella, edge mode (rank-tietoiset poiminnat: suojaa tai kiipeä), fixture swing, player value (xP/milj.), MV-rotaatioparit, replacements, compare (4 pelaajaa), täysi DefCon-lista GW-erittelyllä ja DefCon live omalle joukkueelle, 50 pelaajan watchlist, jaettavat kortit (web), kauden erittely ja päätöspäiväkirja ("Where your season went"), otteluanalyysissa xG, tulosjakauma (top 10), 3+ maalin ja BTTS:n todennäköisyys (sovellus) sekä Multi-match (2-5 ottelun yhteistodennäköisyys, sovellus) [G2, G5, G6, G11].

### 1.4 Mobiili-ilmoitukset
Deadline-muistutukset (24 h ja 2 h ennen, palvelinpush), hinnanmuutoksen iltahälytys ennen FPL:n hintapäivitystä (price watch -datasta) ja mallin viikon poiminnat. Ei loukkaantumis- tai status-ilmoitusta omista pelaajista; push_tokens-taulussa ei ole FPL entry ID:tä [G8].

### 1.5 Otteluennusteet
- 10 sarjaa: Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Mestarien liiga, Brasileirão, Championship, Eredivisie ja Primeira Liga. UEFA Nations League vain sovelluksessa ja SPA:ssa, ei track recordissa [G1].
- 2 541 ottelusivua ja 10 sarjahubia, uudelleengenerointi 3 h välein. Ottelusivulla 1X2-todennäköisyys ilmaiseksi, xG ja tulosjakauma Premiumissa [G1].
- Track record (luettu 16.10. klo 12.54 UTC): 51,1 % oikein (376/736), seuraottelut 50,1 % (341/680), MM 2026 62,5 % (35/56). Ratkaisseissa otteluissa 69,2 %. Malli ei koskaan valitse tasapeliä, joten 26 % tasapeleistä on aina hutia. Sarjakohtainen erittely ja ottelukohtainen lista ovat sivulla [G2, G4, G7].
- Brier 0,588 (n=736; viimeiset 100 ottelua 0,555) ja 10 lokeron kalibraatio ovat olemassa JSONissa (/api/accuracy) ja sovelluksen rolling-kortissa, mutta eivät web-sivuilla (grep predictions.html, index.html ja fpl.html 16.10) [G7, G11].

### 1.6 Havaintoja nykytilasta benchmarkin valossa (mitattu 16.10)
- Premium-portitus toimii palvelinpuolella: /api/fantasy/xp ilman tunnusta palauttaa `meta.masked = true` ja 10 pelaajaa [G9]. Heinäkuun analyysin P0-huoli ei enää päde.
- BPS 26/27 -muutokset on huomioitu xP:n bonushistoriassa (`fpl_xp.py`, #151) [G10].
- Price watch näyttää FPL:n oman virallisen hintaprojektion, päivitys 3 h välein (`generated_at` 13.47 UTC, luettu 16.58 UTC). Virallinen peli päivittää saman datan 15 minuutin välein [G10, F16].
- FPL:n API:ssa on 26/27 uusi kenttä `scout_risks` (lainasopimusesto tietyllä kierroksella, korttipelikieltoriski). GoalIQ:n koodi ei lue sitä (grep 16.10) [F27].
- Projektiotarkkuus FPL:n ep_nextiä vastaan (MAE): GW3 1,54 vs 1,69, GW4 1,68 vs 1,65, GW5 1,62 vs 1,59, GW6 1,61 vs 1,63. Isot pisteet (10+, n=53): GoalIQ 8,77 vs ep_next 8,24 [G3].
- Ei ole: live-pisteitä tai live-rankia, AI-chattia, kausisimulaatiota (mestaruus, putoaminen), monen GW:n hyökkäysvaikeutta, kenttäpelaajien rotaatiopareja, oman joukkueen status-pushia.

## 2. Ominaisuusmatriisi: FPL

Sarakkeet: GIQ = GoalIQ, FFH = Fantasy Football Hub, FPLR = FPL Review, LFPL = LiveFPL, FFS = Fantasy Football Scout, FIX = Fantasy Football Fix, FORM = FPL Form, FFP = Fantasy Football Pundit, FSTAT = FPLStatistics, FPL = virallinen FPL ja PL-sovellus 26/27, ROGUE = FPL Rogue.

| Ominaisuus | GIQ | FFH | FPLR | LFPL | FFS | FIX | FORM | FFP | FSTAT | FPL | ROGUE | Lähde |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| xP per pelaaja per GW | ✓ (top 100 ilm., kaikki Prem.) | ✓ (Starter) | ✓ | ? | ✓ (Chief) | ✓ (Prem.) | ✓ (ilm.) | ✓ (ilm.) | ? | – (Companion ei anna) | ✓ (Pro) | G1, F2, F5, F8, F11, F12, F13, F18, F20 |
| Projektiohorisontti yli 6 GW | – (xP 6 GW; FDR GW38 asti) | ? | ✓h (14 GW, maks.) | ? | ✓ (koko kausi, Chief) | ? | ? | ? | ? | – | ? | G3, F5, F8 |
| Kapteenisuositus | ✓ (pick ilm., ranker Prem.) | ✓ (Best Captain) | ? | ? | ✓ (Captaincy Matrix) | ✓ (captain data) | ✓ (Lineup Suggestor) | ✓ | ? | ? | ✓ (Pro) | G1, F1, F8, F11, F12, F13, F20 |
| Siirtosuositukset omaan joukkueeseen | ✓ (Prem.) | ✓ (AI transfers) | ✓ (solver) | ? | ✓ (AI-työkalu, Chief) | ✓ (AI, Prem.) | ✓ | – | ? | osittain (Companion vertailee kohteita) | ✓ (Pro) | G1, F2, F5, F8, F11, F12, F13, F18, F20 |
| Monen GW:n suunnittelija tai solver | ✓ (planner + chains, Prem.) | ✓ (planners) | ✓ (planner + solver) | ✓ | ✓ (2 planneria) | ✓ (5 luonnosta) | ✓ (optimizer) | – | ? | – | ✓ | G1, F1, F5, F6, F8, F10, F12, F20 |
| Chip-ajoitus | ✓ (Prem.) | – (tulossa kaudella) | ? | ✓ (planneri) | – (oppaat artikkeleina) | ✓ (planneri) | osittain (Free Hit -optimointi) | – | ? | – | ✓ (Pro) | G1, F3, F6, F8, F10, F12, F20 |
| Live-pisteet ja live-rank | – | ✓ (Live Mode, ilm.) | – | ✓ | ✓ (Live Gameweek) | ✓ (Gameweek Live) | ? (valikossa) | ✓ | ? | ✓ (uusi 26/27) | ✓ (ilm.) | F3, F6, F9, F12, F13, F15, F20, F26 |
| Projisoitu bonus kesken ottelun | – | ✓ | – | ✓h | ? | ? | ? | ? | ? | ✓ (20 min jälkeen) | ? | F3, F7, F15 |
| DefCon live | ✓ (oma joukkue, Prem.) | ? | – | ✓h | ? | ? | ? | ? | ? | ✓h (pisteet live) | ? | G2, F7, F32 |
| Hinnanmuutosennuste | ✓ (FPL:n oma projektio, 3 h) | ✓ (Starter) | – | ✓ | ✓h (LiveFPL-widget) | ✓ | ? (valikossa) | ✓ | ✓h (sivu ei vastannut) | ✓ (15 min) | ✓ (ilm.) | G10, F2, F6, F10, F13, F14, F16, F20 |
| Push: deadline ja hinta | ✓ (mobiili) | ✓ | – | ? | ? | ✓h (hinta) | – | – | – | ? | ? | G8, F3 |
| Push: loukkaantuminen omassa joukkueessa | – | ✓ | – | ? | ? | ? | – | – | – | ? | ? | G8, F3 |
| Ennustetut kokoonpanot (aloitus-%) | ✓ (minuuttihistoriasta) | ✓ | ? | – | ✓ (Chief) | ? | ? | ✓ | – | – | ✓ (ilm.) | G1, F1, F8, F13, F20 |
| CS-todennäköisyys joukkueittain | ✓ (malli, ilm.) | ? | ? | – | ✓h (uusi ticker) | ? | osittain (puolustusvaikeus) | ✓ (kertoimista) | – | – (vain FDR) | ? | G3, F8, F12, F13, F15 |
| Hyökkäys- ja puolustusvaikeus erikseen, monta GW | – (proj. maalit vain 1 GW) | ? | ? | – | ✓h (projected goals) | ? | ✓ | – | – | – | ✓ | G3, F8, F12, F13, F20 |
| Erikoistilanteiden järjestys | ✓ | ✓ | ? | – | ? | ? | ✓ (pilkut) | ✓ | – | ? (API-kentät) | ✓ (ilm.) | G1, F1, F12, F13, F20, F27 |
| EO rank-tasoittain tai eliittidata | ✓ (top 1k/10k/100k, ilm.) | osittain (reveals) | ? | ✓ (EO ja threats) | osittain (reveals) | ✓ (Elite XI, Plus) | – | ✓ (top 10k) | – | – | ✓ (Lite) | G3, F2, F6, F8, F11, F13, F20 |
| Miniliiga-analyysi | ✓ (H2H-%, catch your rival) | ✓ | – | ✓ (League Explorer) | ✓h (Mega Bundle) | ? | – | ✓ | – | ✓ (live) | ✓ | G1, F1, F6, F8, F13, F15, F20 |
| Rank-tietoinen neuvonta | ✓ (edge mode, Prem.) | – (chip-työkalu tulossa) | ? | ? | ? | ? | ? | ? | – | – | ? | G1, F3 |
| Julkinen, ennen deadlinea jäädytetty projektiotarkkuus | ✓ (MAE vs ep_next) | – | ? | – | ? | ? | ? | ? | – | – | ? | G3, F21 |
| Mallin oma julkinen FPL-joukkue | ✓ (entry 116920) | ✓ (Hub AI Team) | ? | – | ? | ✓ (AI Team Reveal) | ? | ? | – | – | ? | G2, F1, F10 |
| AI-keskusteluavustaja | – | ? | – | – | – | ✓ (ChatFPL, Plus) | – | – | – | ✓ (FPL Companion) | ? | F11, F18, F19 |
| Joukkueen arviointi (rate my team) | ✓ (ilm.) | ✓ (AI Team Rating) | ? | – | ✓ (ilm.) | ✓ | ? | – | – | – | ✓ (Team Review) | G1, F1, F8, F10, F20 |
| Kausikatsaus, omien päätösten arviointi | ✓ (GW review ilm., kausi Prem.) | ? | – | ? | ? | ? | – | ✓ (Captain Analyser) | – | osittain (ura-%) | ✓ (Season Review) | G2, F13, F15, F20 |
| Tilastotaulukko ja vienti | ✓ (CSV, ilm.) | ✓ (OPTA Stats) | ✓h (projektiot ladattavissa) | ? | ✓ (Opta, Chief) | ✓ (Opta) | ✓ (data export) | ✓ (arkisto 2016-) | – | – | ✓ | G1, F1, F5, F8, F11, F12, F13, F20 |
| Mobiilisovellus | ✓ (iOS, Android) | ✓ (natiivi) | – | ✓ | ✓ | ✓ | – | ? | – | ✓ | ✓ | G1, F3, F6, F9, F10, F20 |
| Hinta | 3,99 €/kk tai 25 €/v | £4,98-29,98/kk vuosilaskutuksella | €3,90/kk + ALV (Patreon) | ilmainen, mainokset | £50/v tai £10/kk; Mega Bundle £100/v | £3,48-3,98/kk vuosilask.; lifetime £295 | ilmainen (lahjoitus) | ilmainen | ilmainen (sivu ei vastannut) | ilmainen | Lite £4,99/v, Pro £14,99/v | G2, F2, F5, F6, F8, F11, F12, F13, F14, F20 |

**Muut merkittävät FPL-työkalut 26/27**

| Palvelu | Hinta | Erottava piirre | Lähde |
|---|---|---|---|
| FPLXI | £19,99 kertamaksu kaudelle (early bird, nousi GW3:n jälkeen), ei automaattista uusintaa; ilmaistaso | Oma ML-malli 5 GW eteenpäin, deterministinen optimoija (XI, kapteeni, penkkijärjestys), joukkueen tuonti ID:llä tai kuvakaappauksesta, julkinen tarkkuus per GW deadlineen lukittuna | F21 |
| FPL Pulse | ilmainen; Pro £2,99/kk tai £24,99/v | Miniliigan Monte Carlo -simulaatio (100 000 kautta; ilmaisella yksi ajo), live-miniliiga, AI-avustaja "Gaffer's Pulse", "Reddit Pulse" (r/FantasyPL:n päivittäinen analyysi, Pro) | F22 |
| FPL Guru | ilmainen 26/27-julkaisun ajan | Siirto-, kapteeni- ja chip-työkalut sekä chat; MCP-liitin Claudeen, ChatGPT:hen, Claude Codeen ja Codexiin | F23 |
| FPLai | Pro £6,99/kk; kausipassi £34,99 (voimassa 31.5.2027 asti) | iPhone, Apple Watch ja web; "Elite Pulse" top 1k -seuranta, Team DNA | F24 |
| FPL Copilot (fplcopilot.com) | ? | HiGHS MIP -solver 10 GW eteenpäin, Claude-pohjainen chat-kerros (h) | F34 |
| Avoimen lähdekoodin MCP-palvelimet | ilmaisia | fpl_mcp (LightGBM-ennusteet, optimointi), FPL Intelligence (11 työkalua) | F28 |

**Mitä matriisista näkyy.**
- Perustoiminnot ovat tasaantuneet: xP, kapteeni, siirrot, suunnittelija, hinnanmuutokset ja kokoonpanot löytyvät lähes kaikilta. GoalIQ on näissä mukana.
- GoalIQ:n erottuvat kohdat: julkinen, ennen deadlinea jäädytetty tarkkuus FPL:n omaa lukua vastaan, EO rank-tasoittain ilmaiseksi, mallin oma pelattu joukkue, rank-tietoinen edge mode ja otteluennusteiden track record samasta mallista.
- GoalIQ:n aukot: live (tietoinen valinta), AI-chat (tietoinen valinta), status-push, monen GW:n hyökkäysvaikeus, horisontti yli 6 GW ja kenttäpelaajien rotaatio.
- Hinta: GoalIQ 25 €/v on keskikastia. FPL Rogue Pro £14,99/v ja FPLXI £19,99 alittavat sen, FFS (£50/v) ja FFH (Starter noin £60/v) ylittävät.

## 3. Ominaisuusmatriisi: ennusteet

| Ominaisuus | GoalIQ | Forebet | PredictZ | WinDrawWin | Opta Analyst | Dimers | ClubElo | StatsUltra | ScoreGPT | Lähde |
|---|---|---|---|---|---|---|---|---|---|---|
| 1X2-todennäköisyys per ottelu | ✓ (ilm.) | ✓h | ? | ? (vinkki + panos) | ✓h (PL viikoittain, ilm.) | ✓h | ✓ | ✓ | – (mallien ääni, ei todennäköisyys) | G4, P1, P3, P4, P6, P7, P8, P9, P10 |
| xG per ottelu | ✓ (Prem.) | ? | ? | ? | ? | ✓h | – | ✓ (ilm.) | ? | G4, P7, P9 |
| Tulosjakauma | ✓ (top 10, Prem.) | ✓h (correct score) | ✓h (ennustettu tulos) | ✓h (ehdotettu tulos) | ? | ✓h | – | ✓ (4 todennäköisintä) | ✓ (exact score) | G5, P2, P3, P4, P7, P9, P10 |
| BTTS ja yli 2,5 maalia | ✓ (sovellus, Prem.) | ✓h | ✓h | ✓h | ? | ✓h | – | ✓ (ilm.) | ? | G5, P1, P3, P4, P7, P9 |
| Kauden simulaatio (mestaruus, top-4/5, putoaminen) | – | ? | ? | ? | ✓ (10 000 simulaatiota) | ? | ✓ | ? (15 000 simuloitua kautta mainitaan) | – | P5, P8, P9 |
| Julkinen, ennen kickoffia lokattu track record | ✓ (n=736, ottelukohtainen) | ? (lähteet ristiriidassa) | ? | ? | ? | ? | – | – (ei mainita) | ✓ (30 pv, 2 712 arvioitua) | G4, P1, P9, P10 |
| Brier tai kalibraatio julkisesti | osittain (JSON ja sovellus, ei web) | ? | ? | ? | ? | ? | – | – | ✓ (kalibraatio) | G7, P10 |
| Vedonlyöntikytkös näkyvissä (kertoimet, panokset, value-vedot) | – (ei kertoimia) | ✓h (Kelly-pohjaiset) | ✓h (kertoimet) | ✓h (panoskoko) | – (kertoimet mallin syötteenä) | ✓h (betting picks) | ? | – ("no tips, affiliate links or odds") | ? | G1, P1, P2, P3, P4, P5, P7, P9 |
| Kielimalli ennusteessa tai selityksessä | – (ei kielimallia ennustepolussa) | – ("purely mathematical") | ? | ? | – | ✓h (AI bet assistant) | – | – | ✓ (5 kielimallin konsensus) | G1, P1, P7, P10 |
| Kattavuus | 10 sarjaa (+ UNL sovelluksessa) | 1 200+ sarjaa (FAQ, h) | 100+ (h) | 140+ (h) | PL, muut ? | useita jalkapallosarjoja (h) | laaja (Eurooppa, Etelä-Amerikka) | 33 | 27 | G1, P1, P3, P4, P7, P8, P9, P10 |
| Ottelukohtaiset hakukonesivut | ✓ (2 541) | ✓h | ✓h | ✓h | ✓h (preview-artikkelit) | ✓h | ? | ✓ (sarjasivut) | ? | G1, P1, P3, P4, P6, P7, P9 |
| Mobiilisovellus | ✓ | ? | ? | ? | ? | ✓h | – | ? | ✓ | G1, P7, P10 |
| Hinta | 1X2 ilm.; xG ja tulosjakauma 3,99 €/kk | ilmainen, mainokset (h) | ilmainen (h) | ilmainen (h) | ilmainen | Pro $29,99/kk (h) | ilmainen | ilmainen | 3 poimintaa/vko ilm.; Pro sovelluksessa | G5, P1, P3, P4, P5, P7, P8, P9, P10 |

Muita: xGStat (Poisson, CS-todennäköisyydet, vain top 3 ilmaiseksi, h) [P12]; AIM GO (LLM-selitykset ja chat Premiumissa, 150+ sarjaa, h) ja BetBrothers (kielimallit vs 40+ vedonvälittäjän kertoimet, h) [P13]; Fantasy Football Pundit näyttää PL:n mestaruus-, top-4- ja putoamistodennäköisyydet [F13].

**Mitä matriisista näkyy.**
- GoalIQ:n kärki ennusteissa on harvinainen: lokattu, julkinen track record ja kalibraatiodata ilman vedonlyöntikytköstä. Vain ScoreGPT tekee saman julkisesti, ja se mainostaa 63-70 %:n osumatarkkuutta (eri ottelujoukko, ei vertailukelpoinen GoalIQ:n 51,1 %:n kanssa).
- Ilmaiset kilpailijat antavat xG:n, tulosjakauman, BTTS:n ja yli 2,5 -todennäköisyyden ilmaiseksi (StatsUltra, Dimersin ilmaisosa). GoalIQ:lla ne ovat Premiumia. Tämä on hinnoittelupäätös, ei ominaisuusaukko, joten se jätetään luvun 5 ulkopuolelle.
- Kausisimulaatio puuttuu GoalIQ:lta, vaikka se on Optalla, ClubElolla ja FFP:llä vakiosisältöä.

## 4. Aallonharja: uudet ja nousevat

### 4.1 FPL 2026/27: mitä muuttui (virallinen)
- **Live:** kokonaissijoitus ja kaikki liigat (myös H2H ja cup) päivittyvät otteluiden aikana. Projisoitu bonus lisätään 20 minuutin kohdalla ja se muuttuu ottelun ajan [F15, F25].
- **BPS:** taklatuksi tulemisen -1 poistettu; CBI 1 BPS per 3 (ennen per 2); maalivahdille 2 BPS per torjunta, +1 boksin sisältä tulleesta ja +1 isosta maalipaikasta; boksin ulkopuolelta tulleen laukauksen torjunnan oma metriikka poistettu; pilkkutorjunta 8 → 7 BPS [F17]. Tavoite: vähentää päällekkäisyyttä DefCon-pisteiden kanssa ja parantaa maalivahtien, laitapuolustajien ja hyökkääjien bonusmahdollisuuksia.
- **Lockdown:** kierroksen pisteet lukitaan klo 9.00 UK viimeistä ottelua seuraavana päivänä (ennen 1 h viimeisen vihellyksen jälkeen), jotta Optan tarkistettu data ehtii BPS- ja DefCon-pisteisiin [F15].
- **Ennallaan:** kaksi chip-sarjaa (WC, FH, TC, BB kummallekin puoliskolle); ensimmäinen sarja käytettävä ennen GW19-deadlinea la 2.1.2027 klo 13.30 GMT eikä siirry jälkimmäiselle puoliskolle; 5 säästettävää vapaata siirtoa; DefCon säilyy; ei AFCON-lisäsiirtoja [F15, F25].
- **Uudet näkymät:** Price Change Predictor (virallinen siirtodata, päivitys 15 min, edistymä prosentteina ja "predicted progress" kalibroinnin jälkeen), squad views (FDR, omistus ja seuraava vastustaja Pick Team-, Points- ja Transfers-sivuilla; form ja hinnanmuutoksen todennäköisyys myöhemmin), ura-% ja uran keskiarvo, Rookie League, GW-recap-kuvat (Adobe Express), aloittelijan joukkueavustaja ja 11 pelipaikkamuutosta [F15, F16, F25].
- **FPL Companion** (Microsoft Copilot, GPT-5.4): tuntee käyttäjän joukkueen, pelaajien saatavuuden ja budjetin, vertailee siirtokohteita ja näyttää Scoutin artikkelit. "The Companion also won't provide predicted points." [F18, F19]
- **Pelaajamäärä:** LiveFPL:n mukaan GW1:een rekisteröityi 8,9 miljoonaa tiliä (edellisellä kaudella 9,5 miljoonaa) (h) [F35]. Microsoftin kumppanuusuutisoinnissa puhutaan yli 13 miljoonasta pelaajasta (eri mittari, h) [F33].

### 4.2 Mitä tämä tekee markkinalle
- Live- ja hintatyökalut muuttuivat peruspalveluksi. Fix kirjoittaa, ettei kolmannen osapuolen live-työkalua enää tarvita miniliigasijan arvioimiseen [F26]. Kolmannet osapuolet siirtyvät "mitä jos" -simulointiin (LiveFPL What-If), uhka-analyysiin (LiveFPL Threats) ja rivaalien autosubeihin (FFH 4.1.2, h) [F4, F6].
- Raha siirtyy päätöksentekoon: projektiot, solverit, chip-ajoitus, miniliigasimulaatiot ja rank-tietoisuus. Virallinen AI ei anna ennustettuja pisteitä, joten numero, jolla on tarkistettava historia, on edelleen niukka.
- FFH rakensi sovelluksensa uudelleen natiivina ja lisäsi henkilökohtaiset hälytykset (deadline, hinnat, loukkaantumiset, siirtoehdotukset). Chip Strategy Tool, joka käyttää myös miniliigasijaa, on luvattu kauden aikana [F3]. FFS:n uusi sovellus on rakennettu Plannerin ympärille, ja FFS:n uusi ticker näyttää CS%:n, projisoidut maalit ja "relative difficulty" -asetuksen [F8, F9].

### 4.3 Uusi data FPL:n julkisessa API:ssa
- bootstrap-static (luettu 16.10): `elements[]` sisältää kentät `price_change_percent`, `price_change_projections` (offset 0-2 vrk ja likelihood), `price_change_hourly_rate`, `price_change_calibrating`, `price_change_locked_until`, `scout_risks` ja `scout_news_link` [F27].
- `scout_risks` 16.10: 15 lainasopimusestoa kierroksittain (esimerkiksi Mudryk GW8, Danso GW12, Garnacho GW16 ja GW27, Grealish GW18 ja GW28, Marmoush GW19 ja GW25) ja 3 korttipelikieltoriskiä (Janelt, McBurnie, Crooks; "will face a 1-match suspension on receiving their next") [F27].
- GoalIQ käyttää jo hintakenttiä (`fpl_price_watch.py`), mutta ei `scout_risks`-kenttää [G10].

### 4.4 AI-avustajat ja MCP
- Virallinen FPL Companion on FPL:n sivustolla ja sovelluksessa [F18]. Hintaa ei mainita.
- Kaupalliset: Fix ChatFPL (krediitit; Pro vain Premium Plus -tasolla), FPL Pulse "Gaffer's Pulse" (vapaat kysymykset Pro-tasolla), FFH:n AI transfers kaikilla tasoilla, FPLai ja FPL Guru [F2, F11, F22, F23, F24].
- MCP-liittimet: FPL Guru tarjoaa isännöidyn MCP-palvelimen Claudeen ja ChatGPT:hen. Avoimen lähdekoodin palvelimia on useita (fpl_mcp, FPL Intelligence, fpl-context-mcp) [F23, F28]. Käyttäjä tuo FPL-datan omaan tekoälyynsä, eikä työkalun tarvitse maksaa kielimallista.
- Arviointikriteerit AI-työkaluille (fploracle, h): yhdistyykö työkalu oikeaan joukkueeseen, huomioiko se rank-tilanteen, perusteleeko se, onko sääntötieto ajan tasalla ja huomioiko se miniliigan [F29]. GoalIQ kattaa nämä ilman chattia: entry ID, edge mode, perustelurivi (WhyThisPick), BPS 26/27 ja miniliiganäkymä.

### 4.5 Julkinen tarkkuus leviää myyntiargumentiksi
- FPLXI: tarkkuus julkaistaan joka kierrokselta, ennusteet lukitaan deadlineen. Sen vertailusivu sanoo FFH:n tarkkuuden olevan "claimed in marketing" [F21].
- ScoreGPT: julkinen tarkkuustaulu 7, 14 ja 30 päivän ikkunoilla (osumat, exact score, kalibraatio) [P10].
- FFS ja Fix väittävät projektioidensa olevan tarkkoja, mutta julkista, jäädytettyä lokia ei löytynyt [F8, F10].
- Johtopäätös: "lokattu ennen kickoffia" ei ole enää GoalIQ:n yksinoikeus. Erottuminen vaatii vertailukohdan (perustaso, FPL:n ep_next) ja oikeat mittarit (Brier, kalibraatio) pelkän osumaprosentin sijaan.

### 4.6 Ennusteet: kausisimulaatiot ja kielimallit
- Opta Analyst: kauden simulaatio 10 000 kertaa, syötteenä vedonlyöntimarkkinan kertoimet ja Opta Power Rankings; ottelukohtaiset todennäköisyydet viikoittain ilmaiseksi [P5, P6].
- ClubElo ja StatsUltra: ilmaiset kausiennusteet; ClubElo näyttää ottelukohtaisesti, mitä on pelissä (putoaminen, mestaruus) [P8, P9].
- Kielimallipohjaisia ennustesovelluksia tulee nopeasti (ScoreGPT, AIM GO, BetBrothers, Predigoal) (h) [P10, P13].
- MM 2026 -tutkimus (arXiv 2607.17765): neljä kielimallia (Claude Opus 4.8, GPT-5.5, Gemini 3.1 Pro, Grok) 104 ottelussa; yksikään ei voittanut markkinan Brier-pistettä, ja mallit valitsivat saman suosikin 92 %:ssa otteluista, joten pelkkä osumaprosentti ei erottele ennustajia [P11].

### 4.7 Hinnoittelu ja paketointi
- Kausipassit ja kertamaksut yleistyvät: FPLXI £19,99 ilman uusintaa, FPLai kausipassi £34,99 (voimassa 31.5.2027 asti), FPL Rogue Pro £14,99/v, FPL Pulse Pro £24,99/v [F20, F21, F22, F24].
- Niput: FFS Mega Bundle £100/v sisältää LiveFPL:n mainoksettomana, Premier Fantasy Toolsin, Mini League Maten ja The Fantasy Newsletterin [F8].
- Takuut ja elinikäiset: FFH:n "Mini-League Promise" (voita tai rahat takaisin) kampanjassa 24.7.-20.9.2026 (h) [F2]; Fix lifetime £295 [F11].

### 4.8 Yhteisön signaalit
- **r/FantasyPL:** Redditin julkinen JSON-haku palautti 16.10 kirjautumissivun ("Welcome to Reddit"), eivätkä hakukoneet tuoneet ketjuja näillä hauilla [R1]. Kirjautumista ei kokeiltu ohjeen mukaisesti. Suoraa Reddit-signaalia ei siis ole, alla toissijaiset lähteet.
- FFS:n sääntömuutosartikkelin kommentit: osa piti muutoksia järkevinä, useampi pyysi deadlinen siirtoa ensimmäiseen kickoffiin, DefConin vaikutusta pidettiin vähäisenä ("nominal") ja peliä tunkkaisena ("stale") [F25].
- Sovellusarviot: FPL.Liven arvioissa valitettiin hitaammasta päivityksestä ja siitä, ettei rivaalien vaihtoja näy (h) [F31]. FFH lisäsi versioon 4.1.2 rivaalien autosubit ja joukkueen jakamisen kuvana (h) [F4].
- FPL Pulse myy r/FantasyPL:n päivittäistä analyysiä Pro-ominaisuutena ("Reddit Pulse") [F22]: yhteisön tunnelma on itsessään tuote.
- Epäsäännölliset deadlinet: GW8:n deadline on perjantaina 23.10. klo 18.30 BST (Ipswich-Forest pe klo 20.00), ja OneFPL varoittaa lauantaiolettamuksesta (h) [F30].

### 4.9 Seuraavan 90 päivän kalenteri
- 23.10.2026: GW8:n perjantai-deadline (18.30 BST) [F30].
- 25.10.2026: UK siirtyy talviaikaan; FPL:n hintapäivitys klo 00.00 UK siirtyy 23.00 UTC:stä 00.00 UTC:hen.
- 2.1.2027 klo 13.30 GMT: GW19-deadline, ensimmäisen chip-sarjan viimeinen käyttöhetki [F15].
- Kauden aikana: FFH:n Chip Strategy Tool [F3]; FPL:n squad views saa formin ja hinnanmuutoksen todennäköisyyden [F15].

## 5. Aukot ja mahdollisuudet

Järjestys: tärkein ensin (pisteet ja strateginen sopivuus yhdessä). Kaikki kohdat käyttävät vain jo käytössä olevia tai vapaita lähteitä. Julkista copya muuttavat kohdat menevät julkaisutarkistajan kautta (CLAUDE.md 6b).

- Lue FPL:n scout_risks xP-putkeen: nollaa pelaajan xP kierroksella, jolle FPL ilmoittaa lainasopimusesteen (loan_ineligible), ja näytä korttipelikieltoriski (suspension_risk) pelaajakortissa; pinta API (xP-putki) sekä SPA:n ja mobiilin pelaajakortti (benchmark 2026-10-16, lähde: FPL:n julkinen API https://fantasy.premierleague.com/api/bootstrap-static/)
  Perustelu: FPL julkaisee 26/27 lähtien kierrokset, joilla lainapelaaja ei saa pelata emoseuraansa vastaan. 16.10 rivejä oli 15, joista kaksi osuu nykyiseen 6 GW:n ikkunaan (Mudryk GW8, Danso GW12) ja useampi chip-suunnittelun ikkunaan (Grealish GW18, Marmoush GW19). GoalIQ:n koodista ei löydy kentän lukua (grep 16.10), joten Premiumin xP, chip timing ja transfer chains laskevat näille kierroksille todennäköisesti normaalin odotusarvon. VARMISTETTU 16.10: data/fpl_xp_projections.json antaa Dansolle GW12:een (vs TOT, emoseura) xp 3.91 ja xmins 84.9, vaikka FPL:n scout_risks sanoo loan_ineligible GW12. Mudryk on listalla excluded (loukkaantunut), joten hänen GW8:aan vika ei nyt osu. Hyötyjä: Premium-käyttäjä, jonka suunnitelma ulottuu estokierrokselle. Yhdenkään kilpailijan ei varmistettu käyttävän kenttää. Toteutus säännön 6a mukaan: yksi lukija, joka palauttaa pelaajan saatavuuden kierrokselle, ja testi synteettisellä estokierroksella.
  Data: FPL bootstrap-static `elements[].scout_risks` (property, gameweek, notes), sama kutsu jota GoalIQ jo käyttää.
  Pisteet: arvo 3/3 · kiire 2/3 · työ S · myynti 1/3 · uutuus 0/2

- Brier, taitopiste ja kalibraatio track record -sivulle: näytä /predictions-sivulla ja etusivun track record -osiossa Brier-piste, Brier skill score yksinkertaista perustasoa vastaan ja kalibraatiotaulukko, jotka /api/accuracy jo laskee; pinta hub-sivu (benchmark 2026-10-16, lähde: ScoreGPT:n julkinen tarkkuustaulu https://scoregpt.app/ ja MM 2026 -tutkimus https://arxiv.org/abs/2607.17765)
  Perustelu: Julkinen tarkkuus ei ole enää GoalIQ:n yksinoikeus (FPLXI, ScoreGPT), ja kielimallisovellukset mainostavat 63-70 %:n osumatarkkuutta, jonka vieressä 51,1 % näyttää heikolta, vaikka ottelujoukot eivät ole vertailukelpoisia. Tutkimuksen mukaan osumaprosentti ei erottele ennustajia (sama suosikki 92 %:ssa otteluista), Brier erottelee. GoalIQ:lla Brier (0,588, n=736) ja 10 lokeron kalibraatio ovat jo JSONissa ja sovelluksen rolling-kortissa, mutta eivät web-sivulla. Perustaso (esimerkiksi sarjan edellisen kauden koti-, tasapeli- ja vierasfrekvenssit) kertoo, onko 0,588 hyvä. Hyötyjä: ennusteita arvioiva lukija ja sivua lainaavat tekoälyhakukoneet. Kilpailijoista vain ScoreGPT näyttää kalibraation.
  Data: oma ennusteloki ja /api/accuracy (brier, calibration); perustaso lasketaan samasta lokista. Ei uusia lähteitä.
  Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 1/3 · uutuus 1/2

- xP-horisontti GW19:ään asti chip-suunnitteluun: laajenna Premiumin xP- ja chip timing -näkymä ensimmäisen chip-puoliskon loppuun (GW19) ja merkitse yli 6 GW:n luvut karkeammiksi; pinta API ja SPA (benchmark 2026-10-16, lähde: FPL Review 14 GW Projection Horizon https://fplreview.com/ ja FFS Season-Long RMT Points Projections https://www.fantasyfootballscout.co.uk/register)
  Perustelu: Ensimmäisen chip-sarjan käyttämättömät chipit menetetään GW19-deadlinessa la 2.1.2027 klo 13.30 GMT, 78 päivän päästä. GoalIQ:n xP kattaa 6 GW ja pidemmälle vain FDR:n, joten "käytä nyt vai säästä GW16-19:lle" -päätös jää ilman pistelukua. FPL Review myy 14 GW:n horisonttia ja FFS koko kauden projektioita maksullisina. Hyötyjä: Premium-käyttäjä, jolla on chip käyttämättä. Selvitys ensin: minuuttiennusteen virhe kasvaa horisontin mukana (minuuttivirhesivu), joten tarkkuus pitää mitata ennen julkaisua.
  Data: oma malli ja FPL:n otteluohjelma; pitkän aikavälin FDR GW13-38 on jo laskettu.
  Pisteet: arvo 2/3 · kiire 2/3 · työ L · myynti 2/3 · uutuus 1/2

- Hyökkäysvaikeus 6 GW:n ruudukkoon: lisää /fpl-sivulle ja SPA:n Teams-näkymään joukkueen projisoidut maalit per ottelu seuraaville 6 GW:lle CS%-ruudukon rinnalle; pinta hub-sivu ja SPA (benchmark 2026-10-16, lähde: FPL Form attacking difficulty https://www.fplform.com/ ja FPL Rogue Fixture Difficulty Ratings https://www.fplrogue.com/tools)
  Perustelu: GoalIQ:n 6 GW:n ruudukko kertoo vain puolustuspuolen (CS%). Hyökkääjää ja kapteenia valitseva tarvitsee toisen puolen, ja malli laskee sen jo (projected goals näkyy vain kuluvan GW:n taulukossa). FPL Form ja FPL Rogue tarjoavat hyökkäys- ja puolustusvaikeuden erikseen ilmaiseksi, FFS:n uusi ticker näyttää projisoidut maalit. Hyötyjä: ilmaiskäyttäjä ja hakukoneliikenne (/fpl on päähub).
  Data: oman Dixon-Coles-mallin joukkuekohtaiset odotetut maalit per ottelu.
  Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 1/3 · uutuus 1/2

- Kauden simulaatio kotimaisille sarjoille: Monte Carlo jäljellä olevista otteluista, tuloksena mestaruuden, top-4:n ja putoamisen todennäköisyydet joukkueittain; pinta API, sarjahubit (/predictions/<sarja>/) ja SPA:n Table (benchmark 2026-10-16, lähde: Opta Analyst supercomputer https://theanalyst.com/articles/premier-league-predictions-2026-27-opta-supercomputer ja ClubElo http://clubelo.com/)
  Perustelu: Kausiennuste on alan vakiosisältöä (Opta, ClubElo, StatsUltra, FFP:n Title, Top 4 & Relegation), ja Optan "supercomputer" on yksi uutisoiduimmista ennustesisällöistä. GoalIQ:lla on malli ja koko kauden otteluohjelma (2 541 lokattua ottelusivua), mutta ei kausisimulaatiota. Hyötyjä: ennusteiden lukija ja sarjahubien hakuliikenne. Ei koske Mestarien liigaa (UEFA-linjaus).
  Data: oma Dixon-Coles-malli ja jo käytössä oleva otteluohjelma; ei uusia lähteitä.
  Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 1/3 · uutuus 2/2

- FPL-todennäköisyyksien kalibraatio: jäädytä ennen deadlinea myös xp_dist-kentän p_haul (10+) ja p_blank ja julkaise /fpl-sivulla kalibraatiotaulukko kierrosten kertyessä; pinta API (jäädytys) ja hub-sivu (benchmark 2026-10-16, lähde: FPLXI:n julkinen tarkkuus https://fplxi.com/vs/fantasy-football-hub)
  Perustelu: GoalIQ julkaisee ilmaisella xP-sivulla 10+- ja Blank-todennäköisyydet ja kirjaa gameweek calls -riveille esimerkiksi "32% chance of 10+", mutta jäädytetyissä `fpl_xp_frozen`-tiedostoissa on vain xp, xmins, ep_next ja form (tarkistettu gw7.json). Viiden kutsun kierroskohtainen loki ei riitä kalibraatioon. Isoissa pisteissä GoalIQ:n virhe on suurempi kuin FPL:n oman ep_nextin (MAE 8,77 vs 8,24, n=53), joten juuri tätä kannattaa mitata. Haul-todennäköisyyksien kalibraatiota ei löytynyt yhdeltäkään kilpailijalta. Mitä aiemmin jäädytys alkaa, sitä enemmän kierroksia on toukokuuhun mennessä.
  Data: oma xp_dist (simulaatio n=2000) ja FPL:n event/live-pisteet, molemmat jo käytössä.
  Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 1/3 · uutuus 2/2

- Oman joukkueen status-push: lähetä push, kun oman 15 pelaajan FPL-status muuttuu (a → d, i, s tai u) tai chance_of_playing laskee; pinta mobiili ja backend (push_dispatch, push_tokens) (benchmark 2026-10-16, lähde: Fantasy Football Hubin uusi sovellus https://app.fantasyfootballhub.co.uk/ffh-app-general.html)
  Perustelu: GoalIQ:n push kattaa deadlinen, hinnan ja mallin poiminnat, mutta ei omien pelaajien loukkaantumisia. FFH:n natiivisovellus mainostaa juuri tätä (injury updates) deadline- ja hintahälytysten rinnalla. Kohderyhmä on GoalIQ:n oman lupauksen mukainen ("someone who kept missing the deadline"). push_tokens-taulussa ei ole entry ID:tä, joten tarvitaan sarake tai sovelluksen lähettämä joukkue.
  Data: FPL bootstrap-static status, news ja chance_of_playing_next_round (jo haetaan) sekä FPL:n julkinen entry picks -rajapinta.
  Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 1/3 · uutuus 2/2

- Kenttäpelaajien rotaatioparit: laajenna Premiumin MV-rotaatioparit puolustajiin ja hyökkääjiin (2 tai 3 pelaajan yhdistelmät, joiden CS% tai xP vuorottelee 6 GW:n aikana); pinta SPA ja mobiili (benchmark 2026-10-16, lähde: FPL Rogue Player Rotation Planner https://www.fplrogue.com/tools ja Fix AI Rotation Planner https://www.fantasyfootballfix.com/premium/)
  Perustelu: Budjettipaikkojen vuorottelu on vakiotyökalu maksullisissa tasoissa (FPL Rogue Pro, Fix Premium, FFS:n tickerin rotation planner). GoalIQ:lla laskenta on olemassa maalivahdeille. Hyötyjä: Premium-käyttäjä, joka rakentaa wildcard-joukkuetta ennen GW19:tä.
  Data: oma CS% ja xP per GW.
  Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 2/3 · uutuus 1/2

- Miniliigan voittotodennäköisyys koko liigalle: laajenna "Catch your rival" simulaatioksi, joka antaa jokaiselle liigan jäsenelle voiton ja top 3:n todennäköisyyden jäljellä olevilla kierroksilla; pinta SPA ja mobiili (benchmark 2026-10-16, lähde: FPL Pulse Mini-League Simulator https://www.fplpulse.com/)
  Perustelu: Miniliiga on FPL:n tunneydin, ja FPL Pulse myy rajattomat simulaatiot Pro-tasolla (ilmaisella yksi ajo). GoalIQ laskee jo rivaalin kiinnikuromisen todennäköisyyden, joten koko liigan jakauma on luonteva laajennus. Virallinen peli näyttää live-aseman mutta ei todennäköisyyttä.
  Data: FPL:n leagues-classic- ja entry history -rajapinnat (jo käytössä miniliiganäkymässä) ja oma xP-jakauma.
  Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 2/3 · uutuus 1/2

- Maalin ja maalipisteen todennäköisyys xP-sivulle: lisää ilmaisen kuluvan GW:n xP-taulukon (top 20) riveille todennäköisyys, että pelaaja tekee maalin, ja todennäköisyys maalista tai syötöstä; pinta hub-sivu ja SPA (benchmark 2026-10-16, lähde: Fantasy Football Pundit Goalscorer & Assist Odds https://www.fantasyfootballpundit.com/)
  Perustelu: FFP:n "who is most likely to score or assist" -sivu on otsikkonsa mukaan kerroinpohjainen. GoalIQ voi vastata samaan kysymykseen omasta mallistaan ilman vedonlyöntikytköstä, ja pelaajakohtainen pistejakaumasimulaatio on jo olemassa. Copy julkaisutarkistajan kautta: vältä kerroin- ja "most likely" -kehystystä.
  Data: oma pelaajamalli (xp_dist-simulaatio).
  Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 1/3 · uutuus 1/2

- Lukuoikeudellinen MCP-liitin ilmaisdataan: tarjoa Claude- ja ChatGPT-käyttäjille MCP-palvelin, joka palauttaa vain jo ilmaiset luvut (CS%, FDR, top 100 xP, track record) lähdelinkkeineen; pinta API (Cloudflare Worker hub-datan päällä, ei Render) (benchmark 2026-10-16, lähde: FPL Guru MCP https://fplguru.com/ ja fpl_mcp https://github.com/GilbertKamau/fpl_mcp)
  Perustelu: Virallinen FPL Companion ei anna ennustettuja pisteitä, ja käyttäjät tuovat FPL-datan omaan tekoälyynsä MCP:n kautta (FPL Guru, avoimet palvelimet). GoalIQ optimoi jo tekoälyhakukoneille (llms.txt); MCP tekisi samoista luvuista kutsuttavia tarkistettavine historioineen. Premium-data ei saa vuotaa (portitus on palvelinpuolella). Ei Renderille: 512 Mi muisti ja aiempi OOM.
  Data: omat ilmaispinnat (staattinen hub-data, /api/accuracy). Isännöinti Cloudflare Workersin ilmaistasolla; 0 € -raja selvitettävä.
  Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 1/3 · uutuus 2/2

## 6. Mitä EI kannata kopioida (ja miksi)

- **Live-rank, live-pisteet, projisoitu bonus ja what-if-simulointi** (LiveFPL, FFH Live Mode, FPL.Live): virallinen peli teki nämä 26/27, ja FFH ja LiveFPL tarjoavat ne ilmaiseksi. Ei tuloja, ja kierroksen aikainen jatkuva pollaus kuormittaisi Renderiä.
- **Hinnanmuutosennuste kärkiominaisuutena:** virallinen ennustin päivittyy 15 minuutin välein, ja GoalIQ:n price watch näyttää jo FPL:n oman projektion 3 tunnin välein. Pidä ilmaisena ominaisuutena, älä investoi siihen.
- **AI-keskusteluavustaja** (Fix ChatFPL, FFH, FPL Pulse, FPL Guru, virallinen Companion): kielimallin kulu jokaisesta kysymyksestä (Fix rajoittaa krediiteillä), virallinen Companion on ilmainen, ja chat sotii "no language model in the prediction path" -linjaa vastaan. MCP-liitin (luku 5) antaa saman hyödyn ilman GoalIQ:n maksamaa kielimallia.
- **Joukkueen tuonti kuvakaappauksesta** (FFH, FPLXI): vaatii kuvantunnistusmallin, eli kulun; entry ID riittää.
- **Kielimallien otteluennusteet** (ScoreGPT, AIM GO, BetBrothers): MM 2026 -tutkimuksessa yksikään kielimalli ei voittanut markkinan Brier-pistettä, ja se rikkoisi GoalIQ:n julkisen metodilupauksen.
- **Vedonlyöntisisältö** (Forebetin Kelly-pohjaiset value-vedot, WinDrawWinin panoskoot, PredictZ:n ja Dimersin kertoimet, affiliate-linkit): GoalIQ:n positio on "not a betting service", ja kauppojen ja lainsäädännön riski kasvaisi. BTTS ja yli 2,5 pidetään analyyttisinä todennäköisyyksinä.
- **Vedonlyöntikertoimet mallin syötteenä** (Opta, FFP:n odds-sivut): maksullinen kerroindata ja vedonlyöntikytkös.
- **Opta-tilastolisenssi** (FFH, FFS, Fix): maksullinen. FPL:n API (Opta-pohjaiset kentät) ja oma laukausmalli riittävät.
- **Asiantuntijaverkosto ja yhteisöpalvelut** (team reveal -asiantuntijat, WhatsApp-ryhmät, Zoom-masterminds, henkilökohtainen tiimiarvio: FFH Pro ja Ultra, FFS): ihmistyötä, mahdotonta yhden hengen tuotteelle.
- **UCL Fantasy -työkalut** (FFS, FFP): UEFA:n käyttöehdot kieltävät automaattisen keruun, ja GoalIQ lopetti UCL Fantasyn 3.10.
- **Lifetime-hinta** (Fix £295) **ja "voita tai rahat takaisin" -takuu** (FFH): pitkä sitoumus palvelun jatkumisesta tai suora rahallinen riski yhden hengen tuotteelle.
- **GW-recap-kuvat ja tiimimerkit:** virallinen peli tekee nämä (Adobe Express). GoalIQ:n jaettavat kortit riittävät.
- **Apple Watch -laajennus** (FPLai): uusi alusta pienelle käyttäjämäärälle.
- **Eliittimanagerien live-siirtohälytykset** (Fix Premium Plus): vaatii valittujen entryjen jatkuvaa seurantaa; GoalIQ:n viikoittainen rank-tasojen otos (n=200) vastaa samaan kysymykseen.

## 7. Lähteet

Luettu 16.10.2026, ellei toisin mainita. "h" = hakukoneen tiivistelmä, sivua ei saatu auki suoraan.

**GoalIQ**
- [G1] `llms.txt`
- [G2] https://goaliq.app/
- [G3] https://goaliq.app/fpl ("Data updated 16 October 2026")
- [G4] https://goaliq.app/predictions
- [G5] https://goaliq.app/faq (päivitetty 3.10.2026)
- [G6] `web/pro-spa/src/lib/tools.ts` (SPA:n työkalurekisteri: reitit, tasot)
- [G7] https://api.goaliq.app/api/accuracy (updated_at 2026-10-16T12:54:35Z: all_time, brier, calibration)
- [G8] mobiilisovelluksen ilmoituskoodi (eri repo), `scripts/push_dispatch.py`, `supabase/migrations/20260813200000_add_push_tokens.sql`
- [G9] https://api.goaliq.app/api/fantasy/xp (ilman tunnusta: meta.masked = true, 10 pelaajaa)
- [G10] `src/models/fpl_xp.py` (#151 BPS 26/27), `src/models/fpl_price_watch.py`, https://api.goaliq.app/api/fantasy/price-watch (generated_at 2026-10-16T13:47:43Z)
- [G11] mobiilisovelluksen näkymät (eri repo): Parlay ja Model Accuracy
- [G12] `data/fpl_xp_frozen/gw7.json` (jäädytetyt kentät)
- [G13] sisäinen ominaisuusanalyysi 25.7.2026 (ei tässä repossa)

**FPL-kilpailijat ja virallinen peli**
- [F1] Fantasy Football Hub, etusivu ja navigaatio: https://www.fantasyfootballhub.co.uk/
- [F2] FFH, tasot ja hinnat: https://www.fantasyfootballhub.co.uk/member-upgrade ; Mini-League Promise ja kampanjaehdot (h): https://www.fantasyfootballhub.co.uk/join , https://www.fantasyfootballhub.co.uk/terms-and-conditions
- [F3] FFH, uusi sovellus: https://app.fantasyfootballhub.co.uk/ffh-app-general.html
- [F4] FFH, Google Play -julkaisutiedot 4.1.2 (h): https://play.google.com/store/apps/details?id=uk.co.fantasyfootballhub.app
- [F5] FPL Review: https://fplreview.com/ (sivun otsikko "Projections, Planner & Solver"; ominaisuuslista h) ja Patreon: https://www.patreon.com/fplreview/membership (Premium €3,90/kk + ALV, Dev Supporter €6,50)
- [F6] LiveFPL, Google Play -kuvaus (päivitetty 25.9.2026, sisältää mainoksia ja sovelluksen sisäisiä ostoja): https://play.google.com/store/apps/details?id=com.pocketgamerguides.livefpl&hl=en_GB
- [F7] LiveFPL, uudistettu sivusto (h): https://www.livefpl.net/
- [F8] Fantasy Football Scout, jäsenyydet ja vertailutaulukko: https://www.fantasyfootballscout.co.uk/register
- [F9] FFS, uusi sovellus 24.7.2026: https://www.fantasyfootballscout.co.uk/2026/07/24/get-the-new-and-upgraded-fantasy-football-scout-app-today
- [F10] Fantasy Football Fix, etusivu: https://www.fantasyfootballfix.com/
- [F11] Fix Premium: https://www.fantasyfootballfix.com/premium/
- [F12] FPL Form: https://www.fplform.com/
- [F13] Fantasy Football Pundit: https://www.fantasyfootballpundit.com/
- [F14] FPLStatistics: https://www.fplstatistics.com/ ja https://www.fplstatistics.co.uk/ (yhteys hylättiin 16.10, ECONNREFUSED); X-bio (h): https://x.com/fpl_statistics
- [F15] Premier League, "All you need to know about changes to FPL for 2026/27": https://www.premierleague.com/en/news/4679873/all-you-need-to-know-about-changes-to-fpl-for-202627
- [F16] Premier League, "What's new in 2026/27 Fantasy: Price Change Predictor": https://www.premierleague.com/en/news/4680462/whats-new-in-202627-fantasy-price-change-predictor
- [F17] Premier League, "Changes to Bonus Points System" (20.7.2026): https://www.premierleague.com/en/news/4679946/whats-new-in-202627-fantasy-changes-to-bonus-points-system
- [F18] Premier League, "How the Fantasy Premier League Companion can help you in 2026/27" (1.8.2026): https://www.premierleague.com/en/news/4685134/how-the-fantasy-premier-league-companion-can-help-you-in-202627
- [F19] Microsoft, FPL Companion (27.7.2026): https://news.microsoft.com/source/emea/features/fantasy-premier-league-companion-gives-managers-a-new-tool-for-success/
- [F20] FPL Rogue, hinnat ja työkalut: https://www.fplrogue.com/pricing , https://www.fplrogue.com/tools
- [F21] FPLXI vs Fantasy Football Hub: https://fplxi.com/vs/fantasy-football-hub
- [F22] FPL Pulse: https://www.fplpulse.com/
- [F23] FPL Guru: https://fplguru.com/
- [F24] FPLai: https://fplai.app/
- [F25] FFS, "FPL 2026/27: 5 rule changes + new features announced" ja kommentit: https://www.fantasyfootballscout.co.uk/2026/07/20/fpl-2026-27-5-rule-changes-new-features-announced
- [F26] Fix, "FPL 2026/27 Changes: Live Ranks, Bonus Points & Chips": https://www.fantasyfootballfix.com/blog-index/fpl-2026-27-new-rules/
- [F27] FPL:n julkinen API, bootstrap-static: https://fantasy.premierleague.com/api/bootstrap-static/
- [F28] MCP-palvelimet: https://github.com/GilbertKamau/fpl_mcp , https://github.com/dohyung1/x402-fpl-api (h)
- [F29] fploracle, "Best AI Tools for FPL in 2026/27, Reviewed" (h): https://fploracle.team/blog/best-ai-tools-for-fpl-2026-27
- [F30] OneFPL, deadlinet 2026/27 (h): https://onefpl.com/blog/fpl-deadlines-2026-27-every-gameweek
- [F31] FPL.Live, Google Play -arviot (h): https://play.google.com/store/apps/details?id=live.fpl
- [F32] Flashscore, FPL 2026/27 rule changes (h): https://www.flashscore.com/news/soccer-premier-league-fantasy-premier-league-2026-27-all-rule-changes-and-new-features/KGmq7ts1/
- [F33] Technology Record, FPL Companion (h): https://www.technologyrecord.com/article/microsoft-copilot-powered-fantasy-premier-league-companion-to-debut-this-season
- [F34] FPL Copilot (h): https://fplcopilot.com/solver
- [F35] LiveFPL X, GW1-rekisteröinnit (h): https://x.com/livefplnet

**Ennustepalvelut**
- [P1] Forebet FAQ (403 suoraan, h): https://www.forebet.com/en/faq
- [P2] Forebet, ominaisuudet (h): https://www.forebet.com/en/soccer-picks-system
- [P3] PredictZ (403 suoraan, h): https://www.predictz.com/
- [P4] WinDrawWin (403 suoraan, h): https://www.windrawwin.com/predictions/ , https://www.windrawwin.com/tips/england-premier-league/
- [P5] Opta Analyst, kausiennuste 2026-27: https://theanalyst.com/articles/premier-league-predictions-2026-27-opta-supercomputer
- [P6] Opta Analyst, viikon ottelut (h): https://theanalyst.com/articles/premier-league-match-predictions
- [P7] Dimers (h): https://www.dimers.com/epl/predictions ; Dimers Pro -arvio (h): https://www.betsmart.co/tool-reviews/dimers-pro
- [P8] ClubElo: http://clubelo.com/
- [P9] StatsUltra: https://statsultra.com/forecasts/premier-league/
- [P10] ScoreGPT: https://scoregpt.app/
- [P11] Ding, Guo, Xu: "FIFA World Cup 2026 as a Contamination-Free Benchmark for LLM Forecasting Agents" (20.7.2026): https://arxiv.org/abs/2607.17765
- [P12] xGStat (h): https://www.xgstat.com/
- [P13] AIM GO (h): https://apps.apple.com/us/app/aim-go-football-prediction-ai/id6763239787 ; BetBrothers (h): https://betbrothers.ai/

**Yhteisö**
- [R1] Reddit, julkinen haku: https://old.reddit.com/r/FantasyPL/search.json?q=tool%20wish%20existed&restrict_sr=1&sort=new&t=year (16.10 palautti kirjautumissivun "Welcome to Reddit"; ei jatkettu)
