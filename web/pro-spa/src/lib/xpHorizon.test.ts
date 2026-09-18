/**
 * Yksikkotestit xP-summan ikkunan lukijalle (CLAUDE.md 6a mekanismi 3:
 * invariantti mitataan SYNTEETTISILLA vaiheilla, ei nykyhetkessa).
 *
 * Vaiheet on kirjoitettu 12.9 mitatusta tilanteesta: next_gameweek 4 kesken,
 * deadline_gameweek 5, horizon_gw 6. Uusi API julkaisee horizon_total_from 5
 * ja horizon_total_gw 5; vanha API ei julkaise kumpaakaan.
 */
import { describe, expect, it } from 'vitest';
import { xpHorizon, xpTotalClaim } from './xpHorizon';

/* Uusi API: kolme vaihetta. */
const BEFORE_DEADLINE = {
	horizon_gw: 6,
	next_gameweek: 5,
	deadline_gameweek: 5,
	horizon_total_from: 5,
	horizon_total_gw: 6
};
const IN_PROGRESS = {
	horizon_gw: 6,
	next_gameweek: 4,
	deadline_gameweek: 5,
	horizon_total_from: 5,
	horizon_total_gw: 5
};
/* Gradauksen jalkeen rivit alkavat taas deadline-kierroksesta. */
const AFTER_GRADING = {
	horizon_gw: 6,
	next_gameweek: 5,
	deadline_gameweek: 5,
	horizon_total_from: 5,
	horizon_total_gw: 6
};
const SEASON_END = {
	horizon_gw: 1,
	next_gameweek: 38,
	deadline_gameweek: 38,
	horizon_total_from: 38,
	horizon_total_gw: 1
};

/* Vanha API: samat vaiheet ilman horizon_total_*-kenttia. */
const OLD_IN_PROGRESS = { horizon_gw: 6, next_gameweek: 4, deadline_gameweek: 5 };
const OLD_BEFORE_DEADLINE = { horizon_gw: 6, next_gameweek: 5, deadline_gameweek: 5 };
/* Compare/differentials-metat: horizon_gw + actionable `gw`, EI next_gameweek. */
const OLD_COUNT_ONLY = { horizon_gw: 6, gw: 5 };

describe('uusi API: otsikko ja summa samasta metasta', () => {
	it('kesken kierroksen summa alkaa deadline-kierroksesta, ei alkaneesta', () => {
		const h = xpHorizon(IN_PROGRESS);
		expect(h.actionableOnly).toBe(true);
		expect(h.from).toBe(5);
		expect(h.to).toBe(9);
		expect(h.count).toBe(5);
		// Erotteleva vaite: sarakkeita on 6, summattuja kierroksia 5. Lukija
		// joka lukisi horizon_gw:ta palauttaisi 6 ja tama kaatuu.
		expect(h.rows).toBe(6);
		expect(h.count).not.toBe(h.rows);
		expect(h.range).toBe('GW5-GW9');
		expect(h.label).toBe('next 5 GWs');
		expect(h.over).toBe('over the next 5 GWs');
		expect(h.span).toBe('5-GW horizon');
		expect(h.gws).toBe('5 GWs');
		// Alkanut kierros ei saa nakya missaan tekstissa.
		for (const s of [h.label, h.over, h.span, h.gws, h.range ?? '']) {
			expect(s).not.toMatch(/\bGW4\b/);
			expect(s).not.toMatch(/\b6\b/);
		}
	});

	it('ennen deadlinea koko horisontti on pelattavissa', () => {
		const h = xpHorizon(BEFORE_DEADLINE);
		expect(h).toMatchObject({
			from: 5,
			to: 10,
			count: 6,
			rows: 6,
			actionableOnly: true,
			range: 'GW5-GW10',
			label: 'next 6 GWs',
			over: 'over the next 6 GWs'
		});
	});

	it('gradauksen jalkeen sama kuin ennen seuraavaa deadlinea', () => {
		expect(xpHorizon(AFTER_GRADING)).toEqual(xpHorizon(BEFORE_DEADLINE));
	});

	it('kauden viimeinen kierros: yksikko, ei "1 GWs"', () => {
		const h = xpHorizon(SEASON_END);
		expect(h.range).toBe('GW38');
		expect(h.label).toBe('next GW');
		expect(h.gws).toBe('1 GW');
		expect(h.span).toBe('1-GW horizon');
	});

	it('kausi ohi: nolla kierrosta ei ole "next 0 GWs"', () => {
		const h = xpHorizon({ horizon_gw: 0, horizon_total_from: 39, horizon_total_gw: 0 });
		expect(h.count).toBe(0);
		expect(h.range).toBeNull();
		expect(h.label).not.toMatch(/next/);
	});

	it('puolikas sopimus (vain horizon_total_gw): lukumaara tosi, "next" EI', () => {
		/* deadline_gameweek on metassa mutta lukija ei saa keksia siita alkua.
		   18.9 (julkaisutarkistajan B3): ENNEN tama palautti `actionableOnly
		   true` ja `label 'next 5 GWs'` PELKAN lukumaaran nojalla. Mitattu
		   18.9 tuotannosta: SPL palauttaa deadline_gameweek null ja
		   next_gameweek 8, ja backendin actionable putoaa next_gameweek:iin —
		   eli alku olisi ollut kentta jota tama lukija kieltaytyy lukemasta.
		   Backend julkaisee `horizon_total_from`in nyt vain deadlinesta, ja
		   sen PUUTTUMINEN on signaali: lukumaara jaa, lupa katoaa. */
		const HALF = { horizon_gw: 6, next_gameweek: 4, deadline_gameweek: 5, horizon_total_gw: 5 };
		const h = xpHorizon(HALF);
		expect(h.actionableOnly).toBe(false);
		expect(h.count).toBe(5);
		expect(h.from).toBeNull();
		expect(h.range).toBeNull();
		expect(h.label).toBe('5-GW horizon');
		expect(h.label).not.toMatch(/next/);
		expect(h.over).toBe('over the 5-GW horizon');
	});

	it('B3 VAIHE: SPL-muoto (deadline_gameweek null) ei tuota valia eika "next"', () => {
		/* MITATTU 18.9: /api/fantasy/xp?league=spl -> next_gameweek 8,
		   deadline_gameweek null, horizon_gw 6, rivit GW8-13. Uudella
		   backendilla horizon_total_gw 6 mutta horizon_total_from null. */
		const SPL = { horizon_gw: 6, next_gameweek: 8, horizon_total_gw: 6 };
		const h = xpHorizon(SPL);
		expect(h.count).toBe(6);
		expect(h.range).toBeNull();
		for (const s of [h.label, h.over, h.span, h.gws, h.totalTitle, h.totalHelp]) {
			expect(s).not.toMatch(/next/i);
			expect(s).not.toMatch(/GW\d/);
		}
		/* EROTTELEVA: sama meta ALUN kanssa nimeaa valin. */
		const pl = xpHorizon({ horizon_gw: 6, next_gameweek: 8, horizon_total_from: 8, horizon_total_gw: 6 });
		expect(pl.range).toBe('GW8-GW13');
		expect(pl.label).toBe('next 6 GWs');
	});

	it('vaiheinvariantti: uudella API:lla ikkuna alkaa aina horizon_total_from:sta', () => {
		for (const meta of [BEFORE_DEADLINE, IN_PROGRESS, AFTER_GRADING, SEASON_END]) {
			const h = xpHorizon(meta);
			expect(h.from).toBe(meta.horizon_total_from);
			expect(h.count).toBe(meta.horizon_total_gw);
			expect(h.range?.startsWith(`GW${meta.horizon_total_from}`)).toBe(true);
			expect(h.label.startsWith('next')).toBe(true);
		}
	});
});

