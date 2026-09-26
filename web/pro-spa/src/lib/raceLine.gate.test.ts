/** Portti: MP-14 toinen puolisko (26.9.2026), Season racen kumulatiivinen eroviiva.
 *
 * Kaavio on vaite: viivalla vain vertaillut kierrokset, puuttuva kierros on
 * katko (ei interpoloitu janaa), viimeinen piste on tasan kortin lauseen luku,
 * eika mikaan piste putoa piirtoalueen ulkopuolelle hiljaa.
 */
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import type { ModelRaceGameweek, ModelRaceResponse } from './api';
import { pointTooltip, raceLineGeometry, raceLineView, RACE_LINE_PAD } from './raceLine';

const row = (gw: number, model: number, you: number, cum: number, extra: Partial<ModelRaceGameweek> = {}): ModelRaceGameweek => ({
	gw,
	model_points: model,
	fpl_average: 50,
	provisional: false,
	state: 'final',
	stale_model_points: false,
	model_cost_verified: true,
	your_points: you,
	diff: you - model,
	cumulative_diff: cum,
	...extra
});

// Mitattu tuotannosta 26.9 (entry 895045): GW4 ei ole kisassa (ei kelvollista freezea).
const LIVE = {
	meta: { available: true, graded_gws: 4, compared_gws: 4, masked: true, model_plays_chips: false, note: null },
	totals: { model: 208, you: 369, diff: 161 },
	gameweeks: [row(1, 41, 97, 56), row(2, 61, 119, 114), row(3, 63, 90, 141), row(5, 43, 63, 161)]
} as unknown as ModelRaceResponse;

const W = 320;
const H = 120;

describe('raceLineView: viivalla vain se mika on kisassa', () => {
	it('elava vastaus: neljä pistettä, GW4 on katko eika jana', () => {
		const v = raceLineView(LIVE)!;
		expect(v.points.map((p) => [p.gw, p.cum])).toEqual([
			[1, 56],
			[2, 114],
			[3, 141],
			[5, 161]
		]);
		expect(v.hasGap).toBe(true);
		const g = raceLineGeometry(v, W, H);
		// Janat 1-2 ja 2-3; ei 3-5 (kalteva jana vaittaisi GW4:n muuttaneen eroa).
		expect(g.segments).toHaveLength(2);
		expect(g.segments.map((s) => [s.x1, s.x2])).toEqual([
			[g.markers[0].cx, g.markers[1].cx],
			[g.markers[1].cx, g.markers[2].cx]
		]);
		// x on kierroksen numero: GW3 -> GW5 on kaksi kierrosvalia.
		const d1 = g.markers[1].cx - g.markers[0].cx;
		expect(g.markers[3].cx - g.markers[2].cx).toBeCloseTo(2 * d1);
		expect(g.endLabel.text).toBe('+161');
		expect(g.zeroLabel).not.toBeNull();
		expect(g.zeroLabel!.y).toBeCloseTo(g.zero + 3);
		expect(g.ticks.map((t) => t.gw)).toEqual([1, 2, 3, 4, 5]);
	});

	it('viimeinen piste eri kuin kortin lause -> ei kaaviota', () => {
		expect(raceLineView({ ...LIVE, totals: { ...LIVE.totals, diff: 160 } })).toBeNull();
	});

	it('vertailun ulkopuolinen rivi (stale / oma luku puuttuu) ei ole viivalla nollana', () => {
		const v = raceLineView({
			...LIVE,
			gameweeks: [
				row(1, 41, 97, 56),
				row(2, 61, 119, 114),
				row(3, 63, 90, 141, { model_points: null, stale_model_points: true, diff: null, cumulative_diff: null }),
				row(4, 50, 70, 134)
			],
			totals: { ...LIVE.totals, diff: 134 }
		} as ModelRaceResponse)!;
		expect(v.points.map((p) => p.gw)).toEqual([1, 2, 4]);
		expect(v.hasGap).toBe(true);
		expect(raceLineGeometry(v, W, H).segments).toHaveLength(1);
	});

	it('ei entrya, yksi piste tai ei saatavilla -> ei kaaviota', () => {
		expect(raceLineView(null)).toBeNull();
		expect(raceLineView({ ...LIVE, totals: { model: 208, you: null, diff: null } } as ModelRaceResponse)).toBeNull();
		expect(raceLineView({ ...LIVE, gameweeks: [row(1, 41, 97, 56)], totals: { ...LIVE.totals, diff: 56 } })).toBeNull();
		expect(raceLineView({ ...LIVE, meta: { ...LIVE.meta, available: false } })).toBeNull();
	});
});

