/**
 * Portti: jokainen polku joka on joskus ollut julkinen, paatyy nykyiseen
 * reittiin (22.9.2026, UX-uudistus A3: Price watch -ryhma purettiin, 11.9
 * Tools-ryhma purettiin).
 *
 * 🔴 MIKSI LISTA ON TASSA EIKA REKISTERISTA JOHDETTU: rekisteri kertoo vain
 * NYKYISET reitit. Jos portti johtaisi vanhat polut rekisterista, poistettu
 * ryhma katoaisi myos portista, eli portti hyvaksyisi tasmalleen sen vian
 * jota se vartioi (jaettu URL /prices -> tyhja sivu tai juuri). Lista on
 * jaadytetty historia: uutta polkua ei poisteta tasta koskaan, ja uuden
 * rakenteen muutoksen jalkeen sen nykyiset polut lisataan.
 *
 * Kaatuu jos yksikin vanha polku:
 *   - ei ratkea (resolvePath palauttaa null),
 *   - ratkeaa polkuun joka ei ole nykyinen reitti,
 *   - ratkeaa eri kohteeseen kuin tassa kirjattu (siirretyt tyokalut).
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { blankComments } from './sourceScan';
import {
	GROUPS,
	LEGACY_HASH_TO_PATH,
	LEGACY_PATHS,
	TOOLS,
	resolvePath,
	toolPath
} from './tools';
import {
	HISTORIC_GROUPS,
	HISTORIC_TOOL_PATHS,
	redirectRules,
	redirectsFile,
	type RedirectRule
} from './legacyPaths';

/* Jaadytetty historia on $lib/legacyPaths:ssa, koska myos buildin
   _redirects lukee sen. Taman portin oma, riippumaton kirjaus on alla
   (MOVED + lukumaarat), joten listan lyhentaminen kaatuu tassa. */
const OLD_GROUPS: readonly string[] = HISTORIC_GROUPS;
const OLD_TOOL_PATHS: readonly string[] = HISTORIC_TOOL_PATHS;

/** Siirtyneet: kohde on kirjattu, jotta "paatyi johonkin" ei riita. */
const MOVED: Record<string, string> = {
	'/prices': '/players/price-watch',
	'/prices/price-watch': '/players/price-watch',
	'/tools': '/team',
	'/tools/chip-timing': '/team/chip-timing',
	'/tools/transfer-chains': '/team/transfer-chains',
	'/tools/edge-mode': '/players/edge-mode',
	'/tools/league': '/team/league'
};

const CURRENT = new Set<string>([
	'/',
	...GROUPS.map((g) => `/${g.id}`),
	...TOOLS.map((t) => toolPath(t))
]);

/** Tarkistin erikseen, jotta erotteleva kontrolli voi ajaa sen rikotulla
 *  resolverilla. */
function oldPathProblems(resolve: (p: string) => string | null): string[] {
	const problems: string[] = [];
	const all = ['/', ...OLD_GROUPS.map((g) => `/${g}`), ...OLD_TOOL_PATHS];
	for (const old of all) {
		const got = resolve(old);
		if (got == null) problems.push(`${old}: ei ratkea`);
		else if (!CURRENT.has(got)) problems.push(`${old} -> ${got}: ei nykyinen reitti`);
		else if (MOVED[old] && got !== MOVED[old]) problems.push(`${old} -> ${got} (odotettiin ${MOVED[old]})`);
		// Vanha polku joka on yha nykyinen, ratkeaa itseensa.
		else if (!MOVED[old] && CURRENT.has(old) && got !== old) problems.push(`${old} -> ${got}: nykyinen reitti ohjattiin pois`);
	}
	return problems;
}