describe('vanha API: fail-closed, ei "next", ei keksittya lukua', () => {
	it('kesken kierroksen summa kattaa myos alkaneen kierroksen, ja teksti sanoo sen', () => {
		const h = xpHorizon(OLD_IN_PROGRESS);
		expect(h.actionableOnly).toBe(false);
		expect(h.count).toBe(6);
		expect(h.rows).toBe(6);
		// Alku on rivien ensimmainen kierros (next_gameweek 4), EI deadline-
		// kierros 5: "GW5-GW10" vaittaisi summan kattavan kierroksen jota
		// riveilla ei ole ja jattavan pois kierroksen joka siina on.
		expect(h.from).toBe(4);
		expect(h.from).not.toBe(OLD_IN_PROGRESS.deadline_gameweek);
		expect(h.to).toBe(9);
		expect(h.range).toBe('GW4-GW9');
		expect(h.label).toBe('GW4-GW9');
		expect(h.over).toBe('over GW4-GW9');
		expect(h.span).toBe('6-GW horizon');
	});

	it('ennen deadlinea vanha API on tosi mutta ei silti lupaa "next"', () => {
		const h = xpHorizon(OLD_BEFORE_DEADLINE);
		expect(h.actionableOnly).toBe(false);
		expect(h.range).toBe('GW5-GW10');
		expect(h.label).toBe('GW5-GW10');
	});

	it('pelkka lukumaara (compare/differentials): ei alkua, ei "next"', () => {
		const h = xpHorizon(OLD_COUNT_ONLY);
		expect(h.from).toBeNull();
		expect(h.range).toBeNull();
		expect(h.count).toBe(6);
		expect(h.label).toBe('6-GW horizon');
		expect(h.over).toBe('over the 6-GW horizon');
		expect(h.gws).toBe('6 GWs');
	});

	it('vaiheinvariantti: vanhalla API:lla yksikaan teksti ei sano "next"', () => {
		for (const meta of [OLD_IN_PROGRESS, OLD_BEFORE_DEADLINE, OLD_COUNT_ONLY]) {
			const h = xpHorizon(meta);
			for (const s of [h.label, h.over, h.span, h.gws]) expect(s).not.toMatch(/\bnext\b/i);
		}
	});
});

