/** Portti: MP-17 maalit vs xG + pelipaikan keskiarvo (27.9.2026).
 *
 * (1) lukija ei keksi nollia: vanha API ja pelaamaton pelaaja -> null,
 *     rivitoin kierros ei lisaa summaan eika ole "0 maalia",
 * (2) otsikko on pelkat luvut, ei tulkintaa (mekanismin nimeaminen on vaite),
 * (3) geometria: viivan paa on tasan summa, nimilaput eivat peita toisiaan,
 * (4) kutsupaikka: PlayerCard kayttaa komponenttia kerran oikealla datalla ja
 *     Pos avg -sarake lukee backendin kentan eika laske itse.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import type { PlayerStatsGw } from './fantasyTools';
import {
	GOALS_XG_CAPTION,
	goalsXgGeometry,
	goalsXgHeadline,
	goalsXgTooltip,
	goalsXgView
} from './goalsXg';

const LIB = fileURLToPath(new URL('.', import.meta.url));
const read = (p: string) => readFileSync(join(LIB, p), 'utf-8');
const strip = (s: string) => s.replace(/<!--[\s\S]*?-->/g, '');

const row = (gw: number, mins: number | null, g = 0, xg = 0): PlayerStatsGw => ({
	gw,
	pts: mins == null ? null : 2,
	xp_frozen: null,
	mins,
	g: mins == null ? null : g,
	xg: mins == null ? null : xg,
	pos_avg_pts: null
});

describe('goalsXgView', () => {
	it('vanha API ilman kenttia -> null (ei nollaviivaa)', () => {
		expect(goalsXgView([{ gw: 1, pts: 6, xp_frozen: 4 }])).toBeNull();
		expect(goalsXgView([])).toBeNull();
		expect(goalsXgView(null)).toBeNull();
	});

	it('pelaaja jolla ei ole minuutteja -> null', () => {
		expect(goalsXgView([row(1, 0), row(2, null)])).toBeNull();
	});

	it('summat kertyvat, rivitoin kierros ei lisaa mitaan', () => {
		const v = goalsXgView([row(1, 90, 1, 0.45), row(2, null), row(3, 80, 2, 1.1)])!;
		expect(v.points.map((p) => [p.gw, p.cumG, p.cumXg])).toEqual([
			[1, 1, 0.45],
			[2, 1, 0.45],
			[3, 3, 1.55]
		]);
		expect(v.totalG).toBe(3);
		expect(v.totalXg).toBe(1.55);
		expect(goalsXgTooltip(v.points[1])).toBe('GW2: no FPL row (did not feature)');
		expect(goalsXgTooltip(v.points[2])).toBe(
			'GW3: 2 goals from 1.10 xG · season so far 3 goals from 1.6 xG'
		);
	});

	it('viiva ei jatku rivittomiin loppukierroksiin', () => {
		const v = goalsXgView([row(1, 90, 0, 0.2), row(2, 90, 1, 0.3), row(3, null)])!;
		expect(v.toGw).toBe(2);
		expect(v.points).toHaveLength(2);
	});
});

describe('copy', () => {
	it('otsikko on luvut ilman tulkintaa', () => {
		const v = goalsXgView([row(1, 90, 1, 0.45), row(2, 90, 0, 0.1)])!;
		expect(goalsXgHeadline(v)).toBe('1 goal from 0.6 xG, GW1-2');
		const kaikki = goalsXgHeadline(v) + GOALS_XG_CAPTION;
		for (const sana of ['overperform', 'underperform', 'regress', 'lucky', 'unlucky', 'clinical', 'due ']) {
			expect(kaikki.toLowerCase()).not.toContain(sana);
		}
		expect(kaikki).not.toContain(String.fromCharCode(0x2014)); // em dash
	});
});

describe('goalsXgGeometry', () => {
	it('viivan paa on tasan summa ja nimilaput eivat peita toisiaan', () => {
		const v = goalsXgView([row(1, 90, 1, 0.9), row(2, 90, 1, 1.05)])!; // 2 / 1.95
		const g = goalsXgGeometry(v, 320, 120);
		const last = g.markers[g.markers.length - 1];
		expect(last.gy).toBeCloseTo(g.endGoals.y, 6);
		expect(last.xy).toBeCloseTo(g.endXg.y, 6);
		expect(Math.abs(g.labelGoalsY - g.labelXgY)).toBeGreaterThanOrEqual(11 - 1e-9);
		// Maalit >= xG -> maalien lappu ylempana (pienempi y).
		expect(g.labelGoalsY).toBeLessThan(g.labelXgY);
		expect(g.hi).toBe(2);
	});
});

describe('kutsupaikka', () => {
	it('PlayerCard: komponentti kerran statsRow-datalla, Pos avg backendilta', () => {
		const pc = strip(read('components/PlayerCard.svelte'));
		expect(pc.match(/<GoalsXgChart /g)?.length).toBe(1);
		expect(pc).toContain('goalsXgView(statsRow?.goaliq.gws)');
		expect(pc).toContain('<GoalsXgChart view={goalsXg} />');
		// Otsikko PlayerCardin omilla luokilla (scoped CSS ei ulotu lapseen).
		expect(pc).toMatch(/<h4 class="gw-title">\{GOALS_XG_TITLE\} <span class="src">source: FPL<\/span><\/h4>/);
		expect(pc).toContain('g.pos_avg_pts != null ? g.pos_avg_pts.toFixed(1)');
		// Kaavio "Season so far" -osion jalkeen, ei mallinakyman sisalla.
		expect(pc.indexOf('<GoalsXgChart')).toBeGreaterThan(pc.indexOf('Season so far, against his position'));
	});

	it('komponentti ei laske summia itse, legenda + taulukko + katkoviiva', () => {
		const c = strip(read('components/GoalsXgChart.svelte'));
		expect(c).toContain('goalsXgGeometry(view, W, H)');
		expect(c).not.toContain('gw-title');
		expect(c).not.toMatch(/\.reduce\(|\+=/);
		expect(c).toContain('class="legend"');
		expect(c).toContain('Show as a table');
		expect(c).toMatch(/path\.xg\s*\{[^}]*stroke-dasharray/);
	});
});
