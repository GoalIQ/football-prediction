/**
 * This week -rivien lukijat synteettisilla vaiheilla (saanto 6a kohta 3).
 *
 * Invariantti mitataan jokaisessa kauden vaiheessa, ei vain siina joka
 * sattuu olemaan tanaan (22.9: kierrosten valissa, GW6 deadline 10.10):
 *   - ennen deadlinea            next_gameweek == deadline_gameweek
 *   - kesken kierroksen          next_gameweek <  deadline_gameweek
 *   - kauden lopussa             ei deadlinea
 *   - kierros jota mallia ei gradattu on uusin (21.9: GW4)
 */
import { describe, expect, it } from 'vitest';
import type { FantasyResponse, ModelRaceResponse } from './api';
import { countdownText, weekPhase } from './gameweek';
import { gwCleanSheets, lastCall, seasonLine, teamsCsGrid } from './weekRows';
import { MODEL_SERIES_COPY } from './modelSeriesCopy';

type Fx = FantasyResponse['teams'][number]['fixtures'][number];
const fx = (gw: number, opp: string, cs: number | undefined, tier: 'near' | 'far' = 'near', venue = 'H'): Fx => ({
	gw,
	opponent_short: opp,
	venue,
	fdr: 3,
	...(cs === undefined ? {} : { cs_pct: cs }),
	tier
});
function fantasy(meta: Partial<FantasyResponse['meta']>, teams: [string, Fx[]][]): FantasyResponse {
	return {
		meta: { available: true, ...meta },
		teams: teams.map(([short, fixtures]) => ({
			name: `${short} FC`,
			short,
			next_avg_cs_pct: 0,
			next_avg_fdr: 0,
			fixtures
		}))
	};
}
const TEAMS: [string, Fx[]][] = [
	['ARS', [fx(5, 'CHE', 30), fx(6, 'LEE', 47), fx(7, 'NFO', 50)]],
	['NEW', [fx(5, 'MUN', 55), fx(6, 'BUR', 38), fx(6, 'WOL', 41), fx(7, 'EVE', 33)]],
	['HUL', [fx(5, 'SUN', 20), fx(6, 'IPS', 39), fx(7, 'LIV', 12, 'far')]],
	['MCI', [fx(5, 'BHA', 40), fx(7, 'LIV', 35)]]
];

describe('weekPhase: kolme vaihetta', () => {
	const now = Date.parse('2026-09-22T10:00:00Z');
	it('ennen deadlinea: ei kesken olevaa kierrosta, tunnit jaljella', () => {
		const p = weekPhase({ next_gameweek: 6, deadline_gameweek: 6, deadline_utc: '2026-10-10T10:00:00+00:00' }, now)!;
		expect(p.gw).toBe(6);
		expect(p.liveGw).toBeNull();
		expect(p.hoursLeft).toBe(432);
		expect(countdownText(p.hoursLeft)).toBe('18 days');
	});
	it('kesken kierroksen: deadline-kierros on paatosten kierros, kesken oleva nimetaan', () => {
		const p = weekPhase({ next_gameweek: 5, deadline_gameweek: 6, deadline_utc: '2026-10-10T10:00:00+00:00' }, now)!;
		expect(p.gw).toBe(6);
		expect(p.liveGw).toBe(5);
	});
	it('kauden lopussa ilman deadlinea: ei keksittya aikaa eika kierrosta', () => {
		expect(weekPhase({}, now)).toBeNull();
		const p = weekPhase({ next_gameweek: 38 }, now)!;
		expect(p.deadline).toBeNull();
		expect(p.hoursLeft).toBeNull();
		expect(countdownText(null)).toBeNull();
	});
	it('deadline meni mutta meta ei ole viela paivittynyt: ei laskuria', () => {
		const p = weekPhase({ next_gameweek: 6, deadline_gameweek: 6, deadline_utc: '2026-09-22T09:00:00Z' }, now)!;
		expect(p.hoursLeft).toBeNull();
	});
	it('laskurin rajat', () => {
		expect(countdownText(47)).toBe('1 day');
		expect(countdownText(5)).toBe('5 hours');
		expect(countdownText(1)).toBe('1 hour');
		expect(countdownText(0)).toBe('under an hour');
	});
});

