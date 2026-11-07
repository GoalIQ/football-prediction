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
 *
 * AIKA (julkaisutarkistaja k1, mitattu 7.11). Vastaus voi kuvata kierrosta,
 * jonka deadline on jo mennyt: Understat-katkossa xP jai 1.11:n versioon, ja
 * API sanoi GW10:n deadlinen jalkeen yha `gw_in_progress: false`,
 * `captain_gw: 10` ja siirtoikkuna GW10-14. `gw_in_progress` ei siis riita,
 * vaan kellonaika ratkaisee: siirto ja kapteeni syntyvat vain kun
 * `meta.deadline_time` on edessa. Sama koskee GW38:n jalkeista aikaa.
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

/** Vastauksen tuoreusraja: rakennamme datan useita kertoja paivassa. */
export const FRESH_MS = 24 * 60 * 60 * 1000;
/** Kauden viimeinen kierros: sen jalkeen ei tule paivitysta, jota odottaa. */
const LAST_GW = 38;

type FlowMeta = Pick<RateTeamResponse, 'meta'>;

/** Onko vastauksen deadline edessa. Puuttuva tai rikkinainen aika = ei, koska
 *  paatosta ei saa esittaa kierrokselle jonka tilaa ei tiedeta. */
export function deadlineAhead(d: FlowMeta, now: number): boolean {
	const t = Date.parse(d.meta.deadline_time ?? '');
	return Number.isFinite(t) && t > now;
}

/** Rivi virran ylapuolelle kun deadline on mennyt. null kun aika on edessa, ei
 *  tiedossa (ei voi vaittaa menneeksi) tai kausi on lopussa (ei tule paivitysta). */
export function flowNotice(d: FlowMeta, now: number): string | null {
	const t = Date.parse(d.meta.deadline_time ?? '');
	const gw = d.meta.deadline_gameweek;
	if (!Number.isFinite(t) || t > now) return null;
	if (typeof gw !== 'number' || gw >= LAST_GW) return null;
	return `GW${gw}'s deadline has passed and the model hasn't updated yet, so transfer and captain calls are paused here.`;
}

/** Paiva jolta rungon saatavuusliput ovat. Liput tulevat projektioartefaktista,
 *  eivat FPL:sta suoraan, joten paiva kuuluu lauseeseen. Lukijan aikavyohyke. */
export function flowUpdateDay(generatedAt: string | null | undefined): string | null {
	const t = Date.parse(generatedAt ?? '');
	if (!Number.isFinite(t)) return null;
	return new Date(t).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}

/** Rakennuspaiva kun projektio on yli vuorokauden vanha, muuten null.
 *  Katkossa API siirtaa kierroksen kellon mukaan, mutta luvut ovat viimeisesta
 *  rakennuksesta (7.11: GW11-kutsut 1.11:n projektiosta), joten paiva kuuluu
 *  jokaisen kutsun viereen. Ilman aikaa ei voi vaittaa kumpaankaan suuntaan. */
export function staleModelDay(generatedAt: string | null | undefined, now: number): string | null {
	const t = Date.parse(generatedAt ?? '');
	if (!Number.isFinite(t) || now - t < FRESH_MS) return null;
	return flowUpdateDay(generatedAt);
}

/** Rivi tyokalujen yhteiseen kehykseen. Lahde on xP:n rakennushetki, koska kutsut
 *  ovat siita: phase0 voi toipua ensin. */
export function staleModelLine(xpGeneratedAt: string | null | undefined, now: number): string | null {
	const day = staleModelDay(xpGeneratedAt, now);
	if (!day) return null;
	return `The model's projection is from ${day}. Results and injuries since then aren't in it.`;
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

/** "None" vain tuoreesta datasta: vanha artefakti ei todista etta FPL ei liputa
 *  ketaan (mitattu 7.11: 11 FPL:n liputtamaa pelaajaa oli artefaktissa puhtaita). */
function newsAnswer(count: number | null, fresh: boolean): string | null {
	if (count == null) return null;
	if (count === 0) return fresh ? 'None' : null;
	return count === 1 ? '1 item' : `${count} items`;
}

/**
 * Virran askeleet jarjestyksessa. Siirto ensin (Villen 5.9: "se mita kayttaja
 * tulee hakemaan on itse siirto"), kapteeni sen jalkeen, koska siirto voi
 * muuttaa kapteenia.
 *
 * `newsCount`: rivien maara uutispaneelissa, null = ei tiedossa.
 * `now`: kello millisekunteina ($lib/now.svelte), jotta deadlinen ylitys
 * poistaa askeleet ilman uutta hakua.
 */
export function myTeamFlowSteps(
	d: RateTeamResponse | null | undefined,
	premium: boolean,
	newsCount: number | null = null,
	now: number = Date.now()
): FlowStep[] {
	if (!d || personalLock(premium, d)) return [];
	const steps: FlowStep[] = [];
	const ahead = deadlineAhead(d, now);
	// Artefakti voi loppua ennen deadlinen kierrosta (k3: GW14:n jalkeen deadline 15).
	// Kesken GW14:n kapteeni ja ikkuna ovat yha 14, ja kun GW14 on pelattu, ikkuna on
	// tyhja ja kapteeni saisi 0 xP:ta. Ikkunan alku ratkaisee molemmat. Vanhalta
	// deploylta tallennetussa vastauksessa ikkunaa ei ole, joten silloin ei paateta.
	const dlGw = d.meta.deadline_gameweek;
	const win = d.transfers?.window_gws;
	const onDeadline =
		!Array.isArray(win) || typeof dlGw !== 'number' || win[0] === dlGw;
	const generated = Date.parse(d.meta.generated_at ?? '');
	const fresh = Number.isFinite(generated) && now - generated < FRESH_MS;
	if (ahead && onDeadline && d.transfers) {
		steps.push({
			id: 'transfer',
			label: 'Transfer',
			question: 'Should you make a transfer?',
			answer: transferAnswer(d)
		});
	}
	const cap = d.captain?.pick ?? null;
	if (ahead && onDeadline && cap) {
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
		answer: newsAnswer(newsCount, fresh)
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
