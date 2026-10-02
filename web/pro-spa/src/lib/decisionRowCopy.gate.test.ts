// $lib/decisionRowCopy.gate.test.ts - 2.10 kuvakatselmus + julkaisutarkistaja.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { ownedWatchText, transferCostText, transferWhy } from './decisionRowCopy';

const read = (rel: string) => readFileSync(new URL(rel, import.meta.url), 'utf8');

describe('decisionRowCopy', () => {
	it('hinta hintaerona, ei etumerkkia eika pankkivaitetta', () => {
		expect(transferCostText(-0.2)).toBe('£0.2m cheaper');
		expect(transferCostText(0.3)).toBe('£0.3m more expensive');
		expect(transferCostText(-0.04)).toBe('same price');
		expect(transferWhy(5.97, -0.2)).toBe('+6.0 xP over the horizon, £0.2m cheaper.');
		expect(transferWhy(5.97, -0.2)).not.toMatch(/frees|-0\.2m cost/);
	});
	it('"more" vain kun jotain on ennen sita', () => {
		expect(ownedWatchText(3, 0)).toBe('3 of your players on watch');
		expect(ownedWatchText(3, 1)).toBe('3 more on watch');
	});
	it('kutsupaikat kayttavat lukijaa', () => {
		const rt = read('./components/RateTeam.svelte');
		expect(rt).toMatch(/rationale: transferWhy\(sug\.delta_xp_horizon, sug\.delta_cost\)/);
		expect(rt).not.toMatch(/m cost\.`/);
		const pw = read('./components/PriceWatch.svelte');
		expect(pw).toMatch(/ownedWatchText\(rest, parts\.length\)/);
		expect(pw).not.toMatch(/more on watch`/);
	});
});
