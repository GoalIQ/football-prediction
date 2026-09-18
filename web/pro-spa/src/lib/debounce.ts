/**
 * Yleiskäyttöinen debounce (18.9.2026, SPA-VALUE-EVENT-TUPLAKIRJAUS).
 *
 * MIKSI. `Value.svelte`:n `$effect` haki uudelleen JOKAISELLA
 * `currentEntryId()`-arvon muutoksella — myös silloin kun käyttäjä vasta
 * kirjoittaa entry-ID:tä RateTeamin/TransferPlannerin jaettuun kenttään
 * (`fplEntry.entry` on Svelte $state, jaettu useamman komponentin kesken).
 * Jokainen välivaiheen validi luku (esim. "1", "11", "116" ennen kuin
 * "116920" on kokonaan kirjoitettu) laukaisi oman `fantasy_tools_used`-
 * eventin value-työkalulle, vaikka käyttäjä ei ole avannut Valuea lainkaan.
 * Seuraus: value näyttää mittareissa suositummalta kuin se on, koska yksi
 * käyttökerta muualla synnyttää monta tapahtumaa täällä.
 *
 * Ratkaisu on YLEINEN funktio eikä Value-kohtainen korjaus, jotta sama
 * kirjoituskaava (`currentEntryId()`-effekti) muissa komponenteissa (esim.
 * PriceWatch) voi käyttää samaa mekanismia ilman kopiointia — ks.
 * CLAUDE.md 6a kohta 1 (yksi lukija/mekanismi, ei sanalista per komponentti).
 */

export interface Debounced<A extends unknown[]> {
	(...args: A): void;
	/** Peruuta odottava kutsu (esim. komponentin unmount). */
	cancel(): void;
}

export function debounce<A extends unknown[]>(
	fn: (...args: A) => void,
	delayMs: number
): Debounced<A> {
	let timer: ReturnType<typeof setTimeout> | null = null;

	function debounced(...args: A): void {
		if (timer !== null) clearTimeout(timer);
		timer = setTimeout(() => {
			timer = null;
			fn(...args);
		}, delayMs);
	}

	debounced.cancel = (): void => {
		if (timer !== null) {
			clearTimeout(timer);
			timer = null;
		}
	};

	return debounced;
}
