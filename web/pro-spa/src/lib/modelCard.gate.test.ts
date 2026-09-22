/**
 * Portti: This weekin "The model's captain" lukee mallin kapteenin YHDESTA
 * palvelimen lukijasta, `/api/fantasy/model-captain` (22.9.2026).
 *
 * 🔴 MITATTU 22.9, kierros 1: ensimmainen versio haki
 * /api/fantasy/model-squadin (optimoijan runko, optimal_proven false) ja
 * otsikoi sen kapteenin "The model's captain". Optimoijan ja mallin entryn
 * rungoissa oli vain 8/15 samaa pelaajaa.
 *
 * 🔴 KIERROS 2 (freeze-ikkuna): korjaus luki `rate-team?entry=116920`, eli
 * FPL:n JULKAISEMAT pickit. Runko jaadytetaan ~29 h ennen deadlinea, mutta
 * FPL julkaisee pickit vasta deadlinella. Siina valissa goaliq.app/fpl
 * nimesi kapteenin freezesta ja kortti edellisen kierroksen pickeista.
 * Nyt palvelin paattaa lahteen ja kertoo sen (`meta.source`).
 *
 * Vaitteet:
 *   1. kortin polku on /api/fantasy/model-captain, ei rate-team eika
 *      model-squad (`modelCardPath`),
 *   2. hakufunktio ja This week eivat koske rate-teamiin mallin kortissa,
 *      eivatka palaa siihen virheessa (fail-closed),
 *   3. lukija `modelCaptainCard` kaantaa kentat raportin kenttakartan
 *      mukaan molemmissa vaiheissa (frozen / entry_picks), ja lahderivi
 *      haarautuu `meta.source`:n mukaan.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import type { ModelCaptainResponse } from './fantasyTools';
import { blankComments } from './sourceScan';
import { modelCaptainCard, modelCardPath, modelSourceLine, NO_FIXTURE } from './weekRows';

const read = (rel: string) =>
	blankComments(readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')).replace(
		/\r\n/g,
		'\n'
	);

/** `export function <name> ... }` -runko. */
function fnBody(src: string, name: string): string {
	const a = src.indexOf(`export function ${name}`);
	if (a === -1) return '';
	const b = src.indexOf('\n}\n', a);
	return src.slice(a, b === -1 ? undefined : b + 2);
}

