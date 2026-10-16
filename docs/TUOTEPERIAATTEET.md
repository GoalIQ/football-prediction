# GoalIQ:n tuoteperiaatteet (auto-kehityksen ja aallonharjan ohje)

Tämä tiedosto kertoo agenteille, mikä tuote on ja mikä ei, jotta niiden ehdotukset osuvat oikeaan.
Vain ihminen muuttaa tätä tiedostoa (portti `.github/auto-kehitys/guard.py` estää agentin muutokset).
Ylläpitäjän linjaus 16.10.2026: tuotekehitys on automaatiota. Tuote benchmarkataan jatkuvasti ja uusia
ominaisuuksia haetaan sekä FPL-työkaluihin että ottelu-ennusteisiin. Ihmisen portti on merge.

## Mikä GoalIQ on

Kaksi tuotelinjaa samasta mallista:

1. **FPL-työkalut** (Premier Leaguen Fantasy): pelaajakohtaiset expected points (xP) per kierros,
   kapteeni, siirrot, chip timing, DefCon, mallin oma joukkue (entry 116920) julkisena kirjanpitona,
   hinnanmuutokset, joukkueuutiset, xG-johtajat, puolustusprofiilit, ennustetut avaukset.
   Lisäksi Saudi Pro Leaguen fantasy (`/spl`).
2. **Ottelu-ennusteet**: 1X2-todennäköisyydet, xG ja tulosjakauma Dixon-Coles-mallista kymmeneen
   sarjaan; julkinen track record, jossa jokainen ennuste kirjataan ennen alkua ja gradataan jälkeen.

Pinnat ja missä ne ovat tässä repossa:

| Pinta | Polku | Julkaisu |
|---|---|---|
| API (FastAPI, Render Starter 512 Mi) | `api/`, `src/` | push mainiin (buildFilter) |
| Web-sovellus pro.goaliq.app (SvelteKit) | `web/pro-spa/` | `pro-spa-deploy.yml` käsin |
| Hub-sivut goaliq.app (staattiset, generoidut) | `scripts/build_*.py` -> `fpl/`, `predictions/`, juuren `*.html` | `hub-deploy.yml` pushista |
| Datan tuottajat (botit) | `scripts/`, työnkulut | ajastetut työnkulut |
| Mobiilisovellus (iOS/Android) | eri repo (goaliq-app) | EI agentin aluetta |

Mobiilisovellus lukee samaa API:a. Uusi API-kenttä ei näy sovelluksessa ennen kuin sovellusta muutetaan,
joten uusi kyky rakennetaan ensin APIin ja webiin.

Käyttäjät tärkeysjärjestyksessä: FPL-manageri, joka tekee päätöksen ennen deadlinea (ilmainen ja Premium),
ennusteiden lukija, ja tekijä tai kumppani, joka lainaa lukuja (ilmaispinnan pitää kestää tarkistus).

## Periaatteet, joita jokaisen muutoksen on noudatettava

- **Väite tarvitsee reitin.** Jokainen luku julkisella pinnalla on tarkistettavissa ilmaispinnalta, ja
  lähde näkyy. Track recordia ei koskaan muokata jälkikäteen. Puuttuva arvo on "ei dataa", ei nolla.
- **Suunnittele niin, ettei vikaa voi syntyä.** (1) Yksi lukija, joka ei voi palauttaa väärää (esim.
  `fpl_xp.load_xp_actionable()` ei anna kierrosta, jonka deadline on mennyt). (2) Poikkeuslista, jossa on
  perustelu. (3) Invariantti mitataan joka kauden vaiheessa: ennen deadlinea, kesken kierroksen ja
  gradauksen jälkeen (`tests/test_gameweek_phase_invariants.py`). Kysy jokaiselta ominaisuudelta: mikä
  ulkoinen tila voi vaihtua alla (kierros, kausi, siirtoikkuna, chip, tilaus, kieli)?
- **Testi kutsuu kutsupaikkaa.** Todista, että testi kaatuu, kun kutsupaikka poistetaan, ei vain funktio.
- **Generoitu sivu regeneroidaan samassa muutoksessa.** Builderin muutos = aja builder ja committaa sivu
  (`tests/test_committed_pages_match_builder.py`).
- **Copy-sync.** Uusi tai muuttunut ominaisuus päivittää `llms.txt`:n ja sen sivun kuvauksen samassa
  PR:ssä. Hinnat, Premium-lupaukset, landing ja FAQ ovat ihmisen (myyntilupaus).
