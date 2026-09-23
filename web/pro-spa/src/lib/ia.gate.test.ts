/**
 * Portti: pron tietoarkkitehtuuri pysyy mobiiliapin kanssa samana, ja
 * puhelimen navi on kokonaan nakyvissa (22.9.2026, UX-uudistus A3 +
 * web-audit T2).
 *
 * 🔴 MITATTU 22.9 (390x844): navin viidesta kohdasta kolme oli ruudun
 * ulkopuolella ja neljas katkesi. /ucl ja /spl renderoivat ilman
 * ylapalkkia. Players-ryhman kaksitoista tyokalua olivat yhdella tasolla.
 *
 * Vaitteet:
 *   1. ryhmat = mobiilin tabit (sama jarjestys ja nimet), enintaan viisi
 *   2. jokainen ryhman tyokalu on tasan yhdessa valitsimen osiossa, ja
 *      esiasetukset ovat Players-osion tyokaluja
 *   3. alapalkki lukee rekisterin, jokaisella ryhmalla on kuvake, ja
 *      puhelimen katkaisupiste on sama ylapalkissa ja alapalkissa
 *   4. pelivalitsimen kohteet ovat olemassa olevia reitteja; /ucl ja /spl
 *      renderoivat AppShellin
 *   5. pelaajakortti avautuu jokaisesta Players-ryhman listasta: rivilla on
 *      `data-player-id`, ja AppShell kantaa ainoan kuuntelijan
 * Jokaisella on erotteleva kontrolli.
 */
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { blankComments } from './sourceScan';
import {
	GAMES,
	GROUPS,
	SPL_SECTIONS,
	activeNav,
	navItems,
	MATCHES_SECTIONS,
	PLAYERS_VIEWS,
	PLAYER_PRESETS,
	TEAM_SECTIONS,
	TOOLS,
	gameOf,
	groupOfPath,
	primaryTool,
	sectionOf,
	type Section
} from './tools';
import { NAV_ICONS } from './navIcons';
import { playerIdFromEvent } from './playerRow';

const src = (rel: string) =>
	readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8').replace(/\r\n/g, '\n');
const code = (rel: string) => blankComments(src(rel));

/** Mobiiliapin alapalkki (goaliq-app feat/ux-mobiili-ia, A3 luku 1) ilman
 *  "You"-tabia, joka on webissa ylapalkin tilinapit. */
const MOBILE_TABS = [
	['week', 'This week'],
	['team', 'My team'],
	['players', 'Players'],
	['matches', 'Matches']
];

describe('1. ryhmat = mobiilin tabit', () => {
	it('sama jarjestys ja samat nimet, enintaan viisi (A2 saanto 1)', () => {
		expect(GROUPS.map((g) => [g.id, g.label])).toEqual(MOBILE_TABS);
		expect(GROUPS.length).toBeLessThanOrEqual(5);
	});
	it('jokaisella tyokalulla on ryhma joka on olemassa', () => {
		const ids = new Set(GROUPS.map((g) => g.id));
		for (const t of TOOLS) expect(ids.has(t.group), `${t.slug} -> ${t.group}`).toBe(true);
	});
});

/** Osio-ongelmat ryhmalle: tyokalu ilman osiota, kahdessa osiossa, tai
 *  osion kohta joka ei ole ryhman tyokalu. */
function sectionProblems(group: string, sections: Section[]): string[] {
	const p: string[] = [];
	const inGroup = TOOLS.filter((t) => t.group === group).map((t) => t.slug);
	const seen = new Map<string, number>();
	for (const s of sections) {
		if (!s.tools.includes(s.lead)) p.push(`${group}/${s.id}: lead ${s.lead} ei ole osion tyokalu`);
		for (const slug of s.tools) {
			if (!inGroup.includes(slug)) p.push(`${group}/${s.id}: ${slug} ei ole ryhman tyokalu`);
			seen.set(slug, (seen.get(slug) ?? 0) + 1);
		}
	}
	for (const slug of inGroup) {
		const n = seen.get(slug) ?? 0;
		if (n !== 1) p.push(`${group}: ${slug} on ${n} osiossa (pitaa olla 1)`);
	}
	return p;
}

