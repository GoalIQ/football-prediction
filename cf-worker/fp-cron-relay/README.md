# fp-cron-relay: Cloudflare Worker joka laukaisee relayn

Worker kutsuu tämän repon `fp-dispatch-relay.yml`:n `workflow_dispatch`ia
slotilla `50 * * * *`. Relay (`scripts/fp_dispatch_relay.py`) päättää mitkä
ajastetut workflow't laukaistaan.

**Historia.** Rakennettu 12.9.2026 laukaisemaan goaliq-appissa asunutta relayta.
27.9.2026 relay siirtyi tähän julkiseen repoon, koska goaliq-app on yksityinen ja
relay kulutti siellä ~870 laskutettua Actions-minuuttia kuukaudessa. Samalla
workerin koodi siirtyi tänne ja kohde vaihtui (`GoalIQ/football-prediction`,
secret `GITHUB_DISPATCH_TOKEN_FP`). 12.9-17.9 cron ei lauennut kertaakaan
vaikka `wrangler deploy` tulosti schedulen; korjaus oli `npx wrangler triggers
deploy` (ks. "Deployn jälkeen").

## Miksi

GitHubin cron laahaa repotasolla. Mitattu 7 vrk 17.9 (goaliq-appin
`scripts/autopilot/cron_realization.py`): fpl-transfer-watch 32 %,
fpl-data-refresh 54 %, accuracy-log 59 %, ja relayn oma cron 29 %. Relay ei voi
korjata itseään; tämä worker on ulkoinen laukaisin. Relayn oma cron jää
varmistukseksi.

## Mitä se ei tee

Se **ei toista relayn logiikkaa.** Relay lukee kohteiden cron-rivit niiden omista
tiedostoista, laskee mitkä slotit laukesivat viimeisen 60 min aikana ja
dedupetoi (jos kohteella on jo ajo slotin jälkeen, se ei tuplaa). Worker tekee
yhden asian: kutsuu relayn `workflow_dispatch`ia sen omalla slotilla. Portti
`tests/test_cf_cron_relay.py` kaataa jos workerin cron eriytyy relayn cronista
tai workeriin ilmestyy kohdelista.

## Secret

Fine-grained PAT: Resource owner **GoalIQ**, repo **football-prediction**,
**Actions: Read and write**, ei muita oikeuksia. Asetetaan vain workerin
secretiksi, ei mihinkään tiedostoon. Workerin kansiosta:

```
npx wrangler secret put GITHUB_DISPATCH_TOKEN_FP
```

Tarkistus (näyttää nimen, ei arvoa):

```
npx wrangler secret list
```

PAT:lla on vanhenemispäivä. Kun se umpeutuu, worker lokittaa `status=401` eikä
laukaise mitään; relayn oma cron jää ainoaksi laukaisimeksi.

## Deploy

Workerin kansiosta (ei kotihakemistosta: wrangler ei silloin löydä
`wrangler.jsonc`:tä):

```
npx wrangler deploy
npx wrangler triggers deploy
```

Tällä workerilla ei ole julkista URLia (`workers_dev: false`), eikä sellaista
avata tarkistusta varten. `fetch`-käsittelijä on `wrangler dev` -ajoa varten.

## Deployn jälkeen: mittaa seuraava slotti, älä lue deploy-tulostetta

1. Aja irrallisena prosessina `timeout 600 npx wrangler tail fp-cron-relay --format json > <tiedosto>`
   niin että se kattaa seuraavan `:50`-slotin. JSON-muodossa banneria ei tulostu,
   joten tyhjä tiedosto tarkoittaa "ei tapahtumia".
2. Tarkista relayn ajolista: `gh run list -R GoalIQ/football-prediction --workflow fp-dispatch-relay.yml -L 3 --json event,createdAt`.
   Slotin jälkeen pitää olla `workflow_dispatch`.
3. Jos slotti meni tyhjänä: `npx wrangler triggers deploy` ja mittaa uudelleen.
4. `status=404` lokissa tarkoittaa että PAT:lta puuttuu Actions-oikeus tai sen
   omistaja/repo on väärä.

**AUTO-S14 on kiinni vasta kun** goaliq-appin `scripts/autopilot/cron_realization.py`
sanoo kohteiden toteuman **≥ 60 %** 7 vrk:n ikkunassa. Mittari laskee sekä
`schedule`- että `workflow_dispatch`-ajot slotin toteumaksi.

## 0 €

Workers free tier: 100 000 pyyntöä/vrk, tämä tekee 24. Relayn Actions-ajot ovat
julkisessa repossa ilmaisia.
