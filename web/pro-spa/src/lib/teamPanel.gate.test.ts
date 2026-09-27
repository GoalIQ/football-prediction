/**
 * Portti: PRO-JOUKKUENAKYMA (Villen paatos 27.9.2026).
 *
 * Syotteen muoto mitattu 27.9 tuotannosta:
 *   GET /api/fantasy     teams[] = {name, short, next_avg_cs_pct, fixtures[]},
 *                        fixture = {gw, opponent, opponent_short, venue, fdr,
 *                        tier: 'near'|'far', cs_pct (vain near)}; meta
 *                        next_gameweek 6, deadline_gameweek 6, far_basis_label
 *   GET /api/fantasy/xp  (ilman tokenia) meta.masked = true, top 10 / 483;
 *                        players[] = {id, web_name, team, team_short, pos,
 *                        price, p_start, predicted_starts, xp_horizon_total}
 */
import { describe, expect, it } from 'vitest';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { FantasyResponse, XpResponse } from './api';
import { CLUB_SLUGS, clubPageUrl, teamPanel, teamParam } from './teamPanel';
import { teamsCsGrid } from './weekRows';

const REPO = resolve(__dirname, '../../../..');
const code = (rel: string) => readFileSync(resolve(__dirname, rel), 'utf8');

function fx(gw: number, opp: string, venue: string, cs?: number, tier: 'near' | 'far' = 'near') {
	return {
		gw,
		opponent: `${opp} FC`,
		opponent_short: opp,
		venue,
		fdr: 2,
		tier,
		...(cs == null ? {} : { cs_pct: cs })
	};
}

/** `next`/`deadline`: kierrosvaihe. Kesken kierroksen next < deadline. */
function fantasy(next: number, deadline: number): FantasyResponse {
	return {
		meta: {
			available: true,
			next_gameweek: next,
			deadline_gameweek: deadline,
			far_basis_label: 'Fixture difficulty only.'
		},
		teams: [
			{
				name: 'Arsenal',
				short: 'ARS',
				next_avg_cs_pct: 40,
				next_avg_fdr: 2,
				fixtures: [
					fx(5, 'LEE', 'H', 60),
					fx(6, 'LEE', 'H', 46.5),
					fx(7, 'NFO', 'A', 49.9),
					fx(9, 'CHE', 'H', 30),
					fx(9, 'BOU', 'A', 41),
					fx(10, 'NEW', 'A', undefined, 'far'),
					// Kaukorivi jolla on silti luku: tier ratkaisee, ei kentan olemassaolo.
					fx(11, 'SUN', 'H', 30, 'far')
				]
			},
			{
				name: 'Leeds',
				short: 'LEE',
				next_avg_cs_pct: 20,
				next_avg_fdr: 4,
				fixtures: [fx(6, 'ARS', 'A', 18.2)]
			}
		]
	} as unknown as FantasyResponse;
}

function xp(masked: boolean): XpResponse {
	const p = (id: number, team: string, total: number, extra = {}) => ({
		id,
		web_name: `P${id}`,
		team: team === 'ARS' ? 'Arsenal' : 'Leeds',
		team_short: team,
		pos: 'MID',
		price: 6.5,
		p_start: 0.915,
		predicted_starts: 91.5,
		xp_horizon_total: total,
		gameweeks: [],
		...extra
	});
	return {
		meta: {
			available: true,
			masked,
			horizon_gw: 6,
			horizon_total_from: 6,
			horizon_total_gw: 6,
			next_gameweek: 6
		},
		players: [p(1, 'ARS', 20.1), p(2, 'LEE', 30), p(3, 'ARS', 25.4), p(4, 'ARS', 3, { p_start: undefined })]
	} as unknown as XpResponse;
}