describe('gwCleanSheets: deadline-kierros, ottelu kerrallaan', () => {
	it('ennen deadlinea: GW6, paras ensin, tuplakierroksen ottelut erikseen', () => {
		const r = gwCleanSheets(fantasy({ next_gameweek: 6, deadline_gameweek: 6 }, TEAMS), 5)!;
		expect(r.gw).toBe(6);
		expect(r.rows.map((x) => `${x.team}-${x.opponent}-${x.cs}`)).toEqual([
			'ARS-LEE-47',
			'NEW-WOL-41',
			'HUL-IPS-39',
			'NEW-BUR-38'
		]);
	});
	it('kesken kierroksen: EI kesken olevaa GW5:tta (siihen ei voi enaa vaikuttaa)', () => {
		const r = gwCleanSheets(fantasy({ next_gameweek: 5, deadline_gameweek: 6 }, TEAMS), 3)!;
		expect(r.gw).toBe(6);
		expect(r.rows.some((x) => x.opponent === 'MUN')).toBe(false);
	});
	it('erotteleva kontrolli: next_gameweekin varaan rakennettu lukija nayttaisi GW5:n', () => {
		const d = fantasy({ next_gameweek: 5, deadline_gameweek: 6 }, TEAMS);
		const wrong = d.teams.flatMap((t) => t.fixtures.filter((f) => f.gw === d.meta.next_gameweek));
		expect(wrong.some((f) => f.opponent_short === 'MUN')).toBe(true);
	});
	it('kaukorivi ja luvuton rivi eivat saa lukua; ei dataa -> null', () => {
		const r = gwCleanSheets(fantasy({ deadline_gameweek: 7 }, TEAMS), 10)!;
		expect(r.rows.some((x) => x.opponent === 'LIV' && x.team === 'HUL')).toBe(false);
		expect(gwCleanSheets(null)).toBeNull();
		expect(gwCleanSheets({ meta: { available: false }, teams: [] })).toBeNull();
	});
});

describe('teamsCsGrid: Teams-nakyma ilman FDR:aa', () => {
	it('sarakkeet deadline-kierroksesta, kesken oleva pois, tyhja kierros on Blank eika nolla', () => {
		const g = teamsCsGrid(fantasy({ next_gameweek: 5, deadline_gameweek: 6 }, TEAMS))!;
		expect(g.gws).toEqual([6, 7]);
		const mci = g.rows.find((r) => r.team === 'MCI')!;
		expect(mci.cells[0]).toMatchObject({ gw: 6, blank: true, fixtures: [] });
		// HUL GW7 on kaukorivi: ottelu on, lukua ei.
		const hul = g.rows.find((r) => r.team === 'HUL')!;
		expect(hul.cells[1]).toMatchObject({ gw: 7, blank: false, fixtures: [] });
		expect(hul.avg).toBe(39);
	});
	it('jarjestys keskiarvon mukaan, tuplakierros laskee molemmat ottelut', () => {
		const g = teamsCsGrid(fantasy({ next_gameweek: 6, deadline_gameweek: 6 }, TEAMS))!;
		expect(g.rows.map((r) => r.team)).toEqual(['ARS', 'HUL', 'NEW', 'MCI']);
		const newc = g.rows.find((r) => r.team === 'NEW')!;
		expect(newc.games).toBe(3);
		expect(newc.avg).toBeCloseTo((38 + 41 + 33) / 3, 5);
	});
});

