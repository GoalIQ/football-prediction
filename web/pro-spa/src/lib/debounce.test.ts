/**
 * node --experimental-strip-types --test src/lib/debounce.test.ts
 *
 * Ei npm-riippuvuuksia (pro-spa:lla ei ole testirunneria eikä
 * node_modulesia asennettuna) — Node 22:n omalla test-runnerilla ja
 * TS-stripbyllä ajettava testi, jotta debounce.ts:n käyttäytyminen on
 * mitattu eikä vain silmämääräisesti oikea.
 */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { debounce } from './debounce.ts';

function odota(ms: number): Promise<void> {
	return new Promise((resolve) => setTimeout(resolve, ms));
}

test('nopea sarja kutsuja tuottaa TASAN yhden kutsun viimeisillä argumenteilla', async () => {
	const kutsut: number[] = [];
	const d = debounce((n: number) => kutsut.push(n), 20);
	// Simuloi "116920" kirjoittamista merkki kerrallaan: monta muutosta
	// nopeasti peräkkäin, kuten fplEntry.entry muuttuu jokaisella
	// näppäimenpainalluksella.
	d(1);
	d(11);
	d(116);
	d(1169);
	d(11692);
	d(116920);
	await odota(40);
	assert.deepEqual(kutsut, [116920], 'kirjoitussarjan piti tuottaa yksi kutsu, ei kuusi');
});

test('negatiivinen kontrolli: kaksi ERILLISTA kaytokertaa (valin yli) tuottavat kaksi kutsua', async () => {
	// Ilman tata portti voisi olla vaarin toiseenkin suuntaan: jos debounce
	// nielisi KAIKEN eika vain nopeaa sarjaa, kaksi aidosti erillista
	// kayttokertaa (esim. tallennettu entry vaihtuu, kayttaja palaa myohemmin)
	// naukyisi vain yhtena, ja se olisi vaarin paattoon suuntaan.
	const kutsut: number[] = [];
	const d = debounce((n: number) => kutsut.push(n), 20);
	d(1);
	await odota(40);
	d(2);
	await odota(40);
	assert.deepEqual(kutsut, [1, 2], 'ajallisesti erilliset kutsut eivat saa sulautua yhdeksi');
});

test('cancel() estaa odottavan kutsun (unmount-turvallisuus)', async () => {
	const kutsut: number[] = [];
	const d = debounce((n: number) => kutsut.push(n), 20);
	d(1);
	d.cancel();
	await odota(40);
	assert.deepEqual(kutsut, [], 'peruutettu kutsu ei saa silti laueta');
});

test('mutaatiokontrolli: ilman debouncea sama kirjoitussarja tuottaisi kuusi kutsua', () => {
	// Tama todistaa etta ylla oleva testi oikeasti mittaa jotain: sama
	// "kirjoitussarja" ilman debouncea (suora kutsu) tuottaa yhden eventin
	// PER MUUTOS, mika on juuri se vika jota debounce.ts korjaa.
	const kutsut: number[] = [];
	const suora = (n: number) => kutsut.push(n);
	[1, 11, 116, 1169, 11692, 116920].forEach(suora);
	assert.equal(kutsut.length, 6, 'ilman debouncea jokainen muutos on oma kutsunsa');
});
