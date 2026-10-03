/**
 * 3.10.2026: UCL Fantasy lopetettu (Villen paatos).
 * Portti: /ucl on pelkka ilmoitus (ei API-kutsua), eika mikaan pinta
 * mainosta UCL Fantasya tai linkita sen nakymiin. Backendin vastine:
 * tests/test_no_uefa_fetch.py.
 */
import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import { GAMES } from './tools';
import { UCL_HEAD } from './routeHeads';

const SRC = fileURLToPath(new URL('..', import.meta.url));

function lahteet(dir: string): string[] {
	const out: string[] = [];
	for (const n of readdirSync(dir)) {
		const p = join(dir, n);
		if (statSync(p).isDirectory()) out.push(...lahteet(p));
		else if (/\.(svelte|ts)$/.test(n) && !/\.test\.ts$/.test(n)) out.push(p);
	}
	return out;
}

describe('UCL Fantasy on poistettu', () => {
	it('/ucl ei hae dataa eika lupaa ominaisuuksia', () => {
		const page = readFileSync(join(SRC, 'routes/ucl/+page.svelte'), 'utf-8');
		expect(page).not.toMatch(/fetch\(|from '\$lib\/api'|Paywall|GameViewNav/);
		expect(UCL_HEAD.description).toMatch(/no longer part of GoalIQ/);
	});
	it('pelivalitsimessa ei ole UCL:aa', () => {
		expect(GAMES.map((g) => g.id)).not.toContain('ucl');
	});
	it('mikaan lahde ei linkita UCL-nakymiin eika mainosta UCL Fantasy -dataa', () => {
		const files = lahteet(SRC);
		expect(files.length).toBeGreaterThan(100);
		const osumat = files.filter((f) => {
			const s = readFileSync(f, 'utf-8');
			return /href="\/ucl[#"]|goaliq\.app\/ucl|fetchUclXp|league=ucl/.test(s);
		});
		expect(osumat).toEqual([]);
	});
});
