/**
 * My teamin paatosvirta (WP16, 7.11.2026): yksi kysymys kerrallaan.
 *
 * MIKSI. Mitattu 390 x 844 -ruudulla ennen tata: kentta alkoi kohdasta 846 px
 * eli kokonaan ensimmaisen ruudun alta, vaikka Ville pyysi 5.9 etta kentta
 * nakyy ensimmaisena, ja siirtoratkaisu oli kohdassa 3 248 px
 * projektiotaulukon jalkeen, vaikka se on syy avata sivu.
 *
 * YKSI LUKIJA (CLAUDE.md 6a). Askeleet, niiden lyhyet vastaukset ja aktiivinen
 * askel ratkeavat tassa. Lukitusta vastauksesta (`personalLock`) ei tule
 * yhtaan askelta, joten maskatusta vastauksesta ei voi syntya "Hold"-vaitetta.
 * Tallennettu vastaus (`rateTeamCache`) voi olla vanhalta deploylta, joten
 * jokainen kentta luetaan vahdin kautta: puuttuva kentta poistaa askeleen tai
 * vastauksen, se ei keksi sita.
 *
 * Luvut ovat palvelimen. Tama ei laske eika lajittele mitaan uutta.
 */
import type { RateTeamResponse } from './fantasyTools';
import { personalLock } from './personalLock';
import { ratingGap } from './ratingGap';
import { NO_FIXTURE } from './weekRows';

export type FlowStepId = 'transfer' | 'captain' | 'news' | 'squad';

export interface FlowStep {
	id: FlowStepId;
	/** Otsikkorivin nimi. */
	label: string;
	/** Paneelin otsikko: se yksi kysymys. */
	question: string;
	/** Lyhyt vastaus otsikkorivilla. null = ei vaitetta, vain nimi. */
	answer: string | null;
}

/** Kierros jolle kapteeni on laskettu. Kesken kierroksen ilman `captain_gw`:ta
 *  null: `meta.gw` on silloin jo alkanut kierros, jolle kapteenia ei voi valita. */
export function captainGwOf(d: Pick<RateTeamResponse, 'meta'>): number | null {
	return d.meta.captain_gw ?? (d.meta.gw_in_progress === true ? null : d.meta.gw);
}

/** Kapteenin vastustajat rungon pelaajarivilta. NO_FIXTURE = ei ottelua,
 *  null = ei rivia eli ei tietoa. Ne ovat eri asioita. */
export function captainOppOf(
	d: Pick<RateTeamResponse, 'team'>,
	captainId: number | null | undefined,
	gw: number | null
): string | null {
	if (captainId == null || gw == null) return null;
	const row = d.team?.players?.find((p) => p.id === captainId);
	const g = row?.gameweeks?.find((x) => x.gw === gw);
	if (!g) return null;
	if (g.opponents.length === 0) return NO_FIXTURE;
	return g.opponents.map((o) => `${o.opp} (${o.venue})`).join(', ');
}

/** Sama kanta kuin siirtokortilla: hit-tietoinen verdikti ensin, vanha
 *  `hold`-lippu vain jos verdikti puuttuu. Tyhja lista on aina pito.
 *  Ei nimea: pelkka sukunimi luettiin vaarin (Tzolis/Tzolakis, $lib/transferLabel),
 *  ja siirto on ensimmainen askel, joten pari tunnisteineen on heti alla. */
function transferAnswer(d: RateTeamResponse): string | null {
	const t = d.transfers;
	if (!t) return null;
	const verdict = t.hold_verdict?.verdict;
	const hold = verdict ? verdict === 'hold' : t.hold === true;
	const top = t.suggestions?.[0];
	if (hold || !top) return 'Hold';
	return 'Move';
}

function newsAnswer(count: number | null): string | null {
	if (count == null) return null;
	if (count === 0) return 'None';
	return count === 1 ? '1 item' : `${count} items`;
}

/**
 * Virran askeleet jarjestyksessa. Siirto ensin (Villen 5.9: "se mita kayttaja
 * tulee hakemaan on itse siirto"), kapteeni sen jalkeen, koska siirto voi
 * muuttaa kapteenia.
 *
 * `newsCount`: rivien maara uutispaneelissa, null = ei viela tiedossa.
 */
export function myTeamFlowSteps(
	d: RateTeamResponse | null | undefined,
	premium: boolean,
	newsCount: number | null = null
): FlowStep[] {
	if (!d || personalLock(premium, d)) return [];
	const steps: FlowStep[] = [];
	if (d.transfers) {
		steps.push({
			id: 'transfer',
			label: 'Transfer',
			question: 'Should you make a transfer?',
			answer: transferAnswer(d)
		});
	}
	const cap = d.captain?.pick ?? null;
	if (cap) {
		steps.push({
			id: 'captain',
			label: 'Captain',
			question: 'Who gets the armband?',
			answer: cap.web_name
		});
	}
	steps.push({
		id: 'news',
		label: 'News',
		question: 'Anything to watch in your squad?',
		answer: newsAnswer(newsCount)
	});
	steps.push({
		id: 'squad',
		label: 'Squad',
		question: 'How does your squad compare?',
		answer: ratingGap(d.rating)?.text ?? null
	});
	return steps;
}

/** Valittu askel jos se on yha olemassa, muuten ensimmainen. Valinta voi jaada
 *  vanhaksi kun joukkue vaihtuu tai vastaus paivittyy. */
export function activeStepId(steps: FlowStep[], chosen: FlowStepId | null): FlowStepId | null {
	if (chosen && steps.some((s) => s.id === chosen)) return chosen;
	return steps[0]?.id ?? null;
}

/** Seuraava askel, null viimeisella. */
export function nextStep(steps: FlowStep[], id: FlowStepId | null): FlowStep | null {
	const i = steps.findIndex((s) => s.id === id);
	return i >= 0 ? (steps[i + 1] ?? null) : null;
}
