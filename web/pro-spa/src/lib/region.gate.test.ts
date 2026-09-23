import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	REGION_STORE_ONLY,
	STORE_ONLY_ACCOUNT_NOTE,
	STORE_ONLY_COPY,
	isStoreOnlyBody,
	pricingBlocksWebCheckout
} from './region';
import { STORE_URL } from './appHandoff';

/**
 * PORTTI: UK-kavija ei nae Stripe-nappia, eika ohjaus ole umpikuja (23.9.2026).
 *
 * Ratkaiseva esto on backendissa (`tests/test_uk_store_only.py`). Tama portti
 * vartioi SPA:n puolta: jokainen ostopinta vaihtaa napit kauppailmoitukseen,
 * ja yksikaan komponentti ei kutsu `startCheckout`ia ohi `openCheckout`in
 * (suora kutsu nayttaisi koodin `region_app_store_only` virhebannerissa).
 */
const LIB = fileURLToPath(new URL('.', import.meta.url));
const SRC = fileURLToPath(new URL('..', import.meta.url));
const REPO = fileURLToPath(new URL('../../../../', import.meta.url));
const read = (p: string) => readFileSync(p, 'utf8');

function walk(dir: string): string[] {
	return readdirSync(dir).flatMap((n) => {
		const p = join(dir, n);
		return statSync(p).isDirectory() ? walk(p) : [p];
	});
}

describe('region: lukijat', () => {
	it('tunnistaa checkoutin alue-eston rungosta', () => {
		expect(isStoreOnlyBody({ error: 'region_app_store_only', country: 'GB' })).toBe(true);
		expect(isStoreOnlyBody({ detail: 'Stripe error' })).toBe(false);
		expect(isStoreOnlyBody({ error: 'something_else' })).toBe(false);
		expect(isStoreOnlyBody(null)).toBe(false);
		expect(isStoreOnlyBody('region_app_store_only')).toBe(false);
	});

	it('hintavastaus sulkee vain eksplisiittisella false-arvolla', () => {
		expect(pricingBlocksWebCheckout({ country: 'GB', web_checkout: false })).toBe(true);
		expect(pricingBlocksWebCheckout({ country: 'FI', web_checkout: true })).toBe(false);
		// Vanha backend ilman kenttaa, tai tyhja vastaus: napit jaavat.
		expect(pricingBlocksWebCheckout({ country: 'GB', plans: {} })).toBe(false);
		expect(pricingBlocksWebCheckout({})).toBe(false);
		expect(pricingBlocksWebCheckout(null)).toBe(false);
	});
});

describe('region: SPA ja backend sanovat saman', () => {
	it('virhekoodi on sama merkkijono kuin backendissa', () => {
		const py = read(join(REPO, 'src', 'regional_pricing.py'));
		expect(py).toContain(`REGION_STORE_ONLY_ERROR = "${REGION_STORE_ONLY}"`);
	});

	it('backendin detail-teksti on sama lause kuin ilmoituksessa', () => {
		// Vanha valimuistissa oleva SPA nayttaa detailin sellaisenaan.
		const py = read(join(REPO, 'api', 'main.py'));
		expect(py).toContain(`"${STORE_ONLY_COPY}"`);
	});
});

describe('region: ostopinnat', () => {
	it('yksikaan komponentti tai reitti ei kutsu startCheckoutia suoraan', () => {
		const sallitut = new Set([join(LIB, 'billing.ts'), join(LIB, 'pricing.svelte.ts')]);
		const rikkojat = walk(SRC)
			.filter((p) => /\.(svelte|ts)$/.test(p) && !p.endsWith('.test.ts'))
			.filter((p) => !sallitut.has(p))
			.filter((p) => /\bstartCheckout\b/.test(read(p)));
		expect(rikkojat, 'kayta openCheckoutia ($lib/pricing.svelte)').toEqual([]);
	});

	const PINNAT = [
		join(LIB, 'components', 'Paywall.svelte'),
		join(LIB, 'components', 'PremiumPreview.svelte'),
		join(LIB, 'components', 'LockedToolPreview.svelte'),
		join(SRC, 'routes', 'checkout', '+page.svelte')
	];
	for (const p of PINNAT) {
		it(`${p.split(/[\\/]/).slice(-2).join('/')} vaihtaa napit kauppailmoitukseen`, () => {
			const c = read(p);
			expect(c).toContain('openCheckout(');
			expect(c).toContain('webCheckoutBlocked()');
			expect(c).toContain('<StoreOnlyNotice');
		});
	}

	it('billing: alue-esto palauttaa koodin ja kirjaa oman tapahtumansa ennen virhepolkua', () => {
		const c = read(join(LIB, 'billing.ts'));
		const esto = c.indexOf('isStoreOnlyBody(body)');
		const kirjaus = c.indexOf("capture('checkout_store_only'");
		const paluu = c.indexOf('return REGION_STORE_ONLY;');
		const virhe = c.indexOf("capture('checkout_failed'");
		expect(esto).toBeGreaterThan(-1);
		expect(kirjaus).toBeGreaterThan(esto);
		expect(paluu).toBeGreaterThan(kirjaus);
		expect(virhe).toBeGreaterThan(paluu);
	});
});

