/**
 * MOBIILI-IA-JATKOT, tulostilan OUT-lippu (1.10.2026). FPL:n
 * `chance_next` koskee deadline-kierrosta; lippu nimeaa sen kun kentta
 * nayttaa muuta kierrosta. Vaiheet mitataan synteettisesti (saanto 6a
 * kohta 3): suunnitteluikkuna, Premiumin muu valinta, kesken oleva kierros.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { doubtFlagGw, doubtFlagText } from './doubtFlag';
import { blankComments } from './sourceScan';

const lue = (rel: string) =>
	blankComments(readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8'));

describe('lippu nimeaa kierroksensa vain kun kentta nayttaa muuta', () => {
	it('suunnitteluikkuna: GW5 result kentalla, FPL:n luku koskee GW6:ta', () => {
		expect(doubtFlagText(0, 5, 6)).toBe('GW6 OUT');
		expect(doubtFlagText(75, 5, 6)).toBe('GW6 75%');
	});
	it('kentta nayttaa deadline-kierrosta: lippu ennallaan', () => {
		expect(doubtFlagText(0, 6, 6)).toBe('OUT');
		expect(doubtFlagText(25, 6, 6)).toBe('25%');
	});
	it('Premium valitsee GW8:n: luku koskee yha GW6:ta', () => {
		expect(doubtFlagText(50, 8, 6)).toBe('GW6 50%');
	});
	it('kierros kesken: kentalla GW6, luku koskee jo GW7:aa', () => {
		expect(doubtFlagText(0, 6, 7)).toBe('GW7 OUT');
	});
	it('ei lukua tai 100 %: ei lippua; tuntematon kierros: entinen muoto', () => {
		expect(doubtFlagText(null, 5, 6)).toBeNull();
		expect(doubtFlagText(undefined, 5, 6)).toBeNull();
		expect(doubtFlagText(100, 5, 6)).toBeNull();
		expect(doubtFlagText(0, 5, null)).toBe('OUT');
		expect(doubtFlagGw(null, 6)).toBeNull();
	});
});

describe('kutsupaikat', () => {
	const tpm = lue('./components/TeamPitchManager.svelte');
	it('kentta ja penkki lukevat lipun yhdesta lukijasta', () => {
		expect(tpm).not.toMatch(/chance_next === 0 \? 'OUT'/);
		expect(tpm.match(/doubtFlagText\(p\.chance_next, shownGw, deadlineGw\)/g)?.length).toBe(4);
	});
	it('nakyva kierros on tulostilassa ratkennut kierros', () => {
		expect(tpm).toMatch(/const shownGw = \$derived\(settledView \? luckGw : selGw\);/);
	});
	it('RateTeam antaa deadline-kierroksen molemmille kentille', () => {
		const rt = lue('./components/RateTeam.svelte');
		expect(rt).toMatch(/deadlineGw=\{data\.meta\.deadline_gameweek \?\? null\}/);
		expect(rt).toMatch(/deadlineGw=\{dataB\.meta\.deadline_gameweek \?\? null\}/);
	});
});