- **Julkinen teksti on englantia, lyhyttä ja tarkistettavaa.** Ei em dashia (—), ei solver-jargonia,
  ei markkinointisuperlatiiveja. Ihminen ajaa julkaisutarkistajan ennen mergeä, joten jokainen uusi tai
  muuttunut käyttäjälle näkyvä merkkijono listataan PR:n rungossa.
- **Free/Premium-raja on myyntipäätös.** Agentti ei siirrä ominaisuutta rajan yli. Uusi ominaisuus
  ehdotetaan Premiumiin tai ilmaiseksi PR:n rungossa, ja ihminen päättää.
- **Render 512 Mi.** Ei raskasta laskentaa eikä mallin sovitusta API-pyynnössä tai käynnistyksessä
  (3.10.2026 artefaktin poisto -> live-fitti -> OOM -> koko API 502). Raskas laskenta tehdään botissa,
  joka kirjoittaa artefaktin `data/`:aan, ja API lukee artefaktin.
- **Ei uusia riippuvuuksia** (Python tai npm) ilman ihmistä.

## Datalähteet

Sallittu: lähteet, joita repo jo käyttää, ja niiden ehtojen sisällä. Pääasiassa FPL:n julkinen API
(`fantasy.premierleague.com/api`, `src/data/fpl_api.py`), olemassa oleva football-data-syöte ja repoon
committoidut aineistot.

Kielletty:

- **UEFA** (uefa.com, gaming.uefa.com): käyttöehtojen kohta 6.2 kieltää automaattisen keruun
  (`tests/test_no_uefa_fetch.py`).
- **Understatin kuluvan kauden puolustussivu** (`/fpl/defence`): robots.txt kieltää.
- Maksulliset rajapinnat ja maksulliset tasot (0 euron sääntö), myös maksullinen kielimallirajapinta.
- Kirjautumista vaativat sivut, maksumuurin kiertäminen, vedonlyöntisivustojen keruu.

Uusi lähde vaatii ihmisen päätöksen: kirjoita siitä `⚠️ EHDOTUS/KYSYMYS` -rivi, jossa on ehtojen linkki.

## Mitä agentti ei tee

- Hintoja, Stripe- tai checkout-koodia, Premium-oikeuksien tarkistusta, tilauksia.
- Sähköposteja, push-viestejä tai sosiaalisen median postauksia.
- Deployta, mallin julkaisua tai `data/`-artefaktien käsimuokkausta. Mallin muutos tehdään haastajana:
  backtest tai vertailu samoilla riveillä, luvut PR:ään, ja julkaisu on ihmisen erillinen päätös.
- Mobiilisovellusta (eri repo).

## Tuotekehityksen suunta (16.10.2026)

Kun agentti ideoi, vähintään yksi kolmesta rivistä osuu näihin teemoihin. Järjestys: ensin se, mitä
geneerinen FPL-sivusto tai ennustesivusto ei pysty tekemään, eli oma malli, todistettu tarkkuus ja nopeus.

**FPL**

1. **Päätös ennen deadlinea, perusteltuna.** Kapteeni, siirrot, penkki ja chip yhdelle entry ID:lle, ja
   jokaisen suosituksen syy mallin luvuista näkyvissä.
2. **Live-kierros.** Mitä omalle joukkueelle tapahtuu juuri nyt: DefCon, bonus, autosubit, live-sijoitus.
3. **Sääntöaallot ensimmäisenä.** Kun FPL:n data muuttuu (uusi kenttä, chip tai pistesääntö,
   `data/fpl_schema_snapshot.json`), GoalIQ:lla on työkalu sille ensimmäisenä.
4. **Todistettu tarkkuus.** xP:n virhe FPL:n omaan ennusteeseen (ep_next) verrattuna, joka kierros, julkisesti.
5. **Minileaguet ja kilpakumppanit.** Erot, effective ownership omassa liigassa, vastustajan kapteeni.

**Ennusteet**

6. **Kalibraatio ja vertailu näkyviin.** Kuinka hyvin todennäköisyydet osuvat, sarjoittain, ja vertailu
   yksinkertaiseen perustasoon samoilla otteluilla.
7. **Ottelusivun syvyys.** Miksi malli sanoo niin: muoto, xG, kotietu, poissaolot, tulosjakauma.
8. **Kattavuus vapailla lähteillä.** Lisää sarjoja ja turnauksia vain sallituista lähteistä.

