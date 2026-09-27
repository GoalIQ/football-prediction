/** Portti: pelaajakortin haku kattaa saman joukon kuin ylahaku (27.9.2026).
 *
 * Julkaisutarkistaja mittasi livena: kirjautumattomalle kortin oma hakukentta
 * ei loytanyt Cherkia, Barrya eika Semenyota (maskattu 10 + 184 / 667), kun
 * saman sivun ylahaku (`draftPool`) loysi. Invariantti mitataan jokaisessa
 * payload-tilassa, ei vain nykyisessa (saanto 6a(3)).
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import type { CardPlayer, XpPoolPlayer, XpResponse } from './api';
import { draftPool } from './draftPool';
import { cardFromLight, cardSearchPool } from './cardSearch';

const LIB = fileURLToPath(new URL('.', import.meta.url));
const strip = (s: string) => s.replace(/<!--[\s\S]*?-->/g, '');

const full = (id: number, name: string): CardPlayer =>
	({ id, web_name: name, full_name: `${name} Full`, team: 'TST', team_short: 'TST', pos: 'MID', price: 6 }) as CardPlayer;
const light = (id: number, name: string): XpPoolPlayer => ({ id, web_name: name, team_short: 'TST', pos: 'MID', price: 6 });

function covers(d: XpResponse) {
	const card = cardSearchPool([...(d.players ?? []), ...(d.excluded ?? [])] as CardPlayer[], d.pool ?? []);
	const ids = new Set(card.map((r) => r.id));
	const missing = draftPool(d).filter((p) => !ids.has(p.id)).map((p) => p.web_name);
	return { card, missing };
}

describe('cardSearchPool', () => {
	it('maskattu (kirjautumaton): kattaa draftPoolin, taydet ensin, ei tuplia', () => {
		const d = {
			players: [full(1, 'Haaland'), full(2, 'Saka')],
			excluded: [full(3, 'Injured')],
			pool: [light(1, 'Haaland'), light(4, 'Cherki'), light(5, 'Barry'), light(3, 'Injured')]
		} as unknown as XpResponse;
		const { card, missing } = covers(d);
		expect(missing).toEqual([]);
		expect(card.map((r) => [r.id, r.light])).toEqual([
			[1, false],
			[2, false],
			[3, false],
			[4, true],
			[5, true]
		]);
	});

	it('premium (kaikki taysina) ja vanha API ilman poolia', () => {
		const prem = { players: [full(1, 'A'), full(4, 'Cherki')], excluded: [], pool: [light(4, 'Cherki')] } as unknown as XpResponse;
		expect(covers(prem).missing).toEqual([]);
		expect(covers(prem).card.every((r) => !r.light)).toBe(true);
		const vanha = { players: [full(1, 'A')], excluded: [full(2, 'B')] } as unknown as XpResponse;
		expect(covers(vanha).missing).toEqual([]);
		expect(covers(vanha).card).toHaveLength(2);
	});

	it('cardFromLight ei keksi mallilukuja', () => {
		const c = cardFromLight(light(4, 'Cherki'));
		expect(c.web_name).toBe('Cherki');
		expect(c.xp_horizon_total).toBeUndefined();
		expect(c.gameweeks).toBeUndefined();
	});
});

describe('kutsupaikka', () => {
	it('PlayerCard hakee searchPoolista ja kevyt valinta merkitaan lightOnly', () => {
		const pc = strip(readFileSync(join(LIB, 'components/PlayerCard.svelte'), 'utf-8'));
		expect(pc).toContain('cardSearchPool(pool, lightPool)');
		expect(pc).toMatch(/return searchPool\s*\.filter\(/);
		expect(pc).not.toMatch(/return pool\s*\.filter\(/);
		expect(pc).toContain('onSelect={selectFromSearch}');
		expect(pc).toMatch(/if \(item\.light\) \{\s*select\(cardFromLight\(item\)\);\s*lightOnly = true;/);
	});
});
