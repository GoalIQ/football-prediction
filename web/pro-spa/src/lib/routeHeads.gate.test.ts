/**
 * Portti: jokaisella pron reitilla on oma link preview (22.9, web-audit T6).
 *
 * 🔴 MIKSI: raaka HTML (jota X, Bluesky, Slack ja Facebook lukevat) oli sama
 * index.html jokaisella reitilla. 21.9 markkinoitu `pro.goaliq.app/ucl`
 * nakyi jaettuna "GoalIQ Premium | FPL tools", og:url osoitti juureen, ja
 * /spl:n og:title oli sama FPL-otsikko vaikka sen <title> oli oma.
 *
 * Sama predikaatti (`buildProblems`) ajetaan buildissa levylle kirjoitetuille
 * tiedostoille (scripts/route-heads.mjs, exit 1). Tama portti ajaa sen
 * app.html-templaatista, joten se kaatuu jo ennen buildia, ja se todistaa
 * erottelevalla kontrollilla etta predikaatti huomaa vanhan tilan.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { blankComments } from './sourceScan';
import { GROUPS, TOOLS, toolPath } from './tools';
import {
	ORIGIN,
	SPL_HEAD,
	UCL_HEAD,
	applyRouteHead,
	buildProblems,
	readHead,
	routeHeads,
	type RouteHead
} from './routeHeads';

const read = (rel: string) =>
	readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8').replace(/\r\n/g, '\n');
const APP_HTML = read('../app.html');
const heads = routeHeads();

/** Mita palvelin antaisi kullekin reitille kun build-skripti on ajettu. */
function servedAfter(): Map<string, string> {
	const m = new Map<string, string>();
	for (const h of heads) m.set(h.path, applyRouteHead(h.prerendered ? splPrerender() : APP_HTML, h));
	return m;
}

/** Prerenderoidun /spl:n muoto: templaatti + sivun oma svelte:head, jonka
 *  SvelteKit lisaa %sveltekit.head%:n kohdalle (sama jarjestys kuin buildissa). */
function splPrerender(): string {
	return APP_HTML.replace(
		'%sveltekit.head%',
		`<title>${SPL_HEAD.title}</title><meta name="description" content="${SPL_HEAD.description}"/>` +
			`<link rel="canonical" href="${ORIGIN}/spl"/>`
	);
}

describe('reittikohtaiset headit', () => {
	it('taulukko kattaa /ucl, /spl, jokaisen ryhman ja jokaisen tyokalun', () => {
		const paths = new Set(heads.map((h) => h.path));
		expect(paths.has('/ucl')).toBe(true);
		expect(paths.has('/spl')).toBe(true);
		for (const g of GROUPS) expect(paths.has(`/${g.id}`), g.id).toBe(true);
		for (const t of TOOLS) expect(paths.has(toolPath(t)), t.slug).toBe(true);
		expect(paths.size).toBe(heads.length);
	});

	it('buildin jalkiehto on tyhja: jokainen reitti saa oman headinsa', () => {
		expect(buildProblems(servedAfter())).toEqual([]);
	});

	it('/ucl: title, og:title ja twitter:title sanovat UCL, og:url on /ucl', () => {
		const h = readHead(servedAfter().get('/ucl')!);
		expect(h.titles).toEqual([UCL_HEAD.title]);
		expect(h.social['og:title']![0]).toContain('UCL');
		expect(h.social['twitter:title']![0]).toContain('UCL');
		expect(h.social['og:url']).toEqual([`${ORIGIN}/ucl`]);
		expect(h.descriptions).toEqual([UCL_HEAD.description]);
	});

	it('/spl: templaatin FPL-otsikko ei jaa title- eika og-tageihin', () => {
		const h = readHead(servedAfter().get('/spl')!);
		expect(h.titles).toEqual([SPL_HEAD.title]);
		expect(h.social['og:title']).toEqual([SPL_HEAD.title]);
		expect(h.social['og:url']).toEqual([`${ORIGIN}/spl`]);
		expect(h.canonicals).toEqual([`${ORIGIN}/spl`]);
	});

	it('otsikot eroavat toisistaan ja templaatista (paitsi saman sivun kaksi osoitetta)', () => {
		const template = readHead(APP_HTML).titles[0];
		const byTitle = new Map<string, Set<string>>();
		for (const h of heads) {
			expect(h.title, h.path).not.toBe(template);
			byTitle.set(h.title, (byTitle.get(h.title) ?? new Set()).add(h.canonical));
		}
		for (const [title, canon] of byTitle) expect(canon.size, title).toBe(1);
		// Ainoa sallittu tuplaotsikko on ryhma jonka ainoa tyokalu se on.
		expect(byTitle.size).toBeGreaterThanOrEqual(heads.length - 1);
	});

	it('julkinen teksti: ei em dashia eika tyhjaa kuvausta', () => {
		for (const h of heads) {
			const d = h.description ?? readHead(APP_HTML).descriptions[0];
			expect(d.length, h.path).toBeGreaterThan(10);
			expect(`${h.title} ${d}`, h.path).not.toContain(String.fromCharCode(0x2014));
		}
	});
});

describe('erotteleva kontrolli: predikaatti nakee vanhan tilan', () => {
	it('ennen 22.9 jokainen reitti sai saman index.html:n -> jokainen reitti kaatuu', () => {
		const before = new Map(heads.map((h) => [h.path, APP_HTML]));
		const problems = buildProblems(before);
		for (const h of heads) {
			expect(problems.some((p) => p.startsWith(`${h.path}:`)), h.path).toBe(true);
		}
		expect(problems.some((p) => p.includes('/ucl: title'))).toBe(true);
	});

	it('muunnos on fail-closed: puuttuva tai tuplattu tagi heittaa', () => {
		const ucl = heads.find((h) => h.path === '/ucl') as RouteHead;
		const noOgUrl = APP_HTML.replace(/<meta property="og:url"[^>]*>/, '');
		expect(() => applyRouteHead(noOgUrl, ucl)).toThrow(/og:url/);
		const twoTitles = APP_HTML.replace('</title>', '</title><title>x</title>');
		expect(() => applyRouteHead(twoTitles, ucl)).toThrow(/title/);
	});
});

describe('yksi lahde: sivut ja build lukevat samat vakiot', () => {
	it('ucl- ja spl-sivun svelte:head lukee UCL_HEAD/SPL_HEAD eika kirjoita omaa', () => {
		const ucl = blankComments(read('../routes/ucl/+page.svelte'));
		expect(ucl).toContain('<title>{UCL_HEAD.title}</title>');
		expect(ucl).toContain('content={UCL_HEAD.description}');
		expect(ucl).not.toContain(`<title>${UCL_HEAD.title}</title>`);
		const spl = blankComments(read('../routes/spl/+page.svelte'));
		expect(spl).toContain('<title>{SPL_HEAD.title}</title>');
		expect(spl).toContain('content={SPL_HEAD.description}');
	});

	it('build ajaa route-heads.mjs:n, ja se kayttaa taman moduulin muunnosta ja jalkiehtoa', () => {
		const pkg = JSON.parse(read('../../package.json'));
		expect(pkg.scripts.build).toMatch(/vite build && node scripts\/route-heads\.mjs$/);
		const script = read('../../scripts/route-heads.mjs');
		expect(script).toContain("import('../src/lib/routeHeads.ts')");
		expect(script).toMatch(/applyRouteHead\(/);
		expect(script).toMatch(/buildProblems\(/);
	});
});
