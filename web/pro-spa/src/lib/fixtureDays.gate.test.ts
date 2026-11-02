/** Portti: Fixtures-listan paivaotsikko on lukijan vyohykkeessa, kuten kellonaika
 * (julkaisutarkistaja 1.11.2026, PR #75).
 *
 * 🔴 MIKSI. Lause "Kick-off times are in your time zone (EET)." oli tosi
 * kellonajalle mutta ei paivaotsikolle: ryhmittely luki API:n UTC-paivan.
 * Mitattu Nodella: New Yorkissa ja Sao Paulossa Arsenal v Hull (la 7.11.
 * 15:00 UTC) oli otsikon "Friday 6 November" alla, Kolkatassa ja Sydneyssa
 * perjantain 20:00 UTC -ottelu (paikallisesti jo lauantai) samoin.
 *
 * Mekanismit (CLAUDE.md 6a): (1) yksi lukija `groupByLocalDay`, (2)
 * kutsupaikkaportti: Fixtures.svelte ryhmittelee sen kautta eika lue
 * `f.date`a avaimeksi, (3) sama funktio mitataan kuudella vyohykkeella ja
 * vuorokauden rajalla.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { fmtDayKey, groupByLocalDay, localDayKey } from './fixtureDays';

// GW10, oikeat ottelut (FPL fixtures?event=10): pe 6.11. 20:00 UTC ja la 7.11. 15:00 UTC.
const ROWS = [
	{ date: '2026-11-06', datetime: '2026-11-06T20:00:00Z', home_team: 'Everton', away_team: 'Coventry' },
	{ date: '2026-11-07', datetime: '2026-11-07T15:00:00Z', home_team: 'Arsenal', away_team: 'Hull' }
];

const day = (tz: string, home: string) => {
	const g = groupByLocalDay(ROWS, tz).find(([, list]) => list.some((r) => r.home_team === home));
	return g ? fmtDayKey(g[0]) : null;
};

describe('Fixtures: paivaotsikko lukijan vyohykkeessa', () => {
	it.each([
		['Europe/Helsinki', 'Friday 6 November', 'Saturday 7 November'],
		['Europe/London', 'Friday 6 November', 'Saturday 7 November'],
		['America/New_York', 'Friday 6 November', 'Saturday 7 November'],
		['America/Sao_Paulo', 'Friday 6 November', 'Saturday 7 November'],
		['Asia/Kolkata', 'Saturday 7 November', 'Saturday 7 November'],
		['Australia/Sydney', 'Saturday 7 November', 'Sunday 8 November']
	])('%s', (tz, everton, arsenal) => {
		expect(day(tz, 'Everton')).toBe(everton);
		expect(day(tz, 'Arsenal')).toBe(arsenal);
	});

	it('vuorokauden raja: 23:30 UTC on Helsingissa jo seuraava paiva, Lontoossa ei', () => {
		expect(localDayKey('2026-11-06T23:30:00Z', '2026-11-06', 'Europe/Helsinki')).toBe('2026-11-07');
		expect(localDayKey('2026-11-06T23:30:00Z', '2026-11-06', 'Europe/London')).toBe('2026-11-06');
	});

	it('ilman hetkea (tai rikkinainen hetki) avain on API:n paiva', () => {
		expect(localDayKey('', '2026-11-06', 'Asia/Tokyo')).toBe('2026-11-06');
		expect(localDayKey('not a date', '2026-11-06', 'Asia/Tokyo')).toBe('2026-11-06');
	});

	it('otsikko avaimesta ei riipu vyohykkeesta', () => {
		expect(fmtDayKey('2026-11-07')).toBe('Saturday 7 November');
	});

	it('KUTSUPAIKKA: Fixtures.svelte ryhmittelee groupByLocalDayn kautta, ei f.date-avaimella', () => {
		const src = readFileSync(resolve(__dirname, 'components/Fixtures.svelte'), 'utf8');
		expect(src).toMatch(/let days = \$derived\(groupByLocalDay\(all\)\);/);
		expect(src).toMatch(/\{fmtDayKey\(date\)\}/);
		expect(src).not.toMatch(/const k = f\.date;/);
		expect(src).not.toMatch(/T00:00:00Z/);
	});
});
