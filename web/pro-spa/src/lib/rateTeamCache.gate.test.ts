/**
 * 23.9.2026, Villen havainto: "My team loading kestaa liian kauan, vaikuttaa
 * bugiselta". Mitattu pro.goaliq.app:sta ennen korjausta: rate-team alkoi
 * vasta Supabase-profiilin jalkeen (1 117 ms) ja valmistui 1 863 ms;
 * model-race haettiin kahdesti (ensin ilman entrya).
 *
 * Kaksi porttia (muisti: testi-kutsuu-funktiota-ei-kutsupaikkaa):
 *   1. kelpoisuussaanto synteettisilla kierrosvaiheilla (saanto 6a kohta 3)
 *   2. lahdeportti kutsupaikoille: automaattiajo lukee tallennetun kopion,
 *      entry-ID luetaan kopiosta ennen profiilia, persistEntry ei kirjoita
 *      samaa arvoa uudelleen ja model-race odottaa entryn ratkeamista.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { RATE_TEAM_STORED_MAX_AGE_MS, storedRateTeamUsable, type StoredRateTeam } from './rateTeamCache';

const H = 60 * 60 * 1000;
const DEADLINE = Date.parse('2026-10-10T10:00:00Z');

function row(over: Partial<StoredRateTeam> = {}, meta: Record<string, unknown> = {}): StoredRateTeam {
	return {
		v: 1,
		userKey: 'u:abc',
		entry: 116920,
		fetchedAt: DEADLINE - 48 * H,
		data: { meta: { entry: 116920, deadline_time: '2026-10-10T10:00:00Z', masked: false, ...meta } },
		...over
	};
}
const want = { entry: 116920, userKey: 'u:abc', premium: true };

describe('storedRateTeamUsable', () => {
	it('sama tili ja entry ennen deadlinea, alle 24 h -> kelpaa', () => {
		expect(storedRateTeamUsable(row(), want, DEADLINE - 40 * H)).toBe(true);
	});
	it('kierrosvaiheet: deadlinella ja kesken kierroksen ei kelpaa', () => {
		const r = row({ fetchedAt: DEADLINE - 2 * H });
		expect(storedRateTeamUsable(r, want, DEADLINE - 1)).toBe(true);
		expect(storedRateTeamUsable(r, want, DEADLINE)).toBe(false);
		expect(storedRateTeamUsable(r, want, DEADLINE + 3 * H)).toBe(false);
	});
	it('puuttuva tai rikki deadline -> ei kelpaa (fail-closed)', () => {
		expect(storedRateTeamUsable(row({}, { deadline_time: null }), want, DEADLINE - 40 * H)).toBe(false);
		expect(storedRateTeamUsable(row({}, { deadline_time: 'x' }), want, DEADLINE - 40 * H)).toBe(false);
	});
	it('ika 24 h ja tulevaisuuden aikaleima', () => {
		const r = row();
		expect(storedRateTeamUsable(r, want, r.fetchedAt + RATE_TEAM_STORED_MAX_AGE_MS - 1)).toBe(true);
		expect(storedRateTeamUsable(r, want, r.fetchedAt + RATE_TEAM_STORED_MAX_AGE_MS)).toBe(false);
		expect(storedRateTeamUsable(r, want, r.fetchedAt - 1)).toBe(false);
	});
	it('toinen tili tai entry ei kelpaa', () => {
		expect(storedRateTeamUsable(row(), { ...want, userKey: 'u:zzz' }, DEADLINE - 40 * H)).toBe(false);
		expect(storedRateTeamUsable(row(), { ...want, entry: 1 }, DEADLINE - 40 * H)).toBe(false);
		expect(storedRateTeamUsable(row({}, { entry: 5 }), want, DEADLINE - 40 * H)).toBe(false);
	});
	it('maskattu ei kelpaa premiumille, kelpaa ilmaiselle', () => {
		const masked = row({}, { masked: true });
		expect(storedRateTeamUsable(masked, want, DEADLINE - 40 * H)).toBe(false);
		expect(storedRateTeamUsable(masked, { ...want, premium: false }, DEADLINE - 40 * H)).toBe(true);
	});
	it('roskarivi ei kaada', () => {
		expect(storedRateTeamUsable(null, want, 0)).toBe(false);
		expect(storedRateTeamUsable({ ...row(), v: 2 } as unknown as StoredRateTeam, want, DEADLINE - 40 * H)).toBe(false);
	});
});

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8');

describe('kutsupaikat', () => {
	it('automaattiajo lukee tallennetun kopion ja kirjoittaa tuoreen', () => {
		const src = read('./components/RateTeam.svelte');
		const start = src.indexOf('async function runRate(');
		expect(start).toBeGreaterThan(0);
		const body = src.slice(start, src.indexOf('\n\t}\n', start));
		expect(body).toMatch(/readStoredRateTeam\(/);
		expect(body).toMatch(/writeStoredRateTeam\(/);
		expect(src).toMatch(/void runRate\(true\)/);
	});
	it('entry-ID luetaan kopiosta ENNEN profiilikierrosta', () => {
		const src = read('./fplEntry.svelte.ts');
		const start = src.indexOf('export async function loadProfileEntry');
		const body = src.slice(start, src.indexOf('\n}\n', start));
		const cache = body.indexOf('readCachedEntry(');
		const profile = body.indexOf('fetchOwnProfileRow(');
		expect(cache).toBeGreaterThan(0);
		expect(profile).toBeGreaterThan(cache);
	});
	it('persistEntry ei kirjoita samaa arvoa uudelleen', () => {
		const src = read('./fplEntry.svelte.ts');
		const start = src.indexOf('export async function persistEntry');
		const body = src.slice(start, src.indexOf('\n}\n', start));
		const same = body.search(/fpl_entry_id \?\? ''\) === s\)/);
		const rpc = body.indexOf("rpc('set_fpl_entry_id'");
		expect(same).toBeGreaterThan(0);
		expect(rpc).toBeGreaterThan(same);
	});
	it('model-race odottaa entryn ratkeamista', () => {
		const src = read('./components/ThisWeek.svelte');
		expect(src).toMatch(/if \(entryId == null && !entryKnown\) return;/);
	});
});
