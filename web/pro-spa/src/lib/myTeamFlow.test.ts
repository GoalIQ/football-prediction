import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import type { RateTeamResponse } from './fantasyTools';
import {
	activeStepId,
	captainGwOf,
	captainOppOf,
	myTeamFlowSteps,
	nextStep,
	type FlowStep
} from './myTeamFlow';
import { NO_FIXTURE } from './weekRows';

/** Vain kentat joita lukija koskee. Vaiheet rakennetaan tasta (6a mekanismi 3). */
function payload(over: Record<string, unknown> = {}, meta: Record<string, unknown> = {}) {
	return {
		meta: { gw: 11, deadline_gameweek: 11, gw_in_progress: false, ...meta },
		team: {
			players: [
				{ id: 7, gameweeks: [{ gw: 11, opponents: [{ opp: 'TOT', venue: 'H' }] }, { gw: 12, opponents: [] }] }
			]
		},
		rating: { team_xp_horizon_no_captain: 260, optimal_team_xp: 263.6 },
		captain: { pick: { id: 7, web_name: 'Gabriel', team_short: 'ARS', gw_xp: 6.3 }, alternative: null },
		transfers: {
			hold: false,
			suggestions: [
				{ out: { web_name: 'Tarkowski' }, in: { web_name: 'Vuskovic' }, delta_xp_horizon: 3.1 }
			],
			hold_verdict: { verdict: 'transfer' }
		},
		...over
	} as unknown as RateTeamResponse;
}

const ids = (s: FlowStep[]) => s.map((x) => x.id);
const answer = (s: FlowStep[], id: string) => s.find((x) => x.id === id)?.answer;

describe('myTeamFlowSteps', () => {
	it('jarjestys: siirto, kapteeni, uutiset, joukkue', () => {
		expect(ids(myTeamFlowSteps(payload(), true))).toEqual(['transfer', 'captain', 'news', 'squad']);
	});

	it('lukittu vastaus ei anna yhtaan askelta eika vaitetta', () => {
		expect(myTeamFlowSteps(payload(), false)).toEqual([]);
		const masked = payload({}, { locked_tool: 'rate-my-team' });
		expect(myTeamFlowSteps(masked, true)).toEqual([]);
		expect(myTeamFlowSteps(null, true)).toEqual([]);
	});

	it('siirtovastaus: verdikti voittaa vanhan lipun, tyhja lista on pito', () => {
		const hold = payload({
			transfers: { hold: false, suggestions: payload().transfers.suggestions, hold_verdict: { verdict: 'hold' } }
		});
		expect(answer(myTeamFlowSteps(hold, true), 'transfer')).toBe('Hold');
		expect(answer(myTeamFlowSteps(payload(), true), 'transfer')).toBe('Move');
		const empty = payload({ transfers: { hold: false, suggestions: [] } });
		expect(answer(myTeamFlowSteps(empty, true), 'transfer')).toBe('Hold');
		const legacy = payload({ transfers: { hold: true, suggestions: payload().transfers.suggestions } });
		expect(answer(myTeamFlowSteps(legacy, true), 'transfer')).toBe('Hold');
	});

	it('vanhan deployn tallennettu vastaus: puuttuva kentta poistaa askeleen, ei keksi sita', () => {
		const old = payload({ transfers: undefined, captain: null, rating: undefined });
		const s = myTeamFlowSteps(old, true);
		expect(ids(s)).toEqual(['news', 'squad']);
		expect(answer(myTeamFlowSteps(payload(), true), 'squad')).toBe('-3.6 xP');
		expect(answer(s, 'squad')).toBeNull();
	});

	it('uutisvastaus: tuntematon ei ole nolla', () => {
		expect(answer(myTeamFlowSteps(payload(), true, null), 'news')).toBeNull();
		expect(answer(myTeamFlowSteps(payload(), true, 0), 'news')).toBe('None');
		expect(answer(myTeamFlowSteps(payload(), true, 1), 'news')).toBe('1 item');
		expect(answer(myTeamFlowSteps(payload(), true, 3), 'news')).toBe('3 items');
	});
});

describe('vaiheet (6a mekanismi 3)', () => {
	const phases: [string, Record<string, unknown>, number | null][] = [
		['ennen deadlinea', { gw: 11, gw_in_progress: false }, 11],
		['kesken kierroksen, captain_gw annettu', { gw: 11, gw_in_progress: true, captain_gw: 12 }, 12],
		['kesken kierroksen ilman captain_gw:ta', { gw: 11, gw_in_progress: true }, null],
		['kierroksen jalkeen', { gw: 12, gw_in_progress: false, captain_gw: 12 }, 12]
	];
	for (const [name, meta, gw] of phases) {
		it(`${name}: kapteenin kierros on ${gw}`, () => {
			expect(captainGwOf(payload({}, meta))).toBe(gw);
		});
		it(`${name}: virta ei hajoa`, () => {
			expect(ids(myTeamFlowSteps(payload({}, meta), true))).toContain('transfer');
		});
	}
});

describe('captainOppOf', () => {
	it('ottelu, ei ottelua ja ei tietoa ovat eri asioita', () => {
		const d = payload();
		expect(captainOppOf(d, 7, 11)).toBe('TOT (H)');
		expect(captainOppOf(d, 7, 12)).toBe(NO_FIXTURE);
		expect(captainOppOf(d, 7, 13)).toBeNull();
		expect(captainOppOf(d, 99, 11)).toBeNull();
		expect(captainOppOf(d, 7, null)).toBeNull();
	});
});

describe('activeStepId ja nextStep', () => {
	const steps = myTeamFlowSteps(payload(), true);
	it('vanhentunut valinta putoaa ensimmaiseen', () => {
		const short = steps.filter((s) => s.id !== 'captain');
		expect(activeStepId(short, 'captain')).toBe('transfer');
		expect(activeStepId(steps, 'news')).toBe('news');
		expect(activeStepId(steps, null)).toBe('transfer');
		expect(activeStepId([], 'news')).toBeNull();
	});
	it('viimeisella ei ole seuraavaa', () => {
		expect(nextStep(steps, 'transfer')?.id).toBe('captain');
		expect(nextStep(steps, 'squad')).toBeNull();
		expect(nextStep(steps, null)).toBeNull();
	});
});

/** Rakenneportti: kentta ensin, paatokset heti sen alla, ei mitaan kentan edessa. */
describe('RateTeam: kentta ensin (Villen 5.9)', () => {
	const raw = readFileSync(new URL('./components/RateTeam.svelte', import.meta.url), 'utf-8');
	const code = raw.replace(/<!--[\s\S]*?-->/g, '');
	const grid = code.slice(code.indexOf('<div class="result-grid">'));

	it('slot A:n tuloslohkossa ei ole otsikkorivia eika nauhaa kentan edessa', () => {
		const beforePitch = grid.slice(0, grid.indexOf('<TeamPitchManager'));
		expect(beforePitch).not.toContain('<SquadHeaderRow');
		expect(code).not.toContain('verdict-strip');
	});

	it('virta renderoityy kentan alle, ei projektioiden jalkeen', () => {
		expect(grid).toContain('belowPitch={decisionFlow}');
		expect(code).toMatch(/\{#snippet decisionFlow\(\)\}[\s\S]*?<MyTeamFlow/);
	});

	it('jokaisella askeleella on paneeli', () => {
		for (const k of ['transfer: flowTransfer', 'captain: flowCaptain', 'news: flowNews', 'squad: flowSquad'])
			expect(code).toContain(k);
	});
});
