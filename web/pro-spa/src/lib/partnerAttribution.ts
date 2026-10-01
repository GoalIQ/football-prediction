/**
 * Kumppaniattribuutio tilille (1.10.2026, mittaus cc-reports/2026-10-01-demon-polku-ja-konversiomittari.md).
 *
 * FPL Demonin linkit tulevat muodossa `?utm_source=fpldemon&utm_medium=partner`.
 * PostHog tallentaa utm:n henkilolle, mutta kolme asiaa katkaisee sen:
 * mainosesto (PostHog ei lataudu lainkaan), selaimen vaihto ja sovellus. Tili
 * on ainoa paikka joka kestaa ne: kun tili on luotu webissa, sovelluksessa
 * tehty osto kuuluu samalle kayttajalle.
 *
 * 🔴 TAMA EI OLE AFFILIATE-REF. `?ref=` (billing.ts) leimaa Stripe-tilauksen
 *    ja menee provisioiden payout-tasmaytykseen (api/main.py). Kumppanilla ei
 *    ole provisiota, joten se kirjataan omaan avaimeensa `partner`, jota
 *    backend ei lue maksuihin. Kahden avaimen sekoittaminen maksaisi
 *    provision tilaukselle jota kukaan ei luvannut.
 *
 * Saanto sama kuin refissa: ensimmainen kumppani pitaa attribuution, eika
 * myohempi linkki ylikirjoita sita.
 */
const PARTNER_KEY = 'giq:partner';
const PARTNER_RE = /^[a-z0-9_-]{2,32}$/;

/** `utm_source` vain kun `utm_medium=partner`. Muut utm:t eivat ole kumppaneita. */
export function partnerFromSearch(search: string): string | null {
	try {
		const q = new URLSearchParams(search);
		if ((q.get('utm_medium') ?? '').trim().toLowerCase() !== 'partner') return null;
		const v = (q.get('utm_source') ?? '').trim().toLowerCase();
		return PARTNER_RE.test(v) ? v : null;
	} catch {
		return null;
	}
}

/** Poimii kumppanin URLista ja sailoo sen. Kutsutaan bootissa. */
export function capturePartner(search = ''): string | null {
	try {
		const found = partnerFromSearch(search);
		if (found && !localStorage.getItem(PARTNER_KEY)) localStorage.setItem(PARTNER_KEY, found);
		return storedPartner();
	} catch {
		return null;
	}
}

export function storedPartner(): string | null {
	try {
		const v = localStorage.getItem(PARTNER_KEY);
		return v && PARTNER_RE.test(v) ? v : null;
	} catch {
		return null;
	}
}

/** Signupin `options.data` / OAuth-paluun `updateUser`-data: ref ja partner
 *  omissa avaimissaan, vain ne joita tililla ei viela ole. */
export function attributionData(
	ref: string | null,
	partner: string | null,
	existing?: Record<string, unknown> | null
): Record<string, string> | null {
	const out: Record<string, string> = {};
	if (ref && !existing?.ref) out.ref = ref;
	if (partner && !existing?.partner) out.partner = partner;
	return Object.keys(out).length > 0 ? out : null;
}
