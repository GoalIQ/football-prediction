/**
 * Portti: WHATIF-ALKUTILA (Villen paatos 27.9.2026). What-if alkaa mallin
 * XI:sta ja MALLIN kapteenista; tallennettu oma kapteeni voittaa; vertailu on
 * mallin XI (ei viime kierroksen FPL-kapteeni `is_captain`).
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { isModelLineup, whatIfDefaultCaptain, whatIfInitialCaptain } from './whatIfStart';

const P = [
	{ id: 1, in_xi: true, is_captain: true },
	{ id: 2, in_xi: true },
	{ id: 3, in_xi: false }
];
const MC = { id: 2, gw: 6 };

describe('whatIfStart', () => {
	it('mallin kapteeni kentan kierrokselle, ei viime kierroksen is_captain', () => {
		expect(whatIfDefaultCaptain(P, MC, 6)).toBe(2);
		// Eri kierroksen kutsu ei osu: vanha kaytos (is_captain).
		expect(whatIfDefaultCaptain(P, MC, 7)).toBe(1);
		// Mallin kapteeni ei rungossa -> is_captain.
		expect(whatIfDefaultCaptain(P, { id: 99, gw: 6 }, 6)).toBe(1);
	});

	it('tallennettu oma kapteeni voittaa, jos rungossa', () => {
		expect(whatIfInitialCaptain(P, 3, MC, 6)).toBe(3);
		expect(whatIfInitialCaptain(P, 99, MC, 6)).toBe(2);
		expect(whatIfInitialCaptain(P, null, MC, 6)).toBe(2);
	});

	it('mallin XI tunnistetaan, muokkaus ei ole mallin XI', () => {
		expect(isModelLineup(P, [1, 2], 2, 2)).toBe(true);
		expect(isModelLineup(P, [2, 1], 2, 2)).toBe(true);
		expect(isModelLineup(P, [1, 3], 2, 2)).toBe(false);
		expect(isModelLineup(P, [1, 2], 1, 2)).toBe(false);
	});

	it('TeamPitchManager kayttaa lukijaa alkutilassa ja vertailussa', () => {
		const src = readFileSync(resolve(__dirname, 'components/TeamPitchManager.svelte'), 'utf8');
		expect(src).toMatch(/whatIfInitialCaptain\(players, savedCap, modelCaptain, defaultGw \?\? null\)/);
		expect(src).toMatch(/whatIfDefaultCaptain\(players, modelCaptain, defaultGw \?\? null\)/);
		expect(src).not.toMatch(/: \(players\.find\(\(p\) => p\.is_captain\)\?\.id \?\? null\)/);
		expect(src).toMatch(/xP vs the model's XI/);
		expect(src).not.toMatch(/loaded lineup/);
	});
});