describe('vanhat polut -> nykyinen reitti', () => {
	it('kontrolli: lista ei ole tyhja ja kattaa purettujen ryhmien jokaisen tyokalun', () => {
		// Jaadytetty: lista saa kasvaa, ei lyhentya (22.9: 6 ryhmaa, 27 polkua).
		expect(OLD_GROUPS.length).toBeGreaterThanOrEqual(6);
		expect(OLD_TOOL_PATHS.length).toBeGreaterThanOrEqual(27);
		for (const moved of Object.keys(MOVED)) {
			expect([...OLD_GROUPS.map((g) => `/${g}`), ...OLD_TOOL_PATHS], moved).toContain(moved);
		}
		expect(OLD_TOOL_PATHS).toContain('/prices/price-watch');
		// Jokainen nykyinen tyokalu oli olemassa ennen 22.9 jollain polulla.
		for (const t of TOOLS) {
			expect(
				OLD_TOOL_PATHS.some((p) => p.endsWith(`/${t.slug}`)),
				`${t.slug}: puuttuu vanhojen polkujen listalta`
			).toBe(true);
		}
	});

	it('jokainen vanha polku paatyy nykyiseen reittiin (ja siirretyt oikeaan)', () => {
		expect(oldPathProblems(resolvePath)).toEqual([]);
	});

	it('nykyinen reitti ratkeaa itseensa, myos loppukauttaviivalla', () => {
		for (const p of CURRENT) {
			expect(resolvePath(p), p).toBe(p);
			if (p !== '/') expect(resolvePath(`${p}/`), `${p}/`).toBe(p);
		}
	});

	it('resolvePath on kiintopiste: ohjauksen kohde ei ohjaudu uudelleen', () => {
		for (const p of [...OLD_GROUPS.map((g) => `/${g}`), ...OLD_TOOL_PATHS]) {
			const once = resolvePath(p);
			expect(resolvePath(once as string), p).toBe(once);
		}
	});

	it('tuntematon: kirjoitusvirhe juureen, tuntematon tyokalu ryhmaansa', () => {
		expect(resolvePath('/playerz')).toBeNull();
		expect(resolvePath('/players/nonexistent-tool')).toBe('/players');
		expect(resolvePath('/prices/nonexistent')).toBe('/players/price-watch');
		expect(resolvePath('/a/b/c')).toBeNull();
	});

	it('vanhat hash-linkit (#tools=<id>) osoittavat nykyiseen reittiin', () => {
		for (const [id, target] of Object.entries(LEGACY_HASH_TO_PATH)) {
			expect(CURRENT.has(target), `#tools=${id} -> ${target}`).toBe(true);
		}
	});

	it('LEGACY_PATHS: jokainen avain on purettu ryhma, ei nykyinen reitti', () => {
		for (const [from, to] of Object.entries(LEGACY_PATHS)) {
			expect(CURRENT.has(from), `${from} on yha reitti, ohjaus varjostaisi sen`).toBe(false);
			expect(CURRENT.has(to), `${from} -> ${to}`).toBe(true);
		}
	});
});

describe('erotteleva kontrolli: portti huomaa puuttuvan ohjauksen', () => {
	it('ilman /prices-ohjausta portti kaatuu (kaksi polkua)', () => {
		const broken = (p: string) =>
			p.startsWith('/prices') ? null : resolvePath(p);
		const problems = oldPathProblems(broken);
		expect(problems.some((x) => x.startsWith('/prices:'))).toBe(true);
		expect(problems.some((x) => x.startsWith('/prices/price-watch:'))).toBe(true);
	});

	it('vanha kayttaytyminen (tuntematon ryhma -> juuri) kaatuu /pricesille', () => {
		const old = (p: string) => (p === '/prices' ? '/' : resolvePath(p));
		expect(oldPathProblems(old).some((x) => x.startsWith('/prices ->'))).toBe(true);
	});
});