describe('region: etusivun ProductIntro', () => {
	const src = read(join(LIB, 'components', 'ProductIntro.svelte'));
	const markup = src.slice(src.lastIndexOf('</script>'));
	const alku = markup.indexOf('{#if webCheckoutBlocked()}');
	const ikkuna = markup.indexOf('{:else if inWindow}');
	const muu = markup.indexOf('{:else}', ikkuna);
	const loppu = markup.indexOf('{/if}', markup.indexOf('One subscription covers', muu));

	it('hakee saman maatiedon kuin muut ostopinnat', () => {
		expect(src).toContain('void loadPricing()');
		expect(src).toMatch(/import \{ loadPricing, webCheckoutBlocked \} from '\$lib\/pricing\.svelte'/);
	});

	it('UK-haara on ensimmainen ja siina ei ole verkkohintaa eika See plans -nappia', () => {
		expect(alku).toBeGreaterThan(-1);
		expect(ikkuna).toBeGreaterThan(alku);
		const uk = markup.slice(alku, ikkuna);
		expect(uk).toContain('<StoreOnlyNotice');
		// Lyhyt muoto: intro on CTA-pinta, upgrade-nakyma nayttaa taydet napit.
		expect(uk).toContain('compact');
		expect(uk).not.toMatch(/[€£$]|See plans|approx/);
		// Yksikaan hintamaininta ei ole ennen UK-haaraa (se nakyisi kaikille).
		expect(markup.indexOf('€')).toBeGreaterThan(ikkuna);
	});

	it('FI/US-nakyma on ennallaan', () => {
		expect(muu).toBeGreaterThan(ikkuna);
		const perus = markup.slice(muu, loppu);
		expect(perus).toContain(
			'<button type="button" class="primary" onclick={onUpgrade}>See plans</button>'
		);
		expect(perus).toContain('€3.99 a month or €25 for the season{#if approxMonthly}');
		expect(perus).toContain(
			'({approxMonthly}, {approxSeason}){/if}. Cancel anytime from the Account menu.'
		);
		expect(perus).toContain('One subscription covers');
	});
});

describe('region: ilmoitus ei ole umpikuja', () => {
	it('molemmat kaupat linkitetaan', () => {
		const c = read(join(LIB, 'components', 'StoreOnlyNotice.svelte'));
		// Molemmat muodot (taysi ja compact) linkittavat kummankin kaupan.
		expect(c.match(/STORE_URL\[store\]/g)?.length).toBe(2);
		expect(c.match(/\{STORE_ONLY_COPY\}/g)?.length).toBe(2);
		expect(c).toMatch(/\['ios', 'android'\]/);
		expect(c).toMatch(/\['android', 'ios'\]/);
		expect(STORE_URL.ios).toMatch(/^https:\/\/apps\.apple\.com\/app\/id\d+$/);
		expect(STORE_URL.android).toContain('id=com.veikkoville.goaliq');
	});

	it('copy: englanti, ei em dashia eika kaarevia lainausmerkkeja, tuote on Premium', () => {
		for (const t of [STORE_ONLY_COPY, STORE_ONLY_ACCOUNT_NOTE]) {
			expect(t).not.toMatch(/[—‘’“”]/);
			expect(t).not.toMatch(/[äöå]/i);
			expect(t).not.toMatch(/\bPro\b/);
		}
		expect(STORE_ONLY_COPY).toContain('App Store');
		expect(STORE_ONLY_COPY).toContain('Google Play');
	});
});
