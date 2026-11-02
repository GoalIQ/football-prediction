import { describe, it, expect, beforeEach } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	ENTRY_TTL_MS,
	funnelProps,
	funnelStep,
	markEntry,
	currentEntry,
	setEntryStore,
	type EntryStore
} from './funnel';

/**
 * PORTTI: ostoketjun lahde kulkee lukosta ostoon (ulkoasu WP3 / A1, 2.11.2026).
 *
 * Ennen: lukko kirjasi lahteensa, mutta Paywall ja kassa kirjasivat aina
 * 'pro_web' ja osto 'web', joten "mika lukko myi" ei ollut luettavissa.
 * Testit ajavat koko ketjun funktion lapi (ei mockattua posthogia) ja
 * tarkistavat lahdekoodista, etta analytics.ts kutsuu sita molemmissa
 * lahetysreiteissa.
 */

function fakeStore(): EntryStore & { raw: string | null } {
	const s = {
		raw: null as string | null,
		get: () => s.raw,
		set: (v: string) => {
			s.raw = v;
		},
		clear: () => {
			s.raw = null;
		}
	};
	return s;
}

const T0 = 1_800_000_000_000;

describe('funnel: askel tapahtumasta', () => {
	it('lukko, paywall, plan, kassa ja osto erottuvat vaikka nimet ovat vanhat', () => {
		expect(funnelStep('paywall_shown', { source: 'personal_lock', tool: 'captain' })).toBe('lock_view');
		expect(funnelStep('paywall_shown', { source: 'pro_web' })).toBe('paywall_view');
		expect(funnelStep('upgrade_tapped', { source: 'personal_lock_captain' })).toBe('lock_tap');
		expect(funnelStep('upgrade_tapped', { source: 'pro_web', plan: 'season' })).toBe('plan_tap');
		expect(funnelStep('checkout_opened', { source: 'pro_web', plan: 'season' })).toBe('checkout_opened');
		expect(funnelStep('checkout_failed', {})).toBe('checkout_failed');
		expect(funnelStep('checkout_store_only', {})).toBe('checkout_store_only');
		expect(funnelStep('purchase_completed', { source: 'web' })).toBe('purchase');
		expect(funnelStep('xp_card_shared', {})).toBeNull();
	});

	it('ketjun ulkopuolinen tapahtuma palautuu koskematta', () => {
		setEntryStore(fakeStore());
		const p = { a: 1 };
		expect(funnelProps('xp_card_shared', p, T0)).toBe(p);
		expect(funnelProps('pro_page_viewed', undefined, T0)).toBeUndefined();
	});
});

