/** Hinta palvelimelta: sivu ei voi sanoa eri lukua kuin Checkout veloittaa.
 *
 * MITATTU 20.9.2026. `billing.ts`:n `PLANS` on kovakoodattu lista
 * ("Season pass: 25 € a year"). Kun aluehinta kytkettiin paalle, nigerialainen
 * olisi nahnyt maksumuurilla 25 € ja Checkoutissa 9 €. Kukaan ei olisi
 * ylilaskutettu, mutta koko hyoty olisi jaanyt saamatta: paatos tehdaan
 * maksumuurilla, ja webin pudotus on juuri siina (383 pro_page_viewed ->
 * 20 upgrade_tapped, 180 vrk).
 *
 * Maata EI paatella selaimesta. Palvelin lukee sen Cloudflaren otsakkeesta ja
 * hakee summan Stripesta, eli sama lahde jolla veloitetaan. Jos haku
 * epaonnistuu, `PLANS` jaa voimaan: vanha oikea luku on parempi kuin tyhja.
 */
import { API_BASE } from './config';
import { PLANS, type PlanKey } from './billing';

interface Hinta {
	amount: number;
	currency: string;
	tier: string;
}

let live = $state<Partial<Record<PlanKey, Hinta>>>({});
let haettu = false;

/** Valuutta lukijan silmin. Tuntematon koodi nayttaa koodina, ei arvattuna
 *  symbolina: vaara symboli on vaarempi kuin tylsa. */
const SYMBOLI: Record<string, string> = { EUR: '€', GBP: '£', USD: '$' };

function raha(h: Hinta): string {
	const n = Number.isInteger(h.amount) ? String(h.amount) : h.amount.toFixed(2);
	const s = SYMBOLI[h.currency];
	return s ? `${n} ${s}` : `${n} ${h.currency}`;
}

/** Hakee hinnat kerran. Virhe ei ole virhe kayttajalle: `PLANS` jaa voimaan. */
export async function loadPricing(): Promise<void> {
	if (haettu) return;
	haettu = true;
	try {
		const r = await fetch(`${API_BASE}/api/web/pricing`);
		if (!r.ok) return;
		const d = await r.json();
		if (d && typeof d === 'object' && d.plans && typeof d.plans === 'object') {
			live = d.plans as Partial<Record<PlanKey, Hinta>>;
		}
	} catch {
		/* fail-soft, ks. moduulin docstring */
	}
}

export function planTier(key: PlanKey): string {
	return live[key]?.tier ?? 'default';
}

/** Napin teksti. Sama muoto kuin `PLANS`issa, mutta luku palvelimelta. */
export function planLabel(key: PlanKey): string {
	const h = live[key];
	if (!h) return PLANS[key].label;
	return key === 'season' ? `Season pass: ${raha(h)} a year` : `Monthly: ${raha(h)}/mo`;
}

/** Naytetaanko UK/US-valuuttalikiarvo.
 *
 * `planApprox` on laskettu LISTAhinnasta (25 € -> "about £21/year"). Jos
 * kavija saa aluehinnan, likiarvo olisi eri hinnasta kuin nappi - kaksi lukua
 * samassa rivissa, eri lahteista. Naytetaan se siis vain listahinnalla.
 */
export function showApprox(key: PlanKey): boolean {
	return planTier(key) === 'default';
}
