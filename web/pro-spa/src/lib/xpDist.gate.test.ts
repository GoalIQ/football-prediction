/**
 * Portti: kortin kattolause ei tormaa "10 or more points" -lukuun (29.9.2026).
 * Ks. $lib/xpDist. Testi mittaa saannon kaikilla p90:n vaiheilla (alle, tasan,
 * yli rajan) ja KUTSUPAIKAN: PlayerCard kayttaa samaa lukijaa.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { HAUL_POINTS, showCeiling } from './xpDist';
import { blankComments } from './sourceScan';

describe('showCeiling', () => {
	it('tasan pisterajalla lause jaa pois (P(>=raja) on silloin aina yli 10 %)', () => {
		expect(showCeiling(HAUL_POINTS)).toBe(false);
	});
	it('muilla arvoilla lause naytetaan', () => {
		expect(showCeiling(HAUL_POINTS - 1)).toBe(true);
		expect(showCeiling(HAUL_POINTS + 1)).toBe(true);
		expect(showCeiling(6)).toBe(true);
	});
	it('puuttuva luku ei nayta lausetta', () => {
		expect(showCeiling(undefined)).toBe(false);
		expect(showCeiling(null)).toBe(false);
		expect(showCeiling(Number.NaN)).toBe(false);
	});
});

describe('PlayerCard kayttaa lukijaa', () => {
	const src = blankComments(
		readFileSync(fileURLToPath(new URL('./components/PlayerCard.svelte', import.meta.url)), 'utf8')
	);
	it('kattolause on showCeiling-ehdon sisalla', () => {
		const i = src.indexOf('showCeiling(player.xp_dist.p90)');
		const j = src.indexOf('He goes past');
		expect(i).toBeGreaterThan(0);
		expect(j).toBeGreaterThan(i);
		expect(src.indexOf('{/if}', i)).toBeGreaterThan(j);
	});
	it('pisteraja tulee vakiosta, ei kovakoodista', () => {
		expect(src).toContain('{HAUL_POINTS} or more points');
	});
});
