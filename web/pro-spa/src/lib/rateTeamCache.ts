/** 23.9 (Villen havainto "My team lataa liian kauan, vaikuttaa bugiselta"):
 * rate-team?entry=N -vastauksen viimeisin kopio selaimessa + entry-ID:n
 * kopio, jotta This week / My team ei odota Supabase-profiilia ennen hakua.
 *
 * MITATTU ENNEN (pro.goaliq.app, poytakone, voimassa oleva token):
 *   profiles-rivi 394 -> 947 ms, rate-team 1 117 -> 1 863 ms, eli haku alkoi
 *   vasta profiilin jalkeen ja mitaan omaa ei nakynyt ~1,9 s:iin. Backend
 *   itse vastaa 0,2-1,6 s:ssa.
 *
 * Tili on yha totuus (fplEntry.svelte.ts): tama on vain valimuisti, jonka
 * profiilin arvo korvaa jos ne eroavat. Kirjautumattomalle EI tallenneta
 * mitaan (tietoinen rajaus, ks. fplEntry.svelte.ts).
 *
 * Kelpoisuus on YHDESSA puhtaassa funktiossa (saanto 6a), sama saanto kuin
 * mobiilin lib/rateTeamCachePolicy.ts:ssa. Mika voi vaihtua alla:
 *   - tili                  -> userKey tasmattava
 *   - entry-ID              -> tasmattava (kentta ja meta.entry)
 *   - kierros               -> meta.deadline_time tulevaisuudessa; puuttuva = ei kelpaa
 *   - xP-projektio (1/vrk)  -> ikaraja 24 h
 *   - tilaus                -> maskattu vastaus ei kelpaa premiumille (lukittu
 *                              siirtolista maksavalle). Maskaamaton syntyy vain
 *                              saman tilin premium-tokenilla.
 */
import type { RateTeamResponse } from './fantasyTools';

export const RATE_TEAM_STORED_MAX_AGE_MS = 24 * 60 * 60 * 1000;

const RESULT_KEY = 'goaliq.rateteam.last.v1';
const ENTRY_KEY = 'goaliq.fplentry.v1';

export interface RateTeamLike {
	meta?: {
		entry?: number | null;
		deadline_time?: string | null;
		masked?: boolean | null;
	} | null;
}

export interface StoredRateTeam<T extends RateTeamLike = RateTeamLike> {
	v: 1;
	userKey: string;
	entry: number;
	fetchedAt: number;
	data: T;
}

export function storedRateTeamUsable(
	stored: StoredRateTeam | null | undefined,
	want: { entry: number; userKey: string; premium: boolean },
	now: number
): boolean {
	if (!stored || stored.v !== 1 || !stored.data) return false;
	if (stored.userKey !== want.userKey) return false;
	if (stored.entry !== want.entry) return false;
	const metaEntry = stored.data.meta?.entry;
	if (metaEntry != null && metaEntry !== want.entry) return false;
	const age = now - stored.fetchedAt;
	if (!(age >= 0 && age < RATE_TEAM_STORED_MAX_AGE_MS)) return false;
	const deadline = Date.parse(stored.data.meta?.deadline_time ?? '');
	if (!Number.isFinite(deadline) || now >= deadline) return false;
	if (want.premium && stored.data.meta?.masked === true) return false;
	return true;
}

function storage(): Storage | null {
	try {
		return typeof localStorage === 'undefined' ? null : localStorage;
	} catch {
		return null;
	}
}

/** Viimeisin tallennettu vastaus, jos saanto sallii sen nayttamisen. */
export function readStoredRateTeam(
	entry: number,
	userId: string,
	premium: boolean
): RateTeamResponse | null {
	try {
		const raw = storage()?.getItem(RESULT_KEY);
		if (!raw) return null;
		const stored = JSON.parse(raw) as StoredRateTeam<RateTeamResponse>;
		return storedRateTeamUsable(stored, { entry, userKey: `u:${userId}`, premium }, Date.now())
			? stored.data
			: null;
	} catch {
		return null;
	}
}

export function writeStoredRateTeam(entry: number, userId: string, data: RateTeamResponse): void {
	try {
		const row: StoredRateTeam<RateTeamResponse> = {
			v: 1,
			userKey: `u:${userId}`,
			entry,
			fetchedAt: Date.now(),
			data
		};
		storage()?.setItem(RESULT_KEY, JSON.stringify(row));
	} catch {
		// fail-safe: tayteen mennyt storage ei kaada tyokalua
	}
}

/** Tilin entry-ID:n kopio (profiles.fpl_entry_id on totuus). */
export function readCachedEntry(userId: string): string | null {
	try {
		const raw = storage()?.getItem(ENTRY_KEY);
		if (!raw) return null;
		const v = JSON.parse(raw) as { u?: string; e?: string };
		return v?.u === userId && typeof v.e === 'string' && /^\d{1,10}$/.test(v.e) ? v.e : null;
	} catch {
		return null;
	}
}

export function writeCachedEntry(userId: string, entry: string | null): void {
	try {
		if (entry == null) {
			storage()?.removeItem(ENTRY_KEY);
			storage()?.removeItem(RESULT_KEY);
		} else {
			storage()?.setItem(ENTRY_KEY, JSON.stringify({ u: userId, e: entry }));
		}
	} catch {
		// fail-safe
	}
}
