import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

/**
 * PORTTI: jokainen tapa jolla checkout voi epaonnistua on mitattava.
 *
 * MITATTU 20.9.2026 (PostHog, 180 vrk): webissa `upgrade_tapped` 20 henkiloa,
 * `checkout_opened` 11. Erotus oli NAKYMATON, koska epaonnistumishaarat
 * palauttivat virheen kayttajalle kirjaamatta tapahtumaa. Emme siis voineet
 * erottaa aitoa epaonnistumista sendBeaconin hukkaamasta tapahtumasta - ja
 * koko historian web-ostot ovat kolme kappaletta, joten 45 %:n aukko
 * viimeisella askeleella ei saa jaada arvaukseksi.
 *
 * Tama testi lukee LAHDEKOODIN, ei kutsu funktiota: kutsuminen vaatisi
 * verkon ja Stripe-sessioiden mockaamisen, ja se mittaisi mockia. Invariantti
 * on yksinkertainen ja luettavissa suoraan: yhtaan "Checkout failed" -paluuta
 * ei ole ilman sita edeltavaa capture('checkout_failed').
 */
const SRC = fileURLToPath(new URL('./billing.ts', import.meta.url));

describe('billing: checkoutin epaonnistuminen on mitattu', () => {
	const koodi = readFileSync(SRC, 'utf8');

	it('jokaista Checkout failed -paluuta kohden on yksi checkout_failed-kirjaus', () => {
		const paluut = koodi.match(/return\s+[`'"]Checkout failed/g) ?? [];
		const kirjaukset = koodi.match(/capture\('checkout_failed'/g) ?? [];
		expect(paluut.length).toBeGreaterThan(0);
		expect(
			kirjaukset.length,
			`${paluut.length} epaonnistumispaluuta mutta ${kirjaukset.length} kirjausta: ` +
				'joku haara palauttaa virheen jattaen sen mittaamatta'
		).toBe(paluut.length);
	});

	it('kirjaus kantaa syyn, ei pelkkaa tapahtumanimea', () => {
		// Ilman syyta tapahtuma kertoisi etta jokin meni pieleen mutta ei mika,
		// ja seuraava sessio joutuisi arvaamaan uudelleen.
		for (const kentta of ['stage:', 'detail:', 'status:']) {
			expect(koodi.includes(kentta), `checkout_failed ei kanna kenttaa ${kentta}`).toBe(true);
		}
	});

	it('checkout_opened lahtee vasta kun Stripe on antanut URLin', () => {
		// Jos se lahtisi ennen fetchia, se mittaisi aikomusta kuten
		// upgrade_tapped, ja koko 20 -> 11 -ero katoaisi nakyvista.
		const url = koodi.indexOf('const { url } = await r.json()');
		const opened = koodi.indexOf("captureBeforeUnload('checkout_opened'");
		expect(url).toBeGreaterThan(-1);
		expect(opened).toBeGreaterThan(url);
	});
});
