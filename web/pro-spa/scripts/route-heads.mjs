/** Reittikohtaiset headit buildin jalkeen (22.9, web-audit T6).
 *
 * Yleistaa 7.8:n fix-spl-head.mjs:n reittitaulukoksi. Taulukko ja muunnos
 * ovat `src/lib/routeHeads.ts`:ssa (sama lukija jota sivut ja vitest-portti
 * kayttavat); tama skripti vain lukee buildin, kirjoittaa tiedostot ja
 * mittaa lopputuloksen levylta.
 *
 *   - Fallback-reitit (/ucl, /week, /players, /players/player-xp, ...):
 *     build/index.html kopioidaan build/<polku>.html:ksi ja head vaihdetaan.
 *     Cloudflare Pages tarjoilee `players/player-xp.html`:n osoitteessa
 *     `/players/player-xp`. Kuori viittaa assetteihin absoluuttisesti
 *     (`/_app4/...`), joten sama tiedosto toimii missa tahansa syvyydessa;
 *     jalkitarkistus kaataa buildin jos niin ei ole.
 *   - Prerenderoitu /spl: templaatin title ja description poistetaan (sivu
 *     tuo omansa), og/twitter-tagit vaihdetaan SPL:n omiin.
 *
 * FAIL-CLOSED: jokainen korvaus osuu tasan kerran tai build kaatuu (exit 1).
 * Hiljainen puolikorjaus olisi sama vika jota tama korjaa.
 *
 * Ajetaan Noden tyyppien riisunnalla (`.ts`-import): Node 22.18+ / 23.6+.
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const fail = (msg) => {
	console.error(`route-heads: ${msg}`);
	process.exit(1);
};

let mod;
try {
	mod = await import('../src/lib/routeHeads.ts');
} catch (e) {
	fail(
		`src/lib/routeHeads.ts ei latautunut (${e?.code ?? e}). Node ${process.version}: ` +
			'tarvitaan 22.18+ tai 23.6+ (TypeScript-tyyppien riisunta ilman lippua).'
	);
}
const { routeHeads, applyRouteHead, buildProblems, readHead, routeFile } = mod;

// 22.9 (A3): vanhojen polkujen 301 palvelimella. Sama lahde kuin portissa
// (src/lib/legacyPaths.ts), joten kartta ja tiedosto eivat voi erota.
let legacy;
try {
	legacy = await import('../src/lib/legacyPaths.ts');
} catch (e) {
	fail(`src/lib/legacyPaths.ts ei latautunut (${e?.code ?? e})`);
}

const BUILD = fileURLToPath(new URL('../build/', import.meta.url));
const INDEX = `${BUILD}index.html`;
if (!existsSync(INDEX)) fail('build/index.html puuttuu (aja vite build ensin)');
const shell = readFileSync(INDEX, 'utf8');

// Kuoren assetit on viitattava absoluuttisesti, muuten syvempi kopio
// (players/player-xp.html) hakisi ne vaarasta hakemistosta.
if (/(src|href)="\.\.?\//.test(shell)) fail('index.html viittaa assetteihin suhteellisesti');
if (!/import\("\/_app\d*\//.test(shell) && !/href="\/_app\d*\//.test(shell))
	fail('index.html:sta ei loytynyt absoluuttista /_app-viittausta');

const heads = routeHeads();
const written = [];
for (const head of heads) {
	const rel = routeFile(head.path);
	const file = `${BUILD}${rel}`;
	let src;
	if (head.prerendered) {
		if (!existsSync(file)) fail(`${rel} puuttuu, vaikka reitti on merkitty prerenderoiduksi`);
		src = readFileSync(file, 'utf8');
	} else {
		// Ei koskaan kirjoiteta prerenderoidun sivun paalle.
		if (existsSync(file)) fail(`${rel} on jo olemassa: prerenderoitu sivu? merkitse prerendered`);
		src = shell;
	}
	let out;
	try {
		out = applyRouteHead(src, head);
	} catch (e) {
		fail(e.message);
	}
	mkdirSync(dirname(file), { recursive: true });
	writeFileSync(file, out);
	written.push({ head, rel });
}

// --- Jalkitarkistus LEVYLTA, ei muistista -------------------------------
// Sama predikaatti kuin vitest-portissa (routeHeads.gate.test.ts).
const served = new Map(written.map(({ head, rel }) => [head.path, readFileSync(`${BUILD}${rel}`, 'utf8')]));
const problems = buildProblems(served, heads);
// Fallback (juuri + tuntemattomat polut) pysyy templaatin mukaisena.
if (readFileSync(INDEX, 'utf8') !== shell) problems.push('index.html muuttui');
if (problems.length) fail(`jalkitarkistus kaatui:\n  ${problems.join('\n  ')}`);

// --- _redirects (Cloudflare Pages) -----------------------------------------
// Fail-closed: kasin kirjoitettu static/_redirects ohitettaisiin hiljaa, joten
// olemassa oleva tiedosto kaataa buildin. Jalkitarkistus luetaan levylta.
const REDIRECTS = `${BUILD}_redirects`;
if (existsSync(REDIRECTS)) fail('build/_redirects on jo olemassa (static/?): generoidaan legacyPaths.ts:sta');
const redirects = legacy.redirectsFile();
writeFileSync(REDIRECTS, redirects);
if (readFileSync(REDIRECTS, 'utf8') !== redirects) fail('_redirects: levylla eri sisalto');
for (const r of legacy.redirectRules()) {
	if (served.has(r.from)) fail(`_redirects: ${r.from} varjostaisi reitin jolla on oma head`);
	if (existsSync(`${BUILD}${routeFile(r.from)}`)) fail(`_redirects: ${r.from} varjostaisi tiedoston`);
}

const titles = new Set([...served.values()].map((h) => readHead(h).titles[0]));
console.log(
	`route-heads: OK (${written.length} reittia, ${titles.size} eri titlea, /ucl = "${readHead(served.get('/ucl')).titles[0]}", _redirects ${legacy.redirectRules().length} saantoa)`
);