/* ---------------- model-race ---------------- */
function race(
	over: Omit<Partial<ModelRaceResponse>, 'meta'> & { meta?: Partial<ModelRaceResponse['meta']> }
): ModelRaceResponse {
	return {
		meta: {
			available: true,
			graded_gws: 4,
			compared_gws: 4,
			masked: true,
			model_plays_chips: false,
			note: null,
			...(over.meta ?? {})
		},
		totals: { model: 208, you: 261, diff: 53, ...(over.totals ?? {}) },
		gameweeks: over.gameweeks ?? [
			{ gw: 3, model_points: 63, fpl_average: 51, your_points: 72, diff: 9, cumulative_diff: 56 },
			{ gw: 5, model_points: 43, fpl_average: 48, your_points: 40, diff: -3, cumulative_diff: 53 }
		]
	} as ModelRaceResponse;
}

describe('lastCall: viimeisin kierros mallin sarjassa', () => {
	it('gradauksen jalkeen: uusin rivi, luvut palvelimelta sellaisenaan', () => {
		expect(lastCall(race({}))).toEqual({
			kind: 'scored',
			gw: 5,
			model: 43,
			you: 40,
			average: 48,
			provisional: false,
			beforeHits: false
		});
	});
	it('gradaamaton kierros on uusin: EI hypata vanhempaan, vaan kerrotaan miksi', () => {
		const r = race({
			meta: { unscored_gws: [{ gw: 6, code: 'no_valid_frozen_squad', would_have_scored: 49, fpl_average: 69 }] }
		});
		const lc = lastCall(r)!;
		expect(lc.kind).toBe('unscored');
		expect(lc.gw).toBe(6);
		expect(lc.kind === 'unscored' && lc.text).toBe(MODEL_SERIES_COPY.unscoredNoValidFreeze(6, 49, 69));
	});
	it('vanhempi gradaamaton kierros (21.9: GW4) ei peita uudempaa riviä', () => {
		const r = race({ meta: { unscored_gws: [{ gw: 4, code: 'no_valid_frozen_squad' }] } });
		expect(lastCall(r)?.gw).toBe(5);
	});
	it('tuntematon syykoodi uusimmalla kierroksella: ei rivia (syyta ei keksita)', () => {
		const r = race({ meta: { unscored_gws: [{ gw: 6, code: 'something_new' }] } });
		expect(lastCall(r)).toBeNull();
	});
	it('stale mallin luku -> null (ei nollaa), provisional ja brutto merkitaan', () => {
		const r = race({
			gameweeks: [
				{
					gw: 5,
					model_points: 43,
					fpl_average: 48,
					your_points: null,
					diff: null,
					cumulative_diff: null,
					stale_model_points: true,
					provisional: true,
					model_cost_verified: false
				}
			]
		});
		expect(lastCall(r)).toMatchObject({ model: null, you: null, provisional: true, beforeHits: true });
	});
	it('ei gradausta viela: null', () => {
		expect(lastCall(race({ meta: { available: false } }))).toBeNull();
		expect(lastCall(null)).toBeNull();
	});
});

describe('seasonLine: sina vs malli tai malli vs keskiarvo', () => {
	it('entryn kanssa: ero ja kierrosmaara', () => {
		expect(seasonLine(race({}))).toEqual({ kind: 'you', diff: 53, gameweeks: 4 });
	});
	it('ilman entrya: mallin rivi vs keskiarvo vain kun hitit on vahennetty', () => {
		const base = { gameweeks: 4, points: 208, average: 230, diff: -22, gws: [1, 2, 3, 5] };
		const r = race({ totals: { model: 208, you: null, diff: null, model_vs_average: { ...base, hits_deducted: true } } });
		expect(seasonLine(r)).toEqual({
			kind: 'model_vs_average',
			text: 'Model vs the FPL average: -22 over 4 gameweeks, hits deducted'
		});
		const gross = race({ totals: { model: 208, you: null, diff: null, model_vs_average: { ...base, hits_deducted: false } } });
		expect(seasonLine(gross)).toBeNull();
	});
});
