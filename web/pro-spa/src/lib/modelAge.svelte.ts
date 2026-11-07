/**
 * Projektion ika koko SPA:lle (7.11.2026). Yksi lahde: `/api/fantasy`
 * `meta.xp_generated_at`, koska kutsut ovat xP:sta ja phase0 voi toipua ensin.
 *
 * Kayttajat:
 * - `ToolsHome`: paivarivi tyokalujen kehykseen.
 * - jakopainikkeet: vanhasta projektiosta ei tehda jaettavaa kuvaa (Villen
 *   paatos 7.11). Kuva kiertaa ilman sivua, joten paiva alalaidassa ei korjaa
 *   sita, etta kortti voi suositella pelaajaa joka on loukkaantunut sen jalkeen.
 *   Jako palaa itsestaan kun data paivittyy.
 *
 * Ilman aikaa (vanha API, haku epaonnistui) jako on paalla ja rivia ei ole:
 * puuttuva tieto ei todista etta data on vanhaa.
 */
import { fetchFantasy } from './api';
import { clock } from './now.svelte';
import { staleModelDay, staleModelLine } from './myTeamFlow';

let built = $state<string | null>(null);
let started = false;

function start(): void {
	if (started || typeof window === 'undefined') return;
	started = true;
	fetchFantasy().then(
		(p) => (built = (p?.meta?.xp_generated_at as string | undefined) ?? null),
		() => {}
	);
}

export const modelAge = {
	/** Rivi tyokalujen kehykseen, tai null. */
	get line(): string | null {
		start();
		return staleModelLine(built, clock.now);
	},
	/** true = projektio yli vuorokauden vanha, jakopainikkeet pois. */
	get stale(): boolean {
		start();
		return staleModelDay(built, clock.now) != null;
	}
};
