/**
 * XP-HORISONTIN-ALKU (29.9.2026): actionableRows mitataan kauden vaiheilla
 * (saanto 6a kohta 3): ennen deadlinea, kesken kierroksen, ilman metaa.
 */
import { describe, expect, it } from 'vitest';
import { actionableRows } from './gameweek';

const rows = [6, 7, 8, 9].map((gw) => ({ gw, xp: gw }));

describe('actionableRows', () => {
	it('ennen deadlinea kaikki rivit', () => {
		expect(actionableRows({ next_gameweek: 6, deadline_gameweek: 6 }, rows).map((r) => r.gw)).toEqual([6, 7, 8, 9]);
	});
	it('kesken kierroksen lukittu kierros pois', () => {
		expect(actionableRows({ next_gameweek: 6, deadline_gameweek: 7 }, rows).map((r) => r.gw)).toEqual([7, 8, 9]);
	});
	it('ilman deadline-kenttaa next_gameweek (vanha payload)', () => {
		expect(actionableRows({ next_gameweek: 6 }, rows).map((r) => r.gw)).toEqual([6, 7, 8, 9]);
	});
	it('ilman metaa ei suodateta eika kaaduta', () => {
		expect(actionableRows(null, rows)).toHaveLength(4);
		expect(actionableRows({ deadline_gameweek: 7 }, undefined)).toEqual([]);
	});
});
