/**
 * Portti: siirtoparin pelaaja naytetaan pelipaikan ja seuran kanssa (1.10.2026).
 *
 * Villen havainto: This weekin "Out Tzolis -> In Tavernier" luettiin
 * maalivahdin vaihdoksi kenttapelaajaan (Tzolis = ARS MID, Tzolakis = HUL GKP).
 * Viisi komponenttia nayttaa siirtoparin, ja jokainen oli muotoillut sen
 * itse: kaksi naytti seuran, yksikaan ei pelipaikkaa.
 *
 * Mekanismi (saanto 6a):
 *   (1) yksi lukija: $lib/transferLabel (transferTag / transferPairText),
 *   (2) poikkeuslista perusteluineen: rivi joka lukee `out.web_name`ia tai
 *       `in.web_name`ia muuhun kuin siirtoparin nayttoon,
 *   (3) skannaus kattaa KAIKKI komponentit, ei vain nykyisia viitta: uusi
 *       pinta joka nayttaa pelkat nimet kaataa taman testin.
 */
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { blankComments } from './sourceScan';
import { transferPairText, transferPlayerText, transferTag } from './transferLabel';

const SRC = fileURLToPath(new URL('..', import.meta.url));

/** Rivi saa lukea nimen ilman tunnistetta vain perustellusti.
 *  Avain: tiedosto (src:sta) + rivin sisalto (trimmattu, osajono). */
const POIKKEUKSET: { file: string; line: string; why: string }[] = [
	{
		file: 'lib/components/RateTeam.svelte',
		line: 'out: sug.out.web_name,',
		why: 'modelChoice on paatoslokiin tallennettava data, ei naytto; naytetty teksti on modelText (transferPairText).'
	},
	{
		file: 'lib/components/RateTeam.svelte',
		line: 'in: sug.in.web_name',
		why: 'sama modelChoice-data kuin edella.'
	},
	{
		file: 'lib/components/RateTeam.svelte',
		line: 'web_name: s.in.web_name,',
		why: 'planner-kentan pelaajarivin kopio (Apply), ei siirtoparin naytto.'
	},
	{
		file: 'lib/components/RateTeam.svelte',
		line: '>{s.out.web_name}',
		why: 'siirtotaulukossa on oma Pos-sarake ({s.pos}) samalla rivilla ja seura vieressa.'
	},
	{
		file: 'lib/components/RateTeam.svelte',
		line: '>{s.in.web_name}',
		why: 'sama siirtotaulukko kuin edella (Pos-sarake).'
	},
	{
		file: 'lib/components/TransferPlanner.svelte',
		line: 'repairNote(t.out.web_name,',
		why: 'yhden pelaajan korjausnootti, ei siirtopari.'
	}
];

