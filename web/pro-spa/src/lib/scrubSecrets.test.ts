/** scrubSecrets: salaisuudet pois, TYYPIT ennallaan.
 *
 * 🔴 MIKSI (22.9): 14.9:n siivous kavi jokaisen olion lapi Object.entriesilla,
 * joten posthog-js:n `timestamp: Date` muuttui `{}`:ksi ja PostHog hylkasi koko
 * lahetyseran 400:lla. Kentalla `$pageleave` putosi 8-18/vrk:sta nollaan 15.9
 * alkaen. Siivoukselle ei ollut yhtaan testia, joten kukaan ei nahnyt etta se
 * muutti muutakin kuin merkkijonoja.
 */
import { describe, expect, it } from 'vitest';
import { REDACTED, scrubSecrets } from './scrubSecrets';

// Koottu paloista, jotta push protection ei lue fikstuuria oikeaksi avaimeksi.
const JWT = ['eyJhbGciOi', 'JIUzI1NiJ9', '.eyJzdWIiOiIxMjMifQ', '.abcDEF_123-xyz'].join('');

describe('scrubSecrets', () => {
	it('sailyttaa Date-aikaleiman Datena (PostHogin timestamp)', () => {
		const ts = new Date('2026-09-22T06:00:00Z');
		const out = scrubSecrets({ event: '$pageleave', timestamp: ts });
		expect(out.timestamp).toBeInstanceOf(Date);
		expect((out.timestamp as Date).toISOString()).toBe('2026-09-22T06:00:00.000Z');
	});

	it('ei muuta sisakkaista Datea tyhjaksi olioksi', () => {
		const out = scrubSecrets({ properties: { $time: new Date(0), list: [new Date(0)] } });
		expect(out.properties.$time).toBeInstanceOf(Date);
		expect(out.properties.list[0]).toBeInstanceOf(Date);
	});

	it('siivoaa tokenin URL:sta', () => {
		const out = scrubSecrets({
			properties: { $current_url: `https://pro.goaliq.app/#access_token=${JWT}&x=1` }
		});
		expect(out.properties.$current_url).toContain(`access_token=${REDACTED}`);
		expect(out.properties.$current_url).not.toContain(JWT);
	});

	it('siivoaa tokenin myos muusta kuin tavallisesta oliosta (ei fail-open)', () => {
		class Box {
			note = `failed with ${JWT}`;
		}
		const out = scrubSecrets({ err: new Box() }) as unknown as { err: { note: string } };
		expect(out.err.note).not.toContain(JWT);
		expect(out.err.note).toContain(REDACTED);
	});

	it('jattaa luvut, totuusarvot ja nullin ennalleen', () => {
		expect(scrubSecrets({ a: 1, b: true, c: null })).toEqual({ a: 1, b: true, c: null });
	});
});
