/** Portti: HTML-titlen muoto "X | GoalIQ" ei saa nakya sivulla tekstina
 *  (WP2, 1.11.2026).
 *
 * 🔴 MIKSI. This weekin footerissa kortin otsikko oli "Beat the Model |
 * GoalIQ". Se on miniliigan nimi FPL:ssa, mutta kortin otsikkona se luki
 * vuotaneena <title>-merkkijonona. Title-muoto kuuluu vain <title>-tagiin ja
 * routeHeads/tools.ts-otsikoihin, jotka menevat <svelte:head>iin.
 *
 * Portti lukee jokaisen .svelte-tiedoston MARKUPIN: script-, style- ja
 * svelte:head-lohkot seka kommentit pois, ja jaljelle jaavasta tekstista
 * haetaan " | GoalIQ".
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = resolve(__dirname, '..');
const LEAK = /\|\s*GoalIQ\b/;

function files(dir: string): string[] {
	return readdirSync(dir).flatMap((n) => {
		const p = join(dir, n);
		if (statSync(p).isDirectory()) return files(p);
		return n.endsWith('.svelte') ? [p] : [];
	});
}

function markup(src: string): string {
	return src
		.replace(/<script[\s\S]*?<\/script>/g, '')
		.replace(/<style[\s\S]*?<\/style>/g, '')
		.replace(/<svelte:head>[\s\S]*?<\/svelte:head>/g, '')
		.replace(/<!--[\s\S]*?-->/g, '');
}

describe('title-muoto ei vuoda sivun tekstiin', () => {
	it('mikaan komponentti ei nayta "| GoalIQ" -tekstia markupissa', () => {
		const osumat: string[] = [];
		for (const f of files(SRC)) {
			const m = markup(readFileSync(f, 'utf-8'));
			m.split('\n').forEach((l, i) => {
				if (LEAK.test(l)) osumat.push(`${relative(SRC, f)}: ${l.trim()}`);
			});
		}
		expect(osumat).toEqual([]);
	});

	it('negatiivinen kontrolli: vanha LeagueBanner-otsikko osuu, <title> ei', () => {
		expect(LEAK.test(markup('<strong>Beat the Model | GoalIQ</strong>'))).toBe(true);
		expect(
			LEAK.test(markup('<svelte:head><title>Creator dashboard | GoalIQ</title></svelte:head>'))
		).toBe(false);
		expect(LEAK.test(markup("<script>const t = 'X | GoalIQ';</script><p>ok</p>"))).toBe(false);
	});
});
