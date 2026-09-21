/**
 * PALUU GOALIQ.APPIIN JOKAISELTA REITILTA (Villen havainto 21.9.2026).
 *
 * 11.9 sama vika korjattiin ylapalkkiin (Hero.svelte `a.home`), mutta korjaus
 * asui AppShellissa. Reitit jotka eivat kayta AppShellia (/spl, ja 21.9 uusi
 * /ucl) jaivat ilman suoraa paluuta ilmaispinnalle - ja juuri niille tullaan
 * goaliq.appista. Korjaus yhteen paikkaan ei suojannut seuraavaa reittia.
 *
 * Portti: jokainen `routes/**\/+page.svelte` joko renderoi AppShellin (jonka
 * Hero kantaa linkin) tai sisaltaa itse suoran linkin `https://goaliq.app`-
 * juureen. Uusi reitti ei paase lapi vahingossa: se joko saa linkin tai
 * joutuu POIKKEUKSET-listalle syyn kanssa, ja syy nakyy diffissa.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { blankComments } from './sourceScan';

const ROUTES = fileURLToPath(new URL('../routes/', import.meta.url));
const HERO = fileURLToPath(new URL('./components/Hero.svelte', import.meta.url));

/** Juureen osoittava linkki: `https://goaliq.app` ilman polkua. Polullinen
 *  (`/privacy.html`, `/ucl/`) ei ole paluu ilmaispinnalle vaan yksi sivu. */
const JUURI = /href="https:\/\/goaliq\.app\/?"/;

const POIKKEUKSET: Record<string, string> = {
	'checkout/+page.svelte':
		'maksuvirta: linkkaa Pro-etusivulle ("Back to GoalIQ Premium on the web"), ' +
		'jonka ylapalkissa goaliq.app on; poistumislinkki ei kilpaile ostonapin kanssa',
	'creator/+page.svelte':
		'luojan kirjautunut hallintasivu, ei kavijapinta: sinne tullaan goaliq.app/creatorsista ' +
		'ja sivun linkkilistassa on goaliq.app-etusivu (Front page)',
	'dev-premium/+page.svelte': 'kehittajan esikatselu, ei julkinen reitti',
	'embed/fdr/+page.svelte':
		'upotus kolmannen osapuolen sivulle iframeen: ainoa linkki vie Pro-sivulle ' +
		'attribuutiolla (?src=embed), paluu goaliq.appiin ei ole lukijan konteksti'
};

function sivut(dir: string): string[] {
	const out: string[] = [];
	for (const n of readdirSync(dir)) {
		const p = join(dir, n);
		if (statSync(p).isDirectory()) out.push(...sivut(p));
		else if (n === '+page.svelte') out.push(relative(ROUTES, p).replace(/\\/g, '/'));
	}
	return out.sort();
}

function koodi(rel: string): string {
	return blankComments(readFileSync(join(ROUTES, rel), 'utf-8'));
}

describe('paluu goaliq.appiin', () => {
	const kaikki = sivut(ROUTES);

	it('kontrolli: reittilista ei ole tyhja ja sisaltaa AppShell- ja erillisreitit', () => {
		expect(kaikki).toContain('+page.svelte');
		expect(kaikki).toContain('ucl/+page.svelte');
		expect(kaikki).toContain('spl/+page.svelte');
	});

	it('kontrolli: AppShellin Hero kantaa juurilinkin (muuten AppShell ei ole peruste)', () => {
		expect(JUURI.test(blankComments(readFileSync(HERO, 'utf-8')))).toBe(true);
	});

	it('kontrolli: polullinen goaliq.app-linkki ei kelpaa paluuksi', () => {
		expect(JUURI.test('<a href="https://goaliq.app/privacy.html">Privacy</a>')).toBe(false);
		expect(JUURI.test('<a href="https://goaliq.app/ucl/">goaliq.app/ucl</a>')).toBe(false);
		expect(JUURI.test('<a href="https://goaliq.app" data-cta="pro-home">goaliq.app</a>')).toBe(true);
	});

	it.each(kaikki)('%s: AppShell tai suora linkki goaliq.appiin', (rel) => {
		if (rel in POIKKEUKSET) return;
		const src = koodi(rel);
		const shell = /<AppShell\b/.test(src);
		expect(
			shell || JUURI.test(src),
			`${rel}: reitilta ei paase suoraan goaliq.appiin. Lisaa murupolkuun ` +
				`<a href="https://goaliq.app" data-cta="pro-home">goaliq.app</a> tai ` +
				`POIKKEUKSET-listalle syyn kanssa.`
		).toBe(true);
	});

	it('poikkeuslistalla ei ole kuolleita riveja', () => {
		for (const rel of Object.keys(POIKKEUKSET)) expect(kaikki).toContain(rel);
	});
});
