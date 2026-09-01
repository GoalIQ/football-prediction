/**
 * $lib/luck — LUCK-PITCH (1.9): mallin tuomio kentalle.
 *
 * PEILI mobiilin `lib/fantasyDisplay.ts`:lle. Sama saanto ajetaan kolmella
 * pinnalla (mobiilin pitch, tama, jakokortit), ja jos kynnys elaa vain yhden
 * pinnan if-lauseessa, pinnat erkanevat hiljaa. `tests/test_luck_parity.py`
 * lukee molemmat tiedostot ja kaatuu jos vakiot eroavat.
 *
 * 10 ja 2 ovat FPL-yhteison omat rajat (haul / blank), 5.0 on xP:n taso jolla
 * pelaaja on valittu NIMENOMAAN tuottamaan. Ne eivat ole viritettyja dataan.
 */
export const LUCK_HAUL_PTS = 10;
export const LUCK_BLANK_PTS = 2;
export const LUCK_HIGH_XP = 5;

export type LuckVerdict = 'called' | 'lucky' | 'robbed' | 'cold' | null;

/**
 * @param xp     PINNATTU ennuste (deadline-freeze), pelaajan oma luku.
 * @param actual Toteutuneet pisteet, pelaajan oma luku.
 *
 * 🔴 Molemmat ovat KERTOIMETTOMIA. Kapteenin tuplaus kertoo kapteeninauhasta,
 * ei siita osuiko malli, ja tuplattuna sama suoritus ylittaisi haul-rajan
 * puolet helpommin. Kerroin kuuluu summaan, ei tuomioon.
 *
 * `null` on tarkoituksellinen enemmisto: jos jokainen pelaaja saa merkin,
 * merkki on koriste eika tuomio.
 */
export function luckVerdict(
	xp: number | null | undefined,
	actual: number | null | undefined
): LuckVerdict {
	if (typeof xp !== 'number' || typeof actual !== 'number') return null;
	const expected = xp >= LUCK_HIGH_XP;
	if (actual >= LUCK_HAUL_PTS) return expected ? 'called' : 'lucky';
	if (actual <= LUCK_BLANK_PTS) return expected ? 'robbed' : 'cold';
	return null;
}

export const LUCK_MARK: Record<Exclude<LuckVerdict, null>, string> = {
	called: '🎯',
	lucky: '🎲',
	robbed: '💀',
	cold: '🧊'
};

export interface SquadLuck {
	points: number;
	xp: number;
	diff: number;
	n: number;
}

/**
 * Rivin summa kertoimineen. `null` kun yksikaan rivi ei kelpaa: tyhja summa
 * olisi "0 pistetta, 0 xP" eli vaite kierroksesta jota ei ole pelattu.
 *
 * 🔴 KUTSUJAN VASTUU: tama on rivin summa SELLAISENA KUIN SE ANNETAAN. Jos
 * kayttaja on muokannut XI:ta what-if-tilassa, summa ei ole hanen
 * kierroksensa tulos eika sita saa otsikoida pisteinaan.
 */
export function squadLuck<T>(
	rows: readonly { item: T; xp: number; actual: number }[],
	multiplierOf: (item: T) => number
): SquadLuck | null {
	if (rows.length === 0) return null;
	let points = 0;
	let xp = 0;
	for (const r of rows) {
		const m = multiplierOf(r.item);
		points += r.actual * m;
		xp += r.xp * m;
	}
	const round2 = (n: number) => Math.round(n * 100) / 100;
	return { points: round2(points), xp: round2(xp), diff: round2(points - xp), n: rows.length };
}
