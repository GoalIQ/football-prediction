/** Portti: MP-14 (26.9.2026) oman joukkueen kausi jaadytettya projektiota vastaan.
 *
 * Lause ja luku samasta lukijasta ($lib/ledger), varaumat nakyvissa (puuttuva
 * freeze, provisionaalinen kierros, vajaa kattavuus), ja kutsupaikka nayttaa
 * lohkon vain FPL-entrylle.
 */
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import type { LedgerResponse } from './api';
import { barTooltip, ledgerHeadline, ledgerNotes, ledgerSummary, ledgerView, signed } from './ledger';

// Mitattu tuotannosta 26.9 (entry 895045).
const LIVE: LedgerResponse = {
	meta: { available: true, graded_gws: 5, missing_freeze_gws: [], provisional_gws: [], note: null },
	totals: { projected: 288.18, actual: 468, diff: 179.82, fpl_average: 299 },
	gameweeks: [
		{ gw: 1, projected: 56.8, actual: 97, diff: 40.2, cumulative_diff: 40.2, players_matched: 15, bench_points: 0, transfer_cost: 0, provisional: false },
		{ gw: 2, projected: 49.44, actual: 119, diff: 69.56, cumulative_diff: 109.76, players_matched: 15, bench_points: 7, transfer_cost: 0, provisional: false },
		{ gw: 3, projected: 71.07, actual: 90, diff: 18.93, cumulative_diff: 128.69, players_matched: 15, bench_points: 11, transfer_cost: 0, provisional: false },
		{ gw: 4, projected: 52.75, actual: 99, diff: 46.25, cumulative_diff: 174.94, players_matched: 15, bench_points: 3, transfer_cost: 0, provisional: false },
		{ gw: 5, projected: 58.12, actual: 63, diff: 4.88, cumulative_diff: 179.82, players_matched: 15, bench_points: 5, transfer_cost: 0, provisional: false }
	]
};

describe('ledgerView: yksi lukija luvulle, lauseelle ja pylvaille', () => {
	it('elava vastaus: summat, erotus ja kierrosmaara samasta nakymasta', () => {
		const v = ledgerView(LIVE)!;
		expect(ledgerSummary(v)).toBe('+179.8 vs the projection, +169 vs the FPL average, over 5 gameweeks');
		expect(ledgerHeadline(v)).toBe(
			'You scored 468 over these gameweeks. The projection said 288.2, and the FPL average was 299.'
		);
		expect(v.bars.map((b) => b.gw)).toEqual([1, 2, 3, 4, 5]);
		expect(v.maxAbs).toBeCloseTo(69.56);
		expect(ledgerNotes(v)).toEqual([]);
	});

	it('alle projektion: miinusmerkki, ei plussaa', () => {
		const v = ledgerView({
			...LIVE,
			totals: { projected: 60, actual: 48, diff: -12 },
			gameweeks: [{ ...LIVE.gameweeks[0], projected: 60, actual: 48, diff: -12, cumulative_diff: -12 }]
		})!;
		expect(ledgerSummary(v)).toBe('48 points over 1 gameweek against a projection of 60.0');
		expect(signed(0)).toBe('0.0');
	});

	it('varaumat: puuttuva freeze, provisionaalinen ja vajaa kattavuus kerrotaan', () => {
		const v = ledgerView({
			...LIVE,
			meta: { ...LIVE.meta, missing_freeze_gws: [3, 1], provisional_gws: [4, 5], in_progress_gws: [6] },
			gameweeks: [
				{ ...LIVE.gameweeks[1], players_matched: 14 },
				{ ...LIVE.gameweeks[3], provisional: true, state: 'awaiting_check' },
				{ ...LIVE.gameweeks[4], provisional: true, state: 'unknown' }
			]
		})!;
		expect(ledgerNotes(v)).toEqual([
			"Not included: GW1, GW3, because we couldn't pair a frozen projection with your picks.",
			"GW6 is still being played, so it isn't included yet.",
			'GW4: played but not confirmed, so bonus points can still change these totals.',
			'GW5: not confirmed yet, so these totals can still move.',
			'GW2: 14 of your 15 had a frozen projection.'
		]);
		expect(barTooltip(v.bars[2])).toBe('GW5: projected 58.1, scored 63, +4.9 (provisional)');
		expect(barTooltip(v.bars[0])).toBe('GW2: projected 49.4, scored 119, +69.6');
	});

	it('k2 C2: keskiarvon alla oleva nakee miinuksen jo kiinni olevalla rivilla', () => {
		// Mitattu 26.9 entry 12345: 268 / 225.32 / FPL-keskiarvo 299.
		const v = ledgerView({ ...LIVE, totals: { projected: 225.32, actual: 268, diff: 42.68, fpl_average: 299 } })!;
		expect(ledgerSummary(v)).toBe('+42.7 vs the projection, -31 vs the FPL average, over 5 gameweeks');
	});

	it('keskiarvo puuttuu -> lause ilman vertailua (ei osittaista summaa)', () => {
		const v = ledgerView({ ...LIVE, totals: { ...LIVE.totals, fpl_average: null } })!;
		expect(ledgerHeadline(v)).toBe('You scored 468 over these gameweeks. The projection said 288.2.');
		expect(ledgerSummary(v)).toBe('468 points over 5 gameweeks against a projection of 288.2');
	});

	it('ei dataa tai ei saatavilla -> ei lohkoa (ei nollaa)', () => {
		expect(ledgerView(null)).toBeNull();
		expect(ledgerView({ ...LIVE, meta: { ...LIVE.meta, available: false } })).toBeNull();
		expect(ledgerView({ ...LIVE, gameweeks: [] })).toBeNull();
		expect(ledgerView({ ...LIVE, totals: { projected: null, actual: null, diff: null } })).toBeNull();
	});
});

describe('kutsupaikat', () => {
	const read = (f: string) => readFileSync(new URL(`./components/${f}`, import.meta.url), 'utf-8');
	it('RateTeam nayttaa lohkon vain FPL-entrylle', () => {
		const src = read('RateTeam.svelte');
		expect(src).toMatch(
			/<SeasonLedger entry=\{data\.meta\.mode === 'entry' \? \(data\.meta\.entry \?\? null\) : null\} \/>/
		);
	});
	it('SeasonLedger ei muotoile lukuja itse (lause ja luku samasta lukijasta)', () => {
		const src = read('SeasonLedger.svelte').replace(/<!--[\s\S]*?-->/g, '');
		expect(src).toMatch(/\{ledgerSummary\(view\)\}/);
		expect(src).toMatch(/\{ledgerHeadline\(view\)\}/);
		expect(src).toMatch(/fetchMyTeamLedger\(/);
		expect(src).not.toMatch(/totals\.(diff|actual|projected)/);
	});
});
