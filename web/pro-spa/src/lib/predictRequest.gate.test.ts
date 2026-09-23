/** Portti: maajoukkueliigan ennuste menee maajoukkuemallille, liigakoodin kanssa.
 *
 * 🔴 MIKSI (23.9, Villen havainto "miksei webissa nay nations league predict"):
 * Nations League puuttui SPA:n liigalistalta kokonaan, ja vaikka se olisi
 * lisatty, predictMatch kutsui aina /api/predict:ia. Mitattu tuotannossa:
 * /api/predict {leagues:['INT-Nations League']} -> 404 (seuramalli ei tunne
 * liigaa), /api/predict-wc samalla bodylla -> 200. Ilman liigakoodia
 * predict-wc olettaa World Cupin -> 404 "not a World Cup 2026 team".
 * Sama vika loytyi mobiilista samana paivana (lib/nationalPredict.ts).
 *
 * Kutsupaikka vartioidaan erikseen: funktiotesti ei huomaa, jos predictMatch
 * palaa kovakoodattuun polkuun ohi lukijan.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { predictRequest } from './predictRequest';
import { findLeague, LEAGUES, STANDINGS_LEAGUES } from './leagues';

const read = (f: string) => readFileSync(resolve(__dirname, f), 'utf-8');

describe('predictRequest: yksi lukija ennustepyynnolle', () => {
	it('Nations League -> /api/predict-wc, liigakoodi mukana', () => {
		const r = predictRequest('INT-Nations League', 'Portugal', 'Wales', 10);
		expect(r.path).toBe('/api/predict-wc');
		expect(r.body).toEqual({
			home_team: 'Portugal',
			away_team: 'Wales',
			leagues: ['INT-Nations League']
		});
	});

	it('seuraliigat -> /api/predict, top_n mukana', () => {
		for (const l of LEAGUES.filter((x) => !x.national)) {
			const r = predictRequest(l.code, 'A', 'B', 5);
			expect(r.path, l.code).toBe('/api/predict');
			expect(r.body, l.code).toEqual({
				home_team: 'A',
				away_team: 'B',
				leagues: [l.code],
				top_n: 5
			});
		}
	});

	it('Nations League on listalla maajoukkueena, ei sarjataulukossa', () => {
		expect(findLeague('INT-Nations League')?.national).toBe(true);
		expect(STANDINGS_LEAGUES.some((l) => l.code === 'INT-Nations League')).toBe(false);
	});
});

describe('kutsupaikat', () => {
	it('predictMatch kayttaa lukijaa eika kovakoodattua ennustepolkua', () => {
		const src = read('api.ts');
		const fn = src.slice(src.indexOf('export async function predictMatch'));
		const body = fn.slice(0, fn.indexOf('\n}\n'));
		expect(body).toContain('predictRequest(league, home, away, topN)');
		expect(body).toContain('${API_BASE}${req.path}');
		expect(body).toContain('JSON.stringify(req.body)');
		expect(src).not.toMatch(/\$\{API_BASE\}\/api\/predict(-wc)?[`?]/);
	});

	it('Predict: maajoukkueliigalla ei seuraliigojen "pre-match-logged"-ingressia', () => {
		const src = read('components/Predict.svelte');
		const m = src.slice(src.lastIndexOf('</script>'));
		const ifNat = m.indexOf('{#if national}');
		const orElse = m.indexOf('{:else}', ifNat);
		const logged = m.indexOf('pre-match-logged');
		expect(ifNat).toBeGreaterThan(-1);
		expect(m.slice(ifNat, orElse)).toContain("aren't in the");
		expect(m.slice(ifNat, orElse)).not.toContain('pre-match-logged');
		expect(logged).toBeGreaterThan(orElse);
	});

	it('Predict: maajoukkueen esitayttovirhe ei lupaa "yet ... appears once"', () => {
		const src = read('components/Predict.svelte');
		const i = src.indexOf('error = national');
		expect(i).toBeGreaterThan(-1);
		const natBranch = src.slice(i, src.indexOf('\n\t\t\t\t:', i));
		expect(natBranch).toContain("We couldn't find");
		expect(natBranch).toContain('${leagueLabel}');
		expect(natBranch).not.toMatch(/\byet\b|appears once/);
	});
});