describe('2. valitsimet ja esiasetukset', () => {
	it('My team, Players ja Matches: jokainen tyokalu tasan yhdessa osiossa', () => {
		expect(sectionProblems('team', TEAM_SECTIONS)).toEqual([]);
		expect(sectionProblems('players', PLAYERS_VIEWS)).toEqual([]);
		expect(sectionProblems('matches', MATCHES_SECTIONS)).toEqual([]);
	});
	it('valitsimissa enintaan kolme segmenttia (A2 saanto 5) ja nimet kuten mobiilissa', () => {
		expect(TEAM_SECTIONS.map((s) => s.label)).toEqual(['Squad', 'Transfers', 'Chips']);
		expect(PLAYERS_VIEWS.map((s) => s.label)).toEqual(['Players', 'Teams']);
		for (const secs of [TEAM_SECTIONS, PLAYERS_VIEWS, MATCHES_SECTIONS])
			expect(secs.length).toBeLessThanOrEqual(3);
	});
	it('ryhman juuri avaa ensimmaisen osion lead-tyokalun (valitsin ja reitti samaa mielta)', () => {
		expect(primaryTool('team')?.slug).toBe(TEAM_SECTIONS[0].lead);
		expect(primaryTool('players')?.slug).toBe(PLAYERS_VIEWS[0].lead);
		expect(primaryTool('matches')?.slug).toBe(MATCHES_SECTIONS[0].lead);
		expect(sectionOf('team', null)?.id).toBe('squad');
		expect(sectionOf('team', 'fit-checker')?.id).toBe('transfers');
		expect(sectionOf('players', 'clean-sheets')?.id).toBe('teams');
	});
	it('esiasetukset: Captain, xP, Value, Differentials, Price change, kaikki Players-osion tyokaluja', () => {
		expect(PLAYER_PRESETS.map((p) => p.label)).toEqual([
			'Captain',
			'xP',
			'Value',
			'Differentials',
			'Price change'
		]);
		const playersView = PLAYERS_VIEWS.find((v) => v.id === 'players')!;
		for (const p of PLAYER_PRESETS) expect(playersView.tools, p.slug).toContain(p.slug);
		expect(PLAYER_PRESETS[0].slug).toBe(playersView.lead);
	});
	it('erotteleva kontrolli: osioton tai tuplattu tyokalu kaatuu', () => {
		const missing = TEAM_SECTIONS.map((s) => ({ ...s, tools: s.tools.filter((x) => x !== 'watchlist') }));
		expect(sectionProblems('team', missing).some((x) => x.includes('watchlist'))).toBe(true);
		const doubled = TEAM_SECTIONS.map((s, i) => (i === 1 ? { ...s, tools: [...s.tools, 'rate-my-team'] } : s));
		expect(sectionProblems('team', doubled).some((x) => x.includes('rate-my-team'))).toBe(true);
	});
});

/** Alapalkin ja ylapalkin puhelinkatkaisupiste. */
function phoneBreakpoints(): { bottom: string[]; hero: string[]; game: string[] } {
	const bp = (s: string) => [...s.matchAll(/@media \(max-width: (\d+)px\)/g)].map((m) => m[1]);
	return {
		bottom: bp(src('./components/BottomNav.svelte')),
		hero: bp(src('./components/Hero.svelte')),
		game: bp(src('./components/GameSwitcher.svelte'))
	};
}