**Molemmat**

9. **Jaettava todiste.** Kortit ja linkit, jotka laskeutuvat sivulle, jolla sama luku näkyy.
10. **Nopea ja saavutettava mobiilissa.** 375 px, näppäimistö, kontrasti, ensimmäinen ruutu ilman odotusta.

## Mistä ideat haetaan, tässä järjestyksessä

1. `docs/AUTO-BACKLOG.md` lohko **Signaalit**: ylläpitäjän, käyttäjien ja autopilotin havainnot.
2. `docs/BENCHMARK.md`: viikoittainen kilpailija- ja ominaisuusvertailu (aallonharja-työnkulku) ja
   FPL-skeeman muutokset.
3. Mallin omat mittarit: `data/accuracy.json` (1X2, Brier, kalibraatio), `data/fpl_xp_gw_accuracy.json`
   (xP vs ep_next).
4. Testien ja koodin `TODO`- ja `HUOM`-kommentit.

## Hyvän backlog-rivin muoto

Yksi asia, yksi tai kaksi pintaa, alle 300 riviä käsin kirjoitettua koodia, ja todennus sanottuna: mikä
testi vihertyy tai mitä pitää näkyä missä. Jos et osaa sanoa todennusta, ehdotus ei ole valmis.

### Pisteet ja mittari

Jokaisen avoimen rivin alle tulee kaksi kenttää omille riveilleen:

      Pisteet: arvo 2/3 · kiire 1/3 · työ M · myynti 1/3 · uutuus 1/2 = 6
      Mittari: <mitä mitataan ja mistä> · tarkistus <vvvv-kk-pp>

- **arvo**: 3 = korjaa virheen, jonka käyttäjä kohtaa (väärä, vanha tai puuttuva luku, hämmentävä näkymä,
  saavutettavuuseste); 2 = uusi hyöty päätökseen tai luku, jota käyttäjä ei saa muualta; 1 = sisäinen.
- **kiire**: 3 = ikkuna alle 30 päivässä (deadline-rytmi, tupla- tai tyhjä kierros, chip-ikkuna,
  siirtoikkuna, kauden vaihe); 2 = 30-90 päivää; 1 = ei aikarajaa.
- **työ**: S = alle 50 riviä; M = 50-300; L = yli 300, selvitys ensin tai riippuu toisesta rivistä.
- **myynti**: 3 = maksava käyttäjä tai ylläpitäjä on pyytänyt (Signaalit); 2 = kilpailija myy tätä
  maksullisena (BENCHMARK.md); 1 = ei tiedossa.
- **uutuus**: 2 = uusi kyky, jota GoalIQ:lla ei ole; 1 = parantaa olemassa olevaa; 0 = korjaus, testi tai
  siistiminen.
- **Piste** = 2 × arvo + kiire + myynti + uutuus - työ (S 0, M 1, L 2). Suurin ensin, tasapelissä ylempi.
- **Lukitus**: ylläpitäjä voi aloittaa Pisteet-kentän merkinnällä `(lukittu)`. Lukitut tehdään ensin.
  Agentti ei lukitse eikä muuta olemassa olevia pisteitä tai mittareita.
- **Konservatiivisesti**: epävarmassa pienempi arvo, kiire ja myynti ja suurempi työ.
- **Mittari**: lähteen on oltava jo olemassa: PostHog-tapahtumat, `/api/accuracy`,
  `data/fpl_xp_gw_accuracy.json`, Cloudflare Web Analytics, autopilotin signaalit, testit.

### Kärkivuoro ja signaalit

- **Joka kolmas ajo on kärkivuoro.** Työnkulku laskee mainin `auto:`-commitit. Kärkivuorolla agentti
  valitsee suurimman pisteen rivin, jonka uutuus on 2. L-rivistä tehdään vaihe 1 ja loput kirjoitetaan
  uusiksi riveiksi. Jos uutuus 2 -riviä ei ole, agentti ideoi sellaisen teemoista ja BENCHMARK.md:stä.
- **Signaali muuttuu riviksi.** Alle 30 päivää vanhasta havainnosta, jolla ei ole merkintää "→ backlog",
  agentti kirjoittaa enintään yhden rivin ajoa kohden ja merkitsee havainnon.
- Enintään kaksi avointa auto-PR:ää kerrallaan. Ihminen mergeää (squash, otsikko säilyy `auto:`-alkuisena).
