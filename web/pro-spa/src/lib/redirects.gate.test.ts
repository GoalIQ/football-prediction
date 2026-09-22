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

/** Ryhmat ennen 22.9 (tools ennen 11.9). */
const OLD_GROUPS = ['week', 'team', 'players', 'prices', 'matches', 'tools'];

/** Tyokalupolut ennen 22.9 (rekisteri 6b65ce233) + /tools/<slug> ennen 11.9. */
const OLD_TOOL_PATHS = [
	'/team/rate-my-team',
	'/team/fit-checker',
	'/team/transfer-planner',
	'/team/watchlist',
	'/team/chip-timing',
	'/team/transfer-chains',
	'/team/league',
	'/players/player-card',
	'/players/captain-ranker',
	'/players/fixture-swing',
	'/players/player-xp',
	'/players/clean-sheets',
	'/players/value',
	'/players/leaders',
	'/players/stats',
	'/players/differentials',
	'/players/replacements',
	'/players/compare',
	'/players/edge-mode',
	'/prices/price-watch',
	'/matches/predict',
	'/matches/fixtures',
	'/matches/table',
	'/tools/chip-timing',
	'/tools/transfer-chains',
	'/tools/edge-mode',
	'/tools/league'
];

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
		expect(OLD_TOOL_PATHS.length).toBeGreaterThanOrEqual(27);
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
