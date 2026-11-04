import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, relative } from 'node:path';
import {
	SEASON_PASS_PLAN,
	formatPassEnd,
	isPassPlan,
	passEnd,
	passHolderNote,
	paywallTerms,
	planTerms,
	seasonHint,
	seasonLabel
} from './seasonPass';

/**
 * PORTTI (WP6 copy-synkka, 4.11.2026): vuosipaketin teksti ja veloitus eivat
 * voi olla eri mielta.
 *
 * Kytkin on Renderin STRIPE_PRICE_SEASON_PASS_2026_27. SPA lukee tilan samasta
 * /api/web/pricing-vastauksesta kuin hinnan (`billing: "one_time"` +
 * `access_until`), joten SPA:n voi deployata ennen kytkinta: ilman kenttia
 * jokainen pinta sanoo tasan saman kuin ennen. Kolme asiaa mitataan:
 *  1. kytkin pois = entinen teksti sanatarkasti,
 *  2. passiteksti ei sano tilauksen sanoja ja nimeaa paivan,
 *  3. yksikaan pinta ei kirjoita vuosipaketin ehtoja kasin (kutsupaikkaportti).
 */
const LIB = fileURLToPath(new URL('.', import.meta.url));
const SRC = join(LIB, '..');
const REPO = join(SRC, '..', '..', '..');
const read = (p: string) => readFileSync(p, 'utf8');

const PASSI = { billing: 'one_time', access_until: '2027-05-30T23:59:59+00:00' };

describe('seasonPass: tila luetaan hintavastauksesta', () => {
	it('ilman passikenttia ei ole passia (= entinen tilausteksti)', () => {
		expect(passEnd(undefined)).toBeNull();
		expect(passEnd(null)).toBeNull();
		expect(passEnd({})).toBeNull();
		// Tamanhetkinen tuotannon vastaus (4.11): season-rivilla ei billing-kenttaa.
		expect(passEnd({ amount: 25, currency: 'EUR', tier: 'default' } as never)).toBeNull();
	});

	it('pelkka billing ilman luettavaa paivaa ei riita', () => {
		expect(passEnd({ billing: 'one_time' })).toBeNull();
		expect(passEnd({ billing: 'one_time', access_until: 'not a date' })).toBeNull();
		expect(passEnd({ billing: 'recurring', access_until: PASSI.access_until })).toBeNull();
	});

	it('paiva on UTC:n paiva eika katsojan kellon', () => {
		// 23:59:59 UTC on Suomessa jo 31.5. Passi paattyy 30.5.
		expect(passEnd(PASSI)).toBe('30 May 2027');
		expect(formatPassEnd('2027-05-30T23:59:59+00:00')).toBe('30 May 2027');
	});

	it('plan-tunniste ja loppuhetki ovat samat kuin palvelimen lahteessa', () => {
		const py = read(join(REPO, 'src', 'season_pass.py'));
		const id = py.match(/^SEASON_PASS_ID\s*=\s*"([^"]+)"/m)?.[1];
		expect(id).toBe(SEASON_PASS_PLAN);
		const end = py.match(/^SEASON_PASS_END\s*=\s*datetime\((\d+),\s*(\d+),\s*(\d+),\s*23,\s*59,\s*59/m);
		expect(end).not.toBeNull();
		const iso = `${end![1]}-${end![2].padStart(2, '0')}-${end![3].padStart(2, '0')}T23:59:59+00:00`;
		expect(formatPassEnd(iso)).toBe(passEnd(PASSI));
		expect(isPassPlan(SEASON_PASS_PLAN)).toBe(true);
		expect(isPassPlan('season')).toBe(false);
		expect(isPassPlan(undefined)).toBe(false);
	});
});

describe('seasonPass: kytkin pois = tasan entinen teksti', () => {
	// Sanatarkat lauseet ennen 4.11 (billing.ts, Paywall, PremiumPreview,
	// ProductIntro, /checkout). Jos naita muutetaan, se on copy-muutos joka
	// kulkee julkaisutarkistajan lapi, ei sivuvaikutus.
	it('vuosinappi, vihje ja ehdot', () => {
		expect(seasonLabel('25 €', null)).toBe('Season pass: 25 € a year');
		expect(seasonHint(null)).toBe(
			'One subscription covers web, iOS and Android. Cancel anytime from the Account menu.'
		);
		expect(planTerms(null)).toBe(
			'Cancel anytime from the Account menu. One subscription covers web, iOS and Android.'
		);
		expect(paywallTerms(null)).toBe(
			'Both plans renew until you cancel, and you can cancel from the Account menu. One subscription covers web, iOS and Android.'
		);
	});
});

