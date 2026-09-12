/** Fixture swing -luku nakyviin (12.9.2026).
 *
 * Swing on high xP miinus low xP, ja lista jarjestetaan sen mukaan
 * (`FixtureSwing.svelte`). Sarake naytti aiemmin suhdelukua (high / low),
 * joten jarjestys ja nakyva luku olivat kaksi eri lukua: 0.5 -> 1.5 nakyi
 * "3.0x" ja 3.0 -> 5.0 "1.7x", vaikka jalkimmainen oli listalla ylempana.
 * Sarake ja jakokortti kayttavat nyt tata samaa funktiota samasta kentasta.
 *
 * Etumerkki paatetaan pyoristetysta arvosta, jotta 0.04 ei nay "+0.0".
 * Portti: tests/test_fixture_swing_column.py */
export function formatSwing(swing: number): string {
	const s = swing.toFixed(1);
	return Number(s) > 0 ? `+${s}` : s;
}

/** Swing NAKYVISTA luvuista (12.9.2026 render-tarkistus). Taulukko nayttaa Low- ja
 * High-arvot yhdella desimaalilla, ja lukija laskee rivin paassaan: Gibbs-White
 * 3.4 -> 5.8 nakyi "+2.3", koska ero laskettiin pyoristamattomista arvoista
 * (5.76 - 3.44 = 2.32). Nyt swing = pyoristetty High miinus pyoristetty Low, ja
 * pyoristys on sama `toFixed(1)` jota solut kayttavat. Tuloskin pyoristetaan,
 * ettei 5.8 - 3.4 = 2.3999999999999995 jarjesty eri paikkaan kuin 2.4.
 * Portti: tests/test_fixture_swing_column.py */
export function swingOf(loXp: number, hiXp: number): number {
	return Number((Number(hiXp.toFixed(1)) - Number(loXp.toFixed(1))).toFixed(1));
}
