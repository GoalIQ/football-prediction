/**
 * Portti: WHATIF-ALKUTILA (Villen paatos 27.9.2026). What-if alkaa mallin
 * XI:sta ja mallin kapteenista; tallennettu oma kapteeni voittaa; vertailu
 * "xP vs the model's XI" on mallin XI + mallin kapteeni KENTAN kierrokselle,
 * luettuna rungosta jonka malli arvioi.
 *
 * Julkaisutarkistaja 27.9 k1 (BLOKATTU): B1 kesken kierroksen
 * (`captain_gw = gw + 1`) paluu `is_captain`iin antoi kayttajan oman
 * kapteenin; B2 siirron jalkeen tuleva pelaaja perii lahtevan `in_xi`:n.
 * Mobiilin portti (goaliq-app lib/whatIfStart.test.ts) ajaa saman saannon
 * molempia moduuleja vasten.
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import {
	isModelLineup,
	modelBaselineXp,
	roundXp,
	whatIfDefaultCaptain,
	whatIfInitialCaptain
} from './whatIfStart';

const pl = (id: number, in_xi: boolean, gw6: number, gw7: number, is_captain = false) => ({
	id,
	in_xi,
	is_captain,
	xp_per_gw: (gw6 + gw7) / 2,
	gameweeks: [
		{ gw: 6, xp: gw6 },
		{ gw: 7, xp: gw7 }
	]
});
// XI = 1, 2; kayttajan FPL-kapteeni 3 on penkilla.
const MODEL = [pl(1, true, 5, 10), pl(2, true, 6, 3), pl(3, false, 2, 2, true)];
const at = (gw: number) => (p: (typeof MODEL)[number]) => roundXp(p, gw);

describe('whatIfStart', () => {
	it('kutsu kentan kierrokselle; muuten mallin saanto, ei is_captain', () => {
		expect(whatIfDefaultCaptain(MODEL, { id: 2, gw: 6 }, 6)).toBe(2);
		expect(whatIfDefaultCaptain(MODEL, { id: 2, gw: 6 }, 7)).toBe(1);
		// B1: kesken kierroksen kutsu koskee seuraavaa kierrosta.
		expect(whatIfDefaultCaptain(MODEL, { id: 1, gw: 7 }, 6)).toBe(2);
		expect(whatIfDefaultCaptain(MODEL, null, 6)).toBe(2);
	});

	it('B1: muokkaamaton kentta kesken kierroksen = vertailu (ero 0)', () => {
		const mc = { id: 1, gw: 7 };
		expect(whatIfInitialCaptain(MODEL, null, mc, 6)).toBe(2);
		expect(modelBaselineXp(MODEL, mc, 6, at(6))).toBe(5 + 6 * 2);
	});

	it('B2: siirron jalkeinen runko ei ole mallin XI', () => {
		expect(isModelLineup(MODEL, [1, 2, 3], [2, 1], 2, 2)).toBe(true);
		expect(isModelLineup(MODEL, [1, 2, 4], [1, 2], 2, 2)).toBe(false);
		expect(isModelLineup(MODEL, [5, 2, 3], [5, 2], 2, 2)).toBe(false);
		expect(isModelLineup(MODEL, [1, 2, 3], [1, 2], 1, 2)).toBe(false);
	});

	it('tallennettu oma kapteeni voittaa, jos rungossa', () => {
		expect(whatIfInitialCaptain(MODEL, 3, { id: 2, gw: 6 }, 6)).toBe(3);
		expect(whatIfInitialCaptain(MODEL, 99, { id: 2, gw: 6 }, 6)).toBe(2);
	});

	it('KUTSUPAIKKA: TeamPitchManager ja RateTeam', () => {
		const src = readFileSync(resolve(__dirname, 'components/TeamPitchManager.svelte'), 'utf8');
		expect(src).toMatch(/whatIfInitialCaptain\(players, savedCap, modelCaptain, defaultGw \?\? null\)/);
		expect(src).toMatch(/modelBaselineXp\(modelPlayers, modelCaptain, selGw \?\? defaultGw \?\? null, xpOf\)/);
		expect(src).not.toMatch(/p\.is_captain\)\?\.id \?\? null\)/);
		expect(src).toMatch(/xP vs the model's XI/);
		expect(src).not.toMatch(/loaded lineup/);
		const rt = readFileSync(resolve(__dirname, 'components/RateTeam.svelte'), 'utf8');
		expect(rt).toMatch(/players=\{plannedPlayers\}\s*modelPlayers=\{data\.team\.players\}/);
		expect(rt).toMatch(/players=\{dataB\.team\.players\}\s*modelPlayers=\{dataB\.team\.players\}/);
		const lib = readFileSync(resolve(__dirname, 'whatIfStart.ts'), 'utf8').replace(/\/\*[\s\S]*?\*\/|\/\/.*$/gm, '');
		expect(lib).not.toMatch(/\.is_captain\b/);
	});
});