/** Hero piilottaa ylanavin puhelimessa (alapalkki korvaa sen). */
function heroHidesNavOnPhone(heroSrc: string): boolean {
	const m = heroSrc.match(/@media \(max-width: 640px\) \{([\s\S]*?)\n\t\}\n/);
	return !!m && /\.nav \{\s*display: none;/.test(m[1]);
}

describe('3. alapalkki', () => {
	it('lukee rekisterin kohteet ja jokaisella kohteella on kuvake', () => {
		// 23.9 (Villen valinta B): kohteet pelin mukaan yhdesta lukijasta.
		const bn = code('./components/BottomNav.svelte');
		expect(bn).toMatch(/import \{ activeNav, navItems \} from '\$lib\/tools'/);
		expect(bn).toMatch(/\{#each items as g/);
		expect(bn).toContain('navItems(page.url.pathname)');
		for (const path of ['/', '/spl', '/ucl'])
			for (const g of navItems(path)) expect(NAV_ICONS[g.icon], `${path} ${g.id}`).toBeTruthy();
	});
	it('palkki on pelin oma: FPL = ryhmat, RSL ja UCL = omat osiot (23.9 valinta B)', () => {
		expect(navItems('/').map((g) => g.label)).toEqual(GROUPS.map((g) => g.label));
		expect(navItems('/players/value').map((g) => g.id)).toEqual(GROUPS.map((g) => g.id));
		expect(navItems('/spl').map((g) => g.label)).toEqual(SPL_SECTIONS.map((s) => s.label));
		expect(navItems('/spl').map((g) => g.href)).toEqual(SPL_SECTIONS.map((s) => `/spl#${s.lead}`));
		expect(activeNav('/spl', '#value')).toBe('players');
		expect(activeNav('/spl', '#accuracy')).toBe('teams');
		expect(activeNav('/spl', '')).toBe('players');
		expect(activeNav('/spl', '#model-squad')).toBe('squad');
		expect(activeNav('/players/value', '')).toBe('players');
		// UCL sai oman palkin samana iltana (Villen valinta: sama rakenne).
		expect(navItems('/ucl').map((g) => g.label)).toEqual(['Players', 'Teams']);
		expect(activeNav('/ucl', '')).toBe('players');
		expect(activeNav('/ucl', '#clean-sheets')).toBe('teams');
	});
	it('ylapalkki lukee saman lukijan, eika nayta FPL:n deadlinea muiden pelien sivuilla', () => {
		const hero = code('./components/Hero.svelte');
		expect(hero).toContain('navItems(page.url.pathname)');
		expect(hero).toContain('activeNav(page.url.pathname, page.url.hash)');
		expect(hero).toMatch(/\{#each navList as g/);
		expect(hero).toContain('{#if fplGame && (gw !== null || dl)}');
		expect(hero).not.toMatch(/\{#each GROUPS as g/);
	});
	it('puhelimen katkaisupiste on 640 px kaikissa kolmessa, ja Hero piilottaa ylanavin siina', () => {
		const b = phoneBreakpoints();
		expect(b.bottom).toContain('640');
		expect(b.hero).toContain('640');
		expect(b.game).toContain('640');
		expect(heroHidesNavOnPhone(src('./components/Hero.svelte'))).toBe(true);
	});
	it('AppShell renderoi alapalkin ja varaa sille tilan', () => {
		const shell = code('./components/AppShell.svelte');
		expect(shell).toContain('<BottomNav />');
		expect(shell).toContain('class="bottom-spacer"');
	});
	it('erotteleva kontrolli: ilman piilotusta Hero-tarkistin kaatuu', () => {
		const hero = src('./components/Hero.svelte').replace(
			/(@media \(max-width: 640px\) \{[\s\S]*?)\.nav \{\s*display: none;\s*\}/,
			'$1'
		);
		expect(heroHidesNavOnPhone(hero)).toBe(false);
	});
	it('aktiivinen ryhma polusta: juuri = This week, peli-reitit eivat korosta FPL-ryhmaa', () => {
		expect(groupOfPath('/')).toBe('week');
		expect(groupOfPath('/week')).toBe('week');
		expect(groupOfPath('/players/value')).toBe('players');
		expect(groupOfPath('/ucl')).toBeNull();
		expect(groupOfPath('/spl')).toBeNull();
		expect(groupOfPath('/prices')).toBeNull();
	});
});

describe('4. pelivalitsin ja erillisreitit', () => {
	it('FPL / UCL Fantasy / RSL Fantasy, kohteet ovat olemassa olevia reitteja', () => {
		expect(GAMES.map((g) => g.label)).toEqual(['FPL', 'UCL Fantasy', 'RSL Fantasy']);
		for (const g of GAMES) {
			const rel = g.href === '/' ? '../routes/+page.svelte' : `../routes${g.href}/+page.svelte`;
			expect(existsSync(fileURLToPath(new URL(rel, import.meta.url))), g.href).toBe(true);
		}
		expect(gameOf('/ucl').id).toBe('ucl');
		expect(gameOf('/spl').id).toBe('spl');
		expect(gameOf('/players/value').id).toBe('fpl');
		expect(gameOf('/').id).toBe('fpl');
	});
	it('Hero kantaa pelivalitsimen, ja valitsin lukee rekisterin', () => {
		expect(code('./components/Hero.svelte')).toContain('<GameSwitcher />');
		expect(code('./components/GameSwitcher.svelte')).toMatch(/\{#each GAMES as g/);
	});
	it('/ucl ja /spl renderoivat sisaltonsa AppShellin sisalla', () => {
		for (const rel of ['../routes/ucl/+page.svelte', '../routes/spl/+page.svelte']) {
			const s = code(rel);
			expect(s, rel).toMatch(/<AppShell>[\s\S]*<\/AppShell>/);
		}
	});
	it('AppShell ei kirjoita omaa otsikkoaan erillisreitille (prerenderoitu /spl: tasan kaksi titlea)', () => {
		expect(code('./components/AppShell.svelte')).toMatch(
			/\{#if !children\}\s*<title>\{pageTitle\(group, tool\)\}<\/title>/
		);
	});
});

/** Players-ryhman listat joiden pelaajarivista kortti avautuu. */
const PLAYER_LISTS: Record<string, RegExp> = {
	'XpTable.svelte': /\{#each g\.players as p \(p\.id\)\}\s*<tr\s+data-player-id=\{p\.id\}/,
	'CaptainRanker.svelte': /<tr data-player-id=\{p\.id\}>/,
	'Value.svelte': /<tr data-player-id=\{p\.id\}>/,
	'Differentials.svelte': /<tr data-player-id=\{p\.id\}>/,
	'PriceWatch.svelte': /<tr data-player-id=\{r\.id\}>/,
	'LockedToolPreview.svelte': /<tr data-player-id=\{p\.id\}>/,
	'FixtureSwing.svelte': /<tr data-player-id=\{r\.p\.id\}/,
	'Leaders.svelte': /<tr data-player-id=\{a\.row\.id\}>[\s\S]*<tr data-player-id=\{p\.id\}/,
	'Stats.svelte': /<tr data-player-id=\{p\.id\}/,
	'Replacements.svelte': /<tr data-player-id=\{p\.id\}>/,
	'EdgeMode.svelte': /<tr data-player-id=\{c\.id\}>/
};

function listProblems(read: (f: string) => string): string[] {
	return Object.entries(PLAYER_LISTS)
		.filter(([f, re]) => !re.test(read(f)))
		.map(([f]) => f);
}

describe('5. pelaajakortti mista tahansa rivista', () => {
	const read = (f: string) => code(`./components/${f}`);

	it('jokaisen Players-listan rivilla on data-player-id', () => {
		expect(listProblems(read)).toEqual([]);
	});
	it('AppShellissa on ainoa kuuntelija, ja sheet on renderoity kerran', () => {
		const shell = code('./components/AppShell.svelte');
		expect(shell).toContain('<main use:playerRows={group}>');
		expect(shell.match(/<PlayerSheet \/>/g)?.length).toBe(1);
	});
	it('delegointi: rivi avaa, rivin oma nappi ja linkki eivat', () => {
		const row = { getAttribute: () => '426' } as unknown as Element;
		const el = (interactive: boolean, inRow: boolean) =>
			({
				closest: (sel: string) =>
					sel.startsWith('a,button') ? (interactive ? ({} as Element) : null) : inRow ? row : null
			}) as unknown as Element;
		expect(playerIdFromEvent(el(false, true))).toBe(426);
		expect(playerIdFromEvent(el(true, true))).toBeNull();
		expect(playerIdFromEvent(el(false, false))).toBeNull();
		expect(playerIdFromEvent(null)).toBeNull();
	});
	it('erotteleva kontrolli: attribuutin poisto yhdesta listasta kaatuu', () => {
		const broken = (f: string) =>
			f === 'Value.svelte' ? read(f).replace('<tr data-player-id={p.id}>', '<tr>') : read(f);
		expect(listProblems(broken)).toEqual(['Value.svelte']);
	});
});
