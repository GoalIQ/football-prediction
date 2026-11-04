/** YKSI LUKIJA (WP6 copy-synkka, 4.11.2026): vuosipaketin myyntiteksti.
 *
 * Villen paatos 1.11: kausipassi on kertamaksu (25 €, Premium 30.5.2027
 * asti, ei uusiudu). Ennen sita vuosipaketti oli tilaus, ja SPA:n kuusi
 * pintaa sanoi sen omin sanoin: "Season pass: 25 € a year" (billing.ts +
 * pricing.svelte.ts), "Both plans renew until you cancel" (Paywall),
 * "Cancel anytime from the Account menu. One subscription covers ..."
 * (PremiumPreview, ProductIntro, /checkout) ja "Manage subscription"
 * (Hero). Passitilassa jokainen naista olisi epatosi.
 *
 * MIKSI TILA EI OLE TASSA VAKIONA: kytkin on Renderin
 * `STRIPE_PRICE_SEASON_PASS_2026_27`. Jos SPA:lla olisi oma kytkin, ne
 * voisivat olla eri mielta: sivu lupaisi kertamaksun ja Stripe veloittaisi
 * tilauksen, tai painvastoin. Siksi tila luetaan SAMASTA vastauksesta kuin
 * hinta: `/api/web/pricing` lisaa season-riville `billing: "one_time"` ja
 * `access_until` vain kun checkout myy passia (api/main.py, sama
 * `_season_pass_price`-kytkin kuin checkoutissa). Puuttuva kentta,
 * epaonnistunut haku tai lukukelvoton paiva = tilausteksti, eli tasan
 * entinen. Portti: `seasonPass.gate.test.ts`.
 *
 * Tekstit ovat julkaisutarkistajan lapi (6b). Ala muotoile niita
 * komponentissa uudelleen: komponentti kutsuu naita.
 */

/** Passin rivin `plan` web_subscriptions-taulussa. = `src/season_pass.py`
 *  SEASON_PASS_ID (portti lukee molemmat). */
export const SEASON_PASS_PLAN = 'season_pass_2026_27';

/** Hintavastauksen season-rivin passikentat (api/main.py web_pricing). */
export interface PassFields {
	billing?: string;
	access_until?: string;
}

/** "30 May 2027". Aikavyohyke UTC: loppuhetki on 23:59:59 UTC, joten
 *  Suomessa paikallinen kello sanoisi 31 May. */
export function formatPassEnd(iso: string | null | undefined): string | null {
	if (typeof iso !== 'string' || iso === '') return null;
	const d = new Date(iso);
	if (Number.isNaN(d.getTime())) return null;
	return new Intl.DateTimeFormat('en-GB', {
		day: 'numeric',
		month: 'long',
		year: 'numeric',
		timeZone: 'UTC'
	}).format(d);
}

/** Passin loppupaiva tekstina, tai null = myydaan tilausta (entinen teksti).
 *  Molemmat kentat vaaditaan: pelkka `billing` ilman paivaa ei riita, koska
 *  passiteksti nimeaa paivan. */
export function passEnd(p: PassFields | null | undefined): string | null {
	if (!p || p.billing !== 'one_time') return null;
	return formatPassEnd(p.access_until);
}

/** Onko tilin web-rivi passi (eika tilaus). */
export function isPassPlan(plan: string | null | undefined): boolean {
	return plan === SEASON_PASS_PLAN;
}

// --- Tekstit. `end` = passEnd(...) tulos; null = tilausteksti. -----------

/** Vuosinapin teksti. `price` on jo muotoiltu ("25 €"). */
export function seasonLabel(price: string, end: string | null): string {
	return end ? `Season pass: ${price}, until ${end}` : `Season pass: ${price} a year`;
}

/** Vuosipaketin likiarvon jakso ("about £21/year"). Passi on kertamaksu,
 *  joten likiarvo on pelkka summa. */
export function seasonPeriodSuffix(pass: boolean): string {
	return pass ? '' : '/year';
}

/** Vuosinapin vihje. */
export function seasonHint(end: string | null): string {
	// Julkaisutarkistaja 4.11: kattavuus ja paiva ovat jo ehtolauseessa ja
	// napissa, joten vihje sanoo vain sen mita ne eivat sano.
	return end
		? 'One payment, nothing renews.'
		: 'One subscription covers web, iOS and Android. Cancel anytime from the Account menu.';
}

/** Ehtolause ostonappien alle: Paywall, PremiumPreview, ProductIntro, /checkout. */
export function planTerms(end: string | null): string {
	return end
		? `The season pass ends on ${end} and there's nothing to cancel. ` +
				'The monthly plan renews until you cancel it from the Account menu. ' +
				'Either plan covers web, iOS and Android.'
		: 'Cancel anytime from the Account menu. One subscription covers web, iOS and Android.';
}

/** Paywallin ehtolause (sama vaite, Paywallin oma entinen muoto tilaukselle). */
export function paywallTerms(end: string | null): string {
	return end
		? planTerms(end)
		: 'Both plans renew until you cancel, and you can cancel from the Account menu. One subscription covers web, iOS and Android.';
}

/** Passin ostaneen Account-valikko: ei "Manage subscription" -nappia, koska
 *  Stripessa ei ole tilausta jota hallita. `endIso` = rivin current_period_end. */
export function passHolderNote(endIso: string | null | undefined): string {
	const end = formatPassEnd(endIso);
	const kesto = end ? `Premium until ${end}` : 'Premium for the season';
	return (
		`Season pass: ${kesto}. It was one payment, so nothing renews and there is nothing to cancel. ` +
		'For a refund within 30 days of the payment, email hello@goaliq.app.'
	);
}
