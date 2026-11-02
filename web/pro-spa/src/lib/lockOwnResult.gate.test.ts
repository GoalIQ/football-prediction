/**
 * Portti: lukko nayttaa kayttajan OMAN tuloksen (ulkoasu WP8 / B1, Villen
 * paatos 1.11.2026; sovelluksen vastinpari WP9, palvelin fp #77).
 *
 *   1. lukija `thisWeekOpenCaptain` on fail-closed: vain palvelimen lukitsema
 *      rate-team-vastaus, vain kun palvelin nimeaa avatun kentan
 *      (`meta.free_open`), vain nelja kenttaa
 *   2. maararivi `lockHiddenLine` vain palvelimen luvusta, ei nollaa
 *   3. "kapteeni auki" -teksti ei lupaa kapteenia Premiumiin
 *   4. kutsupaikat: DecisionCard ja RateTeam kysyvat lukijalta ja valittavat
 *      tuloksen lukolle (muisti testi-kutsuu-funktiota-ei-kutsupaikkaa)
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { blankComments } from './sourceScan';
import {
	CAPTAIN_OPEN_COPY,
	LOCK_COPY,
	lockCopy,
	lockHiddenLine,
	thisWeekOpenCaptain
} from './personalLock';

const PICK = { id: 4, web_name: 'Gabriel', team_short: 'ARS', gw_xp: 6.26 };
const locked = (meta: Record<string, unknown> = {}, captain: unknown = { pick: PICK, alternative: null }) => ({
	meta: {
		masked: true,
		locked_tool: 'rate-my-team',
		free_open: ['captain.pick'],
		hidden_counts: { captain_alternative: 1, transfer_options: 5 },
		...meta
	},
	captain
});

describe('thisWeekOpenCaptain: fail-closed', () => {
	it('lukittu vastaus jossa palvelin avasi kapteenin -> nelja kenttaa', () => {
		expect(thisWeekOpenCaptain(locked())).toEqual({
			id: 4,
			web_name: 'Gabriel',
			team_short: 'ARS',
			gw_xp: 6.26
		});
	});

	it('uusi pick-kentta ei vuoda lukkoon', () => {
		const r = thisWeekOpenCaptain(locked({}, { pick: { ...PICK, reason: 'salainen peruste' } }));
		expect(Object.keys(r ?? {}).sort()).toEqual(['gw_xp', 'id', 'team_short', 'web_name']);
	});

	it('taysi vastaus (ei locked_toolia) ei kelpaa, vaikka kapteeni on siina', () => {
		const full = { meta: { free_open: ['captain.pick'] }, captain: { pick: PICK } };
		expect(thisWeekOpenCaptain(full)).toBeNull();
	});

	it('vanha API ilman free_openia tai ilman captain.pickia -> null', () => {
		expect(thisWeekOpenCaptain(locked({ free_open: undefined }))).toBeNull();
		expect(thisWeekOpenCaptain(locked({ free_open: [] }))).toBeNull();
		expect(thisWeekOpenCaptain(locked({ free_open: 'captain.pick' }))).toBeNull();
	});

	it('toisen tyokalun lukko ei avaa kapteenia', () => {
		expect(thisWeekOpenCaptain(locked({ locked_tool: 'gw-review' }))).toBeNull();
	});

	it('rikkinainen pick -> null, ei kaadu', () => {
		for (const bad of [null, {}, { pick: null }, { pick: { id: 0, web_name: 'X' } }, { pick: { id: 4, web_name: ' ' } }, { pick: { id: 4.5, web_name: 'X' } }]) {
			expect(thisWeekOpenCaptain(locked({}, bad))).toBeNull();
		}
		expect(thisWeekOpenCaptain(null)).toBeNull();
		expect(thisWeekOpenCaptain(undefined)).toBeNull();
	});

	it('puuttuva xP on null, ei 0', () => {
		expect(thisWeekOpenCaptain(locked({}, { pick: { id: 4, web_name: 'Gabriel' } }))?.gw_xp).toBeNull();
	});
});

describe('lockHiddenLine: vain palvelimen luku', () => {
	it('monikko ja yksikko', () => {
		expect(lockHiddenLine(locked())).toBe('Premium lists 5 transfer options for your squad.');
		expect(lockHiddenLine(locked({ hidden_counts: { transfer_options: 1 } }))).toBe(
			'Premium lists 1 transfer option for your squad.'
		);
	});

	it('0, puuttuva, negatiivinen tai murtoluku -> ei rivia', () => {
		for (const h of [{ transfer_options: 0 }, {}, { transfer_options: -1 }, { transfer_options: 2.5 }, null]) {
			expect(lockHiddenLine(locked({ hidden_counts: h }))).toBeNull();
		}
	});

	it('lukitsematon vastaus ei saa riviä', () => {
		expect(lockHiddenLine({ meta: { hidden_counts: { transfer_options: 5 } } })).toBeNull();
	});
});

describe('kapteeni auki -teksti', () => {
	it('ei lupaa kapteenia Premiumiin, nimeaa GoalIQ Premiumin, sama tyyli kuin LOCK_COPY', () => {
		for (const [slug, c] of Object.entries(CAPTAIN_OPEN_COPY)) {
			const t = `${c!.title} ${c!.body}`;
			expect(t, slug).not.toMatch(/captain/i);
			expect(c!.title, slug).toMatch(/part of GoalIQ Premium$/);
			expect(t, slug).not.toMatch(/[–—]/);
			expect(t, slug).not.toMatch(/[€£$]|\d+[.,]\d\d/);
			expect(t, slug).not.toMatch(/[‘’“”]/);
		}
	});

	it('perusteksti lupaa kapteenin, joten kapteeni auki tarvitsee oman muodon', () => {
		for (const slug of Object.keys(CAPTAIN_OPEN_COPY)) {
			expect(LOCK_COPY[slug as keyof typeof LOCK_COPY].body, slug).toMatch(/captain/i);
		}
	});

	it('lockCopy valitsee muodon; muut lukot eivat muutu', () => {
		expect(lockCopy('this-week', { captainOpen: true })).toBe(CAPTAIN_OPEN_COPY['this-week']);
		expect(lockCopy('this-week')).toBe(LOCK_COPY['this-week']);
		expect(lockCopy('gw-review', { captainOpen: true })).toBe(LOCK_COPY['gw-review']);
	});
});

describe('kutsupaikat', () => {
	const DIR = resolve(__dirname, 'components');
	const read = (f: string) => blankComments(readFileSync(resolve(DIR, f), 'utf-8').replace(/\r\n/g, '\n'));

	it('PersonalLock lukee tekstin lockCopysta (ei LOCK_COPY suoraan)', () => {
		const src = read('PersonalLock.svelte');
		expect(src).toMatch(/lockCopy\(tool, \{ captainOpen \}\)/);
		expect(src).not.toMatch(/LOCK_COPY\[/);
		expect(src).toMatch(/\{#if hidden\}/);
	});

	for (const f of ['DecisionCard.svelte', 'RateTeam.svelte']) {
		it(`${f}: avattu kapteeni lukijalta ja valitetty lukolle`, () => {
			const src = read(f);
			expect(src).toMatch(/thisWeekOpenCaptain\((card|data)\)/);
			expect(src).toMatch(/lockHiddenLine\((card|data)\)/);
			expect(src).toMatch(/captainOpen=\{openCap != null\}/);
			expect(src).toMatch(/hidden=\{hiddenLine\}/);
		});
	}

	it('DecisionCard: avatussa lukossa ei vaihtoehtoa eika mallin lahderivia', () => {
		const src = read('DecisionCard.svelte');
		expect(src).toMatch(/openCap \? null : \(model\?\.alt \?\? null\)/);
		expect(src).toMatch(/!ownCap && model/);
	});
});
