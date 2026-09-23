import { describe, expect, it } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { extname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * PORTTI (22.9.2026, SPA-IKKUNAN-PAIVA-KIRJOITETTU-AUKI). Ilmaisikkunan
 * sulkeutumispaiva ("12 September") oli kirjoitettu kasin YHTEENTOISTA
 * merkkijonoon viidessa komponentissa (ToolsHome, ProductIntro,
 * PremiumPreview, Paywall, LoginBox, Hero) `auth.svelte.ts`:n
 * FREE_PREMIUM_UNTILin sijaan. Kaikki yhdeksan alun perin mitattua
 * (ToolsHome, ProductIntro, PremiumPreview, Paywall) olivat
 * `freePremiumWindowActive()`-vartion takana eivatka nakyneet 18.9 jalkeen,
 * mutta seuraava ikkuna avaisi uuden paivan ja jokainen unohtunut
 * merkkijono nayttaisi vaaraa paivaa kunnes joku sattuisi huomaamaan sen.
 * Kaksi lisaa (Hero, LoginBox) loytyi vasta tallä skannauksella - ne EIVAT
 * olleet alkuperaisen kasin tehdyn mittauksen listalla, mika on tasan se
 * riski jota kasin nimetty lista ei koskaan poista (saanto 6a, sama
 * vikaluokka jonka fp:n test_free_window_surface_scope.py korjasi
 * paistetuille sivuille 18.9: pintajoukko on johdettava, ei lueteltava).
 *
 * Korjaus: kaikki lukevat nyt `freePremiumUntilLabel()`:n, joka johtaa
 * paivan `FREE_PREMIUM_UNTIL`-aikaleimasta (sama muoto kuin backendin
 * `src/free_window.day_label()`: '%d %B' ilman johtavaa nollaa).
 *
 * Tama testi SKANNAA koko `src/lib` + `src/routes`-puun (ei kasin
 * nimettya tiedostolistaa) kuukausi+paiva-merkkijonon varalta jokaisessa
 * tiedostossa PAITSI `auth.svelte.ts`:ssa, joka on ainoa sallittu lahde.
 */

const LIB_ROOT = fileURLToPath(new URL('.', import.meta.url)); // .../src/lib/
const SRC_ROOT = fileURLToPath(new URL('../', import.meta.url)); // .../src/

const SOURCE_OF_TRUTH = 'auth.svelte.ts';
const SKIP_DIRS = new Set(['node_modules', '.svelte-kit', 'build']);
const SCAN_EXTS = new Set(['.svelte', '.ts']);

const MONTHS =
	'January|February|March|April|May|June|July|August|September|October|November|December';
const DATE_RE = new RegExp(`\\b\\d{1,2} (?:${MONTHS})\\b`);

function walk(dir: string, out: string[] = []): string[] {
	for (const entry of readdirSync(dir)) {
		if (SKIP_DIRS.has(entry)) continue;
		const p = join(dir, entry);
		const st = statSync(p);
		if (st.isDirectory()) {
			walk(p, out);
		} else if (SCAN_EXTS.has(extname(entry)) && !entry.endsWith('.test.ts')) {
			out.push(p);
		}
	}
	return out;
}

/** Poistaa HTML- ja lohkokommentit kokonaan, ja RIVIKOMMENTIT vain kun `//`
 *  on rivin ALUSSA (whitespacen jalkeen). Jalkimmainen on tarkoituksella
 *  suppea: taman repon koodityyli kirjoittaa selittavat kommentit omille
 *  riveilleen, ja `URL`-kirjaimet kuten `https://pro.goaliq.app/` sisaltavat
 *  `//`:n KESKELLA koodiriviä - laaja `\/\/.*$` -poisto olisi syonyt saman
 *  rivin lopun (mahdollisen paivamaaran mukaan lukien) ja tehnyt portista
 *  sokean juuri sille mita se on olemassa nakemaan. Mutaatiokontrolli alla.
 */
function stripComments(src: string): string {
	return src
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/\/\*[\s\S]*?\*\//g, '')
		.replace(/^[ \t]*\/\/.*$/gm, '');
}

describe('ilmaisikkunan paiva ei ole kasin kirjoitettu SPA:n lahdekoodissa', () => {
	const files = walk(SRC_ROOT).filter((f) => !f.endsWith(`/${SOURCE_OF_TRUTH}`));

	it('skannaus loytaa tiedostoja (kontrolli itse mekanismille)', () => {
		// Jos glob/walk joskus alkaisi palauttaa tyhjan listan (esim. polku
		// muuttuu tai .svelte-kit-hakemisto niellaan vahingossa), alla oleva
		// testi lapaisisi TYHJANA eika mittaisi mitaan. Tama huomaisi sen.
		expect(files.length).toBeGreaterThan(20);
	});

	it('yksikaan tiedosto FREE_PREMIUM_UNTILin lukijan ulkopuolella ei kanna kuukausi+paiva-merkkijonoa', () => {
		const osumat: string[] = [];
		for (const f of files) {
			const koodi = stripComments(readFileSync(f, 'utf8'));
			if (DATE_RE.test(koodi)) osumat.push(f.slice(SRC_ROOT.length));
		}
		expect(osumat, `paivamaara kovakoodattu tiedostoissa: ${osumat.join(', ')}`).toEqual([]);
	});

	it('NEGATIIVINEN KONTROLLI: skanneri LOYTAA kovakoodatun paivan kun sellainen on', () => {
		// Todistaa etta ylla oleva testi oikeasti mittaa jotain eika lapaisisi
		// tyhjana riippumatta sisallosta (muisti: kontrolli-lapaisi-tyhjana).
		const rikki = "<h2>Premium is free until 12 September</h2>";
		expect(DATE_RE.test(stripComments(rikki))).toBe(true);
	});

	it('MUTAATIOKONTROLLI: kommenttien poisto ei syo koodiriviä jolla on URL', () => {
		// Jos stripComments joskus muutettaisiin takaisin laajaksi
		// `\/\/.*$`-poistoksi, tama huomaisi sen: paivamaara SAMASSA
		// tiedostossa mutta ERI rivilla kuin URL ei saa kadota.
		const rikki = [
			"const PRO_URL = 'https://pro.goaliq.app/';",
			"const s = 'Premium is free until 12 September';"
		].join('\n');
		expect(DATE_RE.test(stripComments(rikki))).toBe(true);
	});

	it('kaikki neljä alkuperäistä + kaksi lisälöydöstä käyttävät nyt lukijaa', () => {
		// Kutsupaikkaportti (18.9-oppi: gate-substring-osuma-on-sokea) - ei
		// riita etta funktio on olemassa, jokaisen aiemmin syyllisen
		// tiedoston on kutsuttava sita.
		const komponentit = [
			'components/ToolsHome.svelte',
			'components/ProductIntro.svelte',
			'components/PremiumPreview.svelte',
			'components/Paywall.svelte',
			'components/LoginBox.svelte',
			'components/Hero.svelte'
		];
		for (const rel of komponentit) {
			const koodi = readFileSync(join(LIB_ROOT, rel), 'utf8');
			expect(koodi, `${rel} ei tuo freePremiumUntilLabel`).toContain('freePremiumUntilLabel');
		}
	});
});
