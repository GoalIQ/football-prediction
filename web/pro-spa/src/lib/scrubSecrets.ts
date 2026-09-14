/** Kirjautumissalaisuudet pois kaikesta mika lahtee PostHogiin (14.9.2026).
 *
 * MIKSI TAMA ON OLEMASSA: Google-kirjautumisen ja magic linkin paluu tulee
 * osoitteeseen `https://pro.goaliq.app/#access_token=...&provider_token=...
 * &refresh_token=...`. posthog-js tallentaa osoitteen sellaisenaan, joten
 * Supabase-JWT (sisaltaa sahkopostin), Googlen provider-token ja refresh-token
 * olivat PostHogissa luettavissa. Mitattu 14.9: 72 tapahtumaa, 8 henkiloa,
 * 16.7. alkaen. Avaimet eivat olleet vain `$current_url`issa vaan myos
 * `$session_entry_url`issa, `$set`/`$set_once`issa (-> henkilon
 * `$initial_current_url`) ja `$web_vitals_*_event`-olioissa.
 *
 * MIKSI YKSI KOUKKU EIKA KENTTALISTA: vuoto loytyi viidesta eri kentasta, ja
 * kuudes ilmestyy kun posthog-js lisaa uuden URL-kentan. Siksi tama kay lapi
 * KOKO lahtevan tapahtuman rekursiivisesti ja siivoaa jokaisen merkkijonon.
 * Kentta jota ei ole viela olemassa on silloin jo katettu.
 *
 * Kaksi saantoa, tarkoituksella paallekkain:
 *   1. nimetyt parametrit (`access_token=` ym.) -> arvo pois
 *   2. mika tahansa JWT (`eyJ...x.y.z`) -> pois, missa kontekstissa tahansa.
 *      Kattaa sen tapauksen jossa token paatyy virheviestiin tai muuhun
 *      kenttaan ilman parametrin nimea.
 */

const SECRET_PARAMS =
	'access_token|refresh_token|provider_token|provider_refresh_token|id_token|token_hash';

// Arvo loppuu &:iin, #:iin, valilyontiin tai lainausmerkkiin (JSON-merkkijonon sisalla).
const PARAM_RE = new RegExp(`((?:^|[?#&])(?:${SECRET_PARAMS})=)[^&#\\s"']*`, 'gi');
const JWT_RE = /eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]+/g;

export const REDACTED = '[redacted]';

export function scrubString(value: string): string {
	if (!value) return value;
	return value.replace(PARAM_RE, `$1${REDACTED}`).replace(JWT_RE, REDACTED);
}

/** Palauttaa uuden arvon; alkuperaista ei muuteta.
 *
 *  🔴 Syvyyskatto EI palauta arvoa sellaisenaan. Se olisi fail-open: syva
 *  rakenne (esim. sessiotallenteen DOM-puu) kulkisi siivoamatta juuri siella
 *  missa kukaan ei katso. Katon ylittava osa siivotaan JSON-merkkijonona, ja
 *  jos sekaan ei onnistu (sykli), osa korvataan kokonaan. */
export function scrubSecrets<T>(value: T, depth = 0): T {
	if (depth > 12) {
		try {
			return JSON.parse(scrubString(JSON.stringify(value))) as T;
		} catch {
			return REDACTED as T;
		}
	}
	if (typeof value === 'string') return scrubString(value) as T;
	if (Array.isArray(value)) return value.map((v) => scrubSecrets(v, depth + 1)) as T;
	if (value && typeof value === 'object') {
		const out: Record<string, unknown> = {};
		for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
			out[k] = scrubSecrets(v, depth + 1);
		}
		return out as T;
	}
	return value;
}