describe('teamPanel', () => {
	it('ottelut deadline-kierroksesta; tuplakierros, tyhja kierros, kaukorivi ilman lukua', () => {
		const t = teamPanel(fantasy(6, 6), xp(false), 'ARS')!;
		expect(t.fixtures.map((g) => g.gw)).toEqual([6, 7, 8, 9, 10, 11]);
		expect(t.fixtures[0].items).toEqual([
			{ gw: 6, opponent: 'LEE', opponentName: 'LEE FC', venue: 'H', cs: 46.5 }
		]);
		expect(t.fixtures[2].items).toEqual([]);
		expect(t.fixtures[3].items.map((f) => f.opponent)).toEqual(['CHE', 'BOU']);
		expect(t.fixtures[4].items[0].cs).toBeNull();
		expect(t.fixtures[5].items[0].cs).toBeNull();
		// Ikkuna ei jatku viimeisen ottelun yli (maxGws 8 -> silti GW11 asti).
		expect(teamPanel(fantasy(6, 6), null, 'ARS', 8)!.fixtures.at(-1)!.gw).toBe(11);
		// Kaikki ottelut ennen deadline-kierrosta -> ei riveja.
		expect(teamPanel(fantasy(12, 12), null, 'ARS')!.fixtures).toEqual([]);
		// Keskiarvon vali = Teams-ruudukon sarakkeet (vain CS%:lliset lahirivit).
		expect(t.avgRange).toBe('GW6-GW9');
	});

	it('kesken kierroksen alkanut kierros ei nay (next 5, deadline 6)', () => {
		const t = teamPanel(fantasy(5, 6), xp(false), 'ARS')!;
		expect(t.fixtures[0].gw).toBe(6);
		expect(t.fixtures.flatMap((g) => g.items).some((f) => f.gw === 5)).toBe(false);
	});

	it('CS-keskiarvo ilman lukua -> ei valia', () => {
		const f = fantasy(6, 6);
		(f.teams[1] as { fixtures: unknown[] }).fixtures = [];
		const t = teamPanel(f, null, 'LEE')!;
		expect(t.avgCs).toBeNull();
		expect(t.avgRange).toBeNull();
		expect(t.fixtures).toEqual([]);
	});

	it('CS-keskiarvo on sama luku kuin Teams-nakymassa', () => {
		for (const [n, d] of [
			[6, 6],
			[5, 6]
		] as const) {
			const f = fantasy(n, d);
			const grid = teamsCsGrid(f)!.rows.find((r) => r.team === 'ARS')!;
			expect(teamPanel(f, null, 'ARS')!.avgCs).toBe(grid.avg);
		}
	});

	it('Premium: seuran pelaajat xP-jarjestyksessa, aloitus startPct:sta', () => {
		const t = teamPanel(fantasy(6, 6), xp(false), 'ARS')!;
		expect(t.players!.map((p) => p.id)).toEqual([3, 1, 4]);
		expect(t.players![0].start).toBe(92);
		expect(t.window).toBe('next 6 GWs');
		expect(t.masked).toBe(false);
	});

	it('maskattu (ilmainen) vastaus ei nayta seuran osalistaa', () => {
		const t = teamPanel(fantasy(6, 6), xp(true), 'ARS')!;
		expect(t.players).toBeNull();
		expect(t.masked).toBe(true);
	});

	it('tuntematon tai viime kauden seura ei palauta mitaan', () => {
		expect(teamPanel(fantasy(6, 6), xp(false), 'WOL')).toBeNull();
		expect(teamPanel({ meta: { available: false }, teams: [] } as unknown as FantasyResponse, null, 'ARS')).toBeNull();
		expect(teamPanel(null, null, 'ARS')).toBeNull();
	});

	it('?team= hyvaksyy vain kolmikirjaimisen koodin', () => {
		expect(teamParam('ars')).toBe('ARS');
		expect(teamParam(' MCI ')).toBe('MCI');
		for (const bad of [null, '', 'AR', 'ARSE', 'A1S', '<b>']) expect(teamParam(bad)).toBeNull();
	});
});

