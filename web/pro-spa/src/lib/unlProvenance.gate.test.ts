/** Portti: seuramallin alkupera-alaviite (Provenance) ei nay maajoukkue-ennusteen alla.
 *
 * 🔴 MIKSI (26.9, julkaisutarkistajan anonyymi renderointi
 * pro.goaliq.app/matches/predict?league=INT-Nations+League&home=England&away=Spain):
 * sivun alareunassa luki "Powered by the same match model behind our published,
 * pre-match-logged predictions: 49% correct 1X2 across 609 logged matches", kun
 * saman sivun ingressi sanoo "National teams have their own model ... These
 * predictions aren't in the public track record". Maajoukkueilla on oma malli
 * (src/data/nations_league.py) eika niita kirjata lokiin, joten alaviite oli
 * epatosi juuri silla nakymalla.
 *
 * Liiga on Predictin omaa tilaa (valitsin ei paivita URL:ia), joten ToolsHome
 * ei voi paatella sita osoitteesta: Predict kertoo sen `onNationalChange`lla.
 * Kutsupaikat vartioidaan lahteesta (ei komponenttirenderointia SPA:n testeissa).
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { findLeague, LEAGUES } from './leagues';

const read = (f: string) => readFileSync(resolve(__dirname, 'components', f), 'utf-8');
const noComments = (s: string) =>
	s.replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, ' ')).replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));

describe('Provenance ei vaita seuramallin lokia maajoukkueille', () => {
	it('maajoukkueliiga on merkitty (lukija jonka Predict kayttaa)', () => {
		expect(findLeague('INT-Nations League')?.national).toBe(true);
		expect(LEAGUES.filter((l) => !l.national).length).toBeGreaterThan(0);
	});

	it('Predict kertoo maajoukkuetilan ylospain samasta `national`-arvosta', () => {
		const src = noComments(read('Predict.svelte'));
		expect(src).toMatch(/const national = \$derived\(!!findLeague\(league\)\?\.national\)/);
		expect(src).toMatch(/\$effect\(\(\) => \{\s*onNationalChange\?\.\(national\);\s*\}\)/);
	});

	it('ToolsHome: Provenance vain kun Predict ei ole maajoukkuetilassa', () => {
		const src = noComments(read('ToolsHome.svelte'));
		expect(src).toMatch(/onNationalChange=\{\(n\) => \(predictNational = n\)\}/);
		expect(src).toMatch(
			/hideProvenance = \$derived\(\s*segment === 'matches' && matchesView === 'predict' && predictNational\s*\)/
		);
		const markup = src.slice(src.lastIndexOf('</script>'));
		const i = markup.indexOf('<Provenance />');
		expect(i).toBeGreaterThan(-1);
		// Ainoa Provenance-renderointi on ehdon sisalla.
		expect(markup.indexOf('<Provenance />', i + 1)).toBe(-1);
		expect(markup.slice(0, i).trimEnd().endsWith('{#if !hideProvenance}')).toBe(true);
	});
});