describe('yksi lukija: molemmat reittisivut kysyvat resolvePathilta', () => {
	const read = (rel: string) =>
		blankComments(readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8'));
	for (const rel of ['../routes/[group]/+page.svelte', '../routes/[group]/[tool]/+page.svelte']) {
		it(rel, () => {
			const src = read(rel);
			expect(src).toMatch(/resolvePath\(page\.url\.pathname\)/);
			// Ohjaus kulkee query-parametrit mukana (?entry=, ?src=).
			expect(src).toContain('${page.url.search}');
			// $effect eika onMount: sama sivukomponentti kaytetaan uudelleen
			// reitin sisalla, ja onMount ei ajaisi ohjausta toista kertaa.
			expect(src).toMatch(/\$effect\(\(\) => \{\s*if \(!here\)/);
			expect(src).not.toMatch(/findToolAnywhere|groupById/);
		});
	}
});

/** Palvelimen 301-saantojen ongelmat (erikseen erottelevaa kontrollia varten). */
function ruleProblems(rules: RedirectRule[]): string[] {
	const p: string[] = [];
	const seen = new Set<string>();
	rules.forEach((r, i) => {
		if (CURRENT.has(r.from)) p.push(`${r.from}: lahde on nykyinen reitti (varjostaisi sivun)`);
		if (!CURRENT.has(r.to)) p.push(`${r.from} -> ${r.to}: kohde ei ole nykyinen reitti`);
		if (seen.has(r.from)) p.push(`${r.from}: kahdesti`);
		seen.add(r.from);
		// Pages kayttaa ensimmaista osumaa: jokeri ennen tarkkaa polkua nielisi sen.
		if (r.from.endsWith('/*')) {
			const base = r.from.slice(0, -1);
			for (const later of rules.slice(i + 1))
				if (later.from.startsWith(base)) p.push(`${later.from}: jokerin ${r.from} jalkeen`);
		}
	});
	for (const [from, to] of Object.entries(MOVED)) {
		const hit = rules.find((r) => r.from === from);
		if (!hit) p.push(`${from}: 301 puuttuu`);
		else if (hit.to !== to) p.push(`${from} -> ${hit.to} (odotettiin ${to})`);
	}
	return p;
}

describe('palvelimen 301 (_redirects buildissa)', () => {
	it('jokainen siirtynyt polku ohjautuu, kohteet ovat reitteja, lahteet eivat', () => {
		expect(ruleProblems(redirectRules())).toEqual([]);
	});
	it('purettujen ryhmien tuntematon alipolku ohjautuu (jokeri viimeisena)', () => {
		const rules = redirectRules();
		expect(rules.find((r) => r.from === '/prices/*')?.to).toBe('/players/price-watch');
		expect(rules.find((r) => r.from === '/tools/*')?.to).toBe('/team');
		expect(rules.some((r) => r.from.startsWith('/players') || r.from.startsWith('/team'))).toBe(false);
	});
	it('tiedoston muoto: "<from> <to> 301" jokaisella rivilla', () => {
		const lines = redirectsFile().trim().split('\n').filter((l) => !l.startsWith('#'));
		expect(lines.length).toBe(redirectRules().length);
		for (const l of lines) expect(l).toMatch(/^\/\S+ \/\S* 301$/);
	});
	it('erotteleva kontrolli: puuttuva /prices, jokeri ennen tarkkaa ja nykyisen reitin varjostus kaatuvat', () => {
		const rules = redirectRules();
		expect(ruleProblems(rules.filter((r) => r.from !== '/prices')).some((x) => x.startsWith('/prices:'))).toBe(true);
		const splatFirst = [{ from: '/tools/*', to: '/team' }, ...rules];
		expect(ruleProblems(splatFirst).some((x) => x.includes('jokerin /tools/*'))).toBe(true);
		const shadow = [...rules, { from: '/players/value', to: '/players' }];
		expect(ruleProblems(shadow).some((x) => x.includes('varjostaisi'))).toBe(true);
	});
	it('build kirjoittaa tiedoston taman moduulin generaattorilla', () => {
		const script = readFileSync(fileURLToPath(new URL('../../scripts/route-heads.mjs', import.meta.url)), 'utf-8');
		expect(script).toContain("import('../src/lib/legacyPaths.ts')");
		expect(script).toMatch(/redirectsFile\(\)/);
	});
});