const NAME = /\.(out|in)\.web_name\b/;
const LABEL = /transferTag\(|transferPairText\(|transferPlayerText\(/;
/** Jakokortin rivi: nimi `name:`ssa ja pelipaikka `tag:`ssa (shareCardin pos-tagi). */
const SHARE_TAG = /^\s*tag:\s*[\w.]+\.pos,/;

function walk(dir: string, out: string[] = []): string[] {
	for (const e of readdirSync(dir, { withFileTypes: true })) {
		const p = join(dir, e.name);
		if (e.isDirectory()) walk(p, out);
		else if (/\.(svelte|ts)$/.test(e.name) && !/\.test\.ts$/.test(e.name)) out.push(p);
	}
	return out;
}

function rel(p: string): string {
	return p.slice(SRC.length).replace(/\\/g, '/').replace(/^\//, '');
}

/** Rikkomukset: nimi ilman tunnistetta samalla tai kahdella seuraavalla rivilla. */
export function violations(file: string, src: string): string[] {
	const lines = blankComments(src).split('\n');
	const bad: string[] = [];
	lines.forEach((line, i) => {
		if (!NAME.test(line)) return;
		const near = lines.slice(i, i + 3);
		if (near.some((l) => LABEL.test(l))) return;
		if (/^\s*name:/.test(line) && near.some((l) => SHARE_TAG.test(l))) return;
		const t = line.trim();
		if (POIKKEUKSET.some((x) => x.file === file && t.includes(x.line))) return;
		bad.push(`${file}:${i + 1}: ${t}`);
	});
	return bad;
}

describe('siirtoparin tunniste: yksi lukija', () => {
	const files = walk(join(SRC, 'lib')).concat(walk(join(SRC, 'routes')));

	it('jokainen siirtoparin nimi kulkee transferLabelin kautta (tai on poikkeus)', () => {
		const bad = files.flatMap((f) => violations(rel(f), readFileSync(f, 'utf-8')));
		expect(bad).toEqual([]);
	});

	it('poikkeuslista ei vanhene: jokainen rivi on yha olemassa', () => {
		for (const x of POIKKEUKSET) {
			const src = readFileSync(join(SRC, x.file), 'utf-8');
			expect(src.includes(x.line), `${x.file}: ${x.line}`).toBe(true);
			expect(x.why.length).toBeGreaterThan(10);
		}
	});

	it('skannaus loytaa pinnat (ei vihrea tyhjalla)', () => {
		const hits = files.filter((f) => NAME.test(blankComments(readFileSync(f, 'utf-8'))));
		// DecisionCard, PlanChains, RateTeam, TransferPlanner (HoldVerdictCard antaa olion suoraan transferPairTextille).
		expect(hits.length).toBeGreaterThanOrEqual(4);
	});

	it('NEGATIIVINEN KONTROLLI: pelkka nimipari kaatuu, tunnisteellinen ei', () => {
		const raw = '<li>\n{m.out.web_name}\n<span>→</span>\n</li>\n<li>\n\n\n{m.in.web_name}\n</li>';
		expect(violations('x.svelte', raw)).toHaveLength(2);
		const ok = '{m.out.web_name} <span>({transferTag(m.out.pos, m.out.team_short)})</span>';
		expect(violations('x.svelte', ok)).toEqual([]);
		const share = 'name: `${m.out.web_name} to ${m.in.web_name}`,\ntag: m.out.pos,';
		expect(violations('x.svelte', share)).toEqual([]);
		const shareGw = 'name: `${m.out.web_name} to ${m.in.web_name}`,\ntag: `GW${g.gw}`,';
		expect(violations('x.svelte', shareGw)).toHaveLength(1);
	});
});

describe('transferLabel: muoto (sama kuin backendin move_player_label)', () => {
	it('Tzolis vs Tzolakis erottuu', () => {
		// Sama odotettu merkkijono kuin tests/test_transfer_decision_bar.py:ssa.
		expect(
			transferPairText(
				{ web_name: 'Tzolis', team_short: 'ARS' },
				{ web_name: 'Tavernier', team_short: 'BOU' },
				'MID'
			)
		).toBe('Tzolis (MID, ARS) to Tavernier (MID, BOU)');
		expect(transferPlayerText({ web_name: 'Tzolakis', team_short: 'HUL', pos: 'GKP' })).toBe(
			'Tzolakis (GKP, HUL)'
		);
	});

	it('puuttuva osa jaa pois, ei "null" eika tyhjia sulkuja', () => {
		expect(transferPlayerText({ web_name: 'A' })).toBe('A');
		expect(transferPlayerText({ web_name: 'A', team_short: null }, null)).toBe('A');
		expect(transferPlayerText({ web_name: 'A', team_short: 'ARS' })).toBe('A (ARS)');
		expect(transferTag('MID', 'ARS')).toBe('MID · ARS');
		expect(transferTag(null, 'ARS')).toBe('ARS');
		expect(transferTag(undefined, undefined)).toBe('');
	});

	it('erotin', () => {
		expect(transferPairText({ web_name: 'A' }, { web_name: 'B' }, 'DEF', ' → ')).toBe(
			'A (DEF) → B (DEF)'
		);
	});
});
