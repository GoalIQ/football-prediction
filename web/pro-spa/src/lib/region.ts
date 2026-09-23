/** Maat joissa Premiumia ei myyda verkossa (paatos 23.9.2026).
 *
 * UK (ml. Mansaari): verkko-osto suljettu, Premium myydaan sovelluskauppojen
 * (App Store, Google Play) kautta. Kavija ohjataan sinne.
 *
 * MAATA EI PAATELLA SELAIMESTA. Palvelin lukee sen Cloudflaren
 * `CF-IPCountry`-otsakkeesta ja kertoo tuloksen kahdella tavalla:
 *   - `/api/web/pricing` -> `web_checkout: false` (napit piiloon ennen klikkia)
 *   - checkout-kutsu -> 403 `{error: "region_app_store_only"}` (ratkaiseva esto;
 *     esim. goaliq.app-landingin hinta-CTA joka laskeutuu /checkout-reitille)
 * Lista maista elaa vain backendissa (`src/regional_pricing.py`).
 *
 * Puhdas moduuli ilman Svelte- tai selainriippuvuuksia, jotta se on
 * testattavissa ilman DOMia.
 */

/** Sama merkkijono kuin backendin `REGION_STORE_ONLY_ERROR`. */
export const REGION_STORE_ONLY = 'region_app_store_only';

/** Ilmoituksen teksti. Sama lause kuin backendin `detail`issa, jonka vanha
 *  valimuistissa oleva SPA-versio nayttaa virhebannerissa. */
export const STORE_ONLY_COPY =
	'In the UK and the Isle of Man, GoalIQ Premium is available through the App Store and Google Play.';

/** Toinen rivi: sama tili toimii webissa (sama vaite kuin Paywallin
 *  "Already subscribed in the GoalIQ app?" -rivi). */
export const STORE_ONLY_ACCOUNT_NOTE =
	'Subscribe in the app, then sign in here with the same account and Premium works on the web too.';

/** Onko checkout-vastauksen runko alue-esto. */
export function isStoreOnlyBody(body: unknown): boolean {
	return (
		!!body &&
		typeof body === 'object' &&
		(body as Record<string, unknown>).error === REGION_STORE_ONLY
	);
}

/** Sanooko hintavastaus etta verkko-osto on suljettu.
 *
 *  Vain eksplisiittinen `false` sulkee. Puuttuva kentta (vanha backend,
 *  epaonnistunut haku) jattaa napit nakyviin: ratkaiseva esto on checkoutissa,
 *  eika tama pinta saa pysayttaa myyntia muualla. */
export function pricingBlocksWebCheckout(body: unknown): boolean {
	return (
		!!body &&
		typeof body === 'object' &&
		(body as Record<string, unknown>).web_checkout === false
	);
}