describe('funnel: lahde kulkee lukosta ostoon', () => {
	let store: ReturnType<typeof fakeStore>;
	beforeEach(() => {
		store = fakeStore();
		setEntryStore(store);
	});

	it('lukon napautus -> paywall -> plan -> kassa -> osto kantavat lukon lahteen', () => {
		const view = funnelProps('paywall_shown', { source: 'personal_lock', tool: 'captain' }, T0);
		expect(view?.funnel_step).toBe('lock_view');
		expect(view?.entry_source).toBe('direct');

		funnelProps('upgrade_tapped', { source: 'personal_lock_captain', tool: 'captain' }, T0 + 1);
		const steps = [
			funnelProps('paywall_shown', { source: 'pro_web' }, T0 + 2),
			funnelProps('upgrade_tapped', { source: 'pro_web', plan: 'season' }, T0 + 3),
			funnelProps('checkout_opened', { source: 'pro_web', plan: 'season' }, T0 + 4)
		];
		for (const s of steps) {
			expect(s?.entry_source).toBe('personal_lock_captain');
			expect(s?.entry_tool).toBe('captain');
		}
		// Stripe-redirect = uusi sivulataus: muisti tyhja, sailo jaa.
		setEntryStore(store);
		const buy = funnelProps('purchase_completed', { source: 'web', guest: false }, T0 + 60_000);
		expect(buy?.funnel_step).toBe('purchase');
		expect(buy?.entry_source).toBe('personal_lock_captain');
		expect(buy?.source).toBe('web');
		// Osto tyhjentaa: seuraava osto ei peri vanhaa lahdetta.
		expect(store.raw).toBeNull();
		expect(currentEntry(T0 + 60_001)).toBeNull();
	});

	it('vanhentunut lahde ei kirjaudu oston syyksi', () => {
		funnelProps('upgrade_tapped', { source: 'fantasy_value' }, T0);
		setEntryStore(store);
		const late = funnelProps('purchase_completed', { source: 'web' }, T0 + ENTRY_TTL_MS + 1);
		expect(late?.entry_source).toBe('direct');
	});

	it('kassan avaus virkistaa lahteen, jotta hidas maksaja ei putoa', () => {
		funnelProps('upgrade_tapped', { source: 'fantasy_value' }, T0);
		funnelProps('checkout_opened', { source: 'pro_web', plan: 'monthly' }, T0 + ENTRY_TTL_MS - 10);
		setEntryStore(store);
		const buy = funnelProps('purchase_completed', { source: 'web' }, T0 + ENTRY_TTL_MS + 1000);
		expect(buy?.entry_source).toBe('fantasy_value');
	});

	it('hubin CTA-saapuminen on lahde suoralle kassalle', () => {
		markEntry('src:hero-premium', 'index', T0);
		const tap = funnelProps('upgrade_tapped', { source: 'checkout_route', plan: 'season' }, T0 + 5);
		expect(tap?.entry_source).toBe('src:hero-premium');
		expect(tap?.entry_tool).toBe('index');
	});

	it('lukon napautus korvaa hubin saapumisen (lahempi syy voittaa)', () => {
		markEntry('src:hero-free', 'index', T0);
		funnelProps('upgrade_tapped', { source: 'fantasy_leaders' }, T0 + 5);
		const tap = funnelProps('upgrade_tapped', { source: 'pro_web', plan: 'season' }, T0 + 6);
		expect(tap?.entry_source).toBe('fantasy_leaders');
	});

	it('suora kassa ilman lukkoa ja ilman hubia: lahde on kassan oma source', () => {
		const tap = funnelProps('upgrade_tapped', { source: 'checkout_route', plan: 'season' }, T0);
		expect(tap?.entry_source).toBe('checkout_route');
		const opened = funnelProps('checkout_opened', { source: 'checkout_route', plan: 'season' }, T0 + 1);
		expect(opened?.entry_source).toBe('checkout_route');
	});

	it('rikkinainen tai estetty sailo ei kaada tapahtumaa', () => {
		setEntryStore({
			get: () => '{rikki',
			set: () => {
				throw new Error('QuotaExceeded');
			},
			clear: () => {
				throw new Error('SecurityError');
			}
		});
		const a = funnelProps('upgrade_tapped', { source: 'fantasy_value' }, T0);
		expect(a?.funnel_step).toBe('lock_tap');
		// Muisti kantaa saman sivulatauksen sisalla.
		const b = funnelProps('paywall_shown', { source: 'pro_web' }, T0 + 1);
		expect(b?.entry_source).toBe('fantasy_value');
		expect(() => funnelProps('purchase_completed', {}, T0 + 2)).not.toThrow();
	});

	it('kutsujan oma kentta voittaa', () => {
		const p = funnelProps('paywall_shown', { source: 'pro_web', entry_source: 'x' }, T0);
		expect(p?.entry_source).toBe('x');
	});
});

describe('funnel: kutsupaikat (lahdekoodi)', () => {
	const read = (rel: string) =>
		readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8').replace(/\r\n/g, '\n');

	it('analytics.ts ajaa funnelPropsin seka capture- etta beacon-reitilla', () => {
		const src = read('./analytics.ts');
		const cap = src.slice(src.indexOf('export function capture('), src.indexOf('export function captureBeforeUnload('));
		const bu = src.slice(src.indexOf('export function captureBeforeUnload('), src.indexOf('export function identifyUser('));
		expect(cap).toMatch(/props = funnelProps\(event, props\)/);
		expect(bu).toMatch(/props = funnelProps\(event, props\)/);
	});

	it('layout merkitsee hubin src:n lahteeksi', () => {
		expect(read('../routes/+layout.svelte')).toMatch(/markEntry\(`src:\$\{src\}`/);
	});

	it('mikaan komponentti ei kirjoita entry_sourcea itse (yksi kirjoittaja)', () => {
		const root = fileURLToPath(new URL('..', import.meta.url));
		const offenders: string[] = [];
		const walk = (dir: string) => {
			for (const f of readdirSync(dir)) {
				const p = join(dir, f);
				if (statSync(p).isDirectory()) walk(p);
				else if (/\.(ts|svelte)$/.test(f) && !/\.test\.ts$/.test(f) && !/[\\/]funnel\.ts$/.test(p)) {
					if (/entry_source\s*:/.test(readFileSync(p, 'utf8'))) offenders.push(p);
				}
			}
		};
		walk(root);
		expect(offenders).toEqual([]);
	});
});
