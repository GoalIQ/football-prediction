import { describe, expect, it } from 'vitest';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Portti (7.11.2026, Villen paatos): vanhasta projektiosta ei tehda jaettavaa
 * kuvaa. Jokainen jakopainike on `modelAge.stale`-ehdon takana. Uusi painike
 * ilman ehtoa kaataa testin, ellei se ole poikkeuslistalla perusteluineen.
 */
const DIR = join(fileURLToPath(new URL('.', import.meta.url)), 'components');
const strip = (s: string) => s.replace(/<!--[\s\S]*?-->/g, '');

/** Kortit jotka eivat ole projektiosta. Perustelu pakollinen. */
const POIKKEUKSET: Record<string, string> = {};

function shareButtons(src: string): { line: number; guarded: boolean }[] {
	const lines = strip(src).split('\n');
	const out: { line: number; guarded: boolean }[] = [];
	lines.forEach((l, i) => {
		if (!/<button[^>]*onclick=\{shareImage\}/.test(l)) return;
		const before = lines.slice(Math.max(0, i - 3), i).join('\n');
		out.push({ line: i + 1, guarded: /\{#if !modelAge\.stale\}/.test(before) });
	});
	return out;
}

describe('jakopainikkeet vanhalla projektiolla', () => {
	const files = readdirSync(DIR).filter((f) => f.endsWith('.svelte'));
	const withShare = files.filter((f) =>
		/onclick=\{shareImage\}/.test(readFileSync(join(DIR, f), 'utf-8'))
	);

	it('portti loytaa painikkeet (tyhja portti lapaisisi aina)', () => {
		expect(withShare.sort()).toEqual(
			['CaptainRanker.svelte', 'ComparePlayers.svelte', 'TeamPitchManager.svelte'].sort()
		);
	});

	it('jokainen jakopainike on modelAge.stale-ehdon takana', () => {
		const bad = withShare.flatMap((f) =>
			POIKKEUKSET[f]
				? []
				: shareButtons(readFileSync(join(DIR, f), 'utf-8'))
						.filter((b) => !b.guarded)
						.map((b) => `${f}:${b.line}`)
		);
		expect(bad).toEqual([]);
	});

	it('erotteleva fikstuuri: ehdoton painike kaatuu', () => {
		const src = '<div>\n<button type="button" onclick={shareImage}>Share</button>\n</div>';
		expect(shareButtons(src)).toEqual([{ line: 2, guarded: false }]);
	});

	it('komponentti tuo lukijan', () => {
		for (const f of withShare) {
			expect(readFileSync(join(DIR, f), 'utf-8')).toContain(
				"import { modelAge } from '$lib/modelAge.svelte';"
			);
		}
	});
});
