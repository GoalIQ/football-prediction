import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { PAYWALL_TOP } from './paywallBullets';

/**
 * PORTTI (ulkoasu WP8 / B2 + copy-sync, 2.11.2026):
 *   1. maksumuuri nayttaa 3-5 hyotya ennen avausta (auditoinnin B2)
 *   2. lista on YKSI (Paywall lukee sen, ei kirjoita omaa)
 *   3. mikaan Premium-pinta ei myy oman XI:n kapteenia: se on ilmainen 1.11
 *      alkaen (fp api/premium.py RATE_TEAM_FREE_OPEN, live #77)
 */
const C = resolve(__dirname, 'components');
const read = (f: string) => readFileSync(resolve(C, f), 'utf-8').replace(/\r\n/g, '\n');

describe('paywall: lyhyt lista', () => {
	it('3-5 hyotya, ei tyhjia, ei em/en dashia eika hintoja', () => {
		expect(PAYWALL_TOP.length).toBeGreaterThanOrEqual(3);
		expect(PAYWALL_TOP.length).toBeLessThanOrEqual(5);
		for (const b of PAYWALL_TOP) {
			expect(b.trim().length).toBeGreaterThan(20);
			expect(b).not.toMatch(/[–—]/);
			expect(b).not.toMatch(/[€£$]|\d+[.,]\d\d/);
		}
	});

	it('Paywall piirtaa listan lukijalta ja pitkat kappaleet ovat avauksen takana', () => {
		const src = read('Paywall.svelte');
		expect(src).toMatch(/\{#each PAYWALL_TOP as b/);
		const det = src.indexOf('<details class="all-features">');
		const fpl = src.indexOf('<strong>FPL:</strong>');
		const end = src.indexOf('</details>');
		expect(det).toBeGreaterThan(0);
		expect(fpl).toBeGreaterThan(det);
		expect(end).toBeGreaterThan(fpl);
	});
});

describe('copy-sync: oman XI:n kapteeni ei ole Premium-lupaus', () => {
	const PROMISES = [
		/captain pick for your own/i,
		/captain pick for your squad/i,
		/captain for your XI/i,
		/Captain pick for your own XI/
	];
	it('hyotylista ei lupaa kapteenia', () => {
		for (const b of PAYWALL_TOP) expect(b).not.toMatch(/captain/i);
	});
	for (const f of ['Paywall.svelte', 'PremiumPreview.svelte', 'ProductIntro.svelte']) {
		it(`${f} ei myy kapteenia Premiumina`, () => {
			const src = read(f);
			for (const re of PROMISES) expect(src, `${f}: ${re}`).not.toMatch(re);
		});
	}
});
