/**
 * UCL Fantasy -valintalistat (UCL-LAAJENNUS-FPL-TYYLIIN vaihe 1, 23.9.2026).
 *
 * FPL:n Players-esiasetusten kaava (captain, value, differentials) UCL:n
 * xP-artefaktista. YKSI LUKIJA: /ucl-sivu ei laske listoja itse, ja mobiilin
 * `lib/uclPicks.ts` on taman sanatarkka kopio (sama testisarja).
 * Spec: goaliq-app/cos-reports/ucl-laajennus-spec.md.
 *
 * Mika voi vaihtua alla (saanto 6a) ja miten lukija torjuu sen:
 *   - matchday: kapteenilista lukee kierroksen `meta.deadline_gameweek`ista
 *     ja hakee rivin gw-NUMEROLLA, ei `gameweeks[0]`:sta. Mennyt deadline
 *     (`meta.deadline_passed`) tai puuttuva deadline -> ei listaa: lukittua
 *     kierrosta ei esiteta tulevana.
 *   - tilaus: maskattu vastaus (`meta.masked`) on xP-summan karkikymmenikko.
 *     Siita laskettu "paras arvo" tai "differentiaali" olisi vaara vastaus,
 *     joten lukija palauttaa `locked` eika listaa.
 *   - sarjavaihe: `available=false` -> ei listoja.
 *   - datapohja: thin data (`uefa_matches`) ja `no_history` pois oletuksena;
 *     MD1-takatestissa UEFA-pohjaiset olivat yliennustettuja. Kytkin tuo ne.
 */

export type UclView = 'all' | 'captain' | 'value' | 'differentials';
export const UCL_VIEWS: readonly UclView[] = ['all', 'captain', 'value', 'differentials'];

/** FPL:ssa 10 %. UCL:ssa omistus on jyrkempi: 23.9 xP-summan top 60:sta
 *  40 oli <= 5 % ja 46 <= 10 %, eli 10 % ei erottelisi juuri mitaan. */
export const UCL_DIFF_MAX_OWNED = 5;
export const UCL_CAPTAIN_TOP = 10;
export const UCL_LIST_TOP = 20;

export type UclPos = 'ALL' | 'GKP' | 'DEF' | 'MID' | 'FWD';

export interface UclPickPlayer {
	id: number;
	pos: string;
	price: number;
	owned_pct: number;
	status: string;
	data_basis: string;
	xp_horizon_total: number;
	gameweeks: { gw: number; xp: number }[];
}

export interface UclPickMeta {
	available?: boolean;
	masked?: boolean;
	deadline_gameweek?: number | null;
	deadline_passed?: boolean;
}

export type UclPickRow<P extends UclPickPlayer> = { player: P; score: number };

export type UclPicks<P extends UclPickPlayer> =
	| { state: 'rows'; rows: UclPickRow<P>[]; md: number | null; hiddenThin: number }
	| { state: 'locked' }
	| { state: 'no_matchday' }
	| { state: 'unavailable' };

/** Kierros jolle kapteeni valitaan, tai null kun sita ei saa esittaa tulevana. */
export function captainMatchday(meta: UclPickMeta | null | undefined): number | null {
	if (!meta || meta.deadline_passed) return null;
	const md = meta.deadline_gameweek;
	return typeof md === 'number' && Number.isInteger(md) && md >= 1 ? md : null;
}

/** Pelaajan xP annetulla matchdaylla (rivi haetaan numerolla). */
export function matchdayXp(p: UclPickPlayer, md: number): number | null {
	const g = (p.gameweeks ?? []).find((x) => x.gw === md);
	return g && Number.isFinite(g.xp) ? g.xp : null;
}

function isThin(p: UclPickPlayer): boolean {
	return p.data_basis === 'uefa_matches' || p.data_basis === 'no_history';
}

export function uclPicks<P extends UclPickPlayer>(
	players: readonly P[] | null | undefined,
	meta: UclPickMeta | null | undefined,
	view: Exclude<UclView, 'all'>,
	opts: { pos?: UclPos; includeThin?: boolean } = {}
): UclPicks<P> {
	if (!meta || meta.available === false || !players || players.length === 0) {
		return { state: 'unavailable' };
	}
	if (meta.masked) return { state: 'locked' };
	const pos = opts.pos ?? 'ALL';
	const inPos = players.filter((p) => pos === 'ALL' || p.pos === pos);
	let md: number | null = null;
	if (view === 'captain') {
		md = captainMatchday(meta);
		if (md == null) return { state: 'no_matchday' };
	}
	const all = rank(inPos, view, md);
	if (opts.includeThin) return { state: 'rows', rows: all, md, hiddenThin: 0 };
	// Montako thin data -rivia nousisi listalle jos ne naytettaisiin: sivu
	// kertoo taman luvun, jotta piilotus ei ole hiljainen.
	const hiddenThin = all.filter((r) => isThin(r.player)).length;
	return { state: 'rows', rows: rank(inPos.filter((p) => !isThin(p)), view, md), md, hiddenThin };
}

function rank<P extends UclPickPlayer>(
	base: readonly P[],
	view: Exclude<UclView, 'all'>,
	md: number | null
): UclPickRow<P>[] {
	if (view === 'captain' && md != null) {
		return base
			.map((player) => ({ player, score: matchdayXp(player, md) }))
			.filter((r): r is UclPickRow<P> => r.score != null && r.score > 0)
			.sort((a, b) => b.score - a.score)
			.slice(0, UCL_CAPTAIN_TOP);
	}
	// Value ja differentials: vain pelattavissa olevat (FPL:n value_list
	// kayttaa samaa saatavuusporttia: loukkaantunut ei ole "value pick").
	const fit = base.filter((p) => p.status === 'a');
	if (view === 'value') {
		return fit
			.filter((p) => p.price > 0)
			.map((player) => ({ player, score: player.xp_horizon_total / player.price }))
			.sort((a, b) => b.score - a.score)
			.slice(0, UCL_LIST_TOP);
	}
	return fit
		.filter((p) => p.owned_pct <= UCL_DIFF_MAX_OWNED)
		.map((player) => ({ player, score: player.xp_horizon_total }))
		.sort((a, b) => b.score - a.score)
		.slice(0, UCL_LIST_TOP);
}