describe('raceLineGeometry: nolla aina asteikolla, mikaan piste ei leikkaudu', () => {
	it('malli edella: pisteet nollaviivan alla, nolla piirtoalueen sisalla', () => {
		const v = raceLineView({
			...LIVE,
			gameweeks: [row(1, 60, 50, -10), row(2, 70, 40, -40), row(3, 50, 65, -25)],
			totals: { ...LIVE.totals, diff: -25 }
		})!;
		const g = raceLineGeometry(v, W, H);
		for (const m of g.markers) expect(m.cy).toBeGreaterThan(g.zero);
		expect(g.zero).toBeCloseTo(RACE_LINE_PAD.top);
		expect(g.endLabel.text).toBe('-25');
		// Loppupiste lahella nollaa -> "0" jaa pois ettei se osu loppuluvun paalle.
		const near = raceLineView({
			...LIVE,
			gameweeks: [row(1, 60, 20, -40), row(2, 40, 41, -39), row(3, 50, 88, -1)],
			totals: { ...LIVE.totals, diff: -1 }
		})!;
		expect(raceLineGeometry(near, W, H).zeroLabel).toBeNull();
	});

	it('kaikki pisteet ja nolla piirtoalueen sisalla myos ristiin nollan', () => {
		const v = raceLineView({
			...LIVE,
			gameweeks: [row(1, 60, 50, -10), row(2, 40, 90, 40), row(3, 80, 20, -20)],
			totals: { ...LIVE.totals, diff: -20 }
		})!;
		const g = raceLineGeometry(v, W, H);
		const top = RACE_LINE_PAD.top;
		const bottom = H - RACE_LINE_PAD.bottom;
		for (const y of [g.zero, ...g.markers.map((m) => m.cy)]) {
			expect(y).toBeGreaterThanOrEqual(top - 1e-9);
			expect(y).toBeLessThanOrEqual(bottom + 1e-9);
		}
		for (const m of g.markers) {
			expect(m.cx).toBeGreaterThanOrEqual(g.plotLeft);
			expect(m.cx).toBeLessThanOrEqual(g.plotRight);
		}
		// Loppuluku mahtuu viewBoxiin (oikea marginaali varattu sille).
		expect(g.endLabel.x + 4 * 6).toBeLessThanOrEqual(W);
	});

	it('kesken oleva kierros: jana siihen katkoviivana, vihjeessa varaus', () => {
		const v = raceLineView({
			...LIVE,
			gameweeks: [row(1, 41, 97, 56), row(2, 61, 119, 114, { provisional: true, state: 'in_progress' })],
			totals: { ...LIVE.totals, diff: 114 }
		})!;
		const g = raceLineGeometry(v, W, H);
		expect(g.segments.map((s) => s.dashed)).toEqual([true]);
		expect(pointTooltip(v.points[1])).toBe('GW2: you 119, model 61 (+58). Running total +114 (provisional)');
	});

	it('vanha payload ilman state-kenttaa: provisional ratkaisee', () => {
		const v = raceLineView({
			...LIVE,
			gameweeks: [row(1, 41, 97, 56, { state: undefined }), row(2, 61, 119, 114, { state: undefined, provisional: true })],
			totals: { ...LIVE.totals, diff: 114 }
		})!;
		expect(v.points.map((p) => p.state)).toEqual(['final', 'unknown']);
	});

	it('vihje: luvut samasta rivista, todentamaton hitti merkitaan', () => {
		const v = raceLineView(LIVE)!;
		expect(pointTooltip(v.points[3])).toBe('GW5: you 63, model 43 (+20). Running total +161');
		expect(pointTooltip({ ...v.points[0], costVerified: false })).toBe(
			"GW1: you 97, model 41 (+56). Running total +56 (model's hit not verified)"
		);
	});

	it('koko kausi: akselilla harvennetut numerot, viimeinen aina mukana eika paallekkain', () => {
		const rows = Array.from({ length: 38 }, (_, i) => row(i + 1, 50, 52, 2 * (i + 1)));
		const v = raceLineView({ ...LIVE, gameweeks: rows, totals: { ...LIVE.totals, diff: 76 } })!;
		const g = raceLineGeometry(v, W, H);
		expect(g.ticks[0].gw).toBe(1);
		expect(g.ticks[g.ticks.length - 1].gw).toBe(38);
		expect(g.ticks.length).toBeLessThanOrEqual(11);
		for (let i = 1; i < g.ticks.length; i++) expect(g.ticks[i].x - g.ticks[i - 1].x).toBeGreaterThanOrEqual(12);
		expect(g.segments).toHaveLength(37);
	});
});

describe('kutsupaikka', () => {
	const src = readFileSync(new URL('./components/SeasonRace.svelte', import.meta.url), 'utf-8').replace(
		/<!--[\s\S]*?-->/g,
		''
	);
	it('SeasonRace piirtaa viivan yhdesta lukijasta, ei omaa laskentaa', () => {
		expect(src).toMatch(/let line = \$derived\(raceLineView\(data\)\);/);
		expect(src).toMatch(/raceLineGeometry\(line, LW, LH\)/);
		expect(src).toMatch(/\{#each lineGeom\.segments as sg/);
		expect(src).toMatch(/\{#each lineGeom\.markers as m/);
		expect(src).toMatch(/aria-label=\{RACE_LINE_ARIA\}/);
		expect(src).not.toMatch(/cumulative_diff/);
	});
	it('selite nakyvana tekstina, katkon selitys vain kun katko on', () => {
		expect(src).toMatch(/\{RACE_LINE_CAPTION\}/);
		expect(src).toMatch(/\{#if line\.hasGap\}\s*<p[^>]*>\{RACE_LINE_GAP\}<\/p>/);
	});
});
