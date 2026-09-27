/**
 * CF-CRON-RELAY (AUTO-S14, 12.9.2026)
 *
 * MIKSI TAMA ON OLEMASSA. GitHubin cron laahaa repotasolla. Mitattu 7 vrk:
 *
 *   GoalIQ/football-prediction  fpl-transfer-watch  32 %
 *   GoalIQ/football-prediction  fpl-data-refresh    54 %
 *   GoalIQ/football-prediction  accuracy-log        59 %
 *   Veikkoville/goaliq-app      fp-dispatch-relay   29 %   <- relay silloin
 *
 * 10.9 rakennettiin `fp-dispatch-relay.yml`, joka laukaisee fp-repon
 * workflow't goaliq-appista kasin, koska goaliq-appin cronit toteutuivat
 * silloin 100 %. Mitattu 11.9: relayn OMA cron toteutui 5/15 tunnista, eli
 * viive tuli myos goaliq-appiin. Relay ei voi korjata itseaan.
 *
 * MITA TAMA WORKER EI TEE. Se EI toista relayn logiikkaa. Relay lukee
 * kohde-workflow'n cron-rivit fp-repon omasta tiedostosta (yksi lukija),
 * laskee mitka slotit laukesivat viimeisen 60 min aikana, ja dedupetoi:
 * jos fp-repossa on jo ajo luotu slotin jalkeen, se ei tuplaa. Se logiikka
 * on testattu (`tests/test_fp_dispatch_relay.py`) ja sen
 * kopioiminen tanne olisi kaksi lukijaa samaan kysymykseen — tasan se
 * vikaluokka jonka koko autopilot on olemassa estamaan.
 *
 * Tama worker tekee YHDEN asian: kutsuu relayn `workflow_dispatch`ia sen
 * omalla slotilla. Se on niin pieni, ettei se voi olla se osa joka on
 * rikki. Jos se silti on, relayn `concurrency`-ryhma ja 60 min lookback
 * tekevat ylimaarisesta kutsusta harmittoman.
 *
 * KELLONAIKAA EI SIIRRETA. Cron on `50 * * * *` eli sama slotti jonka
 * relay itse julistaa. Testi `test_cf_cron_relay.py` kaataa jos ne
 * eriytyvat, joten worker ei voi hiljaa ajaa eri hetkella kuin se
 * workflow jota se laukaisee.
 *
 * MITEN TAMAN VAIKUTUS MITATAAN. Ei taman workerin omasta lokista eika
 * "deployasinko mina" -tiedosta, vaan siita mita GitHub sanoo:
 * goaliq-appin `scripts/autopilot/cron_realization.py` laskee toteumaprosentin
 * 7 vrk:n ikkunassa, ja AUTO-S14 on kiinni vasta kun se on >= 60 %.
 *
 * 0 EUR: Workers free tier kattaa 100 000 pyyntoa/vrk; tama tekee 24.
 */

const GITHUB_API = 'https://api.github.com';

//: Kohde. 27.9.2026 relay siirtyi goaliq-appista (yksityinen, ~870
//: laskutettua Actions-min/kk) tahan julkiseen repoon, jossa ajot ovat
//: ilmaisia. PAT on scopattu omistajalle GoalIQ, repo football-prediction,
//: Actions: Read and write (secret GITHUB_DISPATCH_TOKEN_FP; vanha
//: GITHUB_DISPATCH_TOKEN osoitti goaliq-appiin).
const TARGET = {
	repo: 'GoalIQ/football-prediction',
	workflow: 'fp-dispatch-relay.yml',
	ref: 'main',
};

/** Laukaise relay. Palauttaa {ok, status, detail} — ei heita. */
async function dispatch(env) {
	const token = (env.GITHUB_DISPATCH_TOKEN_FP || '').trim();
	if (!token) {
		// Puuttuva secret EI ole poikkeus: se on konfiguraatiotila josta
		// kerrotaan selvasti. Heitto vain saisi CF:n yrittamaan uudelleen
		// ja tayttaisi lokin samalla rivilla (vrt. relayn oma ratkaisu:
		// puuttuva PAT paattaa ajon vihreana + ohje lokiin).
		return {
			ok: false,
			status: 0,
			detail:
				'GITHUB_DISPATCH_TOKEN_FP puuttuu. Aseta se: wrangler secret put ' +
				'GITHUB_DISPATCH_TOKEN_FP (fine-grained PAT, Resource owner ' +
				'GoalIQ, repo football-prediction, Actions: Read and write). ' +
				'Worker ei laukaise mitaan ennen sita.',
		};
	}

	const url = `${GITHUB_API}/repos/${TARGET.repo}/actions/workflows/${TARGET.workflow}/dispatches`;
	let res;
	try {
		res = await fetch(url, {
			method: 'POST',
			headers: {
				Authorization: `Bearer ${token}`,
				Accept: 'application/vnd.github+json',
				'X-GitHub-Api-Version': '2022-11-28',
				// GitHub vaatii User-Agentin; ilman sita 403.
				'User-Agent': 'GoalIQ-cf-cron-relay/1',
				'Content-Type': 'application/json',
			},
			body: JSON.stringify({ ref: TARGET.ref }),
		});
	} catch (e) {
		return { ok: false, status: 0, detail: `verkkovirhe: ${String(e).slice(0, 200)}` };
	}

	// 204 = laukaistu. Kaikki muu on syyta lokittaa rungon kanssa: 404
	// tarkoittaa yleensa etta PAT:lta puuttuu Actions-oikeus TAI ettei
	// workflow'lla ole `workflow_dispatch`-triggeria, ja ne ovat eri vikoja.
	if (res.status === 204) return { ok: true, status: 204, detail: 'dispatched' };
	let body = '';
	try {
		body = (await res.text()).slice(0, 300);
	} catch {
		body = '(rungon luku ei onnistunut)';
	}
	return { ok: false, status: res.status, detail: body };
}

export default {
	async scheduled(event, env, ctx) {
		const r = await dispatch(env);
		const at = new Date(event.scheduledTime).toISOString();
		if (r.ok) {
			console.log(`[cf-cron-relay] ${at} cron=${event.cron} -> ${TARGET.workflow} dispatched`);
			return;
		}
		// console.error nakyy `wrangler tail`issa ja CF:n Logsissa. Talla ei
		// ole vahtia: toteuma mitataan GitHubin ajolistasta
		// (`scripts/autopilot/cron_realization.py`), ei taman lokista.
		console.error(
			`[cf-cron-relay] ${at} cron=${event.cron} EI LAUKAISTU status=${r.status}: ${r.detail}`
		);
	},

	/**
	 * Konfiguraation kaiku. EI tilaa eika salaisuutta: kertoo vain mita tama
	 * worker laukaisee ja milla slotilla, jotta se on tarkistettavissa ilman
	 * dashboardia. `token_set` on boolean, ei arvo.
	 */
	async fetch(request, env) {
		const url = new URL(request.url);
		if (url.pathname !== '/' && url.pathname !== '/config') {
			return new Response('not found', { status: 404 });
		}
		return Response.json({
			worker: 'fp-cron-relay',
			purpose:
				'Trigger fp-dispatch-relay on its own slot because GitHub cron ' +
				'lags at repo level (measured 29 % over 7 days).',
			target: TARGET,
			token_set: Boolean((env.GITHUB_DISPATCH_TOKEN_FP || '').trim()),
			measured_by: 'goaliq-app scripts/autopilot/cron_realization.py (AUTO-S14)',
		});
	},
};
