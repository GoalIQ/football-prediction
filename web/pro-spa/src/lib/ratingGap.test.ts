import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { ratingGap, ratingGapBasis, ratingGapLabel } from './ratingGap';

/* Luvut mitattu livena 25.9 (GW6-GW11): vertailukohta 319.38, FPL:n
   kokonaisrankingin ykkonen 282.59, mallin oma entry 116920 321.97. */
const BEST = 319.38;

describe('ratingGap', () => {
	it('jaljessa: miinus ja yksi desimaali', () => {
		const g = ratingGap({ team_xp_horizon_no_captain: 282.59, optimal_team_xp: BEST, optimal_proven: false });
		expect(g?.text).toBe('-36.8 xP');
		expect(g?.diff).toBeCloseTo(-36.79, 2);
	});

	it('ylitys luetaan summista, ei backendin nollaan leikatusta gap-kentasta', () => {
		const g = ratingGap({ team_xp_horizon_no_captain: 321.97, optimal_team_xp: BEST, optimal_proven: false });
		expect(g?.text).toBe('+2.6 xP');
	});

	it('tasoissa on 0.0 ilman etumerkkia', () => {
		const g = ratingGap({ team_xp_horizon_no_captain: BEST + 0.04, optimal_team_xp: BEST });
		expect(g?.text).toBe('0.0 xP');
		expect(g?.diff).toBe(0);
	});

	it('puuttuva vertailukohta = ei lukua (vanha API, optimi 0, NaN)', () => {
		expect(ratingGap(null)).toBeNull();
		expect(ratingGap({ team_xp_horizon_no_captain: 280 })).toBeNull();
		expect(ratingGap({ team_xp_horizon_no_captain: 280, optimal_team_xp: 0 })).toBeNull();
		expect(ratingGap({ team_xp_horizon_no_captain: NaN, optimal_team_xp: BEST })).toBeNull();
	});

	it('puuttuva optimal_proven = ei todistettu (fail-closed)', () => {
		const g = ratingGap({ team_xp_horizon_no_captain: 282.59, optimal_team_xp: BEST });
		expect(g?.optimal_proven).toBe(false);
		expect(ratingGapLabel(g!)).toBe('vs best found');
		expect(ratingGapBasis(g!, 'over GW6-GW11')).toContain('the strongest squad the model found');
	});

	it('todistettu vertailukohta saa "best"-muodon', () => {
		const g = ratingGap({ team_xp_horizon_no_captain: 282.59, optimal_team_xp: BEST, optimal_proven: true });
		expect(ratingGapLabel(g!)).toBe('vs best squad');
	});

	it('peruste nimeaa molemmat summat ja kapteenin puuttumisen', () => {
		const g = ratingGap({ team_xp_horizon_no_captain: 282.59, optimal_team_xp: BEST });
		const s = ratingGapBasis(g!, 'over GW6-GW11');
		expect(s).toContain('319.4 xP over GW6-GW11');
		expect(s).toContain('yours 282.6');
		expect(s).toContain('captain left out on both sides');
	});
});

/* Portti: arvosanamuoto ei palaa otsikkoriville. '/100' ja varirajat olivat
   MP-09:n vika; jos joku palauttaa ne, tama kaatuu ennen deployta. */
describe('SquadHeaderRow ei nayta arvosanaa', () => {
	const src = readFileSync(new URL('./components/SquadHeaderRow.svelte', import.meta.url), 'utf-8');
	const code = src.replace(/<!--[\s\S]*?-->/g, '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

	it('ei /100-muotoa eika 90/75-rajoja', () => {
		expect(code).not.toMatch(/\/100/);
		expect(code).not.toMatch(/>=\s*90|>=\s*75/);
	});

	it('luku tulee lukijasta, ei omasta laskusta', () => {
		expect(code).toMatch(/ratingGapLabel\(gap\)/);
		expect(code).toMatch(/\{gap\.text\}/);
	});
});
