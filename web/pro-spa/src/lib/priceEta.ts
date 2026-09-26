/**
 * $lib/priceEta.ts - YKSI LUKIJA hintamuutoksen paivasanalle (saanto 6a).
 *
 * 🔴 MIKSI (26.9.2026, julkaisutarkistaja MP-10): paivasana ("tonight")
 * johdettiin price watchin `eta_days`-offsetista ilman kellonaikaa. FPL
 * paivittaa hinnat kerran vuorokaudessa (26.9: 23:00Z), joten sana oli vaarin
 * Amerikoissa joka ilta (Sao Paulossa paivitys on 20:00, jonka jalkeen offset
 * 0 osoittaa jo huomiseen) ja kaikkialla paivityksen ja seuraavan buildin
 * valissa (mediaani 78 min). Nyt backend antaa `eta_at` = FPL:n oma
 * paivitysaika, ja sana lasketaan siita LUKIJAN paikallisessa ajassa.
 *
 * Saanto:
 *   - puuttuva tai jasentymaton `eta_at` -> null (ei paivasanaa)
 *   - mennyt `eta_at` -> null (paivitys on jo tapahtunut, rivi on vanha)
 *   - paikallinen kalenteripaiva (eta_at - 6 h) vs tanaan:
 *       <= 0 -> "today" jos paivityksen paikallinen tunti on 06-17, muuten
 *               "tonight" (Helsinki 02:00 on viela "tonight")
 *       1    -> "tomorrow", >= 2 -> "in N days"
 * Kellonaikaa ei kovakoodata (talviaika 25.10 voi siirtaa sita).
 *
 * Sama tiedosto mobiilissa: goaliq-app lib/priceEta.ts.
 */

export type PriceEtaKind = 'today' | 'tonight' | 'tomorrow' | 'days';

export interface PriceEta {
	kind: PriceEtaKind;
	/** Kalenteripaivia lukijan paikallisessa ajassa (0 = today/tonight). */
	days: number;
}

export interface LocalParts {
	y: number;
	m: number;
	d: number;
	h: number;
}

/** Hetken paikallinen kalenteripaiva ja tunti. Oletus = laitteen vyohyke;
 *  testit antavat synteettisen vyohykkeen. */
export type LocalClock = (ms: number) => LocalParts;

export const deviceClock: LocalClock = (ms) => {
	const t = new Date(ms);
	return { y: t.getFullYear(), m: t.getMonth(), d: t.getDate(), h: t.getHours() };
};

const EVENING_SHIFT_MS = 6 * 60 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

function dayIndex(p: LocalParts): number {
	return Math.round(Date.UTC(p.y, p.m, p.d) / DAY_MS);
}

export function priceEta(
	etaAt: unknown,
	nowMs: number,
	clock: LocalClock = deviceClock
): PriceEta | null {
	if (typeof etaAt !== 'string') return null;
	const at = Date.parse(etaAt);
	if (!Number.isFinite(at) || at <= nowMs) return null;
	// Julkaisutarkistaja 26.9 (B1): kalenteriero yksin antoi kahdelle eri
	// paivitykselle saman sanan klo 00-06 paikallista aikaa (Helsinki 00:30:
	// tonight / tonight / tomorrow). Taysia vuorokausia jaljella on alaraja.
	const diff = Math.max(
		dayIndex(clock(at - EVENING_SHIFT_MS)) - dayIndex(clock(nowMs)),
		Math.floor((at - nowMs) / DAY_MS)
	);
	if (diff <= 0) {
		const h = clock(at).h;
		return { kind: h >= 6 && h <= 17 ? 'today' : 'tonight', days: 0 };
	}
	if (diff === 1) return { kind: 'tomorrow', days: 1 };
	return { kind: 'days', days: diff };
}

/** Englanninkielinen sana (SPA on englanniksi). `capital` taulukon sarakkeeseen. */
export function priceEtaWord(e: PriceEta, capital = false): string {
	const w =
		e.kind === 'days' ? `in ${e.days} days` : e.kind === 'tomorrow' ? 'tomorrow' : e.kind;
	return capital ? w.charAt(0).toUpperCase() + w.slice(1) : w;
}

export interface PriceMoveLike {
	id: number;
	web_name: string;
	status: string;
	eta_at?: string | null;
}

/** Hintaliike jolla on peruste: `_soon` ja tuleva paivitysaika. */
export function sureMove<T extends PriceMoveLike>(
	m: T,
	nowMs: number,
	clock: LocalClock = deviceClock
): (T & { eta: PriceEta }) | null {
	if (!/_soon$/.test(m.status)) return null;
	const eta = priceEta(m.eta_at, nowMs, clock);
	return eta ? { ...m, eta } : null;
}

/** Ruudun rungon hintaliikkeet risers/fallers-listoilta (ei entrya tarvita:
 *  rivit leikataan ruudulla olevaan runkoon, sama saanto kuin saatavuudella). */
export function squadPriceMoves<T extends PriceMoveLike>(
	ids: ReadonlySet<number>,
	risers: readonly T[] | null | undefined,
	fallers: readonly T[] | null | undefined,
	nowMs: number,
	clock: LocalClock = deviceClock
): { rising: (T & { eta: PriceEta })[]; falling: (T & { eta: PriceEta })[] } {
	const pick = (rows: readonly T[] | null | undefined) =>
		(rows ?? [])
			.filter((m) => ids.has(m.id))
			.map((m) => sureMove(m, nowMs, clock))
			.filter((m): m is T & { eta: PriceEta } => m != null);
	return { rising: pick(risers), falling: pick(fallers) };
}

/** Omistetuista riveista ne jotka muuttuvat seuraavassa paivityksessa
 *  (today/tonight lukijan ajassa). `kind` = niiden yhteinen sana. */
export function nextUpdateMoves<T extends PriceMoveLike>(
	rows: readonly T[],
	nowMs: number,
	clock: LocalClock = deviceClock
): { n: number; kind: 'today' | 'tonight' | null } {
	let n = 0;
	let kind: 'today' | 'tonight' | null = null;
	for (const r of rows) {
		const e = priceEta(r.eta_at, nowMs, clock);
		if (e && (e.kind === 'today' || e.kind === 'tonight')) {
			n += 1;
			kind = kind ?? e.kind;
		}
	}
	return { n, kind };
}