describe('puuttuva tai roskadata', () => {
	it('tyhja meta: ei yhtaan numeroa missaan tekstissa (ei ?? 6)', () => {
		for (const meta of [undefined, null, {}]) {
			const h = xpHorizon(meta);
			expect(h.count).toBeNull();
			expect(h.from).toBeNull();
			expect(h.range).toBeNull();
			for (const s of [h.label, h.over, h.span, h.gws]) expect(s).not.toMatch(/\d/);
		}
	});

	it('merkkijono, desimaali tai negatiivinen luku on sama kuin puuttuva', () => {
		const h = xpHorizon({
			horizon_gw: '6' as unknown as number,
			horizon_total_gw: 5.5,
			horizon_total_from: -1,
			next_gameweek: NaN
		});
		expect(h.count).toBeNull();
		expect(h.from).toBeNull();
		expect(h.rows).toBeNull();
		expect(h.actionableOnly).toBe(false);
	});
});

/* --------------------------------------------------------------------------
 * 18.9: lukija palauttaa VALMIIN julkisen tekstin (P1-1 + P1-2). Kutsupaikka
 * ei kokoa otsikkoa eika vaitetta itse, joten naiden tekstien oikeellisuus
 * mitataan tasta — samoilla synteettisilla vaiheilla kuin kentat.
 * ------------------------------------------------------------------------ */
describe('valmiit julkiset tekstit', () => {
	it('kesken kierroksen otsikko ja selite kertovat SUMMATUT kierrokset', () => {
		const h = xpHorizon(IN_PROGRESS);
		expect(h.totalTitle).toBe('Sum of expected points, next 5 GWs');
		expect(h.totalHelp).toBe(
			'the sum of projected points over the next 5 GWs (GW5-GW9)'
		);
		// Erotteleva vaite: sarakkeita on 6. Sarakkeista koottu otsikko
		// sanoisi "next 6 GWs" ja tama kaatuu.
		expect(h.totalTitle).not.toContain('6');
		expect(h.totalHelp).not.toContain('6 GWs');
	});

	it('vanha API: otsikko ei sano "next" missaan vaiheessa', () => {
		for (const meta of [OLD_IN_PROGRESS, OLD_BEFORE_DEADLINE, OLD_COUNT_ONLY]) {
			const h = xpHorizon(meta);
			expect(h.totalTitle).not.toMatch(/\bnext\b/i);
			expect(h.totalHelp).not.toMatch(/\bnext\b/i);
		}
	});

	it('tyhja meta: otsikossa ei ole yhtaan numeroa', () => {
		for (const meta of [undefined, null, {}]) {
			const h = xpHorizon(meta);
			expect(h.totalTitle).toBe('Sum of expected points, model horizon');
			expect(h.totalHelp).not.toMatch(/\d/);
		}
	});

	it('kauden viimeinen kierros: yksikko, ei "next 1 GWs"', () => {
		const h = xpHorizon(SEASON_END);
		expect(h.totalTitle).toBe('Sum of expected points, next GW');
		expect(h.totalHelp).toBe('the sum of projected points over the next GW (GW38)');
	});

	it('nolla kierrosta jaljella: otsikko sanoo sen eika valehtele valia', () => {
		const h = xpHorizon({ horizon_gw: 6, horizon_total_gw: 0, horizon_total_from: 39 });
		expect(h.totalTitle).toBe('Sum of expected points, no GWs left');
		expect(h.totalHelp).toContain('with no GWs left');
		/* 18.9: sama lukija ei saa tuottaa seka "GWs" etta "gameweeks". */
		for (const s of [h.label, h.over, h.span, h.gws, h.totalTitle]) {
			expect(s).not.toMatch(/gameweek/i);
		}
	});
});

describe('xpTotalClaim: luku ja ikkuna samasta kutsusta', () => {
	it('kokoaa vaitteen niin ettei kutsupaikka nae ikkunaa erillisena', () => {
		const c = xpTotalClaim(IN_PROGRESS, 38.06);
		expect(c.value).toBe('38.1 xP');
		expect(c.tail).toBe('projected over the next 5 GWs');
		expect(c.text).toBe('38.1 xP projected over the next 5 GWs');
	});

	it('text on tasan value + tail (jakokortti ja sivu eivat voi eriytya)', () => {
		for (const meta of [BEFORE_DEADLINE, IN_PROGRESS, AFTER_GRADING, SEASON_END, {}]) {
			const c = xpTotalClaim(meta, 12.3);
			expect(c.text).toBe(`${c.value} ${c.tail}`);
		}
	});

	it('vaiheinvariantti: vanhalla API:lla vaite ei sano "next"', () => {
		for (const meta of [OLD_IN_PROGRESS, OLD_BEFORE_DEADLINE, OLD_COUNT_ONLY]) {
			expect(xpTotalClaim(meta, 31.21).text).not.toMatch(/\bnext\b/i);
		}
	});

	it('ikkuna tulee metasta, ei summan luvusta', () => {
		const a = xpTotalClaim(IN_PROGRESS, 1);
		const b = xpTotalClaim(IN_PROGRESS, 99);
		expect(a.tail).toBe(b.tail);
	});
});