describe('seasonPass: passiteksti ei lupaa tilausta', () => {
	const end = passEnd(PASSI);
	const tekstit = {
		label: seasonLabel('25 €', end),
		hint: seasonHint(end),
		terms: planTerms(end),
		paywall: paywallTerms(end),
		holder: passHolderNote(PASSI.access_until)
	};
	// Vuosipaketin tilaussanat. "renews until you cancel" saa esiintya vain
	// kuukausipaketista, joten se tarkistetaan erikseen alla.
	const KIELLETYT = [/a year/i, /\/year/i, /annual/i, /both plans renew/i, /one subscription/i, /cancel anytime/i];

	for (const [nimi, t] of Object.entries(tekstit)) {
		it(`${nimi}: ei tilauksen sanoja`, () => {
			for (const k of KIELLETYT) expect(t, `${nimi} sisaltaa ${k}`).not.toMatch(k);
		});
	}

	it('nappi ja ehdot nimeavat loppupaivan', () => {
		for (const t of [tekstit.label, tekstit.terms, tekstit.paywall, tekstit.holder]) {
			expect(t).toContain('30 May 2027');
		}
	});

	it('uusiutuminen sanotaan vain kuukausipaketista', () => {
		const lauseet = tekstit.terms.split(/(?<=\.)\s+/);
		for (const l of lauseet.filter((x) => /renew/i.test(x))) {
			expect(l, `uusiutumislause ilman kuukausipakettia: ${l}`).toMatch(/monthly/i);
		}
	});

	it('passin ostaneelle ei luvata peruttavaa', () => {
		expect(tekstit.holder).toMatch(/nothing to cancel/);
		expect(tekstit.holder).not.toMatch(/Manage subscription/);
	});
});

describe('seasonPass: kutsupaikat (yksikaan pinta ei kirjoita ehtoja kasin)', () => {
	function lahteet(dir: string): string[] {
		const ulos: string[] = [];
		for (const n of readdirSync(dir)) {
			const p = join(dir, n);
			if (statSync(p).isDirectory()) ulos.push(...lahteet(p));
			else if (/\.(svelte|ts)$/.test(n) && !/\.test\.ts$/.test(n)) ulos.push(p);
		}
		return ulos;
	}
	const OMAT = new Set([join(LIB, 'seasonPass.ts')]);
	// Lauseet jotka ovat vain tilauksesta tosia. Ne saa kirjoittaa VAIN
	// seasonPass.ts:aan, joka valitsee niiden ja passitekstin valilla.
	const TILAUSLAUSEET = [
		'Both plans renew',
		'One subscription covers',
		'Cancel anytime from the Account menu',
		"a year'",
		'a year`',
		'/year'
	];

	it('tilauslauseet asuvat vain lukijassa', () => {
		const loydot: string[] = [];
		for (const p of lahteet(SRC)) {
			if (OMAT.has(p)) continue;
			const c = read(p);
			for (const l of TILAUSLAUSEET) {
				// billing.ts:n kommentit kuvaavat vanhaa vikaa; vain koodi mitataan.
				const koodi = c.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '').replace(/<!--[\s\S]*?-->/g, '');
				if (koodi.includes(l)) loydot.push(`${relative(SRC, p)}: ${l}`);
			}
		}
		expect(loydot).toEqual([]);
	});

	const pinnat: Array<[string, string, RegExp]> = [
		['Paywall', 'lib/components/Paywall.svelte', /paywallTerms\(seasonPassEnd\(\)\)/],
		['PremiumPreview', 'lib/components/PremiumPreview.svelte', /planTerms\(seasonPassEnd\(\)\)/],
		['ProductIntro', 'lib/components/ProductIntro.svelte', /planTerms\(seasonPassEnd\(\)\)/],
		['/checkout', 'routes/checkout/+page.svelte', /planTerms\(seasonPassEnd\(\)\)/],
		['pricing', 'lib/pricing.svelte.ts', /seasonLabel\(raha\(h\), seasonPassEnd\(\)\)/],
		['Hero', 'lib/components/Hero.svelte', /passHolderNote\(auth\.sub\?\.current_period_end\)/]
	];
	for (const [nimi, polku, kutsu] of pinnat) {
		it(`${nimi} kutsuu lukijaa`, () => {
			expect(read(join(SRC, polku))).toMatch(kutsu);
		});
	}

	it('/checkout hakee hintavastauksen (muuten passitila ei koskaan nay siella)', () => {
		expect(read(join(SRC, 'routes/checkout/+page.svelte'))).toContain('void loadPricing()');
	});

	it('vuosinapin vihje ja likiarvo lukevat passitilan joka napissa', () => {
		for (const polku of [
			'lib/components/Paywall.svelte',
			'lib/components/PremiumPreview.svelte',
			'lib/components/LockedToolPreview.svelte'
		]) {
			const c = read(join(SRC, polku));
			expect(c, polku).toContain('planHint(key as PlanKey)');
			expect(c, polku).toContain('planApprox(key as PlanKey, seasonPassEnd() !== null)');
			expect(c, polku).not.toMatch(/plan\.hint/);
		}
		expect(read(join(SRC, 'lib/components/ProductIntro.svelte'))).toContain(
			"planApprox('season', seasonPassEnd() !== null)"
		);
	});

	it('Hero: passin ostaja ei saa Manage subscription -nappia', () => {
		const c = read(join(SRC, 'lib/components/Hero.svelte'));
		expect(c).toMatch(/const passHolder = \$derived\(isPassPlan\(auth\.sub\?\.plan\)\)/);
		const webSub = c.slice(c.indexOf('const webSub = $derived('), c.indexOf('async function manageSubscription'));
		expect(webSub).toContain('!passHolder');
	});
});