const RATE_TEAM = /rate-team|rate_team|fetchRateTeam\(/;

function modelCardProblems(fantasySrc: string, weekSrc: string, rowsSrc: string): string[] {
	const p: string[] = [];
	const body = fnBody(fantasySrc, 'fetchModelEntryCard');
	if (!body) p.push('fetchModelEntryCard puuttuu');
	if (!body.includes('modelCardPath()')) p.push('fetchModelEntryCard ei kayta modelCardPath-lukijaa');
	if (/model-squad|fetchModelSquad/.test(body)) p.push('fetchModelEntryCard lukee model-squadia');
	if (RATE_TEAM.test(body)) p.push('fetchModelEntryCard lukee rate-teamia');
	const path = fnBody(rowsSrc, 'modelCardPath');
	if (RATE_TEAM.test(path) || /entry=/.test(path)) p.push('modelCardPath palasi rate-team?entry=:iin');
	if (/model-squad|fetchModelSquad|fetchModelCard\(/.test(weekSrc))
		p.push('ThisWeek lukee model-squadia tai vanhaa fetchModelCardia');
	if (/fetchRateTeam\(|rate-team/.test(weekSrc)) p.push('ThisWeek hakee rate-teamia itse (mallin kortin paluu)');
	if (!/fetchModelEntryCard\(\)/.test(weekSrc)) p.push('ThisWeek ei hae mallin korttia');
	if (!/modelCaptainCard\(d\)/.test(weekSrc)) p.push('ThisWeek ei kaanna vastausta lukijalla');
	if (/modelEntryId/.test(weekSrc)) p.push('ThisWeek vaatii yha model-racen entry-id:n');
	return p;
}

const SOURCES = () =>
	[read('./fantasyTools.ts'), read('./components/ThisWeek.svelte'), read('./weekRows.ts')] as const;

/** Vastaus kuten backend 22.9 (src/models/fpl_model_captain.py). */
function resp(over: Partial<ModelCaptainResponse['meta']>, rest: Partial<ModelCaptainResponse> = {}) {
	return {
		meta: {
			source: 'entry_picks',
			gw: 6,
			entry_id: 116920,
			picks_gw: 5,
			frozen_at: null,
			frozen_deadline: null,
			deadline_gameweek: 6,
			deadline_time: '2026-10-10T10:00:00Z',
			generated_at: '2026-09-22T09:00:00Z',
			route: { kind: 'fpl_entry', gw: 5, url: 'https://fantasy.premierleague.com/entry/116920/event/5' },
			...over
		},
		captain: {
			id: 1,
			web_name: 'B.Fernandes',
			team_short: 'MUN',
			pos: 'MID',
			gw_xp: 6.75,
			opponents: [{ opp: 'TOT', venue: 'H' }]
		},
		vice_captain: null,
		alternative: {
			id: 2,
			web_name: 'Mbeumo',
			team_short: 'MUN',
			pos: 'MID',
			gw_xp: 6.1,
			opponents: [{ opp: 'TOT', venue: 'H' }]
		},
		...rest
	} as ModelCaptainResponse;
}

const FROZEN_META: Partial<ModelCaptainResponse['meta']> = {
	source: 'frozen',
	gw: 6,
	picks_gw: null,
	frozen_at: '2026-10-09T06:00:00Z',
	frozen_deadline: '2026-10-10T10:00:00Z',
	route: { kind: 'gw_calls', gw: 6, url: 'https://goaliq.app/fpl#gw-calls' }
};


describe('mallin kortti = /api/fantasy/model-captain', () => {
	it('polku: model-captain ilman parametreja (ei rate-team?entry=)', () => {
		expect(modelCardPath()).toBe('/api/fantasy/model-captain');
		expect(modelCardPath()).not.toMatch(/rate-team|entry=/);
	});

	it('lahde: hakufunktio ja This week eivat lue rate-teamia eivatka model-squadia', () => {
		expect(modelCardProblems(...SOURCES())).toEqual([]);
	});

	it('erotteleva kontrolli: kierroksen 2 versio (rate-team?entry=116920) kaatuu', () => {
		const [fantasy, week, rows] = SOURCES();
		const oldRows = rows.replace(
			"return '/api/fantasy/model-captain';",
			'return `/api/fantasy/rate-team?entry=${entryId}`;'
		);
		expect(oldRows).not.toBe(rows);
		expect(modelCardProblems(fantasy, week, oldRows)).toContain('modelCardPath palasi rate-team?entry=:iin');
		const oldFetch = `export function fetchModelEntryCard(entryId: number) {
	return getTool(modelCardPath(entryId), 'rate_team', false);
}
`;
		expect(modelCardProblems(oldFetch, week, rows)).toContain('fetchModelEntryCard lukee rate-teamia');
		const oldWeek = week.replace('fetchModelEntryCard()', 'fetchModelEntryCard(id)') + '\nmodelEntryId(race)';
		const probs = modelCardProblems(fantasy, oldWeek, rows);
		expect(probs).toContain('ThisWeek ei hae mallin korttia');
		expect(probs).toContain('ThisWeek vaatii yha model-racen entry-id:n');
		// Virhehaara joka palaisi rate-teamiin (fail-open).
		const fallback = week.replace('() => (modelFailed = true)', '() => fetchRateTeam(116920)');
		expect(fallback).not.toBe(week);
		expect(modelCardProblems(fantasy, fallback, rows)).toContain(
			'ThisWeek hakee rate-teamia itse (mallin kortin paluu)'
		);
	});

	it('erotteleva kontrolli: kierroksen 1 versio (model-squad) kaatuu', () => {
		const [, week, rows] = SOURCES();
		const old = `export function fetchModelEntryCard() {
	const squad = await getTool('/api/fantasy/model-squad', 'model_squad', false);
	return getTool(\`/api/fantasy/rate-team?players=\${ids}\`, 'rate_team_draft', false);
}
`;
		const problems = modelCardProblems(old, week, rows);
		expect(problems).toContain('fetchModelEntryCard lukee model-squadia');
		expect(problems).toContain('fetchModelEntryCard ei kayta modelCardPath-lukijaa');
	});
});

describe('lukija modelCaptainCard: vaiheet (saanto 6a kohta 3)', () => {
	it('entry_picks (ennen freezea): kapteeni, GW, vastustaja, vaihtoehto, FPL-reitti', () => {
		const c = modelCaptainCard(resp({}))!;
		expect(c.gw).toBe(6);
		expect(c.captain).toEqual({ id: 1, web_name: 'B.Fernandes', team_short: 'MUN', gw_xp: 6.75 });
		expect(c.opp).toBe('TOT (H)');
		expect(c.alt).toEqual({ id: 2, web_name: 'Mbeumo', team_short: 'MUN', gw_xp: 6.1 });
		expect(c.source).toEqual({
			kind: 'entry_picks',
			entryId: 116920,
			picksGw: 5,
			href: 'https://fantasy.premierleague.com/entry/116920/event/5'
		});
		expect(modelSourceLine(c.source)).toEqual({
			before: 'Squad: ',
			link: 'our FPL entry 116920',
			after: ', GW5 picks.',
			href: 'https://fantasy.premierleague.com/entry/116920/event/5'
		});
	});

	it('frozen (freezen ja deadlinen valissa): lukittu runko, ei vaihtoehtoa, gw-calls-reitti', () => {
		// Vaikka palvelin antaisi alternative-kentan, lukittu runko ei tarjoa close callia.
		const c = modelCaptainCard(
			resp(FROZEN_META, {
				captain: {
					id: 16,
					web_name: 'Saka',
					team_short: 'ARS',
					pos: 'MID',
					gw_xp: 6.2,
					opponents: [{ opp: 'LEE', venue: 'A' }],
					gw_xp_frozen: 6.4,
					gw_xp_basis: 'projection'
				}
			})
		)!;
		expect(c.gw).toBe(6);
		expect(c.captain?.web_name).toBe('Saka');
		expect(c.opp).toBe('LEE (A)');
		expect(c.alt).toBeNull();
		expect(c.source.kind).toBe('frozen');
		const line = modelSourceLine(c.source);
		expect(line).toEqual({
			before: 'Squad frozen for GW6, logged on ',
			link: 'goaliq.app/fpl',
			after: '.',
			href: 'https://goaliq.app/fpl#gw-calls'
		});
		// Frozen-rivi ei saa sanoa "picks": FPL:n pickit eivat ole viela julki.
		expect(`${line.before}${line.link}${line.after}`).not.toMatch(/picks|entry/);
	});

	it('vastustaja: [] = ei ottelua, null = ei rivia, tuplakierros yhdistetaan', () => {
		const cap = (opponents: unknown) =>
			modelCaptainCard(
				resp({}, { captain: { ...resp({}).captain!, opponents } as ModelCaptainResponse['captain'] })
			)!.opp;
		expect(cap([])).toBe(NO_FIXTURE);
		expect(cap(null)).toBeNull();
		expect(cap([{ opp: 'TOT', venue: 'H' }, { opp: 'ARS', venue: 'A' }])).toBe('TOT (H), ARS (A)');
		expect(cap([{ opp: null, venue: null }])).toBeNull();
	});

	it('fail-closed: tuntematon lahde, kelvoton entry, ei metaa -> ei korttia', () => {
		expect(modelCaptainCard(null)).toBeNull();
		expect(modelCaptainCard({} as ModelCaptainResponse)).toBeNull();
		expect(modelCaptainCard(resp({ source: 'guess' as never }))).toBeNull();
		expect(modelCaptainCard(resp({ entry_id: 0 }))).toBeNull();
	});

	it('kapteeni puuttuu -> ei kapteenia (kortti sanoo sen), ei keksittya nimea', () => {
		const c = modelCaptainCard(resp({}, { captain: null }))!;
		expect(c.captain).toBeNull();
		expect(c.opp).toBeNull();
		const noName = modelCaptainCard(resp({}, { captain: { ...resp({}).captain!, web_name: null } }))!;
		expect(noName.captain).toBeNull();
	});

	it('reitti: linkki vain omaan tai FPL:n hostiin; muuten teksti ilman linkkia', () => {
		const bad = modelCaptainCard(
			resp({ ...FROZEN_META, route: { kind: 'gw_calls', gw: 6, url: 'https://evil.test/fpl' } })
		)!;
		expect(bad.source.kind).toBe('frozen');
		expect(modelSourceLine(bad.source).href).toBeNull();
		const wrongHost = modelCaptainCard(
			resp({ route: { kind: 'fpl_entry', gw: 5, url: 'https://goaliq.app/fpl#gw-calls' } })
		)!;
		expect(modelSourceLine(wrongHost.source).href).toBeNull();
		const noRoute = modelCaptainCard(resp({ picks_gw: null, route: null }))!;
		expect(modelSourceLine(noRoute.source)).toEqual({
			before: 'Squad: ',
			link: 'our FPL entry 116920',
			after: '.',
			href: null
		});
	});

	it('frozen-rivi ei kanna freezen aikaa (B1 22.9): linkkisivu ei nayta sita', () => {
		// Kelvollinen, kelvoton ja puuttuva aikaleima tuottavat saman rivin.
		for (const frozen_at of ['2026-10-09T06:00:00Z', 'not-a-date', null]) {
			const c = modelCaptainCard(resp({ ...FROZEN_META, frozen_at }))!;
			const l = modelSourceLine(c.source);
			expect(l.before).toBe('Squad frozen for GW6, logged on ');
			expect(`${l.before}${l.link}${l.after}`).not.toMatch(/\d{1,2}:\d{2}|Oct|2026|Invalid/);
		}
		const noGw = modelCaptainCard(resp({ ...FROZEN_META, gw: null }))!;
		expect(modelSourceLine(noGw.source).before).toBe('Squad frozen, logged on ');
	});
});

describe('KUTSUPAIKKA: DecisionCard piirtaa lahderivin lukijalta', () => {
	it('mallin kortti lukee modelSourceLinea eika rakenna FPL-linkkia itse', () => {
		const card = read('./components/DecisionCard.svelte');
		expect(card).toMatch(/modelSourceLine\(model\.source/);
		// B1 22.9: kortti ei muotoile freezen aikaa itse (linkkisivu ei nayta sita).
		expect(card).not.toMatch(/frozen_?[aA]t|formatDeadline/);
		expect(card).not.toMatch(/fantasy\.premierleague\.com\/entry/);
		expect(card).not.toMatch(/modelEntry\b/);
	});
});
