/**
 * Portti: vanhentuneen HTML:n entry-chunk -vika korjautuu yhdella reloadilla (SPA-VANHA-CHUNK-BOOT, 3.10.2026).
 *
 * Mitattu 2.10 PostHogista (omat pois): 30 vrk:ssa 4 oikeaa web_boot_failed-tapahtumaa
 * 'Failed to fetch dynamically imported module .../_app4/immutable/entry/start.*.js'
 * (3.9, 6.9, 11.9, 18.9): selain ajoi deployta vanhempaa HTML:aa jonka entry-chunkia
 * ei enaa ollut, ja kayttaja jai virheruutuun.
 *
 * Testi AJAA app.html:n inline-vahdin vm-hiekkalaatikossa (ei lahteen regexia), koska
 * mekanismi on ajonaikainen: lukko sessionStoragessa, yksi reload, toinen vika raportoidaan.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { describe, expect, it } from 'vitest';

const APP_HTML = readFileSync(fileURLToPath(new URL('../app.html', import.meta.url)), 'utf-8');

function watchdogSource(): string {
	const at = APP_HTML.indexOf('Boot watchdog');
	const open = APP_HTML.indexOf('<script>', at);
	const close = APP_HTML.indexOf('</script>', open);
	expect(at).toBeGreaterThan(0);
	return APP_HTML.slice(open + '<script>'.length, close);
}

type Beacon = { event: string; properties: Record<string, unknown> };

function boot(store: Map<string, string>, opts: { storageThrows?: boolean } = {}) {
	const listeners: Record<string, ((ev: unknown) => void)[]> = {};
	const beacons: Beacon[] = [];
	const timers: (() => void)[] = [];
	let reloads = 0;
	const storage = {
		getItem: (k: string) => {
			if (opts.storageThrows) throw new Error('SecurityError');
			return store.get(k) ?? null;
		},
		setItem: (k: string, v: string) => {
			if (opts.storageThrows) throw new Error('SecurityError');
			store.set(k, v);
		}
	};
	const sandbox: Record<string, unknown> = {
		addEventListener: (t: string, fn: (ev: unknown) => void) => (listeners[t] ??= []).push(fn),
		removeEventListener: () => {},
		sessionStorage: storage,
		localStorage: { getItem: () => null },
		location: { hostname: 'pro.goaliq.app', href: 'https://pro.goaliq.app/', reload: () => reloads++ },
		navigator: {
			sendBeacon: (_url: string, blob: Blob) => {
				void blob.text().then((t) => beacons.push(JSON.parse(t)));
				return true;
			}
		},
		document: { getElementById: () => null, readyState: 'complete' },
		setTimeout: (fn: () => void) => timers.push(fn),
		clearTimeout: () => {},
		Blob
	};
	sandbox.window = sandbox;
	vm.runInNewContext(watchdogSource(), sandbox);
	const fire = (type: string, ev: unknown) => (listeners[type] ?? []).forEach((fn) => fn(ev));
	return {
		reject: (msg: string) => fire('unhandledrejection', { reason: new TypeError(msg) }),
		error: (msg: string) => fire('error', { error: new Error(msg), message: msg }),
		fireTimer: () => timers.forEach((fn) => fn()),
		reloads: () => reloads,
		earlyErrors: () => (sandbox.__goaliqEarlyErrors as unknown[]).length,
		beacons: async () => {
			await new Promise((r) => setTimeout(r, 10));
			return beacons;
		}
	};
}

const ENTRY =
	'Failed to fetch dynamically imported module: https://pro.goaliq.app/_app4/immutable/entry/start.CqUZNksv.js';

describe('boot-vahti: vanhentunut entry-chunk', () => {
	it('ensimmainen vika -> yksi reload ja oma tapahtuma, ei boot_failed-puskuria', async () => {
		const page = boot(new Map());
		page.reject(ENTRY);
		expect(page.reloads()).toBe(1);
		expect(page.earlyErrors()).toBe(0);
		const b = await page.beacons();
		expect(b.map((x) => x.event)).toEqual(['web_boot_stale_reload']);
		expect(b[0].properties.first_error).toBe(ENTRY);
	});

	it('toinen vika minuutin sisalla -> ei silmukkaa, raportoidaan web_boot_failed', async () => {
		const store = new Map<string, string>();
		boot(store).reject(ENTRY);
		const second = boot(store);
		second.reject(ENTRY);
		expect(second.reloads()).toBe(0);
		expect(second.earlyErrors()).toBe(1);
		second.fireTimer();
		const b = await second.beacons();
		expect(b.map((x) => x.event)).toEqual(['web_boot_failed']);
		expect(b[0].properties.after_stale_reload).toBe(true);
	});

	it('vanha lukko (yli minuutti) ei esta uutta reloadia seuraavan deployn jalkeen', () => {
		const store = new Map([['giq_stale_chunk_reload', String(Date.now() - 5 * 60_000)]]);
		const page = boot(store);
		page.reject(ENTRY);
		expect(page.reloads()).toBe(1);
	});

	it('Safarin muotoilu tunnistetaan', () => {
		const page = boot(new Map());
		page.reject('Importing a module script failed.');
		expect(page.reloads()).toBe(1);
	});

	it('muu virhe ei reloadaa', () => {
		const page = boot(new Map());
		page.error("Cannot read properties of undefined (reading 'id')");
		page.reject('NetworkError when attempting to fetch resource.');
		expect(page.reloads()).toBe(0);
		expect(page.earlyErrors()).toBe(2);
	});

	it('ilman sessionStoragea ei reloadata (lukoton reload voisi toistua loputtomiin)', () => {
		const page = boot(new Map(), { storageThrows: true });
		page.reject(ENTRY);
		expect(page.reloads()).toBe(0);
		expect(page.earlyErrors()).toBe(1);
	});
});