describe('klubisivujen sopimus', () => {
	const gen = resolve(REPO, 'scripts/build_fpl_longtail.py');
	it.skipIf(!existsSync(gen))('CLUB_SLUGS on sanatarkasti generaattorin taulu', () => {
		const src = readFileSync(gen, 'utf8');
		const block = src.match(/CLUB_SLUGS = \{([\s\S]*?)\n\}/)?.[1] ?? '';
		const py = Object.fromEntries([...block.matchAll(/"([A-Z]{3})": "([a-z-]+)"/g)].map((m) => [m[1], m[2]]));
		expect(Object.keys(py).length).toBeGreaterThanOrEqual(20);
		expect(CLUB_SLUGS).toEqual(py);
	});
	const dir = resolve(REPO, 'fpl/club');
	it.skipIf(!existsSync(dir))('jokainen julkaistu klubisivu on taulussa', () => {
		const slugs = new Set(Object.values(CLUB_SLUGS));
		const pages = readdirSync(dir).filter((f) => f.endsWith('.html'));
		expect(pages.length).toBeGreaterThanOrEqual(20);
		for (const f of pages) expect(slugs.has(f.replace(/\.html$/, '')), f).toBe(true);
		expect(clubPageUrl('ARS')).toBe('https://goaliq.app/fpl/club/arsenal');
		expect(clubPageUrl('XXX')).toBeNull();
	});
});

describe('KUTSUPAIKAT', () => {
	it('AppShellissa yksi TeamSheet', () => {
		expect(code('./components/AppShell.svelte').match(/<TeamSheet \/>/g)?.length).toBe(1);
	});
	it('seura avaa paneelin kolmesta pinnasta', () => {
		expect(code('./components/PlayerCard.svelte')).toMatch(
			/openTeam\(player\?\.team_short, 'player_card'\)\}\s*>\{player\.team\}<\/button/
		);
		expect(code('./components/TeamsCs.svelte')).toMatch(/onclick=\{\(\) => openTeam\(r\.team, 'teams_cs'\)\}/);
		expect(code('./components/CleanSheets.svelte')).toMatch(
			/onclick=\{\(\) => openTeam\(t\.short \?\? t\.name, 'clean_sheets'\)\}/
		);
	});
	it('paneeli lukee teamPanelin ja avaa pelaajat paneelin paalle', () => {
		const s = code('./components/TeamSheet.svelte');
		expect(s).toMatch(/teamPanel\(fantasy, xp, teamSheet\.short\)/);
		expect(s).toMatch(/<div class="sheet-body" onclick=\{teamPlayerRowClick\}>/);
		expect(s).toMatch(/<tr data-player-id=\{p\.id\}>/);
		expect(s).toMatch(/teamParam\(url\.searchParams\.get\('team'\)\)/);
		expect(s).toMatch(/if \(e\.key === 'Escape' && teamOnTop\(\)\) closeTeam\(\);/);
	});
	it('julkaisutarkistaja 27.9: ei vaikeuslupausta, datakatko ei ole "seuraa ei ole"', () => {
		const s = code('./components/TeamSheet.svelte').replace(/<!--[\s\S]*?-->/g, '');
		expect(s).not.toMatch(/far_basis_label|farLabel/);
		const katko = s.indexOf('{:else if !fantasy.meta?.available}');
		const eiSeuraa = s.indexOf('{:else if !panel}');
		expect(katko).toBeGreaterThan(0);
		expect(katko).toBeLessThan(eiSeuraa);
		expect(s).toMatch(/\{:else if xpFailed\}/);
	});
	it('pelaajakortin Escape ei sulje korttia paneelin alta', () => {
		expect(code('./components/PlayerSheet.svelte')).toMatch(
			/e\.key === 'Escape' && !teamOnTop\(\)\) closePlayer\(\);/
		);
	});
});
