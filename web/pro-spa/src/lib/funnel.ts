/** Web-ostoketjun lahde ja askel (ulkoasu WP3 / auditoinnin A1, 2.11.2026).
 *
 * MITATTU VIKA: lukko kirjasi `paywall_shown {source: 'personal_lock', tool}`
 * ja napautus `upgrade_tapped {source: 'personal_lock_<tool>'}`, mutta sen
 * jalkeen avautuva Paywall kirjasi `paywall_shown {source: 'pro_web'}` ja
 * kassa `upgrade_tapped / checkout_opened {source: 'pro_web'}`. Osto
 * (`purchase_completed {source: 'web'}`) ei tiennyt mista lukosta kayttaja
 * tuli. Ketju lock_view -> lock_tap -> paywall -> plan -> checkout -> purchase
 * katkesi heti lukon jalkeen, joten B-vaiheen lukkokokeita ei voisi lukea.
 * Lisaksi samat kaksi tapahtumanimea tarkoittivat kahta eri askelta.
 *
 * KORJAUS YHDESSA PAIKASSA (CLAUDE.md 6a): `analytics.capture` ajaa jokaisen
 * tapahtuman `funnelProps`-funktion lapi. Komponentit eivat muista mitaan:
 *   - `funnel_step` paatellaan tapahtumasta, joten askeleet erottuvat ilman
 *     etta vanhat tapahtumanimet muuttuvat (historiavertailu sailyy, ks.
 *     billing.ts: hinta ja nimet pysyvat analytiikassa samoina).
 *   - lukon / CTA:n napautus (`upgrade_tapped` ilman planin nimea) tallentaa
 *     lahteen, ja jokainen myohempi ketjun tapahtuma saa `entry_source` +
 *     `entry_tool`. Hubista tultaessa lahde on `hub:<data-cta>` (+layout).
 *   - lahde sailyy Stripe-redirectin yli (localStorage, 2 h) ja tyhjenee
 *     ostoon.
 *
 * Puhdas moduuli + selainsailo injektoitavana: funnel.gate.test.ts. */

export type FunnelStep =
	| 'lock_view'
	| 'lock_tap'
	| 'paywall_view'
	| 'plan_tap'
	| 'checkout_opened'
	| 'checkout_failed'
	| 'checkout_store_only'
	// 2.11 (WP6): kausipassin esto Premium-tilille (billing.ts)
	| 'checkout_already_premium'
	| 'purchase';

/** Paywall.svelten oma lahde: TAMA on paywall-nakyma, kaikki muut ovat lukkoja. */
export const PAYWALL_SOURCE = 'pro_web';

/** Lahde vanhenee: vanha napautus ei saa kirjautua viikon paasta tulevan oston syyksi. */
export const ENTRY_TTL_MS = 2 * 60 * 60 * 1000;

const KEY = 'giq_funnel_entry_v1';

export type FunnelEntry = { source: string; tool: string | null; at: number };

export interface EntryStore {
	get(): string | null;
	set(v: string): void;
	clear(): void;
}

function browserStore(): EntryStore | null {
	try {
		if (typeof localStorage === 'undefined') return null;
		return {
			get: () => localStorage.getItem(KEY),
			set: (v) => localStorage.setItem(KEY, v),
			clear: () => localStorage.removeItem(KEY)
		};
	} catch {
		return null;
	}
}

let store: EntryStore | null | undefined;
let memory: FunnelEntry | null = null;

/** Testeille: vaihda sailo (null = vain muisti). */
export function setEntryStore(s: EntryStore | null): void {
	store = s;
	memory = null;
}

function getStore(): EntryStore | null {
	if (store === undefined) store = browserStore();
	return store;
}

function readEntry(now: number): FunnelEntry | null {
	let e = memory;
	if (e == null) {
		try {
			const raw = getStore()?.get();
			if (raw) {
				const p = JSON.parse(raw) as Partial<FunnelEntry>;
				if (typeof p.source === 'string' && typeof p.at === 'number') {
					e = { source: p.source, tool: typeof p.tool === 'string' ? p.tool : null, at: p.at };
				}
			}
		} catch {
			e = null;
		}
	}
	if (e == null || now - e.at > ENTRY_TTL_MS || now < e.at) return null;
	return e;
}

function writeEntry(e: FunnelEntry | null): void {
	memory = e;
	try {
		const s = getStore();
		if (e == null) s?.clear();
		else s?.set(JSON.stringify(e));
	} catch {
		/* sailo estetty (yksityinen ikkuna): muisti riittaa saman sivulatauksen sisalla */
	}
}

/** Ketjun alku: lukon / CTA:n napautus tai hubin CTA-saapuminen. */
export function markEntry(source: string, tool: string | null = null, now = Date.now()): void {
	if (!source) return;
	writeEntry({ source, tool, at: now });
}

/** Nykyinen voimassa oleva lahde, tai null. */
export function currentEntry(now = Date.now()): FunnelEntry | null {
	return readEntry(now);
}

function str(v: unknown): string | null {
	return typeof v === 'string' && v.length > 0 ? v : null;
}

/** Askel tapahtumasta, tai null jos tapahtuma ei kuulu ostoketjuun. */
export function funnelStep(event: string, props?: Record<string, unknown>): FunnelStep | null {
	switch (event) {
		case 'paywall_shown':
			return props?.source === PAYWALL_SOURCE ? 'paywall_view' : 'lock_view';
		case 'upgrade_tapped':
			return str(props?.plan) ? 'plan_tap' : 'lock_tap';
		case 'checkout_opened':
			return 'checkout_opened';
		case 'checkout_failed':
			return 'checkout_failed';
		case 'checkout_store_only':
			return 'checkout_store_only';
		case 'checkout_already_premium':
			return 'checkout_already_premium';
		case 'purchase_completed':
			return 'purchase';
		default:
			return null;
	}
}

/** Lisaa ketjun tapahtumaan `funnel_step`, `entry_source` ja `entry_tool`, ja
 * paivittaa lahteen (napautus asettaa, kassan avaus virkistaa, osto tyhjentaa).
 * Muut tapahtumat palautetaan koskematta. Kutsujan propit voittavat, jos ne
 * asettavat saman kentan itse. */
export function funnelProps(
	event: string,
	props?: Record<string, unknown>,
	now = Date.now()
): Record<string, unknown> | undefined {
	const step = funnelStep(event, props);
	if (step == null) return props;

	if (step === 'lock_tap') {
		const source = str(props?.source) ?? 'unknown';
		markEntry(source, str(props?.tool), now);
	}

	let entry = readEntry(now);
	// Suora kassa ilman lukkoa (esim. /checkout-reitti ilman hubin src:ta):
	// lahde on kassan oma source, ei 'unknown'.
	if (entry == null && step === 'plan_tap') {
		const source = str(props?.source);
		if (source) {
			markEntry(source, null, now);
			entry = readEntry(now);
		}
	}

	const out: Record<string, unknown> = {
		funnel_step: step,
		entry_source: entry?.source ?? 'direct',
		entry_tool: entry?.tool ?? null,
		...props
	};

	if (step === 'checkout_opened' && entry) writeEntry({ ...entry, at: now });
	if (step === 'purchase') writeEntry(null);
	return out;
}
