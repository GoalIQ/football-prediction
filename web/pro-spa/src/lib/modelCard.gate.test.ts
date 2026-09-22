/**
 * Portti: This weekin "The model's captain" lukee MALLIN joukkueen, ei
 * optimoijan vapaata runkoa (22.9.2026, julkaisutarkistaja B1).
 *
 * 🔴 MITATTU 22.9: ensimmainen versio haki /api/fantasy/model-squadin
 * (optimoijan runko, optimal_proven false) ja otsikoi sen kapteenin
 * "The model's captain". goaliq.app/fpl kertoo julkisesti etta mallin runko
 * jaadytetaan ennen jokaista deadlinea ja pelataan FPL:ssa entryna 116920;
 * optimoijan ja entryn rungoissa oli vain 8/15 samaa pelaajaa. Kortti olisi
 * siis nimennyt julkisesti kapteenin jota malli ei pelaa.
 *
 * Vaitteet:
 *   1. lukija `modelEntryId` antaa model-racen entry_seriesin id:n tai null,
 *      eika mitaan muuta (ei oletus-id:ta),
 *   2. kortin polku on rate-team mallin entrylle (`modelCardPath`),
 *   3. hakufunktio ja This week eivat koske model-squadiin, ja This week
 *      kysyy id:n lukijalta.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import type { ModelRaceResponse } from './api';
import { blankComments } from './sourceScan';
import { modelCardPath, modelEntryId } from './weekRows';

const read = (rel: string) =>
	blankComments(readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')).replace(
		/\r\n/g,
		'\n'
	);

/** `export function fetchModelEntryCard ... }` -runko. */
function fnBody(src: string, name: string): string {
	const a = src.indexOf(`export function ${name}`);
	if (a === -1) return '';
	const b = src.indexOf('\n}\n', a);
	return src.slice(a, b === -1 ? undefined : b + 2);
}

function modelCardProblems(fantasySrc: string, weekSrc: string): string[] {
	const p: string[] = [];
	const body = fnBody(fantasySrc, 'fetchModelEntryCard');
	if (!body) p.push('fetchModelEntryCard puuttuu');
	if (!body.includes('modelCardPath(')) p.push('fetchModelEntryCard ei kayta modelCardPath-lukijaa');
	if (/model-squad|fetchModelSquad/.test(body)) p.push('fetchModelEntryCard lukee model-squadia');
	if (/model-squad|fetchModelSquad|fetchModelCard\(/.test(weekSrc))
		p.push('ThisWeek lukee model-squadia tai vanhaa fetchModelCardia');
	if (!/fetchModelEntryCard\(id\)/.test(weekSrc)) p.push('ThisWeek ei hae mallin entryn korttia');
	if (!/modelEntryId\(race\)/.test(weekSrc)) p.push('ThisWeek ei kysy entryn id:ta lukijalta');
	return p;
}

const race = (entry_series: unknown) =>
	({ meta: { available: true }, totals: {}, gameweeks: [], entry_series }) as unknown as ModelRaceResponse;

describe('mallin kortti = mallin oma FPL-entry', () => {
	it('lukija: entry_seriesin id tai null, ei oletusta', () => {
		expect(modelEntryId(race({ entry_id: 116920, gameweeks: [] }))).toBe(116920);
		expect(modelEntryId(race(null))).toBeNull();
		expect(modelEntryId(race({ entry_id: null }))).toBeNull();
		expect(modelEntryId(race({ entry_id: 0 }))).toBeNull();
		expect(modelEntryId(race({ entry_id: 1.5 }))).toBeNull();
		expect(modelEntryId(null)).toBeNull();
	});

	it('polku on rate-team mallin entrylle', () => {
		expect(modelCardPath(116920)).toBe('/api/fantasy/rate-team?entry=116920');
	});

	it('lahde: hakufunktio ja This week eivat lue model-squadia', () => {
		expect(modelCardProblems(read('./fantasyTools.ts'), read('./components/ThisWeek.svelte'))).toEqual([]);
	});

	it('erotteleva kontrolli: 22.9:n ensimmainen versio (model-squad) kaatuu', () => {
		const old = `export function fetchModelEntryCard(entryId: number) {
	const squad = await getTool('/api/fantasy/model-squad', 'model_squad', false);
	return getTool(\`/api/fantasy/rate-team?players=\${ids}\`, 'rate_team_draft', false);
}
`;
		const problems = modelCardProblems(old, read('./components/ThisWeek.svelte'));
		expect(problems).toContain('fetchModelEntryCard lukee model-squadia');
		expect(problems).toContain('fetchModelEntryCard ei kayta modelCardPath-lukijaa');
		const oldWeek = read('./components/ThisWeek.svelte').replace('fetchModelEntryCard(id)', 'fetchModelCard()');
		expect(modelCardProblems(read('./fantasyTools.ts'), oldWeek).length).toBeGreaterThan(0);
	});
});
