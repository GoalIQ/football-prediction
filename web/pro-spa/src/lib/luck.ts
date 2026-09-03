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
/**
 * MITATTU, ei arvattu. Ensimmainen versio vertasi pisteita absoluuttisiin
 * rajoihin (haul >= 10, blank <= 2) ja xP:ta rajaan 5.0. Aineistossa
 * (GW1-GW2, 607 pelaaja-kierrosta) xP >= 5.0 tayttyi 4 kertaa 607:sta ja
 * suurin freeze oli 5.78 - kynnys ei jakanut populaatiota vaan oli seina,
 * ja merkin sai 61 % pelaajista (6,8 / XI). Syy oli skaalavirhe: xP:n
 * mediaani on ~2 kun "haul" on 10+.
 *
 * Nyt tuomio luetaan pelaajan omasta POIKKEAMASTA. Kynnykset ovat
 * epasymmetriset koska jakauma on: alisuoritus on rajattu, ylisuoritus ei
 * (p05 -2.9, p50 -0.1, p95 +7.0). Valitut arvot: 1,6 merkkia / XI, 43 yli /
 * 48 alle. Jos naita muuttaa, aja mittaus uudelleen.
 *
 * `tests/test_luck_parity.py` kaatuu jos nama eroavat mobiilista.
 */
export const LUCK_OVER_DIFF = 6;
export const LUCK_UNDER_DIFF = 2.5;

/**
 * Kaksi tuomiota, ei nelja. "Malli osui" ja "ansaittu nolla" poistettiin
 * mittauksen perusteella: ensimmainen oli mahdoton, toinen oli perustaso
 * (125 osumaa 151:sta).
 */
export type LuckVerdict = 'lucky' | 'robbed' | null;

/**
 * @param xp     PINNATTU ennuste (deadline-freeze), pelaajan oma luku.
 * @param actual Toteutuneet pisteet, pelaajan oma luku.
 *
 * 🔴 Molemmat KERTOIMETTOMIA: kapteenin tuplaus kaksinkertaistaisi poikkeaman
 * automaattisesti. Kerroin kuuluu summaan, ei tuomioon.
 */
export function luckVerdict(
	xp: number | null | undefined,
	actual: number | null | undefined
): LuckVerdict {
	if (typeof xp !== 'number' || typeof actual !== 'number') return null;
	const diff = actual - xp;
	if (diff >= LUCK_OVER_DIFF) return 'lucky';
	if (diff <= -LUCK_UNDER_DIFF) return 'robbed';
	return null;
}

export const LUCK_MARK: Record<Exclude<LuckVerdict, null>, string> = {
	lucky: '🎲',
	robbed: '💀'
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

/**
 * Saako paattyneen kierroksen luvut (toteuma + deadline-freeze) nayttaa, kun
 * pinta katsoo kierrosta `selGw`?
 *
 * 🔴 TAMA ON AINOA LUKIJA. Pitchin kartta rakennettiin `last_finished`
 * -lohkosta ilman ehtoa, ja silloin GW2:n pisteet nakyivat GW3:n xP:n
 * paikalla. Ehto ei ole "kierros juuri paattyi": FPL pitaa entryn picksit
 * edellisessa kierroksessa deadlineen asti, joten `picksGw ===
 * lastFinished.gw` on totta koko suunnitteluikkunan ajan (3.9.2026).
 *
 * Sama funktio mobiilissa: `goaliq-app/lib/fantasyDisplay.ts`.
 */
export function settledGwReadable(
	selGw: number | null | undefined,
	luckGw: number | null | undefined,
	sameSquad: boolean
): boolean {
	if (!sameSquad || luckGw == null) return false;
	if (selGw == null) return true;
	return selGw === luckGw;
}
